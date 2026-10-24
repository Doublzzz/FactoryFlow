# Bilingual README and demo brief / 中英文README演示说明

## 中文

目标：让第一次看到项目的人理解“小工厂如何收单、分批送货、查看待交并与客户对账”。在README.md和README.en.md中使用同一业务场景与同一事实边界，文字自然，不把中文逐词硬译成英文。

素材在 `samples/purchase-orders/`。两种语言的采购单是同一张合成订单，包含四行、前导零料号、三个单位和小数数量。可先展示源单，再在独立合成环境中录入、送货、对账并拍摄当前产品的真实界面。不能把采购单版式截图当作系统已实现页面；PDF里的采购条款和地址也不代表系统已存储这些字段。

建议README结构：一句话用途、采购单到业务界面的简短演示、三至五张关键截图、当前功能/明确边界、安装运行、验证与隐私。中文/英文截图分别切换真实界面语言。使用前后明确的数量：120/30/90 PCS、240/80/160 PCS、35.5/10.25/25.25 KG、48/12/36 M；本次送货金额784.40 CNY。客户认可与正式结算不能称为付款。

保留“合成演示”标记。不要使用真实客户原件、生产数据库、账号文件或私人模板；不要加入未经测量的准确率、效率或真实使用案例。库存、海外财务、公开发布和许可证选择不属于README视觉修改。

## English

Explain the concrete small-factory workflow: receive an order, record partial deliveries, see what remains, and reconcile with the customer. Keep the Chinese and English READMEs aligned on facts while writing each language naturally.

Use the shared synthetic source order in `samples/purchase-orders/`. Capture current application screens in a separate synthetic environment. The PDF is an input-document illustration, not a screenshot of implemented UI. Preserve the SYNTHETIC labels, exact decimals, units and CNY currency.

Suggested sequence: source purchase order, reviewed order, outstanding quantities after partial delivery, reconciliation draft/export. Add three to five useful screenshots rather than a gallery of every control. Include setup requirements, supported behavior and limits. Acceptance/finalization must not be described as payment.

Do not use customer documents, private runtime files or historical screenshots. Do not invent adoption, accuracy or productivity claims. README/UI review does not authorize inventory, overseas finance, public publication or a license decision.
