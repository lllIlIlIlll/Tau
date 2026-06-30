#!/usr/bin/env python3
"""configure_tauchain.py - 人类首次配置 Tau 邮件 SMTP。

用法:
  python assets/scripts/configure_tauchain.py                # 交互模式（默认）
  python assets/scripts/configure_tauchain.py --interactive  # 同上
  python assets/scripts/configure_tauchain.py --non-interactive  # 读环境变量
  python assets/scripts/configure_tauchain.py --send-test    # 配置后立即发一封测试邮件

写入与字段契约统一来自 memory.email_config（禁止自带 json.dump 绕开校验）。
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from memory import email_config


DEFAULTS = {
    "sender_name": "Tau 日报",
    "subject": "Tau 日报 {date}",
    "body": "今日日报见附件。",
    "smtp_timeout": 30,
}


def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v if v is not None else default


def _prompt(label: str, default: str = "", secret: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    prompt = f"{label}{suffix}: "
    if secret:
        return getpass.getpass(prompt)
    return input(prompt).strip() or default


def _infer_or_ask(addr: str) -> dict:
    """SMTP 推断；命中则用命中值，未命中则手填。"""
    info = email_config.infer_provider(addr)
    if info is None:
        print(f"未识别 {addr!r} 的 SMTP 服务商，需手填：")
        host = _prompt("SMTP 服务器", "smtp.example.com")
        port_s = _prompt("端口（SSL 465 / STARTTLS 587）", "465")
        ssl_s = _prompt("SSL 还是 STARTTLS", "SSL").upper()
        return {
            "host": host,
            "port": int(port_s),
            "ssl": ssl_s == "SSL",
            "note": "手填",
        }
    print(f"推断：{info['host']}:{info['port']}（{'SSL' if info['ssl'] else 'STARTTLS'}）")
    if info.get("note"):
        print(f"注意：{info['note']}")
    return info


def _interactive() -> dict:
    print("=== Tau 邮件 SMTP 首次配置 ===\n")
    addr = _prompt("发件邮箱地址（如 you@qq.com）")
    if not addr or "@" not in addr:
        sys.exit("发件邮箱不能为空且必须含 @")

    info = _infer_or_ask(addr)

    sender = _prompt("发件人显示名", DEFAULTS["sender_name"])
    recipients_s = _prompt("收件人（逗号分隔）")
    if not recipients_s:
        sys.exit("收件人不能为空")

    auth = _prompt("SMTP 授权码", secret=True)
    if not auth:
        sys.exit("授权码不能为空")

    return {
        "smtp_host": info["host"],
        "smtp_port": info["port"],
        "smtp_use_ssl": info["ssl"],
        "smtp_user": addr,
        "smtp_pass": auth,
        "sender_name": sender,
        "to_addrs": [r.strip() for r in recipients_s.split(",") if r.strip()],
        "subject": DEFAULTS["subject"],
        "body": DEFAULTS["body"],
        "smtp_timeout": DEFAULTS["smtp_timeout"],
    }


def _non_interactive() -> dict:
    """从环境变量读全部字段；缺失则报错退出（不静默回填）。"""
    required_env = {
        "TAU_SMTP_HOST": "smtp_host",
        "TAU_SMTP_PORT": "smtp_port",
        "TAU_SMTP_USER": "smtp_user",
        "TAU_SMTP_PASS": "smtp_pass",
        "TAU_TO_ADDRS": "to_addrs",
    }
    missing = [k for k in required_env if not _env(k)]
    if missing:
        sys.exit(f"非交互模式需设置环境变量：{', '.join(missing)}")

    port = _env("TAU_SMTP_PORT")
    try:
        port_int = int(port)
    except ValueError:
        sys.exit(f"TAU_SMTP_PORT 必须是整数，得到 {port!r}")

    ssl = _env("TAU_SMTP_SSL", "true").lower() in ("1", "true", "yes", "ssl")
    return {
        "smtp_host": _env("TAU_SMTP_HOST"),
        "smtp_port": port_int,
        "smtp_use_ssl": ssl,
        "smtp_user": _env("TAU_SMTP_USER"),
        "smtp_pass": _env("TAU_SMTP_PASS"),
        "sender_name": _env("TAU_SENDER_NAME", DEFAULTS["sender_name"]),
        "to_addrs": [r.strip() for r in _env("TAU_TO_ADDRS").split(",") if r.strip()],
        "subject": _env("TAU_SUBJECT", DEFAULTS["subject"]),
        "body": _env("TAU_BODY", DEFAULTS["body"]),
        "smtp_timeout": int(_env("TAU_SMTP_TIMEOUT", str(DEFAULTS["smtp_timeout"]))),
    }


def _send_test() -> None:
    """调 memory.email_send.send_email() 发一封测试邮件（复用库 API）。"""
    sys.path.insert(0, str(REPO / "memory"))
    from email_send import send_email
    print("\n发送测试邮件...")
    try:
        result = send_email(today="1970-01-01")  # 强制幂等不影响真实日报
        print(f"✅ {result}")
    except RuntimeError as e:
        if "已发过" in str(e):
            print(f"⚠️  {e}（如需重测，删 $TAU_HOME/temp/email_report.sent）")
        else:
            print(f"❌ 发送失败：{e}")
            print("   常见：授权码错 / 端口被挡 / SSL/STARTTLS 选错")
            sys.exit(1)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--interactive", action="store_true", help="交互模式（默认）")
    g.add_argument("--non-interactive", action="store_true", help="非交互模式（读环境变量）")
    ap.add_argument("--send-test", action="store_true", help="配置后立即发一封测试邮件")
    args = ap.parse_args()

    if args.non_interactive:
        cfg = _non_interactive()
    else:
        cfg = _interactive()

    print(f"\n写入配置到 {email_config.CONFIG_FILE} ...")
    email_config.save_email_config(cfg)
    print("✅ 已保存（含 chmod 0o600，旧文件已备份）")

    if args.send_test:
        _send_test()


if __name__ == "__main__":
    main()