"""Bounded local worker. No cloud calls, process creation or imports of engines at import."""

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from threading import BoundedSemaphore

from factoryflow.kernel.contracts import BusinessError

MAX_BYTES = 10 * 1024 * 1024
_capacity = BoundedSemaphore(1)


def run_owned(command, timeout):
    """Own the complete process tree; kill descendants even when decode hangs."""
    job = None
    process = None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [
                ("per_process", ctypes.c_int64),
                ("per_job", ctypes.c_int64),
                ("flags", wintypes.DWORD),
                ("min_ws", ctypes.c_size_t),
                ("max_ws", ctypes.c_size_t),
                ("active", wintypes.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class Extended(ctypes.Structure):
            _fields_ = [
                ("basic", Basic),
                ("io", ctypes.c_uint64 * 6),
                ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t),
                ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        job = kernel.CreateJobObjectW(None, None)
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not job or not kernel.SetInformationJobObject(
            job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            if job:
                kernel.CloseHandle(job)
            raise OSError("OCR_PROCESS_UNAVAILABLE")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(subprocess.CREATE_NO_WINDOW | 4) if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
        if job:
            if not kernel.AssignProcessToJobObject(job, int(process._handle)):
                raise OSError("OCR_PROCESS_UNAVAILABLE")
            native = ctypes.WinDLL("ntdll")
            native.NtResumeProcess.argtypes = [wintypes.HANDLE]
            if native.NtResumeProcess(int(process._handle)) != 0:
                raise OSError("OCR_PROCESS_UNAVAILABLE")
        return process.wait(timeout=timeout)
    finally:
        if job:
            kernel.CloseHandle(job)
        elif process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()


class LocalExtractor:
    def __init__(self, engine="windows", python: Path | None = None):
        if not isinstance(engine, str) or engine not in {"windows", "rapid"}:
            raise ValueError("OCR_ENGINE_UNSUPPORTED")
        if engine == "windows" and python is not None:
            raise ValueError("OCR_CONFIGURATION_INVALID")
        if engine == "rapid" and (
            not isinstance(python, Path) or not python.is_absolute() or not python.is_file()
        ):
            raise ValueError("OCR_INTERPRETER_UNAVAILABLE")
        self.engine, self.python = engine, python

    def extract(self, content: bytes, media_type: str) -> dict:
        if not _capacity.acquire(blocking=False):
            raise BusinessError("EXTRACTION_BUSY", 409)
        try:
            with tempfile.TemporaryDirectory(prefix="factoryflow-ocr-") as directory:
                root = Path(directory)
                (root / "source").write_bytes(content)
                if self.engine == "rapid":
                    if not self.python.is_file():
                        return {
                            "status": "failed",
                            "error_code": "OCR_INTERPRETER_UNAVAILABLE",
                            "pages": [],
                        }
                    (root / "engine.json").write_text(
                        json.dumps({"engine": "rapid", "python": str(self.python)}),
                        encoding="utf-8",
                    )
                try:
                    command = [
                        sys.executable,
                        "-m",
                        "factoryflow.modules.documents.adapters.ocr_worker",
                        str(root),
                        media_type,
                    ]
                    returncode = run_owned(command, 90)
                except subprocess.TimeoutExpired:
                    return {"status": "failed", "error_code": "EXTRACTION_TIMEOUT", "pages": []}
                except OSError:
                    return {"status": "failed", "error_code": "EXTRACTION_FAILED", "pages": []}
                path = root / "result.json"
                if returncode or not path.is_file() or path.stat().st_size > 40 * 1024 * 1024:
                    return {"status": "failed", "error_code": "EXTRACTION_FAILED", "pages": []}
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if (
                        not isinstance(data, dict)
                        or data.get("status") not in {"ready", "failed"}
                        or not isinstance(data.get("pages"), list)
                        or len(data["pages"]) > 5
                    ):
                        raise ValueError("invalid result")
                    return data
                except ValueError, OSError:
                    return {"status": "failed", "error_code": "EXTRACTION_FAILED", "pages": []}
        finally:
            _capacity.release()
