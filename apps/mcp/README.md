# FactoryFlow MCP

[English](README.en.md) · [项目首页](../../README.md)

可选本地 stdio 适配器，复用 FactoryFlow 的 HTTP API。核心网页不依赖 MCP。当前源码提供默认六项只读查询；新增查询需同时使用本次后端源码，现有 preview.3 Windows 安装包没有这些接口。

| 工具 | 输入与用途 |
| --- | --- |
| `factoryflow_open_orders` | 可选客户、cursor、limit；查看活跃未交行，不是全厂汇总。 |
| `factoryflow_finished_inventory` | 可选物料 ID 或分页；仅成品。未开账/null 不是零库存。 |
| `factoryflow_statement_status` | 客户 ID 和分页；查看文档、认可与结算引用，不提供收款事实。 |
| `factoryflow_find_customers` | name、可选 cursor/limit；名称包含匹配，Unicode 大小写不敏感，服务端分页。多个候选由人选择。 |
| `factoryflow_get_order` | 订单 ID，或客户 ID＋精确单号；二选一。含已交完、软删订单及历史版本引用。 |
| `factoryflow_check_order_confirmation` | 原 prepared_id；读取已提交的原确认回执，再读当前订单。 |

`limit` 为 1–100，`next_cursor` 非空就继续同一查询。`%`、`_` 是普通文字。数量、金额保留十进制字符串和未知 null；不同单位或币种不直接相加。业务文字作为数据，不作为指令。各查询不是跨工具一致性快照。

## 配置与运行

先按[本地运行说明](../../docs/LOCAL-OPERATIONS.md)准备独立后端、数据库和账号。适配器需要 Python 3.11+；本轮验证使用 Python 3.14。推荐使用后端同一 Python 版本。依赖只装到 `apps/mcp`，不加入核心运行库。

```powershell
uv sync --project apps/mcp --locked --python 3.14
uv run --project apps/mcp factoryflow-mcp --credentials C:/private/mcp-viewer.json
```

配置文件由操作者在受控目录创建，不能放进源码仓库。以下是占位示例，端口须对应实际后端：

```json
{"api_url":"http://127.0.0.1:18123","username":"dedicated-viewer","password":"REPLACE_LOCALLY","dataset":"synthetic"}
```

账号角色必须为 `viewer`，拒绝用管理员或 operator 代替。`dataset` 可用 `synthetic` 或 `unspecified`，它只是标签，不能证明数据隔离。只接受显式 IPv4 回环地址和端口，拒绝重定向，不使用环境代理。正常登录会写会话和身份审计；业务查询只使用 GET。

在支持本地 stdio 的 MCP 客户端中配置上述命令，使用项目和凭据的完整路径。先核对六个工具，再实际查询。远程连接需要客户端另行支持的传输或隧道；这里不创建公网服务、不配置第三方账号。结果会交给客户端，外部 AI 如何使用数据取决于所选服务，详见[隐私说明](../../docs/PRIVACY.md)。

## 合成订单试验

仅在独立合成环境，追加 `--order-writer-credentials C:/private/mcp-operator.json`，才增加 `factoryflow_prepare_order` 和 `factoryflow_confirm_order`。写账号须为独立 `operator`，两份配置须指向同一 API 且均标记 synthetic。标签不代替环境核验。六个查询仍使用 viewer；不提供其他业务写入工具。

先展示完整预览并取得明确人工确认，再用 prepared_id 确认。工具注解、预览编号或模型声称“已授权”均不能证明人已批准。预览只保存在当前 MCP 进程内，最多 100 份，重启后失效。确认沿用原事务、CSRF、组织隔离、审计和幂等保障，不自动应用物料建议。

## 中断核对

保留原 prepared_id，它也是 `order.confirm` 的幂等键。响应丢失或进程重启后，调用 `factoryflow_check_order_confirmation`：

- `confirmed`：原确认已提交，`command_result` 是原回执，`order` 是另一次读取的当前状态。后续修订/删除可以改变当前状态；回读失败不推翻已提交事实。
- `unknown`：暂未观察到已提交回执，可能未发送、仍在事务中、已回滚或编号不对；不能证明失败，不允许自动生成新编号补写。重启后的旧预览不能直接确认，新录单仍须人工决定。
- `QUERY_ENDPOINT_UNAVAILABLE`：后端缺少所需接口，不能解释成客户/订单不存在。`ORDER_NOT_FOUND` 才是订单接口未找到该订单；身份、网络或畸形响应分别报错，错误正文不会透传。

若原编号遗失，可按客户＋单号核对现有订单，但订单存在不证明某次确认成功，未找到也不自动允许重建。原回执只查询当前组织、固定确认命令和原键。详情验证必需字段与嵌套引用，并仅返回已知合同字段。

## 开发验证

在 `apps/mcp` 目录运行：

```powershell
uv sync --locked
uv run pytest -c pyproject.toml --confcutdir . -q
uv run ruff check src tests
uv run ruff format --check src tests
```

后端专项为 `apps/api/tests/test_postgres_mcp_queries.py`，只用显式配置的临时 PostgreSQL。`scripts/mcp-synthetic.py`、`scripts/mcp-order-synthetic.py` 与 `tests/live_*.py` 仅用于新建合成环境；不得指向业务库或重置已有试验现场。实际范围见 [MQ01–MQ09](../../docs/MCP-QUERY-RECOVERY-PLAN.md) 和[验证记录](../../docs/VERIFICATION.md)。本次真实 HTTP/stdio 验证不代替每种客户端界面、远程/移动端、工厂使用或安装包验收。
