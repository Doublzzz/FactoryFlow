# Verification scope / 验证范围

The source snapshot follows completed local synthetic checks. It is not evidence of factory production, native Excel pagination, physical printer output, overseas suitability or public release readiness.

The bilingual work passed 101 distinct Python cases in focused groups covering built-in Excel, delivery layouts, PostgreSQL export replay/conflicts, customer template preservation and historical archive behavior. Three Node language tests, explicit-message/placeholder checks, architecture, generated contract checks, TypeScript checking and an isolated web build passed. Browser checks covered Chinese/English switching with retained drafts and source text, a 390px viewport, read-only views and an interrupted export followed by authentication recovery and the same-request retry.

Existing local business query snapshots and object hashes were compared during the previous local preview update. Those private snapshots, runtime state and historical logs are deliberately not included here. This is a summary of the verified scope, not a new full-suite CI result.

The repository's purchase-order PDFs/PNGs/JSON/CSVs are newly generated synthetic examples. Their arithmetic, cross-language consistency, metadata and final rendered pages are checked separately. The CSVs are reference line data and are not a promise of direct order CSV import. The item-catalog CSV is intended for the existing reviewed material-import flow.

Reproduce focused checks using the commands in LOCAL-OPERATIONS.md. PostgreSQL/OCR/platform-dependent skips must remain visible. No automatic cloud workflow is enabled by this snapshot.

## Fresh source preview check — 2026-10-23

A new clone on Windows 11 x64 used freshly downloaded dependencies, managed Python 3.14.9, Node 24.19.0 and PostgreSQL 18.6. A new loopback cluster was prepared, explicitly migrated to `0013_material_pool`, and given a new synthetic local account through the interactive setup command. Real browser sign-in reached the empty first-order workspace. No original project database, objects or virtual environment was reused.

The final full Python run passed **901 tests with no failures or skips** in 546.17 seconds. During preparation, a stale test expected migration `0008` after upgrading to current head. Only that test was changed to use the existing `REVISION` constant; its rollback and evidence-preservation checks were retained. Two focused migration tests and the final full run passed after the change.

Architecture checks, the 9 architecture tests, generated OpenAPI and TypeScript checks, frontend typecheck/build, 3 language tests and message checks also passed. The final language scan covered 1388 translations and 1236 literal message calls. The build retains an approximately 559 kB main JavaScript chunk warning.

After removing separate preview entry points and their dedicated tests, **14 browser/business checks were rerun on the final UI**. They passed ordinary local login, expired-session recovery with unsaved input, manual order confirmation, exact delivery/void quantities, replay after lost responses, a 390px layout, cold restart, backup/restore and immutable evidence downloads. There were no unexpected external requests or browser runtime errors. The prepared browser test used the Codex-bundled Playwright runner and installed Chrome; neither is included in the source archive.

The six README images come from the earlier real Chinese/English product flows, with human correction explicitly recorded. See [FIRST-ORDER-UI.md](FIRST-ORDER-UI.md) and [README-SCREENSHOTS.md](README-SCREENSHOTS.md) for those image and OCR evidence boundaries. This cleanup removed optional preview controls; it did not change the normal product screens shown in the images.

The project uses MIT. License text and project-package license metadata agree, and locked dependency versions remain unchanged. Dependency licenses remain separate.

This is an independent source environment on an existing Windows host. It is not a clean-machine installer test, a cross-platform result, an exhaustive security/license audit, or factory acceptance. Installation needs internet access; OCR engine/model availability and real-document quality remain separate concerns. See [LOCAL-OPERATIONS.md](LOCAL-OPERATIONS.md) and [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md).
