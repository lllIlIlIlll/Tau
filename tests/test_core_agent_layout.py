"""core/agent 子包结构不变量（refactor safety net）。
跟随 core/agent 重构进度逐 task 追加；全部绿 = 结构达标。"""

def test_format_leaf_importable():
    from core.agent.format import (
        json_default, get_pretty_json, _clean_content, _compact_tool_args,
    )
    # 行为快照（取自原 core/agent_loop.py，行为零变化）
    assert json_default({1, 2}) == [1, 2]
    assert json_default(object()) != [1, 2]  # 兜底 str
    assert "script" in get_pretty_json({"script": "a; b; c"})
    assert _clean_content("") == ""
    assert _compact_tool_args("ask_user", {"question": "q", "_index": 0}) == "q"


def test_loop_module_importable():
    from core.agent.loop import (
        StepOutcome, BaseHandler, try_call_generator, exhaust, agent_runner_loop,
    )
    o = StepOutcome(data=1, next_prompt="x", should_exit=False)
    assert o.data == 1 and o.next_prompt == "x" and o.should_exit is False
    assert hasattr(BaseHandler, "dispatch") and hasattr(BaseHandler, "turn_end_callback")
    assert callable(agent_runner_loop) and callable(exhaust) and callable(try_call_generator)


def test_loop_no_upper_deps():
    """loop.py 源码不得 import handler/runtime（依赖方向单向）。"""
    import core.agent.loop as m, inspect
    src = inspect.getsource(m)
    assert "from .handler" not in src and "from .runtime" not in src
    assert "import core.agent.handler" not in src and "import core.agent.runtime" not in src


def test_handler_module_importable():
    from core.agent.handler import TauHandler
    assert TauHandler.__module__ == "core.agent.handler"
    # BaseHandler 子类契约（确保继承自 loop.BaseHandler，非旧 agent_loop）
    from core.agent.loop import BaseHandler
    assert issubclass(TauHandler, BaseHandler)
    for do in ("do_code_run", "do_file_read", "do_file_write", "do_file_patch",
               "do_web_scan", "do_web_execute_js", "do_ask_user", "do_no_tool"):
        assert hasattr(TauHandler, do), f"TauHandler 缺 {do}"


def test_runtime_module_importable():
    from core.agent.runtime import Tau, get_system_prompt, load_tool_schema, main
    assert Tau.__module__ == "core.agent.runtime"
    assert callable(get_system_prompt) and callable(load_tool_schema) and callable(main)


def test_facade_exports():
    import core.agent
    for sym in ("Tau", "TauHandler", "agent_runner_loop", "BaseHandler", "StepOutcome"):
        assert hasattr(core.agent, sym), f"core.agent facade 缺 {sym}"
    # facade 符号指向子模块（非空 re-export）
    assert core.agent.Tau.__module__ == "core.agent.runtime"
    assert core.agent.TauHandler.__module__ == "core.agent.handler"


def test_shim_taumain_redirects():
    from core.taumain import Tau
    assert Tau.__module__ == "core.agent.runtime"  # shim 必须指向新实现


def test_shim_handler_redirects():
    from core.handler import TauHandler
    assert TauHandler.__module__ == "core.agent.handler"


def test_agent_loop_module_removed():
    """core.agent_loop 模块应已删除（无真实文件）。"""
    import importlib.util
    spec = importlib.util.find_spec("core.agent_loop")
    assert spec is None, f"core.agent_loop 仍存在: {spec}"
