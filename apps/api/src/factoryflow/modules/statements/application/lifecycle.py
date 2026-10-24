"""Human-authorized statement recognition, reservations and fixed settlement versions."""

import base64
import binascii
import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.statements.application.service import StatementService
from factoryflow.modules.statements.domain.draft import (
    calculate,
    canonical,
    period,
    reason,
    source_key,
)
from factoryflow.modules.statements.domain.lifecycle import confirmed_price, quantity, token


class StatementLifecycle:
    def __init__(self, transaction, read_transaction, store):
        self.transaction, self.read_transaction, self.store = transaction, read_transaction, store

    @staticmethod
    def lock(work, actor, identifier, expected=None, *, draft=False):
        initial = work.statements.get(actor, identifier, history=False)
        work.customers.lock(actor, UUID(initial["customer_id"]))
        work.lifecycle.lock_statement(actor, identifier)
        current = work.statements.get(actor, identifier, history=False)
        if expected is not None:
            StatementService.require_version(current, expected)
        if draft and current["status"] != "draft":
            raise BusinessError("STATEMENT_STATE_CONFLICT", 409)
        return current

    @staticmethod
    def touch(work, actor, current, action, why, *, review_adjustments=False):
        if review_adjustments:
            current["adjustments"] = [
                {**a, "status": "needs_review"} for a in current["adjustments"]
            ]
        work.statements.update(actor, current["id"], current, current["status"])
        work.statements.event(actor, current["id"], action, why)

    @staticmethod
    def finish(work, actor, key, action, identifier, result):
        work.journal.audit(actor, "statement." + action, identifier)
        work.journal.finish(actor, "statement." + action, key, result)
        return result

    def view(self, actor, identifier):
        with self.read_transaction() as work:
            work.statements.get(actor, identifier, history=False)
            return {
                kind: work.lifecycle.rows(actor, kind, statement=identifier)
                for kind in ("evidence", "approvals", "allocations", "reviews", "review_transfers")
            } | {"history": work.lifecycle.history(actor, identifier)}

    def listing(self, actor, kind, customer, cursor=None, limit=50):
        with self.read_transaction() as work:
            work.customers.require(actor, customer)
            return work.lifecycle.page(actor, kind, customer, cursor, limit)

    def evidence(self, actor, key, identifier, kind, body):
        actor.require_write()
        person = reason(body["person"], True)
        note = reason(body.get("note", ""), kind == "feedback" and not body.get("content_base64"))
        try:
            occurred = date.fromisoformat(body["occurred_on"])
        except ValueError:
            raise BusinessError("INVALID_INPUT") from None
        content = None
        if body.get("content_base64"):
            try:
                content = base64.b64decode(body["content_base64"], validate=True)
            except ValueError, binascii.Error:
                raise BusinessError("INVALID_INPUT") from None
            signatures = {
                "image/png": b"\x89PNG\r\n\x1a\n",
                "image/jpeg": b"\xff\xd8\xff",
                "application/pdf": b"%PDF-",
            }
            if body.get("media_type") not in signatures or not content.startswith(
                signatures[body["media_type"]]
            ):
                raise BusinessError("FILE_TYPE_UNSUPPORTED")
            if not 0 < len(content) <= 10 * 1024 * 1024:
                raise BusinessError("FILE_TOO_LARGE", 413)
            name = body.get("filename", "").strip()
            if not name or len(name) > 180 or any(ord(c) < 32 for c in name):
                raise BusinessError("INVALID_INPUT")
        elif body.get("filename") or body.get("media_type"):
            raise BusinessError("INVALID_INPUT")
        payload = {k: v for k, v in body.items() if k != "content_base64"}
        payload.update(
            id=str(identifier), sha256=hashlib.sha256(content).hexdigest() if content else None
        )
        with self.transaction() as work:
            prior = work.journal.claim(actor, "statement." + kind, key, payload)
            if prior is not None:
                return prior
            current = self.lock(work, actor, identifier, body.get("expected_version"))
            if kind == "sent":
                record = work.exports.get(actor, body["export_id"])
                if (
                    record["statement_id"] != str(identifier)
                    or not record["current"]
                    or record["status"] != "ready"
                ):
                    raise BusinessError("STATEMENT_EXPORT_STALE", 409)
            digest = None
            if content:
                digest = self.store.put(
                    json.dumps(
                        {
                            "format": "statement-feedback-v1",
                            "sha256": payload["sha256"],
                            "base64": body["content_base64"],
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                )
            result = work.lifecycle.add(
                actor,
                "evidence",
                {
                    "statement_id": identifier,
                    "customer_id": current["customer_id"],
                    "kind": kind,
                    "export_id": body.get("export_id"),
                    "statement_version": current["version"],
                    "person": person,
                    "occurred_on": occurred,
                    "note": note,
                    "object_hash": digest,
                    "media_type": body.get("media_type"),
                    "filename": body.get("filename"),
                },
            )
            return self.finish(work, actor, key, kind, identifier, result)

    def download_evidence(self, actor, identifier):
        with self.read_transaction() as work:
            row = work.lifecycle.get(actor, "evidence", identifier)
        if not row["object_hash"]:
            raise BusinessError("STATEMENT_EVIDENCE_FILE_MISSING", 404)
        envelope = json.loads(self.store.read(row["object_hash"]))
        content = base64.b64decode(envelope["base64"], validate=True)
        if hashlib.sha256(content).hexdigest() != envelope["sha256"]:
            raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
        return row, content

    @staticmethod
    def consume(work, actor, current, body):
        line = next(
            (
                x
                for x in current["lines"]
                if source_key(x) == source_key(body) and x["status"] == "included"
            ),
            None,
        )
        if line is None:
            raise BusinessError("STATEMENT_SOURCE_INVALID", 409)
        q = quantity(body["quantity"], line["source"])
        if q > Decimal(line["quantity"]):
            raise BusinessError("STATEMENT_QUANTITY_EXCEEDED", 409)
        original = {**line}
        line["quantity"] = canonical(Decimal(line["quantity"]) - q)
        line["status"] = "included" if Decimal(line["quantity"]) else "released"
        line["reason"] = body["reason"]
        work.statements.write_lines(actor, current["id"], current["customer_id"], current["lines"])
        return original, q

    def command(self, actor, key, identifier, action, body):
        actor.require_write()
        body = {**body, "reason": reason(body.get("reason"), True)}
        with self.transaction() as work:
            prior = work.journal.claim(
                actor, "statement." + action, key, {"id": str(identifier), **body}
            )
            if prior is not None:
                return prior
            current = self.lock(
                work,
                actor,
                identifier,
                body["expected_version"],
                draft=action != "correct_settlement",
            )
            if action == "approve":
                result = self.approve(work, actor, current, body)
            elif action == "review":
                result = self.review(work, actor, current, body)
            elif action == "claim_review":
                result = self.claim_review(work, actor, current, body)
            elif action == "reserve":
                result = self.reserve(work, actor, current, body)
            elif action == "release":
                result = self.release(work, actor, current, body)
            elif action == "settle":
                result = self.settle(work, actor, current, body)
            elif action == "correct_settlement":
                result = self.correct_settlement(work, actor, current, body)
            else:
                raise ValueError("unsupported statement command")
            return self.finish(work, actor, key, action, identifier, result)

    def approve(self, work, actor, current, body):
        sent = work.lifecycle.get(actor, "evidence", body["sent_id"])
        feedback = work.lifecycle.get(actor, "evidence", body["feedback_id"])
        if (
            any(e["statement_id"] != current["id"] for e in (sent, feedback))
            or sent["kind"] != "sent"
            or feedback["kind"] != "feedback"
        ):
            raise BusinessError("STATEMENT_EVIDENCE_MISMATCH", 409)
        sent_record = work.exports.get(actor, sent["export_id"])
        original = sent_record["snapshot"]["statement"]
        sent_line = next(
            (
                x
                for x in original["lines"]
                if source_key(x) == source_key(body) and x["status"] == "included"
            ),
            None,
        )
        if sent_line is None or quantity(body["quantity"], sent_line["source"]) > Decimal(
            sent_line["quantity"]
        ):
            raise BusinessError("STATEMENT_EVIDENCE_MISMATCH", 409)
        current_line = next(
            (
                x
                for x in current["lines"]
                if source_key(x) == source_key(body) and x["status"] == "included"
            ),
            None,
        )
        if current_line is None or current_line.get(
            "external_document_number", ""
        ) != sent_line.get("external_document_number", ""):
            raise BusinessError("STATEMENT_EXTERNAL_NUMBER_MISMATCH", 409)
        p = confirmed_price(body["unit_price"])
        start, end = period(body["target_start"], body["target_end"])
        source, q = self.consume(work, actor, current, body)
        if end < source["source"]["delivery_date"]:
            raise BusinessError("STATEMENT_PERIOD_INVALID")
        result = work.lifecycle.add(
            actor,
            "approvals",
            {
                "statement_id": current["id"],
                "customer_id": current["customer_id"],
                "delivery_id": source["delivery_id"],
                "order_line_id": source["order_line_id"],
                "external_document_number": sent_line.get("external_document_number", ""),
                "sent_id": sent["id"],
                "feedback_id": feedback["id"],
                "quantity": q,
                "unit_price": p,
                "target_start": start,
                "target_end": end,
                "reason": body["reason"],
                "source": source["source"],
                "review_quantity": min(
                    q, work.lifecycle.review_claimed(actor, current["id"], source)
                ),
            },
        )
        work.lifecycle.approve_transfers(
            actor, current["id"], source, q, body["reason"], result["id"]
        )
        self.touch(work, actor, current, "approve", body["reason"])
        return result

    def review(self, work, actor, current, body):
        transfers = [
            x
            for x in work.lifecycle.rows(actor, "review_transfers", statement=current["id"])
            if x["status"] == "claimed"
            and source_key(work.lifecycle.get(actor, "reviews", x["review_id"])) == source_key(body)
        ]
        source, q = self.consume(work, actor, current, body)
        remaining = Decimal(source["quantity"]) - q
        freed = max(
            Decimal(0), sum((Decimal(x["quantity"]) for x in transfers), Decimal(0)) - remaining
        )
        work.lifecycle.reconcile_transfers(actor, current["id"], current["lines"], body["reason"])
        if q > freed:
            result = work.lifecycle.add(
                actor,
                "reviews",
                {
                    "statement_id": current["id"],
                    "customer_id": current["customer_id"],
                    "delivery_id": source["delivery_id"],
                    "order_line_id": source["order_line_id"],
                    "quantity": q - freed,
                    "reason": body["reason"],
                    "external_document_number": source.get("external_document_number", ""),
                    "source": source["source"],
                },
            )
        else:
            result = work.lifecycle.get(actor, "reviews", transfers[0]["review_id"])
        self.touch(work, actor, current, "review", body["reason"])
        return result

    def claim_review(self, work, actor, current, body):
        review = work.lifecycle.get(actor, "reviews", body["review_id"])
        StatementService.require_version(review, body["review_version"])
        if (
            review["customer_id"] != current["customer_id"]
            or review["source"]["delivery_date"] > current["period_end"]
        ):
            raise BusinessError("STATEMENT_SOURCE_INVALID", 409)
        work.deliveries.lock_sources(actor, [source_key(review)])
        q = quantity(body["quantity"], review["source"])
        if q > Decimal(review["remaining_quantity"]):
            raise BusinessError("STATEMENT_QUANTITY_EXCEEDED", 409)
        p = canonical(confirmed_price(body["unit_price"]))
        existing = next((x for x in current["lines"] if source_key(x) == source_key(review)), None)
        if (
            existing
            and existing["status"] == "included"
            and existing.get("external_document_number", "")
            != review.get("external_document_number", "")
        ):
            raise BusinessError("STATEMENT_EXTERNAL_NUMBER_MISMATCH", 409)
        if existing and existing["status"] == "included":
            if existing["unit_price"] != p:
                raise BusinessError("STATEMENT_PRICE_CONFLICT", 409)
            existing["quantity"] = canonical(Decimal(existing["quantity"]) + q)
        else:
            line = {k: review[k] for k in ("delivery_id", "order_line_id", "source")}
            line["external_document_number"] = review.get("external_document_number", "")
            line.update(
                quantity=canonical(q), unit_price=p, status="included", reason=body["reason"]
            )
            if existing:
                current["lines"].remove(existing)
            current["lines"].append(line)
        work.statements.write_lines(actor, current["id"], current["customer_id"], current["lines"])
        work.lifecycle.add(
            actor,
            "review_transfers",
            {
                "statement_id": current["id"],
                "customer_id": current["customer_id"],
                "review_id": review["id"],
                "quantity": q,
                "status": "claimed",
                "reason": body["reason"],
            },
        )
        self.touch(work, actor, current, "claim_review", body["reason"])
        return work.statements.get(actor, current["id"])

    def reserve(self, work, actor, current, body):
        approval = work.lifecycle.get(actor, "approvals", body["approval_id"])
        StatementService.require_version(approval, body["approval_version"])
        if approval["customer_id"] != current["customer_id"] or (
            approval["target_start"],
            approval["target_end"],
        ) != (current["period_start"], current["period_end"]):
            raise BusinessError("STATEMENT_TARGET_MISMATCH", 409)
        q = quantity(body["quantity"], approval["source"])
        if q > Decimal(approval["available_quantity"]):
            raise BusinessError("STATEMENT_QUANTITY_EXCEEDED", 409)
        result = work.lifecycle.add(
            actor,
            "allocations",
            {
                "statement_id": current["id"],
                "customer_id": current["customer_id"],
                "approval_id": approval["id"],
                "quantity": q,
                "unit_price": Decimal(approval["unit_price"]),
                "status": "reserved",
                "reason": body["reason"],
            },
        )
        self.touch(work, actor, current, "reserve", body["reason"])
        return result

    def release(self, work, actor, current, body):
        row = work.lifecycle.get(actor, "allocations", body["allocation_id"])
        StatementService.require_version(row, body["allocation_version"])
        if row["statement_id"] != current["id"] or row["status"] != "reserved":
            raise BusinessError("STATEMENT_STATE_CONFLICT", 409)
        result = work.lifecycle.change(
            actor, "allocations", row["id"], {"status": "released", "reason": body["reason"]}
        )
        self.touch(work, actor, current, "release", body["reason"], review_adjustments=True)
        return result

    @staticmethod
    def settlement_preview(work, actor, current, body):
        blockers = []
        if current["status"] != "draft":
            blockers.append("STATEMENT_STATE_CONFLICT")
        if any(x["status"] == "included" for x in current["lines"]):
            blockers.append("STATEMENT_UNAPPROVED_QUANTITY")
        if not body["fees_confirmed"]:
            blockers.append("STATEMENT_FEES_UNKNOWN")
        if body["reconfirmation"] == "unknown":
            blockers.append("STATEMENT_RECONFIRMATION_UNKNOWN")
        if body["reconfirmation"] == "received" and not any(
            e["kind"] == "feedback"
            for e in work.lifecycle.rows(actor, "evidence", statement=current["id"])
        ):
            blockers.append("STATEMENT_RECONFIRMATION_EVIDENCE_REQUIRED")
        if any(x["status"] == "needs_review" for x in current["adjustments"]):
            blockers.append("STATEMENT_ADJUSTMENTS_REVIEW")
        total = current["calculation"]["total"]
        if total is None or Decimal(total) < 0:
            blockers.append("STATEMENT_AMOUNT_UNCONFIRMED")
        allocations = work.lifecycle.rows(actor, "allocations", statement=current["id"])
        approvals = work.lifecycle.rows(actor, "approvals", statement=current["id"])
        if not any(x["status"] == "reserved" for x in allocations) and not approvals:
            blockers.append("STATEMENT_EMPTY_SETTLEMENT")
        inputs = {k: v for k, v in body.items() if k != "preview_token"}
        return {
            "token": token(
                {
                    "statement": current,
                    "allocations": allocations,
                    "approvals": approvals,
                    "input": inputs,
                }
            ),
            "blockers": blockers,
            "calculation": current["calculation"],
            "affected_allocations": [x for x in allocations if x["status"] == "reserved"],
        }

    def preview(self, actor, identifier, body):
        body = {**body, "reason": reason(body["reason"], True)}
        with self.read_transaction() as work:
            current = work.statements.get(actor, identifier, history=False)
            StatementService.require_version(current, body["expected_version"])
            return self.settlement_preview(work, actor, current, body)

    def settle(self, work, actor, current, body):
        preview = self.settlement_preview(work, actor, current, body)
        if preview["blockers"]:
            raise BusinessError(preview["blockers"][0], 409)
        if preview["token"] != body["preview_token"]:
            raise BusinessError("STATEMENT_PREVIEW_STALE", 409)
        for row in preview["affected_allocations"]:
            work.lifecycle.change(
                actor,
                "allocations",
                row["id"],
                {
                    "status": "settled",
                    "settlement_version": current["version"] + 1,
                    "reason": body["reason"],
                },
            )
        work.lifecycle.confirmed_header(
            actor, current["id"], body["fees_confirmed"], body["reconfirmation"]
        )
        work.statements.event(actor, current["id"], "settle", body["reason"])
        return work.statements.get(actor, current["id"])

    @staticmethod
    def approval_impact(work, actor, approval, body):
        rows = work.lifecycle.rows(actor, "allocations", approval=approval["id"])
        affected = [r for r in rows if r["status"] == "reserved"]
        inputs = {k: v for k, v in body.items() if k != "preview_token"}
        return {
            "token": token({"approval": approval, "allocations": rows, "input": inputs}),
            "affected_allocations": affected,
            "blockers": [],
            "calculation": None,
        }

    def change_approval(self, actor, key, identifier, action, body, *, preview=False):
        if not preview:
            actor.require_write()
        body = {**body, "reason": reason(body["reason"], True)}
        with self.read_transaction() if preview else self.transaction() as work:
            if not preview:
                prior = work.journal.claim(
                    actor, "statement." + action, key, {"id": str(identifier), **body}
                )
                if prior is not None:
                    return prior
            approval = work.lifecycle.get(actor, "approvals", identifier)
            if not preview:
                work.customers.lock(actor, UUID(approval["customer_id"]))
                approval = work.lifecycle.get(actor, "approvals", identifier)
            StatementService.require_version(approval, body["expected_version"])
            impact = self.approval_impact(work, actor, approval, body)
            settled = Decimal(approval["settled_quantity"])
            changes = {"reason": body["reason"]}
            if action == "defer":
                start, end = period(body["target_start"], body["target_end"])
                if (
                    end < approval["source"]["delivery_date"]
                    or Decimal(approval["quantity"]) == settled
                ):
                    impact["blockers"].append("STATEMENT_NO_PENDING_QUANTITY")
                changes.update(target_start=start, target_end=end)
            else:
                q = quantity(body["quantity"], approval["source"], allow_zero=True)
                p = confirmed_price(body["unit_price"])
                if settled:
                    impact["blockers"].append("STATEMENT_FORMAL_CORRECTION_REQUIRED")
                if q > Decimal(approval["quantity"]):
                    impact["blockers"].append("STATEMENT_REAPPROVAL_REQUIRED")
                if body["disposition"] != "review":
                    impact["blockers"].append("STATEMENT_DISPOSITION_REQUIRED")
                evidence = work.lifecycle.get(actor, "evidence", body["evidence_id"])
                if (
                    evidence["customer_id"] != approval["customer_id"]
                    or evidence["kind"] != "feedback"
                ):
                    impact["blockers"].append("STATEMENT_EVIDENCE_MISMATCH")
                changes.update(quantity=q, unit_price=p)
            if preview:
                return impact
            if impact["blockers"]:
                raise BusinessError(impact["blockers"][0], 409)
            if body["preview_token"] != impact["token"]:
                raise BusinessError("STATEMENT_PREVIEW_STALE", 409)
            self.cancel_reservations(work, actor, impact["affected_allocations"], body["reason"])
            if action == "correct_approval":
                changes["correction"] = self.correction_record(actor, approval, body)
            result = work.lifecycle.change(actor, "approvals", identifier, changes)
            if action == "correct_approval" and Decimal(approval["quantity"]) > changes["quantity"]:
                self.add_review(
                    work,
                    actor,
                    approval,
                    Decimal(approval["quantity"]) - changes["quantity"],
                    body["reason"],
                )
            return self.finish(work, actor, key, action, identifier, result)

    @staticmethod
    def add_review(work, actor, approval, q, why):
        return work.lifecycle.add(
            actor,
            "reviews",
            {
                k: approval[k]
                for k in ("statement_id", "customer_id", "delivery_id", "order_line_id", "source")
            }
            | {
                "quantity": q,
                "reason": why,
                "external_document_number": approval.get("external_document_number", ""),
            },
        )

    def cancel_reservations(self, work, actor, rows, why):
        touched = set()
        for row in rows:
            work.lifecycle.change(
                actor, "allocations", row["id"], {"status": "released", "reason": why}
            )
            touched.add(row["statement_id"])
        for identifier in sorted(touched):
            current = self.lock(work, actor, identifier, draft=True)
            self.touch(work, actor, current, "cancel_reservations", why, review_adjustments=True)

    def correction_preview(self, actor, identifier, body):
        body = {**body, "reason": reason(body["reason"], True)}
        with self.read_transaction() as work:
            current = work.statements.get(actor, identifier, history=False)
            StatementService.require_version(current, body["expected_version"])
            return self.formal_impact(work, actor, current, body)[0]

    def formal_impact(self, work, actor, current, body):
        row = work.lifecycle.get(actor, "allocations", body["allocation_id"])
        approval = work.lifecycle.get(actor, "approvals", row["approval_id"])
        evidence = work.lifecycle.get(actor, "evidence", body["evidence_id"])
        rows = work.lifecycle.rows(actor, "allocations", approval=approval["id"])
        q = quantity(body["quantity"], approval["source"], allow_zero=True)
        p = confirmed_price(body["unit_price"])
        blockers = []
        if (
            current["status"] != "confirmed"
            or row["statement_id"] != current["id"]
            or row["status"] != "settled"
        ):
            blockers.append("STATEMENT_STATE_CONFLICT")
        if evidence["customer_id"] != current["customer_id"] or evidence["kind"] != "feedback":
            blockers.append("STATEMENT_EVIDENCE_MISMATCH")
        if (
            body["cause"] not in ("entry_error", "customer_change")
            or not body["no_downstream_effects"]
        ):
            blockers.append("STATEMENT_DOWNSTREAM_EFFECTS")
        # A later formal use of this approval requires a separately designed reversal.
        if any(x["status"] == "settled" and x["id"] != row["id"] for x in rows):
            blockers.append("STATEMENT_DOWNSTREAM_EFFECTS")
        if q > Decimal(row["quantity"]):
            blockers.append("STATEMENT_REAPPROVAL_REQUIRED")
        if any(
            x.get("delivery_id") == approval["delivery_id"]
            and x.get("order_line_id") == approval["order_line_id"]
            for x in current["adjustments"]
        ):
            blockers.append("STATEMENT_RELATED_FEES_REVIEW")
        affected = [x for x in rows if x["status"] == "reserved"]
        inputs = {k: v for k, v in body.items() if k != "preview_token"}
        revised_lines = [
            {**line, "quantity": canonical(q), "unit_price": canonical(p)}
            if line["allocation_id"] == row["id"]
            else line
            for line in current["settlement_lines"]
        ]
        calculation = calculate(
            current["lines"] + revised_lines,
            current["tax_mode"],
            current["tax_rate"],
            current["adjustments"],
        )
        if calculation["total"] is None or Decimal(calculation["total"]) < 0:
            blockers.append("STATEMENT_AMOUNT_UNCONFIRMED")
        preview = {
            "token": token(
                {"statement": current, "approval": approval, "rows": rows, "input": inputs}
            ),
            "blockers": blockers,
            "affected_allocations": affected,
            "calculation": calculation,
        }
        return preview, row, approval, q, p

    def correct_settlement(self, work, actor, current, body):
        preview, row, approval, q, p = self.formal_impact(work, actor, current, body)
        if preview["blockers"]:
            raise BusinessError(preview["blockers"][0], 409)
        if preview["token"] != body["preview_token"]:
            raise BusinessError("STATEMENT_PREVIEW_STALE", 409)
        self.cancel_reservations(work, actor, preview["affected_allocations"], body["reason"])
        version = current["version"] + 1
        work.lifecycle.change(
            actor,
            "allocations",
            row["id"],
            {"status": "superseded", "superseded_version": version, "reason": body["reason"]},
        )
        difference = Decimal(row["quantity"]) - q
        correction = self.correction_record(actor, row, body)
        changes = {"unit_price": p, "reason": body["reason"], "correction": correction}
        if body["disposition"] == "review":
            changes["quantity"] = Decimal(approval["quantity"]) - difference
        work.lifecycle.change(actor, "approvals", approval["id"], changes)
        if difference and body["disposition"] == "review":
            self.add_review(work, actor, approval, difference, body["reason"])
        if q:
            work.lifecycle.add(
                actor,
                "allocations",
                {
                    "statement_id": current["id"],
                    "customer_id": current["customer_id"],
                    "approval_id": approval["id"],
                    "quantity": q,
                    "unit_price": p,
                    "status": "settled",
                    "settlement_version": version,
                    "reason": body["reason"],
                },
            )
        work.statements.update(actor, current["id"], current, "confirmed")
        work.statements.event(
            actor, current["id"], "correct_settlement", body["reason"], correction=correction
        )
        return work.statements.get(actor, current["id"])

    @staticmethod
    def correction_record(actor, original, body):
        return {
            "evidence_id": body["evidence_id"],
            "cause": body["cause"],
            "disposition": body["disposition"],
            "previous_quantity": original["quantity"],
            "quantity": canonical(quantity(body["quantity"], allow_zero=True)),
            "previous_unit_price": original["unit_price"],
            "unit_price": canonical(confirmed_price(body["unit_price"])),
            "reason": body["reason"],
            "actor_id": str(actor.user_id),
            "recorded_at": datetime.now(UTC).isoformat(),
            "no_downstream_effects": body.get("no_downstream_effects", True),
        }
