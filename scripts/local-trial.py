"""Manage an explicitly synthetic, persistent local trial; never a business deployment."""

import argparse
import ctypes
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import httpx
import psycopg
from factoryflow.bootstrap import build_services, create_app
from factoryflow.modules.fulfillment.domain.print_layout import default_layout
from factoryflow.platform.backup import restore_backup, validate_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import REVISION, engine_for
from factoryflow.platform.migrations import upgrade_database
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url

PROJECT = Path(__file__).resolve().parents[1]
BASE = PROJECT / ".runtime/local-trial"
SCRIPT = Path(__file__).resolve()
BIN = PROJECT / ".tools/postgresql-18.6-4/pgsql/bin"
WEB = PROJECT / "apps/web/dist"
KIND = "factoryflow-local-trial-v1"
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


class TrialError(ValueError):
    """A deliberately credential-free operator message."""


def direct(path):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise TrialError("Trial paths must not contain symbolic links or junctions")
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
            raise TrialError(
                "Another trial maintenance operation is running; retry later"
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


def owned(path):
    direct(BASE)
    root = direct(path)
    if root.parent != (BASE / "environments").resolve() or not re.fullmatch(
        "[a-f0-9]{32}", root.name
    ):
        raise TrialError("Not an owned local-trial environment")
    for name in (
        "owner.json",
        "private-state.json",
        "app.json",
        "pgdata",
        "objects",
        "client.json",
        "sample.json",
        "server-process.json",
        "postgres.log",
        "server.log",
    ):
        direct(root / name)
    expected = {"kind": KIND, "id": root.name, "synthetic_only": True}
    if read(root / "owner.json") != expected:
        raise TrialError("Trial ownership marker mismatch")
    return root


def active():
    path = direct(BASE / "active.json")
    if not path.is_file():
        raise TrialError("No prepared trial. Run prepare explicitly first.")
    return owned(BASE / "environments" / read(path)["id"])


def environment(root):
    root = owned(root)
    state = read(root / "private-state.json")
    settings = Settings.load(root / "app.json")
    url = make_url(settings.database_url)
    admin = make_url(state["admin_url"])
    if (
        url.host != "127.0.0.1"
        or url.username != "ff_runtime"
        or url.database != "factoryflow_trial"
        or url.query
        or url.port != state["port"]
        or url.port == 55433
        or not isinstance(url.port, int)
        or not 1024 <= url.port <= 65535
        or admin.host != "127.0.0.1"
        or admin.database != "postgres"
        or admin.username != "ff_admin"
        or admin.port != url.port
        or admin.query
        or settings.object_root.resolve() != (root / "objects").resolve()
        or (
            settings.archive_root is not None
            and settings.archive_root.resolve() != (root / "archives").resolve()
        )
        or settings.ocr_engine != "windows"
        or settings.ocr_python is not None
        or state["api_port"] in {8100, 8101, 8110, 61290}
        or not 1024 <= state["api_port"] <= 65535
    ):
        raise TrialError("Trial configuration does not match its isolated environment")
    return settings, state


def available(port):
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError as failure:
            raise TrialError(f"Port {port} is occupied; nothing was stopped") from failure


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
        raise TrialError(f"PostgreSQL {name} failed; inspect the owned private postgres.log")
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
            raise TrialError("Database process belongs to another data directory")


def _process_handle(pid, access):
    if os.name != "nt":
        raise TrialError("This prepared local trial requires Windows")
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
        raise TrialError("Cannot verify process creation identity")
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
        "local-trial.py" in command
        and re.search(r"\bserve\s", command)
        and re.search(r'--root\s+"?' + re.escape(root) + r'"?(?:\s|$)', command)
    )


def stop_api(root):
    path = root / "server-process.json"
    if not path.is_file():
        return
    record = read(path)
    if record.get("root") != str(root):
        raise TrialError("Server record belongs to another environment")
    running = process(record["pid"])
    if not running:
        return
    if not matches_process(record, running):
        raise TrialError("PID was reused or ownership changed; process left untouched")
    kernel, handle = _process_handle(record["pid"], 0x1001)
    if not handle:
        return
    try:
        if _creation(kernel, handle) != record["created"]:
            raise TrialError("Process changed during stop; left untouched")
        if not kernel.TerminateProcess(handle, 0):
            raise TrialError("Owned API could not be stopped")
    finally:
        kernel.CloseHandle(handle)
    for _ in range(30):
        try:
            available(read(root / "private-state.json")["api_port"])
            return
        except ValueError:
            time.sleep(0.1)
    raise TrialError("API port did not close; database left running")


def stop(root):
    _, state = environment(root)
    stop_api(root)
    available(state["api_port"])
    if pg("pg_ctl", "-D", root / "pgdata", "status", check=False) == 0:
        database_identity(root)
        pg("pg_ctl", "-D", root / "pgdata", "-m", "fast", "-w", "stop")
    available(state["port"])
    return {"state": "stopped", "environment": root.name, "data_retained": True}


def fingerprint():
    digest = hashlib.sha256()
    paths = [SCRIPT, PROJECT / "pyproject.toml"]
    for directory in (PROJECT / "apps/api/src", WEB):
        paths += [p for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    for path in sorted(paths):
        digest.update(str(path.relative_to(PROJECT)).replace("\\", "/").encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def status(root):
    settings, state = environment(root)
    record = (
        read(root / "server-process.json") if (root / "server-process.json").is_file() else None
    )
    running = process(record["pid"]) if record else None
    api_owned = bool(
        record and record.get("root") == str(root) and matches_process(record, running)
    )
    db_running = pg("pg_ctl", "-D", root / "pgdata", "status", check=False) == 0
    report = {
        "environment": root.name,
        "synthetic_only": True,
        "url": f"http://127.0.0.1:{state['api_port']}/",
        "database_running": db_running,
        "api_owned": api_owned,
        "expected_schema": REVISION,
        "schema": None,
        "ready": False,
        "source_build_sha256": fingerprint(),
        "running_sha256": record.get("build_sha256") if api_owned else None,
    }
    if db_running:
        database_identity(root)
        engine = engine_for(settings.database_url)
        try:
            with engine.connect() as conn:
                report["schema"] = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
        finally:
            engine.dispose()
    if api_owned:
        with httpx.Client(trust_env=False, timeout=2) as client:
            try:
                report["ready"] = (
                    client.get(report["url"] + "api/v1/health/ready").status_code == 200
                )
            except httpx.HTTPError:
                pass
    report["restart_required"] = bool(
        api_owned and report["running_sha256"] != report["source_build_sha256"]
    )
    return report


def start(root):
    if not (WEB / "index.html").is_file():
        raise TrialError("Prepared web build required; startup does not build or install")
    _, state = environment(root)
    before = status(root)
    if before["ready"]:
        return before
    if before["api_owned"]:
        raise TrialError("Owned API is unhealthy. Inspect status/logs and stop explicitly.")
    available(state["api_port"])
    database_start(root)
    runtime = build_services(environment(root)[0])
    try:
        runtime.check_ready()  # Reject an old schema. Startup never migrates.
    finally:
        runtime.close()
    with (root / "server.log").open("ab") as log:
        subprocess.Popen(
            [sys.executable, str(SCRIPT), "serve", "--root", str(root)],
            cwd=PROJECT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            creationflags=FLAGS,
        )
    with httpx.Client(trust_env=False, timeout=1) as client:
        for _ in range(60):
            try:
                if client.get(before["url"] + "api/v1/health/ready").status_code == 200:
                    result = status(root)
                    if result["api_owned"]:
                        return result
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
    raise TrialError("Trial startup failed; inspect owned server.log. Existing data retained.")


def serve(root):
    import uvicorn

    settings, state = environment(root)
    application = create_app(settings=settings, web_directory=WEB)
    application.state.services.check_ready()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", state["api_port"]))
        listener.listen(128)
        running = process(os.getpid())
        save(
            root / "server-process.json",
            running | {"root": str(root), "build_sha256": fingerprint()},
        )
        config = uvicorn.Config(
            application, host="127.0.0.1", port=state["api_port"], access_log=False
        )
        uvicorn.Server(config).run(sockets=[listener])


def new_cluster(api_port):
    available(api_port)
    root = BASE / "environments" / uuid4().hex
    root.mkdir(parents=True)
    save(root / "owner.json", {"kind": KIND, "id": root.name, "synthetic_only": True})
    port = free_port()
    while port in {55433, api_port}:
        port = free_port()
    admin_password, runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    admin_url = f"postgresql://ff_admin:{admin_password}@127.0.0.1:{port}/postgres"
    state = {
        "admin_url": admin_url,
        "runtime_password": runtime_password,
        "port": port,
        "api_port": api_port,
    }
    save(root / "private-state.json", state)
    save(
        root / "app.json",
        {
            "database_url": f"postgresql+psycopg://ff_runtime:{runtime_password}@127.0.0.1:{port}/factoryflow_trial",
            "object_root": str(root / "objects"),
            "archive_root": str(root / "archives"),
            "secure_cookies": False,
        },
    )
    try:
        password = root / "init-password.tmp"
        password.write_text(admin_password, encoding="utf-8")
        try:
            pg(
                "initdb",
                "-D",
                root / "pgdata",
                "-U",
                "ff_admin",
                "--pwfile",
                password,
                "--auth=scram-sha-256",
                "--encoding=UTF8",
                "--locale=C",
            )
        finally:
            password.unlink(missing_ok=True)
        with (root / "pgdata/postgresql.conf").open("a") as stream:
            stream.write(
                f"\nlisten_addresses='127.0.0.1'\nport={port}\nlog_statement='none'\nlog_min_error_statement='panic'\n"
            )
        database_start(root)
        with psycopg.connect(admin_url, autocommit=True) as conn:
            conn.execute(
                sql.SQL("CREATE ROLE ff_runtime LOGIN PASSWORD {}").format(
                    sql.Literal(runtime_password)
                )
            )
    except Exception:
        abandon_new(root)
        raise TrialError(
            f"Preparation failed; retained environment {root.name} is stopped"
        ) from None
    return root


def abandon_new(root):
    """Stop only this freshly created, verified cluster; preserve all files."""
    try:
        if pg("pg_ctl", "-D", root / "pgdata", "status", check=False) == 0:
            database_identity(root)
            pg("pg_ctl", "-D", root / "pgdata", "-m", "fast", "-w", "stop")
    except Exception:
        raise TrialError(
            f"New environment {root.name} could not be stopped safely; files retained"
        ) from None


def seed(root, runtime):
    login = {"username": "trial-admin", "password": secrets.token_hex(24)}
    save(root / "client.json", login)
    actor = runtime.identity.provision_factory("合成试用工厂", login["username"], login["password"])

    def key(label):
        return uuid5(UUID(root.name), label)

    customer = runtime.customers.create(actor, key("customer"), "合成客户 · 本机试用")
    order = runtime.orders.confirm(
        actor,
        key("order"),
        {
            "customer_id": customer["id"],
            "order_number": "SYN-TRIAL-001",
            "business_date": "2026-10-12",
            "currency": "CNY",
            "lines": [
                {
                    "description": "合成铝型材 / 80 × 40 mm",
                    "item_code": "SYN-AL-01",
                    "item_name": "合成铝型材",
                    "specification": "80 × 40 mm",
                    "quantity": "125.5",
                    "unit": "KG",
                    "source_unit_price": "1.2500",
                    "source_amount": None,
                },
                {
                    "description": "合成安装件 / 本色",
                    "item_code": "SYN-PT-02",
                    "item_name": "合成安装件",
                    "specification": "本色",
                    "quantity": "240",
                    "unit": "PCS",
                    "source_unit_price": "0.8000",
                    "source_amount": None,
                },
            ],
        },
    )
    detail = runtime.orders.detail(actor, UUID(order["order_id"]))
    delivery = runtime.deliveries.create(
        actor,
        key("delivery"),
        {
            "order_id": detail["id"],
            "customer_id": customer["id"],
            "revision_id": detail["revision_id"],
            "expected_version": detail["version"],
            "delivery_date": "2026-10-12",
            "lines": [
                {"order_line_id": line["id"], "quantity": quantity}
                for line, quantity in zip(detail["lines"], ["25.5", "80"], strict=True)
            ],
        },
    )
    statement = runtime.statements.create(
        actor,
        key("statement"),
        {
            "customer_id": customer["id"],
            "period_start": "2026-10-01",
            "period_end": "2026-10-31",
            "tax_mode": "untaxed_final",
            "tax_rate": "0",
            "adjustments": [],
            "lines": [
                {
                    "delivery_id": delivery["id"],
                    "order_line_id": line["id"],
                    "quantity": quantity,
                    "unit_price": price,
                    "reason": "合成演示",
                }
                for line, quantity, price in zip(
                    detail["lines"], ["25.5", "80"], ["1.25", "0.8"], strict=True
                )
            ],
        },
    )
    export = runtime.statement_exports.create(actor, key("export"), statement["id"], 1)
    runtime.statement_exports.generate(actor, export["id"])
    layout = runtime.delivery_layouts.save(
        actor, key("layout"), 0, default_layout() | {"company_name": "合成示例 · 本机试用工厂"}
    )
    save(
        root / "sample.json",
        {
            "synthetic_only": True,
            "customer_id": customer["id"],
            "order_id": detail["id"],
            "delivery_id": delivery["id"],
            "statement_id": statement["id"],
            "export_id": export["id"],
            "layout_version": layout["version"],
        },
    )


def prepare(api_port):
    if (BASE / "active.json").exists():
        raise TrialError("A trial already exists. Use start; prepare never replaces it.")
    if api_port in {8100, 8101, 8110, 61290} or not 1024 <= api_port <= 65535:
        raise TrialError("Choose a separate trial API port")
    root = new_cluster(api_port)
    try:
        _, state = environment(root)
        with psycopg.connect(state["admin_url"], autocommit=True) as conn:
            conn.execute("CREATE DATABASE factoryflow_trial OWNER ff_admin")
        owner_url = make_url(state["admin_url"]).set(
            drivername="postgresql+psycopg", database="factoryflow_trial"
        )
        owner = engine_for(owner_url.render_as_string(hide_password=False))
        try:
            upgrade_database(owner, PROJECT)  # Only explicit new synthetic preparation.
        finally:
            owner.dispose()
        (root / "objects").mkdir()
        runtime = build_services(environment(root)[0])
        try:
            seed(root, runtime)
        finally:
            runtime.close()
        save(BASE / "active.json", {"id": root.name})
    except Exception:
        abandon_new(root)
        raise TrialError(
            f"Preparation failed; retained environment {root.name} is stopped"
        ) from None
    return {"state": "prepared", "environment": root.name, "login_file": str(root / "client.json")}


def backup_path(path):
    direct(BASE)
    path = direct(path)
    if path.parent != (BASE / "backups").resolve() or not re.fullmatch("[a-f0-9]{32}", path.name):
        raise TrialError("Only a backup created by this trial manager is accepted")
    for name in (
        "trial.json",
        "trial.sha256",
        "data",
        "data/manifest.json",
        "data/objects",
        "data/database.dump",
    ):
        direct(path / name)
    if not (path / "trial.json").is_file() or read(path / "trial.json").get("kind") != KIND:
        raise TrialError("Trial backup ownership record missing")
    manifest = validate_backup(path / "data")
    try:
        metadata = read(path / "trial.json")
        expected = (path / "trial.sha256").read_text(encoding="ascii").strip()
        if hashlib.sha256((path / "trial.json").read_bytes()).hexdigest() != expected:
            raise ValueError
        if metadata["schema"] != manifest["schema_revision"]:
            raise ValueError
        if not re.fullmatch("[a-f0-9]{32}", metadata["environment"]):
            raise ValueError
        login = metadata["login"]
        if set(login) != {"username", "password"} or any(
            not isinstance(login[key], str) or not login[key] for key in login
        ):
            raise ValueError
        sample = metadata["sample"]
        if sample["synthetic_only"] is not True or not isinstance(sample["layout_version"], int):
            raise ValueError
        for key in ("customer_id", "order_id", "delivery_id", "statement_id", "export_id"):
            UUID(sample[key])
    except OSError, KeyError, TypeError, ValueError, AttributeError:
        raise TrialError("Trial backup metadata integrity validation failed") from None
    return path


def backup(root):
    runtime = build_services(environment(root)[0])
    database_identity(root)
    target = direct(BASE / "backups" / uuid4().hex)
    try:
        manifest = runtime.backup(target / "data", BIN)
    finally:
        runtime.close()
    # Keep login and synthetic scenario identity with the private local backup.
    save(
        target / "trial.json",
        {
            "kind": KIND,
            "environment": root.name,
            "schema": manifest["schema_revision"],
            "login": read(root / "client.json"),
            "sample": read(root / "sample.json"),
        },
    )
    (target / "trial.sha256").write_text(
        hashlib.sha256((target / "trial.json").read_bytes()).hexdigest() + "\n", encoding="ascii"
    )
    backup_path(target)
    save(BASE / "latest-backup.json", {"id": target.name})
    return {
        "backup": str(target),
        "verified": True,
        "schema": manifest["schema_revision"],
        "objects": len(manifest["objects"]),
    }


def restore(path, activate=False):
    path = backup_path(path)  # Validate before any environment changes.
    source = read(path / "trial.json")
    old = active()
    _, old_state = environment(old)
    # A temporary distinct API port allows restoration while the old environment is still running.
    root = new_cluster(free_port())
    try:
        _, state = environment(root)
        restore_backup(
            state["admin_url"], "factoryflow_trial", root / "objects", path / "data", BIN, PROJECT
        )
        save(root / "client.json", source["login"])
        save(root / "sample.json", source["sample"])
        runtime = build_services(environment(root)[0])
        try:
            runtime.check_ready()
            actor = runtime.identity.login(**source["login"])["actor"]
            runtime.orders.detail(actor, UUID(source["sample"]["order_id"]))
            runtime.statement_exports.download(
                actor, source["sample"]["export_id"], historical=True
            )
        finally:
            runtime.close()
    except Exception:
        raise TrialError(f"Restore failed; retained environment {root.name}") from None
    finally:
        abandon_new(root)
    if activate:
        stop(old)
        state["api_port"] = old_state["api_port"]
        save(root / "private-state.json", state)
        save(BASE / "active.json", {"id": root.name})
    return {
        "state": "restored",
        "environment": root.name,
        "activated": activate,
        "database_running": False,
        "previous_environment": old.name,
        "old_data_retained": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["prepare", "start", "stop", "status", "backup", "restore", "serve"]
    )
    parser.add_argument("--port", type=int, default=8120)
    parser.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    if args.action == "serve":
        if args.root is None:
            parser.error("Internal server requires its owned environment")
        serve(owned(args.root))
        return
    if args.root is not None:
        parser.error("Environment paths cannot be overridden")
    with maintenance_lock():
        if args.action == "prepare":
            result = prepare(args.port)
        elif args.action == "restore":
            path = args.backup or BASE / "backups" / read(BASE / "latest-backup.json")["id"]
            result = restore(path, args.activate)
        else:
            result = {"start": start, "stop": stop, "status": status, "backup": backup}[
                args.action
            ](active())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.action == "start" and args.open_browser and result["ready"]:
        import webbrowser

        webbrowser.open(result["url"])


if __name__ == "__main__":
    try:
        main()
    except Exception as failure:
        # Never render DB URLs, HTTP payloads, or provider exceptions into the console.
        safe = str(failure) if isinstance(failure, TrialError) else type(failure).__name__
        print(
            f"Local trial operation failed: {safe}. Existing environments retained.",
            file=sys.stderr,
        )
        sys.exit(1)
