# Status / 当前状态

## v0.1.0-preview.2 — 2026-10-26

This source targets [v0.1.0-preview.2](https://github.com/Doublzzz/FactoryFlow/releases/tag/v0.1.0-preview.2), a Windows developer preview. The [first GitHub Actions run](https://github.com/Doublzzz/FactoryFlow/actions/runs/40316043350) passed on commit `579fdcb544aa4910a8838bae112d5d1ebe06d059`. Release availability is shown on the release page; preview.1 remains available. The public-source update starts from `5cfd96a382e61e52cc49d51cb17f3a89b8584f74`.

本源码对应 preview.2 Windows 开发者预览，已取得实际 GitHub CI 通过结果；下载状态以版本页面为准，旧 preview.1 保留。

The preview.2 source includes:

- Optional finished-goods opening balances, receipts, physical counts and immutable movements. Deliveries can deduct stock or explicitly skip it; shortages require confirmation, and voiding reverses the original movements. Historical deliveries are not deducted retroactively. Raw materials, purchasing, production/BOM and costing remain outside scope.
- CNY and USD orders and statements, with fixed order currency after confirmation and separate statements per currency. Interface language does not change currency. There is no exchange conversion, payment processing or foreign tax compliance.
- English Windows installation, first-use local account setup and operating commands, alongside the Chinese entry points. See the [English offline guide](FACTORY-OFFLINE-GUIDE-en.txt).
- English built-in outputs and new archives with a fixed generation language. Customer-entered text, customer templates, custom layout wording and older generated files retain their original content.

本版包含可选成品库存、CNY/USD 分币种订单与对账、英文 Windows 独立使用入口及新英文归档；不扩展到采购、原材料、生产/BOM、成本、收付款、换汇或海外税务。

The schema head is `0015_order_currencies`, following `0014_finished_goods_inventory`; preview.1 used `0013_material_pool`. Migration is an explicit administration operation. Import and startup do not migrate or reset a database. See [local operations](LOCAL-OPERATIONS.md) before running source or handling a backup.

当前迁移头为 `0015_order_currencies`。升级必须显式执行，启动不会自动迁移或重置数据；预览版继续保留 README 中的备份与兼容性限制。

The independent public-candidate run passed 1013 Python tests with no failures or skips. Source/contract/build checks and final Windows ZIP installation, CNY/USD workflows, optional inventory, OCR execution and backup/restore checks passed. The final package build is `e5b753f6d3711c4c`. Exact evidence and limits are in [VERIFICATION](VERIFICATION.md); GitHub CI results are linked above. Reproduction commands and PostgreSQL setup are in [CONTRIBUTING](../CONTRIBUTING.md).

公开候选独立通过 1013 项测试，最终安装包及恢复核对通过；详细范围见验证记录。GitHub CI 已实际通过，记录见上方链接。合成检查不等于工厂业务验收。
