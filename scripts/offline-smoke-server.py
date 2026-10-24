"""Test-only Python egress guard; NOT an OS sandbox or a production firewall."""

import ipaddress
import os
import runpy
import shlex
import socket
import sys
import tempfile
from pathlib import Path


def local_address(host: object) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError, TypeError:
        return False


def allowed_ocr_process(executable, command):
    if isinstance(command, str):
        command = [part.strip('"') for part in shlex.split(command, posix=False)]
    return (
        isinstance(command, list)
        and len(command) == 5
        and Path(command[0]).resolve() == Path(sys.executable).resolve()
        and (executable is None or Path(executable).resolve() == Path(sys.executable).resolve())
        and command[1:3] == ["-m", "factoryflow.modules.documents.adapters.ocr_worker"]
        and Path(command[3]).resolve().parent == Path(tempfile.gettempdir()).resolve()
        and Path(command[3]).name.startswith("factoryflow-ocr-")
        and command[4] in {"image/png", "image/jpeg", "application/pdf"}
    )


def windows_version_probe(executable, command):
    """Recognize stdlib platform._syscmd_ver fallbacks; they remain blocked."""
    shell = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/cmd.exe")
    commands = {
        f'{shell} /c "{query}"'.casefold() for query in ("ver", "command /c ver", "cmd /c ver")
    }
    return (
        os.name == "nt"
        and isinstance(executable, str)
        and Path(executable).resolve() == Path(shell).resolve()
        and isinstance(command, str)
        and command.casefold() in commands
    )


def main() -> None:
    probing = True
    denied = 0

    def guard(event, args):
        nonlocal denied
        blocked = False
        if event == "socket.getaddrinfo":
            blocked = not local_address(args[0])
        elif event in {"socket.connect", "socket.sendto"}:
            address = args[-1]
            blocked = not isinstance(address, tuple) or not local_address(address[0])
        elif event == "subprocess.Popen":
            blocked = not allowed_ocr_process(args[0], args[1])
        elif event in {"os.system", "os.posix_spawn", "os.exec"}:
            blocked = True
        if blocked:
            denied += 1
            if not probing:
                if event == "subprocess.Popen" and windows_version_probe(args[0], args[1]):
                    marker = "OFFLINE_BLOCKED_WINDOWS_VERSION_PROBE"
                else:
                    marker = f"OFFLINE_UNEXPECTED_EGRESS:{event}"
                print(marker, flush=True)
            raise PermissionError("Offline smoke denies external network and child processes")

    sys.addaudithook(guard)
    probes = [
        lambda: socket.getaddrinfo("offline-probe.invalid", 443),
        lambda: socket.create_connection(("192.0.2.1", 443), timeout=0.1),
    ]
    for probe in probes:
        try:
            probe()
        except PermissionError:
            continue
        raise RuntimeError("Offline guard did not block a negative control")
    if denied != len(probes):
        raise RuntimeError("Offline guard negative controls were not observed")
    probing = False
    print("OFFLINE_GUARD_READY:2_NEGATIVE_CONTROLS_BLOCKED", flush=True)
    entry = Path(__file__).resolve().with_name("serve-local.py")
    runpy.run_path(str(entry), run_name="__main__")


if __name__ == "__main__":
    main()
