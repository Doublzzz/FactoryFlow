"""Optional local browser setup. Business operations remain in factory-local.py."""

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
import secrets
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAX_BODY = 8192


class SetupSession:
    def __init__(self, factory, terms):
        self.factory = factory
        self.terms = terms
        self.terms_hash = hashlib.sha256(terms.encode("utf-8")).hexdigest()
        self.phase = "form"
        self.result = None
        self.attempted = False

    def has_active(self):
        # A damaged marker must never be interpreted as an empty installation.
        return (self.factory.BASE / "active.json").exists()

    def consented(self):
        path = self.factory.direct(self.factory.BASE / "setup-consent.json")
        if not path.exists():
            return False
        try:
            return self.factory.read(path) == {"terms_sha256": self.terms_hash}
        except ValueError, OSError:
            return False

    def state(self):
        return {
            "phase": self.phase,
            "existing": self.has_active(),
            "terms_required": not self.consented(),
            "terms": self.terms,
            "data_directory": str(self.factory.BASE),
        } | (self.result or {})

    def validate(self, body):
        errors = {}
        allowed = {"name", "username", "password", "confirmation", "accept_terms"}
        if not isinstance(body, dict) or set(body) - allowed:
            return {"form": "设置请求不完整，请重新打开启动入口。"}
        if not self.consented() and body.get("accept_terms") is not True:
            errors["accept_terms"] = "请先阅读并同意随包组件条款。"
        if not self.has_active():
            for key, maximum, label in (("name", 200, "工厂名称"), ("username", 100, "账号")):
                value = body.get(key)
                if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                    errors[key] = f"请填写{label}，最多 {maximum} 个字符。"
            password = body.get("password")
            if not isinstance(password, str) or not 12 <= len(password) <= 128:
                errors["password"] = "密码须为 12 至 128 个字符。"
            if not isinstance(body.get("confirmation"), str) or body["confirmation"] != password:
                errors["confirmation"] = "两次密码不同，请检查后再试。"
        return errors

    def submit(self, body):
        if self.phase == "ready" or (self.phase == "failed" and not self.has_active()):
            return self.result
        errors = self.validate(body)
        if errors:
            return {"phase": "form", "errors": errors, "message": "请检查下面标出的内容。"}
        entered_lock = False
        step = "检查运行状态"
        try:
            with self.factory.maintenance_lock():
                entered_lock = True
                # Another launcher may have finished while this page was open.
                existing = self.has_active()
                if not existing and self.attempted:
                    return self.result
                self.factory.save(
                    self.factory.BASE / "setup-consent.json", {"terms_sha256": self.terms_hash}
                )
                if not existing:
                    self.attempted = True
                    step = "首次建立数据"
                    self.factory.prepare(
                        body["name"].strip(), body["username"].strip(), body["password"]
                    )
                step = "启动软件"
                started = self.factory.start(self.factory.active())
                if not started.get("ready") or not started.get("api_owned"):
                    raise self.factory.LocalError("程序尚未就绪，数据仍保留。")
                self.phase = "ready"
                self.result = {
                    "phase": "ready",
                    "url": started["url"],
                    "message": "软件已就绪，请进入后用自己的账号登录。",
                }
        except Exception as error:
            if not entered_lock:
                return {
                    "phase": "form",
                    "errors": {"form": "另一个启动或维护操作正在进行，请稍后再试。"},
                }
            self.phase = "failed"
            self.result = {
                "phase": "failed",
                "can_retry": self.has_active(),
                "message": f"{step}未完成，已有文件已保留。",
                "detail": (
                    str(error)
                    if isinstance(error, self.factory.LocalError)
                    else "请保留数据目录中的日志，并联系维护人员。"
                ),
            }
            # No request body, credentials, database URL or exception text is written.
            try:
                self.factory.save(
                    self.factory.BASE / "setup-diagnostic.json",
                    {"step": step, "error_type": type(error).__name__, "active": self.has_active()},
                )
            except ValueError, OSError:
                pass
        return self.result


class SetupServer(HTTPServer):
    def __init__(self, session, template):
        self.session = session
        self.token = secrets.token_urlsafe(32)
        self.csp_nonce = secrets.token_urlsafe(24)
        self.page = template.read_text(encoding="utf-8").replace("__CSP_NONCE__", self.csp_nonce)
        super().__init__(("127.0.0.1", 0), SetupHandler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.last_request = time.monotonic()
        self.timeout = 0.5

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(10)
        return connection, address


class SetupHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, value, html=False):
        data = (value if html else json.dumps(value, ensure_ascii=False)).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8" if html else "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; "
            f"script-src 'nonce-{self.server.csp_nonce}'; "
            "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        try:
            self.wfile.write(data)
        except TimeoutError, BrokenPipeError, ConnectionResetError:
            pass  # A closed page cannot undo or repeat the completed operation.

    def authorized(self, *, write=False):
        if self.headers.get_all("Host") != [f"127.0.0.1:{self.server.server_port}"]:
            self.reply(403, {"message": "请从本机启动入口打开。"})
            return False
        if write and self.headers.get_all("Origin") != [self.server.origin]:
            self.reply(403, {"message": "设置请求来源无效。"})
            return False
        tokens = self.headers.get_all("X-FactoryFlow-Setup") or []
        if len(tokens) != 1 or not secrets.compare_digest(tokens[0], self.server.token):
            self.reply(403, {"message": "设置页面已失效，请重新打开启动入口。"})
            return False
        self.server.last_request = time.monotonic()
        return True

    def do_GET(self):
        if self.path == "/":
            if self.headers.get_all("Host") != [f"127.0.0.1:{self.server.server_port}"]:
                self.reply(403, {"message": "请从本机启动入口打开。"})
            else:
                self.reply(200, self.server.page, html=True)
        elif self.path == "/state":
            if self.authorized():
                self.reply(200, self.server.session.state())
        else:
            self.reply(404, {"message": "页面不存在。"})

    def do_POST(self):
        if not self.authorized(write=True):
            return
        if self.path != "/start":
            self.reply(404, {"message": "操作不存在。"})
            return
        if self.headers.get("Content-Type") != "application/json":
            self.reply(415, {"message": "设置请求格式不正确。"})
            return
        try:
            lengths = self.headers.get_all("Content-Length") or []
            if len(lengths) != 1 or self.headers.get("Transfer-Encoding"):
                raise ValueError
            length = int(lengths[0])
            if length < 1 or length > MAX_BODY:
                self.reply(413, {"message": "设置请求过大或为空。"})
                return
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except TimeoutError, ValueError, UnicodeError:
            self.reply(400, {"message": "设置请求未完整收到，请重新检查页面状态。"})
            return
        self.reply(200, self.server.session.submit(body))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def preflight(app, data_root):
    for path in (app, data_root):
        if not path.is_absolute() or path.absolute() != path.resolve():
            raise ValueError("程序和测试数据目录不能包含链接或映射目录。")
    parent = data_root
    while not parent.exists():
        if parent.parent == parent:
            raise ValueError("测试数据所在磁盘不存在，请检查完整路径。")
        parent = parent.parent
    try:
        with tempfile.TemporaryFile(dir=parent):
            pass
    except OSError:
        raise ValueError("测试数据目录不可写，请选择自己有写入权限的目录。") from None


def open_window(factory, url):
    if factory.open_browser(url) is False:
        ctypes.windll.user32.MessageBoxW(
            None,
            "未找到 Chrome 或新版 Edge，请在浏览器中打开以下地址。\n"
            "可按 Ctrl+C 复制此提示：\n\n" + url,
            "交有数 · 打开设置页面",
            0x40,
        )


def run(factory, session, template):
    if session.has_active() and session.consented():
        result = session.submit({})
        if result["phase"] == "ready":
            open_window(factory, result["url"])
            return
    with SetupServer(session, template) as server:
        # The secret is a fragment, never an HTTP URL, query string or access log.
        open_window(factory, server.origin + "/#" + server.token)
        ready_at = None
        while time.monotonic() - server.last_request < 900:
            server.handle_request()  # A running setup finishes even after the page closes.
            if session.phase == "ready":
                ready_at = ready_at or time.monotonic()
                if time.monotonic() - ready_at > 60:
                    break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    app = HERE.parent
    preflight(app, args.data_root)
    installer = load_module("offline_install_support", HERE / "install-offline.py")
    manifest = installer.verify(app)
    if manifest.get("python") != os.sys.version.split()[0]:
        raise ValueError("启动程序与随包运行库版本不一致，请使用本包启动入口。")
    terms = installer.microsoft_terms(app)
    factory = load_module("offline_operations", HERE / "factory-local.py")
    factory.path_encoding()
    factory.BASE = factory.direct(args.data_root)
    run(factory, SetupSession(factory, terms), HERE / "offline-setup.html")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        message = (
            str(error)
            if isinstance(error, ValueError)
            else "软件未能启动，请保留数据目录与安装包，并联系维护人员。"
        )
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(None, message, "交有数 · 启动未完成", 0x10)
        raise SystemExit(1) from None
