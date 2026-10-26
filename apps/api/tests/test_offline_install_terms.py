"""CLI acceptance uses only synthetic TEMP bundles, without desktop shortcuts."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]

# Verbatim section from Python's Windows LICENSE.txt; unrelated license sections excluded.
TERMS = """Additional Conditions for this Windows binary build
---------------------------------------------------

This program is linked with and uses Microsoft Distributable Code,
copyrighted by Microsoft Corporation. The Microsoft Distributable Code
is embedded in each .exe, .dll and .pyd file as a result of running
the code through a linker.

If you further distribute programs that include the Microsoft
Distributable Code, you must comply with the restrictions on
distribution specified by Microsoft. In particular, you must require
distributors and external end users to agree to terms that protect the
Microsoft Distributable Code at least as much as Microsoft's own
requirements for the Distributable Code. See Microsoft's documentation
(included in its developer tools and on its website at microsoft.com)
for specific details.

Redistribution of the Windows binary build of the Python interpreter
complies with this agreement, provided that you do not:

- alter any copyright, trademark or patent notice in Microsoft's
Distributable Code;

- use Microsoft's trademarks in your programs' names or in a way that
suggests your programs come from or are endorsed by Microsoft;

- distribute Microsoft's Distributable Code to run on a platform other
than Microsoft operating systems, run-time technologies or application
platforms; or

- include Microsoft Distributable Code in malicious, deceptive or
unlawful programs.

These restrictions apply only to the Microsoft Distributable Code as
defined above, not to Python itself or any programs running on the
Python interpreter. The redistribution of the Python interpreter and
libraries is governed by the Python Software License included with this
file, or by other licenses as marked.
"""


@pytest.fixture
def cli_bundle(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "offline_install_terms", ROOT / "scripts/install-offline.py"
    )
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    package = tmp_path / "package"
    source = package / "app"
    license_path = source / "runtime/python/LICENSE.txt"
    license_path.parent.mkdir(parents=True)
    license_path.write_text(
        "Synthetic preceding license\n" + TERMS + "\n----------\nSynthetic next license\n",
        encoding="utf-8",
    )
    for name in (
        "启动工厂软件",
        "停止工厂软件",
        "备份工厂数据",
        "恢复工厂备份",
        "查看运行状态",
        "Start FactoryFlow",
        "Stop FactoryFlow",
        "Back Up Data",
        "Restore Backup",
        "Check Status",
    ):
        (source / (name + ".cmd")).write_text("@echo synthetic\n", encoding="utf-8")
    files = {
        path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source.rglob("*")
        if path.is_file()
    }
    (source / "bundle.json").write_text(
        json.dumps(
            {"kind": "factoryflow-offline-v1", "build_id": "1234567890abcdef", "files": files}
        ),
        encoding="utf-8",
    )
    destination = tmp_path / "synthetic-install"
    monkeypatch.setattr(installer, "__file__", str(package / "install.py"))
    monkeypatch.setattr(
        sys,
        "argv",
        ["install.py", "--destination", str(destination), "--no-shortcuts"],
    )
    return SimpleNamespace(
        installer=installer, source=source, license=license_path, destination=destination
    )


@pytest.mark.parametrize("answer", ["", "N", "no", "yes", "anything else"])
def test_rejecting_terms_never_creates_destination(cli_bundle, monkeypatch, capsys, answer):
    def forbidden(*args, **kwargs):
        pytest.fail("Declining terms must not install or access desktop shortcuts")

    monkeypatch.setattr(sys, "argv", sys.argv[:-1])  # Exercise the default shortcut setting.
    monkeypatch.setattr(cli_bundle.installer, "install", forbidden)
    monkeypatch.setattr(
        cli_bundle.installer, "ctypes", SimpleNamespace(create_unicode_buffer=forbidden)
    )
    monkeypatch.setattr("builtins.input", lambda prompt: answer)
    assert cli_bundle.installer.main() == 1
    assert not cli_bundle.destination.exists()
    output = capsys.readouterr().out
    assert TERMS in output
    assert "不改变 FactoryFlow 的 MIT 许可" in output
    assert "Synthetic preceding license" not in output
    assert "Synthetic next license" not in output


@pytest.mark.parametrize("error", [EOFError, OSError])
def test_no_interactive_input_cancels_without_writes(cli_bundle, monkeypatch, error):
    def unavailable(prompt):
        raise error("synthetic unavailable stdin")

    monkeypatch.setattr("builtins.input", unavailable)
    assert cli_bundle.installer.main() == 1
    assert not cli_bundle.destination.exists()


@pytest.mark.parametrize("explicit_flag", [False, True])
def test_explicit_acceptance_installs_synthetic_bundle(
    cli_bundle, monkeypatch, capsys, explicit_flag
):
    def answer(prompt):
        if explicit_flag:
            pytest.fail("Explicit acceptance must not read stdin")
        return "Y"

    monkeypatch.setattr("builtins.input", answer)
    if explicit_flag:
        monkeypatch.setattr(sys, "argv", [*sys.argv, "--accept-third-party-terms"])
    assert cli_bundle.installer.main() == 0
    program = cli_bundle.destination / "program/1234567890abcdef"
    assert cli_bundle.installer.verify(program) == cli_bundle.installer.verify(cli_bundle.source)
    assert (program / "runtime/python/LICENSE.txt").read_bytes() == cli_bundle.license.read_bytes()
    assert (cli_bundle.destination / "启动工厂软件.cmd").is_file()
    assert TERMS in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["file", "title", "underline", "ending", "separator"])
def test_incomplete_terms_fail_even_with_acceptance_flag(cli_bundle, monkeypatch, failure):
    if failure == "file":
        cli_bundle.license.unlink()
    else:
        text = cli_bundle.license.read_text(encoding="utf-8")
        if failure == "title":
            text = text.replace("Additional Conditions for this Windows binary build", "Unknown")
        elif failure == "underline":
            text = text.replace("---------------------------------------------------", "Unknown", 1)
        elif failure == "ending":
            text = text.replace("file, or by other licenses as marked.", "Truncated")
        else:
            text = text.replace("\n----------\n", "\nUnknown separator\n")
        cli_bundle.license.write_text(text, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [*sys.argv, "--accept-third-party-terms"])
    with pytest.raises(ValueError, match="Microsoft 组件条件"):
        cli_bundle.installer.main()
    assert not cli_bundle.destination.exists()


@pytest.mark.parametrize("answer,installed", [("Y", True), ("N", False)])
def test_english_install_preserves_terms_and_requires_explicit_consent(
    cli_bundle, monkeypatch, capsys, answer, installed
):
    monkeypatch.setattr(sys, "argv", [*sys.argv, "--language", "en"])
    monkeypatch.setattr("builtins.input", lambda prompt: answer)
    assert cli_bundle.installer.main() == (0 if installed else 1)
    output = capsys.readouterr().out
    assert TERMS in output
    assert "Microsoft" in output and "MIT" in output
    assert not any("\u4e00" <= char <= "\u9fff" for char in output)
    assert cli_bundle.destination.exists() is installed
    if installed:
        assert (cli_bundle.destination / "Start FactoryFlow.cmd").is_file()
        assert (cli_bundle.destination / "启动工厂软件.cmd").is_file()
