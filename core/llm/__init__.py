"""Tau LLM layer — split out of the original monolithic LLM core module.

Public API (stable):
- Sessions:  BaseSession, ClaudeSession, LLMSession, NativeClaudeSession, NativeOAISession, MixinSession
- Clients:   ToolClient, NativeToolClient
- Factory:   resolve_session, resolve_client, fast_ask
- Keys:      reload_taukeys
- Response:  MockFunction, MockToolCall, MockResponse, tryparse
- Conv util: openai_tools_to_claude, auto_make_url

Internal helpers (prefix `_`) live in the submodules (trim/transport/convert/
response/providers) — import them from there, not from this package. The two
exceptions below are kept on the facade only because out-of-package consumers
monkey-patch / read them: `_record_usage` (apps/common/cost_tracker),
`_load_taukeys` (plugins/langfuse_tracing).
"""
from .keys import reload_taukeys, _load_taukeys
from .transport import auto_make_url, _record_usage
from .convert import openai_tools_to_claude
from .response import MockFunction, MockToolCall, MockResponse, tryparse
from .session import BaseSession
from .providers.claude import ClaudeSession, NativeClaudeSession
from .providers.openai import LLMSession, NativeOAISession
from .clients import (
    ToolClient, NativeToolClient, MixinSession,
    resolve_session, resolve_client, fast_ask,
)
