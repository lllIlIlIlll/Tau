"""Tau LLM layer — split out of the original monolithic LLM core module.

Layout (post-2026-07-02 PR-1 flatten):
- keys.py         — taukey 加载/缓存
- transport.py    — URL 构造、SSE 重试、usage、日志（safeprint 由 messages 定义并 re-export）
- session.py      — BaseSession
- clients.py      — ToolClient / NativeToolClient / MixinSession / 工厂
- providers/      — 协议装订 + 流解析（claude / openai）
- messages.py     — 横向职责：消息/工具 schema 转换、历史压缩、响应解析

Public API (stable):
- Sessions:  BaseSession, ClaudeSession, LLMSession, NativeClaudeSession, NativeOAISession, MixinSession
- Clients:   ToolClient, NativeToolClient
- Factory:   resolve_session, resolve_client, fast_ask
- Keys:      reload_taukeys
- Response:  MockFunction, MockToolCall, MockResponse, tryparse
- Conv util: openai_tools_to_claude, auto_make_url

Internal helpers (prefix `_`) live in the submodules (messages, transport,
providers) — import them from there, not from this package. The two
exceptions below are kept on the facade only because out-of-package consumers
monkey-patch / read them: `_record_usage` (apps/common/cost_tracker),
`_load_taukeys` (plugins/langfuse_tracing).
"""
from .keys import reload_taukeys, _load_taukeys
from .transport import auto_make_url, _record_usage
from .messages import openai_tools_to_claude, MockFunction, MockToolCall, MockResponse, tryparse
from .session import BaseSession
from .providers.claude import ClaudeSession, NativeClaudeSession
from .providers.openai import LLMSession, NativeOAISession
from .clients import (
    ToolClient, NativeToolClient, MixinSession,
    resolve_session, resolve_client, fast_ask,
)