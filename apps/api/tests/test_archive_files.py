import hashlib
import io
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from zipfile import ZipFile

import pytest
from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.archives.adapters.local_archive import (
    LocalArchiveStore,
    build_zip,
    canonical_json,
)
from factoryflow.modules.archives.domain.paths import relative_path


def item(**changes):
    value = {
        "kind": "source",
        "source_id": str(uuid4()),
        "title": "合成订单",
        "customer_id": str(uuid4()),
        "customer_name": "合成客户",
        "business_date": "2026-01-30",
        "period_end": None,
        "version_label": "修订v1",
        "state_label": "已确认",
        "extension": "png",
        "token": "a" * 64,
    }
    value["key"] = f"source:{value['source_id']}"
    value.update(changes)
    return value


@pytest.mark.parametrize(
    "rule,prefix",
    [
        ("date", "工作文件/2026/01/30/订单原件/"),
        ("customer", "工作文件/合成客户_"),
        ("month_customer", "工作文件/2026/01/合成客户_"),
    ],
)
def test_rules(rule, prefix):
    value = item()
    path = relative_path(rule, value)
    assert path.startswith(prefix)
    assert value["source_id"] in path
    assert "修订v1" in path and "已确认" in path


@pytest.mark.parametrize("rule", ["date", "customer", "month_customer"])
def test_missing_date_waits(rule):
    assert relative_path(rule, item(business_date=None)).startswith("工作文件/待归类/")


@pytest.mark.parametrize("rule", ["customer", "month_customer"])
def test_missing_customer_waits(rule):
    assert relative_path(rule, item(customer_id=None)).startswith("工作文件/待归类/")


def test_cross_month_and_safe_names():
    value = item(
        title="../CON:非法\\路径\x00. " * 100, customer_name="NUL", period_end="2026-02-10"
    )
    path = relative_path("month_customer", value)
    assert path.startswith("工作文件/2026/01/")
    assert "2026-01-30" in path and "2026-02-10" in path
    assert len(path) < 220 and "\\" not in path and "\x00" not in path
    assert ".." not in path.split("/")
    assert path != relative_path("month_customer", item())
    other = dict(value, token="b" * 64)
    assert path != relative_path("month_customer", other)


@pytest.mark.parametrize(
    "changes",
    [{"source_id": "../escape"}, {"token": "bad"}, {"extension": "../png"}, {"kind": "other"}],
)
def test_invalid_item(changes):
    with pytest.raises(BusinessError):
        relative_path("date", item(**changes))


def test_invalid_rule():
    with pytest.raises(BusinessError, match="ARCHIVE_RULE_INVALID"):
        relative_path("unsafe", item())


def test_english_paths_and_manifest_keep_customer_text_and_safe_names():
    value = item(
        title="Synthetic order.pdf",
        customer_name="Original 用户名",
        version_label="确认版本 v1",
        state_label="已确认",
    )
    path = relative_path("month_customer", value, locale="en")
    assert path.startswith("Work files/2026/01/Original 用户名_")
    assert "/Order originals/" in path and "Confirmed" in path
    with ZipFile(io.BytesIO(build_zip({path: b"synthetic"}, {"locale": "en"}))) as reader:
        assert "manifest.json" in reader.namelist()
        assert "清单.json" not in reader.namelist()
        assert reader.read(path) == b"synthetic"


def test_zip_deterministic_and_same_manifest():
    files = {"工作文件/订单/b.png": b"two", "工作文件/订单/a.png": b"one"}
    manifest = {"说明": "工作文件", "version": 1}
    archive = build_zip(files, manifest)
    assert (
        hashlib.sha256(archive).digest()
        == hashlib.sha256(
            build_zip(dict(reversed(list(files.items()))), dict(reversed(list(manifest.items()))))
        ).digest()
    )
    with ZipFile(io.BytesIO(archive)) as reader:
        assert reader.namelist() == sorted([*files, "清单.json"])
        assert reader.read("清单.json") == canonical_json(manifest)
        for path, content in files.items():
            assert reader.read(path) == content
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in reader.infolist())


@pytest.mark.parametrize(
    "path", ["../x", "/x", "C:/x", "x\\y", "CON", "x. ", "a/../b", "a//b", "清单.json", "x\x00"]
)
def test_zip_rejects_paths(path):
    with pytest.raises(BusinessError):
        build_zip({path: b"a"}, {})


@pytest.mark.parametrize(
    "files",
    [
        {"A": b"1", "a": b"2"},
        {"A/x": b"1", "a/y": b"2"},
        {"a": b"1", "a/b": b"2"},
        {f"f{i}": b"a" for i in range(51)},
        {"a": b"x" * (50 * 1024 * 1024)},
    ],
)
def test_zip_rejects_collisions_and_limits(files):
    with pytest.raises(BusinessError):
        build_zip(files, {})


def test_publish_is_lazy_idempotent_and_concurrent(tmp_path):
    root = tmp_path / "archive"
    store = LocalArchiveStore(root)
    org, batch = str(uuid4()), str(uuid4())
    files, manifest = {"工作文件/a.png": b"original"}, {"work": True}
    assert not root.exists()
    assert not store.available(org, batch, files, manifest)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: store.publish(org, batch, files, manifest), range(4)))
    assert results == [f"{org}/{batch}"] * 4
    assert store.available(org, batch, files, manifest)
    assert (root / results[0] / "清单.json").read_bytes() == canonical_json(manifest)
    assert not list((root / org).glob(".staging-*"))


@pytest.mark.parametrize("corruption", ["extra", "empty_dir", "missing", "changed"])
def test_existing_conflict_never_overwrites(tmp_path, corruption):
    store = LocalArchiveStore(tmp_path)
    org, batch = str(uuid4()), str(uuid4())
    files = {"work/a": b"original"}
    directory = tmp_path / store.publish(org, batch, files, {})
    target = directory / "work/a"
    if corruption == "extra":
        (directory / "extra").write_bytes(b"user")
    elif corruption == "empty_dir":
        (directory / "extra").mkdir()
    elif corruption == "missing":
        target.unlink()
    else:
        target.write_bytes(b"user")
    for operation in [store.available, store.publish]:
        with pytest.raises(BusinessError, match="ARCHIVE_COPY_CONFLICT"):
            operation(org, batch, files, {})
    if corruption == "changed":
        assert target.read_bytes() == b"user"


def test_failure_cleans_stage_and_retry_recovers(tmp_path, monkeypatch):
    store = LocalArchiveStore(tmp_path)
    org, batch = str(uuid4()), str(uuid4())
    original = os.fsync
    monkeypatch.setattr(os, "fsync", lambda _: (_ for _ in ()).throw(OSError("private")))
    with pytest.raises(BusinessError, match="ARCHIVE_COPY_FAILED") as error:
        store.publish(org, batch, {"work/a": b"a"}, {})
    assert "private" not in str(error.value)
    assert not (tmp_path / org / batch).exists()
    assert not list((tmp_path / org).glob(".staging-*"))
    monkeypatch.setattr(os, "fsync", original)
    store.publish(org, batch, {"work/a": b"a"}, {})


def test_unconfigured_and_relative_root(tmp_path):
    with pytest.raises(BusinessError, match="ARCHIVE_NOT_CONFIGURED"):
        LocalArchiveStore(None).publish(str(uuid4()), str(uuid4()), {}, {})
    with pytest.raises(BusinessError):
        LocalArchiveStore(type(tmp_path)("relative")).publish(str(uuid4()), str(uuid4()), {}, {})


@pytest.mark.skipif(os.name != "nt", reason="Windows junction enforcement")
@pytest.mark.parametrize("position", ["ancestor", "child", "internal"])
def test_real_junction_refused(tmp_path, position):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, check=False
    )
    assert result.returncode == 0
    org, batch = str(uuid4()), str(uuid4())
    try:
        if position == "ancestor":
            store = LocalArchiveStore(link / "root")
        elif position == "child":
            store = LocalArchiveStore(tmp_path)
            link.rename(tmp_path / org)
            link = tmp_path / org
        else:
            store = LocalArchiveStore(tmp_path)
            directory = tmp_path / store.publish(org, batch, {"work/a": b"a"}, {})
            (directory / "work/a").unlink()
            (directory / "work").rmdir()
            link.rename(directory / "work")
            link = directory / "work"
        with pytest.raises(BusinessError):
            store.publish(org, batch, {"work/a": b"a"}, {})
        assert not (target / batch).exists()
    finally:
        link.rmdir()
