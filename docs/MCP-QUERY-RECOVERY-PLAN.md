# MCP query and recovery contract / 查询与中断核对

2026-11-09. Optional source integration; no installer update.

The following synthetic acceptance examples preserve the owning API's organization, transaction and idempotency boundaries. / 以下合成例子保持原 API 的组织、事务和幂等边界。

| ID | 行为与可观察结果 |
| --- | --- |
| MQ01 | 默认 viewer 增加客户名称检索、订单详情、中断确认核对，合计 6 个只读工具；显式 synthetic operator 仅再增加预览和确认，合计 8 个。客户查找不需要写权限。 |
| MQ02 | 客户名称按去首尾空白后的文字、大小写不敏感包含匹配，服务端按 ID 分页，limit 1–100。`%`、`_` 当普通文字；空白拒绝。同一检索词命中多个客户时返回各候选 UUID，不自动选择。`next_cursor` 仍有值时不声称查全。第 1001 个客户也能命中。 |
| MQ03 | 订单详情接受订单 UUID，或显式客户 UUID＋精确订单号；二选一，拒绝空白或混合定位。单号在客户内唯一，同号不同客户不能自动挑选。已交完、已软删的订单仍能查到且保留当前状态。 |
| MQ04 | 详情保留当前 revision/version、各行已交/未交量、币种/单位、来源数量/价格/金额字符串及 null、历史版本引用。只读，不应用物料建议，不推导收款。上游畸形数据/错误不得冒充成功或回显敏感正文。 |
| MQ05 | 原 prepared_id 等于 order.confirm 的幂等键。只读 GET 回执只读取当前组织＋固定 order.confirm＋该键的已提交结果，不获取其他命令、其他组织、原始 payload/hash，不加锁、不写 journal。 |
| MQ06 | 回执存在报告 confirmed，另读当前订单；当前被修订/软删仍保留原确认成功事实，并明确当前状态已变。回读失败仅标失败，不推翻已提交回执。 |
| MQ07 | 回执不存在（尚未发送、仍在事务中、已回滚、键错误等）一律 unknown，不能证明未创建/允许重建。网络失败或旧后端缺接口返回明确工具错误。查询本身永不重试 POST 或自动生成新预览。 |
| MQ08 | MCP 进程重启后仍可用原 prepared_id 查回执；旧预览仍不可直接确认。若原编号遗失，可按客户＋单号核对订单，但订单存在不证明某次确认已成功；后续写入仍需人工决定。 |
| MQ09 | viewer 只能读，匿名拒绝，组织隔离保持。真实 PostgreSQL 验证确认事务未提交时 unknown，提交后 confirmed；失败回滚仍 unknown；同键重放仍一笔订单。查询前后业务表摘要相同，登录会话/审计单列。 |

Tests: `apps/api/tests/test_postgres_mcp_queries.py`, `apps/mcp/tests/test_queries_recovery.py`, and `apps/mcp/tests/live_query_recovery_smoke.py`. See [verification](VERIFICATION.md) for actual results and limitations.
