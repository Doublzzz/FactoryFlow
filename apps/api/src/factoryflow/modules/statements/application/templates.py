"""Human-confirmed mappings; immutable file objects and transactional template records."""

import base64
import hashlib
import json
from uuid import uuid7

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.statements.domain.customer_templates import require_coverage


def template_bytes(store, record):
    try:
        envelope = json.loads(store.read(record["object_hash"]))
        content = base64.b64decode(envelope["content"], validate=True)
        if (
            envelope["type"] != "customer-statement-template-v1"
            or envelope["sha256"] != record["file_hash"]
            or hashlib.sha256(content).hexdigest() != record["file_hash"]
        ):
            raise ValueError("Template integrity mismatch")
        return content
    except KeyError, ValueError, TypeError:
        raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503) from None


class StatementTemplates:
    def __init__(
        self, transaction, read_transaction, store, inspect, validate, render, preview_grid
    ):
        self.transaction, self.read_transaction, self.store = transaction, read_transaction, store
        self.inspect_file, self.validate, self.render, self.preview_grid = (
            inspect,
            validate,
            render,
            preview_grid,
        )

    @staticmethod
    def present(record):
        return {
            k: record[k]
            for k in ("id", "customer_id", "name", "version", "file_hash", "mapping", "created_at")
        }

    def decode(self, actor, customer_id, body):
        actor.require_write()
        with self.read_transaction() as work:
            work.customers.require(actor, customer_id)
        if not body["filename"].lower().endswith(".xlsx"):
            raise BusinessError("STATEMENT_TEMPLATE_UNSUPPORTED")
        if len(body["content_base64"]) > 2796204:
            raise BusinessError("STATEMENT_TEMPLATE_FILE_LIMIT")
        try:
            content = base64.b64decode(body["content_base64"], validate=True)
        except ValueError, TypeError:
            raise BusinessError("STATEMENT_TEMPLATE_UNSUPPORTED") from None
        if not content or len(content) > 2 * 1024 * 1024:
            raise BusinessError("STATEMENT_TEMPLATE_FILE_LIMIT")
        if (
            "inspected_sha256" in body
            and hashlib.sha256(content).hexdigest() != body["inspected_sha256"]
        ):
            raise BusinessError("STATEMENT_TEMPLATE_FILE_CHANGED", 409)
        return content

    def inspect(self, actor, customer_id, body):
        return self.inspect_file(self.decode(actor, customer_id, body))

    def preview(self, actor, customer_id, body):
        content = self.decode(actor, customer_id, body)
        self.validate(content, body["mapping"])
        with self.read_transaction() as work:
            statement = work.statements.get(actor, body["statement_id"], history=False)
        if statement["customer_id"] != str(customer_id):
            raise BusinessError("STATEMENT_NOT_FOUND", 404)
        if statement["version"] != body["expected_version"]:
            raise BusinessError("VERSION_CONFLICT", 409)
        if statement["status"] not in {"draft", "confirmed"}:
            raise BusinessError("STATEMENT_STATE_CONFLICT", 409)
        require_coverage(body["mapping"], statement)
        rendered = self.render(
            {
                "id": "preview",
                "template_id": "customer-v1",
                "template_version": 1,
                "preview": True,
                "statement": statement,
                "customer_template": {"name": "模板预览", "version": 1, "mapping": body["mapping"]},
            },
            content,
        )
        return {
            "content_base64": base64.b64encode(rendered).decode(),
            "grid": self.preview_grid(rendered),
            "statement_version": statement["version"],
        }

    def import_template(self, actor, key, customer_id, body):
        content = self.decode(actor, customer_id, body)
        self.validate(content, body["mapping"])
        name = body["name"].strip()
        if not name or len(name) > 80:
            raise BusinessError("STATEMENT_TEMPLATE_MAPPING", 422, "name")
        file_hash = hashlib.sha256(content).hexdigest()
        payload = {
            "customer_id": str(customer_id),
            "name": name,
            "file_hash": file_hash,
            "mapping": body["mapping"],
        }
        with self.transaction() as work:
            prior = work.journal.claim(actor, "statement.template.import", key, payload)
            if prior is not None:
                return prior
            work.customers.lock(actor, customer_id)
            envelope = json.dumps(
                {
                    "type": "customer-statement-template-v1",
                    "sha256": file_hash,
                    "content": base64.b64encode(content).decode(),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            digest = self.store.put(envelope)
            identifier = uuid7()
            work.templates.create(
                actor, customer_id, identifier, name, file_hash, digest, body["mapping"]
            )
            result = self.present(work.templates.get(actor, customer_id, identifier))
            work.journal.audit(actor, "statement.template.import", identifier)
            work.journal.finish(actor, "statement.template.import", key, result)
            return result

    def listing(self, actor, customer_id, cursor=None, limit=50):
        with self.read_transaction() as work:
            work.customers.require(actor, customer_id)
            page = work.templates.listing(actor, customer_id, cursor, limit)
            return {**page, "items": [self.present(row) for row in page["items"]]}

    def detail(self, actor, customer_id, identifier):
        with self.read_transaction() as work:
            work.customers.require(actor, customer_id)
            return self.present(work.templates.get(actor, customer_id, identifier))
