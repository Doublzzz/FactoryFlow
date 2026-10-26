# Local operation / 本地运行

Run these PowerShell commands from a fresh clone's root on Windows x64. This creates a separate synthetic development environment. Do not point it at a business database or private imported directory. The commands do not install a Windows service.

## Dependencies

Prepare [Node.js 24](https://nodejs.org/en/download) (`>=24.19.0 <25`, see `.node-version`) and [uv](https://docs.astral.sh/uv/getting-started/installation/). Both commands must be available in this PowerShell session. uv can download the Python 3.14 interpreter; a separate global Python installation is unnecessary.

```powershell
node --version
uv --version
$env:UV_PYTHON_INSTALL_DIR = Join-Path (Get-Location) '.tools\python'
uv sync --locked --python 3.14
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
npm ci --ignore-scripts
if ($LASTEXITCODE -ne 0) { throw 'Node dependency installation failed' }
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Web build failed' }
```

For the local database, use the Windows x64 PostgreSQL **18.6** binary ZIP linked by [EDB](https://www.enterprisedb.com/download-postgresql-binaries), the archive provider linked by [PostgreSQL](https://www.postgresql.org/download/windows/). The helper expects this exact directory layout:

```text
.tools/postgresql-18.6-4/pgsql/bin/pg_ctl.exe
```

The following archive and checksum were checked on 2026-10-23. The checksum records the downloaded bytes; it is not an independent signature from EDB. If the provider replaces the archive, review the new version instead of bypassing the check.

```powershell
New-Item -ItemType Directory -Path .tools -Force | Out-Null
Invoke-WebRequest 'https://sbp.enterprisedb.com/getfile.jsp?fileid=1260609' -OutFile .tools/postgresql-18.6-4.zip
$archiveHash = (Get-FileHash .tools/postgresql-18.6-4.zip -Algorithm SHA256).Hash
if ($archiveHash -ne 'E2246BA91D22345BC3D017586C09EDE52D9DF180B1EEB480F050445F1CAD84E2') { throw 'PostgreSQL archive differs from the checked version' }
Expand-Archive .tools/postgresql-18.6-4.zip -DestinationPath .tools/postgresql-18.6-4
& .tools/postgresql-18.6-4/pgsql/bin/postgres.exe --version
```

The ZIP is approximately 385 MB. Its extracted files, Python, installed packages and runtime data remain ignored local files. This source preview contains no installers or OCR model binaries. `infra/compose.dev.yaml` remains an unvalidated alternative; it does not prepare the role/configuration used below.

## New synthetic development environment only

Check that loopback ports **55433** (database) and **8100** (web/API) are free. If either is occupied, stop here and inspect the owner; do not terminate an unrelated process. The database helper currently uses the fixed port 55433.

```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 55433, 8100 }
.\.venv\Scripts\python.exe scripts/dev-database.py prepare
if ($LASTEXITCODE -ne 0) { throw 'Database preparation failed' }
.\.venv\Scripts\python.exe scripts/manage.py migrate --admin-config .runtime/development/admin.json
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
.\.venv\Scripts\python.exe scripts/manage.py setup --admin-config .runtime/development/admin.json --factory "Synthetic Factory" --username synthetic-admin
if ($LASTEXITCODE -ne 0) { throw 'Account setup failed' }
.\.venv\Scripts\python.exe scripts/serve-local.py --config .runtime/development/app.json
```

Setup prompts for a new local password without echoing it. Do not paste credentials into issues or commit generated configuration. A prepare command refuses to replace an existing environment. Current schema head is `0015_order_currencies`; startup does not migrate.

Open `http://127.0.0.1:8100/` and sign in with `synthetic-admin` and the password you just chose. The helper binds PostgreSQL and the API to loopback. `/api/v1/health/live` checks the process; `/api/v1/health/ready` checks configured schema/object readiness.

Stop the foreground API with Ctrl+C, then stop this database with:

```powershell
.\.venv\Scripts\python.exe scripts/dev-database.py stop
```

For an already prepared environment, use `start` (or `status`) in place of `stop`, then run `serve-local.py` again. Do not rerun `prepare`, migrations or first-account setup for a routine restart. Do not edit ownership markers to bypass checks.

## Data, OCR and backups

Runtime configuration, credentials, databases, uploads and object storage stay outside version control under ignored private paths. Windows OCR depends on supported installed language resources; RapidOCR needs a separately prepared runtime/model set. Missing OCR is an explicit error; manual order entry remains available. Successful OCR does not guarantee correct table rows. Real-document accuracy and physical printing require acceptance.

`scripts/backup-local.py create` creates a new backup; `restore` restores into a new database/object directory after hash checks. It does not authorize replacing a live environment. Backups contain private data and account password hashes and must not be uploaded to this source repository.

## Verification

```powershell
.\.venv\Scripts\python.exe scripts/check_architecture.py
.\.venv\Scripts\python.exe scripts/export-openapi.py --check
npm run contracts:check
npm run typecheck
node --test scripts/test-i18n.mjs
node scripts/check-i18n.mjs
npm run build
```

Database tests require the disposable cluster prepared above. The suite creates and drops its own random databases on that cluster:

```powershell
$env:FACTORYFLOW_TEST_ADMIN_CONFIG = Join-Path (Get-Location) '.runtime\development\admin.json'
.\.venv\Scripts\python.exe -m pytest
```

Omitted configuration causes skips, not successful business validation. Never use real business credentials or a customer database to run tests. Native OCR tests additionally depend on the Windows host and its language resources.

The preview.1 fresh-clone check used Windows 11 x64, Node 24.19.0, uv 0.13.5, managed Python 3.14.9 and PostgreSQL 18.6. It used newly downloaded dependencies and a new database on an existing Windows machine. See [verification](VERIFICATION.md) for preview.2 results and the separate GitHub Actions status. These checks do not establish a clean-machine installer, Windows 10, macOS or factory-use acceptance.
