"""Shared helpers for tau_cli/commands/*.

启动类命令都通过 launch_frontend() Popen 子进程,internal 命令用各自的 run() 实现。
"""
import os, subprocess, sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _apps():
    return os.path.join(PROJECT_DIR, "apps")


def _reflect():
    return os.path.join(PROJECT_DIR, "reflect")


def launch_frontend(cmd_parts, args=None):
    """启动前端/工具子进程 (Popen, 阻塞等待子进程结束)"""
    full_cmd = []
    for part in cmd_parts:
        part = part.replace("{PROJECT_DIR}", PROJECT_DIR)
        part = part.replace("{APPS}", _apps())
        part = part.replace("{REFLECT}", _reflect())
        full_cmd.append(part)

    if args:
        full_cmd.extend(args)

    print(f"🚀 {' '.join(full_cmd)}")
    sys.stdout.flush()
    os.chdir(PROJECT_DIR)
    proc = subprocess.Popen(full_cmd)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        sys.exit(0)
