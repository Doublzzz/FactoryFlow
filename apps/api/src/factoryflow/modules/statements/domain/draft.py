"""Exact draft inputs and calculations; no storage or framework dependencies."""

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from uuid import UUID

from factoryflow.kernel.contracts import BusinessError
from factoryflow.kernel.quantity import confirm_quantity

MAX_PRICE = Decimal("999999999999.9999")
MAX_AMOUNT = Decimal("999999999999999999999999999999.99")
MODES = {"included", "untaxed_final", "add_tax"}


def decimal_value(value, places, maximum, *, signed=False):
    pattern = (r"-?" if signed else "") + rf"[0-9]+(?:\.[0-9]{{1,{places}}})?"
    if not isinstance(value, str) or len(value) > 64 or not re.fullmatch(pattern, value):
        raise BusinessError("STATEMENT_DECIMAL_INVALID")
    number = Decimal(value)
    if number.copy_abs() > maximum:
        raise BusinessError("STATEMENT_AMOUNT_OUT_OF_RANGE")
    return number


def canonical(number):
    value = format(number, "f")
    return (value.rstrip("0").rstrip(".") if "." in value else value) if number else "0"


def price(value):
    return None if value is None else canonical(decimal_value(value, 4, MAX_PRICE))


def reason(value, required=False):
    if not isinstance(value, str) or len(value) > 500 or (required and not value.strip()):
        raise BusinessError("STATEMENT_REASON_REQUIRED")
    return value.strip()


def external_document_number(value):
    if (
        not isinstance(value, str)
        or len(value) > 120
        or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value)
    ):
        raise BusinessError("STATEMENT_EXTERNAL_NUMBER_INVALID")
    return value.strip()


def period(start, end):
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError, TypeError:
        raise BusinessError("STATEMENT_PERIOD_INVALID") from None
    if first > last:
        raise BusinessError("STATEMENT_PERIOD_INVALID")
    return first.isoformat(), last.isoformat()


def source_key(line):
    try:
        return str(UUID(str(line["delivery_id"]))), str(UUID(str(line["order_line_id"])))
    except KeyError, ValueError, TypeError:
        raise BusinessError("STATEMENT_SOURCE_INVALID") from None


def prepare_draft(payload):
    currency = payload.get("currency", "CNY")
    if currency not in ("CNY", "USD"):
        raise BusinessError("CURRENCY_REQUIRED", field="currency")
    start, end = period(payload.get("period_start"), payload.get("period_end"))
    try:
        customer = str(UUID(str(payload.get("customer_id"))))
    except ValueError:
        raise BusinessError("INVALID_INPUT") from None
    mode = payload.get("tax_mode")
    if mode not in MODES:
        raise BusinessError("STATEMENT_TAX_MODE_REQUIRED")
    rate = canonical(decimal_value(payload.get("tax_rate"), 4, Decimal(100)))
    raw = payload.get("lines")
    if not isinstance(raw, list) or not 0 <= len(raw) <= 200:
        raise BusinessError("STATEMENT_LINES_REQUIRED")
    lines, seen = [], set()
    for line in raw:
        key = source_key(line)
        if key in seen:
            raise BusinessError("STATEMENT_DUPLICATE_SOURCE")
        seen.add(key)
        quantity = confirm_quantity(line.get("quantity"), None).canonical
        item = {
            "delivery_id": key[0],
            "order_line_id": key[1],
            "quantity": quantity,
            "external_document_number": external_document_number(
                line.get("external_document_number", "")
            ),
            "reason": reason(line.get("reason", ""), quantity == "0"),
        }
        # Preserve pre-field command fingerprints for omitted or empty optional metadata.
        if not item["external_document_number"]:
            item.pop("external_document_number")
        if "unit_price" in line:
            item["unit_price"] = price(line["unit_price"])
        lines.append(item)
    adjustments = []
    for adjustment in payload.get("adjustments", []):
        if len(adjustments) >= 100 or adjustment.get("stage") not in {"before_tax", "after_tax"}:
            raise BusinessError("STATEMENT_ADJUSTMENT_INVALID")
        if not isinstance(adjustment.get("kind"), str) or not 1 <= len(adjustment["kind"]) <= 80:
            raise BusinessError("STATEMENT_ADJUSTMENT_INVALID")
        amount = decimal_value(adjustment.get("amount"), 2, MAX_AMOUNT, signed=True)
        item = {
            "stage": adjustment["stage"],
            "kind": adjustment["kind"],
            "amount": canonical(amount),
            "reason": reason(adjustment.get("reason"), True),
            "status": "active",
        }
        if adjustment.get("delivery_id") or adjustment.get("order_line_id"):
            key = source_key(adjustment)
            item.update(delivery_id=key[0], order_line_id=key[1])
        adjustments.append(item)
    return {
        # Omitted/explicit CNY retains the pre-currency command fingerprint.
        **({"currency": currency} if currency != "CNY" else {}),
        "customer_id": customer,
        "period_start": start,
        "period_end": end,
        "tax_mode": mode,
        "tax_rate": rate,
        "lines": sorted(lines, key=source_key),
        "adjustments": adjustments,
        "reason": reason(payload.get("reason", "")),
    }


def calculate(lines, tax_mode, tax_rate, adjustments):
    if tax_mode not in MODES:
        raise BusinessError("STATEMENT_TAX_MODE_REQUIRED")
    rate = decimal_value(tax_rate, 4, Decimal(100))
    with localcontext() as context:
        context.prec = 64

        def money(number):
            rounded = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if abs(rounded) > MAX_AMOUNT:
                raise BusinessError("STATEMENT_AMOUNT_OUT_OF_RANGE")
            return format(rounded if rounded else Decimal(0), ".2f")

        amounts, subtotal, warnings = [], Decimal(0), set()
        for line in lines:
            if line["status"] != "included":
                amounts.append(None)
                continue
            value = price(line["unit_price"])
            if value is None:
                warnings.add("PRICE_REQUIRED")
                amounts.append(None)
            else:
                amount = money(Decimal(line["quantity"]) * Decimal(value))
                amounts.append(amount)
                subtotal += Decimal(amount)
        before, after = Decimal(0), Decimal(0)
        for adjustment in adjustments:
            if adjustment["status"] != "active":
                warnings.add("ADJUSTMENT_REVIEW_REQUIRED")
                continue
            value = decimal_value(adjustment["amount"], 2, MAX_AMOUNT, signed=True)
            if adjustment["stage"] == "before_tax":
                before += value
            else:
                after += value
        base = subtotal + before
        tax = Decimal(money(base * rate / 100)) if tax_mode == "add_tax" else Decimal(0)
        total = base + tax + after
        if total < 0:
            warnings.add("NEGATIVE_TOTAL_REVIEW_REQUIRED")
        incomplete = "PRICE_REQUIRED" in warnings or "ADJUSTMENT_REVIEW_REQUIRED" in warnings
        return {
            "line_amounts": amounts,
            "priced_subtotal": money(subtotal),
            "tax_base": None if incomplete else money(base),
            "tax_amount": None if incomplete else money(tax),
            "total": None if incomplete else money(total),
            "warnings": sorted(warnings),
        }
