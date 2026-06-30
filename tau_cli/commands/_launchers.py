"""启动类命令注册表 — 数据驱动，替代 6 个同构文件。

每个 entry 的 schema:
- name:   str, 命令名（同时作为 LAUNCHERS dict 的 key）
- help:   str, 简短一行，用于 `tau <cmd> --help`
- desc:   str, 多行描述，用于 `tau list` 表格的 desc 列
- cmd:    list[str], 启动模板，保留 {PROJECT_DIR}/{APPS}/{REFLECT} 占位符
         运行时由 _common.expand() 在 launch_frontend() 内部展开
- flags:  dict[str, dict] (可选), 命令特有 flag 覆写 (e.g. {"--native": {"cmd": [...]}})
         当前 6 个 entry 均未使用; 字段保留以备未来扩展。

注意: help/desc 文案逐字保留自原 cli_cmd.py / configure.py / gui.py / tui.py /
hub.py / launch.py。删除旧文件后,本文件是 6 个启动类命令的唯一定义点。
"""

from . import _common as _c

LAUNCHERS: dict[str, dict] = {
    "gui": {
        "name": "gui",
        "help": "启动桌面GUI (gui/app.py)",
        "desc": "启动基于 PySide6 的完整桌面聊天界面（气泡代码高亮、文件拖拽、历史搜索）",
        "cmd": ["python", "{APPS}/gui/app.py"],
    },
    "tui": {
        "name": "tui",
        "help": "启动终端 TUI (tui/app.py)",
        "desc": "启动终端图形界面（Textual），适合纯终端环境或 SSH",
        "cmd": ["python", "{APPS}/tui/app.py"],
    },
    "cli": {
        "name": "cli",
        "help": "启动 CLI 对话 (taumain)",
        "desc": "启动命令行交互对话模式，最轻量的使用方式",
        "cmd": ["python", "{PROJECT_DIR}/core/taumain.py"],
    },
    "launch": {
        "name": "launch",
        "help": "启动 webview 桌面壳 (launch.pyw)",
        "desc": "以原生窗口形式包装 stapp Web 界面（基于 pywebview）",
        "cmd": ["python", "{APPS}/hub/launch.pyw"],
    },
    "hub": {
        "name": "hub",
        "help": "启动 Hub 管理器 (launcher)",
        "desc": "启动 hub 前端管理面板（系统托盘 + 浏览器界面）",
        "cmd": ["python", "{APPS}/hub/hub.pyw"],
    },
    "configure": {
        "name": "configure",
        "help": "运行初始配置向导 (configure_taukey.py)",
        "desc": "首次安装后配置 API Key、模型参数等基础设置",
        "cmd": ["python", "{PROJECT_DIR}/assets/scripts/configure_taukey.py"],
    },
}


def run(name: str, args):
    """分发到对应启动器。name 必须是 LAUNCHERS 的合法 key。

    内部仍按原 cli.py:83-92 的语义: flags 覆写 + cmd 模板选择。
    保留 flags 字段以备未来扩展（当前 6 个 entry 未使用）。
    """
    entry = LAUNCHERS[name]
    cmd_parts = list(entry["cmd"])

    # 规范化 args 为本地 list (允许调用方传 None/tuple/list), flags 处理需 mutate
    args = list(args) if args else []

    flags = entry.get("flags", {})
    for flag_name, flag_info in flags.items():
        if flag_name in args:
            cmd_parts = list(flag_info["cmd"])
            args.remove(flag_name)
            break

    _c.launch_frontend(cmd_parts, args or None)
