# Current business rules / 当前业务规则

## Orders and evidence

A person reviews source documents or enters order lines and confirms an order. Revisions retain earlier evidence. Item codes, names, specifications, source units and exact quantities are business data. Do not infer missing units or rewrite source text through translation.

## Deliveries

Normal deliveries consume outstanding order quantities. Partial delivery is supported; over-delivery is rejected. Voiding reverses the original delivery under the existing state/version rules and retains its history. Quantities with different units are not added together.

## Reconciliation

A draft gathers delivery quantities, prices and explicit adjustments. Sending evidence, customer feedback, accepted quantities, pending review, current-period selection and finalization are distinct facts. Finalization fixes the selected accepted quantities and amounts; it is not a payment event. Eligible accepted or pending-review balances may be carried to a later period through explicit commands. Earlier finalized evidence remains unchanged.

All quantities and amounts use exact decimals. Each order and statement uses CNY or USD, selected explicitly and independently of interface language. CNY is the default. A confirmed order's currency cannot change; the same customer and period use separate statements for different currencies. Amounts in different currencies are never added or converted. The existing tax modes are tax-included, no-additional-tax and explicitly added tax. These modes do not establish foreign tax compliance.

## Item catalog

The catalog records item identity and internal/customer codes, not inventory. Orders can operate without a catalog link. Later linking does not rewrite confirmed source fields or historical delivery/reconciliation evidence. Batch xlsx/CSV import requires a reviewed plan with explicit new/link/skip decisions; duplicates and conflicts are not silently overwritten.

## Files and outputs

The supported uploaded order sources are image/PDF files. Local extraction produces candidates for human review; it does not authorize business writes. Customer-owned Excel templates are uploaded and mapped with restrictions; unsupported features must fail explicitly.

Working-file organization creates fixed copies. It is not a replacement for full database/object backups or formal reconciliation. Generated historical files remain in their original language and state.

## Optional finished-goods inventory

Inventory is optional. Open each finished item's balance from a physical count, then record receipts or later counts with immutable movements. An unopened item has no recorded balance; it is not zero stock. Historical deliveries are not deducted retroactively.

A delivery either deducts linked finished-goods stock or explicitly skips stock handling for later review. A shortage requires explicit confirmation before a book balance can go negative. Delivery, stock movements, audit and idempotency results commit together. Voiding a delivery reverses its original movements. An external return reference on a statement does not itself create a stock return.

## Supplier purchasing and raw-material inventory

Finished goods and raw materials have immutable kinds and separate inventory use. A supplier can be disabled without deleting historical snapshots. A purchase has one supplier and fixed material/quantity/unit snapshots. Creating it does not receive stock. Receiving may refer to purchase lines or be direct from a supplier; partial receipts cannot exceed a purchase's outstanding quantity. Closing a purchase stops new receipts without rewriting past receipts.

Open raw-material balances explicitly. Receipt, issue, return and count movements remain immutable. Issues cannot exceed the available balance; partial returns refer to the original issue and cannot exceed the unreturned quantity. Voiding a receipt reverses the whole receipt atomically, requires a reason and sufficient current balance, and is not a real supplier return. Versioned counts reject stale concurrent changes. Transactions retain ownership, audit, idempotency and database concurrency safeguards.

## Reviewed purchase documents

Sales-order sources and purchase sources have distinct purposes. Image/PDF extraction and Excel mapping produce candidates only; people verify supplier, items, units, quantities, optional prices and currency. An unknown price stays unknown and is distinct from zero. Money uses Decimal and the document's CNY/USD currency. Saving a purchase and its source reference is one transaction and must not create a receipt. A source cannot create another purchase through a second key or concurrent request. Print views use saved snapshots and do not write business records.

## Small production workflow

Plan from an order line linked to a finished item. Reference raw-material issues and partial returns explicitly; no automatic BOM consumption is inferred. Record good and scrapped quantities in batches. Accepted good completion and the finished-goods receipt commit together, with audit and idempotency. Good completion cannot exceed the remaining plan. A whole completion can be voided with a reason only when its linked stock can be reversed; a production order can be closed explicitly. Completion is not delivery and does not consume the customer's outstanding delivery quantity. Earlier business evidence remains unchanged.

## Deliberately absent

BOM, automatic scheduling, batches, multiple warehouses, costing, exchange rates, invoices, payment processing, overseas accounting/tax and a general plugin platform are outside this preview. Preparing this source does not establish production acceptance or authorize publication. The synthetic order examples are documents for demonstrations, not ready-made customer data for a real business database.
