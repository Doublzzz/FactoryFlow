# Release notes / 版本说明

## Source update, no new installer / 源码更新，未发新安装包 — 2026-11-09

- Optional stdio MCP adapter: six default viewer queries; synthetic operator preview/confirmation remain explicit opt-in (eight tools total). / 可选 stdio MCP，默认六项只读；合成订单预览与确认须显式启用。
- Customer-name pagination with Unicode case folding; exact order ID or customer-plus-number lookup, including fully delivered/deleted orders and revision references. / 客户名称分页检索，按订单 ID 或客户＋单号查完整详情。
- Original confirmation receipts remain queryable after response loss/process restart. Unknown outcomes never authorize automatic re-entry; current order/readback status is separate from the committed receipt. / 中断或重启后核对原回执，未知不自动重建，原确认与当前状态分开。
- Bilingual setup and privacy boundaries, contract projections and MCP CI checks. No schema migration or change to the owning business write commands. / 补齐中英文接入、隐私边界、生成合同与 MCP CI，无迁移及业务写命令语义变更。

The adapter requires the matching source backend and is not part of the existing preview.3 ZIP. No new Windows package or release tag accompanies this update. See [setup](../apps/mcp/README.en.md) and [verification](VERIFICATION.md). / 现有 preview.3 安装包不含本次新增接口；本轮没有更换安装包或新增 tag。

## v0.1.0-preview.3 — 2026-11-04

This public release follows the delivered version `b4e2d4b6ea86c4b2`. The maintainer confirmed on 2026-11-04 that the delivered version was deployed and ran on a non-test local installation. The public package build is `e8afc55a99d89c32` and is separately verified; it does not claim to be the identical frozen private package.

本公开版基于已交付的 `b4e2d4b6ea86c4b2`。维护者于 2026-11-04 确认该交付版本已在非测试本机部署跑通；公开包单独编号、单独记录检查，不冒充原冻结包的相同字节。

CI final result confirmed on 2026-11-04: [public run 41860994186](https://github.com/Doublzzz/FactoryFlow/actions/runs/41860994186) **completed / success**, with **1,235 passed / 14 skipped**. The earlier pending metadata has resolved. Windows package build `e8afc55a99d89c32` and download bytes are unchanged.

公开仓库 CI 已结束并成功：1,235 项通过、14 项按平台条件跳过。此前等待最终状态的记录已收口；安装包仍为已验证版本，工厂实际业务、打印与 OCR 效果继续按使用验收。

Changes since preview.2 / 相比 preview.2：

- Supplier purchasing, partial/direct receipts, raw-material opening balances, issues, partial returns, counts and immutable movements. / 供应商采购、分批或直接收料、原料开账、领用、分次退料、实盘与流水。
- Small production workflow: order-line planning, linked material issues/returns, good/scrap completion and atomic finished-goods receipt. / 从订单明细安排生产，关联领退料，记录合格与报废，完工同事务入成品库存。
- Reviewed image/PDF/Excel purchase input, optional CNY/USD prices and print views; saving a purchase does not receive stock. / 采购图片、PDF、Excel 核对导入，可空价格和打印；保存采购不自动收料。
- Up to five independent order files per selection, clearer purchase validation and unsaved-draft handling, improved OCR header/currency/specification spacing, material selection and narrow-screen account layout. / 每次最多选五份独立订单文件，改善采购校验与草稿保护、OCR 表头/币种/规格空格、物料选择及窄屏账号布局。
- Local administrator-password recovery, simpler login, and process-level UTF-8 support for Chinese Windows paths without changing global region settings. / 本机管理员密码恢复、简洁登录和中文路径进程级 UTF-8，无需修改系统区域设置。

Schema: `0018_purchase_documents` (preview.2: `0015_order_currencies`). Migration remains an explicit operation; startup does not migrate or reset data. Keep existing installations and backups; use a separate data directory for public-preview evaluation. This release does not perform an automatic upgrade of an existing business installation.

验收边界：维护者确认的是上述交付版本的非测试本机运行；不表示所有真实业务、所有单据 OCR、实体打印或所有 Windows 设备均已验收。公开候选工程检查另见 [VERIFICATION](VERIFICATION.md)。不含 BOM、自动排程、成本、收付款、换汇、税务合规、批次多仓或局域网多人部署。

Acceptance remains bounded: local operation is confirmed for the delivered version, not every real workflow, OCR document, physical printer or Windows device. Public-package checks are recorded separately. No BOM, automatic scheduling, costing, payments, currency conversion, tax compliance, batch/multi-warehouse or network multi-user deployment is added.

The public source keeps the existing removal of private demo-only login controls. MIT is unchanged: redistribution must retain `Copyright (c) 2026 Doublzzz` and the full permission notice. Third-party terms remain separate. See [DISTRIBUTION](DISTRIBUTION.md) for package/source identity and [LICENSE](../LICENSE) for the license.
