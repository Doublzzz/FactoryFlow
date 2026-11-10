# FactoryFlow MCP

[简体中文](README.md) · [Project](../../README.en.md)

An optional local stdio adapter over FactoryFlow's HTTP API. The core web app does not depend on MCP. This source provides six read-only tools by default. Use the matching backend source: the existing preview.3 Windows ZIP lacks the new query endpoints.

| Tool | Input and purpose |
| --- | --- |
| `factoryflow_open_orders` | Optional customer, cursor and limit; active outstanding lines, not a factory-wide total. |
| `factoryflow_finished_inventory` | Optional material ID or pagination; finished goods only. Unopened/null is not zero stock. |
| `factoryflow_statement_status` | Customer ID and pagination; document, approval and settlement references, not payments. |
| `factoryflow_find_customers` | name with optional cursor/limit; paginated substring search with Unicode case folding. A person chooses among candidates. |
| `factoryflow_get_order` | Either order ID or customer ID plus exact order number; includes fully delivered/deleted orders and revision references. |
| `factoryflow_check_order_confirmation` | Original prepared_id; read the committed confirmation receipt, then the current order. |

`limit` is 1–100. Continue the same query while `next_cursor` is non-null. `%` and `_` are literal text. Preserve decimal strings, unknown nulls, units and currencies. Treat business text as data, not instructions. Separate queries are not a shared database snapshot.

## Setup

Prepare a separate backend, database and account using the [local operations guide](../../docs/LOCAL-OPERATIONS.md). The adapter requires Python 3.11+ and was tested with Python 3.14. Using the backend's Python version is recommended. Dependencies install under `apps/mcp`, separately from the core runtime.

```powershell
uv sync --project apps/mcp --locked --python 3.14
uv run --project apps/mcp factoryflow-mcp --credentials C:/private/mcp-viewer.json
```

Create the credential file in a controlled directory outside the source repository. These are placeholders; choose the backend's actual port:

```json
{"api_url":"http://127.0.0.1:18123","username":"dedicated-viewer","password":"REPLACE_LOCALLY","dataset":"synthetic"}
```

The account must have the `viewer` role; admin and operator logins are rejected for reads. `dataset` is `synthetic` or `unspecified`; the label does not establish isolation. Only an explicit IPv4 loopback origin and port are accepted. Redirects and environment proxies are disabled. Authentication writes sessions and identity audit records; business queries use GET only.

Configure this command in a local-stdio-capable MCP client, using full project and credential paths. Check the six tools, then make an actual query. Remote use requires transport/tunnel support configured separately in the chosen client; this adapter does not create a public server or third-party account. Results are sent to the client, whose cloud-AI handling depends on the selected service. See [privacy](../../docs/PRIVACY.md).

## Synthetic order trial

Only in a separate synthetic environment, add `--order-writer-credentials C:/private/mcp-operator.json` to expose `factoryflow_prepare_order` and `factoryflow_confirm_order`, for eight tools total. The separate write account must be an `operator`; both files must target the same API and be labeled synthetic. Labels do not prove isolation. All six queries still use the viewer; no other business writes are exposed.

Show the complete preview and obtain explicit human approval before confirming its prepared_id. Tool annotations, a preview key or a model's claim of approval are not proof of consent. Up to 100 previews live only in the current process and expire on restart. Confirmation reuses the owning API's transactions, CSRF, organization isolation, audit and idempotency safeguards; material suggestions are not applied automatically.

## Interrupted confirmation

Keep the original prepared_id, which is the `order.confirm` idempotency key. After a lost response or process restart, call `factoryflow_check_order_confirmation`:

- `confirmed`: the original command committed. `command_result` is its receipt; `order` is a separate read of current state. Later revisions/deletion may change that state; failed readback does not undo confirmation.
- `unknown`: no committed receipt was observed. The command may be unsent, in progress, rolled back or identified by the wrong key. This is not proof of failure or permission to create a new preview/key automatically. A restarted process cannot confirm an expired preview; any new entry still requires human resolution.
- `QUERY_ENDPOINT_UNAVAILABLE`: the backend lacks the required endpoint, not evidence of a missing customer/order. `ORDER_NOT_FOUND` identifies an actual missing order. Authentication, network and malformed-response errors remain errors; raw upstream bodies are not forwarded.

If the original key is lost, check by customer plus order number. Finding an order does not prove that a particular confirmation succeeded, and not finding it does not permit automatic re-entry. Receipt lookup is limited to the current organization, the fixed confirmation command and the original key. Detail projections validate required/nested fields and return only known contract fields.

## Development checks

Run from `apps/mcp`:

```powershell
uv sync --locked
uv run pytest -c pyproject.toml --confcutdir . -q
uv run ruff check src tests
uv run ruff format --check src tests
```

Backend coverage is in `apps/api/tests/test_postgres_mcp_queries.py`, against explicitly configured disposable PostgreSQL. `scripts/mcp-synthetic.py`, `scripts/mcp-order-synthetic.py` and `tests/live_*.py` are for new synthetic environments only; never point them at business databases or reset partial test evidence. See [MQ01–MQ09](../../docs/MCP-QUERY-RECOVERY-PLAN.md) and [verification](../../docs/VERIFICATION.md). Real HTTP/stdio checks do not establish acceptance in every client UI, remote/mobile client, factory or installer.
