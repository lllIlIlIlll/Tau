"""兼容 shim —— TauHandler 实现已迁至 core.agent.handler。
外部 `from core.handler import TauHandler` 继续可用（零修改）。

DEPRECATED shim — will be removed in v5.0. Use `core.agent.handler` instead.
"""
from core.agent.handler import TauHandler  # noqa: F401
