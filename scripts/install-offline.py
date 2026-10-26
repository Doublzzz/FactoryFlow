"""Install a verified offline bundle per user; never copy, reset or migrate business data."""

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
from pathlib import Path, PurePosixPath
from uuid import uuid4

LANGUAGE = "zh-CN"


def tr(chinese, english):
    return english if LANGUAGE == "en" else chinese


def verify(root):
    manifest = json.loads((root / "bundle.json").read_text(encoding="utf-8"))
    if manifest.get("kind") != "factoryflow-offline-v1" or not re.fullmatch(
        "[a-f0-9]{16}", manifest.get("build_id", "")
    ):
        raise ValueError(tr("安装包标记不匹配。", "The installation bundle marker does not match."))
    for name, digest in manifest["files"].items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
            raise ValueError(
                tr("安装包文件路径无效。", "The installation bundle contains an invalid file path.")
            )
        path = root.joinpath(*relative.parts)
        if path.resolve() != path.absolute() or not path.is_file():
            raise ValueError(
                tr(
                    "安装包不完整，请完整解压。",
                    "The bundle is incomplete. Extract the entire ZIP file first.",
                )
            )
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise ValueError(
                    tr(
                        "安装包校验失败，请重新复制压缩包并解压。",
                        "Bundle verification failed. Copy the ZIP again and extract it completely.",
                    )
                )
    return manifest


def install(source, destination):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    manifest = verify(source)
    if destination.resolve() != destination:
        raise ValueError(
            tr(
                "安装目录不能包含链接或映射目录。",
                "The install directory must not contain symbolic links or junctions.",
            )
        )
    program = destination / "program" / manifest["build_id"]
    if program.resolve() != program:
        raise ValueError(
            tr(
                "程序目录不能包含链接或映射目录。",
                "The program directory must not contain symbolic links or junctions.",
            )
        )
    if program.exists():
        if verify(program) != manifest:
            raise ValueError(
                tr(
                    "已有同名程序内容不同，未覆盖。",
                    "An existing program with this build ID has different contents. "
                    "It was not overwritten.",
                )
            )
    else:
        # Interrupted copies remain separate, so a retry can use a fresh staging directory.
        staging = program.parent / (".install-" + manifest["build_id"] + "-" + uuid4().hex)
        staging.mkdir(parents=True)
        for name in [*manifest["files"], "bundle.json"]:
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, target)
        verify(staging)
        try:
            staging.rename(program)
        except FileExistsError:
            if verify(program) != manifest:
                raise ValueError(
                    tr(
                        "已有同名程序内容不同，未覆盖。",
                        "An existing program with this build ID has different contents. "
                        "It was not overwritten.",
                    )
                ) from None
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
        if not (program / (name + ".cmd")).is_file():
            continue
        target = destination / (name + ".cmd")
        text = '@echo off\r\nchcp 65001 >nul\r\ncall "' + str(program / (name + ".cmd")) + '"\r\n'
        target.write_text(text, encoding="utf-8", newline="")
    return destination / ("Start FactoryFlow.cmd" if LANGUAGE == "en" else "启动工厂软件.cmd")


def microsoft_terms(source):
    try:
        text = (source / "runtime/python/LICENSE.txt").read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(
            tr(
                "缺少随包 Python 许可证，无法核对 Microsoft 组件条件。",
                "The Python license is missing; Microsoft component terms cannot be checked.",
            )
        ) from error
    lines = text.splitlines(keepends=True)
    title = "Additional Conditions for this Windows binary build"
    for start, line in enumerate(lines):
        if line.strip() != title:
            continue
        # The title's underline precedes the terms; the next divider ends this section.
        if start + 1 >= len(lines) or set(lines[start + 1].strip()) != {"-"}:
            break
        for end in range(start + 2, len(lines)):
            if set(lines[end].strip()) == {"-"}:
                section = "".join(lines[start:end])
                if "Microsoft Distributable Code" in section and section.rstrip().endswith(
                    "file, or by other licenses as marked."
                ):
                    return section
                break
        break
    raise ValueError(
        tr(
            "随包 Python 许可证缺少完整的 Microsoft 组件条件，安装已停止。",
            "The Python license lacks complete Microsoft component terms. Installation stopped.",
        )
    )


def main():
    global LANGUAGE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--language", choices=["zh-CN", "en"], default="zh-CN")
    parser.add_argument("--no-shortcuts", action="store_true")
    parser.add_argument(
        "--accept-third-party-terms",
        action="store_true",
        help="Confirm that the bundled Microsoft component terms were read and accepted in advance",
    )
    args = parser.parse_args()
    LANGUAGE = args.language
    source = Path(__file__).resolve().parent / "app"
    destination = args.destination or Path(os.environ["LOCALAPPDATA"]) / "FactoryFlow"
    print(
        tr(
            "以下为随包 Python 许可证中的 Microsoft 组件条件原文。",
            "The following Microsoft component terms are quoted from the bundled Python license.",
        )
    )
    print(
        tr(
            "这些条件仅约束 Microsoft 组件，不改变 FactoryFlow 的 MIT 许可。",
            "These terms apply only to Microsoft components; "
            "they do not change FactoryFlow's MIT license.",
        )
    )
    print(microsoft_terms(source))
    if not args.accept_third_party_terms:
        try:
            accepted = input(
                tr(
                    "同意上述 Microsoft 组件条件并继续安装？输入 Y 同意，其他输入取消：",
                    "Accept the Microsoft component terms above and continue? "
                    "Type Y to accept; anything else cancels: ",
                )
            )
        except EOFError, OSError:
            accepted = ""
        if accepted.strip().upper() != "Y":
            print(
                tr(
                    "安装已取消，未复制程序或创建快捷方式。",
                    "Installation cancelled. No program files or shortcuts were created.",
                )
            )
            return 1
    entry = install(source, destination)
    if not args.no_shortcuts:
        folder = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 16, None, 0, folder) == 0:
            desktop = Path(folder.value) / (
                "FactoryFlow.cmd" if LANGUAGE == "en" else "FactoryFlow 工厂软件.cmd"
            )
            desktop.write_text(
                '@echo off\r\nchcp 65001 >nul\r\ncall "' + str(entry) + '"\r\n',
                encoding="utf-8",
                newline="",
            )
    print(
        tr(
            "安装完成。打开下方程序入口，首次使用时设置账号。",
            "Installation complete. Open the program entry below to set up your account.",
        )
    )
    print(tr("程序入口：", "Program entry: ") + str(entry))
    print(
        tr(
            "业务数据独立保存；重复安装不会清空数据。",
            "Business data is stored separately. Reinstalling does not erase it.",
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(tr("安装未完成：", "Installation did not complete: ") + str(error))
        raise SystemExit(1) from None
