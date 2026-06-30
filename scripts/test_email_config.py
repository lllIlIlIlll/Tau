"""test_email_config.py - T-04 库单元测试

覆盖 memory.email_config 的所有公共 API:
  - 常量 (REQUIRED / DEFAULTS / CONFIG_DIR / CONFIG_FILE)
  - has_email_config / validate / save_email_config / load_email_config
  - infer_provider (5 域名 + 大小写不敏感 + 未知/null/空)
  - save 输入不变 / 文件权限 600 / save+load 往返

所有测试使用临时 cwd，绝不触碰真实 .tau/tauchain.json
"""
import os
import sys
import shutil
import tempfile
import importlib

# memory/ 用裸名 import（与 daily_report_* 一致，无 __init__.py）
MEM_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "memory"
)
if MEM_DIR not in sys.path:
    sys.path.insert(0, MEM_DIR)

import email_config  # noqa: E402

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


def test_imports():
    required = [
        "REQUIRED", "DEFAULTS", "CONFIG_DIR", "CONFIG_FILE",
        "has_email_config", "validate", "save_email_config",
        "load_email_config", "infer_provider",
    ]
    for name in required:
        assert hasattr(email_config, name), f"missing: {name}"
    _ok("imports")


def test_constants():
    assert set(email_config.REQUIRED) == {
        "smtp_host", "smtp_port", "smtp_user", "smtp_pass", "to_addrs",
    }
    assert "smtp_use_ssl" in email_config.DEFAULTS
    assert "smtp_timeout" in email_config.DEFAULTS
    assert "subject" in email_config.DEFAULTS
    assert "body" in email_config.DEFAULTS
    assert "sender_name" in email_config.DEFAULTS
    assert email_config.CONFIG_DIR.endswith(".tau")
    assert email_config.CONFIG_FILE.endswith(".tau/tauchain.json")
    _ok("constants")


def test_has_email_config_false():
    assert email_config.has_email_config() is False
    _ok("has_email_config_false")


def _valid_cfg():
    return {
        "smtp_host": "smtp.qq.com",
        "smtp_port": 465,
        "smtp_user": "u@qq.com",
        "smtp_pass": "tok",
        "to_addrs": ["a@x.com"],
    }


def test_save_load_roundtrip():
    cfg = _valid_cfg()
    email_config.save_email_config(cfg)
    loaded = email_config.load_email_config()
    assert loaded["smtp_host"] == "smtp.qq.com"
    assert loaded["smtp_pass"] == "tok"  # 明文存储
    assert loaded["to_addrs"] == ["a@x.com"]
    assert loaded["smtp_use_ssl"] is True  # 465 → ssl=True
    assert loaded["subject"] == "Tau 日报 {date}"  # default
    assert "meta" in loaded and loaded["meta"]["version"] == 1
    _ok("save_load_roundtrip")


def test_save_file_mode_600():
    cfg = _valid_cfg()
    email_config.save_email_config(cfg)
    mode = oct(os.stat(email_config.CONFIG_FILE).st_mode & 0o777)
    assert mode == "0o600", f"expected 0o600, got {mode}"
    _ok("save_file_mode_600")


def test_load_missing():
    if os.path.exists(email_config.CONFIG_FILE):
        os.remove(email_config.CONFIG_FILE)
    try:
        email_config.load_email_config()
    except ValueError as e:
        assert "配置文件不存在" in str(e)
        _ok("load_missing")
        return
    raise AssertionError("load_email_config should raise when missing")


def test_validate_empty():
    errs = email_config.validate({})
    assert "缺少字段: smtp_host" in errs
    assert "缺少字段: smtp_pass" in errs
    _ok("validate_empty")


def test_validate_full():
    cfg = _valid_cfg()
    assert email_config.validate(cfg) == []
    _ok("validate_full")


def test_validate_bad_port():
    cfg = _valid_cfg()
    cfg["smtp_port"] = "abc"
    errs = email_config.validate(cfg)
    assert any("smtp_port" in e for e in errs), errs
    _ok("validate_bad_port")


def test_validate_toaddrs_nonlist():
    cfg = _valid_cfg()
    cfg["to_addrs"] = "single@x.com"
    errs = email_config.validate(cfg)
    assert "to_addrs" in " ".join(errs)
    _ok("validate_toaddrs_nonlist")


def test_validate_toaddrs_empty_list():
    cfg = _valid_cfg()
    cfg["to_addrs"] = []
    errs = email_config.validate(cfg)
    assert any("to_addrs" in e for e in errs), errs
    _ok("validate_toaddrs_empty_list")


def test_infer_provider_qq():
    r = email_config.infer_provider("u@qq.com")
    assert r and r["host"] == "smtp.qq.com" and r["port"] == 465
    _ok("infer_provider_qq")


def test_infer_provider_gmail():
    r = email_config.infer_provider("u@gmail.com")
    assert r and r["host"] == "smtp.gmail.com" and r["port"] == 587
    _ok("infer_provider_gmail")


def test_infer_provider_163():
    r = email_config.infer_provider("u@163.com")
    assert r and r["host"] == "smtp.163.com" and r["port"] == 465
    _ok("infer_provider_163")


def test_infer_provider_unknown():
    assert email_config.infer_provider("u@unknown.com") is None
    assert email_config.infer_provider("not-an-email") is None
    assert email_config.infer_provider("") is None
    assert email_config.infer_provider(None) is None
    _ok("infer_provider_unknown")


def test_infer_provider_case_insensitive():
    r = email_config.infer_provider("U@QQ.COM")
    assert r and r["host"] == "smtp.qq.com"
    _ok("infer_provider_case_insensitive")


def test_save_input_not_mutated():
    cfg = _valid_cfg()
    original_keys = set(cfg.keys())
    email_config.save_email_config(cfg)
    assert set(cfg.keys()) == original_keys
    _ok("save_input_not_mutated")


def test_save_partial_raises():
    cfg = {"smtp_host": "smtp.qq.com"}  # 缺 4 个字段
    try:
        email_config.save_email_config(cfg)
    except ValueError as e:
        assert "缺少字段" in str(e)
        _ok("save_partial_raises")
        return
    raise AssertionError("save should raise on partial cfg")


def main():
    print("=== testing memory/email_config.py ===")
    tmp = tempfile.mkdtemp(prefix="email_cfg_test_")
    os.environ["TAU_HOME"] = tmp
    # reload 让 CONFIG_DIR / CONFIG_FILE 常量用新 TAU_HOME 重新求值
    importlib.reload(email_config)
    try:
        tests = [
            test_imports, test_constants, test_has_email_config_false,
            test_save_load_roundtrip, test_save_file_mode_600,
            test_load_missing,
            test_validate_empty, test_validate_full,
            test_validate_bad_port, test_validate_toaddrs_nonlist,
            test_validate_toaddrs_empty_list,
            test_infer_provider_qq, test_infer_provider_gmail,
            test_infer_provider_163, test_infer_provider_unknown,
            test_infer_provider_case_insensitive,
            test_save_input_not_mutated, test_save_partial_raises,
        ]
        for fn in tests:
            try:
                fn()
            except Exception as e:
                _fail(fn.__name__, e)
    finally:
        del os.environ["TAU_HOME"]
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print(f"=== {PASSED} passed, {FAILED} failed ===")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
