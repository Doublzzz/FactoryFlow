"""Durable content-addressed JSON; exclusive publication, verified reads, no overwrite."""

import hashlib
import os
import re
import tempfile
from pathlib import Path

from factoryflow.kernel.contracts import BusinessError


class LocalEvidenceStore:
    def __init__(self, root: Path):
        self.root = root

    def put(self, content: bytes) -> str:
        digest = hashlib.sha256(content).hexdigest()
        if not self.root.is_dir():
            raise BusinessError("OBJECT_STORE_UNAVAILABLE", 503)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.root, prefix="staging-", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, self.root / f"{digest}.json")
            except FileExistsError:
                pass
            if self.read(digest) != content:
                raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return digest

    def read(self, digest: str) -> bytes:
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
        path = self.root / f"{digest}.json"
        if path.is_symlink():
            raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
        try:
            content = path.read_bytes()
        except OSError:
            raise BusinessError("EVIDENCE_UNAVAILABLE", 503) from None
        if hashlib.sha256(content).hexdigest() != digest:
            raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
        return content
