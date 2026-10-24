# FactoryFlow / 交有数

[简体中文](README.md) · English

An order and delivery workspace for small factories: take an order, deliver it in batches, see what remains, and reconcile with the customer.

**A local Windows developer preview.** For people exploring the workflow, reviewing the source, or trying synthetic examples. It has not passed production or factory-use acceptance.

![Outstanding order lines after partial deliveries, preserving quantities and units — synthetic demo](docs/images/readme/en-03-open-lines.png)

One synthetic order: 30 of 120 PCS delivered leaves 90 PCS; 10.25 of 35.5 KG delivered leaves 25.25 KG. Quantities with different units stay separate.

## Start with an order

You do not need a complete customer directory or item catalog first. Create a customer while entering an order, confirm lines without catalog links, and add reusable items as repeat orders arrive.

![Start with one order: create a customer inline, review and confirm the order, then organize items later — synthetic demo, Chinese UI](docs/images/readme/zh-first-order.gif)

Chinese UI; synthetic example, slowed to 0.5× (24 seconds). Recognition waiting and parts of manual review are omitted; this is not a measure of order-entry time.

1. **Review the order.** Upload an image or PDF and check the extracted candidate against its source, or enter the order manually.
2. **Record partial deliveries.** Track delivered and outstanding quantities by order line. Voiding a delivery reverses its original quantities and preserves its history.
3. **Reconcile with the customer.** Gather delivery lines into a draft, record sending evidence and feedback, and distinguish accepted, pending-review and deferred quantities.
4. **Finalize the period.** Fix selected quantities and amounts, then explicitly carry eligible balances forward while retaining earlier evidence.
5. **Keep the paperwork.** Export built-in or customer-template Excel files and organize copies of orders, delivery notes and reconciliation files.

![Four candidate lines manually reviewed against the source; confirmation is still required — synthetic demo](docs/images/readme/en-02b-manually-reviewed.png)

This is a **manually corrected candidate**, not evidence of successful automatic extraction. For this synthetic sample, the raw table parser produced 3 structured candidate rows in Chinese and 0 in English. Zero rows does not mean OCR read no text. Table parsing remains unreliable, and both samples needed corrections or manual entry. The [capture notes](docs/README-SCREENSHOTS.md) document that distinction.

The [bilingual synthetic purchase orders](samples/purchase-orders/README.en.md) include source previews and reference line items. Companies, contacts, identifiers and transaction data are fictional; no real customer documents are included.

## Product choices

- **People confirm business actions.** Extraction proposes candidates; a person confirms the order. Customer acceptance and period finalization are separate actions too.
- **Build the catalog through orders.** Keep internal and customer item codes, create entries manually, or review an xlsx/UTF-8 CSV import. Catalog entries do not create stock; linking an item later does not rewrite confirmed source fields.
- **Keep exact quantities and history.** Preserve source units and use exact decimals for quantities and money. Confirmed revisions stay immutable. Each business transaction commits its audit records, idempotency result and ledger effects together.

## What works, and where it stops

The web UI supports Simplified Chinese and English. New built-in reconciliation Excel exports and live delivery printing support English. Customer names, item codes, notes and source documents retain their original text. Customer templates retain their wording; archived delivery copies currently use the Chinese layout.

The current currency is **CNY only**. Customer acceptance and finalized reconciliation do not mean payment received. Delivery notes and statements are not tax invoices. Inventory, payment processing, multiple currencies and foreign tax compliance are outside the current capabilities.

The preview release will provide source, a Windows offline package, third-party source materials and checksums together under Releases. See [distribution notes](docs/DISTRIBUTION.md) for build inputs and verification scope. Native Excel behavior, physical printing, real-document compatibility and factory use need separate acceptance. Prepared core operations do not require cloud AI or an online account; initial dependency installation needs internet access.

## Local development

Use Windows, Node.js 24 (see `package.json` for the exact range), uv, Python 3.14 and a separate PostgreSQL instance. Follow the [local operations guide](docs/LOCAL-OPERATIONS.md) for dependencies, configuration, explicit migrations and the first local account before starting the service. Startup does not migrate or reset data automatically.

Frontend and contract checks, once the development environment is ready:

```powershell
npm run typecheck
npm run contracts:check
npm run build
```

These checks do not establish real-world business or factory acceptance. See the [verification record](docs/VERIFICATION.md) for tested scope and limitations.

## Development and feedback

AI assisted with code, documentation and tests. The maintainer controls requirements, scope and releases. People using the product still confirm business writes.

After publication, feedback through GitHub Issues is welcome: Which step is hard to understand? Which units or document layouts are difficult to review? Share synthetic reproduction steps; keep customer originals, prices, credentials and databases private.

Further reading: [business rules](docs/PRODUCT-SPEC.md) · [architecture](docs/ARCHITECTURE.md) · [glossary](docs/GLOSSARY.zh-en.md) · [privacy and release scope](docs/PRIVACY.md)

## License

This project uses the [MIT License](LICENSE), permitting commercial use and closed-source redistribution with the copyright and license notices retained. Fonts and dependencies retain their own licenses; see [third-party materials](THIRD-PARTY-NOTICES.md).
