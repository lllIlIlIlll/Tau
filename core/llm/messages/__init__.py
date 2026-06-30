"""Tau LLM messages subpackage — horizontal responsibility.

集中收纳「消息/工具 schema 转换」「历史压缩」「响应解析」三个横向职责,
与 core/llm/providers/ 的纵向协议装订形成正交。

子模块(搬迁自原 core/llm/{convert,trim,response}.py):
- schema   — Claude ↔ OAI 消息/tool schema 双向转换
- history  — 历史压缩/截断(safeprint 来自 transport)
- response — MockResponse / MockToolCall / tryparse / 文本工具回退解析

旧路径兼容:
- core.llm.convert   → messages.schema
- core.llm.trim      → messages.history
- core.llm.response  → messages.response
通过 sys.modules 映射实现,外部 import 路径保持不变。
"""
import sys
from . import schema, history, response
from .schema import openai_tools_to_claude
from .response import MockFunction, MockToolCall, MockResponse, tryparse

# 旧路径兼容:让 from core.llm.convert/trim/response import X 仍可解析。
# 注意:sys.modules 映射只影响"从旧路径 import"这一行为;函数/类的 __module__ 属性
# 仍由其定义文件决定(即 core.llm.messages.{schema,history,response}),
# 这是 Task 8 smoke 脚本断言需要同步更新的原因。
sys.modules['core.llm.convert'] = schema
sys.modules['core.llm.trim'] = history
sys.modules['core.llm.response'] = response
