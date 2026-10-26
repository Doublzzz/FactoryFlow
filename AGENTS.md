# FactoryFlow execution contract

Read README.md, docs/STATUS.md, docs/PRODUCT-SPEC.md and relevant source before changing behavior. The current request defines scope. Do not start additional business capabilities, overseas finance or publication work without authorization.

- Check Git status and preserve existing work. Do not automatically commit, push or deploy.
- Use only synthetic data in source, tests, examples and shared evidence. Do not read or upload runtime databases, credentials, customer files or private local configuration. Do not inspect `.codex/`.
- Modules own their commands, invariants, persistence and public contracts. Cross-module code uses only the owner's public interface.
- Domain code depends only on the standard library, its own domain and the small shared kernel. Adapters own HTTP, ORM, storage and model providers.
- Bootstrap composes adapters. Import and startup must not create databases, migrate, access the network or initialize directories.
- Every business command commits its audit, idempotency result and required ledger effects atomically. Preserve ownership and concurrency enforcement.
- Decimal quantities and amounts cross HTTP as strings. Never use binary float for business quantity or money. Confirmed revisions are immutable.
- Change DTO source and regenerate OpenAPI/TypeScript; do not hand-edit generated contracts.
- Keep the smallest coherent implementation. Add abstractions only for demonstrated behavior; do not remove transaction or evidence safeguards to simplify code.
- Freeze business examples before new behavior. Run relevant tests, architecture and contract checks, frontend typecheck/build where affected, and whitespace checks. PostgreSQL behavior needs real PostgreSQL evidence; a skip is not a pass.
- For ledger changes verify rollback, replay/conflict, reverse operations, ownership and concurrent database enforcement.
- State actual results and limitations. Synthetic tests do not establish factory, commercial or overseas acceptance.

This repository contains a clean source snapshot. Its synthetic examples may be used for bilingual README demonstrations, but should never be presented as real customers or production outcomes.
