"""Recovery preserves data, audits atomically, revokes sessions and refuses ambiguous accounts."""

import hashlib
import importlib.util
import json
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from conftest import SYNTHETIC_PASSWORD
from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[3]
NEW_PASSWORD = "Synthetic-Recovered-Password-789"
BODY = {"password": NEW_PASSWORD, "confirmation": NEW_PASSWORD, "confirmed": True}


def test_reset_preserves_business_data_and_account_revokes_sessions_and_unlocks(pg):
    old_login = pg.runtime.identity.login("synthetic-admin", SYNTHETIC_PASSWORD)
    with pg.owner.begin() as conn:
        before = conn.execute(text("SELECT * FROM customers")).all()
        conn.execute(
            text("UPDATE users SET failed_attempts=5,locked_until=now()+interval '15 min'")
        )
    expected = pg.runtime.identity.local_admin()
    assert expected == pg.actor
    pg.runtime.identity.reset_local_admin_password(expected, NEW_PASSWORD)
    with pytest.raises(BusinessError, match="AUTH_FAILED"):
        pg.runtime.identity.login("synthetic-admin", SYNTHETIC_PASSWORD)
    with pytest.raises(BusinessError, match="LOGIN_REQUIRED"):
        pg.runtime.identity.authenticate(old_login["session_token"])
    assert pg.api.request("GET", "/api/v1/auth/session").status_code == 401
    login = pg.runtime.identity.login("synthetic-admin", NEW_PASSWORD)
    assert login["actor"] == expected
    with pg.owner.connect() as conn:
        assert conn.execute(text("SELECT * FROM customers")).all() == before
        assert conn.execute(text("SELECT failed_attempts,locked_until FROM users")).one() == (
            0,
            None,
        )
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE "
                    "command_type='identity.local_password_reset'"
                )
            ).scalar_one()
            == 1
        )
        assert NEW_PASSWORD not in json.dumps(
            [list(row) for row in conn.execute(text("SELECT * FROM audit_events"))], default=str
        )


def test_ambiguous_admin_changed_identity_and_invalid_password_do_not_reset(pg):
    identity = pg.runtime.identity
    expected = identity.local_admin()
    with pytest.raises(BusinessError, match="PASSWORD_LENGTH"):
        identity.reset_local_admin_password(expected, "short")
    with pytest.raises(BusinessError, match="RECOVERY_ACCOUNT_CHANGED"):
        identity.reset_local_admin_password(replace(expected, user_id=uuid4()), NEW_PASSWORD)
    other = identity.add_user(expected, "synthetic-operator", SYNTHETIC_PASSWORD, "operator")
    with pg.owner.begin() as conn:
        conn.execute(text("UPDATE users SET role='admin' WHERE id=:id"), {"id": other.user_id})
    with pytest.raises(BusinessError, match="RECOVERY_ADMIN_NOT_UNIQUE"):
        identity.reset_local_admin_password(expected, NEW_PASSWORD)
    assert identity.login("synthetic-admin", SYNTHETIC_PASSWORD)["actor"] == expected


def test_audit_failure_rolls_back_password_and_session_deletion(pg):
    identity = pg.runtime.identity
    expected = identity.local_admin()
    login = identity.login("synthetic-admin", SYNTHETIC_PASSWORD)
    with pg.owner.begin() as conn:
        conn.execute(
            text(
                "CREATE FUNCTION deny_reset_audit() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN IF NEW.command_type='identity.local_password_reset' THEN "
                "RAISE EXCEPTION 'synthetic audit failure'; END IF; RETURN NEW; END $$"
            )
        )
        conn.execute(
            text(
                "CREATE TRIGGER deny_reset BEFORE INSERT ON audit_events "
                "FOR EACH ROW EXECUTE FUNCTION deny_reset_audit()"
            )
        )
    with pytest.raises(Exception, match="synthetic audit failure"):
        identity.reset_local_admin_password(expected, NEW_PASSWORD)
    assert identity.authenticate(login["session_token"])[0] == expected
    assert identity.login("synthetic-admin", SYNTHETIC_PASSWORD)["actor"] == expected


def test_recovery_waits_for_in_flight_login_and_revokes_its_session(pg):
    identity = pg.runtime.identity
    expected = identity.local_admin()
    done, errors = threading.Event(), []

    def recover():
        try:
            identity.reset_local_admin_password(expected, NEW_PASSWORD)
        except Exception as error:
            errors.append(type(error).__name__)
        finally:
            done.set()

    with pg.owner.begin() as conn:
        conn.execute(text("SELECT id FROM users WHERE id=:id FOR UPDATE"), {"id": expected.user_id})
        worker = threading.Thread(target=recover)
        worker.start()
        assert not done.wait(0.35)
        conn.execute(
            text(
                "INSERT INTO sessions (token_hash,organization_id,user_id,csrf_token,expires_at) "
                "VALUES (:token,:org,:id,:csrf,now()+interval '1 hour')"
            ),
            {
                "token": hashlib.sha256(b"synthetic-concurrent-token").hexdigest(),
                "org": expected.organization_id,
                "id": expected.user_id,
                "csrf": "synthetic-concurrent-csrf",
            },
        )
    worker.join(timeout=10)
    assert done.is_set() and errors == []
    with pytest.raises(BusinessError, match="LOGIN_REQUIRED"):
        identity.authenticate("synthetic-concurrent-token")
    assert identity.login("synthetic-admin", NEW_PASSWORD)["actor"] == expected


@pytest.fixture
def recovery(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "test_recovery_entry", ROOT / "scripts/recover-offline.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls, settings = [], object()
    root = tmp_path / "synthetic-root"

    @contextmanager
    def lock():
        calls.append("lock")
        yield

    def backup(path):
        calls.append("backup")
        return {"verified": True}

    factory = SimpleNamespace(
        BASE=tmp_path,
        maintenance_lock=lock,
        active=lambda: root,
        environment=lambda path: (settings, {}),
        database_identity=lambda path: None,
        backup=backup,
    )
    account = SimpleNamespace(username="synthetic-admin")
    runtime = SimpleNamespace(
        settings=settings,
        identity=SimpleNamespace(
            reset_local_admin_password=lambda expected, password: calls.append("reset")
        ),
    )
    session = module.RecoverySession(factory, runtime, root, account, "http://127.0.0.1:12345/")
    return SimpleNamespace(session=session, calls=calls, factory=factory, runtime=runtime)


@pytest.mark.parametrize(
    "body",
    [
        BODY | {"password": "short"},
        BODY | {"confirmation": "wrong"},
        BODY | {"confirmed": False},
        BODY | {"extra": True},
        [],
    ],
)
def test_invalid_or_unconfirmed_request_never_mutates(recovery, body):
    assert recovery.session.submit(body)["phase"] == "form"
    assert recovery.calls == []


def test_replayed_submit_resets_once_and_only_after_verified_backup(recovery):
    assert recovery.session.submit(BODY)["phase"] == "ready"
    assert recovery.session.submit(BODY)["phase"] == "ready"
    assert recovery.calls == ["lock", "backup", "reset"]
    assert NEW_PASSWORD not in json.dumps(recovery.session.state())


def test_changed_environment_bad_backup_or_expiry_cannot_reset(recovery):
    recovery.factory.backup = lambda root: {"verified": False}
    assert recovery.session.submit(BODY)["phase"] == "failed"
    assert "reset" not in recovery.calls
    assert recovery.session.submit(BODY)["phase"] == "failed"
    recovery.session.phase = "form"
    recovery.session.deadline = time.monotonic() - 1
    recovery.calls.clear()
    assert recovery.session.submit(BODY)["phase"] == "failed"
    assert recovery.calls == []


def test_active_environment_changed_while_page_open_is_rejected(recovery):
    recovery.factory.active = lambda: Path("synthetic-other-environment")
    assert recovery.session.submit(BODY)["phase"] == "failed"
    assert recovery.calls == ["lock"]


def test_failure_has_no_secret_and_is_not_automatically_retried(recovery):
    def fail(*args):
        recovery.calls.append("reset")
        raise RuntimeError("postgresql://SYNTHETIC_PRIVATE_SECRET")

    recovery.runtime.identity.reset_local_admin_password = fail
    result = recovery.session.submit(BODY)
    assert result["phase"] == "failed" and "SECRET" not in json.dumps(result)
    recovery.session.submit(BODY)
    assert recovery.calls.count("reset") == 1
