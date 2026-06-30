"""Smoke test: the core.llm public API imports cleanly from the package facade,
and internal helpers import from their submodules (post-install, no compat shim).
taukeys lives on core.llm.keys."""
# Public API — from the package facade.
from core.llm import (
    reload_taukeys,
    BaseSession, LLMSession, ClaudeSession, NativeClaudeSession, NativeOAISession,
    ToolClient, NativeToolClient, MixinSession,
    resolve_session, resolve_client, fast_ask,
    auto_make_url, openai_tools_to_claude,
    MockFunction, MockToolCall, MockResponse, tryparse,
)
# Load-bearing privates kept on the facade for out-of-package consumers
# (plugins/langfuse_tracing._load_taukeys, apps/common/cost_tracker._record_usage).
from core.llm import _load_taukeys, _record_usage
# Internals live in submodules — new code imports them there, not from the package.
from core.llm.trim import compress_history_tags, trim_messages_history, safeprint
from core.llm.transport import _stream_with_retry, _write_llm_log
from core.llm.convert import (_fix_messages, _msgs_claude2oai, _to_responses_input,
                              _drop_unsigned_thinking, _ensure_thinking_blocks,
                              _stamp_oai_cache_markers, _prepare_oai_tools, _try_parse_tool_args)
from core.llm.keys import taukeys
assert compress_history_tags.__module__.endswith('llm.trim'), compress_history_tags.__module__
assert auto_make_url.__module__.endswith('llm.transport'), auto_make_url.__module__
assert _stream_with_retry.__module__.endswith('llm.transport'), _stream_with_retry.__module__
assert _record_usage.__module__.endswith('llm.transport'), _record_usage.__module__
assert _write_llm_log.__module__.endswith('llm.transport'), _write_llm_log.__module__
assert _fix_messages.__module__.endswith('llm.convert'), _fix_messages.__module__
assert _msgs_claude2oai.__module__.endswith('llm.convert'), _msgs_claude2oai.__module__
assert openai_tools_to_claude.__module__.endswith('llm.convert'), openai_tools_to_claude.__module__
assert MockResponse.__module__.endswith('llm.response'), MockResponse.__module__
assert MockToolCall.__module__.endswith('llm.response'), MockToolCall.__module__
assert tryparse.__module__.endswith('llm.response'), tryparse.__module__
assert BaseSession.__module__.endswith('llm.session'), BaseSession.__module__
assert ClaudeSession.__module__.endswith('llm.providers.claude'), ClaudeSession.__module__
assert NativeClaudeSession.__module__.endswith('llm.providers.claude'), NativeClaudeSession.__module__
assert LLMSession.__module__.endswith('llm.providers.openai'), LLMSession.__module__
assert NativeOAISession.__module__.endswith('llm.providers.openai'), NativeOAISession.__module__
assert ToolClient.__module__.endswith('llm.clients'), ToolClient.__module__
assert NativeToolClient.__module__.endswith('llm.clients'), NativeToolClient.__module__
assert MixinSession.__module__.endswith('llm.clients'), MixinSession.__module__
assert resolve_client.__module__.endswith('llm.clients'), resolve_client.__module__

from core.paths import TAUKEY_PATH
print(f'[SMOKE-OK] taukey_path={TAUKEY_PATH} '
      f'taukeys_loaded={len(taukeys)} '
      f'private_load={_load_taukeys.__name__} '
      f'classes=({LLMSession.__name__},{ToolClient.__name__},{MixinSession.__name__}) '
      f'trim={compress_history_tags.__module__} '
      f'transport={auto_make_url.__module__} '
      f'convert={_fix_messages.__module__} '
      f'response={MockResponse.__module__} '
      f'session={BaseSession.__module__} '
      f'claude={ClaudeSession.__name__} '
      f'openai={LLMSession.__name__} '
      f'clients={ToolClient.__module__}')
