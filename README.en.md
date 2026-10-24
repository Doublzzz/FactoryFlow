# FactoryFlow / 交有数

[简体中文](README.md) · English

An order and delivery workspace for small factories: take an order, deliver it in batches, see what remains, and reconcile with the customer. The offline package processes business data and OCR on your computer, without uploading them to the cloud.

**Windows developer preview**

![Outstanding order lines after partial deliveries, preserving quantities and units — synthetic demo](docs/images/readme/en-03-open-lines.png)

One synthetic order: 30 of 120 PCS delivered leaves 90 PCS; 10.25 of 35.5 KG delivered leaves 25.25 KG. Quantities with different units stay separate.

## Download and try

For Windows 10/11 x64, download `FactoryFlow-Windows-x64-v0.1.0-preview.1.zip` (about 174 MB) from the [v0.1.0-preview.1 release](https://github.com/Doublzzz/FactoryFlow/releases/tag/v0.1.0-preview.1).

1. Extract the whole ZIP, run `安装.cmd`, and follow the prompts to review the third-party component terms and install.
2. Open the FactoryFlow desktop shortcut. On first launch, set your factory name and local account.
3. Try entering an order, making a partial delivery and preparing a statement with the [synthetic purchase orders](samples/purchase-orders/README.en.md).

Python, PostgreSQL and local OCR models are included. You do not need to install Python, Node.js or a database separately; core operations work offline once the ZIP has been downloaded and extracted. The [offline guide](docs/FACTORY-OFFLINE-GUIDE.txt) covers installation, backups and troubleshooting; its current text and installer prompts are in Chinese. Application source, third-party source materials and `SHA256SUMS.txt` are on the same release page.

## Start with an order

You do not need a complete customer directory or item catalog first. Create a customer while entering an order, confirm lines without catalog links, and add reusable items as repeat orders arrive.

![English first-run screen with file upload and manual order entry — synthetic demo](docs/images/readme/en-01-first-run.png)

![Start with one order: create a customer inline, review and confirm the order, then organize items later — synthetic demo, Chinese UI](docs/images/readme/zh-first-order.gif)

Chinese UI; a 24-second synthetic demo at 0.5× speed, with recognition waiting and parts of manual review omitted. [Full capture notes](docs/README-SCREENSHOTS.md)

1. **Review the order.** Upload an image or PDF and check the extracted candidate against its source, or enter the order manually.
2. **Record partial deliveries.** Track delivered and outstanding quantities by order line. Voiding a delivery reverses its original quantities and preserves its history.
3. **Reconcile with the customer.** Gather delivery lines into a draft, record sending evidence and feedback, and distinguish accepted, pending-review and deferred quantities.
4. **Finalize the period.** Fix selected quantities and amounts, then explicitly carry eligible balances forward while retaining earlier evidence.
5. **Keep the paperwork.** Export built-in or customer-template Excel files and organize copies of orders, delivery notes and reconciliation files.

![Four candidate lines manually reviewed against the source; confirmation is still required — synthetic demo](docs/images/readme/en-02b-manually-reviewed.png)

The screenshot shows a manually reviewed candidate. Recognition only proposes candidates; table parsing is still unreliable and requires corrections or manual entry against the original. [Raw extraction results and capture notes](docs/README-SCREENSHOTS.md)

The [bilingual synthetic purchase orders](samples/purchase-orders/README.en.md) include source previews and reference line items. Companies, contacts, identifiers and transaction data are fictional; no real customer documents are included.

## Product choices

- **People confirm business actions.** Extraction proposes candidates; a person confirms the order. Customer acceptance and period finalization are separate actions too.
- **Build the catalog through orders.** Keep internal and customer item codes, create entries manually, or review an xlsx/UTF-8 CSV import. Catalog entries do not create stock; linking an item later does not rewrite confirmed source fields.
- **Keep exact quantities and history.** Preserve source units and use exact decimals for quantities and money. Confirmed revisions stay immutable. Each business transaction commits its audit records, idempotency result and ledger effects together.

## What works, and where it stops

The web UI supports Simplified Chinese and English. New built-in reconciliation Excel exports and live delivery printing support English. Customer names, item codes, notes and source documents retain their original text. Customer templates retain their wording; archived delivery copies currently use the Chinese layout.

The current currency is **CNY only**. Customer acceptance and finalized reconciliation do not mean payment received. Delivery notes and statements are not tax invoices. Inventory, payment processing, multiple currencies and foreign tax compliance are outside the current capabilities.

This is a developer preview and has not passed production or factory-use acceptance. See the [verification record](docs/VERIFICATION.md) for completed engineering checks. Installation on a clean Windows machine, native Excel behavior, physical printing and real-document compatibility still need acceptance. Use a new trial data directory; this release does not provide an in-place upgrade for an existing business database.

The offline package runs on one computer and does not provide multi-user access over a local network. Backups and exported files still contain business information and need to be kept private. See the [distribution notes](docs/DISTRIBUTION.md) for build inputs and third-party materials.

## Local development

Development from source requires Windows, Node.js 24 (see `package.json` for the exact range), uv, Python 3.14 and a separate PostgreSQL instance. Installing development dependencies for the first time needs internet access. Follow the [local operations guide](docs/LOCAL-OPERATIONS.md) for dependencies, configuration, explicit migrations and the first local account before starting the service. Startup does not migrate or reset data automatically. These development tools are not required to try the Windows package.

Frontend and contract checks, once the development environment is ready:

```powershell
npm run typecheck
npm run contracts:check
npm run build
```

## Development and feedback

AI assisted with code, documentation and tests. The maintainer controls requirements, scope and releases. People using the product still confirm business writes.

Use [GitHub Issues](https://github.com/Doublzzz/FactoryFlow/issues/new/choose) to report problems or suggest improvements: Which step is hard to understand? Which units or document layouts are difficult to review? Reproduce issues with synthetic data; do not upload real customer documents, prices, credentials, databases or full logs. Report security vulnerabilities privately using the [security policy](SECURITY.md).

Further reading: [business rules](docs/PRODUCT-SPEC.md) · [architecture](docs/ARCHITECTURE.md) · [glossary](docs/GLOSSARY.zh-en.md) · [privacy and release scope](docs/PRIVACY.md)

## License

This project uses the [MIT License](LICENSE), permitting commercial use and closed-source redistribution with the copyright and license notices retained. Fonts and dependencies retain their own licenses; see [third-party materials](THIRD-PARTY-NOTICES.md).
