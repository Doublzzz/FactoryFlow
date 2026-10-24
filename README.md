<p align="center">
  <img src="docs/images/logo.svg" width="72" height="72" alt="">
</p>

<h1 align="center">交有数 FactoryFlow</h1>

<p align="center">
  <strong>给小工厂的订单、送货与对账工具。</strong><br>
  有工厂一线业务人员直接参与制作，早期版本已在工厂日常使用。<br>
  不用先导入资料，从第一张订单开始用；数据和识别都在你自己的电脑上。
</p>

<p align="center">
  <a href="https://github.com/Doublzzz/FactoryFlow/releases/tag/v0.1.0-preview.1"><img alt="Windows 预览版" src="https://img.shields.io/github/v/release/Doublzzz/FactoryFlow?include_prereleases&label=Windows%20%E9%A2%84%E8%A7%88%E7%89%88&color=5b6ee1"></a>
  <img alt="数据只在本机" src="https://img.shields.io/badge/%E6%95%B0%E6%8D%AE-%E5%8F%AA%E5%9C%A8%E6%9C%AC%E6%9C%BA-2f8f5b">
  <img alt="界面 中文和 English" src="https://img.shields.io/badge/%E7%95%8C%E9%9D%A2-%E4%B8%AD%E6%96%87%20%7C%20English-555">
  <a href="LICENSE"><img alt="MIT 许可" src="https://img.shields.io/github/license/Doublzzz/FactoryFlow?color=555"></a>
</p>

<p align="center">
  <a href="#下载试用">下载试用</a> · <a href="#一张订单怎么走完">看看怎么用</a> · <a href="README.en.md">English</a>
</p>

![一张订单就能上手：拖入采购单，录单时新建客户，对照原件核对后生成订单（合成演示）](docs/images/readme/zh-first-order.gif)

<p align="center"><sub>合成演示，0.5 倍速节选，省略了识别等待和部分逐项核对。<a href="docs/README-SCREENSHOTS.md">演示说明</a></sub></p>

## 为什么做成这样

**不用先建档，从第一张订单开始。** 很多小厂手上没有整理好的客户名单和物料表。拿到订单拍张照、或者照着纸质单填，客户在录单时顺手新建；同样的货反复出现了，再把它收录进物料池。已经有物料表的，也可以先导入。

**数据只在这台电脑上。** 离线安装包自带数据库和本地识别模型。订单原件、送货记录、对账文件都存在本机，不经过云端，不用注册在线账号，断网也能用。

**每一步由人确认，数量对得上。** 识别只给候选，人对照原件核对后才生成订单。件、千克、米分开算，数量和金额用精确小数；改订单会另存新版本，旧版本和凭证都留着。

## 这些细节来自真实的小厂

交有数有真实工厂的一线业务人员参与制作，早期版本已经在工厂日常使用。产品围绕具体业务问题展开：这张单还欠多少？送出去的货，客户认了多少？哪些放进本月对账，哪些还要跟进？

- **一张订单分几次送，剩多少要看得清。** 每批按订单行登记数量、打印送货单；录错后作废这次送货，未交数量随之恢复，原记录仍能查到。
- **件数、重量和长度，各有各的账。** 同一张单可以有件、千克、米，未交数量按行计算，不把不同单位硬加成一个总数。
- **客户的料号，和自家的料号对得上。** 同一物料可对应不同客户的不同料号，文本编号的前导零保留。先录单、之后补入物料池，也保留原订单上的名称、规格和料号。
- **月底按客户的表格交账。** 客户 Excel 模板可上传、对应字段并核对预览；对账行还能填客户的外部单号，方便双方找到同一笔送货。
- **只认可了一部分，剩下的还要继续跟。** 客户认可、待核对、本期结算分别记录；已认可的数量可以分期结算，需要转期的余量由人明确安排。客户认可和正式结算都不代表钱已到账。
- **回头核对时，找得到原件和当时的版本。** 订单修改会另存版本，已固定的结算凭证保留；送货记录、客户反馈和相关文件都有据可查。

## 下载试用

Windows 10/11 x64：到 [v0.1.0-preview.1 预览版](https://github.com/Doublzzz/FactoryFlow/releases/tag/v0.1.0-preview.1)下载 `FactoryFlow-Windows-x64-v0.1.0-preview.1.zip`（约 174 MB）。

1. 完整解压 ZIP，双击 `安装.cmd`，按提示阅读第三方组件条件并完成安装。
2. 打开桌面的 FactoryFlow 入口，首次启动时设置工厂名称和本地账号。
3. 用仓库里的[合成采购单](samples/purchase-orders/README.md)试一遍录单、分批送货和对账。

不用另装 Python、数据库或 Node.js。安装、备份和故障处理见[离线使用说明](docs/FACTORY-OFFLINE-GUIDE.txt)；同版源码、第三方源码材料和 `SHA256SUMS.txt` 都在版本页面。

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

## 当前限制

- 这是新整理打包的 **Windows 开发者预览**。在全新 Windows 上的安装、原生 Excel 分页、实体打印和更多单据版式的兼容性还在验证，见[验证记录](docs/VERIFICATION.md)。
- 只支持单机使用，不提供局域网多人访问。
- 预览阶段，升级到新版本时能否直接沿用数据暂不保证。不要把唯一一份真实业务数据放在预览版里，记得定期备份。
- 只支持 **CNY**。客户认可和正式结算不代表收到付款，对账单和送货单不是税务发票。不含库存、付款、多币种和海外税务。
- 界面支持简体中文和 English；内置对账 Excel 和送货打印有英文版。客户名称、料号和原件文字保持原样，客户模板保留原文，归档的送货副本目前用中文版式。
- 备份和导出文件里有业务资料，需要自己妥善保管。构建输入与第三方材料见[分发说明](docs/DISTRIBUTION.md)。

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

[MIT](LICENSE)：允许商用和闭源再分发，须保留版权与许可声明。字体及依赖遵循各自许可，见[第三方材料清单](THIRD-PARTY-NOTICES.md)。
