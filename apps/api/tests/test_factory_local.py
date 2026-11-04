"""Factory install ownership and repeat-start safeguards; synthetic paths only."""

import hashlib
import importlib.util
import json
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from conftest import ROOT


@pytest.fixture
def factory(tmp_path):
    path = ROOT / "scripts/factory-local.py"
    assert path.is_file(), "Factory operator entry is not implemented"
    spec = importlib.util.spec_from_file_location("factory_local", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.BASE = tmp_path / "factory-data"
    module.PROJECT = tmp_path / "app"
    module.BIN = module.PROJECT / "runtime/postgresql/bin"
    module.save(module.PROJECT / "bundle.json", {"kind": "factoryflow-offline-v1", "files": {}})
    return module


def test_foreign_environment_rejected_without_configuration(factory, tmp_path):
    for path in (tmp_path, factory.BASE / "environments" / "wrong"):
        with pytest.raises(ValueError):
            factory.owned(path)


def test_factory_marker_cannot_accept_synthetic_trial(factory):
    identifier = uuid4().hex
    root = factory.BASE / "environments" / identifier
    factory.save(
        root / "owner.json",
        {
            "kind": "factoryflow-local-trial-v1",
            "id": identifier,
            "synthetic_only": True,
        },
    )
    with pytest.raises(ValueError):
        factory.owned(root)


def test_repeat_setup_never_creates_or_resets_database(factory, monkeypatch):
    factory.save(factory.BASE / "active.json", {"id": uuid4().hex})
    monkeypatch.setattr(factory, "new_cluster", lambda *_: pytest.fail("must not create"))
    with pytest.raises(ValueError):
        factory.prepare("Synthetic", "synthetic-admin", "Synthetic-Password-123")


def test_partial_first_setup_survives_relaunch_without_another_cluster(factory, monkeypatch):
    root = factory.BASE / "environments" / uuid4().hex
    factory.save(root / "owner.json", {"kind": factory.KIND, "id": root.name})
    before = (root / "owner.json").read_bytes()
    monkeypatch.setattr(factory, "new_cluster", lambda *_: pytest.fail("must retain failed setup"))
    for _ in range(2):
        with pytest.raises(factory.LocalError, match="未完成|incomplete"):
            factory.prepare("Synthetic", "synthetic-admin", "Synthetic-Password-123")
    assert list((factory.BASE / "environments").iterdir()) == [root]
    assert (root / "owner.json").read_bytes() == before
    assert not (factory.BASE / "active.json").exists()


def test_initdb_failure_keeps_output_and_removes_password_file(factory, monkeypatch):
    def run(command, **kwargs):
        if command[0].endswith("initdb.exe"):
            assert kwargs["stdout"] is kwargs["stderr"]
            kwargs["stdout"].write(b"Synthetic initdb encoding failure\n")
            return SimpleNamespace(returncode=1)
        assert command[0].endswith("pg_ctl.exe") and command[-1] == "status"
        return SimpleNamespace(returncode=3)

    monkeypatch.setattr(factory.subprocess, "run", run)
    with pytest.raises(factory.LocalError, match="已停止|stopped"):
        factory.new_cluster()
    [root] = list((factory.BASE / "environments").iterdir())
    assert (root / "initdb.log").read_bytes() == b"Synthetic initdb encoding failure\n"
    assert not (root / "init-password.tmp").exists()
    assert not (factory.BASE / "active.json").exists()


def test_reused_pid_or_foreign_command_is_never_ours(factory, tmp_path):
    root = str(tmp_path / "synthetic")
    record = {"pid": 99, "created": "10", "root": root}
    same = {"pid": 99, "created": "10", "command": f'python factory-local.py serve --root "{root}"'}
    assert factory.matches_process(record, same)
    assert not factory.matches_process(record, same | {"created": "11"})
    assert not factory.matches_process(record, same | {"command": "python other.py"})


def test_runtime_settings_use_current_bundle_ocr_and_private_paths(factory, tmp_path):
    identifier = uuid4().hex
    root = factory.BASE / "environments" / identifier
    factory.save(root / "owner.json", {"kind": factory.KIND, "id": identifier})
    factory.save(
        root / "private-state.json",
        {
            "admin_url": "postgresql://ff_admin:Synthetic@127.0.0.1:59231/postgres",
            "runtime_password": "Synthetic",
            "port": 59231,
            "api_port": 59232,
        },
    )
    factory.OCR_PYTHON = tmp_path / "python.exe"
    factory.OCR_PYTHON.write_bytes(b"synthetic")
    settings, _ = factory.environment(root)
    assert settings.object_root == root / "objects"
    assert settings.ocr_engine == "rapid"
    assert settings.ocr_python == factory.OCR_PYTHON
    assert "factoryflow_business" in settings.database_url


def test_cluster_start_failure_stops_only_verified_new_cluster(factory, monkeypatch):
    calls = []

    def pg(name, *args, **kwargs):
        calls.append((name, args))
        if name == "initdb":
            path = args[1]
            path.mkdir()
            (path / "postgresql.conf").write_text("")
        return 0

    monkeypatch.setattr(factory, "pg", pg)
    monkeypatch.setattr(factory, "database_start", lambda root: (_ for _ in ()).throw(ValueError()))
    monkeypatch.setattr(factory, "database_identity", lambda root: calls.append(("verified", root)))
    with pytest.raises(ValueError):
        factory.new_cluster()
    assert any(name == "verified" for name, _ in calls)
    assert any(name == "pg_ctl" and "stop" in args for name, args in calls)
    assert not (factory.BASE / "active.json").exists()


def test_piped_first_setup_does_not_wait_for_native_console(factory, monkeypatch):
    from io import StringIO

    monkeypatch.setattr(factory.sys, "stdin", StringIO("Synthetic-piped-secret\n"))
    monkeypatch.setattr(factory.getpass, "getpass", lambda _: pytest.fail("must use explicit pipe"))
    assert factory.password_input("password:") == "Synthetic-piped-secret"


def test_english_first_setup_rejects_short_password_before_creating_data(factory, monkeypatch):
    factory.LANGUAGE = "en"
    monkeypatch.setattr(
        factory, "new_cluster", lambda *_: pytest.fail("invalid setup created data")
    )
    with pytest.raises(factory.LocalError, match="Password"):
        factory.prepare("Synthetic Factory", "synthetic", "short")
    assert not factory.BASE.exists()


def test_installer_preserves_business_directory_and_rejects_tampering(tmp_path, monkeypatch):
    import hashlib

    spec = importlib.util.spec_from_file_location(
        "offline_install", ROOT / "scripts/install-offline.py"
    )
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    source = tmp_path / "app"
    source.mkdir()
    names = ("启动工厂软件", "停止工厂软件", "备份工厂数据", "恢复工厂备份", "查看运行状态")
    for name in names:
        (source / (name + ".cmd")).write_bytes(b"synthetic")
    manifest = {
        "kind": "factoryflow-offline-v1",
        "build_id": "a" * 16,
        "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()},
    }
    (source / "bundle.json").write_text(json.dumps(manifest))
    (source / "private-unlisted.txt").write_bytes(b"must-never-be-copied")
    destination = tmp_path / "installed"
    data = destination / "data/private-synthetic"
    data.parent.mkdir(parents=True)
    data.write_bytes(b"retain-me")
    original_copy = installer.shutil.copy2
    with monkeypatch.context() as patch:
        patch.setattr(installer.shutil, "copy2", lambda *_: (_ for _ in ()).throw(OSError()))
        with pytest.raises(OSError):
            installer.install(source, destination)
    assert not (destination / "program" / ("a" * 16)).exists()
    assert installer.shutil.copy2 is original_copy
    installer.install(source, destination)
    installer.install(source, destination)
    assert data.read_bytes() == b"retain-me"
    assert not list((destination / "program").rglob("private-unlisted.txt"))
    (source / (names[0] + ".cmd")).write_bytes(b"tampered")
    with pytest.raises(ValueError):
        installer.install(source, destination)
    assert data.read_bytes() == b"retain-me"


@pytest.mark.parametrize("encoding", ["cp936", "cp65001", "cp1252"])
def test_database_identity_uses_lossless_system_path_bytes(
    factory, tmp_path, monkeypatch, encoding
):
    name = "中文测试数据" if encoding != "cp1252" else "données"
    root = tmp_path / name
    raw = str(root / "pgdata").replace("\\", "/").encode(encoding)
    queries = []

    @contextmanager
    def connect(*args, **kwargs):
        def execute(query):
            queries.append(query)
            return SimpleNamespace(fetchone=lambda: (raw.hex(),))

        yield SimpleNamespace(execute=execute)

    monkeypatch.setattr(factory, "environment", lambda _: (None, {"admin_url": "synthetic"}))
    monkeypatch.setattr(factory.psycopg, "connect", connect)
    monkeypatch.setattr(factory, "path_encoding", lambda: encoding, raising=False)
    monkeypatch.setattr(factory, "database_executable", lambda _: None)
    factory.database_identity(root)
    assert "textsend" in queries[0] and "hex" in queries[0]


@pytest.mark.parametrize("value", ["not-hex", "ff", "72656c6174697665", "433a2f666f726569676e"])
def test_database_identity_rejects_unverifiable_or_foreign_paths(
    factory, tmp_path, monkeypatch, value
):
    @contextmanager
    def connect(*args, **kwargs):
        yield SimpleNamespace(execute=lambda _: SimpleNamespace(fetchone=lambda: (value,)))

    monkeypatch.setattr(factory, "environment", lambda _: (None, {"admin_url": "synthetic"}))
    monkeypatch.setattr(factory.psycopg, "connect", connect)
    monkeypatch.setattr(factory, "path_encoding", lambda: "cp65001", raising=False)
    monkeypatch.setattr(factory, "database_executable", lambda _: None)
    with pytest.raises(factory.LocalError):
        factory.database_identity(tmp_path / "expected")


def utf8_bundle(factory):
    files, executables = {}, {}
    for name in ("initdb.exe", "postgres.exe", "pg_ctl.exe", "pg_dump.exe", "pg_restore.exe"):
        path = factory.BIN / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic hash fixture: " + name.encode())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files[f"runtime/postgresql/bin/{name}"] = digest
        executables[name] = {"sha256": digest}
    marker = factory.PROJECT / "runtime/postgresql/path-encoding.json"
    factory.save(
        marker,
        {
            "kind": "factoryflow-postgresql-utf8-v1",
            "encoding": "utf-8",
            "minimum_windows_build": 18362,
            "executables": executables,
        },
    )
    files["runtime/postgresql/path-encoding.json"] = hashlib.sha256(marker.read_bytes()).hexdigest()
    factory.save(
        factory.PROJECT / "bundle.json",
        {
            "kind": "factoryflow-offline-v1",
            "postgresql_path_encoding": "utf-8",
            "files": files,
        },
    )
    return marker


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process UTF-8 and ACP contract")
def test_process_utf8_does_not_depend_on_system_codepage(factory, monkeypatch):
    utf8_bundle(factory)
    monkeypatch.setattr(factory.ctypes.windll.kernel32, "GetACP", lambda: 936)
    assert factory.path_encoding() == "utf-8"


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "corrupt",
        "undeclared",
        "exe_changed",
        pytest.param(
            "old_os",
            marks=pytest.mark.skipif(
                sys.platform != "win32", reason="Windows minimum build contract"
            ),
        ),
    ],
)
def test_invalid_utf8_runtime_fails_before_native_process_or_data(factory, monkeypatch, failure):
    marker = utf8_bundle(factory)
    if failure == "missing":
        marker.unlink()
    elif failure == "corrupt":
        marker.write_text("{}")
    elif failure == "undeclared":
        bundle = factory.read(factory.PROJECT / "bundle.json")
        del bundle["postgresql_path_encoding"]
        factory.save(factory.PROJECT / "bundle.json", bundle)
    elif failure == "exe_changed":
        (factory.BIN / "postgres.exe").write_bytes(b"different runtime")
    else:
        monkeypatch.setattr(factory.sys, "getwindowsversion", lambda: SimpleNamespace(build=17763))
    monkeypatch.setattr(factory.subprocess, "run", lambda *a, **kw: pytest.fail("must not execute"))
    with pytest.raises(factory.LocalError):
        factory.new_cluster()
    assert not factory.BASE.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows legacy ACP contract")
def test_legacy_bundle_uses_one_system_encoding(factory, monkeypatch):
    monkeypatch.setattr(factory.ctypes.windll.kernel32, "GetACP", lambda: 936)
    assert factory.path_encoding() == "cp936"


def test_foreign_database_executable_rejected_before_connecting(factory, tmp_path, monkeypatch):
    root = tmp_path / "中文 数据"
    path = root / "pgdata/postmaster.pid"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"12345\n")
    monkeypatch.setattr(factory, "environment", lambda _: (None, {"admin_url": "synthetic"}))
    monkeypatch.setattr(factory, "process_image", lambda _: tmp_path / "old-app/postgres.exe")
    monkeypatch.setattr(factory.psycopg, "connect", lambda *a, **k: pytest.fail("must not connect"))
    with pytest.raises(factory.LocalError, match="另一个版本"):
        factory.database_identity(root)
    monkeypatch.setattr(factory, "process_image", lambda _: factory.BIN / "postgres.exe")
    factory.database_executable(root)


def test_foreign_running_database_rejected_before_any_stop(factory, tmp_path, monkeypatch):
    calls = []

    def pg(name, *args, **kwargs):
        calls.append(args[-1])
        assert args[-1] == "status", "must not stop a foreign database"
        return 0

    def reject(root):
        raise factory.LocalError("another runtime; no process was stopped")

    monkeypatch.setattr(factory, "environment", lambda _: (None, {"api_port": 59999}))
    monkeypatch.setattr(factory, "pg", pg)
    monkeypatch.setattr(factory, "database_identity", reject)
    monkeypatch.setattr(factory, "stop_api", lambda _: pytest.fail("API must remain running"))
    with pytest.raises(factory.LocalError, match="another runtime"):
        factory.stop(tmp_path)
    assert calls == ["status"]
