"""Small shared command contracts; no persistence or HTTP dependencies."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class BusinessError(ValueError):
    def __init__(self, code: str, status: int = 422, field: str | None = None):
        self.code, self.status, self.field = code, status, field
        super().__init__(code)


@dataclass(frozen=True)
class Actor:
    organization_id: UUID
    user_id: UUID
    username: str
    role: str

    def require_write(self):
        if self.role not in {"admin", "operator"}:
            raise BusinessError("WRITE_FORBIDDEN", 403)


class CommandJournal(Protocol):
    def claim(self, actor: Actor, command: str, key: UUID, payload: dict) -> dict | None: ...
    def finish(self, actor: Actor, command: str, key: UUID, result: dict) -> None: ...
    def audit(self, actor: Actor, command: str, entity_id: UUID) -> None: ...
