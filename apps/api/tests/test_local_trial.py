"""Maintenance ownership and failure boundaries without touching a real environment."""

import hashlib
import importlib.util
import json
import os
import socket
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from conftest import ROOT


@pytest.fixture
def trial(tmp_path):
    path = ROOT / "scripts/local-trial.py"
    assert path.is_file(), "Unified local trial maintenance entry is not implemented"
    spec = importlib.util.spec_from_file_location("local_trial", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.BASE = tmp_path / "local-trial"
    return module


def owned_fixture(trial):
    identity = uuid4().hex
    root = trial.BASE / "environments" / identity
    root.mkdir(parents=True)
    (root / "owner.json").write_text(
        json.dumps({"kind": "factoryflow-local-trial-v1", "id": identity, "synthetic_only": True})
    )
    (root / "private-state.json").write_text(
        json.dumps(
            {
                "admin_url": "postgresql://ff_admin:Synthetic@127.0.0.1:59123/postgres",
                "runtime_password": "Synthetic",
                "port": 59123,
                "api_port": 59124,
            }
        )
    )
    (root / "app.json").write_text(
        json.dumps(
            {
                "database_url": "postgresql+psycopg://ff_runtime:Synthetic@127.0.0.1:59123/factoryflow_trial",
                "object_root": str(root / "objects"),
                "secure_cookies": False,
            }
        )
    )
    return root


def test_foreign_path_is_rejected_before_reading_configuration(trial, tmp_path):
    for path in (
        tmp_path / "development",
        trial.BASE / "environments" / "not-an-id",
        Path("C:/other"),
    ):
        with pytest.raises(ValueError):
            trial.owned(path)


def test_marker_is_required_and_owned_environment_is_accepted(trial):
    root = owned_fixture(trial)
    assert trial.owned(root) == root.resolve()
    (root / "owner.json").write_text("{}")
    with pytest.raises(ValueError):
        trial.owned(root)


@pytest.mark.parametrize(
    "change",
    [
        {
            "database_url": "postgresql+psycopg://ff_runtime:Synthetic@127.0.0.1:55433/factoryflow_dev"
        },
        {
            "database_url": "postgresql+psycopg://ff_runtime:Synthetic@remote:59123/factoryflow_trial"
        },
        {"database_url": "postgresql+psycopg://ff_runtime:Synthetic@127.0.0.1:59123/foreign"},
        {"object_root": "C:/other/objects"},
        {"archive_root": "C:/other/archives"},
        {"archive_root": 42},
        {"ocr_engine": "rapid", "ocr_python": "C:/missing/python.exe"},
    ],
)
def test_changed_configuration_cannot_escape_trial(trial, change):
    root = owned_fixture(trial)
    path = root / "app.json"
    path.write_text(json.dumps(json.loads(path.read_text()) | change))
    with pytest.raises(ValueError):
        trial.environment(root)


def test_backup_path_must_be_owned_and_complete(trial, tmp_path):
    with pytest.raises(ValueError):
        trial.backup_path(tmp_path / "foreign")
    path = trial.BASE / "backups" / uuid4().hex
    path.mkdir(parents=True)
    with pytest.raises(ValueError):
        trial.backup_path(path)


def test_process_identity_requires_creation_time_and_owned_command(trial):
    record = {"pid": 42, "created": "123", "root": str(trial.BASE / "environments" / ("a" * 32))}
    correct = {
        "pid": 42,
        "created": "123",
        "command": f"python local-trial.py serve --root {record['root']}",
    }
    assert trial.matches_process(record, correct)
    for changed in ({"created": "999"}, {"command": "python other.py"}, {"pid": 43}):
        assert not trial.matches_process(record, correct | changed)


def test_existing_trial_cannot_be_prepared_again(trial, monkeypatch):
    root = owned_fixture(trial)
    trial.save(trial.BASE / "active.json", {"id": root.name})
    monkeypatch.setattr(trial, "new_cluster", lambda port: pytest.fail("must not create cluster"))
    with pytest.raises(ValueError, match="already exists"):
        trial.prepare(8120)


def test_occupied_api_port_does_not_start_or_stop_database(trial, monkeypatch):
    root = owned_fixture(trial)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        state_path = root / "private-state.json"
        trial.save(state_path, trial.read(state_path) | {"api_port": listener.getsockname()[1]})
        monkeypatch.setattr(trial, "status", lambda root: {"ready": False, "api_owned": False})
        monkeypatch.setattr(trial, "database_start", lambda root: pytest.fail("occupied port"))
        with pytest.raises(ValueError, match="occupied"):
            trial.start(root)
        assert listener.getsockname()[1] > 0


def test_schema_rejection_never_migrates_or_launches_api(trial, monkeypatch):
    root = owned_fixture(trial)
    events = []

    class OldSchema:
        def check_ready(self):
            events.append("checked")
            raise RuntimeError("schema mismatch")

        def close(self):
            events.append("closed")

    monkeypatch.setattr(trial, "status", lambda root: {"ready": False, "api_owned": False})
    monkeypatch.setattr(trial, "database_start", lambda root: events.append("database"))
    monkeypatch.setattr(trial, "build_services", lambda settings: OldSchema())
    monkeypatch.setattr(trial, "upgrade_database", lambda *a: pytest.fail("implicit migration"))
    monkeypatch.setattr(trial.subprocess, "Popen", lambda *a, **kw: pytest.fail("API launched"))
    with pytest.raises(RuntimeError, match="schema mismatch"):
        trial.start(root)
    assert events == ["database", "checked", "closed"]


def test_reused_pid_is_never_terminated(trial, monkeypatch):
    root = owned_fixture(trial).resolve()
    trial.save(root / "server-process.json", {"pid": 42, "created": "123", "root": str(root)})
    monkeypatch.setattr(trial, "process", lambda pid: {"pid": 42, "created": "999"})
    monkeypatch.setattr(trial, "_process_handle", lambda *a: pytest.fail("terminate attempted"))
    with pytest.raises(ValueError, match="reused"):
        trial.stop_api(root)


def test_corrupt_backup_fails_before_creating_environment(trial, monkeypatch):
    path = trial.BASE / "backups" / uuid4().hex
    trial.save(path / "trial.json", {"kind": trial.KIND})
    trial.save(
        path / "data/manifest.json",
        {
            "format": 1,
            "schema_revision": trial.REVISION,
            "database_sha256": "0" * 64,
            "objects": [],
        },
    )
    (path / "data/database.dump").write_bytes(b"corrupted synthetic dump")
    monkeypatch.setattr(trial, "new_cluster", lambda port: pytest.fail("created before validation"))
    with pytest.raises(ValueError):
        trial.restore(path, activate=True)
    assert not (trial.BASE / "active.json").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction and locking contract")
@pytest.mark.parametrize("name", ["objects", "pgdata"])
def test_junction_escape_is_rejected_before_database_access(trial, tmp_path, name):
    root = owned_fixture(trial)
    external = tmp_path / "external"
    external.mkdir()
    link = root / name
    env = os.environ | {"TRIAL_TEST_LINK": str(link), "TRIAL_TEST_TARGET": str(external)}
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "New-Item -ItemType Junction -Path $env:TRIAL_TEST_LINK "
            "-Target $env:TRIAL_TEST_TARGET | Out-Null",
        ],
        env=env,
        check=True,
        capture_output=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        with pytest.raises(ValueError, match="junctions"):
            trial.environment(root)
    finally:
        os.rmdir(link)  # Removes this junction only; the external target is retained.
    assert external.is_dir()


@pytest.mark.skipif(os.name != "nt", reason="Windows locking contract")
def test_maintenance_lock_rejects_concurrent_operation_and_releases(trial):
    with trial.maintenance_lock():
        with pytest.raises(ValueError, match="Another trial"):
            with trial.maintenance_lock():
                pytest.fail("concurrent operation entered")
    with trial.maintenance_lock():
        pass


def test_failed_preparation_stops_new_cluster_and_reports_identity(trial, monkeypatch):
    root = owned_fixture(trial)
    stopped = []
    monkeypatch.setattr(trial, "new_cluster", lambda port: root)
    monkeypatch.setattr(
        trial.psycopg,
        "connect",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("synthetic secret")),
    )
    monkeypatch.setattr(trial, "abandon_new", lambda root: stopped.append(root))
    with pytest.raises(ValueError, match=root.name) as failure:
        trial.prepare(8120)
    assert "synthetic secret" not in str(failure.value)
    assert stopped == [root]
    assert not (trial.BASE / "active.json").exists()


def test_metadata_damage_is_rejected_before_restore_allocation(trial, monkeypatch):
    path = trial.BASE / "backups" / uuid4().hex
    trial.save(path / "trial.json", {"kind": trial.KIND, "login": {"password": "damaged"}})
    (path / "trial.sha256").write_text("0" * 64)
    payload = b"synthetic valid-hash dump"
    trial.save(
        path / "data/manifest.json",
        {
            "format": 1,
            "schema_revision": trial.REVISION,
            "database_sha256": hashlib.sha256(payload).hexdigest(),
            "objects": [],
        },
    )
    (path / "data/database.dump").write_bytes(payload)
    with pytest.raises(ValueError, match="metadata"):
        trial.backup_path(path)


def test_active_pointer_failure_stops_prepared_cluster(trial, monkeypatch):
    root = owned_fixture(trial)
    stopped = []

    class Noop:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, *args):
            pass

        def dispose(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(trial, "new_cluster", lambda port: root)
    monkeypatch.setattr(trial.psycopg, "connect", lambda *a, **kw: Noop())
    monkeypatch.setattr(trial, "engine_for", lambda *a: Noop())
    monkeypatch.setattr(trial, "upgrade_database", lambda *a: None)
    monkeypatch.setattr(trial, "build_services", lambda *a: Noop())
    monkeypatch.setattr(trial, "seed", lambda *a: None)
    monkeypatch.setattr(trial, "save", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
    monkeypatch.setattr(trial, "abandon_new", lambda root: stopped.append(root))
    with pytest.raises(ValueError, match=root.name):
        trial.prepare(8120)
    assert stopped == [root]
