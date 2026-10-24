# Runtime infrastructure

The Windows development helper expects a separately prepared PostgreSQL binary distribution at `.tools/postgresql-18.6-4/pgsql`. It creates a loopback-only synthetic development cluster with separate admin/runtime roles and randomly generated local credentials in ignored files.

Current schema head is `0013_material_pool`. Migration and account creation are explicit; application startup does neither. See [local operations](../docs/LOCAL-OPERATIONS.md).

`compose.dev.yaml` is a separate, unvalidated Docker development option. It requires a user-provided environment password and does not itself create application roles, run migrations or initialize an account. No database files or credential configuration are supplied in this repository.
