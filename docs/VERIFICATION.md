# Verification scope / 验证范围

## preview.2 public candidate — 2026-10-26

This candidate was assembled on public commit `5cfd96a382e61e52cc49d51cb17f3a89b8584f74`. Its source and packages are prepared locally; nothing from this preparation has been committed, pushed or released. The GitHub Actions workflow is configured for push/PR, but has not run on GitHub. YAML and embedded Python syntax checks do not count as a remote CI pass.

The independent public checkout used Windows 11 x64, Python 3.14.7, Node 24.19.0 and PostgreSQL 18.6. Locked dependencies were installed into new local environments from existing caches. The existing PostgreSQL developer binaries were reused with a new, disposable loopback cluster; no business database or original checkout environment was reused. The complete public Python suite passed **1013 tests, with no failures or skips, in 637.53 seconds**. This includes PostgreSQL inventory/currency transaction, reversal, replay/conflict, ownership, concurrent enforcement, migration rollback and backup/restore cases.

Ruff checks and formatting passed for 221 Python files. Architecture boundaries, OpenAPI/TypeScript contract checks, frontend typecheck and build, four Node language tests, and whitespace checks passed. The translation scan checked 1487 translations and 1330 literal message calls. The built main JavaScript chunk is 584.70 kB and retains Vite's size warning. This preparation does not add code splitting.

The final Windows ZIP has build ID `e5b753f6d3711c4c`, 174367899 bytes and SHA-256 `068bd73827985fa31ca53bd5989dff8c40b96f4045f7f7b7a4ac8a72c3f3c317`. Its 7013 archive members passed CRC and manifest checks. Application, migrations, web output, operating scripts, guides and licenses matched the public candidate byte-for-byte (147 files). Package/source membership checks found no runtime databases, private runtime credentials, private demo entry points or development-machine paths in application files.

Of 6853 third-party runtime/notice files, 6847 match preview.1 byte-for-byte. The other six differ only in RECORD hashes for virtual-environment console launchers that are not included in the package. Library code, binaries, model files, notices, dependency versions and the reviewed optional-component omission are unchanged. The matching third-party source attachment is reused without byte changes; its SHA-256 is `abbacc7cd95a1f3dd42e97ba57ab92c2bf99b9ad559c29f68aabdb8d9eee9322`.

The final ZIP was extracted and installed into a separate directory. Checks used bundled Python, an isolated PATH, external HTTP(S) proxies pointed at an unused loopback port, and fresh synthetic data directories. English installation and first-account setup passed; desktop shortcut creation was suppressed in this automated check. Chrome exercised normal local login, a 100 PCS USD order, a 30 PCS partial delivery and a saved 70.37 USD draft. The installed service then completed formal reconciliation, English Excel and archive generation, and backup/restore with identical evidence bytes. An additional installed inventory scenario opened 50 PCS, received 20, delivered 30, skipped a 10 PCS delivery, reversed the tracked delivery and counted 65 PCS. All stock entries and the final balance were identical after restore. The restored browser showed 70 PCS outstanding on the first order and 65 PCS in stock, with no console errors.

The public installed-package script separately passed blank first setup, the CNY order/delivery/formal-statement/Excel flow, actual packaged OCR inference, restart persistence and restore into a new data home. The English OCR sample returned a USD candidate but **zero parsed item rows**; rows still needed manual entry. Successful inference is not proof of usable order extraction.

All services created for these checks were stopped and private evidence retained outside the source tree. The work did not upgrade an existing installation or business database. These are checks on an existing Windows host, not clean-machine Windows 10/11 acceptance, a new Linux result, macOS support, native Excel pagination, physical printing or factory-use acceptance. Use a new data directory for this preview. GitHub Actions execution and publication remain pending.

公开候选本轮独立通过 1013 项 Python 测试，零失败、零跳过；最终安装包完成中英文流程、USD 正式对账、库存及备份恢复验证。GitHub CI 尚未运行，也尚未发布。OCR 可运行但该英文测试单未提取出明细，仍须人工录入；不把合成检查当作工厂使用验收。

## Historical preview.1 evidence

The source snapshot follows completed local synthetic checks. It is not evidence of factory production, native Excel pagination, physical printer output, overseas suitability or public release readiness.

The bilingual work passed 101 distinct Python cases in focused groups covering built-in Excel, delivery layouts, PostgreSQL export replay/conflicts, customer template preservation and historical archive behavior. Three Node language tests, explicit-message/placeholder checks, architecture, generated contract checks, TypeScript checking and an isolated web build passed. Browser checks covered Chinese/English switching with retained drafts and source text, a 390px viewport, read-only views and an interrupted export followed by authentication recovery and the same-request retry.

Existing local business query snapshots and object hashes were compared during the previous local preview update. Those private snapshots, runtime state and historical logs are deliberately not included here. This is a summary of the verified scope, not a new full-suite CI result.

The repository's purchase-order PDFs/PNGs/JSON/CSVs are newly generated synthetic examples. Their arithmetic, cross-language consistency, metadata and final rendered pages are checked separately. The CSVs are reference line data and are not a promise of direct order CSV import. The item-catalog CSV is intended for the existing reviewed material-import flow.

Reproduce focused checks using the commands in LOCAL-OPERATIONS.md. PostgreSQL/OCR/platform-dependent skips must remain visible. No automatic cloud workflow was enabled at this earlier baseline; the preview.2 candidate's prepared workflow is described above.

## Fresh source preview check — 2026-10-23

A new clone on Windows 11 x64 used freshly downloaded dependencies, managed Python 3.14.9, Node 24.19.0 and PostgreSQL 18.6. A new loopback cluster was prepared, explicitly migrated to `0013_material_pool`, and given a new synthetic local account through the interactive setup command. Real browser sign-in reached the empty first-order workspace. No original project database, objects or virtual environment was reused.

The final full Python run passed **901 tests with no failures or skips** in 546.17 seconds. During preparation, a stale test expected migration `0008` after upgrading to current head. Only that test was changed to use the existing `REVISION` constant; its rollback and evidence-preservation checks were retained. Two focused migration tests and the final full run passed after the change.

Architecture checks, the 9 architecture tests, generated OpenAPI and TypeScript checks, frontend typecheck/build, 3 language tests and message checks also passed. The final language scan covered 1388 translations and 1236 literal message calls. The build retains an approximately 559 kB main JavaScript chunk warning.

After removing separate preview entry points and their dedicated tests, **14 browser/business checks were rerun on the final UI**. They passed ordinary local login, expired-session recovery with unsaved input, manual order confirmation, exact delivery/void quantities, replay after lost responses, a 390px layout, cold restart, backup/restore and immutable evidence downloads. There were no unexpected external requests or browser runtime errors. The prepared browser test used the Codex-bundled Playwright runner and installed Chrome; neither is included in the source archive.

The six README images come from the earlier real Chinese/English product flows, with human correction explicitly recorded. See [FIRST-ORDER-UI.md](FIRST-ORDER-UI.md) and [README-SCREENSHOTS.md](README-SCREENSHOTS.md) for those image and OCR evidence boundaries. This cleanup removed optional preview controls; it did not change the normal product screens shown in the images.

The project uses MIT. License text and project-package license metadata agree, and locked dependency versions remain unchanged. Dependency licenses remain separate.

This is an independent source environment on an existing Windows host. It is not a clean-machine installer test, a cross-platform result, an exhaustive security/license audit, or factory acceptance. Installation needs internet access; OCR engine/model availability and real-document quality remain separate concerns. See [LOCAL-OPERATIONS.md](LOCAL-OPERATIONS.md) and [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md).
