"""Direct PostgreSQL constraints for synthetic statement lifecycle records."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_statements import draft, source


def test_lifecycle_tables_exist(pg):
    with pg.owner.connect() as conn:
        assert conn.scalar(text("SELECT to_regclass('statement_approvals')")) is not None


def prepared(pg):
    delivery = source(pg)
    response = pg.api.command("/api/v1/statements", draft(pg, delivery))
    assert response.status_code == 200, response.text
    statement = response.json()
    params = {
        "org": pg.actor.organization_id,
        "actor": pg.actor.user_id,
        "customer": pg.customer_id,
        "statement": statement["id"],
        "delivery": delivery["id"],
        "line": delivery["lines"][0]["order_line_id"],
        "export": uuid4(),
        "sent": uuid4(),
        "feedback": uuid4(),
        "approval": uuid4(),
        "review": uuid4(),
    }
    with pg.owner.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO statement_exports(organization_id,id,statement_id,customer_id,
            statement_version,template_id,template_version,snapshot,status,object_hash,file_hash)
            VALUES(:org,:export,:statement,:customer,1,'standard-v1',1,'{}','ready',
            repeat('a',64),repeat('a',64))
        """),
            params,
        )
        conn.execute(
            text("""
            INSERT INTO statement_evidence(organization_id,id,statement_id,customer_id,
            kind,export_id,statement_version,person,occurred_on,note,actor_id) VALUES
            (:org,:sent,:statement,:customer,'sent',:export,1,'Synthetic','2026-10-02','',:actor),
            (:org,:feedback,:statement,:customer,'feedback',NULL,1,'Synthetic',
            '2026-10-03','Synthetic phone confirmation',:actor)
        """),
            params,
        )
        conn.execute(
            text("""
            UPDATE statement_lines SET quantity=0,status='released',reason='Synthetic approval'
            WHERE organization_id=:org AND statement_id=:statement
        """),
            params,
        )
        conn.execute(
            text("""
            INSERT INTO statement_approvals(organization_id,id,customer_id,statement_id,
            delivery_id,order_line_id,sent_id,feedback_id,quantity,unit_price,target_start,
            target_end,reason,source,actor_id) VALUES(:org,:approval,:customer,:statement,
            :delivery,:line,:sent,:feedback,0.1,2,'2026-10-01','2026-10-31',
            'Synthetic approval','{}',:actor)
        """),
            params,
        )
    return params


def allocate(conn, params, quantity="0.06"):
    conn.execute(
        text("""
        INSERT INTO statement_allocations(organization_id,id,customer_id,approval_id,
        statement_id,quantity,unit_price,status,reason,actor_id)
        VALUES(:org,:id,:customer,:approval,:statement,:quantity,2,'reserved','Synthetic',:actor)
    """),
        params | {"id": uuid4(), "quantity": quantity},
    )


def add_review(conn, params):
    conn.execute(
        text("""
        INSERT INTO statement_reviews(organization_id,id,customer_id,statement_id,
        delivery_id,order_line_id,quantity,reason,source,actor_id)
        VALUES(:org,:review,:customer,:statement,:delivery,:line,0.025,
        'Synthetic review','{}',:actor)
    """),
        params,
    )


def test_direct_reservations_serialize_per_approval(pg):
    params = prepared(pg)
    barrier = Barrier(2)

    def run(_):
        barrier.wait()
        try:
            with pg.owner.begin() as conn:
                allocate(conn, params)
            return True
        except DBAPIError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, range(2))) == [False, True]
    with pg.owner.connect() as conn:
        assert str(conn.scalar(text("SELECT sum(quantity) FROM statement_allocations"))) == "0.06"
        assert str(conn.scalar(text("SELECT claimed FROM statement_balances"))) == "0.1"


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE statement_approvals SET quantity=0.101 WHERE id=:approval",
        "UPDATE statement_approvals SET quantity=-1,version=2 WHERE id=:approval",
        "UPDATE statement_approvals SET quantity=0.1001,version=2 WHERE id=:approval",
        "UPDATE statement_approvals SET customer_id=:actor,version=2 WHERE id=:approval",
        "UPDATE statement_lifecycle_events SET snapshot='{}'",
        "DELETE FROM statement_approvals WHERE id=:approval",
        "UPDATE statements SET status='confirmed',version=2 WHERE id=:statement",
        "UPDATE deliveries SET status='void',version=2,void_reason='Synthetic',voided_at=now() "
        "WHERE id=:delivery",
    ],
)
def test_direct_mutation_cannot_bypass_evidence_and_quantity_contract(pg, mutation):
    params = prepared(pg)
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(text(mutation), params)
    with pg.owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM statement_lifecycle_events")) == 1


def test_review_gate_claim_release_and_immutable_original(pg):
    params = prepared(pg)
    with pg.owner.begin() as conn:
        add_review(conn, params)
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(
            text("""
            UPDATE statement_lines SET quantity=0.02,status='included'
            WHERE organization_id=:org AND statement_id=:statement
        """),
            params,
        )
    with pg.owner.begin() as conn:
        conn.execute(
            text("""
            UPDATE statement_lines SET quantity=0.02,status='included'
            WHERE organization_id=:org AND statement_id=:statement
        """),
            params,
        )
        conn.execute(
            text("""
            INSERT INTO statement_review_transfers(organization_id,id,customer_id,review_id,
            statement_id,quantity,status,reason,actor_id) VALUES(:org,:transfer,:customer,
            :review,:statement,0.02,'claimed','Synthetic claim',:actor)
        """),
            params | {"transfer": uuid4()},
        )
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(
            text("""
            UPDATE statement_lines SET quantity=0,status='released'
            WHERE organization_id=:org AND statement_id=:statement
        """),
            params,
        )
    with pg.owner.begin() as conn:
        conn.execute(
            text("""
            UPDATE statement_lines SET quantity=0,status='released'
            WHERE organization_id=:org AND statement_id=:statement
        """),
            params,
        )
        conn.execute(
            text("""
            UPDATE statement_review_transfers SET status='released',version=2
            WHERE organization_id=:org
        """),
            params,
        )
    with pg.owner.connect() as conn:
        assert str(conn.scalar(text("SELECT quantity FROM statement_reviews"))) == "0.025"
        assert str(conn.scalar(text("SELECT claimed FROM statement_balances"))) == "0.10"
        assert conn.scalar(text("SELECT version FROM statement_reviews")) == 3
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(text("UPDATE statement_reviews SET quantity=0.01,version=2"))


def test_settled_row_retains_original_formal_version(pg):
    params = prepared(pg)
    with pg.owner.begin() as conn:
        allocate(conn, params)
        conn.execute(
            text("""
            UPDATE statements SET status='confirmed',version=2,fees_confirmed=true,
            reconfirmation='not_required' WHERE id=:statement
        """),
            params,
        )
        conn.execute(
            text("""
            INSERT INTO statement_events(organization_id,id,statement_id,version,action,
            reason,actor_id,snapshot) VALUES(:org,:event,:statement,2,
            'settle','Synthetic',:actor,'{}')
        """),
            params | {"event": uuid4()},
        )
        conn.execute(
            text("""
            UPDATE statement_allocations SET status='settled',version=2,settlement_version=2
        """)
        )
    for mutation in (
        "UPDATE statement_allocations SET quantity=0.05,version=3",
        "UPDATE statement_allocations SET status='released',version=3,settlement_version=NULL",
        "UPDATE statement_allocations SET status='superseded',version=3,superseded_version=3",
    ):
        with pytest.raises(DBAPIError), pg.owner.begin() as conn:
            conn.execute(text(mutation))
    with pg.owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM statement_lifecycle_events")) == 3
    with pg.owner.begin() as conn:
        conn.execute(text("UPDATE statements SET version=3"))
        conn.execute(
            text("""
            INSERT INTO statement_events(organization_id,id,statement_id,version,action,
            reason,actor_id,snapshot) VALUES(:org,:event,:statement,3,
            'correct_settlement','Synthetic correction',:actor,'{}')
            """),
            params | {"event": uuid4()},
        )
        conn.execute(
            text("""
            UPDATE statement_allocations SET status='superseded',version=3,superseded_version=3
        """)
        )
    with pg.owner.connect() as conn:
        assert conn.scalar(text("SELECT settlement_version FROM statement_allocations")) == 2
        assert conn.scalar(text("SELECT superseded_version FROM statement_allocations")) == 3


def test_review_case_total_and_source_capacity_limits(pg):
    params = prepared(pg)
    with pg.owner.begin() as conn:
        add_review(conn, params)
    for quantity in ("0.02", "0.026", "-0.01", "0.0001"):
        with pytest.raises(DBAPIError), pg.owner.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO statement_review_transfers(organization_id,id,customer_id,
                review_id,statement_id,quantity,status,reason,actor_id)
                VALUES(:org,:transfer,:customer,:review,:statement,:quantity,
                'approved','Synthetic',:actor)
                """),
                params | {"transfer": uuid4(), "quantity": quantity},
            )
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO statement_review_transfers(organization_id,id,customer_id,
            review_id,statement_id,quantity,status,reason,actor_id,approval_id)
            VALUES(:org,:transfer,:customer,:review,:statement,0.02,
            'approved','Synthetic old approval must not resolve review',:actor,:approval)
        """),
            params | {"transfer": uuid4()},
        )
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        add_review(conn, params | {"review": uuid4()})
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO statement_evidence(organization_id,id,statement_id,customer_id,
            kind,export_id,statement_version,person,occurred_on,note,actor_id)
            VALUES(:org,:new,:statement,:customer,'sent',:export,99,
            'Synthetic','2026-10-04','Synthetic',:actor)
            """),
            params | {"new": uuid4()},
        )
