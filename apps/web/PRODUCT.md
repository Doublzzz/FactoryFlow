# Product UI context

FactoryFlow helps small-factory operators review customer orders, track outstanding quantities, record deliveries and reconcile with customers. The business rules are in `docs/PRODUCT-SPEC.md`; the source and tests define implemented behavior.

The default workspace starts with open orders. Each item keeps customer/order identity, item code, name, specification, ordered quantity, delivered quantity, remaining quantity and unit together. Different units are never summed. Source documents and extracted candidates are compared before a person confirms an order.

The item catalog stores identity, not stock. Reconciliation distinguishes sending evidence, customer acceptance, pending review, selected quantities and finalization. Finalization does not mean payment. Working-file organization preserves fixed copies and does not replace backups.

Use synthetic data for demos. Do not infer OCR accuracy, time savings or production use from illustrations. Chinese and English interfaces retain user-entered text and existing output bytes. Keep statuses, errors, access controls and transaction safeguards visible and correct.
