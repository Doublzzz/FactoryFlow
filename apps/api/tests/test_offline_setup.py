"""Local setup requests cannot overwrite an account or repeat an uncertain setup."""

import importlib.util
import json
import threading
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
BODY = {
    "name": "合成测试工厂",
    "username": "synthetic-admin",
    "password": "Synthetic-Password-123",
    "confirmation": "Synthetic-Password-123",
    "accept_terms": True,
}


@pytest.fixture
def setup(tmp_path):
    path = ROOT / "scripts/launch-offline.py"
    assert path.is_file(), "The browser setup entry is not implemented"
    spec = importlib.util.spec_from_file_location("offline_setup", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    base = tmp_path / "synthetic-data"
    failure = {"prepare_after_active": False, "start": False, "locked": False}

    class LocalError(ValueError):
        pass

    @contextmanager
    def lock():
        if failure["locked"]:
            raise LocalError("Another factory maintenance operation is running; retry later")
        calls.append("lock")
        try:
            yield
        finally:
            calls.append("unlock")

    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def prepare(name, username, password):
        assert not (base / "active.json").exists()
        calls.append(("prepare", name, username, password))
        save(base / "active.json", {"id": "a" * 32})
        if failure["prepare_after_active"]:
            raise LocalError("Setup exists but the final stop needs inspection")

    def active():
        return json.loads((base / "active.json").read_text())["id"]

    def start(root):
        calls.append(("start", root))
        if failure["start"]:
            raise RuntimeError("postgresql://SYNTHETIC_SECRET@localhost/secret")
        return {"url": "http://127.0.0.1:61234/", "ready": True, "api_owned": True}

    factory = SimpleNamespace(
        BASE=base,
        LocalError=LocalError,
        maintenance_lock=lock,
        prepare=prepare,
        active=active,
        start=start,
        save=save,
        read=lambda path: json.loads(path.read_text(encoding="utf-8")),
        direct=lambda path: path,
    )
    session = module.SetupSession(factory, "Synthetic component terms")
    return SimpleNamespace(
        module=module, session=session, factory=factory, calls=calls, failure=failure
    )


@pytest.mark.parametrize(
    "changed,field",
    [
        ({"name": "  "}, "name"),
        ({"name": "x" * 201}, "name"),
        ({"username": ""}, "username"),
        ({"username": "x" * 101}, "username"),
        ({"password": "short", "confirmation": "short"}, "password"),
        ({"confirmation": "different"}, "confirmation"),
        ({"accept_terms": False}, "accept_terms"),
    ],
)
def test_invalid_input_never_creates_data(setup, changed, field):
    response = setup.session.submit(BODY | changed)
    assert response["phase"] == "form" and field in response["errors"]
    assert not setup.factory.BASE.exists()
    assert setup.calls == []


def test_confirmation_and_password_are_not_trimmed(setup):
    response = setup.session.submit(BODY | {"password": BODY["password"] + " "})
    assert "confirmation" in response["errors"]
    assert not setup.factory.BASE.exists()


def test_setup_is_locked_and_duplicate_response_does_not_repeat_prepare(setup):
    response = setup.session.submit(BODY | {"name": "  合成测试工厂  "})
    assert response["phase"] == "ready"
    assert setup.calls == [
        "lock",
        ("prepare", "合成测试工厂", BODY["username"], BODY["password"]),
        ("start", "a" * 32),
        "unlock",
    ]
    calls = setup.calls.copy()
    assert setup.session.submit(BODY) == response
    assert setup.calls == calls
    saved = list(setup.factory.BASE.glob("*.json"))
    assert saved
    assert all(BODY["password"] not in path.read_text() for path in saved)


def test_other_window_finishing_setup_is_rechecked_under_lock(setup):
    setup.factory.save(setup.factory.BASE / "active.json", {"id": "b" * 32})
    response = setup.session.submit(BODY)
    assert response["phase"] == "ready"
    assert setup.calls == ["lock", ("start", "b" * 32), "unlock"]


def test_failed_response_after_active_never_initializes_again(setup):
    setup.failure["prepare_after_active"] = True
    first = setup.session.submit(BODY)
    assert first["phase"] == "failed" and first["can_retry"]
    assert setup.session.submit({})["phase"] == "ready"
    assert sum(isinstance(call, tuple) and call[0] == "prepare" for call in setup.calls) == 1


def test_failed_setup_without_active_is_not_automatically_repeated(setup):
    def failed_prepare(*args):
        setup.calls.append(("prepare",))
        raise setup.factory.LocalError("Synthetic initialization failure")

    setup.factory.prepare = failed_prepare
    first = setup.session.submit(BODY)
    assert first["phase"] == "failed" and not first["can_retry"]
    second = setup.session.submit(BODY)
    assert second == first
    assert setup.calls.count(("prepare",)) == 1


def test_corrupt_active_is_never_treated_as_empty_database(setup):
    setup.factory.BASE.mkdir()
    (setup.factory.BASE / "active.json").write_text("broken JSON")
    result = setup.session.submit({"accept_terms": True})
    assert result["phase"] == "failed"
    assert not any(isinstance(call, tuple) and call[0] == "prepare" for call in setup.calls)
    assert (setup.factory.BASE / "active.json").read_text() == "broken JSON"


def test_maintenance_conflict_is_safe_to_retry_and_error_does_not_leak_secret(setup):
    setup.failure["locked"] = True
    result = setup.session.submit(BODY)
    assert result["phase"] == "form" and not setup.factory.BASE.exists()
    setup.failure["locked"] = False
    setup.failure["start"] = True
    result = setup.session.submit(BODY)
    assert result["phase"] == "failed" and result["can_retry"]
    assert "SYNTHETIC_SECRET" not in json.dumps(result)
    setup.failure["start"] = False
    assert setup.session.submit({})["phase"] == "ready"


@pytest.fixture
def http_setup(setup):
    template = ROOT / "scripts/offline-setup.html"
    server = setup.module.SetupServer(setup.session, template)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield setup, server
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


def request(server, method, path, body=None, headers=None):
    conn = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    given = {
        "Host": f"127.0.0.1:{server.server_port}",
        "Origin": server.origin,
        "X-FactoryFlow-Setup": server.token,
        "Content-Type": "application/json",
    }
    given.update(headers or {})
    conn.request(method, path, body=body, headers=given)
    response = conn.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    conn.close()
    return result


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "attacker.invalid"},
        {"Origin": "https://attacker.invalid"},
        {"Origin": "null"},
        {"X-FactoryFlow-Setup": "wrong"},
        {"Content-Type": "application/x-www-form-urlencoded"},
    ],
)
def test_cross_site_or_non_json_request_cannot_create_account(http_setup, headers):
    setup, server = http_setup
    status, response_headers, _ = request(
        server, "POST", "/start", json.dumps(BODY), headers=headers
    )
    assert 400 <= status < 500
    assert "Access-Control-Allow-Origin" not in response_headers
    assert setup.calls == [] and not setup.factory.BASE.exists()


def test_get_cannot_write_and_oversize_request_is_rejected(http_setup):
    setup, server = http_setup
    assert request(server, "GET", "/start")[0] == 404
    assert request(server, "POST", "/start", "x" * 9000)[0] == 413
    assert setup.calls == []


def test_page_contains_no_token_and_nonce_is_required_for_state(http_setup):
    setup, server = http_setup
    status, headers, content = request(server, "GET", "/")
    assert status == 200 and "Content-Security-Policy" in headers
    assert server.token.encode() not in content
    assert BODY["password"].encode() not in content
    assert request(server, "GET", "/state", headers={"X-FactoryFlow-Setup": ""})[0] == 403
    assert request(server, "GET", "/state")[0] == 200
    assert setup.calls == []


def test_browser_post_replay_returns_same_result_without_request_logging(http_setup, capsys):
    setup, server = http_setup
    first = request(server, "POST", "/start", json.dumps(BODY))
    second = request(server, "POST", "/start", json.dumps(BODY))
    assert first[0] == second[0] == 200
    assert json.loads(first[2])["phase"] == json.loads(second[2])["phase"] == "ready"
    assert sum(isinstance(call, tuple) and call[0] == "prepare" for call in setup.calls) == 1
    output = capsys.readouterr()
    assert BODY["password"] not in output.out + output.err
    assert server.token not in output.out + output.err


@pytest.mark.parametrize("which", ["program", "data"])
def test_full_chinese_path_is_allowed_without_creating_environment(setup, tmp_path, which):
    program = tmp_path / "program"
    data = tmp_path / "data"
    if which == "program":
        program = tmp_path / "中文用户" / "program"
    else:
        data = tmp_path / "中文用户" / "data"
    setup.module.preflight(program, data)
    assert not program.exists() and not data.exists()


def test_missing_drive_reports_error_instead_of_looping(setup, tmp_path):
    class MissingDrive:
        parent = property(lambda self: self)

        def __str__(self):
            return "Z:/"

        def is_absolute(self):
            return True

        def absolute(self):
            return self

        def resolve(self):
            return self

        def exists(self):
            return False

    with pytest.raises(ValueError, match="磁盘不存在"):
        setup.module.preflight(tmp_path / "program", MissingDrive())


def test_hidden_launcher_has_visible_browser_fallback(setup, monkeypatch):
    messages = []
    monkeypatch.setattr(
        setup.module,
        "ctypes",
        SimpleNamespace(
            windll=SimpleNamespace(
                user32=SimpleNamespace(MessageBoxW=lambda *args: messages.append(args))
            )
        ),
    )
    setup.module.open_window(
        SimpleNamespace(open_browser=lambda _: False), "http://127.0.0.1:12345/"
    )
    assert len(messages) == 1 and "http://127.0.0.1:12345/" in messages[0][1]
