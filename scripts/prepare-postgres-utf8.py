"""Add Windows process UTF-8 manifests to a NEW PostgreSQL runtime copy only."""

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import struct
from pathlib import Path

REQUIRED_EXES = {
    "initdb.exe",
    "postgres.exe",
    "pg_ctl.exe",
    "pg_dump.exe",
    "pg_restore.exe",
    "pg_controldata.exe",
}
KIND = "factoryflow-postgresql-utf8-v1"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def image(data):
    """Read the bounded PE resource tree and hashes of all other raw sections."""

    def take(offset, size):
        if offset < 0 or size < 0 or offset + size > len(data):
            raise ValueError("Truncated PE input")
        return data[offset : offset + size]

    def number(offset, fmt="<I"):
        return struct.unpack(fmt, take(offset, struct.calcsize(fmt)))[0]

    if take(0, 2) != b"MZ":
        raise ValueError("Not a Windows executable")
    pe = number(60)
    if take(pe, 4) != b"PE\0\0" or number(pe + 4, "<H") != 0x8664:
        raise ValueError("Only AMD64 PE executables are supported")
    optional = pe + 24
    if number(optional, "<H") != 0x20B or number(pe + 20, "<H") < 152:
        raise ValueError("Unsupported PE optional header")
    if number(optional + 108) < 5 or any(take(optional + 144, 8)):
        raise ValueError("Signed or unsupported executables must not be transformed")
    sections, ranges = {}, []
    table = optional + number(pe + 20, "<H")
    for index in range(number(pe + 6, "<H")):
        header = table + index * 40
        name = take(header, 8).rstrip(b"\0").decode("ascii")
        size, offset = number(header + 16), number(header + 20)
        raw = take(offset, size)
        ranges.append((number(header + 12), size, offset))
        if name != ".rsrc":
            if name in sections:
                raise ValueError("Duplicate PE section")
            sections[name] = hashlib.sha256(raw).hexdigest()

    def location(rva, size):
        for start, length, offset in ranges:
            if start <= rva and rva + size <= start + length:
                return offset + rva - start
        raise ValueError("PE resource outside a raw section")

    resources = {}
    resource_rva, resource_size = number(optional + 128), number(optional + 132)
    if resource_rva:
        base = location(resource_rva, resource_size)

        def resource(offset, size):
            if offset < 0 or offset + size > resource_size:
                raise ValueError("Invalid PE resource offset")
            return take(base + offset, size)

        def visit(offset, keys):
            if len(keys) >= 3:
                raise ValueError("Invalid PE resource depth")
            header = resource(offset, 16)
            count = sum(struct.unpack("<HH", header[12:16]))
            for index in range(count):
                name, value = struct.unpack("<II", resource(offset + 16 + index * 8, 8))
                if name & 0x80000000:
                    at = name & 0x7FFFFFFF
                    length = struct.unpack("<H", resource(at, 2))[0]
                    name = resource(at + 2, length * 2).decode("utf-16-le")
                key = (*keys, name)
                if value & 0x80000000:
                    visit(value & 0x7FFFFFFF, key)
                else:
                    if len(key) != 3 or key in resources:
                        raise ValueError("Invalid PE resource leaf")
                    rva, size, _, _ = struct.unpack("<IIII", resource(value, 16))
                    resources[key] = take(location(rva, size), size)

        visit(0, ())
    return {"sections": sections, "resources": resources}


def manifest(name):
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">'
        f'<assemblyIdentity type="win32" name="FactoryFlow.PostgreSQL.{name}" '
        'version="18.6.0.0"/>'
        '<application xmlns="urn:schemas-microsoft-com:asm.v3"><windowsSettings>'
        '<activeCodePage xmlns="http://schemas.microsoft.com/SMI/2019/WindowsSettings">'
        "UTF-8</activeCodePage></windowsSettings></application></assembly>"
    ).encode()


def add_manifest(path, content):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.BeginUpdateResourceW.argtypes = [ctypes.c_wchar_p, ctypes.c_int]
    kernel.BeginUpdateResourceW.restype = ctypes.c_void_p
    kernel.UpdateResourceW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ushort,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    kernel.EndUpdateResourceW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    handle = kernel.BeginUpdateResourceW(str(path), False)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    buffer = ctypes.create_string_buffer(content)
    if not kernel.UpdateResourceW(handle, 24, 1, 0, buffer, len(content)):
        error = ctypes.get_last_error()
        kernel.EndUpdateResourceW(handle, True)
        raise ctypes.WinError(error)
    if not kernel.EndUpdateResourceW(handle, False):
        raise ctypes.WinError(ctypes.get_last_error())


def prepare(source, target):
    source, target = Path(source).resolve(), Path(target).absolute()
    if target.exists():
        raise FileExistsError("The PostgreSQL output directory must be new")
    if target.resolve() != target or target.is_relative_to(source):
        raise ValueError("Output must be direct and outside the input runtime")
    for directory in ("bin", "lib", "share"):
        if not (source / directory).is_dir():
            raise ValueError("PostgreSQL runtime is incomplete")
    executables = sorted((source / "bin").glob("*.exe"))
    if not REQUIRED_EXES <= {path.name for path in executables}:
        raise ValueError("Required PostgreSQL executables are missing")
    before = {}
    for path in executables:
        if not re.fullmatch(r"[a-z0-9_]+\.exe", path.name):
            raise ValueError("Unexpected executable name")
        parsed = image(path.read_bytes())
        if any(key[0] == 24 for key in parsed["resources"]):
            raise ValueError("Existing manifests require a separately reviewed merge")
        before[path.name] = (digest(path), parsed)
    if os.name != "nt":
        raise ValueError("Runtime resource preparation requires Windows")
    target.mkdir(parents=True)
    for directory in ("bin", "lib", "share"):
        shutil.copytree(source / directory, target / directory)
    records = {}
    for path in executables:
        destination = target / "bin" / path.name
        original_hash, original = before[path.name]
        if digest(destination) != original_hash:
            raise ValueError("Source executable changed during copy")
        content = manifest(path.stem)
        add_manifest(destination, content)
        changed = image(destination.read_bytes())
        if (
            changed["sections"] != original["sections"]
            or changed["resources"] != original["resources"] | {(24, 1, 0): content}
            or digest(path) != original_hash
        ):
            raise ValueError("Runtime transformation changed more than its manifest")
        records[path.name] = {
            "before_sha256": original_hash,
            "sha256": digest(destination),
            "non_resource_sections": changed["sections"],
        }
    receipt = {
        "kind": KIND,
        "encoding": "utf-8",
        "minimum_windows_build": 18362,
        "change": "Added process activeCodePage UTF-8 manifest; code and prior resources retained",
        "executables": records,
    }
    (target / "path-encoding.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    result = prepare(args.source, args.target)
    print(json.dumps({"encoding": result["encoding"], "executables": len(result["executables"])}))
