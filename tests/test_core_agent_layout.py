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
