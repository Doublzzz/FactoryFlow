"""Seed fixed synthetic archive examples only in an owned unified trial environment."""

import importlib.util
import json
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from factoryflow.bootstrap import build_services
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def picture(title, pending=False):
    image = Image.new("RGB", (1100, 1050), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 24)
    draw.text((35, 25), "完全合成样例 · 文件整理验证", fill="black", font=font)
    draw.text((35, 70), title, fill="black", font=font)
    if pending:
        draw.text((35, 130), "客户和业务日期尚未人工确认，保留待归类。", fill="black", font=font)
    else:
        draw.text((35, 130), "合成客户·星河工场 / 2026-09-30", fill="black", font=font)
        for index in range(1, 13):
            draw.text(
                (35, 180 + index * 52),
                f"SYN-{index:02}  合成部件 {index}  5 PCS",
                fill="black",
                font=font,
            )
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def main():
    spec = importlib.util.spec_from_file_location("archive_trial", ROOT / "scripts/local-trial.py")
    trial = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trial)
    root = trial.active()  # Verifies exact UUID path and synthetic ownership marker.
    settings, _ = trial.environment(root)
    if settings.archive_root != root / "archives":
        raise ValueError("Archive demo requires the configured owned trial archive root")
    receipt = root / "archive-demo.json"
    if receipt.exists():
        print(json.dumps({"state": "already-seeded", "environment": root.name}))
        return
    runtime = build_services(settings)
    try:
        runtime.check_ready()
        actor = runtime.identity.login(**trial.read(root / "client.json"))["actor"]
        customer = runtime.customers.create(actor, uuid4(), "合成客户·星河工场")
        original = runtime.extraction.upload(
            actor, uuid4(), "合成订单-星河.png", "image/png", picture("SYN-ARCHIVE-NORMAL")
        )
        pending = runtime.extraction.upload(
            actor,
            uuid4(),
            "合成原件-待核对.png",
            "image/png",
            picture("待人工核对的合成原件", True),
        )
        # This fixed fixture only establishes trace ownership; it does not run or assess OCR.
        runtime.extraction.extractor.extract = lambda *_: {
            "status": "ready",
            "error_code": None,
            "pages": [],
            "engine": "synthetic-archive-fixture",
        }
        run = runtime.extraction.extract(actor, uuid4(), UUID(original["source_id"]))
        body = {
            "customer_id": str(customer["id"]),
            "order_number": "SYN-ARCHIVE-NORMAL",
            "business_date": "2026-09-30",
            "currency": "CNY",
            "extraction_id": run["extraction_id"],
            "lines": [
                {
                    "item_code": f"SYN-{i:02}",
                    "item_name": f"合成部件 {i}",
                    "specification": f"演示规格 {i}",
                    "quantity": "5",
                    "unit": "PCS",
                }
                for i in range(1, 13)
            ],
        }
        # Use the normal HTTP DTO boundary for confirmed order commands.
        import httpx

        with httpx.Client(base_url="http://127.0.0.1:8120", trust_env=False, timeout=30) as client:
            login = client.post("/api/v1/auth/login", json=trial.read(root / "client.json"))
            login.raise_for_status()
            client.headers["X-CSRF-Token"] = login.json()["csrf_token"]

            def command(path, payload):
                result = client.post(path, json=payload, headers={"Idempotency-Key": str(uuid4())})
                if result.status_code != 200:
                    raise RuntimeError(
                        f"Synthetic command failed: {result.status_code} "
                        f"{result.json().get('code')}"
                    )
                return result.json()

            confirmed = command("/api/v1/orders", body)
            order = client.get(f"/api/v1/orders/{confirmed['order_id']}").json()
            delivery = command(
                "/api/v1/deliveries",
                {
                    "order_id": order["id"],
                    "customer_id": customer["id"],
                    "revision_id": order["revision_id"],
                    "expected_version": 1,
                    "delivery_date": "2026-10-01",
                    "lines": [{"order_line_id": i["id"], "quantity": "1"} for i in order["lines"]],
                },
            )
            void = command(
                "/api/v1/deliveries",
                {
                    "order_id": order["id"],
                    "customer_id": customer["id"],
                    "revision_id": order["revision_id"],
                    "expected_version": 2,
                    "delivery_date": "2026-10-02",
                    "lines": [{"order_line_id": order["lines"][0]["id"], "quantity": "1"}],
                },
            )
            command(
                f"/api/v1/deliveries/{void['id']}/void",
                {"expected_version": 1, "reason": "合成演示：保留作废工作文件"},
            )
            statement = command(
                "/api/v1/statements",
                {
                    "customer_id": customer["id"],
                    "period_start": "2026-09-20",
                    "period_end": "2026-10-31",
                    "tax_mode": "untaxed_final",
                    "tax_rate": "0",
                    "adjustments": [],
                    "lines": [
                        {
                            "delivery_id": delivery["id"],
                            "order_line_id": order["lines"][0]["id"],
                            "quantity": "1",
                            "unit_price": "2.5000",
                            "reason": "合成演示",
                        }
                    ],
                },
            )
            export = command(
                f"/api/v1/statements/{statement['id']}/exports", {"expected_version": 1}
            )
            generated = client.post(f"/api/v1/statement-exports/{export['id']}/generate")
            generated.raise_for_status()
            if generated.json()["status"] != "ready":
                raise RuntimeError("Synthetic Excel generation failed")
            long_body = {k: v for k, v in body.items() if k != "extraction_id"} | {
                "order_number": "SYN-ARCHIVE-OVERSIZE",
                "lines": [
                    {
                        "item_code": "SYN-LONG",
                        "item_name": "合成超高规格",
                        "specification": "\n".join(
                            f"合成规格第 {i} 行完整保留" for i in range(1, 41)
                        ),
                        "quantity": "5",
                        "unit": "PCS",
                    }
                ],
            }
            long_result = command("/api/v1/orders", long_body)
            long_order = client.get(f"/api/v1/orders/{long_result['order_id']}").json()
            oversize = command(
                "/api/v1/deliveries",
                {
                    "order_id": long_order["id"],
                    "customer_id": customer["id"],
                    "revision_id": long_order["revision_id"],
                    "expected_version": 1,
                    "delivery_date": "2026-10-03",
                    "lines": [{"order_line_id": long_order["lines"][0]["id"], "quantity": "1"}],
                },
            )
        trial.save(
            receipt,
            {
                "customer_id": str(customer["id"]),
                "source_id": original["source_id"],
                "pending_source_id": pending["source_id"],
                "order_id": order["id"],
                "delivery_id": delivery["id"],
                "void_delivery_id": void["id"],
                "oversize_delivery_id": oversize["id"],
                "statement_id": statement["id"],
                "export_id": export["id"],
            },
        )
        print(json.dumps({"state": "seeded", "environment": root.name, "synthetic_only": True}))
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
