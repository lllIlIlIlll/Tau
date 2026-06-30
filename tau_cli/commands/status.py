"""tau status — 检查 Tau 进程运行状态"""
import sys
COMMAND = {
    "name": "status",
    "help": "检查运行状态",
    "desc": "检查当前是否已有 Tau 进程在运行",
    "cmd": None,
    "internal": True,
}


def run(args=None):
    try:
        import psutil
    except ImportError:
        print("⚠️ tau status 需要 psutil — 运行: uv pip install psutil")
        return
    running = [p for p in psutil.process_iter(['pid', 'name', 'cmdline'])
               if p.info['cmdline'] and any('taumain' in c for c in p.info['cmdline'])]
    if running:
        print(f"🟢 运行中: {len(running)} 个进程")
        for p in running:
            print(f"   PID {p.info['pid']} — {' '.join(p.info['cmdline'][:3])}")
    else:
        print("⚫ Tau 进程未运行")
