import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import Actor, BusinessError, CommandJournal
from factoryflow.modules.identity.domain.passwords import hash_password, verify_password


class IdentityRepository(Protocol):
    def require_empty_factory(self) -> None: ...
    def create_organization(self, organization_id: UUID, name: str) -> None: ...
    def create_user(self, actor: Actor, password_hash: str) -> None: ...
    def lock_user(self, username: str) -> dict | None: ...
    def login_result(self, user_id: UUID, success: bool, now: datetime) -> None: ...
    def create_session(self, actor: Actor, digest: str, csrf: str, expires: datetime) -> None: ...
    def session(self, digest: str) -> dict | None: ...
    def delete_session(self, digest: str) -> None: ...


@dataclass
class IdentityWork:
    identities: IdentityRepository
    journal: CommandJournal


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class IdentityService:
    def __init__(self, transaction):
        self.transaction = transaction

    def provision_factory(self, name: str, username: str, password: str) -> Actor:
        if not name.strip() or len(name) > 200 or not username.strip() or len(username) > 100:
            raise BusinessError("INVALID_INPUT")
        password_hash = hash_password(password)
        actor = Actor(uuid7(), uuid7(), username.strip(), "admin")
        with self.transaction() as work:
            work.identities.require_empty_factory()
            work.identities.create_organization(actor.organization_id, name.strip())
            work.identities.create_user(actor, password_hash)
            work.journal.audit(actor, "identity.provision_factory", actor.organization_id)
        return actor

    def add_user(self, actor: Actor, username: str, password: str, role: str) -> Actor:
        if actor.role != "admin":
            raise BusinessError("ADMIN_REQUIRED", 403)
        if not username.strip() or len(username) > 100 or role not in {"operator", "viewer"}:
            raise BusinessError("INVALID_INPUT")
        password_hash = hash_password(password)
        user = Actor(actor.organization_id, uuid7(), username.strip(), role)
        with self.transaction() as work:
            work.identities.create_user(user, password_hash)
            work.journal.audit(actor, "identity.add_user", user.user_id)
        return user

    def login(self, username: str, password: str) -> dict:
        now = datetime.now(UTC)
        result = None
        with self.transaction() as work:
            user = work.identities.lock_user(username.strip())
            valid = verify_password(password, user["password_hash"] if user else None)
            if user:
                locked = user["locked_until"] is not None and user["locked_until"] > now
                valid = valid and user["active"] and not locked
                work.identities.login_result(user["id"], valid, now)
                if valid:
                    actor = Actor(
                        user["organization_id"], user["id"], user["username"], user["role"]
                    )
                    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                    expires = now + timedelta(hours=12)
                    work.identities.create_session(actor, token_digest(token), csrf, expires)
                    work.journal.audit(actor, "identity.login", actor.user_id)
                    result = {
                        "actor": actor,
                        "session_token": token,
                        "csrf_token": csrf,
                        "expires_at": expires,
                    }
        if result is None:
            raise BusinessError("AUTH_FAILED", 401)
        return result

    def authenticate(self, token: str | None) -> tuple[Actor, str]:
        if not token or len(token) > 200:
            raise BusinessError("LOGIN_REQUIRED", 401)
        with self.transaction() as work:
            session = work.identities.session(token_digest(token))
            if not session:
                raise BusinessError("LOGIN_REQUIRED", 401)
            return (
                Actor(
                    session["organization_id"],
                    session["user_id"],
                    session["username"],
                    session["role"],
                ),
                session["csrf_token"],
            )

    def logout(self, token: str, actor: Actor):
        with self.transaction() as work:
            work.identities.delete_session(token_digest(token))
            work.journal.audit(actor, "identity.logout", actor.user_id)
