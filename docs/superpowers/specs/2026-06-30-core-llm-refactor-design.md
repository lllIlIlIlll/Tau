# core/llm 内部职责重构 — 设计文档

> 日期: 2026-06-30
> 范围: `core/llm/` 内部文件组织重构，外部零破坏
> 参考: https://github.com/earendil-works/pi/tree/main/packages/ai（仅职责切分思路）

---

## 1. 背景与目标

Tau 的 `core/llm/` 当前 9 个文件、约 1116 行，已按"职责拆分"分层但**仍混入横向职责**——`convert.py`（消息/工具 schema 转换）、`trim.py`（历史压缩）、`response.py`（响应解析）这 3 个文件本质都是"消息形态加工"，与具体 provider/协议无关，却平铺在 `core/llm/` 顶层，与 `session.py`、`clients.py`、`providers/` 这些跟 provider/协议耦合的模块混在一起。

参考 Pi `packages/ai` 的目录组织（`stream.ts` / `types.ts` / `models.ts` / `providers/` / `utils/` / `oauth/`），其核心架构优点是**"协议层（Api）≠ 提供商层（Provider）"正交化** + **"通用工具"独立子包**。本设计借鉴"通用工具独立子包"这一条，对**横向职责**做集中收纳，但不引入 Provider/Api 拆解（避免超出本次范围）。

### 目标

- 把"消息形态加工"（convert / trim / response）集中到 `core/llm/messages/` 子包。
- `providers/` 退回到只承担"协议装订 + 流解析"的纵向职责。
- **`core/llm/__init__.py` 的公开导出符号集合保持一字不动**——外部调用方零修改。
- 旧的内部 import 路径（如 `from core.llm.convert import openai_tools_to_claude`）继续可用。

### 非目标

- 不引入 Pi 的 Provider/Api 正交化（保持现状：provider = 协议）。
- 不新增 provider（Google / Mistral 等）。
- 不引入 OAuth 套件、TypeBox schema 校验、image-models 子系统、registry 抽象。
- 不动 `clients.py` 内部结构（仅更新其 import 行）。
- 不动 `transport.py`、`session.py`、`keys.py`、`providers/*` 业务逻辑（仅更新其 import 行）。
- 不重写 `clients.MixinSession` 故障转移、`!!!Error:` 字符串协议、`tryparse` JSON fallback 协议等已稳定子系统。

---

## 2. 目录结构

```
core/llm/                           # 总入口（外部零改动）
├── __init__.py                     # 9 行 re-export 主体不动；docstring 更新为 5 子包说明
├── keys.py                         # taukey 加载/缓存（不动）
├── transport.py                    # URL/SSE 重试/usage/日志（不动；safeprint 留此）
├── session.py                      # BaseSession（不动）
├── clients.py                      # ToolClient/NativeToolClient/MixinSession/工厂（不动；仅改 import 行）
├── providers/                      # 纯协议装订 + 流解析（不动业务；仅改 import 行）
│   ├── __init__.py
│   ├── claude.py
│   └── openai.py
└── messages/                       # ← 新建子包：消息形态加工（横向职责）
    ├── __init__.py                 # re-export 旧 convert/trim/response 公开符号 + sys.modules 兼容映射
    ├── schema.py                   # ← 原 convert.py 内容（搬迁不改）
    ├── history.py                  # ← 原 trim.py 内容（搬迁；safeprint 不在此）
    └── response.py                 # ← 原 response.py 内容（搬迁不改）
```

**核心边界**：横向（`messages/`）= 跟 provider 无关的消息形态工作；纵向（`providers/`）= 跟协议绑定的装订/解析。两者通过 `session.py` 这层"实例属性 + ask 流生成器"粘合。

---

## 3. 职责映射（逐函数级）

| 当前位置 | 目标位置 | 角色 |
|---|---|---|
| `convert.py: openai_tools_to_claude` | `messages/schema.py` | OAI↔Claude tool schema 互转（**公开**） |
| `convert.py: _try_parse_tool_args` | `messages/schema.py` | 解析 OAI tool args（支持粘接 JSON） |
| `convert.py: _stamp_oai_cache_markers` | `messages/schema.py` | 给 OAI 兼容中转打 Anthropic cache_control |
| `convert.py: _prepare_oai_tools` | `messages/schema.py` | OAI `chat_completions` ↔ `responses` tool 形态切换 |
| `convert.py: _to_responses_input` | `messages/schema.py` | messages → responses API `input[]` |
| `convert.py: _msgs_claude2oai` | `messages/schema.py` | Claude content-block → OAI messages |
| `convert.py: _fix_messages` | `messages/schema.py` | Claude messages 交替/tool 配对修复 |
| `convert.py: _drop_unsigned_thinking` | `messages/schema.py` | 丢弃无 signature 的 thinking |
| `convert.py: _ensure_thinking_blocks` | `messages/schema.py` | deepseek 等需要补占位 thinking |
| `trim.py: compress_history_tags` | `messages/history.py` | 历史长消息压缩 |
| `trim.py: _sanitize_leading_user_msg` | `messages/history.py` | 头位 user 消息的 tool_result 改写 |
| `trim.py: trim_messages_history` | `messages/history.py` | 历史总成本上限裁剪 |
| `trim.py: safeprint` | **`safeprint` 定义保留在 `messages/history.py`**；原 `transport.py:4` 的 `from .trim import safeprint` 改为 `from .messages.history import safeprint`（history 不依赖 transport；transport 依赖 history） | 静默 print 防 OSError；定义与原始 `trim.py` 同一文件 |
| `response.py`（全部内容） | `messages/response.py`（原样搬移） | `MockResponse` / `MockToolCall` / `MockFunction` / `tryparse` / `_parse_text_tool_calls` / `_ensure_text_block` |
| `clients.py: ToolClient._parse_mixed_response` 内调用 `_parse_text_tool_calls` | import 改为 `from .messages.response import _parse_text_tool_calls` | 内部依赖路径变更 |
| `providers/claude.py` 中 4 行 `from ..convert/trim/response` | 改为 `from ..messages.schema/...` / `from ..messages.response import ...` / `from ..messages.history import ...` | import 路径更新 |
| `providers/openai.py` 同上 | 同上 | 同上 |
| `session.py` 的 `from .trim import trim_messages_history, safeprint` | 改为 `from .messages.history import trim_messages_history` + `from .transport import safeprint` | import 路径更新 |

### 关键不变量

- `safeprint` **定义保留在 `messages/history.py`**（与 `compress_history_tags` 的 `[Cut]`/`[Debug]` log 同处）。`transport.py:4` 的 `from .trim import safeprint` 改为 `from .messages.history import safeprint`。多文件 import safeprint 仍从 `transport.py` 间接获得（re-export），但**单向依赖**：transport → history，无循环。
- `messages/response.py` 的所有函数都是**纯函数**，从 `response.py` 文件级搬到 `messages/response.py` 一字不改。
- `messages/__init__.py` 必须做 `sys.modules` 兼容映射：
  ```python
  import sys
  from . import schema, history, response
  sys.modules['core.llm.convert'] = schema
  sys.modules['core.llm.trim'] = history
  sys.modules['core.llm.response'] = response
  ```
  作用：旧路径 `from core.llm.convert import openai_tools_to_claude` 仍可解析（虽然该形式不推荐继续使用，但保证零破坏）。
- `__init__.py` 公开符号集合**一字不动**：
  ```python
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
  ```
  注意：上述 `from .convert import ...` 与 `from .response import ...` 在新结构下分别解析到 `messages.schema` 与 `messages.response`（靠 `messages/__init__.py` 的 re-export 与 `sys.modules` 兼容映射共同保证）。

---

## 4. 数据流

一次完整 `chat(messages, tools)` 调用：

```
用户/调用方 (apps/im/*, apps/pet/app.py)
        │
        │ chat(messages, tools)
        ▼
clients.ToolClient  ──┐
clients.NativeToolClient ──┐
                          │
        ┌─────────────────┴─────────────────┐
        │ 1. 消息形态加工 (横向)              │
        │   messages.history.trim_messages_history(...)
        │   messages.schema._fix_messages(...)
        │   messages.schema._msgs_claude2oai(...) [仅 OAI]
        │   messages.schema._to_responses_input(...) [仅 responses]
        │   messages.schema.openai_tools_to_claude(...) [仅 NativeClaude]
        └─────────────────┬─────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────┐
        │ 2. 协议装订 + 网络传输 (纵向)        │
        │   session.BaseSession.ask / raw_ask │
        │     ├ providers.claude.*Session    │
        │     │   └ transport._stream_with_retry(SSE) ── HTTP ──→ upstream
        │     └ providers.openai.*Session     │
        │         └ transport._stream_with_retry(SSE) ── HTTP ──→ upstream
        └─────────────────┬───────────────────┘
                          │  text chunks (generator)
                          ▼
        ┌─────────────────────────────────────┐
        │ 3. 响应还原 (横向)                    │
        │   messages.response.tryparse        │
        │   messages.response._parse_text_tool_calls
        │   messages.response.MockResponse 构造
        └─────────────────┬───────────────────┘
                          │
                          ▼
        返回 MockResponse {thinking, content, tool_calls, raw}
```

横切关注点 `transport._record_usage`、`transport._write_llm_log` 在第 2 步内触发。`clients.py` 同时调度横向（`messages/`）与纵向（`providers/`）。

---

## 5. 错误处理（沿用现状，不重新设计）

- **网络/HTTP**：`transport._stream_with_retry` 处理 `{408,409,425,429,500,502,503,504,529}` + `Timeout`/`ConnectionError`，指数退避，最长 30s。已稳定且独立，不重构。
- **流中断**：`!!!Error: ...` 字符串协议（`providers/claude.py` 与 `providers/openai.py` 都在用）。`clients.MixinSession` 通过 `test_error = lambda x: isinstance(x,str) and x.lstrip().startswith(('!!!Error:','[Error:'))` 识别。协议字符串保持不变。
- **JSON 解析失败**：`messages/response.py` `tryparse` 多级 fallback；tool 解析失败 → `MockToolCall('bad_json', {...})` 软失败而非抛异常。
- **taukey mtime 缓存**：`keys.reload_taukeys` 自动检测改动；`core.paths.TAUKEY_PATH` 找不到 → 报错指向 `tau configure`。

### 不做之事（明确边界）

1. 不动 `clients.py` 内部结构。
2. 不动 `providers/` 的 provider/Api 绑定（保持"provider = 协议"现状）。
3. 不加新 provider（Google/Mistral 等）。
4. 不加 OAuth 套件、TypeBox schema 校验、image-models 子系统、registry 抽象。
5. 不引入生成物（model registry codegen）——Tau 的模型列表在 `taukey.json` 里手维护。
6. 不重写任何已稳定子系统的实现。

---

## 6. 迁移步骤（按风险递增顺序，每步独立 commit）

1. **创建 `core/llm/messages/` 子包骨架**：`mkdir -p core/llm/messages` + 空 `__init__.py`。
2. **搬 `response.py` → `messages/response.py`**：纯文件复制，无内容改动。
   - 验证：`python -c "from core.llm.response import MockResponse, MockToolCall, tryparse"` 通过。
3. **搬 `trim.py` → `messages/history.py`**（不含 `safeprint`）：纯文件复制 + 删除 `safeprint` 行；本文件 import `safeprint` 改为 `from .transport import safeprint`。
   - 验证：`from core.llm.trim import trim_messages_history` 通过（依赖最终兼容层）。
4. **搬 `convert.py` → `messages/schema.py`**：纯文件复制，无内容改动。
   - 验证：`from core.llm.convert import openai_tools_to_claude` 通过（依赖最终兼容层）。
5. **写 `messages/__init__.py`**：
   - 从 `messages.schema/history/response` 重新导出公开符号（`openai_tools_to_claude`、`tryparse`、`MockFunction`、`MockToolCall`、`MockResponse`）。
   - 设置 `sys.modules['core.llm.convert'] = schema`、`sys.modules['core.llm.trim'] = history`、`sys.modules['core.llm.response'] = response`。
6. **更新内部 import 路径**：
   - `providers/claude.py`：4 行 `from ..convert/trim/response` → `from ..messages.schema/...` 等。
   - `providers/openai.py`：同上。
   - `clients.py`：1 行 `_parse_text_tool_calls` import → `from .messages.response import _parse_text_tool_calls`。
   - `session.py`：1 行 `from .trim import` → `from .messages.history import trim_messages_history` + `from .transport import safeprint`。
7. **更新 `scripts/smoke_llmcore.py`**：脚本里 12 条 `assert ... __module__.endswith('llm.trim/convert/response/transport/clients/providers.*')` 断言改为新模块路径：
   - `llm.trim` → `llm.messages.history`
   - `llm.convert` → `llm.messages.schema`
   - `llm.response` → `llm.messages.response`
   - 其余（`llm.transport` / `llm.session` / `llm.clients` / `llm.providers.*`）不变
   - `from core.llm.trim import ...` / `from core.llm.convert import ...` 改为 `from core.llm.messages.history import ...` / `from core.llm.messages.schema import ...`
8. **删除旧文件**：`rm core/llm/convert.py core/llm/trim.py core/llm/response.py`。**删除前** `git grep "from core\.llm\.convert\|from core\.llm\.trim\|from core\.llm\.response"` 应无外部残留（仅 `__init__.py` re-export 行 + 兼容映射）。
9. **更新 `core/llm/__init__.py` 顶部 docstring**：从"9 个文件"叙述改成"5 个子包"叙述；9 行 `from ... import ...` 主体**一字不动**。
10. **最终验证**：
    - `python -c "import core.llm; print(sorted(dir(core.llm)))"` 与重构前对照，公开符号集合不变。
    - `pytest tests/test_taukey_path.py` 绿。
    - `python scripts/smoke_llmcore.py` 跑通（新断言全部绿）。
    - `git grep -nE "from core\.llm\.convert|from core\.llm\.trim|from core\.llm\.response"` → 应只剩 `__init__.py` 9 行 re-export 主体（这些是公开 API，不是兼容层）；**核心兼容层在 `messages/__init__.py` 的 `sys.modules` 映射**。

### 回滚预案

每步独立 commit；任一步出错 `git revert <sha>` 即可，无数据库/无迁移。

---

## 7. 验收清单

- [ ] `core/llm/__init__.py` 9 行 re-export 一字不动
- [ ] `core.llm.openai_tools_to_claude / MockResponse / MockToolCall / MockFunction / tryparse / ToolClient / NativeToolClient / ClaudeSession / NativeClaudeSession / LLMSession / NativeOAISession / MixinSession / BaseSession / resolve_session / resolve_client / fast_ask / reload_taukeys / auto_make_url / _load_taukeys / _record_usage` 全部仍可 `from core.llm import X`
- [ ] 旧 import 路径 `from core.llm.convert import openai_tools_to_claude` 仍可解析（靠 `messages/__init__.py` 的 `sys.modules` 兼容映射）
- [ ] `from core.llm.response import ...` / `from core.llm.trim import ...` 通过 `sys.modules` 兼容层仍可解析
- [ ] `tests/test_taukey_path.py` 全绿
- [ ] `scripts/smoke_llmcore.py` 跑通（**注意**: 该脚本当前断言内部 `__module__` 以 `llm.trim/convert/response/transport/clients/providers.*` 结尾——重构后这些断言需改写为 `llm.messages.{schema,history,response}`，详见迁移步骤 8 后的脚本更新）
- [ ] `git grep` 验证外部调用方（`apps/*`、`plugins/*`、`scripts/*`）无 import 路径变更
- [ ] `core/llm/convert.py` / `core/llm/trim.py` / `core/llm/response.py` 物理删除

---

## 8. 参考

- Pi `packages/ai` 目录结构：https://github.com/earendil-works/pi/tree/main/packages/ai
- 本地副本（用于离线对照）：`/Users/x404/agents/pi/packages/ai/src/`
- 本地已用 Pi 对标约定（参见 [[pi-local-copy-path]]）
- Tau 结构哲学（参见 [[tau-structure-philosophy]]）：不重排顶层目录，`core/llm/` 内部子包划分不违反此约定
