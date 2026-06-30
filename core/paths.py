"""唯一仓库根锚点。所有'仓库根相对'路径解析的单一来源。
TAU_HOME 可被环境变量覆盖（scheduled task / 容器 / CI 友好）；
否则回溯到本文件上两级（core/ 的父目录 = 仓库根）。"""
import os
from pathlib import Path

TAU_HOME = Path(os.environ.get("TAU_HOME") or Path(__file__).resolve().parent.parent)
ASSETS = TAU_HOME / "assets"
MEMORY = TAU_HOME / "memory"
TEMP = TAU_HOME / "temp"
SCHE_TASKS = TAU_HOME / "sche_tasks"
TAU = TAU_HOME / ".tau"
TAUKEY_PATH = TAU / "taukey.py"
