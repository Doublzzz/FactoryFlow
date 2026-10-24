from decimal import Decimal

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.statements.domain.customer_templates import CUSTOM_TEMPLATE
from factoryflow.modules.statements.domain.draft import MODES, canonical, decimal_value, reason
from factoryflow.modules.statements.domain.templates import DEFAULT_TEMPLATE, TEMPLATES


class StatementSettings:
    def __init__(self, transaction):
        self.transaction = transaction

    def get(self, actor, customer_id):
        with self.transaction() as work:
            work.customers.require(actor, customer_id)
            return work.statements.settings(actor, customer_id)

    def save(self, actor, key, customer_id, expected, payload):
        actor.require_write()
        day = payload.get("cycle_day")
        if day is not None and (type(day) is not int or not 1 <= day <= 31):
            raise BusinessError("STATEMENT_PERIOD_INVALID")
        if payload.get("tax_mode") not in MODES:
            raise BusinessError("STATEMENT_TAX_MODE_REQUIRED")
        template = payload.get("template_id", DEFAULT_TEMPLATE)
        custom_id = payload.get("customer_template_id")
        if template not in {*TEMPLATES, CUSTOM_TEMPLATE} or (
            (template == CUSTOM_TEMPLATE) != bool(custom_id)
        ):
            raise BusinessError("STATEMENT_TEMPLATE_INVALID")
        body = {
            "template_id": template,
            "customer_id": str(customer_id),
            "expected_version": expected,
            "cycle_day": day,
            "tax_mode": payload["tax_mode"],
            "tax_rate": canonical(decimal_value(payload.get("tax_rate"), 4, Decimal(100))),
            "reason": reason(payload.get("reason"), True),
        }
        if custom_id is not None:
            body["customer_template_id"] = str(custom_id)
        with self.transaction() as work:
            prior = work.journal.claim(actor, "statement.settings", key, body)
            if prior is not None:
                return prior
            work.customers.lock(actor, customer_id)
            if custom_id is not None:
                work.templates.get(actor, customer_id, custom_id)
            previous = work.statements.settings(actor, customer_id)
            version = previous["version"] if previous else 0
            if type(expected) is not int or expected != version:
                raise BusinessError("VERSION_CONFLICT", 409)
            work.statements.save_settings(actor, customer_id, body, version + 1)
            result = work.statements.settings(actor, customer_id)
            work.journal.audit(actor, "statement.settings", customer_id)
            work.journal.finish(actor, "statement.settings", key, result)
            return result
