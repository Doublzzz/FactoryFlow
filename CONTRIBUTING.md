# Contributing / 参与贡献

## English

Read [README](README.en.md), [STATUS](docs/STATUS.md), [AGENTS.md](AGENTS.md), and the relevant business contract before changing code. This guide describes the preview.2 source candidate; the published preview.1 package contains an earlier version. The [verification workflow](.github/workflows/verify.yml) is prepared locally; its presence does not mean GitHub Actions has run or passed.

### Set up and check

Use Python 3.14, Node 24 (the exact version is in `.node-version`), and uv (CI pins `0.12.21`). From the repository root:

```text
uv sync --locked
npm ci
npm run build
uv run pytest -ra
uv run ruff check apps/api/src apps/api/tests scripts migrations tests
uv run ruff format --check apps/api/src apps/api/tests scripts migrations tests
node --test scripts/test-i18n.mjs
node scripts/check-i18n.mjs
uv run python scripts/check_architecture.py
uv run python scripts/export-openapi.py --check
npm run contracts:check
npm run typecheck
git diff --check
```

For database tests, prepare a **dedicated synthetic PostgreSQL 18 cluster**, with `ff_admin` as administrator and `ff_runtime` as the application login. Follow [local operations](docs/LOCAL-OPERATIONS.md) for the Windows setup, explicit migrations, and account creation. Never reuse a business database. Point `FACTORYFLOW_TEST_ADMIN_CONFIG` at a private JSON file containing `admin_url` (host `127.0.0.1`, database `postgres`) and `runtime_password`. The fixture creates and drops disposable databases. Backup tests also need PostgreSQL 18 `pg_dump` and `pg_restore` at `.tools/postgresql-18.6-4/pgsql/bin`.

Without that environment variable, PostgreSQL tests skip: this is partial coverage. The Linux CI workflow supplies a PostgreSQL 18 service and matching client tools; Windows OCR, junction, and locking checks skip on Linux under their existing markers. CI does not replace independent Windows installation, browser/OCR/printing checks, or factory acceptance. To run the configured application, use the commands in [README](README.md) and local operations; startup does not migrate a database automatically.

### Change contracts and send a PR

Change server DTOs first, then run `uv run python scripts/export-openapi.py` and `npm run contracts:generate`. Review the generated OpenAPI/TypeScript diff; do not edit generated contracts by hand. Keep module boundaries and transaction, audit, idempotency, and Decimal safeguards. New business behavior needs concrete synthetic examples and focused tests; see the [execution contract](AGENTS.md).

Keep each PR focused. Describe the problem, resulting behavior, checks actually run, skips, and remaining limits. Preserve unrelated work. Include only synthetic examples: no customer names, order IDs, prices, business documents, database dumps, credentials, runtime files, or local evidence. Do not commit `.tools`, `.venv`, `node_modules`, or private configuration. Review screenshots, logs, and generated files before sharing. Report vulnerabilities privately through [GitHub security reporting](https://github.com/Doublzzz/FactoryFlow/security/advisories/new); do not disclose secrets or exploit details in a public issue.

## 简体中文

修改前先读 [README](README.md)、[STATUS](docs/STATUS.md)、[AGENTS.md](AGENTS.md) 和相关业务合同。本指南面向 preview.2 源码候选；已发布的 preview.1 安装包为较早版本。[验证工作流](.github/workflows/verify.yml) 已在本地准备，文件存在不代表 GitHub Actions 已执行或通过。

### 准备与检查

使用 Python 3.14、Node 24（准确版本见 `.node-version`）和 uv（CI 固定为 `0.12.21`）。在仓库根目录执行上方命令，先构建网页，再运行测试、风格、架构、合同和类型检查。

数据库测试必须使用**独立的 PostgreSQL 18 合成环境**：管理员为 `ff_admin`，应用登录角色为 `ff_runtime`。Windows 准备、显式迁移和首次账号设置见[本地运行说明](docs/LOCAL-OPERATIONS.md)，不得复用业务库。将 `FACTORYFLOW_TEST_ADMIN_CONFIG` 指向私有 JSON 配置，其中包含 `admin_url`（主机必须为 `127.0.0.1`、数据库必须为 `postgres`）和 `runtime_password`。测试夹具会创建并删除独立测试库；备份测试还需要 `.tools/postgresql-18.6-4/pgsql/bin` 下的 PostgreSQL 18 `pg_dump`、`pg_restore`。

未设置该环境变量时，PostgreSQL 用例会跳过，只能算部分覆盖。Linux CI 工作流配置 PostgreSQL 18 服务与同主版本客户端；Windows 原生 OCR、junction 和锁检查按现有标记跳过。CI 不能代替独立 Windows 安装、浏览器/OCR/打印检查或工厂验收。实际启动按 README 和本地运行说明操作，启动不会自动迁移数据库。

### 合同变更与 PR

先改服务端 DTO，再执行 `uv run python scripts/export-openapi.py` 和 `npm run contracts:generate`，审查生成的 OpenAPI/TypeScript 差异，不手改生成合同。保留模块边界、事务、审计、幂等及 Decimal 保障。新增业务行为先明确合成示例，再做聚焦测试，详见[执行合同](AGENTS.md)。

每个 PR 聚焦一个问题，说明改后行为、实际检查、跳过项和限制，保留无关改动。样例只用合成数据；不要提交客户名称、订单号、价格、业务文件、数据库备份、凭据、运行目录或本机证据，也不要提交 `.tools`、`.venv`、`node_modules` 和私有配置。分享前检查截图、日志与生成文件。安全漏洞通过 [GitHub 私密漏洞报告](https://github.com/Doublzzz/FactoryFlow/security/advisories/new) 提交，不在公开 issue 披露凭据或利用细节。
