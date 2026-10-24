"""Seed only an explicitly owned synthetic layout smoke environment via its API."""

import argparse
import json
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith(
        "factoryflow-business-layout-"
    ):
        parser.error("Only this task's dedicated synthetic layout environment is accepted")
    output = root / "demo-data.json"
    if output.exists():
        parser.error("Synthetic demo already seeded; nothing replaced")
    credentials = json.loads((root / "client.json").read_text())
    port = json.loads((root / "preview.json").read_text(encoding="utf-8-sig"))["port"]
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=20) as client:
        response = client.post("/api/v1/auth/login", json=credentials)
        response.raise_for_status()
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]

        def command(path, body):
            result = client.post(path, json=body, headers={"Idempotency-Key": str(uuid4())})
            if not result.is_success:
                raise RuntimeError(f"Synthetic setup failed: HTTP {result.status_code}")
            return result.json()

        customers = client.get("/api/v1/customers")
        customers.raise_for_status()
        customer = next(
            (c for c in customers.json() if c["full_name"] == "合成客户 · 北辰设备厂"), None
        )
        if customer is None:
            customer = command("/api/v1/customers", {"full_name": "合成客户 · 北辰设备厂"})
        deliveries = {}
        for mode, count in (("normal", 12), ("oversize", 1), ("void", 2)):
            lines = []
            for index in range(count):
                specification = "80 × 40 × 3 mm / 本色阳极氧化 / 边角去毛刺"
                if index == 2:
                    specification += "\n合成验证：安装孔位按图核对，长规格须完整保留。"
                if mode == "oversize":
                    specification = "\n".join(
                        f"合成超长规格第 {n + 1} 行，禁止截断" for n in range(40)
                    )
                lines.append(
                    {
                        "description": "合成零件",
                        "item_code": f"SYN-LAYOUT-{index + 1:02}",
                        "item_name": f"合成安装零件 {index + 1}",
                        "specification": specification,
                        "quantity": "20",
                        "unit": "PCS",
                        "source_unit_price": None,
                        "source_amount": None,
                    }
                )
            confirmed = command(
                "/api/v1/orders",
                {
                    "customer_id": customer["id"],
                    "order_number": f"SYN-LAYOUT-{mode.upper()}",
                    "business_date": "2026-10-11",
                    "currency": "CNY",
                    "lines": lines,
                },
            )
            order = client.get(f"/api/v1/orders/{confirmed['order_id']}").json()
            delivery = command(
                "/api/v1/deliveries",
                {
                    "order_id": order["id"],
                    "customer_id": customer["id"],
                    "revision_id": order["revision_id"],
                    "expected_version": order["version"],
                    "delivery_date": "2026-10-11",
                    "lines": [
                        {"order_line_id": line["id"], "quantity": "12"} for line in order["lines"]
                    ],
                },
            )
            if mode == "void":
                delivery = command(
                    f"/api/v1/deliveries/{delivery['id']}/void",
                    {"expected_version": 1, "reason": "合成验证：作废打印必须显示状态"},
                )
            deliveries[mode] = delivery["id"]
        output.write_text(
            json.dumps({"customer_id": customer["id"], "deliveries": deliveries}, indent=2),
            encoding="utf-8",
        )
    print("Synthetic normal, long-row and void deliveries prepared.")


if __name__ == "__main__":
    main()
