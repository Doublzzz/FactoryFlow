"""Owned catalog persistence. No order/evidence table access."""

from uuid import uuid7

from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text


class MaterialRepository:
    def __init__(self, conn):
        self.conn = conn

    def lock(self, actor):
        # One organization-sized catalog lock keeps multi-row commands in a single lock order.
        self.conn.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
            {"scope": f"{actor.organization_id}:materials"},
        )

    @staticmethod
    def view(row):
        return {
            key: str(value) if key in {"id", "created_by", "updated_by"} else value
            for key, value in row.items()
            if key in {"id", "own_code", "name", "specification", "unit", "active", "version"}
        }

    def get(self, actor, identifier):
        row = (
            self.conn.execute(
                text("SELECT * FROM materials WHERE organization_id=:org AND id=:id"),
                {"org": actor.organization_id, "id": identifier},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("MATERIAL_NOT_FOUND", 404)
        return self.view(row)

    def by_own_code(self, actor, code):
        row = (
            self.conn.execute(
                text("SELECT * FROM materials WHERE organization_id=:org AND own_code=:code"),
                {"org": actor.organization_id, "code": code},
            )
            .mappings()
            .first()
        )
        return self.view(row) if row else None

    def import_candidates(self, actor, name, specification):
        rows = self.conn.execute(
            text("""SELECT * FROM materials WHERE organization_id=:org AND active
            AND ((:name<>'' AND strpos(lower(name),lower(:name))>0)
              OR specification=:spec)
            ORDER BY own_code,id LIMIT 5"""),
            {"org": actor.organization_id, "name": name, "spec": specification},
        ).mappings()
        return [self.view(row) for row in rows]

    def insert(self, actor, data):
        identifier = uuid7()
        params = {**data, "id": identifier, "org": actor.organization_id, "actor": actor.user_id}
        automatic = data["own_code"] is None
        for _ in range(10000 if automatic else 1):
            if automatic:
                number = self.conn.execute(text("SELECT nextval('material_code_seq')")).scalar_one()
                params["own_code"] = f"WL{number:06d}"
            row = (
                self.conn.execute(
                    text("""INSERT INTO materials
                (organization_id,id,own_code,name,specification,unit,created_by,updated_by)
                VALUES(:org,:id,:own_code,:name,:specification,:unit,:actor,:actor)
                ON CONFLICT (organization_id,own_code) DO NOTHING RETURNING *"""),
                    params,
                )
                .mappings()
                .first()
            )
            if row is not None:
                return self.view(row)
        raise BusinessError("MATERIAL_NUMBER_BUSY" if automatic else "MATERIAL_CODE_EXISTS", 409)

    def update(self, actor, identifier, data, active):
        row = (
            self.conn.execute(
                text("""UPDATE materials SET own_code=:own_code,name=:name,
            specification=:specification,unit=:unit,active=:active,version=version+1,
            updated_by=:actor,updated_at=now()
            WHERE organization_id=:org AND id=:id RETURNING *"""),
                {
                    **data,
                    "org": actor.organization_id,
                    "id": identifier,
                    "actor": actor.user_id,
                    "active": active,
                },
            )
            .mappings()
            .one()
        )
        return self.view(row)

    def list(self, actor, query, offset, limit):
        # strpos treats user punctuation literally (no wildcard interpretation).
        rows = (
            self.conn.execute(
                text("""SELECT m.* FROM materials m WHERE m.organization_id=:org
            AND (:q='' OR strpos(
                lower(m.own_code||' '||m.name||' '||coalesce(m.specification,'')),lower(:q))>0
              OR EXISTS(SELECT 1 FROM customer_material_codes c
                WHERE c.organization_id=m.organization_id
                AND c.material_id=m.id AND strpos(lower(c.customer_code),lower(:q))>0))
            ORDER BY m.own_code,m.id LIMIT :limit OFFSET :offset"""),
                {"org": actor.organization_id, "q": query, "offset": offset, "limit": limit + 1},
            )
            .mappings()
            .all()
        )
        items = [self.view(row) for row in rows[:limit]]
        by_id = {item["id"]: item for item in items}
        if query and items:
            matches = self.conn.execute(
                text("""SELECT c.material_id,c.customer_code,u.full_name AS customer_name
                FROM customer_material_codes c JOIN customers u
                  ON u.organization_id=c.organization_id AND u.id=c.customer_id
                WHERE c.organization_id=:org AND c.material_id=ANY(:ids)
                AND strpos(lower(c.customer_code),lower(:q))>0
                ORDER BY u.full_name,c.customer_code"""),
                {
                    "org": actor.organization_id,
                    "ids": [row["id"] for row in rows[:limit]],
                    "q": query,
                },
            ).mappings()
            for match in matches:
                by_id[str(match["material_id"])].setdefault("matched_customer_codes", []).append(
                    {
                        "customer_name": match["customer_name"],
                        "customer_code": match["customer_code"],
                    }
                )
        return {"items": items, "next_offset": offset + limit if len(rows) > limit else None}

    @staticmethod
    def code_view(row):
        return {
            key: str(value) if key in {"customer_id", "material_id"} else value
            for key, value in row.items()
            if key != "organization_id"
        }

    def code(self, actor, customer_id, code):
        row = (
            self.conn.execute(
                text(
                    "SELECT * FROM customer_material_codes "
                    "WHERE organization_id=:org AND customer_id=:customer AND customer_code=:code"
                ),
                {"org": actor.organization_id, "customer": customer_id, "code": code},
            )
            .mappings()
            .first()
        )
        return self.code_view(row) if row else None

    def save_code(self, actor, customer_id, code, material_id, source, exists):
        params = {
            **source,
            "org": actor.organization_id,
            "customer": customer_id,
            "code": code,
            "material": material_id,
        }
        sql = (
            "UPDATE customer_material_codes SET material_id=:material,item_name=:item_name,"
            "specification=:specification,canonical_unit=:canonical_unit,version=version+1 "
            "WHERE organization_id=:org AND customer_id=:customer AND customer_code=:code"
            if exists
            else "INSERT INTO customer_material_codes(organization_id,customer_id,"
            "customer_code,material_id,item_name,specification,canonical_unit) "
            "VALUES(:org,:customer,:code,:material,:item_name,:specification,:canonical_unit)"
        )
        self.conn.execute(text(sql), params)
        return self.code(actor, customer_id, code)

    def codes(self, actor, material_id=None, customer_id=None):
        rows = self.conn.execute(
            text(
                "SELECT * FROM customer_material_codes WHERE organization_id=:org"
                " AND (CAST(:material AS uuid) IS NULL OR material_id=:material)"
                " AND (CAST(:customer AS uuid) IS NULL OR customer_id=:customer)"
                " ORDER BY customer_id,customer_code LIMIT 1000"
            ),
            {"org": actor.organization_id, "material": material_id, "customer": customer_id},
        ).mappings()
        return [self.code_view(row) for row in rows]
