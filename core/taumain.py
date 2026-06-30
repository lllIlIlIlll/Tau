"""入口 shim —— Tau 运行时已迁至 core.agent.runtime。
保留在 core/ 顶层是因为它被当脚本/模块直跑：
  python -m core.taumain --reflect ...   (start_scheduler.sh / start_autonomous.sh)
  python core/taumain.py --task ...      (tau_cli / SOPs)
脚本直跑读文件而非 import 系统，故不能纯靠 sys.modules 别名。"""
from core.agent.runtime import Tau, get_system_prompt, load_tool_schema, main  # noqa: F401

if __name__ == '__main__':
    main()
