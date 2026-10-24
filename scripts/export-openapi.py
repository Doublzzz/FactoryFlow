"""Export deterministic OpenAPI without starting services or touching a database."""

import argparse
import json
from pathlib import Path

from factoryflow.bootstrap import create_app

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "contracts" / "openapi.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = (
        json.dumps(create_app().openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != content:
            print("OpenAPI drift: run uv run python scripts/export-openapi.py")
            return 1
        print("OpenAPI matches server DTOs.")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(content, encoding="utf-8", newline="\n")
    print("Exported contracts/openapi.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
