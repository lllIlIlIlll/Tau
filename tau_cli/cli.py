"""tau_cli/cli.py - Tau 命令行分发入口。

通过 `python -m tau_cli <command>` 或 `tau <command>` 调用。
命令定义与执行在 tau_cli/commands/ 下, 本文件仅负责 main() 与 dispatch。
"""
import argparse, sys, textwrap

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "gb2312"):
    sys.stdout.reconfigure(errors="replace") if hasattr(sys.stdout, "reconfigure") else None

from tau_cli.commands import _launchers as _launchers_mod
from tau_cli.commands import run, list as list_cmd, status as status_cmd, update as update_cmd


COMMANDS = {
    **_launchers_mod.LAUNCHERS,
    "list":   list_cmd.COMMAND,
    "status": status_cmd.COMMAND,
    "update": update_cmd.COMMAND,
    "run":    run.COMMAND,
}


def main():
    parser = argparse.ArgumentParser(
        prog="tau",
        description="Tau 全局命令入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            示例:
              tau gui               启动桌面 GUI
              tau launch            启动 webview 桌面壳
              tau list              列出所有命令
        """),
    )
    parser.add_argument("command", nargs="?", help="命令名")
    parser.add_argument("args", nargs="*", help="子命令参数")
    parser.add_argument("-v", "--version", action="store_true", help="显示版本")

    args, unknown = parser.parse_known_args()

    if args.version:
        print("Tau v0.1.0")
        return

    cmd = args.command

    if not cmd or cmd == "help":
        parser.print_help()
        print("\n--- 命令列表 ---")
        list_cmd.run(commands=COMMANDS)
        return

    if cmd not in COMMANDS:
        print(f"❌ 未知命令: {cmd}")
        print(f"   使用 'tau list' 查看可用命令")
        sys.exit(1)

    info = COMMANDS[cmd]
    extra = list(args.args) + unknown

    # === dispatch ===
    if cmd == "list":
        list_cmd.run(commands=COMMANDS)
        return
    if cmd == "status":
        status_cmd.run(extra or None)
        return
    if cmd == "update":
        update_cmd.run(extra or None)
        return
    if cmd == "run":
        run.run(extra or None)
        return

    # 启动类命令 — 委派给 _launchers.run() (内含 flags 处理 + cmd 模板选择)
    _launchers_mod.run(cmd, extra if extra else None)


if __name__ == "__main__":
    main()
