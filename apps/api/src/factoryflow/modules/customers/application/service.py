from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import Actor, BusinessError, CommandJournal


class CustomerRepository(Protocol):
    def lock(self, organization_id: UUID, customer_id: UUID) -> dict | None: ...
    def get(self, organization_id: UUID, customer_id: UUID) -> dict | None: ...
    def insert(self, organization_id: UUID, customer_id: UUID, full_name: str) -> dict: ...
    def list(self, organization_id: UUID) -> list[dict]: ...


class CustomerAccess:
    def __init__(self, repository: CustomerRepository):
        self.repository = repository

    def require(self, actor: Actor, customer_id: UUID) -> dict:
        customer = self.repository.get(actor.organization_id, customer_id)
        if customer is None:
            raise BusinessError("CUSTOMER_NOT_FOUND", 404)
        return customer

    def lock(self, actor: Actor, customer_id: UUID) -> dict:
        customer = self.repository.lock(actor.organization_id, customer_id)
        if customer is None:
            raise BusinessError("CUSTOMER_NOT_FOUND", 404)
        return customer


@dataclass
class CustomerWork:
    customers: CustomerRepository
    journal: CommandJournal


class CustomerService:
    def __init__(self, transaction):
        self.transaction = transaction

    def create(self, actor: Actor, key: UUID, full_name: str) -> dict:
        actor.require_write()
        if not full_name.strip() or len(full_name) > 200:
            raise BusinessError("CUSTOMER_NAME_REQUIRED", field="full_name")
        name = full_name.strip()
        with self.transaction() as work:
            prior = work.journal.claim(actor, "customer.create", key, {"full_name": name})
            if prior is not None:
                return prior
            customer_id = uuid7()
            result = work.customers.insert(actor.organization_id, customer_id, name)
            work.journal.audit(actor, "customer.create", customer_id)
            work.journal.finish(actor, "customer.create", key, result)
            return result

    def list(self, actor: Actor) -> list[dict]:
        with self.transaction() as work:
            return work.customers.list(actor.organization_id)
