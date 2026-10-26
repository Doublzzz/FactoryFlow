"""Build an allowlisted offline Windows package into a NEW directory outside the repository."""

import argparse
import csv
import hashlib
import importlib.metadata as metadata
import io
import json
import shutil
import sys
import tomllib
import zipfile
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]

# This application processes still images and PDFs, never video.
OCR_VIDEO_PLUGIN = {
    "distribution": "opencv-python",
    "version": "5.0.0.93",
    "path": "cv2/opencv_videoio_ffmpeg500_64.dll",
    "sha256": "7aabff029d1fa47cf56ede4dbbe05dc62da3208f07cd16471d4c966a33f9aa31",
    "reason": "Unused optional FFmpeg video backend omitted from the application runtime.",
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def tree(source, destination):
    shutil.copytree(
        source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".git")
    )


def python_runtime(source, destination):
    source = source.resolve()
    destination.mkdir(parents=True)
    for path in source.iterdir():
        if path.is_file() and (
            path.suffix.lower() in {".exe", ".dll", ".txt"} or path.name == "BUILD"
        ):
            shutil.copy2(path, destination / path.name)
        elif path.name in {"DLLs", "tcl"}:
            tree(path, destination / path.name)
        elif path.name == "Lib":
            shutil.copytree(
                path,
                destination / "Lib",
                ignore=shutil.ignore_patterns(
                    "site-packages", "__pycache__", "*.pyc", "test", "tests", "ensurepip", "idlelib"
                ),
            )


def dependency_files(site, requirements, python_version=None):
    installed = {
        canonicalize_name(d.metadata["Name"]): d for d in metadata.distributions(path=[str(site)])
    }
    selected, visited, pending = {}, set(), [Requirement(r) for r in requirements]
    markers = (
        {}
        if python_version is None
        else {
            "python_version": ".".join(python_version.split(".")[:2]),
            "python_full_version": python_version,
        }
    )
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        key = name, tuple(sorted(requirement.extras))
        if key in visited:
            continue
        visited.add(key)
        if name not in installed:
            raise ValueError(f"Dependency not installed: {name}")
        distribution = installed[name]
        if requirement.specifier and distribution.version not in requirement.specifier:
            raise ValueError(f"Pinned dependency mismatch: {name}")
        selected[name] = distribution
        for value in distribution.requires or []:
            child = Requirement(value)
            if child.marker is None or any(
                child.marker.evaluate(markers | {"extra": extra})
                for extra in requirement.extras | {""}
            ):
                pending.append(child)
    files = []
    for distribution in selected.values():
        record = distribution.read_text("RECORD")
        if not record:
            raise ValueError(f"Dependency file inventory missing: {distribution.metadata['Name']}")
        # Distribution.files filters missing paths in Python 3.14; inspect the raw inventory.
        inventory = [Path(row[0]) for row in csv.reader(io.StringIO(record)) if row]
        if not inventory:
            raise ValueError(f"Dependency file inventory empty: {distribution.metadata['Name']}")
        for relative in inventory:
            if (
                ".." in relative.parts
                or "__pycache__" in relative.parts
                or relative.suffix == ".pyc"
            ):
                continue
            source = Path(distribution.locate_file(relative))
            if not source.is_file():
                raise ValueError(f"Dependency file missing: {relative}")
            files.append((source, relative))
    return {name: d.version for name, d in sorted(selected.items())}, files


def copy_dependencies(files, destination, *, omitted=()):
    destination.mkdir(parents=True, exist_ok=True)
    for source, relative in files:
        if relative.as_posix() in omitted:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative.name == "RECORD" and omitted:
            rows = list(csv.reader(io.StringIO(source.read_text(encoding="utf-8"))))
            kept = [row for row in rows if not row or row[0] not in omitted]
            if kept != rows:
                with target.open("w", encoding="utf-8", newline="") as stream:
                    csv.writer(stream, lineterminator="\n").writerows(kept)
                continue
        shutil.copy2(source, target)


def build(
    output,
    ocr_base,
    ocr_site,
    vc_redist,
    *,
    notices_directory,
    postgres_root=None,
    web_directory=None,
):
    output = output.resolve()
    archive = output.parent / (output.name + ".zip")
    receipt_path = output.parent / (output.name + "-build.json")
    if output.exists() or output.is_relative_to(ROOT.resolve()):
        raise ValueError("Output must be a new directory outside the project")
    if archive.exists():
        raise ValueError("Output ZIP already exists")
    if receipt_path.exists():
        raise ValueError("Output build receipt already exists")
    pg = postgres_root or ROOT / ".tools/postgresql-18.6-4/pgsql"
    web = web_directory or ROOT / "apps/web/dist"
    primary_site = Path(sys.prefix) / "Lib/site-packages"
    required_directories = (
        Path(sys.base_prefix),
        Path(sys.base_prefix) / "Lib",
        primary_site,
        ocr_base,
        ocr_base / "Lib",
        ocr_site,
        ROOT / "apps/api/src/factoryflow",
        ROOT / "migrations",
        web,
        notices_directory,
        *(pg / name for name in ("bin", "lib", "share")),
    )
    for path in required_directories:
        if not path.is_dir():
            raise ValueError(f"Required source directory missing: {path}")
    pg_licenses = (
        ("COPYING",)
        if (pg / "COPYING").is_file()
        else ("server_license.txt", "commandlinetools_3rd_party_licenses.txt")
    )
    required_files = (
        ROOT / "LICENSE",
        ROOT / "pyproject.toml",
        ROOT / "alembic.ini",
        ROOT / "scripts/factory-local.py",
        ROOT / "scripts/install-offline.py",
        ROOT / "docs/FACTORY-OFFLINE-GUIDE.txt",
        ROOT / "docs/FACTORY-OFFLINE-GUIDE-en.txt",
        Path(sys.base_prefix) / "python.exe",
        ocr_base / "python.exe",
        notices_directory / "README.md",
        notices_directory / "inventory.json",
        *(pg / name for name in pg_licenses),
        *((vc_redist,) if vc_redist else ()),
    )
    for path in required_files:
        if not path.is_file():
            raise ValueError(f"Required source file missing: {path}")
    if "MIT License" not in (ROOT / "LICENSE").read_text(encoding="utf-8"):
        raise ValueError("Project LICENSE must contain the MIT License")
    with (ROOT / "pyproject.toml").open("rb") as stream:
        requirements = tomllib.load(stream)["project"]["dependencies"]
    primary, primary_files = dependency_files(primary_site, requirements)
    ocr, ocr_files = dependency_files(
        ocr_site,
        ["rapidocr==3.9.2", "onnxruntime==1.30.0", "pillow==12.1.1"],
        "3.14.7",
    )
    omissions = []
    if OCR_VIDEO_PLUGIN["distribution"] in ocr:
        if ocr[OCR_VIDEO_PLUGIN["distribution"]] != OCR_VIDEO_PLUGIN["version"]:
            raise ValueError("OpenCV video omission requires the reviewed package version")
        plugin = ocr_site / OCR_VIDEO_PLUGIN["path"]
        if not plugin.is_file() or digest(plugin) != OCR_VIDEO_PLUGIN["sha256"]:
            raise ValueError("OpenCV video plugin differs from the reviewed bytes")
        omissions.append(OCR_VIDEO_PLUGIN.copy())
    output.mkdir(parents=True)
    app = output / "app"
    app.mkdir()
    python_runtime(Path(sys.base_prefix), app / "runtime/python")
    python_runtime(ocr_base, app / "runtime/ocr")
    copy_dependencies(primary_files, app / "runtime/python/Lib/site-packages")
    copy_dependencies(
        ocr_files,
        app / "runtime/ocr/Lib/site-packages",
        omitted=tuple(item["path"] for item in omissions),
    )
    tree(ROOT / "apps/api/src/factoryflow", app / "runtime/python/Lib/site-packages/factoryflow")
    for directory in ("bin", "lib", "share"):
        tree(pg / directory, app / "runtime/postgresql" / directory)
    # Python's supplied redistributable C runtime also serves the local PostgreSQL executables.
    for path in (app / "runtime/python").glob("vcruntime*.dll"):
        shutil.copy2(path, app / "runtime/postgresql/bin" / path.name)
    tree(web, app / "apps/web/dist")
    shutil.copy2(ROOT / "LICENSE", app / "LICENSE")
    shutil.copy2(ROOT / "LICENSE", output / "LICENSE")
    tree(notices_directory, app / "third-party")
    (app / "third-party/postgresql").mkdir(exist_ok=True)
    for name in pg_licenses:
        shutil.copy2(pg / name, app / "third-party/postgresql" / name)
    tree(ROOT / "migrations", app / "migrations")
    shutil.copy2(ROOT / "alembic.ini", app / "alembic.ini")
    (app / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/factory-local.py", app / "scripts/factory-local.py")
    shutil.copy2(ROOT / "scripts/install-offline.py", output / "install.py")
    shutil.copy2(ROOT / "docs/FACTORY-OFFLINE-GUIDE.txt", output / "使用说明.txt")
    shutil.copy2(ROOT / "docs/FACTORY-OFFLINE-GUIDE-en.txt", output / "Read me.txt")
    if vc_redist:
        (output / "运行库").mkdir()
        shutil.copy2(vc_redist, output / "运行库/VC_redist.x64.exe")
    commands = {
        "启动工厂软件": "start",
        "停止工厂软件": "stop",
        "备份工厂数据": "backup",
        "恢复工厂备份": "restore",
        "查看运行状态": "status",
        "Start FactoryFlow": "start",
        "Stop FactoryFlow": "stop",
        "Back Up Data": "backup",
        "Restore Backup": "restore",
        "Check Status": "status",
    }
    for name, action in commands.items():
        language = "en" if name.isascii() else "zh-CN"
        content = (
            "@echo off\r\nchcp 65001 >nul\r\nsetlocal\r\n"
            '"%~dp0runtime\\python\\python.exe" -I -X utf8 '
            '"%~dp0scripts\\factory-local.py" '
            + action
            + " --language "
            + language
            + "\r\npause\r\n"
        )
        (app / (name + ".cmd")).write_text(content, encoding="utf-8", newline="")
    setup = (
        "@echo off\r\nchcp 65001 >nul\r\nsetlocal\r\n"
        "echo 正在校验并安装 FactoryFlow 离线版，请稍候...\r\n"
        '"%~dp0app\\runtime\\python\\python.exe" -I -X utf8 "%~dp0install.py"\r\n'
        "if errorlevel 1 echo 如提示缺少 MSVCP 或 VCRUNTIME，请按使用说明中的运行库步骤处理。\r\n"
        "pause\r\n"
    )
    (output / "安装.cmd").write_text(setup, encoding="utf-8", newline="")
    english_setup = (
        "@echo off\r\nchcp 65001 >nul\r\nsetlocal\r\n"
        "echo Verifying and installing FactoryFlow. Please wait...\r\n"
        '"%~dp0app\\runtime\\python\\python.exe" -I -X utf8 "%~dp0install.py" --language en\r\n'
        "if errorlevel 1 echo Missing MSVCP or VCRUNTIME? See the runtime steps in Read me.txt.\r\n"
        "pause\r\n"
    )
    (output / "Install.cmd").write_text(english_setup, encoding="utf-8", newline="")
    if vc_redist:
        (output / "Install Runtime.cmd").write_text(
            '@echo off\r\nchcp 65001 >nul\r\n"%~dp0运行库\\VC_redist.x64.exe"\r\npause\r\n',
            encoding="utf-8",
            newline="",
        )
    files = {
        str(p.relative_to(app)).replace("\\", "/"): digest(p)
        for p in sorted(app.rglob("*"))
        if p.is_file()
    }
    identifier = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]
    manifest = {
        "kind": "factoryflow-offline-v1",
        "build_id": identifier,
        "platform": "Windows 10/11 x64",
        "python": sys.version.split()[0],
        "postgresql": "18.6",
        "dependencies": primary,
        "ocr_dependencies": ocr,
        "omitted_optional_components": omissions,
        "files": files,
    }
    (app / "bundle.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                z.write(path, str(path.relative_to(output)))
    receipt = {
        "package": str(archive),
        "sha256": digest(archive),
        "build_id": identifier,
        "files": len(files),
        "bytes": archive.stat().st_size,
        "private_business_data": False,
        "network_required_on_target": False,
    }
    with receipt_path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ocr-base", type=Path, required=True)
    parser.add_argument("--ocr-site", type=Path, required=True)
    parser.add_argument("--vc-redist", type=Path)
    parser.add_argument("--postgres-root", type=Path)
    parser.add_argument("--web-directory", type=Path)
    parser.add_argument("--notices-directory", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.output,
                args.ocr_base,
                args.ocr_site,
                args.vc_redist,
                postgres_root=args.postgres_root,
                web_directory=args.web_directory,
                notices_directory=args.notices_directory,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
