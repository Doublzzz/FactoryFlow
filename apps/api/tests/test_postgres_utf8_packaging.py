"""The Unicode runtime transformation only changes manifests in a new copy."""

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load():
    path = ROOT / "scripts/prepare-postgres-utf8.py"
    assert path.is_file(), "Unicode runtime preparation must be implemented"
    spec = importlib.util.spec_from_file_location("postgres_utf8_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_target_is_never_modified(tmp_path):
    module = load()
    target = tmp_path / "existing"
    target.mkdir()
    (target / "retained.txt").write_text("synthetic existing bytes")
    with pytest.raises(FileExistsError):
        module.prepare(tmp_path / "missing-source", target)
    assert (target / "retained.txt").read_text() == "synthetic existing bytes"


def test_invalid_native_input_fails_before_copy(tmp_path):
    module = load()
    source = tmp_path / "source"
    (source / "bin").mkdir(parents=True)
    for name in module.REQUIRED_EXES:
        (source / "bin" / name).write_bytes(b"not an executable")
    for name in ("lib", "share"):
        (source / name).mkdir()
    with pytest.raises(ValueError):
        module.prepare(source, tmp_path / "candidate")
    assert not (tmp_path / "candidate").exists()


@pytest.mark.skipif(
    os.name != "nt" or not os.environ.get("FACTORYFLOW_NATIVE_PG_TEST_ROOT"),
    reason="explicit native PostgreSQL build input required",
)
def test_real_runtime_manifest_transform_preserves_code_and_original(tmp_path):
    module = load()
    source = Path(os.environ["FACTORYFLOW_NATIVE_PG_TEST_ROOT"])
    original = {
        p.relative_to(source).as_posix(): module.digest(p) for p in source.rglob("*") if p.is_file()
    }
    target = tmp_path / "中文 程序"
    receipt = module.prepare(source, target)
    assert receipt["encoding"] == "utf-8"
    assert receipt["minimum_windows_build"] == 18362
    assert set(module.REQUIRED_EXES) <= set(receipt["executables"])
    for name, record in receipt["executables"].items():
        before = module.image((source / "bin" / name).read_bytes())
        after = module.image((target / "bin" / name).read_bytes())
        assert before["sections"] == after["sections"]
        assert all(after["resources"][key] == value for key, value in before["resources"].items())
        assert set(after["resources"]) - set(before["resources"]) == {(24, 1, 0)}
        assert b">UTF-8</activeCodePage>" in after["resources"][(24, 1, 0)]
        assert module.digest(target / "bin" / name) == record["sha256"]
    assert json.loads((target / "path-encoding.json").read_text()) == receipt
    assert all(module.digest(source / name) == expected for name, expected in original.items())
