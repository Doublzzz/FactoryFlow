# First-order UI / 从第一张订单开始

This change makes the first order the entry point: upload a source document or enter it manually, create the customer during entry, and build a reusable item catalog later. It changes frontend presentation and copy without changing server contracts, database schema or business rules.

| Area | Behavior |
|---|---|
| Empty workspace | Shows upload and manual entry. Customer creation and item import remain optional. |
| File selection | The drop area retains a real file input and accessible labels; dropped files carry into the order-review page. |
| Outstanding orders | Desktop and mobile show delivered progress while retaining each line's original quantity and unit. Ratios use decimal-string/BigInt calculations. |
| Order details | Shows how many lines are linked to the catalog. Per-line catalog actions expand on request; confirmed source fields remain unchanged. |
| Mobile navigation | Five labeled destinations; the overflow menu exposes file organization, customers and the catalog. |
| Language | Chinese and English labels share the same business actions; source text is preserved. |

The integrated candidate also corrects progress-row alignment, the item-control grid, optional address accessibility, English labels and outdated browser-test selectors. These fixes were checked against the real local backend, using independent synthetic databases.

The 2026-10-23 verification included TypeScript/build checks, API-contract and architecture checks, language checks, and 14 isolated browser/business checks. Separate Chinese and English screenshot runs exercised upload, manual correction, order confirmation, partial deliveries, catalog links and a reconciliation draft at desktop and mobile widths. See [README-SCREENSHOTS.md](README-SCREENSHOTS.md).

OCR is still a review aid: the demonstrated raw Chinese result had 3 structured rows and the English result had 0. Both were corrected manually before confirmation. These are synthetic local checks, not factory-use or recognition-quality acceptance. Source-clone setup and remaining platform limits are described in [LOCAL-OPERATIONS.md](LOCAL-OPERATIONS.md).
