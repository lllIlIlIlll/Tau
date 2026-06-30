"""Tau agent 层 —— 对齐 Pi packages/agent 的分层组织（E-组织型，行为零变化）。

分层（单向依赖，无环）：
- format   输出整形叶子（loop + handler 共用）
- loop     无状态循环原语（agent_runner_loop / BaseHandler / StepOutcome）
- handler  TauHandler（工具适配器 + plan 模式 + turn_end 策略）
- runtime  Tau 编排器（任务队列 / 三种入口 / 流式 / LLM 会话管理）

公开 API（facade）只 re-export 这五个；format 四函数与 runtime 的
get_system_prompt/load_tool_schema/main 留子模块（按需 `from core.agent.<sub> import`），
遵循 core/llm 重构『_ 与内部 helper 留子模块』约定。
"""
from .loop import agent_runner_loop, BaseHandler, StepOutcome
from .handler import TauHandler
from .runtime import Tau
