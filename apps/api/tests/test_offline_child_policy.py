import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

from conftest import ROOT


def test_windows_audit_command_line_allows_only_owned_ocr_worker():
    spec = importlib.util.spec_from_file_location(
        "offline_guard", ROOT / "scripts/offline-smoke-server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    command = [
        sys.executable,
        "-m",
        "factoryflow.modules.documents.adapters.ocr_worker",
        str(Path(tempfile.gettempdir()) / "factoryflow-ocr-synthetic"),
        "image/png",
    ]
    assert module.allowed_ocr_process(None, subprocess.list2cmdline(command))
    assert module.allowed_ocr_process(sys.executable, command)
    assert not module.allowed_ocr_process(None, [sys.executable, "-c", "print('synthetic')"])
    assert not module.allowed_ocr_process(None, command + ["extra"])
    assert not module.allowed_ocr_process(None, command[:3] + [str(ROOT), "image/png"])
