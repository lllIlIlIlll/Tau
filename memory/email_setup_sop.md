# Email Setup SOP（v3 · 2026-06-21 refactor）

> spec: `docs/specs/2026-06-21-email-feature-refactor-design.md`
> 触发：用户表达"配置邮箱 / 设置发件箱 / 帮我配邮件 / SMTP 配一下"等设置意图
> **不在邮件发不出去/链路故障时执行**——那是 email_report 故障排查 SOP（待写）
> **v3 变更**：邮件模块从 `mailer/` 迁至 `memory/`（库）+ `assets/scripts/configure_tauchain.py`（v2.2+ 活跃维护的人类交互式向导）。授权码从 keychain 改为 `.tau/tauchain.json` 明文存储（受 `.gitignore` + 文件权限 `600` 保护）。

## 阶段 1 · 确认意图

一句话："我要帮你配的是 Tau 日报的发件邮箱（用你自己的 QQ/Gmail 给订阅者发日报），对吗？"
- 答是 → 阶段 2
- 答否 → 礼貌退出："好的，这个 SOP 是配发件邮箱的，你描述的不是这个场景。"

## 阶段 2 · 收集 4 个必填项

依次问，**每项都允许回车用默认值**。问下一项前不复述上一项（避免啰嗦）。

- **2.1 发件邮箱地址**（如 lllilililll@qq.com）—— *唯一不可默认*
  校验：调 `from memory.email_config import infer_provider; infer_provider(addr)` 试一下。
  - 返回 None → 提示："这个域名我表里没有，稍后让你手填 SMTP 地址，继续。"
- **2.2 发件人显示名**（默认 "Tau 日报"）
- **2.3 收件人地址**（逗号分隔，默认空，待会儿必须填）
- **2.4 SMTP 授权码**（粘贴时不可见）—— *唯一不可默认*

  提示文本：
  > 如果你还没申请授权码：
  > - QQ 邮箱：设置 → 账户 → POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务 → 开启服务 → 生成授权码
  > - 163 邮箱：设置 → POP3/SMTP/IMAP → 开启 + 新增授权密码
  > - Gmail：Google 账号 → 安全性 → 应用专用密码（需先开启两步验证）
  >
  > 把生成的字符串粘过来（粘贴时终端不显示，正常）：

  调用前先 `import sys; sys.stdin.isatty()` 检查；若非交互终端（SSH no-tty / Claude Code 后台批处理），改用 agent 的 `ask_user` 工具替代（同样隐私保护）。

  用 `getpass.getpass()` 接住，**不打印、不写日志**。

## 阶段 3 · 推断 + 提示

调 `infer_provider(addr)`（`memory.email_config.infer_provider`）。
- 返回非 None → 展示："我将用 {host}:{port}（{'SSL' if ssl else 'STARTTLS'}）"
  + 如果 provider 有 note（如 Gmail 的"需应用专用密码"）→ 复述一次
- 返回 None → 退手填 host / port / SSL 三项：
  > 你的邮箱服务商不是常见几家，我来问你三件事：
  > - SMTP 服务器地址（如 smtp.example.com）：
  > - 端口（SSL 通常 465，STARTTLS 通常 587）：
  > - 用 SSL 还是 STARTTLS？（SSL/STARTTLS）

## 阶段 4 · 写入

调 `memory.email_config.save_email_config(cfg)`：

```python
from memory import email_config

cfg = {
    'smtp_host':    infer_host or 阶段 3 手填,
    'smtp_port':    infer_port or 阶段 3 手填,
    'smtp_use_ssl': infer_ssl  or 阶段 3 手填,
    'smtp_user':    阶段 2.1,
    'smtp_pass':    阶段 2.4 拿到的授权码,  # 明文写入 .tau/tauchain.json
    'sender_name':  阶段 2.2,
    'to_addrs':     阶段 2.3 逗号 split + strip,
    'subject':      '[Tau 日报] {date} 非传统安全领域动态日报',  # 默认值
    'body':         '今日日报见附件。',  # 默认值
    'smtp_timeout': 30,
    'meta': {
        'version': 1,
        'created_at': datetime.now().isoformat(),
        'purpose': 'Tau 日报 SMTP',
    },
}
email_config.save_email_config(cfg)  # 自动 mkdir .tau/ + chmod 0o600
```

- ✅ **v3 单一 API**：所有写操作走 `memory.email_config.save_email_config(cfg)`，禁止直接 `json.dump` 写 `.tau/tauchain.json`（绕开校验 + chmod）

## 阶段 5 · 验证

调 `python memory/email_report.py`（无参 send() 会自动从 `.tau/tauchain.json` 读 cfg + 密码，发测试邮件）。

或更通用：直接调 `memory.email_report.send()`（库 API）。

- 成功 → 提示："✅ 已发一封测试邮件到 {recipients}，收到即配置完成。"
- 失败 → 进入阶段 6

## 附录 A · 人类配置入口

唯一交互式配置入口：

```text
assets/scripts/configure_tauchain.py
```

设计要点：
- **复用库**：写入与字段契约复用 `memory.email_config.save_email_config`（不再自带写逻辑），杜绝字段漂移；按邮箱域名调 `memory.email_config.infer_provider` 自动推断 SMTP。
- **交互 + 非交互双模式**：
  - 交互：`python assets/scripts/configure_tauchain.py`（默认模式，逐项问 4 个必填 + 推断 SMTP）
  - 非交互（CI/CD）：`--non-interactive` + 环境变量（`TAU_SMTP_HOST`、`TAU_SMTP_PORT`、`TAU_SMTP_USER`、`TAU_SMTP_PASS`、`TAU_TO_ADDRS` 等）
  - 配置后验证：`--send-test` 调 `memory.email_report.send()` 发一封测试邮件
- **安全**：生成 `.tau/tauchain.json`，文件权限 `0o600`，原配置自动备份到 `.tau/tauchain.json.bak.<timestamp>`。

Agent 程序化写入（不走 SOP 模板）：

```python
from memory import email_config
email_config.save_email_config(cfg)
```

## 阶段 6 · 错误处理

**不撤销已写入的 `.tau/tauchain.json`**。按错误类型给可执行建议：

- **smtplib.SMTPAuthenticationError (535)** →
  > 邮箱服务器拒绝登录。最常见原因：
  > 1. 授权码输错（回看阶段 2.4，重输一次）
  > 2. Gmail 没在账号里启用"应用专用密码"（需先开启两步验证）
  > 3. QQ 没在邮箱设置里开启 SMTP 服务
  >
  > 配置已保留，改完任意一项说"重试发测试邮件"即可。

- **socket.timeout / ConnectionRefusedError** →
  > 连不上 SMTP 服务器。常见原因：
  > 1. 端口被防火墙挡
  > 2. 端口选错（SSL 通常 465，STARTTLS 通常 587）
  >
  > 配置已保留，改完说"重试"。

- **smtplib.SMTPException 其他** →
  > 服务器返回 {错误原文}。配置已保留，如需帮助把这段错误贴出来。

- **email_config 写入失败 / 未配置（阶段 4 / 5）** →
  > `.tau/tauchain.json` 不存在或字段缺失，错误 {X}。请跑 `python assets/scripts/configure_tauchain.py`（首次配置）。
  > 权限问题：`chmod 600 .tau/tauchain.json`。

## 重试入口

用户说"重试发测试邮件" → 跳回阶段 5（**不重做 2.1-2.4**，直接跑 `python memory/email_report.py`）。如果用户说"重配"，回到阶段 2.1。

## 不做什么（防 agent 漂移）

- ❌ 不主动开浏览器帮申请授权码（SOP 只给文字提示；涉及验证码/人机验证/SMS）
- ❌ 不替用户修改 `keychain.py` 内部实现
- ❌ 不动 `daily_report_*` 调度 prompt
- ❌ 不引入第三方邮件 SaaS / OAuth
- ❌ 不替用户改邮箱服务商的安全设置
- ❌ 不批量配置多账号（超出本 SOP 范围）
- ❌ 不在 SOP 里谈 IMAP 收件 / 同步（那是另一个场景）
- ❌ 不替用户清理 `temp/email_report.test_sent`（那是测试邮件的幂等标记，下次测试自动覆盖）

## 终止条件

- 阶段 5 成功 → "✅ 配置完成"
- 阶段 6 任一错误 → 等用户说"重试"或"算了"
- 用户中途说"算了"/"先这样" → 当前阶段标记"未完成"，不写文件