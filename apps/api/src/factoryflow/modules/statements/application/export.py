"""Snapshot, render outside transactions, then register first successful bytes."""

import base64
import hashlib
import json
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.statements.application.templates import template_bytes
from factoryflow.modules.statements.domain.customer_templates import (
    CUSTOM_TEMPLATE,
    require_coverage,
)
from factoryflow.modules.statements.domain.templates import DEFAULT_TEMPLATE, TEMPLATES


class StatementExports:
    def __init__(self, transaction, read_transaction, store, render):
        self.transaction, self.read_transaction = transaction, read_transaction
        self.store, self.render = store, render

    @staticmethod
    def present(record):
        result = {
            key: record[key]
            for key in (
                "id",
                "statement_id",
                "statement_version",
                "statement_status",
                "template_id",
                "template_version",
                "status",
                "current",
                "file_hash",
                "error_code",
                "created_at",
            )
        }
        template = record["snapshot"].get("customer_template")
        result["customer_template_id"] = template["id"] if template else None
        result["template_name"] = template["name"] if template else TEMPLATES[record["template_id"]]
        result["locale"] = "source" if template else record["snapshot"].get("locale", "zh-CN")
        return result

    def create(
        self,
        actor,
        key,
        statement_id,
        expected,
        template_id=None,
        customer_template_id=None,
        locale="zh-CN",
    ):
        actor.require_write()
        if locale not in ("zh-CN", "en"):
            raise BusinessError("UNSUPPORTED_LOCALE", 422, field="locale")
        payload = {
            "statement_id": str(statement_id),
            "expected_version": expected,
            "template_id": template_id,
        }
        if customer_template_id is not None:
            payload["customer_template_id"] = str(customer_template_id)
        # Omitted and explicit Chinese retain the pre-localization command fingerprint.
        if locale != "zh-CN":
            payload["locale"] = locale
        with self.transaction() as work:
            prior = work.journal.claim(actor, "statement.export", key, payload)
            if prior is not None:
                # Replay identity, but return live validity/status, never a stale 'current' flag.
                return self.present(work.exports.get(actor, prior["id"]))
            initial = work.statements.get(actor, statement_id, history=False)
            work.customers.lock(actor, UUID(initial["customer_id"]))
            statement = work.statements.get(actor, statement_id, history=False)
            if type(expected) is not int or statement["version"] != expected:
                raise BusinessError("VERSION_CONFLICT", 409)
            if statement["status"] not in {"draft", "confirmed"}:
                raise BusinessError("STATEMENT_STATE_CONFLICT", 409)
            warnings = set(statement["calculation"]["warnings"]) - {"PRICE_REQUIRED"}
            lines = statement["lines"] + statement.get("settlement_lines", [])
            if warnings or (
                statement["status"] == "draft" and not any(i["status"] == "included" for i in lines)
            ):
                raise BusinessError("STATEMENT_EXPORT_REVIEW_REQUIRED", 409)
            settings = work.statements.settings(actor, statement["customer_id"])
            if template_id is None:
                if customer_template_id is not None:
                    raise BusinessError("STATEMENT_TEMPLATE_INVALID")
                template_id = (settings or {}).get("template_id", DEFAULT_TEMPLATE)
                customer_template_id = (settings or {}).get("customer_template_id")
            if template_id not in {*TEMPLATES, CUSTOM_TEMPLATE} or (
                (template_id == CUSTOM_TEMPLATE) != bool(customer_template_id)
            ):
                raise BusinessError("STATEMENT_TEMPLATE_INVALID")
            template = None
            if customer_template_id is not None:
                record = work.templates.get(actor, statement["customer_id"], customer_template_id)
                require_coverage(record["mapping"], statement)
                template = {
                    k: record[k]
                    for k in ("id", "name", "version", "object_hash", "file_hash", "mapping")
                }
            identifier = uuid7()
            snapshot = {
                "id": str(identifier),
                "template_id": template_id,
                "template_version": template["version"] if template else 1,
                "calculation_version": 1,
                "locale": locale,
                "statement": statement,
            }
            if template is not None:
                snapshot["customer_template"] = template
            work.exports.create(actor, snapshot)
            result = self.present(work.exports.get(actor, identifier))
            work.journal.audit(actor, "statement.export", identifier)
            work.journal.finish(actor, "statement.export", key, result)
            return result

    def generate(self, actor, identifier):
        actor.require_write()
        with self.read_transaction() as work:
            record = work.exports.get(actor, identifier)
        if record["status"] == "ready":
            return self.present(record)
        digest, file_hash = None, None
        error_code = "EXPORT_RENDER_FAILED"
        try:
            snapshot = {**record["snapshot"], "current": record["current"]}
            if snapshot["template_id"] == CUSTOM_TEMPLATE:
                content = self.render(
                    snapshot, template_bytes(self.store, snapshot["customer_template"])
                )
            else:
                content = self.render(snapshot)
            file_hash = hashlib.sha256(content).hexdigest()
            envelope = json.dumps(
                {
                    "type": "statement-xlsx-v1",
                    "sha256": file_hash,
                    "content": base64.b64encode(content).decode("ascii"),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            digest = self.store.put(envelope)
        except BusinessError as failure:
            if failure.code == "STATEMENT_TEMPLATE_TEXT_LIMIT":
                error_code = failure.code
            digest, file_hash = None, None
        except Exception:
            # Renderer/storage failures are persisted file outcomes, not business rollbacks.
            # Third-party renderers also raise non-ValueError exceptions. Never log source data.
            digest, file_hash = None, None
        with self.transaction() as work:
            work.customers.lock(actor, UUID(record["customer_id"]))
            current = work.exports.get(actor, identifier)
            if current["status"] != "ready":
                work.exports.finish(actor, identifier, digest, file_hash, error_code)
                work.journal.audit(
                    actor,
                    "statement.export.ready" if digest else "statement.export.failed",
                    identifier,
                )
            return self.present(work.exports.get(actor, identifier))

    def listing(self, actor, statement_id, cursor=None, limit=50):
        with self.read_transaction() as work:
            work.statements.get(actor, statement_id, history=False)
            page = work.exports.listing(actor, statement_id, cursor, limit)
            return {**page, "items": [self.present(i) for i in page["items"]]}

    def download(self, actor, identifier, historical=False):
        with self.read_transaction() as work:
            record = work.exports.get(actor, identifier)
        if record["status"] != "ready":
            raise BusinessError("STATEMENT_EXPORT_NOT_READY", 409)
        if not record["current"] and not historical:
            raise BusinessError("STATEMENT_EXPORT_STALE", 409)
        try:
            envelope = json.loads(self.store.read(record["object_hash"]))
            content = base64.b64decode(envelope["content"], validate=True)
            if (
                envelope["type"] != "statement-xlsx-v1"
                or hashlib.sha256(content).hexdigest() != record["file_hash"]
            ):
                raise ValueError("invalid export content")
        except KeyError, ValueError, TypeError:
            raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503) from None
        return content, self.present(record)
