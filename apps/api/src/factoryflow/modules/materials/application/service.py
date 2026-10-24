"""Catalog public facade joins its caller's transaction; commands own their journal."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.materials.application.importing import build_import_plan, inspection
from factoryflow.modules.materials.domain.material import prepare_material, signature, text_value


class MaterialCatalog:
    def __init__(self, repository, customers):
        self.repository = repository
        self.customers = customers

    def lock(self, actor):
        self.repository.lock(actor)

    def require(self, actor, identifier, expected=None, *, active=True):
        material = self.repository.get(actor, identifier)
        if expected is not None and expected != material["version"]:
            raise BusinessError("MATERIAL_VERSION_CONFLICT", 409)
        if active and not material["active"]:
            raise BusinessError("MATERIAL_INACTIVE", 409)
        return material

    def create(self, actor, payload):
        return self.repository.insert(actor, prepare_material(payload))

    def remember(self, actor, customer_id, code, material, source, expected=0, reason=None):
        self.customers.require(actor, UUID(str(customer_id)))
        code = text_value(code, "customer_code", 100, required=True)
        before = self.repository.code(actor, customer_id, code)
        actual = before["version"] if before else 0
        if actual != expected:
            raise BusinessError("MATERIAL_MAPPING_CONFLICT", 409)
        if (
            before
            and before["material_id"] == material["id"]
            and all(before[field] == value for field, value in signature(source).items())
        ):
            return {"before": before, "after": before}
        if before:
            text_value(reason, "reason", 500, required=True)
        after = self.repository.save_code(
            actor, customer_id, code, material["id"], signature(source), bool(before)
        )
        return {"before": before, "after": after}

    def choose(self, actor, customer_id, line, choice):
        material = self.require(actor, choice["material_id"], choice["expected_material_version"])
        mapping = choice.get("mapping")
        if mapping:
            if (
                str(mapping["customer_id"]) != str(customer_id)
                or mapping["customer_code"] != (line.get("item_code") or "").strip()
            ):
                raise BusinessError("MATERIAL_MAPPING_CONFLICT", 409)
            saved = self.repository.code(actor, customer_id, mapping["customer_code"])
            if (
                not saved
                or saved["version"] != mapping["expected_mapping_version"]
                or saved["material_id"] != material["id"]
                or {field: saved[field] for field in signature(line)} != signature(line)
                or saved["canonical_unit"] is None
            ):
                raise BusinessError("MATERIAL_MAPPING_CONFLICT", 409)
        return material

    def suggestions(self, actor, customer_id, lines):
        suggestions = []
        for line in lines:
            code = (line.get("item_code") or "").strip()
            if not code:
                continue
            mapping = self.repository.code(actor, customer_id, code)
            if not mapping:
                continue
            material = self.repository.get(actor, mapping["material_id"])
            source = signature(line)
            matches = (
                material["active"]
                and source["canonical_unit"] is not None
                and all(mapping[field] == value for field, value in source.items())
            )
            suggestions.append(
                {
                    "line_number": line["line_number"],
                    "material": material,
                    "automatic": matches,
                    "mapping": {
                        "customer_id": str(customer_id),
                        "customer_code": code,
                        "expected_mapping_version": mapping["version"],
                    },
                }
            )
        return suggestions

    def summarize(self, actor, identifiers):
        return {
            str(identifier): self.repository.get(actor, identifier)
            for identifier in set(identifiers)
        }


@dataclass
class MaterialWork:
    catalog: MaterialCatalog
    journal: object


def change_record(actor, before, after, reason=None):
    return {
        "before": before,
        "after": after,
        "reason": reason,
        "actor_id": str(actor.user_id),
        "occurred_at": datetime.now(UTC).isoformat(),
    }


class MaterialService:
    def __init__(self, transaction, import_reader):
        self.transaction = transaction
        self.import_reader = import_reader

    def inspect_import(self, actor, payload):
        actor.require_write()
        return inspection(
            self.import_reader(
                payload["filename"], payload["content_base64"], payload.get("header_row", 1)
            )
        )

    def preview_import(self, actor, payload):
        actor.require_write()
        table = self.import_reader(
            payload["filename"], payload["content_base64"], payload.get("header_row", 1)
        )
        with self.transaction() as work:
            work.catalog.lock(actor)
            result, _ = build_import_plan(work.catalog, actor, table, payload)
            return result

    def confirm_import(self, actor, key, payload):
        actor.require_write()
        table = self.import_reader(
            payload["filename"], payload["content_base64"], payload.get("header_row", 1)
        )
        stable = {name: value for name, value in payload.items() if name != "content_base64"}
        stable["file_hash"] = table["file_hash"]
        with self.transaction() as work:
            prior = work.journal.claim(actor, "material.import", key, stable)
            if prior is not None:
                return prior
            work.catalog.lock(actor)
            plan, rows = build_import_plan(work.catalog, actor, table, payload)
            if plan["preview_fingerprint"] != payload["preview_fingerprint"]:
                raise BusinessError("MATERIAL_IMPORT_STALE", 409)
            if not plan["ready"]:
                raise BusinessError("MATERIAL_IMPORT_UNRESOLVED", field="choices")
            creates = [row for row in rows if row["action"] == "create"]
            # Explicit codes enter the unique domain before the automatic sequence is used.
            for row in sorted(creates, key=lambda value: value["source"]["own_code"] is None):
                row["material"] = work.catalog.create(actor, row["data"])
            results = []
            audited = set()
            mapping_count = 0
            for row in rows:
                if row["action"] == "skip":
                    results.append(
                        {
                            "row_number": row["row_number"],
                            "action": "skip",
                            "reason": "用户明确跳过",
                            "material": None,
                            "change": None,
                            "mapping_change": None,
                        }
                    )
                    continue
                material = row["material"]
                mapping_change = None
                if row["source"]["customer_code"] and not row["mapping"]:
                    mapping_change = work.catalog.remember(
                        actor,
                        payload["customer_id"],
                        row["source"]["customer_code"],
                        material,
                        {**row["source"], "item_name": row["source"]["name"]},
                    )
                    mapping_count += 1
                results.append(
                    {
                        "row_number": row["row_number"],
                        "action": row["action"],
                        "reason": None,
                        "material": material,
                        "change": change_record(
                            actor, None if row["action"] == "create" else material, material
                        ),
                        "mapping_change": mapping_change,
                    }
                )
                if material["id"] not in audited:
                    work.journal.audit(actor, "material.import", UUID(material["id"]))
                    audited.add(material["id"])
            result = {
                "file_hash": table["file_hash"],
                "rows": results,
                "created_count": len(creates),
                "reused_count": sum(row["action"] == "reuse" for row in rows),
                "skipped_count": sum(row["action"] == "skip" for row in rows),
                "mapping_count": mapping_count,
                "actor_id": str(actor.user_id),
                "occurred_at": datetime.now(UTC).isoformat(),
            }
            work.journal.finish(actor, "material.import", key, result)
            return result

    def list(self, actor, query="", offset=0, limit=50):
        with self.transaction() as work:
            return work.catalog.repository.list(actor, query.strip(), offset, limit)

    def codes(self, actor, material_id=None, customer_id=None, customer_code=None):
        with self.transaction() as work:
            if material_id:
                work.catalog.require(actor, material_id, active=False)
            if customer_id:
                work.catalog.customers.require(actor, customer_id)
            if customer_code is not None:
                if not customer_id:
                    raise BusinessError("INVALID_INPUT", field="customer_id")
                row = work.catalog.repository.code(actor, customer_id, customer_code.strip())
                return {"items": [row] if row else []}
            return {"items": work.catalog.repository.codes(actor, material_id, customer_id)}

    def create(self, actor, key, payload):
        actor.require_write()
        data = prepare_material(payload)
        with self.transaction() as work:
            prior = work.journal.claim(actor, "material.create", key, data)
            if prior is not None:
                return prior
            work.catalog.lock(actor)
            material = work.catalog.create(actor, data)
            result = {**material, "change": change_record(actor, None, material)}
            work.journal.audit(actor, "material.create", UUID(material["id"]))
            work.journal.finish(actor, "material.create", key, result)
            return result

    def update(self, actor, key, identifier, payload):
        actor.require_write()
        data = prepare_material(payload)
        reason = text_value(payload.get("reason"), "reason", 500, required=True)
        with self.transaction() as work:
            prior = work.journal.claim(
                actor, "material.update", key, {"id": str(identifier), **payload}
            )
            if prior is not None:
                return prior
            work.catalog.lock(actor)
            before = work.catalog.require(
                actor, identifier, payload["expected_version"], active=False
            )
            if data["own_code"] is None:
                raise BusinessError("INVALID_INPUT", field="own_code")
            for field in ("specification", "unit"):
                if before[field] and before[field] != data[field]:
                    raise BusinessError("MATERIAL_IDENTITY_IMMUTABLE", 409, field=field)
            material = work.catalog.repository.update(actor, identifier, data, payload["active"])
            result = {**material, "change": change_record(actor, before, material, reason)}
            work.journal.audit(actor, "material.update", identifier)
            work.journal.finish(actor, "material.update", key, result)
            return result

    def save_code(self, actor, key, payload):
        actor.require_write()
        with self.transaction() as work:
            prior = work.journal.claim(actor, "material.code", key, payload)
            if prior is not None:
                return prior
            work.catalog.lock(actor)
            material = work.catalog.require(
                actor, payload["material_id"], payload["expected_material_version"]
            )
            changed = work.catalog.remember(
                actor,
                payload["customer_id"],
                payload["customer_code"],
                material,
                payload,
                payload.get("expected_mapping_version", 0),
                payload.get("reason"),
            )
            result = {
                **changed["after"],
                "change": change_record(actor, **changed, reason=payload.get("reason")),
            }
            work.journal.audit(actor, "material.code", UUID(material["id"]))
            work.journal.finish(actor, "material.code", key, result)
            return result
