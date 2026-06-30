"""日报两道代码层闸门回归测试。

复现并锁定两个曾经失效的闸门:
  1. render.py 入口必须调用 enforce_window — window 字符串不符 SOP H1 时 exit 2。
  2. validate.py 非 --strict 模式也必须用退出码反映校验失败 (旧版 main() 返回值被丢弃, 恒 exit 0)。

从 worktree 根执行: python -m unittest tests.test_daily_report_gates -v
"""
import json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER = os.path.join(ROOT, "memory", "daily_report_render.py")
VALIDATE = os.path.join(ROOT, "memory", "daily_report_validate.py")


def _write_json(payload: dict) -> str:
    fd, path = tempfile.mkstemp(suffix=".json", dir=os.path.join(ROOT, "temp"))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return path


class TestDailyReportGates(unittest.TestCase):
    def test_render_rejects_bad_window(self):
        """window 字符串与 SOP H1 24h 区间不符 → render exit 2 (而非照常渲染)。"""
        bad = {
            "date": "2026-06-23",
            # 起点应为 06-22, 这里故意写 06-20 (3天窗口)
            "window": "2026-06-20 00:00 至 2026-06-23 18:00（北京时间）",
            "s1_items": [], "s2_items": [], "s3_hot": [], "s3_clues": [],
            "trends": {}, "signals": [],
        }
        path = _write_json(bad)
        try:
            r = subprocess.run(
                [sys.executable, RENDER, path, "--fmt", "md",
                 "--output-dir", "temp/output/daily_20260623"],
                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 2,
                             f"window 不符应 exit 2, 实得 {r.returncode}\n{r.stderr}")
        finally:
            os.unlink(path)

    def test_validate_nonstrict_propagates_failure(self):
        """校验失败时, 即使不带 --strict 也必须 exit≠0 (否则 $? 判断得到假 PASS)。"""
        failing = {
            "date": "2026-06-23",
            "window": "2026-06-22 00:00 至 2026-06-23 18:00（北京时间）",
            "s1_items": [],  # 板块一应 3-5 条 → E.4-03 FAIL
            "s2_items": [], "s3_hot": [], "s3_clues": [],
            "trends": {}, "signals": [],
        }
        path = _write_json(failing)
        try:
            r = subprocess.run(
                [sys.executable, VALIDATE, path],
                cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0,
                                f"校验失败应 exit≠0, 实得 {r.returncode}\n{r.stdout}")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
