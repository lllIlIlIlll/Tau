"""tau list — 列出所有可用命令"""
COMMAND = {
    "name": "list",
    "help": "列出所有可用前端/服务",
    "desc": "显示所有注册的命令",
    "cmd": None,
    "internal": True,
}


def run(args=None, *, commands=None):
    """commands: 由 cli.py 注入的 COMMANDS 字典 (避免循环 import)"""
    cmds = commands or {}
    print()
    frontend_cmds = [(k, v) for k, v in sorted(cmds.items()) if v.get("cmd") is not None]
    internal_cmds = [(k, v) for k, v in sorted(cmds.items()) if v.get("cmd") is None]

    print(f"  {'命令':20s}  {'说明'}")
    print(f"  {'━'*20}  {'━'*40}")
    for name, info in frontend_cmds:
        print(f"  {name:20s}  {info.get('help', info.get('desc', '')[:40])}")
    print()
    for name, info in internal_cmds:
        print(f"  {name:20s}  {info.get('help', info.get('desc', '')[:40])}")
    print()
