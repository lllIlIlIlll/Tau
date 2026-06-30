"""验证 path-hack 已消灭：在干净子进程（cwd≠仓库根、PYTHONPATH 清空）
中导入核心顶层模块，全部成功才算地基达成。"""
import subprocess, sys, tempfile, os

TOPLEVEL = ["core.paths", "core.taumain", "TMWebDriver", "TMWebDriver.simphtml",
            "plugins.hooks", "memory.email_config", "reflect.scheduler"]

def main():
    code = "import " + ", ".join(TOPLEVEL)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run([sys.executable, "-c", code], cwd=d, env=env,
                           capture_output=True, text=True)
    if r.returncode != 0:
        print("[SMOKE-FAIL]\n" + r.stderr); sys.exit(1)
    print("[SMOKE-OK] clean-subprocess import:", ", ".join(TOPLEVEL))

if __name__ == "__main__":
    main()
