from datetime import timedelta

from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text


class IdentityRepository:
    def __init__(self, conn):
        self.conn = conn

    def require_empty_factory(self):
        self.conn.execute(text("SELECT pg_advisory_xact_lock(782334901)"))
        if self.conn.execute(text("SELECT EXISTS(SELECT 1 FROM organizations)")).scalar_one():
            raise BusinessError("FACTORY_ALREADY_INITIALIZED", 409)

    def create_organization(self, organization_id, name):
        self.conn.execute(
            text("INSERT INTO organizations (id,name) VALUES (:id,:name)"),
            {"id": organization_id, "name": name},
        )

    def create_user(self, actor, password_hash):
        self.conn.execute(
            text(
                "INSERT INTO users (id,organization_id,username,password_hash,role) "
                "VALUES (:id,:org,:name,:password,:role)"
            ),
            {
                "id": actor.user_id,
                "org": actor.organization_id,
                "name": actor.username,
                "password": password_hash,
                "role": actor.role,
            },
        )

    def lock_user(self, username):
        row = (
            self.conn.execute(
                text("SELECT * FROM users WHERE username=:name FOR UPDATE"), {"name": username}
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def login_result(self, user_id, success, now):
        if success:
            self.conn.execute(
                text("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=:id"),
                {"id": user_id},
            )
        else:
            self.conn.execute(
                text("""UPDATE users SET
              failed_attempts=CASE WHEN locked_until IS NOT NULL AND locked_until<=:now
                                  THEN 1 ELSE failed_attempts+1 END,
              locked_until=CASE WHEN locked_until IS NOT NULL AND locked_until<=:now THEN NULL
                                WHEN failed_attempts>=4 THEN :until ELSE locked_until END
              WHERE id=:id"""),
                {"id": user_id, "now": now, "until": now + timedelta(minutes=15)},
            )

    def create_session(self, actor, digest, csrf, expires):
        self.conn.execute(
            text("DELETE FROM sessions WHERE user_id=:id AND expires_at<=now()"),
            {"id": actor.user_id},
        )
        self.conn.execute(
            text(
                "INSERT INTO sessions "
                "(token_hash,organization_id,user_id,csrf_token,expires_at) "
                "VALUES (:hash,:org,:id,:csrf,:expires)"
            ),
            {
                "hash": digest,
                "org": actor.organization_id,
                "id": actor.user_id,
                "csrf": csrf,
                "expires": expires,
            },
        )

    def session(self, digest):
        row = (
            self.conn.execute(
                text("""SELECT s.organization_id,s.user_id,s.csrf_token,u.username,u.role
          FROM sessions s JOIN users u ON u.id=s.user_id AND u.organization_id=s.organization_id
          WHERE s.token_hash=:hash AND s.expires_at>now() AND u.active"""),
                {"hash": digest},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def delete_session(self, digest):
        self.conn.execute(text("DELETE FROM sessions WHERE token_hash=:hash"), {"hash": digest})
