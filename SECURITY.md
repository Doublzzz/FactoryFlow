# 安全反馈 / Security policy

FactoryFlow 当前是开发者预览。报告问题时请注明[预览版本](https://github.com/Doublzzz/FactoryFlow/releases/tag/v0.1.0-preview.1)或源码提交，以及 Windows 和浏览器版本。

FactoryFlow is a developer preview. Include the [preview version](https://github.com/Doublzzz/FactoryFlow/releases/tag/v0.1.0-preview.1) or source commit, Windows version and browser version in your report.

## 私下报告 / Report privately

如果发现可能泄露业务资料、绕过权限或破坏数据的问题，请勿在公开 Issue 中描述漏洞细节或上传复现材料。

If an issue may expose business information, bypass permissions or compromise data, do not describe the vulnerability or upload reproduction material in a public issue.

1. 查看仓库的 [Security → Advisories](https://github.com/Doublzzz/FactoryFlow/security/advisories)。若有 **Report a vulnerability** 按钮，请通过它提交私密报告。
2. 若没有该按钮，只开一个标题为 **Private security contact request** 的空白 Issue，请维护者提供私密联系方式。正文只说明需要私下联系；不要放漏洞详情、截图、日志或附件。等维护者提供私密渠道后再发送材料。

1. Open [Security → Advisories](https://github.com/Doublzzz/FactoryFlow/security/advisories). If **Report a vulnerability** is available, use it to submit a private report.
2. If that button is unavailable, open a blank issue titled **Private security contact request**, asking the maintainer for a private contact channel. Include only that request, with no vulnerability details, screenshots, logs or attachments. Wait for a private channel before sharing the report.

## 报告内容 / What to include

请只在自己的测试环境中复现，使用虚构客户和合成资料。私密报告中说明版本、受影响功能、最小复现步骤、实际影响，以及已经做过的处理即可。若需错误信息，只提供检查并脱敏后的最小片段。

Reproduce the issue only in your own test environment, using fictional customers and synthetic data. In the private report, include the version, affected feature, minimal reproduction steps, impact and any action already taken. If error output is needed, include only the smallest inspected and redacted excerpt.

不要发送真实客户原件、价格、联系方式、账号密码、令牌、数据库、备份、完整日志或带个人用户名的本机路径。合成复现应保留问题所需的结构，不要把真实业务资料仅改个文件名后上传。

Do not send real customer originals, prices, contact details, passwords, tokens, databases, backups, full logs or local paths containing personal usernames. Preserve only the structure needed to reproduce the issue; renaming a real business file does not make it synthetic.

普通功能问题和建议可使用 [Issue 模板](https://github.com/Doublzzz/FactoryFlow/issues/new/choose)。

For ordinary bugs and feature suggestions, use the [issue templates](https://github.com/Doublzzz/FactoryFlow/issues/new/choose).
