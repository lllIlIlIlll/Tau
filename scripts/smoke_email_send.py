"""smoke_email_send.py - T-06 消费侧 smoke 测试

测 memory/email_send.send_email() 在 4 种 cfg 状态下的分支：
  A. v2 (tauchain) 路径：cfg 完整 + 无今日 sent 标记 → 真实 SMTP 发信
  B. 幂等分支：cfg 完整 + 已有今日 sent 标记 → 抛 RuntimeError 不重发
  C. 配置缺失：未配置 .tau/tauchain.json → 抛 ValueError
  D. docx 缺失：今日日报未生成 → 抛 FileNotFoundError

依赖：memory/email_config + memory/email_send
所有 SMTP 发信在 test 模式用 mock（避免真实外发）
"""
import os
import sys
import json
import shutil
import tempfile
import unittest
import importlib
from unittest.mock import patch, MagicMock

PASSED = 0
FAILED = 0


def _ok(name):
    global PASSED
    PASSED += 1
    print(f"  PASS  {name}")


def _fail(name, err):
    global FAILED
    FAILED += 1
    print(f"  FAIL  {name}: {type(err).__name__}: {err}")


def _setup_home():
    """建临时 home + 建一份假 '今天' 的日报 docx。隔离通过 TAU_HOME env。"""
    tmp = tempfile.mkdtemp(prefix="email_report_smoke_")
    os.environ["TAU_HOME"] = tmp

    # 关键：reload 模块，让 CONFIG_DIR / CONFIG_FILE / SENT / EMAIL_LOG 常量
    # 用新的 TAU_HOME 重新求值（模块级常量只在 import 时求值一次）
    import core.paths
    importlib.reload(core.paths)  # 重读 TAU_HOME env（锚点首次 import 已冻结）
    import memory.email_config as email_config
    importlib.reload(email_config)
    import memory.email_send as email_send  # noqa: F401
    importlib.reload(email_send)

    # 建一份假的 "今日" 日报 docx（命名按 _today_docx 约定：以 today 开头）
    today = __import__("datetime").date.today().isoformat()
    docx_dir = os.path.join(tmp, "sche_tasks", "done")
    os.makedirs(docx_dir, exist_ok=True)
    docx_path = os.path.join(docx_dir, f"{today}_daily_report_test.docx")
    with open(docx_path, "wb") as f:
        f.write(b"fake docx content for smoke test")

    return tmp, docx_path


def _write_valid_cfg():
    from memory.email_config import save_email_config
    save_email_config({
        "smtp_host": "smtp.qq.com",
        "smtp_port": 465,
        "smtp_user": "u@qq.com",
        "smtp_pass": "tok",
        "to_addrs": ["a@x.com"],
    })


def test_a_v2_path_sends():
    """A. v2 路径：完整 cfg + 无今日 sent 标记 → SMTP 发信成功"""
    tmp, docx_path = _setup_home()
    import memory.email_send as email_send  # import 在 setup_home 之后，常量取 TAU_HOME 锚定
    try:
        _write_valid_cfg()

        sent_marker = email_send.SENT
        assert not os.path.exists(sent_marker), "sent marker should not exist"

        with patch("memory.email_send.smtplib.SMTP_SSL") as mock_ssl, \
             patch("memory.email_send.smtplib.SMTP")      as mock_plain:
            mock_ssl.return_value.__enter__.return_value = MagicMock()
            mock_plain.return_value.__enter__.return_value = MagicMock()
            result = email_send.send_email()
            assert "已发送" in result, result
            # SSL 路径（465）应被调用
            assert mock_ssl.called, "SMTP_SSL should be used for port 465"

        # 幂等标记应被写入
        assert os.path.exists(sent_marker), "sent marker should be created"
        with open(sent_marker) as f:
            content = f.read()
        assert "daily_" in content and ".docx" in content

        # 审计日志应追加 OK
        log = email_send.EMAIL_LOG
        assert os.path.exists(log), "audit log should exist"
        with open(log) as f:
            lines = f.readlines()
        assert any("OK" in ln for ln in lines), f"no OK line: {lines}"

        _ok("test_a_v2_path_sends")
    finally:
        del os.environ["TAU_HOME"]
        shutil.rmtree(tmp, ignore_errors=True)


def test_b_idempotent_skip():
    """B. 幂等：今天已发过 → 抛 RuntimeError 不重发"""
    tmp, docx_path = _setup_home()
    import memory.email_send as email_send
    try:
        _write_valid_cfg()
        # 预写今日 sent 标记
        today = __import__("datetime").date.today().isoformat()
        os.makedirs(os.path.dirname(email_send.SENT), exist_ok=True)
        with open(email_send.SENT, "w") as f:
            f.write(f"{today} {today}_daily_report_test.docx\n")

        from unittest.mock import patch
        with patch("memory.email_send.smtplib.SMTP_SSL") as mock_ssl:
            try:
                email_send.send_email()
            except RuntimeError as e:
                assert "已发过" in str(e), str(e)
                assert not mock_ssl.called, "SMTP must NOT be called on idempotent skip"
                _ok("test_b_idempotent_skip")
                return
            raise AssertionError("expected RuntimeError on idempotent send")
    finally:
        del os.environ["TAU_HOME"]
        shutil.rmtree(tmp, ignore_errors=True)


def test_c_unconfigured():
    """C. 未配置 → 抛 ValueError"""
    tmp, _ = _setup_home()
    import memory.email_send as email_send
    try:
        # 不写 cfg
        from memory.email_config import CONFIG_FILE
        assert not os.path.exists(CONFIG_FILE)

        try:
            email_send.send_email()
        except ValueError as e:
            assert "配置文件不存在" in str(e) or "请先跑" in str(e), str(e)
            _ok("test_c_unconfigured")
            return
        raise AssertionError("expected ValueError when unconfigured")
    finally:
        del os.environ["TAU_HOME"]
        shutil.rmtree(tmp, ignore_errors=True)


def test_d_docx_missing():
    """D. docx 缺失 → 抛 FileNotFoundError"""
    tmp, _ = _setup_home()
    import memory.email_send as email_send
    try:
        # tmp 默认会建一份今日 docx，用不存在的 done_dir 触发 FileNotFoundError
        empty_done = os.path.join(tmp, "empty_done")
        _write_valid_cfg()
        try:
            email_send.send_email(done_dir=empty_done)
        except FileNotFoundError as e:
            assert "没有" in str(e) or "sche_tasks" in str(e) or "empty_done" in str(e), str(e)
            _ok("test_d_docx_missing")
            return
        raise AssertionError("expected FileNotFoundError when docx missing")
    finally:
        del os.environ["TAU_HOME"]
        shutil.rmtree(tmp, ignore_errors=True)


def test_e_skip_no_audit():
    """E. SKIP 路径不再写 audit 行（避免 scheduler 重跑污染日志）"""
    tmp, _ = _setup_home()
    import memory.email_send as email_send
    try:
        _write_valid_cfg()
        today = __import__("datetime").date.today().isoformat()
        # 预写 sent 标记 → 触发 SKIP 路径
        os.makedirs(os.path.join(tmp, "temp"), exist_ok=True)
        with open(os.path.join(tmp, "temp", "email_report.sent"), "w") as f:
            f.write(f"{today} {today}_daily_report_test.docx\n")
        try:
            email_send.send_email()
        except RuntimeError as e:
            assert "已发过" in str(e), str(e)
        # 关键断言：audit log 不应被创建
        log_path = email_send.EMAIL_LOG
        assert not os.path.exists(log_path), f"SKIP 不应写 audit log, got {log_path}"
        _ok("test_e_skip_no_audit")
    finally:
        del os.environ["TAU_HOME"]
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("=== testing memory/email_send.py (smoke, 5 cases) ===")
    for fn in (
        test_a_v2_path_sends,
        test_b_idempotent_skip,
        test_c_unconfigured,
        test_d_docx_missing,
        test_e_skip_no_audit,
    ):
        try:
            fn()
        except Exception as e:
            _fail(fn.__name__, e)
            import traceback
            traceback.print_exc()

    print()
    print(f"=== {PASSED} passed, {FAILED} failed ===")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
