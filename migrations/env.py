"""Only explicit operator/test migration commands supply a connection."""

from alembic import context

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Use scripts/manage.py migrate with an explicit private admin configuration")
context.configure(connection=connection, target_metadata=None)
with context.begin_transaction():
    context.run_migrations()
