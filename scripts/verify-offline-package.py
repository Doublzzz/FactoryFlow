"""Exercise an installed package with only synthetic business data and explicit external paths."""

import argparse
import hashlib
import http.cookiejar
import importlib.util
import json
import os
import secrets
import subprocess
import sys
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from uuid import uuid4


class API:
    def __init__(self, url):
        self.url = url.rstrip("/") + "/api/v1"
        self.csrf = ""
        self.client = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        )

    def call(self, method, path, body=None, *, raw=None, headers=None, binary=False):
        extra = {"X-CSRF-Token": self.csrf, **(headers or {})}
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            extra["Content-Type"] = "application/json"
        if method == "POST":
            extra["Idempotency-Key"] = str(uuid4())
        request = urllib.request.Request(self.url + path, data=data, headers=extra, method=method)
        try:
            with self.client.open(request, timeout=120) as response:
                content = response.read()
                return content if binary else json.loads(content)
        except urllib.error.HTTPError as error:
            failure = json.loads(error.read())
            raise RuntimeError(f"{method} {path}: {error.code} {failure.get('code')}") from None

    def command(self, path, body):
        return self.call("POST", path, body)

    def login(self, username, password):
        self.csrf = self.command("/auth/login", {"username": username, "password": password})[
            "csrf_token"
        ]


def main():
    from openpyxl import load_workbook
    from PIL import Image, ImageDraw, ImageFont
    from sqlalchemy import text

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    assert Path(sys.prefix).resolve() == (args.app / "runtime/python").resolve()
    spec = importlib.util.spec_from_file_location(
        "factory_local", args.app / "scripts/factory-local.py"
    )
    factory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(factory)
    factory.BASE = args.root / "首台电脑数据"
    assert not factory.BASE.exists(), "Use a new synthetic verification root"
    for key in list(os.environ):
        if key.upper().startswith(("PYTHON", "PG")):
            del os.environ[key]
    windows = Path(os.environ["SYSTEMROOT"])
    os.environ["PATH"] = (
        str(windows / "System32") + ";" + str(windows / "System32/WindowsPowerShell/v1.0")
    )
    os.environ["HTTP_PROXY"] = os.environ["HTTPS_PROXY"] = "http://127.0.0.1:9"
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    login = {"username": "synthetic-offline-admin", "password": secrets.token_urlsafe(24)}
    start = subprocess.run(
        [
            sys.executable,
            "-I",
            "-X",
            "utf8",
            str(factory.SCRIPT),
            "start",
            "--no-browser",
            "--data-root",
            str(factory.BASE),
        ],
        input="Synthetic Offline Factory\n"
        + login["username"]
        + "\n"
        + login["password"]
        + "\n"
        + login["password"]
        + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=150,
    )
    (args.root / "first-start-output.txt").write_text(start.stdout + start.stderr, encoding="utf-8")
    assert start.returncode == 0, "First setup/start failed; inspect private first-start-output.txt"
    original = factory.active()
    restored = None
    report = {"installed_app": str(args.app), "build_id": factory.build_id(), "checks": {}}
    try:
        state = factory.status(original)
        assert state["ready"] and state["schema"] == state["expected_schema"]
        runtime = factory.build_services(factory.environment(original)[0])
        try:
            with runtime.engine.connect() as connection:
                for table in (
                    "customers",
                    "orders",
                    "deliveries",
                    "statements",
                    "statement_templates",
                ):
                    assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0
        finally:
            runtime.close()
        report["checks"]["blank_first_setup"] = True
        api = API(state["url"])
        api.login(**login)
        customer = api.command("/customers", {"full_name": "Synthetic Offline Customer"})
        order = api.command(
            "/orders",
            {
                "customer_id": customer["id"],
                "order_number": "SYN-OFFLINE-001",
                "business_date": "2026-10-01",
                "currency": "CNY",
                "lines": [
                    {
                        "description": "Synthetic offline part",
                        "item_code": "SYN-PART-01",
                        "item_name": "Synthetic part",
                        "specification": "Synthetic specification",
                        "quantity": "12",
                        "unit": "PCS",
                        "source_unit_price": "3.25",
                        "source_amount": None,
                    }
                ],
            },
        )
        order = api.call("GET", "/orders/" + order["order_id"])
        delivery = api.command(
            "/deliveries",
            {
                "order_id": order["id"],
                "customer_id": customer["id"],
                "revision_id": order["revision_id"],
                "expected_version": order["version"],
                "delivery_date": "2026-10-02",
                "inventory_mode": "skip",
                "lines": [{"order_line_id": order["lines"][0]["id"], "quantity": "5"}],
            },
        )
        source = {"delivery_id": delivery["id"], "order_line_id": order["lines"][0]["id"]}
        draft = api.command(
            "/statements",
            {
                "customer_id": customer["id"],
                "period_start": "2026-10-01",
                "currency": "CNY",
                "period_end": "2026-10-31",
                "tax_mode": "untaxed_final",
                "tax_rate": "0",
                "adjustments": [],
                "lines": [
                    {
                        **source,
                        "quantity": "5",
                        "unit_price": "3.25",
                        "reason": "Synthetic",
                        "external_document_number": "SYN-EXT-0001",
                    }
                ],
            },
        )
        path = "/statements/" + draft["id"]
        export = api.command(path + "/exports", {"expected_version": draft["version"]})
        assert (
            api.command("/statement-exports/" + export["id"] + "/generate", {})["status"] == "ready"
        )
        sent = api.command(
            path + "/sent",
            {
                "expected_version": draft["version"],
                "export_id": export["id"],
                "person": "Synthetic Sender",
                "occurred_on": "2026-10-03",
                "note": "Synthetic send record",
            },
        )
        feedback = api.command(
            path + "/feedback",
            {
                "person": "Synthetic Receiver",
                "occurred_on": "2026-10-03",
                "note": "Synthetic confirmation",
            },
        )
        approval = api.command(
            path + "/approve",
            {
                "expected_version": api.call("GET", path)["version"],
                **source,
                "sent_id": sent["id"],
                "feedback_id": feedback["id"],
                "quantity": "5",
                "unit_price": "3.25",
                "target_start": "2026-10-01",
                "target_end": "2026-10-31",
                "reason": "Synthetic approved",
            },
        )
        assert approval["external_document_number"] == "SYN-EXT-0001"
        api.command(
            path + "/reserve",
            {
                "expected_version": api.call("GET", path)["version"],
                "approval_id": approval["id"],
                "approval_version": approval["version"],
                "quantity": "5",
                "reason": "Synthetic settlement",
            },
        )
        body = {
            "expected_version": api.call("GET", path)["version"],
            "fees_confirmed": True,
            "reconfirmation": "not_required",
            "reason": "Synthetic checked",
        }
        preview = api.command(path + "/settlement-preview", body)
        assert preview["blockers"] == []
        formal = api.command(path + "/settle", body | {"preview_token": preview["token"]})
        assert formal["status"] == "confirmed" and formal["calculation"]["total"] == "16.25"
        final_export = api.command(path + "/exports", {"expected_version": formal["version"]})
        assert (
            api.command("/statement-exports/" + final_export["id"] + "/generate", {})["status"]
            == "ready"
        )
        export_path = "/statement-exports/" + final_export["id"] + "/file"
        exported = api.call("GET", export_path, binary=True)
        book = load_workbook(BytesIO(exported))
        assert any("SYN-EXT-0001" in str(cell.value) for row in book.active for cell in row)
        report["checks"]["order_partial_delivery_formal_statement_excel"] = True
        image = Image.new("RGB", (1200, 420), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(str(windows / "Fonts/arial.ttf"), 40)
        for y, line in enumerate(
            ("SYNTHETIC ORDER 001", "Product       Qty       Unit", "Test part      12        PCS")
        ):
            draw.text((45, 40 + y * 100), line, fill="black", font=font)
        stream = BytesIO()
        image.save(stream, format="PNG")
        uploaded = api.call(
            "POST",
            "/sources",
            raw=stream.getvalue(),
            headers={"Content-Type": "image/png", "X-Filename": "synthetic-offline.png"},
        )
        extracted = api.command("/sources/" + uploaded["source_id"] + "/extractions", {})
        assert extracted["status"] == "ready", "Packaged offline OCR failed"
        detail = api.call("GET", "/extractions/" + extracted["extraction_id"])
        assert any("SYNTHETIC" in p["text"].upper() for p in detail["pages"])
        report["checks"]["packaged_ocr_actual_inference"] = True
        factory.stop(original)
        state = factory.start(original)
        api = API(state["url"])
        api.login(**login)
        assert api.call("GET", path) == formal
        assert api.call("GET", export_path, binary=True) == exported
        report["checks"]["restart_preserves_data_and_exact_export"] = True
        backed = factory.backup(original)
        factory.stop(original)
        factory.BASE = args.root / "换电脑恢复数据"
        result = factory.restore(Path(backed["backup"]))
        assert result["previous_environment"] is None and result["old_data_retained"]
        restored = factory.active()
        state = factory.start(restored)
        api = API(state["url"])
        api.login(**login)
        assert api.call("GET", path) == formal
        assert api.call("GET", export_path, binary=True) == exported
        assert (
            api.call("GET", "/sources/" + uploaded["source_id"] + "/download", binary=True)
            == stream.getvalue()
        )
        report["checks"]["backup_restore_on_fresh_data_home"] = True
        report["export_sha256"] = hashlib.sha256(exported).hexdigest()
        report["schema"] = state["schema"]
        # Synthetic credentials stay beside the private receipt for optional browser QA.
        (args.root / "ui-login-private.json").write_text(json.dumps(login), encoding="utf-8")
        (args.root / "receipt.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report["checks"], ensure_ascii=False))
    finally:
        if restored:
            factory.stop(restored)
        factory.BASE = args.root / "首台电脑数据"
        factory.stop(original)


if __name__ == "__main__":
    main()
