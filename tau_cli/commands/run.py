"""tau run <query> — 同步 in-process 跑一次 Agent 任务, 拿到结果后退出。

与 'tau cli' (进 REPL) 不同: 'tau run' 不进交互模式, 一次任务结束即退出。
与 'tau cli --task' (Popen 子进程) 不同: 'tau run' 在当前进程同步执行, 失败会传播。
"""
import sys

COMMAND = {
    "name": "run",
    "help": "同步运行单次 Agent 任务 (in-process)",
    "desc": "直接跑一次任务后退出, 适合脚本化调用; 用法: tau run <query>",
    "cmd": None,
    "internal": True,
}


def run(args=None):
    args = args or []
    if not args:
        print("用法: tau run <query>...")
        print("示例: tau run 帮我在桌面创建一个 hello.txt")
        sys.exit(1)

    # Lazy import: core.taumain 在 import 时拉起 requests 等重依赖,
    # 不能让 cli.py 顶层 import run 就把这些 deps 拉进来 (tau list 跑不起来)。
    import threading
    from core.taumain import Tau

    query = " ".join(args)
    agent = Tau()
    agent.verbose = False
    threading.Thread(target=agent.run, daemon=True).start()

    dq = agent.put_task(query, source="cli-once")
    try:
        while True:
            item = dq.get(timeout=600)
            if "next" in item:
                print(item["next"], end="", flush=True)
            if "done" in item:
                print()
                if agent.stop_sig:
                    sys.exit(130)
                break
    except KeyboardInterrupt:
        agent.abort()
        print("\n[Interrupted]")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
