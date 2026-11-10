# Privacy and snapshot scope / 隐私与快照范围

## Optional MCP data flow / 可选 MCP 数据流

The core offline application stores data locally and does not require cloud AI. Enabling the separate MCP adapter gives the configured client the results of authorized queries. Whether that client forwards data to cloud AI depends on the user's chosen client/service; FactoryFlow's local-storage claim does not make that external processing offline. Use a dedicated viewer and keep credentials outside the repository. Synthetic-only write trials require a separate explicit operator configuration; a `synthetic` label alone does not prove isolation.

核心离线应用默认本机运行，不依赖云端 AI。启用可选 MCP 后，授权查询结果会交给所选客户端；是否进一步发送到云端 AI 由该客户端/服务决定，不属于“离线处理”的承诺。使用专用只读账号，凭据不入库；写入试验另需显式配置的合成环境 operator，标签不代替数据隔离。

The public history starts from a reviewed source snapshot. Later candidates are assembled on that public baseline; they do not inherit the development repository's old commits or internal context records. Downloadable application-source ZIPs contain no Git metadata.

Included: application source, migrations, generated API contracts, locked dependency manifests, synthetic tests, generic operating documentation, licensed UI font resources, and explicitly synthetic demo assets.

Excluded: private agent configuration, runtime/database/object directories, account configuration, credentials, customer originals/templates, machine-specific paths, private handoffs/knowledge mirrors, historical private logs/screenshots, installed toolchains/dependencies, offline installers and the original development repository's Git history. Public engineering notes and explicitly synthetic README screenshots are included; no development commits are included.

All purchase-order samples are fictional and visibly marked SYNTHETIC. Contact domains use `.example`; addresses are explicitly fictional. Prices and identifiers are invented for arithmetic and UI scenarios. Synthetic test passwords are not runtime credentials and must never be used for deployment.

PDF metadata uses generic project labels; files contain no signatures, bank accounts, actual phone numbers or private attachments. The project uses the [MIT License](../LICENSE). The UI font retains its adjacent SIL Open Font License, and dependencies retain their own licenses; see [third-party materials](../THIRD-PARTY-NOTICES.md).

Private visibility limits access; it is not a substitute for reviewing every future change. Do not commit generated runtime files, uploads or confidential evidence. This review is scoped to the selected snapshot and does not establish that other repositories or their old histories have been sanitized.
