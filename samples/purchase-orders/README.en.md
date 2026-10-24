# Synthetic purchase-order examples

[简体中文](README.md)

All parties, addresses, contacts, identifiers and prices are fictional. Every PDF/PNG is visibly marked as synthetic. These are not customer originals, binding purchase documents or tax invoices. Contact domains use `.example`; no phone numbers, bank details or real signatures are included.

- [Chinese PDF](purchase-order-zh.pdf) / [PNG](purchase-order-zh.png)
- [English PDF](purchase-order-en.pdf) / [PNG](purchase-order-en.png)
- [Canonical structured data](purchase-order.json)
- [Chinese reference CSV](purchase-order-zh.csv) / [English reference CSV](purchase-order-en.csv)
- [Item catalog import CSV](material-catalog.csv)

The two languages describe the same order; do not import both as separate orders. Four lines demonstrate PCS/KG/M, item codes with leading zeroes and decimal quantities. The currency is CNY, with tax included and no additional tax.

## Suggested demonstration

1. Upload one PDF/PNG version, then manually verify the extraction candidate. The CSVs are reference line data, not an implemented order-CSV import format.
2. Choose or create an explicitly synthetic customer and confirm the four lines. The total is 2949.20 CNY; quantities with different units are not summed.
3. Deliver 30 PCS, 80 PCS, 10.25 KG and 12 M. Remaining quantities are 90, 160, 25.25 and 36 respectively. This delivery's illustrative value is 784.40 CNY.
4. Prepare a reconciliation draft, export in either language and record customer feedback through the actual UI. Acceptance and finalization do not mean payment.
5. Demonstrate voiding in a separate scenario before reconciliation occupancy prevents it; do not claim finalized deliveries can be unconditionally voided.

The catalog CSV can use the existing reviewed item-import flow. It creates/links catalog records, not inventory. Party/address/terms blocks on the sample document illustrate a common PO layout; they do not claim that every field is stored by the application.

## For README authors and reviewers

Use the bilingual source documents and synthetic data for new screenshots of the real UI. Keep synthetic labels. Do not claim actual customers, production adoption, overseas accounting, OCR accuracy or measured time savings. `generate.py` recreates the PDFs using the optional authoring package ReportLab and the repository's OFL font; this is not an application runtime dependency.
