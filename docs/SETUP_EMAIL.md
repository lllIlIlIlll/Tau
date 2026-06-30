# 邮件配置与使用说明

> 适用版本：v2.1（2026-06-21 及之后）

## 一句话流程

让 agent 按 [`memory/email_setup_sop.md`](../memory/email_setup_sop.md) 的阶段 1-5 走一遍。Agent 会问你 4 个必填项（发件邮箱 / 发件人显示名 / 收件人 / SMTP 授权码），自动推断 SMTP 服务器，然后发一封测试邮件验证。

## 仓库内相关文件

| 文件 | 用途 |
|---|---|
| `memory/email_config.py` | 字段契约 + `save/load/validate/infer_provider` 库 API |
| `memory/email_send.py` | 当日 docx 定位 + SMTP 发送 + 幂等（`__main__` 可手跑） |
| `memory/email_setup_sop.md` | Agent 配置流程（SOP，L3 Skill） |
| `assets/email_providers.json` | SMTP 推断表（按域名匹配） |
| `assets/email_daily_report.task.json` | 调度任务定义（样例，需拷贝到 `sche_tasks/`） |
| `.tau/tauchain.json` | 配置落点（含密码，`0o600`，gitignored） |

## 快速配置（Agent SOP）

在 agent loop 中说：

> "帮我配一下邮件发送"（或 "配邮箱" / "设置发件箱" 等同义意图）

agent 会：
1. 阶段 1：确认意图（要配的是 Tau 日报发件邮箱）
2. 阶段 2：问你 4 项（发件邮箱 / 显示名 / 收件人 / 授权码）
3. 阶段 3：调 `memory.email_config.infer_provider(addr)` 推断 SMTP
4. 阶段 4：调 `memory.email_config.save_email_config(cfg)` 写入 `.tau/tauchain.json`
5. 阶段 5：跑 `python memory/email_send.py` 发一封测试邮件到收件人

## 程序化写入（不通过 SOP）

```python
from memory.email_config import save_email_config, infer_provider

info = infer_provider("you@qq.com")
# info = {"host": "smtp.qq.com", "port": 465, "ssl": True, "note": ""}

save_email_config({
    "smtp_host":    info["host"],
    "smtp_port":    info["port"],
    "smtp_use_ssl": info["ssl"],
    "smtp_user":    "you@qq.com",
    "smtp_pass":    "your_auth_code",   # 授权码
    "sender_name":  "Tau 日报",
    "to_addrs":     ["a@example.com", "b@example.com"],
    # subject / body / smtp_timeout / meta.version 都有默认值
})
```

## CI / 非交互模式

设环境变量后让 agent 写配置：

```bash
export TAU_SMTP_HOST=smtp.qq.com
export TAU_SMTP_PORT=465
export TAU_SMTP_USER=you@qq.com
export TAU_SMTP_PASS=auth_code
export TAU_TO_ADDRS=a@x.com,b@y.com
export TAU_SENDER_NAME="Tau 日报"
```

agent 会读这些 env → 调 `save_email_config` → 跑测试邮件。

## 配置字段

| 字段 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `smtp_host` | ✅ | — | SMTP 服务器 |
| `smtp_port` | ✅ | — | 1-65535 整数 |
| `smtp_user` | ✅ | — | 发件邮箱地址 |
| `smtp_pass` | ✅ | — | 授权码（**明文存储**，文件 `0o600`） |
| `to_addrs` | ✅ | — | 非空字符串列表 |
| `smtp_use_ssl` | | `True` | SSL（465）/ STARTTLS（587） |
| `smtp_timeout` | | `30` | 秒 |
| `sender_name` | | `smtp_user` | 发件人显示名 |
| `subject` | | `Tau 日报 {date}` | 主题模板 |
| `body` | | `今日日报见附件。` | 正文模板 |

字段校验在 `memory.email_config.validate(cfg)`，保存前会先跑。

## 路径 home 锚定

库用 `os.environ.get("TAU_HOME")` 决定配置 / 发送 / 审计路径，默认落仓库根：

| 文件 | 默认路径 |
|---|---|
| 配置 | `$TAU_HOME/.tau/tauchain.json`（默认 `<repo>/.tau/tauchain.json`） |
| 当日 docx | `$TAU_HOME/sche_tasks/done/<today>_*.docx` |
| 幂等标记 | `$TAU_HOME/temp/email_report.sent` |
| 审计日志 | `$TAU_HOME/temp/email_report.log`（只记 OK / FAIL，不记 SKIP） |

`TAU_HOME=tmp` 用于测试隔离（库自动重读）。

## 错误处理

| 异常 | 触发 | 怎么办 |
|---|---|---|
| `ValueError` "配置文件不存在" | `.tau/tauchain.json` 缺失 | 跑 SOP 配置 |
| `ValueError` "配置不合法" | 字段不全或格式错 | 检查 SOP 阶段 2 的输入 |
| `FileNotFoundError` "没有 ... .docx" | 当日日报未生成 | 跑日报生成流程 |
| `RuntimeError` "当天已发过日报" | 幂等命中 | 正常状态，等次日 |
| `RuntimeError` "SMTP 失败" | 535 鉴权错 / 连接超时 / 端口错 | 见 SOP 阶段 6 错误指引 |

## 已被删除（v2.1 之前存在，不要再调用）

- `mailer/`（整包）
- `assets/scripts/configure_tauchain.py`（v2.2+ 人类交互式向导，邮件多账号入口）
- `tau_cli/email_setup.py`（v1 维护工具，已 `git rm`）
- `python -m tau_cli.email_setup {setup,migrate,test}`（命令不再可用）

## 迁移自 v1

如果你有旧部署的 v1 凭据（keychain.py + `temp/email_report.json`），手动迁移：

1. 读旧数据：`memory.keychain.get_smtp_pass()` + 读 `temp/email_report.json`
2. 调 `memory.email_config.save_email_config({...})` 写新格式
3. 删 `temp/email_report.json`（v1 兜底不再读）
4. 跑 `python memory/email_send.py` 验证

无 v1 残留：忽略本节。
