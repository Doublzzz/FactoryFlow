"""Factory install ownership and repeat-start safeguards; synthetic paths only."""

import importlib.util
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


def test_installer_preserves_business_directory_and_rejects_tampering(tmp_path, monkeypatch):
    import hashlib
    import json

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
