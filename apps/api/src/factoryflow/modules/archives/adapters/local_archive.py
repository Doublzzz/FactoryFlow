"""Deterministic ZIP and exclusive, verified local work-file publication."""

import io
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from factoryflow.kernel.contracts import BusinessError

_LIMIT = 50 * 1024 * 1024
_MANIFEST = "清单.json"
_DEVICE = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)", re.I)


def canonical_json(value: dict) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except ValueError, TypeError, UnicodeError:
        raise BusinessError("ARCHIVE_PATH_INVALID") from None


def _contents(files: dict[str, bytes], manifest: dict) -> dict[str, bytes]:
    if len(files) > 50:
        raise BusinessError("ARCHIVE_PATH_INVALID")
    result = dict(files)
    seen = {_MANIFEST.casefold()}
    directories = set()
    directory_names = {}
    for name, content in files.items():
        if not isinstance(name, str) or not isinstance(content, bytes):
            raise BusinessError("ARCHIVE_PATH_INVALID")
        parts = name.split("/")
        if any(
            not p
            or p in {".", ".."}
            or p.rstrip(". ") != p
            or re.search(r'[<>:"\\|?*\x00-\x1f\x7f]', p)
            or _DEVICE.match(p)
            for p in parts
        ):
            raise BusinessError("ARCHIVE_PATH_INVALID")
        folded = name.casefold()
        if folded in seen:
            raise BusinessError("ARCHIVE_PATH_INVALID")
        seen.add(folded)
        directories.update("/".join(parts[:i]).casefold() for i in range(1, len(parts)))
        for index in range(1, len(parts)):
            directory = "/".join(parts[:index])
            previous = directory_names.setdefault(directory.casefold(), directory)
            if previous != directory:
                raise BusinessError("ARCHIVE_PATH_INVALID")
    if seen & directories:
        raise BusinessError("ARCHIVE_PATH_INVALID")
    result[_MANIFEST] = canonical_json(manifest)
    if sum(map(len, result.values())) > _LIMIT:
        raise BusinessError("ARCHIVE_PATH_INVALID")
    return result


def build_zip(files: dict[str, bytes], manifest: dict) -> bytes:
    content = _contents(files, manifest)
    stream = io.BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        for name in sorted(content):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, content[name])
    return stream.getvalue()


def _safe(path: Path) -> None:
    """Reject every existing ancestor reparse point, including Windows junctions."""
    for ancestor in [*reversed(path.parents), path]:
        try:
            metadata = ancestor.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode) or (
            getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise BusinessError("ARCHIVE_COPY_CONFLICT", 409)


class LocalArchiveStore:
    def __init__(self, root: Path | None):
        self.root = root

    def _directory(self, organization_id: str, batch_id: str) -> Path:
        if self.root is None:
            raise BusinessError("ARCHIVE_NOT_CONFIGURED", 503)
        try:
            if not self.root.is_absolute() or ".." in self.root.parts:
                raise ValueError
            org, batch = str(UUID(organization_id)), str(UUID(batch_id))
            if org != organization_id or batch != batch_id:
                raise ValueError
        except ValueError, TypeError, AttributeError:
            raise BusinessError("ARCHIVE_PATH_INVALID") from None
        directory = self.root / org / batch
        _safe(directory)
        return directory

    @staticmethod
    def _verify(directory: Path, content: dict[str, bytes]) -> bool:
        _safe(directory)
        if not directory.exists():
            return False
        if not directory.is_dir():
            raise BusinessError("ARCHIVE_COPY_CONFLICT", 409)
        expected_dirs = set()
        for name in content:
            parts = name.split("/")
            expected_dirs.update("/".join(parts[:i]) for i in range(1, len(parts)))
        actual_files, actual_dirs = set(), set()
        for parent, dirs, names in os.walk(directory, followlinks=False):
            for name in [*dirs, *names]:
                path = Path(parent) / name
                _safe(path)
                relative = path.relative_to(directory).as_posix()
                if name in dirs:
                    actual_dirs.add(relative)
                else:
                    if not stat.S_ISREG(path.lstat().st_mode):
                        raise BusinessError("ARCHIVE_COPY_CONFLICT", 409)
                    actual_files.add(relative)
        if actual_files != set(content) or actual_dirs != expected_dirs:
            raise BusinessError("ARCHIVE_COPY_CONFLICT", 409)
        for name, value in content.items():
            path = directory / name
            _safe(path)
            if path.stat().st_size != len(value) or path.read_bytes() != value:
                raise BusinessError("ARCHIVE_COPY_CONFLICT", 409)
        return True

    def available(
        self, organization_id: str, batch_id: str, files: dict[str, bytes], manifest: dict
    ) -> bool:
        try:
            return self._verify(
                self._directory(organization_id, batch_id), _contents(files, manifest)
            )
        except OSError:
            raise BusinessError("ARCHIVE_COPY_CONFLICT", 409) from None

    def publish(
        self, organization_id: str, batch_id: str, files: dict[str, bytes], manifest: dict
    ) -> str:
        staging = None
        try:
            directory = self._directory(organization_id, batch_id)
            content = _contents(files, manifest)
            if self._verify(directory, content):
                return f"{organization_id}/{batch_id}"
            _safe(directory.parent)
            directory.parent.mkdir(parents=True, exist_ok=True)
            _safe(directory.parent)
            staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=directory.parent))
            for name, value in content.items():
                path = staging / name
                _safe(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                _safe(path)
                with path.open("xb") as stream:
                    stream.write(value)
                    stream.flush()
                    os.fsync(stream.fileno())
            self._verify(staging, content)
            _safe(directory)
            try:
                os.rename(staging, directory)
                staging = None
            except OSError:
                if not self._verify(directory, content):
                    raise
            if not self._verify(directory, content):
                raise BusinessError("ARCHIVE_COPY_FAILED", 503)
            return f"{organization_id}/{batch_id}"
        except OSError:
            raise BusinessError("ARCHIVE_COPY_FAILED", 503) from None
        finally:
            if staging is not None:
                # Only the exact unique directory created by this call may be removed.
                try:
                    _safe(staging)
                    if (
                        staging.is_absolute()
                        and staging.parent == directory.parent
                        and staging.name.startswith(".staging-")
                    ):
                        for parent, dirs, names in os.walk(staging, followlinks=False):
                            for name in [*dirs, *names]:
                                _safe(Path(parent) / name)
                        shutil.rmtree(staging)
                except OSError:
                    raise BusinessError("ARCHIVE_COPY_FAILED", 503) from None
