<p align="center"><strong>简体中文</strong> · <a href="README.en.md">English</a></p>

<p align="center">
  <img src="docs/images/logo.svg" width="72" height="72" alt="">
</p>

<h1 align="center">交有数 FactoryFlow</h1>

<p align="center">
  <strong>给小工厂老板和办公室人员的订单、送货与对账工具。</strong><br>
  工厂一线业务人员直接参与制作，早期版本已在工厂日常使用。<br>
  不用先导入资料，从第一张订单开始用；核心业务和识别默认在你自己的电脑上。
</p>

<p align="center">
  <a href="https://github.com/Doublzzz/FactoryFlow/releases/tag/v0.1.0-preview.3"><img alt="Windows 预览版" src="https://img.shields.io/github/v/release/Doublzzz/FactoryFlow?include_prereleases&label=Windows%20%E9%A2%84%E8%A7%88%E7%89%88&color=5b6ee1"></a>
  <img alt="默认本机运行" src="https://img.shields.io/badge/%E6%95%B0%E6%8D%AE-%E9%BB%98%E8%AE%A4%E6%9C%AC%E6%9C%BA-2f8f5b">
  <img alt="界面 中文和 English" src="https://img.shields.io/badge/%E7%95%8C%E9%9D%A2-%E4%B8%AD%E6%96%87%20%7C%20English-555">
  <a href="https://github.com/Doublzzz/FactoryFlow/actions/workflows/verify.yml"><img alt="CI" src="https://github.com/Doublzzz/FactoryFlow/actions/workflows/verify.yml/badge.svg?branch=main"></a>
  <a href="LICENSE"><img alt="MIT 许可" src="https://img.shields.io/github/license/Doublzzz/FactoryFlow?color=555"></a>
</p>

<p align="center">
  <a href="#下载试用">下载试用</a> · <a href="#一张订单怎么走完">看看怎么用</a> · <a href="#后续模块与定制需求">定制需求</a>
</p>

![一张订单就能上手：拖入采购单，录单时新建客户，对照原件核对后生成订单（合成演示）](docs/images/readme/zh-first-order.gif)

<p align="center"><sub>合成演示，0.5 倍速节选，省略了识别等待和部分逐项核对。<a href="docs/README-SCREENSHOTS.md">演示说明</a></sub></p>

## 谁适合用

主要面向小型生产工厂的老板，以及负责跟单、安排送货和月末对账的办公室人员：每天要记清客户订了什么、已经交了多少、还欠多少，以及哪些已经获得客户认可、安排在本期结算。

如果贸易公司只需要管理客户订单、分批交货和对账，也可以试用这套流程。preview.3 包含可选成品库存、供应商采购、原料库存和小生产流程；BOM、自动排程和成本毛利管理尚未覆盖。

## 为什么做成这样

**不用先建档，从第一张订单开始。** 很多小厂手上没有整理好的客户名单和物料表。拿到订单拍张照、或者照着纸质单填，客户在录单时顺手新建；同样的货反复出现了，再把它收录进物料池。已经有物料表的，也可以先导入。

**核心业务默认在这台电脑上。** 离线安装包自带数据库和本地识别模型。订单原件、送货记录、对账文件都存在本机；默认不经过云端，不用注册在线账号，断网也能用。可选 MCP 的数据流见下方接入说明。

**每一步由人确认，数量对得上。** 识别只给候选，人对照原件核对后才生成订单。件、千克、米分开算，数量和金额用精确小数；改订单会另存新版本，旧版本和凭证都留着。

## 这些细节来自真实的小厂

工厂一线业务人员直接参与了交有数的制作，早期版本已经在工厂日常使用。产品围绕具体业务问题展开：这张单还欠多少？送出去的货，客户认了多少？哪些放进本月对账，哪些还要跟进？

- **一张订单分几次送，剩多少要看得清。** 每批按订单行登记数量、打印送货单；录错后作废这次送货，未交数量随之恢复，原记录仍能查到。
- **件数、重量和长度，各有各的账。** 同一张单可以有件、千克、米，未交数量按行计算，不把不同单位硬加成一个总数。
- **客户的料号，和自家的料号对得上。** 同一物料可对应不同客户的不同料号，文本编号的前导零保留。先录单、之后补入物料池，也保留原订单上的名称、规格和料号。
- **月底按客户的表格交账。** 客户 Excel 模板可上传、对应字段并核对预览；对账行还能填客户的外部单号，方便双方找到同一笔送货。
- **只认可了一部分，剩下的还要继续跟。** 客户认可、待核对、本期结算分别记录；已认可的数量可以分期结算，需要转期的余量由人明确安排。客户认可和正式结算都不代表钱已到账。
- **回头核对时，找得到原件和当时的版本。** 订单修改会另存版本，已固定的结算凭证保留；送货记录、客户反馈和相关文件都有据可查。

## 下载试用

Windows 10 1903+ / Windows 11 x64 开发者预览：[v0.1.0-preview.3](https://github.com/Doublzzz/FactoryFlow/releases/tag/v0.1.0-preview.3)。下载 `FactoryFlow-Windows-x64-v0.1.0-preview.3.zip`，包含采购与原料、小生产、CNY/USD、英文安装和可选成品库存。

1. 完整解压 ZIP，双击 `安装.cmd`；英文用户运行 `Install.cmd`。按提示阅读第三方组件条件并完成安装。
2. 打开桌面的 FactoryFlow 入口，首次启动时设置工厂名称和本地账号。
3. 用仓库里的[合成采购单](samples/purchase-orders/README.md)试一遍录单、分批送货和对账。

无需在线账号，也不用另装 Python、数据库或 Node.js。安装、备份和故障处理见[中文使用说明](docs/FACTORY-OFFLINE-GUIDE.txt)或[English guide](docs/FACTORY-OFFLINE-GUIDE-en.txt)。同版应用源码、第三方源码材料和 `SHA256SUMS.txt` 在版本页面。

请使用新的数据目录试用，保留现有安装及备份；本次不提供业务数据库的原地升级。旧 [preview.1](https://github.com/Doublzzz/FactoryFlow/releases/tag/v0.1.0-preview.1) 继续保留。检查结果与边界见[当前状态](docs/STATUS.md)和[验证记录](docs/VERIFICATION.md)。

## 一张订单怎么走完

**1. 收单。** 上传订单照片、截图或 PDF，左边看原件、右边核对识别出的明细；也可以直接手填。

![对照采购单人工核对后的四行明细，还需勾选确认才生成订单（合成演示）](docs/images/readme/zh-02b-manually-reviewed.png)

<sub>上图是人工核对后的结果。识别只提出候选，表格解析还不稳定，需要对照原件校正或补录。<a href="docs/README-SCREENSHOTS.md">原始识别结果</a></sub>

**2. 分批送货。** 按订单行登记每次送了多少，待交数量自动减掉；作废一次送货会退回原数量，记录保留。

![分批送货后的待交清单，各行保留自己的单位（合成演示）](docs/images/readme/zh-03-open-lines.png)

<sub>同一张合成订单：120 件交了 30 件，剩 90 件；35.5 千克交了 10.25 千克，剩 25.25 千克。</sub>

**3. 跟客户对账。** 按期间把送货明细汇成对账草稿，记录发给客户的依据和客户反馈，区分已认可、待核对和暂缓的数量。

**4. 固定本期结算。** 确认这一期的数量与金额，符合条件的余额显式转到下期，早期凭证都保留。

**5. 导出和归档。** 用内置格式或客户自己的 Excel 模板导出对账单，订单原件、送货副本和对账文件统一整理归档。

## 库存、采购、生产与币种

**成品库存按需启用。** 不用库存也能完成订单、送货和对账；需要时按成品开账，记录入库和实盘。送货可同步扣减，也可明确跳过、留待核对；账面不足时须确认后才允许负余额。作废送货按原库存流水冲回，旧送货不追扣，未开账也不等于零库存。原料与成品分开管理；BOM、批次多仓和成本核算尚未覆盖。

**CNY 和 USD 分别记账。** 每张订单、每张对账单保持一种币种，订单确认后币种不可更改；同一客户同一期间的两种币种分别对账，不相加、不换汇。界面语言与币种独立，不新增收付款、发票或海外税务规则。

**采购与原料。** 采购单支持图片/PDF、Excel 导入或手工填写，人工核对后保存和打印；保存采购不自动收料。可按采购单分批收料，也可直接收料；原料明确开账后登记领用、分次退料、实盘与流水。采购价格可留空，不推断付款事实。

**小生产流程。** 从订单明细安排生产，关联领退料，分批登记合格与报废，合格完工同步入成品库存。完工不等于送货，不自动按 BOM 扣料，也不自动排产。

**2026-11-04 交付状态。** 本版所基于的版本已完成非测试本机部署并跑通，由维护者确认；公开包另外完成其标明的检查。真实业务覆盖、实体打印、不同单据 OCR 和其他设备兼容继续逐项验收，详见[版本说明](docs/RELEASE-NOTES.md)。上方演示截图来自早期版本，用于说明基本流程。

## 当前限制

- 当前版本为 **Windows 开发者预览**，安装与业务流程的检查记录见[验证记录](docs/VERIFICATION.md)。
- 只支持单机使用，不提供局域网多人访问。
- 预览阶段，升级到新版本时能否直接沿用数据暂不保证。不要把唯一一份真实业务数据放在预览版里，记得定期备份。
- preview.3支持 **CNY / USD**，不含汇率换算和收付款。客户认可和正式结算不代表收到付款，对账单和送货单不是税务发票，不提供海外税务合规。
- 界面默认简体中文，可切换 English；内置对账 Excel、送货打印和新归档支持英文，生成时固定语言。客户名称、料号、原件、客户模板及自定义版式文字保持原样；旧导出和归档不因切换语言而改变。
- 备份和导出文件里有业务资料，需要自己妥善保管。构建输入与第三方材料见[分发说明](docs/DISTRIBUTION.md)。

## 后续模块与定制需求

成品库存、采购与原料、小生产已进入 preview.3。如果你需要其他业务流程，或希望按自己的工厂流程定制功能，欢迎[联系我讨论](https://github.com/Doublzzz/FactoryFlow/issues/new?template=feature_request.yml)。可以先说说谁来用、现在怎么处理、希望解决什么问题，再一起确认范围。

目前通过 GitHub 功能建议接收需求。公开留言只需概述场景，不要附真实客户单据或敏感业务资料。

## 可选 AI / MCP 接入（源码版）

需要让 AI 帮忙查“这个客户还有哪些订单没交”时，可单独配置 [MCP 适配器](apps/mcp/README.md)。默认六个只读工具：未交订单、成品库存、对账状态、客户名称检索、完整订单详情、确认中断后的回执核对。客户检索支持分页；订单可按客户＋单号或 ID 查找；中断后使用原编号核对，结果未知不会自动重建订单。

适配器需与本次源码后端配套运行，**不包含在现有 preview.3 Windows 安装包中**。只有显式配置独立的合成测试 operator，才增加预览和确认两个工具，合计八个；写工具仅供独立合成环境试验，操作者须核验数据隔离，不能用于真实业务；没有库存、送货或对账写工具。

启用后，查询结果会提供给所连接的 MCP 客户端；是否再发送到云端 AI 取决于你选择的客户端和服务。请按需要授权，数量和金额保持原单位、币种及精确小数字符串；对账金额不是到账金额。见 [接入说明](apps/mcp/README.md)、[English setup](apps/mcp/README.en.md) 和[验证范围](docs/VERIFICATION.md)。

## 从源码开发

需要 Windows、Node.js 24（准确范围见 `package.json`）、uv、Python 3.14 和独立的 PostgreSQL，首次安装开发依赖需要联网。按[本地运行说明](docs/LOCAL-OPERATIONS.md)准备依赖、配置、显式迁移和首个本地账号后再启动；启动本身不会自动迁移或重置数据。

```powershell
npm run typecheck
npm run contracts:check
npm run build
```

更多背景：[业务规则](docs/PRODUCT-SPEC.md) · [架构](docs/ARCHITECTURE.md) · [术语表](docs/GLOSSARY.zh-en.md) · [隐私与发布范围](docs/PRIVACY.md)

## 开发与反馈

AI 协助编写了代码、文档和测试；需求、范围和发布由维护者决定。产品里的业务写入始终由使用者确认。

欢迎在 [GitHub Issues](https://github.com/Doublzzz/FactoryFlow/issues/new/choose) 反馈：哪一步不好懂？哪种单位或单据版式难核对？请用合成数据复现，不要上传真实客户原件、价格、账号、数据库或完整日志。安全漏洞请按[安全反馈说明](SECURITY.md)私下报告。

## 许可

[MIT](LICENSE)：允许商用和闭源再分发，须保留 `Copyright (c) 2026 Doublzzz` 及完整许可声明。字体及依赖遵循各自许可，见[第三方材料清单](THIRD-PARTY-NOTICES.md)。
