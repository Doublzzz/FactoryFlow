"""OS-user initiated, local-only administrator password recovery; no remote reset API."""

import argparse
import ctypes
import importlib.util
import os
import time
from pathlib import Path

from factoryflow.bootstrap import build_services
from factoryflow.kernel.contracts import BusinessError

HERE = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecoverySession:
    def __init__(self, factory, runtime, root, account, url, language="zh-CN"):
        self.factory, self.runtime = factory, runtime
        self.root, self.account, self.url = root, account, url
        self.language = language
        self.phase, self.result = "form", None
        self.deadline = time.monotonic() + 900

    def tr(self, chinese, english):
        return english if self.language == "en" else chinese

    def state(self):
        return {
            "phase": self.phase,
            "language": self.language,
            "username": self.account.username,
            "data_directory": str(self.factory.BASE),
        } | (self.result or {})

    def submit(self, body):
        if self.phase != "form":
            return self.result  # Replayed/lost-response submissions never reset twice.
        if time.monotonic() >= self.deadline:
            self.phase = "failed"
            self.result = {
                "phase": "failed",
                "message": self.tr(
                    "页面已过期，请关闭后重新打开重设密码入口。",
                    "This page has expired. Close it and open Reset Login Password again.",
                ),
            }
            return self.result
        errors = {}
        if not isinstance(body, dict) or set(body) != {"password", "confirmation", "confirmed"}:
            errors["form"] = self.tr("请求不完整，请重新打开页面。", "Reopen the recovery page.")
        else:
            password = body["password"]
            if not isinstance(password, str) or not 12 <= len(password) <= 128:
                errors["password"] = self.tr(
                    "密码须为 12 至 128 个字符。", "Use 12 to 128 characters."
                )
            if not isinstance(body["confirmation"], str) or body["confirmation"] != password:
                errors["confirmation"] = self.tr(
                    "两次密码不同，请检查后再试。", "The passwords do not match."
                )
            if body["confirmed"] is not True:
                errors["confirmed"] = self.tr(
                    "请确认你有权管理这台电脑上的工厂账号。",
                    "Confirm you manage this factory account.",
                )
        if errors:
            return {"phase": "form", "errors": errors}
        entered = False
        try:
            with self.factory.maintenance_lock():
                entered = True
                if (
                    self.factory.active() != self.root
                    or self.factory.environment(self.root)[0] != self.runtime.settings
                ):
                    raise ValueError("RECOVERY_ENVIRONMENT_CHANGED")
                self.factory.database_identity(self.root)
                # The backup is complete and verified before changing any login credential.
                backup = self.factory.backup(self.root)
                if backup.get("verified") is not True:
                    raise ValueError("RECOVERY_BACKUP_NOT_VERIFIED")
                self.runtime.identity.reset_local_admin_password(self.account, body["password"])
                self.phase = "ready"
                self.result = {
                    "phase": "ready",
                    "url": self.url,
                    "message": self.tr(
                        "密码已重设，账号和业务数据已保留。请用新密码登录。",
                        "Password reset. Your account and business data are retained. "
                        "Sign in again.",
                    ),
                }
        except Exception:
            if not entered:
                return {
                    "phase": "form",
                    "errors": {
                        "form": self.tr(
                            "另一个维护操作正在进行，请稍后再试。",
                            "Another maintenance operation is running. Try again shortly.",
                        )
                    },
                }
            self.phase = "failed"
            self.result = {
                "phase": "failed",
                "message": self.tr(
                    "未能确认重设结果。请先尝试用新密码登录；如仍失败，保留数据并联系维护人员。",
                    "The reset result could not be confirmed. Try the new password; "
                    "if that fails, retain your data and contact support.",
                ),
            }
            # Deliberately omit exception text, database URLs, usernames and password material.
        return self.result


def run(factory, runtime, setup, template, language):
    with factory.maintenance_lock():
        root = factory.active()
        if factory.environment(root)[0] != runtime.settings:
            raise ValueError("RECOVERY_ENVIRONMENT_CHANGED")
        factory.database_identity(root)
        status = factory.status(root)
        if not status.get("ready") or not status.get("api_owned") or status.get("restart_required"):
            raise ValueError("请先从当前版本启动软件，再打开重设密码。 / Start this version first.")
        account = runtime.identity.local_admin()
    session = RecoverySession(factory, runtime, root, account, status["url"], language)
    with setup.SetupServer(session, template) as server:
        setup.open_window(factory, server.origin + "/#" + server.token)
        finished_at = None
        while time.monotonic() < session.deadline:
            server.handle_request()
            if session.phase != "form":
                finished_at = finished_at or time.monotonic()
                if time.monotonic() - finished_at > 60:
                    break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=HERE.parent)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--language", choices=["zh-CN", "en"], default="zh-CN")
    args = parser.parse_args()
    setup = load_module("recovery_transport", HERE / "launch-offline.py")
    factory = load_module("recovery_factory", args.app / "scripts/factory-local.py")
    factory.LANGUAGE = args.language
    if args.data_root:
        factory.BASE = factory.direct(args.data_root)
    setup.preflight(args.app, factory.BASE)
    installer = load_module("recovery_installer", args.app / "scripts/install-offline.py")
    manifest = installer.verify(args.app)
    if manifest.get("python") != os.sys.version.split()[0]:
        raise ValueError("请使用安装包自带的重设入口。 / Use the installed recovery entry.")
    factory.path_encoding()
    root = factory.active()
    runtime = build_services(factory.environment(root)[0])
    try:
        run(factory, runtime, setup, HERE / "offline-recovery.html", args.language)
    finally:
        runtime.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        message = (
            "无法打开密码恢复。请确认已启动软件，且当前工厂只有一个启用的管理员账号。"
            "现有数据未重建。 / Recovery could not open. Start the app and check that "
            "there is exactly one active administrator. Existing data is retained."
        )
        if isinstance(error, BusinessError) and error.code == "RECOVERY_ADMIN_NOT_UNIQUE":
            message = (
                "管理员账号不唯一，未修改任何密码，请联系维护人员。 / Administrator is not unique."
            )
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(None, message, "交有数 · 账号恢复", 0x10)
        raise SystemExit(1) from None
