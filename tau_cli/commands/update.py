"""tau update — git pull + pip install -e ."""
import os, shutil, subprocess, sys
from ._common import PROJECT_DIR
COMMAND = {
    "name": "update",
    "help": "更新项目 (git pull + uv/pip install)",
    "desc": "从 Git 拉取最新代码并更新依赖",
    "cmd": None,
    "internal": True,
}


def run(args=None):
    os.chdir(PROJECT_DIR)
    print("🔄 git pull...")
    r = subprocess.run(["git", "pull"], capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr)
    if shutil.which("uv"):
        print("📦 uv pip install...")
        install_cmd = ["uv", "pip", "install", "-e", "."]
    else:
        print("📦 pip install...")
        install_cmd = [sys.executable, "-m", "pip", "install", "-e", "."]
    r2 = subprocess.run(install_cmd, capture_output=True, text=True)
    print(r2.stdout[-500:] if r2.stdout else "")
    if r2.returncode != 0:
        print(r2.stderr[-500:])
