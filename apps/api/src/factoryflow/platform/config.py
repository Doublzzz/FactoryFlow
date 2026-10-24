"""Explicit configuration loading, never at import time."""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str = field(repr=False)
    object_root: Path
    secure_cookies: bool = False
    ocr_engine: str = "windows"
    ocr_python: Path | None = field(default=None, repr=False)
    archive_root: Path | None = field(default=None, repr=False)

    def __post_init__(self):
        if self.archive_root is not None and (
            not isinstance(self.archive_root, Path) or not self.archive_root.is_absolute()
        ):
            raise ValueError("ARCHIVE_CONFIGURATION_INVALID")
        if not isinstance(self.ocr_engine, str) or self.ocr_engine not in {"windows", "rapid"}:
            raise ValueError("OCR_ENGINE_UNSUPPORTED")
        if self.ocr_engine == "windows" and self.ocr_python is not None:
            raise ValueError("OCR_CONFIGURATION_INVALID")
        if self.ocr_engine == "rapid" and (
            not isinstance(self.ocr_python, Path)
            or not self.ocr_python.is_absolute()
            or not self.ocr_python.is_file()
        ):
            raise ValueError("OCR_INTERPRETER_UNAVAILABLE")

    @classmethod
    def load(cls, path: Path):
        value = json.loads(path.read_text(encoding="utf-8"))
        if "archive_root" in value and not isinstance(value["archive_root"], str):
            raise ValueError("ARCHIVE_CONFIGURATION_INVALID")
        if "ocr_python" in value and not isinstance(value["ocr_python"], str):
            raise ValueError("OCR_CONFIGURATION_INVALID")
        if not isinstance(value.get("ocr_engine", "windows"), str):
            raise ValueError("OCR_ENGINE_UNSUPPORTED")
        return cls(
            value["database_url"],
            Path(value["object_root"]),
            value.get("secure_cookies", False),
            value.get("ocr_engine", "windows"),
            Path(value["ocr_python"]) if isinstance(value.get("ocr_python"), str) else None,
            Path(value["archive_root"]) if isinstance(value.get("archive_root"), str) else None,
        )
