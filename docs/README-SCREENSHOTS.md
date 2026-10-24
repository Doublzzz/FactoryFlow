# README 截图 / README screenshots

使用 `samples/purchase-orders/` 的中英文合成采购单，拍当前产品的真实界面。事实边界见 [README-DEMO-BRIEF.md](README-DEMO-BRIEF.md)：不使用真实客户原件、生产数据库或历史截图；不宣称识别准确率、提效或真实用户认可；对账草稿不表示付款。

## 运行

脚本每次自行创建独立的临时 PostgreSQL、对象目录、账号和本地服务，结束时停止自己的服务与数据库并保留证据。它不接受现有服务地址或账号；中英文各运行一次，因此不会把两种采购单录进同一个环境。

前提与 business smoke 相同：项目 `.venv`、`.tools/postgresql-18.6-4/pgsql`、已构建的前端、Chrome 和 Playwright 可用。可通过 `FACTORYFLOW_PLAYWRIGHT_PATH` 指定 Playwright，`FACTORYFLOW_BROWSER_CHANNEL` 指定浏览器。临时账号为 `smoke-admin`，密码随机生成。

```powershell
node scripts/readme-screenshots.mjs --lang zh-CN --out <输出目录> --ocr-python <离线OCR运行时/python.exe>
node scripts/readme-screenshots.mjs --lang en --out <输出目录> --ocr-python <离线OCR运行时/python.exe>
```

`--ocr-python` 选择已准备好的 RapidOCR 运行时，只修改本次新环境的配置，不安装模型、不修改其他实例。省略时使用应用默认的 Windows OCR。截图回执记录实际引擎；不同引擎的结果不能混用。`--video` 可额外录制浏览器过程，本次验收只要求 PNG。

浏览器和服务启用现有 smoke 的外网阻断方式。截图前检查实例身份、空业务数据、页面错误、横向溢出和开发错误遮罩；异常 HTTP、浏览器脚本或外网请求会使运行失败。

Python 查询 Windows 版本时的三个已知 `ver` 子进程探针仍被阻止，但单独记为 `blocked_windows_version_probes`，避免误报为业务外网请求；其他子进程与网络拦截规则不变。

## 流程与镜头

桌面为 1440×900，手机为 390×844 CSS 像素、2 倍像素密度。文件前缀为 `zh-` 或 `en-`，每种语言 7 张。

| 文件 | 画面与核对点 |
|---|---|
| `01-first-run` | 空库首次打开，「从第一张订单开始」、上传入口和本机存储提示 |
| `02-source-review` | 原件与未经修改的识别候选；候选不足四行或识别错误也如实保留 |
| `02b-manually-reviewed` | 根据同一合成原件补齐并校正后的四行订单，尚未确认生成订单 |
| `03-open-lines` | 分批送货后：120/30/90 件、240/80/160 件、35.5/10.25/25.25 千克、48/12/36 米；包含进度条 |
| `03-open-lines-phone` | 同一待交清单，底部五个有可访问名称的导航按钮；首张卡片进度条可见、无横向溢出 |
| `04-order-detail` | 前两行已由用户操作收录进物料池，显示 2 / 4；收起物料操作后的订单详情 |
| `05-statement` | 2026 年 11 月、加入四条送货明细、采用订单含税价并保存后的对账草稿，总额 784.40 CNY |

真实流程依次为上传识别、录单时新建客户、对照原件校正、勾选确认、送货 30 / 80 / 10.25 / 12、收录两行物料、保存对账草稿。手机截图可正常滚动至首张卡片，不能用 CSS 或开发者工具改变页面。

脚本在第 02 张及原始 JSON 保存之后，才通过界面按合成采购单逐字段补齐数据；这模拟人工核对，不代表识别器自己得到了四行正确结果。金额、币种和行数的修改同样记录，不能把格式规范化次数当作识别错误率。

## 证据与使用边界

- `<语言>-capture.json`：`completed`、实际引擎、原始候选行数、截图清单、逐字段校正及页面/网络/清理错误。只有 `completed: true` 且清理错误为空才算整次完成。
- `<语言>-raw-extraction.json`：修改前的真实提取结果，必须与 `02-source-review` 一起保留。
- 临时环境中的 `capture-server.log`：本次服务启动、外网阻断和停止的核对材料。临时配置含随机测试凭据，不应发布。

2026-10-23 在真实本地后端与离线包使用的 RapidOCR 运行时上，中英文业务流程均完成。该合成样本的原始中文结果为 3 行，英文为 0 行；两者都需要人工校正/补录。此记录说明当前样本的实际结果，不代表其他原件的识别质量。上传成功和人工校正后的订单完成不能写成「上传即准确识别四行」。

README 可选 `03-open-lines` 展示分批送货，再用 `02b-manually-reviewed` 展示人工核对。若放 `02-source-review`，图注必须明确它是待核对的原始候选，不能遮掩缺行。建议图注：

```markdown
![分批送货后，按订单查看已交与待交数量（合成演示）](docs/images/readme/zh-03-open-lines.png)
![根据采购单人工校正后，再确认生成订单（合成演示）](docs/images/readme/zh-02b-manually-reviewed.png)
```

英文静图图注使用 “Synthetic demo; manually reviewed against the source”。中英文 README 各采用人工核对完成、分批送货后待交清单两张原始截图；2026-10-24 起，英文 README 使用独立录制的英文动图，中文动图保持原样。原先的首次打开静图仍保存在 `docs/images/readme/`。六张 PNG 复制时均核对了 SHA-256，未修改图像内容。完整截图与原始提取回执保留为独立本地验证材料；其中的运行配置不属于源码发布范围。

## 从第一张订单开始的动图

`docs/images/readme/zh-first-order.gif` 展示同一张合成订单的四个状态：空库开始、录单时新建客户、人工核对后确认、第一张订单已保存。确认完成时物料池仍为空，页面显示 `0 / 4` 行已关联物料；这展示了无需预先准备客户和物料档案的上手路径。

动图为 960×720、24 秒循环、约 3.25 MB。按本次审阅反馈，在已采用的 12 秒剪辑上将每帧显示时长加倍，保留原有画面与字幕，避免关键操作和结果一闪而过。四段分别约为 6、5.5、5、7.5 秒；这是 0.5 倍速操作节选，不是实际用户完成首张订单的计时。

画面来自全新合成环境中的真实产品操作。原始中文提取为 3 行，经对照原单人工补齐、校正为 4 行后，再勾选并确认生成订单。识别等待和部分逐项核对过程被省略，并在字幕及 README 图注中披露。顶部说明为后期字幕；没有重绘产品界面或改写业务结果。

## English first-order GIF

`docs/images/readme/en-first-order.gif` was recorded on 2026-10-24 using the actual English UI and the English synthetic purchase order. It shows four stages: start with an empty workspace, create a customer during order entry, review and confirm the order, and see the saved order with 0 of 4 lines linked to the item catalog.

The capture used the installed Windows preview, build `26e4bb90445db734`, with a new temporary PostgreSQL database, object directory and synthetic account. No existing business database or customer documents were used. The existing README capture script was limited to the first-order flow; the packaged application and its UI were not changed for the recording.

RapidOCR returned **0 item rows** for this sample. The four rows were entered through the UI from the original before confirmation. The recording follows the manual review path; it does not show OCR automatically producing four correct rows. Waiting and some field-by-field entry are omitted. This result describes this synthetic sample only, not recognition accuracy on other documents.

The GIF is 960×720, 24 seconds, 144 frames and approximately 2.5 MB. Four excerpts play at 0.5× speed for 6, 5.5, 5 and 7.5 seconds. This is an edited demonstration, not a completion-time measurement. English captions sit above a crop of the real product recording; no product labels or business results were redrawn.

The recording completed with no browser runtime errors, unexpected HTTP failures or observed external requests. The saved order had four lines and the item catalog was still empty. The recording's local server and database were stopped afterward. Raw video, extraction results, correction records and capture receipts are retained locally; private runtime configuration is not part of the source repository.
