"""Offline factory operations. Empty first setup; private persistent data outside the app."""

import argparse
import ctypes
import getpass
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import psycopg
from factoryflow.bootstrap import build_services, create_app
from factoryflow.kernel.contracts import BusinessError
from factoryflow.platform.backup import restore_backup, validate_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import REVISION, engine_for
from factoryflow.platform.migrations import upgrade_database
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url

PROJECT = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FactoryFlow" / "data"
SCRIPT = Path(__file__).resolve()
BIN = PROJECT / "runtime/postgresql/bin"
WEB = PROJECT / "apps/web/dist"
OCR_PYTHON = PROJECT / "runtime/ocr/python.exe"
KIND = "factoryflow-business-v1"
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
LANGUAGE = "zh-CN"


def tr(chinese, english):
    return english if LANGUAGE == "en" else chinese


class LocalError(ValueError):
    """Credential-free operator message."""


def direct(path):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise LocalError("Factory data paths must not contain symbolic links or junctions")
    return path


@contextmanager
def maintenance_lock():
    import msvcrt

    direct(BASE).mkdir(parents=True, exist_ok=True)
    with direct(BASE / "maintenance.lock").open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise LocalError(
                "Another factory maintenance operation is running; retry later"
            ) from None
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def save(path, value):
    direct(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = direct(path.with_suffix(path.suffix + ".tmp"))
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def available(port):
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError as failure:
            raise LocalError(f"Port {port} is occupied; nothing was stopped") from failure


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def pg(name, *args, check=True):
    result = subprocess.run(
        [str(BIN / f"{name}.exe"), *map(str, args)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
        creationflags=FLAGS,
    )
    if check and result.returncode:
        raise LocalError(f"PostgreSQL {name} failed; inspect the owned private postgres.log")
    return result.returncode


def database_start(root):
    _, state = environment(root)
    if pg("pg_ctl", "-D", root / "pgdata", "status", check=False) == 0:
        database_identity(root)
        return
    available(state["port"])
    pg("pg_ctl", "-D", root / "pgdata", "-l", root / "postgres.log", "-w", "start")
    database_identity(root)


def database_identity(root):
    _, state = environment(root)
    with psycopg.connect(state["admin_url"], connect_timeout=3) as conn:
        data = conn.execute("SHOW data_directory").fetchone()[0]
        if Path(data).resolve() != (root / "pgdata").resolve():
            raise LocalError("Database process belongs to another data directory")


def _process_handle(pid, access):
    if os.name != "nt":
        raise LocalError("This factory installation requires Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p, *([ctypes.c_void_p] * 4)]
    kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    handle = kernel.OpenProcess(access, False, pid)
    return kernel, handle


def _creation(kernel, handle):
    values = [ctypes.c_uint64() for _ in range(4)]
    if not kernel.GetProcessTimes(handle, *[ctypes.byref(v) for v in values]):
        raise LocalError("Cannot verify process creation identity")
    return str(values[0].value)


def process(pid):
    kernel, handle = _process_handle(int(pid), 0x1000)
    if not handle:
        return None
    try:
        created = _creation(kernel, handle)
        command = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); "
                f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=FLAGS,
            check=True,
        ).stdout.strip()
        return {"pid": int(pid), "created": created, "command": command}
    finally:
        kernel.CloseHandle(handle)


def matches_process(record, running):
    if not running or any(record[k] != running[k] for k in ("pid", "created")):
        return False
    command = running["command"].replace("\\", "/").casefold()
    root = record["root"].replace("\\", "/").casefold()
    return bool(
        "factory-local.py" in command
        and re.search(r"\bserve\s", command)
        and re.search(r'--root\s+"?' + re.escape(root) + r'"?(?:\s|$)', command)
    )


def stop_api(root):
    path = root / "server-process.json"
    if not path.is_file():
        return
    record = read(path)
    if record.get("root") != str(root):
        raise LocalError("Server record belongs to another environment")
    running = process(record["pid"])
    if not running:
        return
    if not matches_process(record, running):
        raise LocalError("PID was reused or ownership changed; process left untouched")
    kernel, handle = _process_handle(record["pid"], 0x1001)
    if not handle:
        return
    try:
        if _creation(kernel, handle) != record["created"]:
            raise LocalError("Process changed during stop; left untouched")
        if not kernel.TerminateProcess(handle, 0):
            raise LocalError("Owned API could not be stopped")
    finally:
        kernel.CloseHandle(handle)
    for _ in range(30):
        try:
            available(read(root / "private-state.json")["api_port"])
            return
        except ValueError:
            time.sleep(0.1)
    raise LocalError("API port did not close; database left running")


def stop(root):
    _, state = environment(root)
    stop_api(root)
    available(state["api_port"])
    if pg("pg_ctl", "-D", root / "pgdata", "status", check=False) == 0:
        database_identity(root)
        pg("pg_ctl", "-D", root / "pgdata", "-m", "fast", "-w", "stop")
    available(state["port"])
    return {"state": "stopped", "environment": root.name, "data_retained": True}


def owned(path):
    direct(BASE)
    root = direct(path)
    if root.parent != (BASE / "environments").resolve() or not re.fullmatch(
        "[a-f0-9]{32}", root.name
    ):
        raise LocalError(
            tr(
                "不属于 FactoryFlow 的业务数据目录，未进行操作。",
                "This data directory does not belong to FactoryFlow. No operation was performed.",
            )
        )
    for name in (
        "owner.json",
        "private-state.json",
        "pgdata",
        "objects",
        "archives",
        "server-process.json",
        "postgres.log",
        "server.log",
    ):
        direct(root / name)
    if read(root / "owner.json") != {"kind": KIND, "id": root.name}:
        raise LocalError(
            tr(
                "业务数据目录标记不匹配，未进行操作。",
                "The business data directory marker does not match. No operation was performed.",
            )
        )
    return root


def active():
    return owned(BASE / "environments" / read(direct(BASE / "active.json"))["id"])


def environment(root):
    root = owned(root)
    state = read(root / "private-state.json")
    admin = make_url(state["admin_url"])
    if (
        admin.host != "127.0.0.1"
        or admin.username != "ff_admin"
        or admin.database != "postgres"
        or admin.query
        or admin.port != state["port"]
        or any(
            type(state[k]) is not int or not 1024 <= state[k] <= 65535 for k in ("port", "api_port")
        )
        or state["port"] == state["api_port"]
    ):
        raise LocalError(
            tr(
                "本机业务配置不匹配，未进行操作。",
                "The local business configuration does not match. No operation was performed.",
            )
        )
    runtime_url = admin.set(
        drivername="postgresql+psycopg",
        database="factoryflow_business",
        username="ff_runtime",
        password=state["runtime_password"],
    )
    return Settings(
        runtime_url.render_as_string(hide_password=False),
        root / "objects",
        ocr_engine="rapid",
        ocr_python=OCR_PYTHON,
        archive_root=root / "archives",
    ), state


def build_id():
    return read(PROJECT / "bundle.json")["build_id"]


def ready(url):
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url + "api/v1/health/ready", timeout=2) as response:
            return response.status == 200
    except urllib.error.URLError, TimeoutError, OSError:
        return False


def status(root):
    _, state = environment(root)
    path = root / "server-process.json"
    record = read(path) if path.is_file() else None
    running = process(record["pid"]) if record else None
    ours = bool(record and record.get("root") == str(root) and matches_process(record, running))
    url = f"http://127.0.0.1:{state['api_port']}/"
    db_running = pg("pg_ctl", "-D", root / "pgdata", "status", check=False) == 0
    schema = None
    if db_running:
        database_identity(root)
        engine = engine_for(environment(root)[0].database_url)
        try:
            with engine.connect() as conn:
                schema = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        finally:
            engine.dispose()
    return {
        "environment": root.name,
        "url": url,
        "database_running": db_running,
        "api_owned": ours,
        "ready": ours and ready(url),
        "schema": schema,
        "expected_schema": REVISION,
        "restart_required": ours and record.get("build_id") != build_id(),
        "data_directory": str(BASE),
    }


def start(root):
    if not (WEB / "index.html").is_file():
        raise LocalError(
            tr(
                "网页文件不完整，请重新解压完整安装包。",
                "Web files are incomplete. Extract the complete installation bundle again.",
            )
        )
    before = status(root)
    if before["ready"]:
        if before["restart_required"]:
            raise LocalError(
                tr(
                    "请先运行“停止工厂软件”，再启动新版本。",
                    "Run Stop FactoryFlow before starting the new version.",
                )
            )
        return before
    if before["api_owned"]:
        raise LocalError(
            tr(
                "已有程序尚未就绪，请先停止再启动；业务数据仍保留。",
                "The program is not ready. Stop it and start again; business data is retained.",
            )
        )
    _, state = environment(root)
    available(state["api_port"])
    database_start(root)
    runtime = build_services(environment(root)[0])
    try:
        runtime.check_ready()  # Startup does not migrate or replace existing business data.
    finally:
        runtime.close()
    with (root / "server.log").open("ab") as log:
        subprocess.Popen(
            [
                sys.executable,
                "-I",
                str(SCRIPT),
                "serve",
                "--root",
                str(root),
                "--data-root",
                str(BASE),
                "--language",
                LANGUAGE,
            ],
            cwd=PROJECT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            creationflags=FLAGS,
        )
    for _ in range(100):
        if ready(before["url"]):
            result = status(root)
            if result["api_owned"]:
                return result
        time.sleep(0.2)
    raise LocalError(
        tr(
            "启动未完成；业务数据保留。请查看数据目录中的 server.log。",
            "Startup failed; business data is retained. Check server.log in the data directory.",
        )
    )


def serve(root):
    import uvicorn

    settings, state = environment(root)
    application = create_app(settings=settings, web_directory=WEB)
    application.state.services.check_ready()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", state["api_port"]))
        listener.listen(128)
        save(
            root / "server-process.json",
            process(os.getpid()) | {"root": str(root), "build_id": build_id()},
        )
        config = uvicorn.Config(
            application, host="127.0.0.1", port=state["api_port"], access_log=False
        )
        uvicorn.Server(config).run(sockets=[listener])


def new_cluster(api_port=None):
    root = direct(BASE / "environments" / uuid4().hex)
    root.mkdir(parents=True)
    save(root / "owner.json", {"kind": KIND, "id": root.name})
    api_port = api_port or free_port()
    available(api_port)
    port = free_port()
    while port == api_port:
        port = free_port()
    admin_password, runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    state = {
        "admin_url": f"postgresql://ff_admin:{admin_password}@127.0.0.1:{port}/postgres",
        "runtime_password": runtime_password,
        "port": port,
        "api_port": api_port,
    }
    save(root / "private-state.json", state)
    password_file = direct(root / "init-password.tmp")
    try:
        try:
            password_file.write_text(admin_password, encoding="utf-8")
            pg(
                "initdb",
                "-D",
                root / "pgdata",
                "-U",
                "ff_admin",
                "--pwfile",
                password_file,
                "--auth=scram-sha-256",
                "--encoding=UTF8",
                "--locale=C",
            )
        finally:
            password_file.unlink(missing_ok=True)
        with (root / "pgdata/postgresql.conf").open("a", encoding="utf-8") as stream:
            stream.write(
                f"\nlisten_addresses='127.0.0.1'\nport={port}\nlog_statement='none'\n"
                "log_min_error_statement='panic'\n"
            )
        database_start(root)
        with psycopg.connect(state["admin_url"], autocommit=True) as conn:
            conn.execute(
                sql.SQL("CREATE ROLE ff_runtime LOGIN PASSWORD {}").format(
                    sql.Literal(runtime_password)
                )
            )
    except Exception:
        try:
            if pg("pg_ctl", "-D", root / "pgdata", "status", check=False) == 0:
                database_identity(root)
                pg("pg_ctl", "-D", root / "pgdata", "-m", "fast", "-w", "stop")
        except Exception:
            raise LocalError(
                tr(
                    f"首次建立未完成，目录 {root.name} 的停止状态需检查；文件已保留。",
                    f"Initial setup failed. Check whether directory {root.name} is stopped; "
                    "files were retained.",
                )
            ) from None
        raise LocalError(
            tr(
                f"首次建立未完成，目录 {root.name} 已停止并保留；请检查随包运行库。",
                f"Initial setup failed. Directory {root.name} was stopped and retained; "
                "check the bundled runtimes.",
            )
        ) from None
    return root


def prepare(name, username, password):
    if (BASE / "active.json").exists():
        raise LocalError(
            tr(
                "业务数据已经存在，请直接启动。首次设置不会覆盖旧数据。",
                "Business data already exists. Start the app directly; "
                "initial setup will not overwrite it.",
            )
        )
    # Validate before creating the cluster; credentials never enter process arguments or logs.
    if not name.strip() or len(name) > 200 or not username.strip() or len(username) > 100:
        raise LocalError(
            tr("工厂名称或账号长度不正确。", "Factory name or username has an invalid length.")
        )
    if not 12 <= len(password) <= 128:
        raise LocalError(
            tr("密码须为 12 至 128 个字符。", "Password must contain 12 to 128 characters.")
        )
    root = new_cluster()
    try:
        _, state = environment(root)
        with psycopg.connect(state["admin_url"], autocommit=True) as conn:
            conn.execute("CREATE DATABASE factoryflow_business OWNER ff_admin")
        owner_url = make_url(state["admin_url"]).set(
            drivername="postgresql+psycopg", database="factoryflow_business"
        )
        owner = engine_for(owner_url.render_as_string(hide_password=False))
        try:
            upgrade_database(owner, PROJECT)
        finally:
            owner.dispose()
        (root / "objects").mkdir()
        runtime = build_services(environment(root)[0])
        try:
            runtime.identity.provision_factory(name, username, password)
            runtime.check_ready()
        finally:
            runtime.close()
        save(BASE / "active.json", {"id": root.name})
    finally:
        stop(root)
    return {"state": "prepared", "environment": root.name, "business_rows": 0}


def backup(root):
    database_start(root)
    target = direct(
        BASE / "backups" / (datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:8])
    )
    runtime = build_services(environment(root)[0])
    try:
        manifest = runtime.backup(target, BIN)
    finally:
        runtime.close()
    validate_backup(target)
    return {
        "backup": str(target),
        "verified": True,
        "schema": manifest["schema_revision"],
        "objects": len(manifest["objects"]),
    }


def restore(path):
    path = direct(path)
    validate_backup(path)  # A copied backup works even on a new computer with no active data.
    previous = active() if (BASE / "active.json").exists() else None
    root = new_cluster()
    try:
        _, state = environment(root)
        restore_backup(
            state["admin_url"], "factoryflow_business", root / "objects", path, BIN, PROJECT
        )
        runtime = build_services(environment(root)[0])
        try:
            runtime.check_ready()
        finally:
            runtime.close()
    finally:
        stop(root)
    if previous is not None:
        stop(previous)
    save(BASE / "active.json", {"id": root.name})
    return {
        "state": "restored",
        "environment": root.name,
        "old_data_retained": True,
        "previous_environment": previous.name if previous else None,
    }


def open_browser(url):
    candidates = [
        Path(os.environ.get(name, "")) / suffix
        for name, suffix in (
            ("PROGRAMFILES", "Google/Chrome/Application/chrome.exe"),
            ("PROGRAMFILES(X86)", "Google/Chrome/Application/chrome.exe"),
            ("LOCALAPPDATA", "Google/Chrome/Application/chrome.exe"),
            ("PROGRAMFILES(X86)", "Microsoft/Edge/Application/msedge.exe"),
        )
    ]
    for executable in candidates:
        if executable.is_file():
            subprocess.Popen([str(executable), url], creationflags=FLAGS)
            return
    print(
        tr(
            "请用 Chrome 或新版 Edge 打开：",
            "Open this address in Chrome or a recent version of Edge: ",
        )
        + url
    )


def password_input(prompt):
    # Windows getpass otherwise waits on a console even when input is an explicit pipe.
    return getpass.getpass(prompt) if sys.stdin.isatty() else input(prompt)


def main():
    global BASE, LANGUAGE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status", "backup", "restore", "serve"])
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--language", choices=["zh-CN", "en"], default="zh-CN")
    args = parser.parse_args()
    LANGUAGE = args.language
    if args.data_root:
        BASE = direct(args.data_root)
    if os.name != "nt" or sys.getwindowsversion().major < 10 or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise LocalError(
            tr(
                "此安装包需要 Windows 10/11 64 位系统。",
                "This bundle requires 64-bit Windows 10 or 11.",
            )
        )
    if args.action == "serve":
        if not args.root:
            parser.error("serve requires --root")
        serve(args.root)
        return
    with maintenance_lock():
        if args.action == "start":
            if not (BASE / "active.json").exists():
                print(
                    tr(
                        "首次使用：建立空白业务库。此后每天直接启动即可。",
                        "First use: set up an empty business database. "
                        "On later days, simply start the app.",
                    )
                )
                name = input(tr("工厂名称：", "Factory name: ")).strip()
                username = input(tr("登录账号：", "Username: ")).strip()
                password = password_input(
                    tr(
                        "设置密码（12 字符以上，输入时不显示）：",
                        "Password (12 to 128 characters; hidden when typed): ",
                    )
                )
                if password_input(tr("再次输入密码：", "Repeat password: ")) != password:
                    raise LocalError(
                        tr(
                            "两次密码不同，尚未建立业务库，请重新启动。",
                            "Passwords do not match. No database was created; start again.",
                        )
                    )
                prepare(name, username, password)
            result = start(active())
            print(tr("FactoryFlow 已启动：", "FactoryFlow started: ") + result["url"])
            print(
                tr(
                    "关闭浏览器前请保存录入。下班时运行“停止工厂软件”。",
                    "Save your work before closing the browser. Run Stop FactoryFlow to finish.",
                )
            )
            if not args.no_browser:
                open_browser(result["url"] + ("?lang=en" if LANGUAGE == "en" else ""))
        elif args.action == "restore":
            path = args.backup or Path(
                input(
                    tr("请粘贴备份文件夹完整路径：", "Paste the full path of the backup folder: ")
                )
                .strip()
                .strip('"')
            )
            if (
                not args.backup
                and input(
                    tr(
                        "将恢复到新目录并切换使用，旧数据保留。继续？输入 Y：",
                        "Restore into a new directory and switch to it, retaining the old data? "
                        "Type Y to continue: ",
                    )
                ).upper()
                != "Y"
            ):
                return
            result = restore(path)
            print(
                tr(
                    "备份已恢复。请运行“启动工厂软件”，用原账号登录。",
                    "Backup restored. Run Start FactoryFlow and use your original account.",
                )
            )
        else:
            result = {"stop": stop, "status": status, "backup": backup}[args.action](active())
            if args.action == "backup":
                print(
                    tr(
                        "备份已校验，请将整个文件夹复制到 U 盘：\n",
                        "Backup verified. Copy this entire folder to a USB drive:\n",
                    )
                    + result["backup"]
                )
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (LocalError, BusinessError) as error:
        print(
            tr("操作未完成：", "Operation did not complete: ")
            + (str(error) if isinstance(error, LocalError) else error.code)
        )
        sys.exit(1)
    except Exception:
        # Never emit private database URLs, raw SQL values or credentials into a console traceback.
        print(
            tr(
                "操作未完成，数据仍保留。请检查数据目录和安装包是否完整，再联系支持。",
                "The operation did not complete; data is retained. "
                "Check the data directory and installation bundle, then contact support.",
            )
        )
        sys.exit(1)
