# Architecture / 架构

FactoryFlow is a modular monolith: React/TypeScript web UI, a Python/FastAPI API, PostgreSQL and immutable local object storage. The prepared web bundle and API can be served from the same loopback origin. LAN/public hosting, TLS and identity integration require separate work.

## Ownership and dependency direction

`apps/api/src/factoryflow/bootstrap.py` is the composition root. Business capabilities live in `modules/<capability>/domain`, `application`, `adapters` and `public.py`. Pure domain code does not depend on HTTP or ORM. Cross-module callers import the owner's public interface. `kernel` contains only shared small value/error primitives; `platform` owns technical lifecycle concerns.

Current modules: identity, customers, documents, orders, fulfillment, statements, archives and materials. No inventory module or general plugin platform is included.

## Data and commands

One business command owns one PostgreSQL transaction. Version and ownership checks, audit events, idempotent results and ledger effects commit together. Database constraints and locks enforce concurrent boundaries. HTTP quantity/money values are decimal strings; calculations use Decimal.

Confirmed revisions and export snapshots remain immutable evidence. Object bytes are stored by content hash; database references become authoritative only when the command commits. Existing outputs are not regenerated merely because the user changes interface language.

## Contracts and runtime

Server DTOs project to `contracts/openapi.json` and `packages/api-client/src/schema.d.ts`. Use `scripts/export-openapi.py` and `npm run contracts:generate` to regenerate. `scripts/check_architecture.py` checks import boundaries.

The application does not perform migrations or initialize data on import/startup. Schema migration is an explicit administration command; current head is `0013_material_pool`. Runtime roles are separate from administration. Source does not contain actual runtime account credentials or customer documents.

## Language

`apps/web/src/i18n.ts` stores the language choice and translates explicit product messages with parameter interpolation. `messages.en.ts` contains English labels. Customer-entered variables are not recursively translated. Switching language rerenders the existing form without remounting it.

Built-in statement exports fix their locale in the export snapshot and idempotency input. Missing legacy locale means Chinese. Customer templates preserve their wording and existing system annotations. Live delivery printing translates system labels and untouched defaults; custom layout text stays as entered. Archived delivery copies retain their Chinese archive rules.
