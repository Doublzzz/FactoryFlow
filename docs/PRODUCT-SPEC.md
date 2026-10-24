# Current business rules / 当前业务规则

## Orders and evidence

A person reviews source documents or enters order lines and confirms an order. Revisions retain earlier evidence. Item codes, names, specifications, source units and exact quantities are business data. Do not infer missing units or rewrite source text through translation.

## Deliveries

Normal deliveries consume outstanding order quantities. Partial delivery is supported; over-delivery is rejected. Voiding reverses the original delivery under the existing state/version rules and retains its history. Quantities with different units are not added together.

## Reconciliation

A draft gathers delivery quantities, prices and explicit adjustments. Sending evidence, customer feedback, accepted quantities, pending review, current-period selection and finalization are distinct facts. Finalization fixes the selected accepted quantities and amounts; it is not a payment event. Eligible accepted or pending-review balances may be carried to a later period through explicit commands. Earlier finalized evidence remains unchanged.

All quantities and amounts use exact decimals. Current currency is CNY. The existing tax modes are tax-included, no-additional-tax and explicitly added tax. These modes do not establish foreign tax compliance.

## Item catalog

The catalog records item identity and internal/customer codes, not inventory. Orders can operate without a catalog link. Later linking does not rewrite confirmed source fields or historical delivery/reconciliation evidence. Batch xlsx/CSV import requires a reviewed plan with explicit new/link/skip decisions; duplicates and conflicts are not silently overwritten.

## Files and outputs

The supported uploaded order sources are image/PDF files. Local extraction produces candidates for human review; it does not authorize business writes. Customer-owned Excel templates are uploaded and mapped with restrictions; unsupported features must fail explicitly.

Working-file organization creates fixed copies. It is not a replacement for full database/object backups or formal reconciliation. Generated historical files remain in their original language and state.

## Deliberately absent

Inventory, a general plugin platform, overseas accounting/tax, multi-currency, invoices, payment processing, production deployment and public release are not implemented or authorized by this snapshot. The synthetic order examples are documents for demonstrations, not ready-made customer data for a real business database.
