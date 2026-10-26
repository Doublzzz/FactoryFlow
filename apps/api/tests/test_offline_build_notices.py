"""Synthetic package trees only: no runtime processes, database, or network."""

import importlib.util
import json
import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def distribution(site, name, version):
    package = name.replace("-", "_")
    info = f"{package}-{version}.dist-info"
    contents = {
        f"{package}/__init__.py": "# synthetic dependency\n",
        f"{info}/METADATA": f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
        f"{info}/licenses/LICENSE": "Synthetic dependency license\n",
    }
    contents[f"{info}/RECORD"] = "".join(f"{name},,\n" for name in [*contents, f"{info}/RECORD"])
    for relative, content in contents.items():
        write(site / relative, content)


@pytest.fixture
def package_inputs(tmp_path, monkeypatch):
    builder = load_script("offline_build_notices", "build-offline-package.py")
    source = tmp_path / "sanitized-source"
    primary = tmp_path / "python"
    ocr = tmp_path / "ocr"
    pg = tmp_path / "external-postgresql"
    web = tmp_path / "external-web"
    notices = tmp_path / "reviewed-notices"
    for base in (primary, ocr):
        write(base / "python.exe", "synthetic executable")
        write(base / "Lib/os.py", "# synthetic standard library\n")
    distribution(primary / "Lib/site-packages", "tiny-runtime", "1.0")
    for name, version in (("rapidocr", "3.9.2"), ("onnxruntime", "1.30.0"), ("pillow", "12.1.1")):
        distribution(ocr / "Lib/site-packages", name, version)
    for directory in ("bin", "lib", "share"):
        write(pg / directory / "synthetic.txt", "synthetic PostgreSQL runtime")
    for name in ("server_license.txt", "commandlinetools_3rd_party_licenses.txt"):
        write(pg / name, "synthetic PostgreSQL notice: " + name)
    write(web / "index.html", "<title>Synthetic build</title>")
    write(notices / "README.md", "Synthetic reviewed third-party notices")
    write(notices / "inventory.json", '{"synthetic": true}')
    write(notices / "component/LICENSE.txt", "Synthetic component license")
    write(notices.parent / "unrelated-private.txt", "must not be copied")
    write(source / "LICENSE", "MIT License\nSynthetic project license fixture\n")
    write(source / "pyproject.toml", '[project]\ndependencies = ["tiny-runtime==1.0"]\n')
    write(source / "apps/api/src/factoryflow/__init__.py", "# synthetic application\n")
    write(source / "migrations/env.py", "# synthetic migration source\n")
    write(source / "alembic.ini", "[alembic]\n")
    write(source / "scripts/factory-local.py", "# synthetic entry point\n")
    shutil.copyfile(ROOT / "scripts/install-offline.py", source / "scripts/install-offline.py")
    write(source / "docs/FACTORY-OFFLINE-GUIDE.txt", "Synthetic guide")
    write(source / "docs/FACTORY-OFFLINE-GUIDE-en.txt", "Synthetic English guide")
    monkeypatch.setattr(builder, "ROOT", source)
    monkeypatch.setattr(
        builder, "sys", SimpleNamespace(base_prefix=primary, prefix=primary, version="3.14.7")
    )
    return SimpleNamespace(
        builder=builder,
        source=source,
        primary=primary,
        ocr=ocr,
        pg=pg,
        web=web,
        notices=notices,
        output=tmp_path / "distribution",
    )


def build(inputs, **overrides):
    options = {
        "postgres_root": inputs.pg,
        "web_directory": inputs.web,
        "notices_directory": inputs.notices,
    }
    options.update(overrides)
    return inputs.builder.build(
        inputs.output, inputs.ocr, inputs.ocr / "Lib/site-packages", None, **options
    )


def test_notices_are_hashed_archived_and_installed(package_inputs, tmp_path):
    inputs = package_inputs
    receipt = build(inputs)
    app = inputs.output / "app"
    installer = load_script("offline_notice_installer", "install-offline.py")
    manifest = installer.verify(app)
    expected = {
        "LICENSE": inputs.source / "LICENSE",
        "third-party/README.md": inputs.notices / "README.md",
        "third-party/inventory.json": inputs.notices / "inventory.json",
        "third-party/component/LICENSE.txt": inputs.notices / "component/LICENSE.txt",
        "third-party/postgresql/server_license.txt": inputs.pg / "server_license.txt",
        "third-party/postgresql/commandlinetools_3rd_party_licenses.txt": (
            inputs.pg / "commandlinetools_3rd_party_licenses.txt"
        ),
    }
    for relative, source in expected.items():
        assert manifest["files"][relative] == inputs.builder.digest(source)
    assert (inputs.output / "LICENSE").read_bytes() == (app / "LICENSE").read_bytes()
    assert (inputs.output / "Read me.txt").read_text(encoding="utf-8") == "Synthetic English guide"
    assert "--language en" in (inputs.output / "Install.cmd").read_text(encoding="utf-8")
    for name, action in (
        ("Start FactoryFlow", "start"),
        ("Stop FactoryFlow", "stop"),
        ("Back Up Data", "backup"),
        ("Restore Backup", "restore"),
        ("Check Status", "status"),
    ):
        entry = app / (name + ".cmd")
        assert f"{action} --language en" in entry.read_text(encoding="utf-8")
        assert entry.name in manifest["files"]
    assert not (app / "unrelated-private.txt").exists()
    assert not (app / "third-party/unrelated-private.txt").exists()
    assert (app / "apps/web/dist/index.html").read_bytes() == (
        inputs.web / "index.html"
    ).read_bytes()
    for runtime, package, version in (
        ("python", "tiny_runtime", "1.0"),
        ("ocr", "rapidocr", "3.9.2"),
        ("ocr", "onnxruntime", "1.30.0"),
        ("ocr", "pillow", "12.1.1"),
    ):
        relative = (
            f"runtime/{runtime}/Lib/site-packages/{package}-{version}.dist-info/licenses/LICENSE"
        )
        assert relative in manifest["files"]
    with zipfile.ZipFile(receipt["package"]) as archive:
        assert archive.read("LICENSE") == (inputs.source / "LICENSE").read_bytes()
        for relative, source in expected.items():
            assert archive.read("app/" + relative) == source.read_bytes()
    destination = tmp_path / "installed"
    installer.install(app, destination)
    installed = destination / "program" / receipt["build_id"]
    assert installer.verify(installed) == manifest
    for relative, source in expected.items():
        assert (installed / relative).read_bytes() == source.read_bytes()


@pytest.mark.parametrize(
    "relative",
    [
        "notices/README.md",
        "notices/inventory.json",
        "pg/server_license.txt",
        "pg/commandlinetools_3rd_party_licenses.txt",
        "source/LICENSE",
    ],
)
def test_missing_license_or_notice_fails_before_creating_output(package_inputs, relative):
    inputs = package_inputs
    owner, filename = relative.split("/", 1)
    (getattr(inputs, owner) / filename).unlink()
    with pytest.raises(ValueError, match="Required source file missing"):
        build(inputs)
    assert not inputs.output.exists()
    assert not inputs.output.with_suffix(".zip").exists()


@pytest.mark.parametrize("source", ["pg", "web", "notices", "ocr"])
def test_missing_source_directory_fails_before_creating_output(package_inputs, source):
    inputs = package_inputs
    shutil.rmtree(getattr(inputs, source))
    with pytest.raises(ValueError, match="Required source directory missing"):
        build(inputs)
    assert not inputs.output.exists()


def test_existing_zip_rejected_before_copying_app(package_inputs):
    inputs = package_inputs
    archive = inputs.output.with_suffix(".zip")
    archive.write_bytes(b"existing archive must survive")
    with pytest.raises(ValueError, match="ZIP already exists"):
        build(inputs)
    assert not inputs.output.exists()
    assert archive.read_bytes() == b"existing archive must survive"


def test_existing_build_receipt_rejected_without_overwriting(package_inputs):
    inputs = package_inputs
    receipt = inputs.output.parent / (inputs.output.name + "-build.json")
    receipt.write_bytes(b"existing receipt must survive")
    with pytest.raises(ValueError, match="build receipt already exists"):
        build(inputs)
    assert not inputs.output.exists()
    assert not inputs.output.with_suffix(".zip").exists()
    assert receipt.read_bytes() == b"existing receipt must survive"


@pytest.mark.parametrize("runtime", ["primary", "ocr"])
@pytest.mark.parametrize("failure", ["missing", "version", "record", "listed-file"])
def test_invalid_dependencies_fail_before_copying_runtime(package_inputs, runtime, failure):
    inputs = package_inputs
    site = getattr(inputs, runtime) / "Lib/site-packages"
    name, version = ("tiny_runtime", "1.0") if runtime == "primary" else ("rapidocr", "3.9.2")
    info = site / f"{name}-{version}.dist-info"
    if failure == "missing":
        shutil.rmtree(info)
        message = "Dependency not installed"
    elif failure == "version":
        write(info / "METADATA", f"Metadata-Version: 2.1\nName: {name}\nVersion: 0.0\n")
        message = "Pinned dependency mismatch"
    elif failure == "record":
        (info / "RECORD").unlink()
        message = "Dependency file inventory missing"
    else:
        (info / "licenses/LICENSE").unlink()
        message = "Dependency file missing"
    with pytest.raises(ValueError, match=message):
        build(inputs)
    assert not inputs.output.exists()
    assert not inputs.output.with_suffix(".zip").exists()
    assert not (inputs.output.parent / (inputs.output.name + "-build.json")).exists()


def test_non_mit_project_license_rejected_before_creating_output(package_inputs):
    inputs = package_inputs
    write(inputs.source / "LICENSE", "Synthetic incompatible license")
    with pytest.raises(ValueError, match="Project LICENSE must contain the MIT License"):
        build(inputs)
    assert not inputs.output.exists()


def test_existing_default_dependency_paths_still_work(package_inputs):
    inputs = package_inputs
    shutil.copytree(inputs.pg, inputs.source / ".tools/postgresql-18.6-4/pgsql")
    shutil.copytree(inputs.web, inputs.source / "apps/web/dist")
    receipt = build(inputs, postgres_root=None, web_directory=None)
    manifest = json.loads((inputs.output / "app/bundle.json").read_text(encoding="utf-8"))
    assert receipt["build_id"] == manifest["build_id"]


def test_notice_directory_is_required(package_inputs):
    inputs = package_inputs
    with pytest.raises(TypeError, match="notices_directory"):
        inputs.builder.build(inputs.output, inputs.ocr, inputs.ocr / "Lib/site-packages", None)
    assert not inputs.output.exists()


def test_source_built_postgresql_license_is_preserved(package_inputs):
    inputs = package_inputs
    for name in ("server_license.txt", "commandlinetools_3rd_party_licenses.txt"):
        (inputs.pg / name).unlink()
    write(inputs.pg / "COPYING", "Synthetic upstream PostgreSQL license")
    build(inputs)
    assert (inputs.output / "app/third-party/postgresql/COPYING").read_bytes() == (
        inputs.pg / "COPYING"
    ).read_bytes()


def add_opencv(inputs, monkeypatch, version="5.0.0.93"):
    site = inputs.ocr / "Lib/site-packages"
    distribution(site, "opencv-python", version)
    rapid_info = site / "rapidocr-3.9.2.dist-info/METADATA"
    rapid_info.write_text(rapid_info.read_text() + f"Requires-Dist: opencv-python=={version}\n")
    extras = {
        "cv2/cv2.pyd": "synthetic still-image library",
        "cv2/opencv_videoio_ffmpeg500_64.dll": "synthetic optional video library",
        "cv2/unrelated.dll": "synthetic unrelated library",
    }
    record = site / f"opencv_python-{version}.dist-info/RECORD"
    for relative, content in extras.items():
        write(site / relative, content)
    record.write_text(record.read_text() + "".join(f"{p},,\n" for p in extras))
    monkeypatch.setitem(
        inputs.builder.OCR_VIDEO_PLUGIN,
        "sha256",
        inputs.builder.digest(site / "cv2/opencv_videoio_ffmpeg500_64.dll"),
    )
    return site, record


def test_only_reviewed_optional_video_plugin_is_omitted(package_inputs, monkeypatch):
    inputs = package_inputs
    site, record = add_opencv(inputs, monkeypatch)
    input_record = record.read_bytes()
    receipt = build(inputs)
    app = inputs.output / "app"
    relative = "runtime/ocr/Lib/site-packages/cv2/opencv_videoio_ffmpeg500_64.dll"
    assert not (app / relative).exists()
    assert record.read_bytes() == input_record
    assert (site / "cv2/opencv_videoio_ffmpeg500_64.dll").is_file()
    output_site = app / "runtime/ocr/Lib/site-packages"
    assert "opencv_videoio_ffmpeg" not in (output_site / record.relative_to(site)).read_text()
    for name in (
        "cv2/cv2.pyd",
        "cv2/unrelated.dll",
        "opencv_python-5.0.0.93.dist-info/licenses/LICENSE",
    ):
        assert (output_site / name).read_bytes() == (site / name).read_bytes()
    manifest = json.loads((app / "bundle.json").read_text())
    assert relative not in manifest["files"]
    assert manifest["omitted_optional_components"] == [inputs.builder.OCR_VIDEO_PLUGIN]
    with zipfile.ZipFile(receipt["package"]) as archive:
        assert "app/" + relative not in archive.namelist()


@pytest.mark.parametrize("failure", ["changed-bytes", "unreviewed-version"])
def test_unreviewed_opencv_omission_fails_before_output(package_inputs, monkeypatch, failure):
    inputs = package_inputs
    version = "5.0.0.93" if failure == "changed-bytes" else "5.0.0.94"
    site, _ = add_opencv(inputs, monkeypatch, version)
    if failure == "changed-bytes":
        (site / "cv2/opencv_videoio_ffmpeg500_64.dll").write_text("changed input")
    with pytest.raises(ValueError, match="OpenCV video"):
        build(inputs)
    assert not inputs.output.exists()


def test_dotted_version_is_preserved_in_archive_name(package_inputs):
    inputs = package_inputs
    inputs.output = inputs.output.with_name("FactoryFlow-v0.1.0-preview.1")
    receipt = build(inputs)
    assert Path(receipt["package"]).name == "FactoryFlow-v0.1.0-preview.1.zip"
