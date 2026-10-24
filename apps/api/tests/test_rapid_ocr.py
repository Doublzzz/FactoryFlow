"""Synthetic adapter contracts; no installed model inference or business material."""

import io
import json
import os
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pytest
from factoryflow.modules.documents.adapters import ocr, ocr_worker
from factoryflow.modules.documents.adapters import rapid_ocr_worker as rapid
from factoryflow.platform.config import Settings
from PIL import Image


def synthetic_output():
    return SimpleNamespace(
        boxes=[[[1, 2], [50, 2], [50, 20], [1, 20]]],
        txts=["Synthetic 1 · 25 PCS"],
        scores=[0.9],
    )


def test_whole_block_text_polygon_and_confidence_preserved():
    result = rapid.blocks(synthetic_output())
    word = result["lines"][0]["words"][0]
    assert word == {
        "text": "Synthetic 1 · 25 PCS",
        "x": 1,
        "y": 2,
        "width": 49,
        "height": 18,
        "polygon": [[1, 2], [50, 2], [50, 20], [1, 20]],
        "confidence": 0.9,
    }
    assert result["text"] == word["text"]
    assert rapid.blocks(SimpleNamespace(boxes=None, txts=None, scores=None))["lines"] == []


@pytest.mark.parametrize(
    "change",
    [
        {"scores": []},
        {"txts": ["x" * 10001]},
        {"boxes": [[[float("nan"), 2]] * 4]},
        {"boxes": [[[1, 2]] * 4]},
        {"scores": [2]},
    ],
)
def test_bad_output_rejected(change):
    output = synthetic_output()
    output.__dict__.update(change)
    with pytest.raises(ValueError, match="OCR_RESULT_INVALID"):
        rapid.blocks(output)


def test_config_defaults_and_explicit_engine(tmp_path):
    config = tmp_path / "app.json"
    config.write_text(json.dumps({"database_url": "synthetic", "object_root": "synthetic"}))
    assert Settings.load(config).ocr_engine == "windows"
    assert ocr.LocalExtractor().engine == "windows"
    settings = Settings("synthetic", tmp_path, ocr_engine="rapid", ocr_python=Path(sys.executable))
    assert ocr.LocalExtractor(settings.ocr_engine, settings.ocr_python).engine == "rapid"


@pytest.mark.parametrize(
    "engine,python,code",
    [
        ("other", None, "OCR_ENGINE_UNSUPPORTED"),
        ("rapid", None, "OCR_INTERPRETER_UNAVAILABLE"),
        ("rapid", Path("missing-synthetic.exe"), "OCR_INTERPRETER_UNAVAILABLE"),
        ("windows", Path(sys.executable), "OCR_CONFIGURATION_INVALID"),
    ],
)
def test_invalid_config(engine, python, code, tmp_path):
    with pytest.raises(ValueError, match=code):
        ocr.LocalExtractor(engine, python)
    with pytest.raises(ValueError, match=code):
        Settings("synthetic", tmp_path, ocr_engine=engine, ocr_python=python)


def test_interpreter_removed_after_startup(tmp_path):
    python = tmp_path / "synthetic-python.exe"
    python.write_bytes(b"synthetic")
    extractor = ocr.LocalExtractor("rapid", python)
    python.unlink()
    assert (
        extractor.extract(b"synthetic", "image/png")["error_code"] == "OCR_INTERPRETER_UNAVAILABLE"
    )


def test_existing_relative_interpreter_rejected(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    relative = Path("synthetic-python.exe")
    relative.write_bytes(b"synthetic")
    assert relative.is_file()
    with pytest.raises(ValueError, match="OCR_INTERPRETER_UNAVAILABLE"):
        ocr.LocalExtractor("rapid", relative)
    with pytest.raises(ValueError, match="OCR_INTERPRETER_UNAVAILABLE"):
        Settings("synthetic", tmp_path, ocr_engine="rapid", ocr_python=relative)
    config = tmp_path / "app.json"
    config.write_text(
        json.dumps(
            {
                "database_url": "synthetic",
                "object_root": "synthetic",
                "ocr_engine": "rapid",
                "ocr_python": str(relative),
            }
        )
    )
    with pytest.raises(ValueError, match="OCR_INTERPRETER_UNAVAILABLE"):
        Settings.load(config)


def test_asset_versions_hashes_and_missing_models(monkeypatch, tmp_path):
    monkeypatch.setattr(
        rapid.importlib.metadata, "distribution", lambda name: SimpleNamespace(version="wrong")
    )
    with pytest.raises(ValueError, match="OCR_VERSION_MISMATCH"):
        rapid.verify_assets()
    monkeypatch.setattr(
        rapid.importlib.metadata,
        "distribution",
        lambda name: SimpleNamespace(
            version="3.9.2" if name == "rapidocr" else "1.30.0",
            locate_file=lambda filename: tmp_path / Path(filename).name,
        ),
    )
    with pytest.raises(ValueError, match="OCR_MODEL_MISMATCH"):
        rapid.verify_assets()
    for name, _digest in rapid.MODELS.values():
        (tmp_path / name).write_bytes(b"synthetic")
    with pytest.raises(ValueError, match="OCR_MODEL_MISMATCH"):
        rapid.verify_assets()


def test_rapid_render_grid_trace_without_windows_supplements(monkeypatch, tmp_path):
    content = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(content, format="PNG")
    (tmp_path / "source").write_bytes(content.getvalue())
    metadata = {"runtime": "synthetic", "model_sha256": {"det": "synthetic"}}
    monkeypatch.setattr(
        ocr_worker,
        "recognize_rapid",
        lambda *args: rapid.blocks(synthetic_output()) | {"engine_metadata": metadata},
    )
    monkeypatch.setattr(ocr_worker, "recognize", lambda *args: pytest.fail("Windows OCR called"))
    monkeypatch.setattr(
        ocr_worker, "recover_headers", lambda *args: pytest.fail("header OCR called")
    )
    result = ocr_worker.run(tmp_path, "image/png", "rapid", sys.executable)
    assert result["status"] == "ready"
    assert result["engine"] == "rapidocr" and result["engine_version"] == "3.9.2"
    assert result["engine_metadata"] == metadata
    page = result["pages"][0]
    assert page["preview_base64"] and page["table_grids"] == [] and page["header_ocr"] == []
    assert page["rows"] == ["Synthetic 1 · 25 PCS"]


@pytest.mark.parametrize(
    "value,code",
    [
        ({"text": "", "lines": []}, None),
        ({"text": "", "lines": [], "error_code": "OCR_MODEL_MISMATCH"}, "OCR_MODEL_MISMATCH"),
        ({"text": "secret", "lines": "bad"}, "OCR_RESULT_INVALID"),
        ({"text": "", "lines": [], "error_code": "private/path"}, "OCR_RESULT_INVALID"),
    ],
)
def test_page_ipc_validation(monkeypatch, tmp_path, value, code):
    def stub(command, **kwargs):
        Path(command[-1]).write_text(json.dumps(value))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(ocr_worker.subprocess, "run", stub)
    result = ocr_worker.recognize_rapid(
        Image.new("RGB", (100, 100)), tmp_path, 0, sys.executable, time.monotonic() + 5
    )
    assert result.get("error_code") == code


def test_page_timeout_is_static(monkeypatch, tmp_path):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("private-synthetic", 1)

    monkeypatch.setattr(ocr_worker.subprocess, "run", timeout)
    result = ocr_worker.recognize_rapid(
        Image.new("RGB", (100, 100)), tmp_path, 0, sys.executable, time.monotonic() + 5
    )
    assert result["error_code"] == "OCR_TIMEOUT" and result["text"] == ""


def test_network_and_child_audit_negative_controls():
    for event in ("socket.getaddrinfo", "socket.connect", "socket.sendto", "subprocess.Popen"):
        with pytest.raises(PermissionError, match="OCR_OFFLINE_POLICY"):
            rapid.deny_network(event, ())


def test_installed_audit_in_isolated_child_denies_network_and_process(tmp_path):
    allowed = tmp_path / "synthetic.txt"
    allowed.write_text("synthetic local read", encoding="utf-8")
    script = f"""
import runpy, socket, subprocess, sys
from pathlib import Path
policy = runpy.run_path({str(Path(rapid.__file__).resolve())!r})["deny_network"]
sys.addaudithook(policy)
assert Path({str(allowed)!r}).read_text(encoding="utf-8") == "synthetic local read"
for operation in (
    lambda: socket.getaddrinfo("synthetic.invalid", 443),
    lambda: subprocess.Popen([sys.executable, "-c", "raise SystemExit(99)"]),
):
    try:
        operation()
    except PermissionError as error:
        assert str(error) == "OCR_OFFLINE_POLICY"
    else:
        raise AssertionError("audit failed to deny")
print("LOCAL_READ_OK;NETWORK_DENIED;CHILD_DENIED")
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        capture_output=True,
        text=True,
        timeout=5,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "LOCAL_READ_OK;NETWORK_DENIED;CHILD_DENIED"
    assert result.stderr == ""


def test_verified_models_explicit_cpu_enum_contract_and_trace_metadata(monkeypatch, tmp_path):
    paths = {kind: tmp_path / name for kind, (name, _) in rapid.MODELS.items()}
    monkeypatch.setattr(rapid, "verify_assets", lambda: paths)
    session = SimpleNamespace(
        session=SimpleNamespace(get_providers=lambda: ["CPUExecutionProvider"])
    )

    class EngineType(Enum):
        ONNXRUNTIME = "onnxruntime"

    def require_engine_enum(value):
        # Pinned ParseParams.update_batch rejects string enum parameters.
        if not isinstance(value, Enum):
            raise TypeError("The value of Det.engine_type must be Enum Type.")
        assert value is EngineType.ONNXRUNTIME

    with pytest.raises(TypeError, match="must be Enum Type"):
        require_engine_enum("onnxruntime")

    class SyntheticEngine:
        def __init__(self, params):
            for kind, path in paths.items():
                assert params[f"{kind.title()}.model_path"] == str(path)
                require_engine_enum(params[f"{kind.title()}.engine_type"])
            for provider in ("cuda", "dml", "cann", "coreml"):
                assert params[f"EngineConfig.onnxruntime.use_{provider}"] is False
            self.text_det = self.text_cls = self.text_rec = SimpleNamespace(session=session)

        def __call__(self, page, **kwargs):
            assert kwargs == {"return_word_box": True, "return_single_char_box": False}
            return synthetic_output()

    monkeypatch.setitem(sys.modules, "rapidocr", SimpleNamespace(RapidOCR=SyntheticEngine))
    monkeypatch.setitem(
        sys.modules, "rapidocr.utils.typings", SimpleNamespace(EngineType=EngineType)
    )
    result = rapid.run(tmp_path / "synthetic.png")
    assert result["engine_metadata"]["runtime_version"] == "1.30.0"
    assert result["engine_metadata"]["model_sha256"] == {
        kind: pair[1] for kind, pair in rapid.MODELS.items()
    }


@pytest.mark.parametrize(
    "raw",
    [b"not-json", b"[]", b'{"status":"ready","pages":"bad"}', b"x" * (40 * 1024 * 1024 + 1)],
    ids=["not-json", "not-dict", "bad-pages", "oversized"],
)
def test_outer_result_shape_and_size(monkeypatch, tmp_path, raw):
    def stub(command, timeout):
        (Path(command[3]) / "result.json").write_bytes(raw)
        return 0

    monkeypatch.setattr(ocr, "run_owned", stub)
    assert ocr.LocalExtractor("rapid", Path(sys.executable)).extract(b"synthetic", "image/png") == {
        "status": "failed",
        "error_code": "EXTRACTION_FAILED",
        "pages": [],
    }


def test_subword_results_align_exactly_and_keep_original_block():
    output = synthetic_output()
    baseline = rapid.blocks(output)
    output.word_results = [
        [
            (token, 0.8, [[x, 3], [x + 4, 3], [x + 4, 19], [x, 19]])
            for token, x in [("Synthetic", 2), ("1", 10), ("·", 18), ("25", 26), ("PCS", 34)]
        ]
    ]
    observed = rapid.blocks(output)
    word = observed["lines"][0]["words"][0]
    assert word["subwords"][1]["start"] == 10
    assert word["subwords"][2]["text"] == "·"
    parts = word.pop("subwords")
    assert observed == baseline
    assert rapid.valid_subwords(word, parts)


@pytest.mark.parametrize(
    "tokens",
    [
        [
            ("Synthetic", 0.8, [[2, 3], [6, 3], [6, 19], [2, 19]]),
            ("wrong", 0.8, [[10, 3], [14, 3], [14, 19], [10, 19]]),
        ],
        [("Synthetic", 0.8, [[float("nan"), 3]] * 4)],
        [("Synthetic", 0.8, [[0, 3], [60, 3], [60, 19], [0, 19]])],
        [("Synthetic", 0.8, None)],
        [("Synthetic", 0.8, [{"x": 2, "y": 3}] * 4)],
    ],
)
def test_bad_optional_tokens_preserve_whole_block(tokens):
    output = synthetic_output()
    expected = rapid.blocks(output)
    output.word_results = [tokens]
    assert rapid.blocks(output) == expected


def test_optional_token_count_is_bounded():
    output = synthetic_output()
    expected = rapid.blocks(output)
    output.word_results = [[("S", 0.9, [[2, 3], [6, 3], [6, 19], [2, 19]])] * 513]
    assert rapid.blocks(output) == expected


def test_ipc_discards_invalid_optional_evidence_only(monkeypatch, tmp_path):
    data = rapid.blocks(synthetic_output())
    data["lines"][0]["words"][0]["subwords"] = [{"start": 0, "end": 999, "text": "bad"}]

    def stub(command, **kwargs):
        Path(command[-1]).write_text(json.dumps(data))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(ocr_worker.subprocess, "run", stub)
    result = ocr_worker.recognize_rapid(
        Image.new("RGB", (100, 100)), tmp_path, 0, sys.executable, time.monotonic() + 5
    )
    assert result == rapid.blocks(synthetic_output())


@pytest.mark.skipif(os.name != "nt", reason="Windows job lifecycle")
def test_outer_timeout_kills_nested_child(tmp_path):
    pid_path = tmp_path / "child.pid"
    child = "import time; time.sleep(60)"
    parent = (
        "import subprocess,sys,time,pathlib; "
        f"p=subprocess.Popen([sys.executable,'-c',{child!r}]); "
        f"pathlib.Path({str(pid_path)!r}).write_text(str(p.pid)); time.sleep(60)"
    )
    with pytest.raises(subprocess.TimeoutExpired):
        ocr.run_owned([sys.executable, "-c", parent], 1)
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32")
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, int(pid_path.read_text()))
    if handle:
        try:
            exit_code = wintypes.DWORD()
            assert kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            assert exit_code.value != 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
