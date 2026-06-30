# core/llm 内部职责重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `core/llm/` 内部按"横向职责"与"纵向职责"切分，新增 `messages/` 子包收纳 `convert/trim/response`，外部零破坏。

**Architecture:** 单文件级搬迁 + import 路径更新 + `sys.modules` 兼容层 + 仓库内 smoke 脚本断言改写。每步独立 commit，可独立回滚。

**Tech Stack:** Python ≥3.10,<3.14 · 现有 `core/llm/` 模块树 · `pytest` · `uv` 包管理 · 无新依赖

## 全局约束

- 工作目录: `/Users/x404/Tau/.worktrees/tau-v4.0.0`
- 所有路径相对此根
- 包管理器: uv (不用 pip/venv/poetry) — 来自 [[uv-default-package-manager]]
- Python 版本: `>=3.10,<3.14` (pyproject.toml:11)
- 提交语言: 英文(commit message) / 中文(spec + 对话)
- 重构后**不修改**:
  - `core/llm/__init__.py` 的 9 行 `from ... import ...` 主体
  - `core/llm/transport.py` / `core/llm/keys.py` / `core/llm/session.py` / `core/llm/providers/claude.py` / `core/llm/providers/openai.py` / `core/llm/clients.py` 的业务逻辑（仅改 import 行）
  - `core/llm/messages/` 下三个新文件的内部代码（纯搬迁，零修改）
  - 任何 `apps/*` / `plugins/*` / `tests/*`（除 `scripts/smoke_llmcore.py`）
- 重构后**新增/修改**:
  - 新增 `core/llm/messages/__init__.py` / `messages/schema.py` / `messages/history.py` / `messages/response.py`
  - 修改 `core/llm/session.py:3` / `clients.py:7` / `providers/claude.py:3-6` / `providers/openai.py:3-8` 的 import 行
  - 修改 `core/llm/__init__.py` 顶部 docstring
  - 修改 `scripts/smoke_llmcore.py` 的 import 行与 `__module__` 断言
  - 删除 `core/llm/convert.py` / `core/llm/trim.py` / `core/llm/response.py`

## 任务总览

| # | 任务 | 文件 | commit 类型 |
|---|---|---|---|
| 1 | 建 messages/ 子包骨架 | `core/llm/messages/__init__.py` (新) | chore |
| 2 | 搬迁 response.py | `core/llm/messages/response.py` (新) | refactor |
| 3 | 搬迁 trim.py (剔除 safeprint) | `core/llm/messages/history.py` (新) | refactor |
| 4 | 搬迁 convert.py | `core/llm/messages/schema.py` (新) | refactor |
| 5 | 写 messages/__init__.py 兼容层 | `core/llm/messages/__init__.py` (改) | feat |
| 6 | 改 session.py + clients.py import | 2 文件 (改) | refactor |
| 7 | 改 providers/{claude,openai}.py import | 2 文件 (改) | refactor |
| 8 | 改 scripts/smoke_llmcore.py 断言 | 1 文件 (改) | test |
| 9 | 删旧文件 + 更新 __init__.py docstring + 终验 | 3 文件 (删) + 1 文件 (改) | chore |

---

## Task 1: 建 messages/ 子包骨架

**Files:**
- Create: `core/llm/messages/__init__.py`

**Step 1:**

- [ ] **Step 1: 创建空 `__init__.py`**

```bash
mkdir -p core/llm/messages
touch core/llm/messages/__init__.py
```

- [ ] **Step 2: 验证包存在**

Run: `ls -la core/llm/messages/`
Expected: 看到 `__init__.py` 文件，size = 0

- [ ] **Step 3: 验证不破坏现有 import**

Run: `python -c "from core.llm.convert import openai_tools_to_claude; print('ok')"`
Expected: 输出 `ok`（旧文件仍在，`messages/__init__.py` 是空的不影响 import）

- [ ] **Step 4: Commit**

```bash
git add core/llm/messages/__init__.py
git commit -m "chore(llm): scaffold messages/ subpackage (empty)"
```

---

## Task 2: 搬迁 response.py → messages/response.py

**Files:**
- Create: `core/llm/messages/response.py` (内容为原 `core/llm/response.py` 全文)
- Read for copy: `core/llm/response.py`

**Step 1:**

- [ ] **Step 1: 创建 `messages/response.py`**

文件路径 `core/llm/messages/response.py`，**内容逐字复制** `core/llm/response.py`（59 行原封不动），不做任何修改：

```python
"""Mock response objects + text-mode tool-call fallback parsers."""
import json, re

class MockFunction:
    def __init__(self, name, arguments): self.name, self.arguments = name, arguments

class MockToolCall:
    def __init__(self, name, args, id=''):
        arg_str = json.dumps(args, ensure_ascii=False) if isinstance(args, (dict, list)) else (args or '{}')
        self.function = MockFunction(name, arg_str); self.id = id

class MockResponse:
    def __init__(self, thinking, content, tool_calls, raw, stop_reason='end_turn'):
        self.thinking = thinking; self.content = content
        self.tool_calls = tool_calls; self.raw = raw
        self.stop_reason = 'tool_use' if tool_calls else stop_reason
    def __repr__(self):
        return f"<MockResponse thinking={bool(self.thinking)}, content='{self.content}', tools={bool(self.tool_calls)}>"

def tryparse(json_str):
    try: return json.loads(json_str)
    except Exception: pass
    json_str = json_str.strip().strip('`').replace('json\n', '', 1).strip()
    try: return json.loads(json_str)
    except Exception: pass
    try: return json.loads(json_str[:-1])
    except Exception: pass
    if '}' in json_str: json_str = json_str[:json_str.rfind('}') + 1]
    return json.loads(json_str)

def _parse_text_tool_calls(content):
    """Fallback: extract tool calls from text when model doesn't use native tool_use blocks."""
    tcs = []
    _jp = next((p for p in ['[{"type":"tool_use"', '[{"type": "tool_use"'] if p in content), None)
    if _jp and content.endswith('}]'):
        try:
            idx = content.index(_jp); raw = json.loads(content[idx:])
            tcs = [MockToolCall(b["name"], b.get("input", {}), id=b.get("id", "")) for b in raw if b.get("type") == "tool_use"]
            return tcs, content[:idx].strip()
        except Exception: pass
    _xp = r"<(?:tool_use|tool_call)>((?:(?!<(?:tool_use|tool_call)>).){15,}?)</(?:tool_use|tool_call)>"
    for s in re.findall(_xp, content, re.DOTALL):
        try:
            d = tryparse(s.strip()); name = d.get('name')
            args = d.get('arguments') or d.get('args') or d.get('input') or {}
            if name: tcs.append(MockToolCall(name, args))
        except Exception: pass
    if tcs: content = re.sub(_xp, "", content, flags=re.DOTALL).strip()
    return tcs, content

def _ensure_text_block(blocks):
    """If response has thinking but no text block, inject a synthetic summary from thinking's first line."""
    if any(b.get("type") == "text" for b in blocks): return None
    th = next((b.get("thinking", "") for b in blocks if b.get("type") == "thinking"), "")
    if not th: return None
    line = th.strip().split('\n', 1)[0]
    txt = "<summary>" + (line[:60] + '...' if len(line) > 60 else line) + "</summary>"
    blocks.insert(1, {"type": "text", "text": txt})
    return txt
```

- [ ] **Step 2: 验证 `messages.response` 可独立 import**

Run: `python -c "from core.llm.messages.response import MockResponse, MockToolCall, MockFunction, tryparse, _parse_text_tool_calls, _ensure_text_block; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 3: 验证旧路径仍可用**

Run: `python -c "from core.llm.response import MockResponse; print(MockResponse.__module__)"`
Expected: 输出 `core.llm.response`（旧 `response.py` 还在，路径未受影响）

- [ ] **Step 4: Commit**

```bash
git add core/llm/messages/response.py
git commit -m "refactor(llm): move response.py to messages/response.py (verbatim copy)"
```

---

## Task 3: 搬迁 trim.py → messages/history.py（剔除 safeprint）

**Files:**
- Create: `core/llm/messages/history.py`
- Read for copy: `core/llm/trim.py`

**Interfaces:**
- Consumes: `safeprint`（来自 `core.llm.transport`，本任务 import 它而非定义）
- Produces: `trim_messages_history(history, sess)`、`compress_history_tags(messages, keep_recent=10, max_len=800, force=False, interval=5)`、`_sanitize_leading_user_msg(msg)`

**Step 1:**

- [ ] **Step 1: 创建 `messages/history.py`**

文件路径 `core/llm/messages/history.py`。**复制 `core/llm/trim.py` 全部 73 行**但**删除第 4-7 行的 `safeprint` 定义**与第 5 行 `print = safeprint`，并在文件顶部改为从 `core.llm.transport` 导入 `safeprint`：

```python
import json, re
from core.llm.transport import safeprint
print = safeprint

def compress_history_tags(messages, keep_recent=10, max_len=800, force=False, interval=5):
    """Compress <thinking>/<tool_use>/<tool_result> tags in older messages to save tokens."""
    compress_history_tags._cd = getattr(compress_history_tags, '_cd', 0) + 1
    if force: compress_history_tags._cd = 0
    if compress_history_tags._cd % interval != 0: return messages
    _before = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    _pats = {tag: re.compile(rf'(<{tag}>)([\s\S]*?)(</{tag}>)') for tag in ('thinking', 'think', 'tool_use', 'tool_result')}
    _hist_pat = re.compile(r'<(history|key_info|earlier_context)>[\s\S]*?</\1>')
    def _trunc_str(s): return s[:max_len//2] + '\n...[Truncated]...\n' + s[-max_len//2:] if isinstance(s, str) and len(s) > max_len else s
    def _trunc(text):
        text = _hist_pat.sub(lambda m: f'<{m.group(1)}>[...]</{m.group(1)}>', text)
        for pat in _pats.values(): text = pat.sub(lambda m: m.group(1) + _trunc_str(m.group(2)) + m.group(3), text)
        return text
    for i, msg in enumerate(messages):
        if i >= len(messages) - keep_recent: break
        c = msg['content']
        if isinstance(c, str): msg['content'] = _trunc(c)
        elif isinstance(c, list):
            for b in c:
                if not isinstance(b, dict): continue
                t = b.get('type')
                if t == 'text' and isinstance(b.get('text'), str): b['text'] = _trunc(b['text'])
                elif t == 'tool_result':
                    tc = b.get('content')
                    if isinstance(tc, str): b['content'] = _trunc_str(tc)
                    elif isinstance(tc, list):
                        for sub in tc:
                            if isinstance(sub, dict) and sub.get('type') == 'text': sub['text'] = _trunc_str(sub.get('text'))
                elif t == 'tool_use' and isinstance(b.get('input'), dict):
                    for k, v in b['input'].items(): b['input'][k] = _trunc_str(v)
    print(f"[Cut] {_before} -> {sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)}")
    return messages

def _sanitize_leading_user_msg(msg):
    """把 user 消息里的 tool_result 块改写成纯文本，避免孤立引用。
    history 统一使用 Claude content-block 格式：content 是 list of blocks。"""
    msg = dict(msg)
    content = msg.get('content')
    if not isinstance(content, list): return msg
    texts = []
    for block in content:
        if not isinstance(block, dict): continue
        if block.get('type') == 'tool_result':
            c = block.get('content', '')
            if isinstance(c, list):
                texts.extend(b.get('text', '') for b in c if isinstance(b, dict))
            else: texts.append(str(c))
        elif block.get('type') == 'text': texts.append(block.get('text', ''))
    msg['content'] = [{"type": "text", "text": '\n'.join(t for t in texts if t)}]
    return msg

def trim_messages_history(history, sess):
    cap = sess.context_win * 3
    target = int(cap * getattr(sess, 'trim_keep_rate', 0.6))
    def cost(): return sum(len(json.dumps(m, ensure_ascii=False)) for m in history)
    compress_history_tags(history, interval=getattr(sess, 'cut_msg_interval', 5))
    print(f'[Debug] Current context: {cost()} chars, {len(history)} messages.')
    if cost() <= cap: return
    compress_history_tags(history, keep_recent=4, force=True)
    if cost() <= target: return
    while len(history) > 9 and cost() > target:
        history.pop(0)
        while history and history[0].get('role') != 'user': history.pop(0)
        if history and history[0].get('role') == 'user': history[0] = _sanitize_leading_user_msg(history[0])
    print(f'[Debug] Trimmed context, current: {cost()} chars, {len(history)} messages.')
```

注意顶部 `from core.llm.transport import safeprint` —— 是相对路径 `from ..transport import safeprint` 的绝对等价；这里用绝对路径避免后续 messages 包内相对路径混淆（`history.py` 与 `transport.py` 同级；`from ..transport` 在 `messages/` 内部也可工作，但显式绝对路径更不易出错）。

- [ ] **Step 2: 验证 `messages.history` 可独立 import**

Run: `python -c "from core.llm.messages.history import trim_messages_history, compress_history_tags, _sanitize_leading_user_msg; print(trim_messages_history.__module__)"`
Expected: 输出 `core.llm.messages.history`

- [ ] **Step 3: 验证旧 `core.llm.trim` 仍可用**

Run: `python -c "from core.llm.trim import trim_messages_history; print(trim_messages_history.__module__)"`
Expected: 输出 `core.llm.trim`（旧文件仍在）

- [ ] **Step 4: Commit**

```bash
git add core/llm/messages/history.py
git commit -m "refactor(llm): move trim.py to messages/history.py (safeprint imported from transport)"
```

---

## Task 4: 搬迁 convert.py → messages/schema.py

**Files:**
- Create: `core/llm/messages/schema.py`
- Read for copy: `core/llm/convert.py`

**Interfaces:**
- Produces: `openai_tools_to_claude(tools)`、`_try_parse_tool_args(raw)`、`_stamp_oai_cache_markers(messages, model)`、`_prepare_oai_tools(tools, api_mode)`、`_to_responses_input(messages)`、`_msgs_claude2oai(messages)`、`_fix_messages(messages)`、`_drop_unsigned_thinking(messages)`、`_ensure_thinking_blocks(messages, model)`

**Step 1:**

- [ ] **Step 1: 创建 `messages/schema.py`**

文件路径 `core/llm/messages/schema.py`。**逐字复制** `core/llm/convert.py` 全部 168 行（含 module docstring），不做任何修改：

```python
"""Message / tool-schema conversion between Claude content-block format and OpenAI formats."""
import json, re, uuid

def _try_parse_tool_args(raw):
    """Parse tool args string; split concatenated JSON objects like {..}{..} if needed.
    Returns list of parsed dicts."""
    if not raw: return [{}]
    try: return [json.loads(raw)]
    except Exception: pass
    parts = re.split(r'(?<=\})(?=\{)', raw)
    if len(parts) > 1:
        parsed = []
        for p in parts:
            try: parsed.append(json.loads(p))
            except Exception: return [{"_raw": raw}]
        return parsed
    return [{"_raw": raw}]

def _stamp_oai_cache_markers(messages, model):
    """Add cache_control to last 2 user messages for Anthropic models via OAI-compatible relay."""
    ml = model.lower()
    if not any(k in ml for k in ('claude', 'anthropic')): return
    user_idxs = [i for i, m in enumerate(messages) if m.get('role') == 'user']
    for idx in user_idxs[-2:]:
        c = messages[idx].get('content')
        if isinstance(c, str):
            messages[idx] = {**messages[idx], 'content': [{'type': 'text', 'text': c, 'cache_control': {'type': 'ephemeral'}}]}
        elif isinstance(c, list) and c:
            c = list(c); c[-1] = dict(c[-1], cache_control={'type': 'ephemeral'})
            messages[idx] = {**messages[idx], 'content': c}

def _prepare_oai_tools(tools, api_mode="chat_completions"):
    if api_mode == "responses":
        resp_tools = []
        for t in tools:
            if t.get("type") == "function" and "function" in t:
                rt = {"type": "function"}; rt.update(t["function"])
                resp_tools.append(rt)
            else: resp_tools.append(t)
        return resp_tools
    return tools

def _to_responses_input(messages):
    result, pending = [], []
    for msg in messages:
        role = str(msg.get("role", "user")).lower()
        if role == "tool":
            cid = msg.get("tool_call_id") or (pending.pop(0) if pending else f"call_{uuid.uuid4().hex[:8]}")
            result.append({"type": "function_call_output", "call_id": cid, "output": msg.get("content", "")})
            continue
        if role not in ["user", "assistant", "system", "developer"]: role = "user"
        if role == "system": role = "developer"  # Responses API uses 'developer' instead of 'system'
        content = msg.get("content", "")
        text_type = "output_text" if role == "assistant" else "input_text"
        parts = []
        if isinstance(content, str):
            if content: parts.append({"type": text_type, "text": content})
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict): continue
                ptype = part.get("type")
                if ptype == "text":
                    text = part.get("text", "")
                    if text: parts.append({"type": text_type, "text": text})
                elif ptype == "image_url":
                    url = (part.get("image_url") or {}).get("url", "")
                    if url and role != "assistant": parts.append({"type": "input_image", "image_url": url})
        if len(parts) == 0: parts = [{"type": text_type, "text": str(content) if not isinstance(content, list) else '[empty]'}]
        result.append({"role": role, "content": parts})
        pending = []
        for tc in (msg.get("tool_calls") or []):
            f = tc.get("function", {})
            cid = tc.get("id") or f"call_{uuid.uuid4().hex[:8]}"
            pending.append(cid)
            result.append({"type": "function_call", "call_id": cid, "name": f.get("name", ""), "arguments": f.get("arguments", "")})
    return result

def _msgs_claude2oai(messages):
    result = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        blocks = content if isinstance(content, list) else [{"type": "text", "text": str(content)}]
        if role == "assistant":
            text_parts, tool_calls, reasoning = [], [], ""
            for b in blocks:
                if not isinstance(b, dict): continue
                if b.get("type") == "thinking" and b.get("thinking"): reasoning = b["thinking"]
                elif b.get("type") == "text" and b.get("text"): text_parts.append({"type": "text", "text": b.get("text", "")})
                elif b.get("type") == "tool_use":
                    tool_calls.append({
                        "id": b.get("id") or '', "type": "function",
                        "function": {"name": b.get("name", ""), "arguments": json.dumps(b.get("input", {}), ensure_ascii=False)}
                    })
            m = {"role": "assistant"}
            if reasoning: m["reasoning_content"] = reasoning
            if text_parts: m["content"] = text_parts
            elif not tool_calls: m["content"] = "."
            if tool_calls: m["tool_calls"] = tool_calls
            result.append(m)
        elif role == "user":
            text_parts = []
            for b in blocks:
                if not isinstance(b, dict): continue
                if b.get("type") == "tool_result":
                    if text_parts:
                        result.append({"role": "user", "content": text_parts})
                        text_parts = []
                    tr = b.get("content", "")
                    if isinstance(tr, list):
                        tr = "\n".join(x.get("text", "") for x in tr if isinstance(x, dict) and x.get("type") == "text")
                    result.append({"role": "tool", "tool_call_id": b.get("tool_use_id") or '', "content": tr if isinstance(tr, str) else str(tr)})
                elif b.get("type") == "image":
                    src = b.get("source") or {}
                    if src.get("type") == "base64" and src.get("data"):
                        text_parts.append({"type": "image_url", "image_url": {"url": f"data:{src.get('media_type', 'image/png')};base64,{src.get('data', '')}"}})
                elif b.get("type") == "image_url": text_parts.append(b)
                elif b.get("type") == "text" and b.get("text"): text_parts.append({"type": "text", "text": b.get("text", "")})
            if text_parts: result.append({"role": "user", "content": text_parts})
        else: result.append(msg)
    return result

def _keep_claude_block(b): return not isinstance(b, dict) or b.get("type") != "thinking" or b.get("signature")
def _drop_unsigned_thinking(messages):
    for m in messages:
        c = m.get("content")
        if isinstance(c, list): m["content"] = [b for b in c if _keep_claude_block(b)]
    return messages

def _ensure_thinking_blocks(messages, model):
    """deepseek needs thinking in history!"""
    if 'deepseek' not in model.lower(): return messages
    for m in messages:
        if m.get("role") != "assistant": continue
        c = m.get("content")
        if not isinstance(c, list): continue
        has_thinking = any(isinstance(b, dict) and b.get("type") == "thinking" for b in c)
        if not has_thinking: m["content"] = [{"type": "thinking", "thinking": "...", "signature": "placeholder"}, *c]
    return messages

def _fix_messages(messages):
    """修复 messages 符合 Claude API：交替、tool_use/tool_result 配对"""
    if not messages: return messages
    _wrap = lambda c: c if isinstance(c, list) else [{"type": "text", "text": str(c)}]
    fixed = []
    for m in messages:
        if fixed and m['role'] == fixed[-1]['role']:
            fixed[-1] = {**fixed[-1], 'content': _wrap(fixed[-1]['content']) + [{"type": "text", "text": "\n"}] + _wrap(m['content'])}; continue
        if fixed and fixed[-1]['role'] == 'assistant' and m['role'] == 'user':
            uses = [b.get('id') for b in fixed[-1].get('content', []) if isinstance(b, dict) and b.get('type') == 'tool_use' and b.get('id')]
            has = {b.get('tool_use_id') for b in _wrap(m['content']) if isinstance(b, dict) and b.get('type') == 'tool_result'}
            miss = [uid for uid in uses if uid not in has]
            if miss: m = {**m, 'content': [{"type": "tool_result", "tool_use_id": uid, "content": "(error)"} for uid in miss] + _wrap(m['content'])}
            orphan = has - set(uses)
            if orphan: m = {**m, 'content': [{"type":"text","text":str(b.get('content',''))} if isinstance(b,dict) and b.get('type')=='tool_result' and b.get('tool_use_id') in orphan else b for b in _wrap(m['content'])]}
        fixed.append(m)
    while fixed and fixed[0]['role'] != 'user': fixed.pop(0)
    return fixed

def openai_tools_to_claude(tools):
    """[{type:'function', function:{name,description,parameters}}] → [{name,description,input_schema}]."""
    result = []
    for t in tools:
        if 'input_schema' in t: result.append(t); continue
        fn = t.get('function', t)
        result.append({'name': fn['name'], 'description': fn.get('description', ''),
            'input_schema': fn.get('parameters', {'type': 'object', 'properties': {}})})
    return result
```

- [ ] **Step 2: 验证 `messages.schema` 可独立 import**

Run: `python -c "from core.llm.messages.schema import openai_tools_to_claude, _fix_messages, _msgs_claude2oai, _to_responses_input, _drop_unsigned_thinking, _ensure_thinking_blocks, _stamp_oai_cache_markers, _prepare_oai_tools, _try_parse_tool_args; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 3: 验证旧 `core.llm.convert` 仍可用**

Run: `python -c "from core.llm.convert import openai_tools_to_claude; print(openai_tools_to_claude.__module__)"`
Expected: 输出 `core.llm.convert`

- [ ] **Step 4: Commit**

```bash
git add core/llm/messages/schema.py
git commit -m "refactor(llm): move convert.py to messages/schema.py (verbatim copy)"
```

---

## Task 5: 写 messages/__init__.py（兼容层）

**Files:**
- Modify: `core/llm/messages/__init__.py` (Task 1 创建的空文件)

**Interfaces:**
- Consumes: `messages.schema`, `messages.history`, `messages.response` 子模块
- Produces: 重新导出公开符号 `openai_tools_to_claude` / `tryparse` / `MockFunction` / `MockToolCall` / `MockResponse`；设置 `sys.modules` 兼容映射

**Step 1:**

- [ ] **Step 1: 写 `messages/__init__.py`**

文件路径 `core/llm/messages/__init__.py`，**完整内容**（覆盖 Task 1 创建的空文件）：

```python
"""Tau LLM messages subpackage — horizontal responsibility.

集中收纳「消息/工具 schema 转换」「历史压缩」「响应解析」三个横向职责，
与 core/llm/providers/ 的纵向协议装订形成正交。

子模块（搬迁自原 core/llm/{convert,trim,response}.py）:
- schema   — Claude ↔ OAI 消息/tool schema 双向转换
- history  — 历史压缩/截断（safeprint 来自 transport）
- response — MockResponse / MockToolCall / tryparse / 文本工具回退解析

旧路径兼容:
- core.llm.convert   → messages.schema
- core.llm.trim      → messages.history
- core.llm.response  → messages.response
通过 sys.modules 映射实现，外部 import 路径保持不变。
"""
import sys
from . import schema, history, response
from .schema import openai_tools_to_claude
from .response import MockFunction, MockToolCall, MockResponse, tryparse

# 旧路径兼容：让 from core.llm.convert/trim/response import X 仍可解析。
# 注意：sys.modules 映射只影响"从旧路径 import"这一行为；函数/类的 __module__ 属性
# 仍由其定义文件决定（即 core.llm.messages.{schema,history,response}），
# 这是 Task 8 smoke 脚本断言需要同步更新的原因。
sys.modules['core.llm.convert'] = schema
sys.modules['core.llm.trim'] = history
sys.modules['core.llm.response'] = response
```

- [ ] **Step 2: 验证新公开符号**

Run: `python -c "from core.llm.messages import openai_tools_to_claude, MockResponse, MockToolCall, MockFunction, tryparse; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 3: 验证旧路径 import 仍解析（即使旧文件还在）**

Run: `python -c "from core.llm.convert import openai_tools_to_claude; from core.llm.response import MockResponse; from core.llm.trim import trim_messages_history; print('compat ok')"`
Expected: 输出 `compat ok`

- [ ] **Step 4: 验证旧路径 import 解析到的 __module__ 是新位置**

Run: `python -c "from core.llm.convert import openai_tools_to_claude; print(openai_tools_to_claude.__module__)"`
Expected: 输出 `core.llm.messages.schema`（不是 `core.llm.convert` —— 因为 `sys.modules` 映射优先解析到 `messages.schema`，里面定义的函数 `__module__` 是 `core.llm.messages.schema`）

- [ ] **Step 5: Commit**

```bash
git add core/llm/messages/__init__.py
git commit -m "feat(llm): add messages/__init__.py compat layer (sys.modules alias for old paths)"
```

---

## Task 6: 改 session.py + clients.py import

**Files:**
- Modify: `core/llm/session.py:3`
- Modify: `core/llm/clients.py:2-10`（仅 import 行）

**Step 1:**

- [ ] **Step 1: 修改 `session.py:3`**

修改前 (`core/llm/session.py` 第 3 行):
```python
from .trim import trim_messages_history, safeprint
```

修改后:
```python
from .messages.history import trim_messages_history
from .transport import safeprint
```

- [ ] **Step 2: 修改 `clients.py` 的 4 行 import**

修改前 (`core/llm/clients.py` 第 2-10 行):
```python
import os, re, json, time
from .keys import reload_taukeys
from .trim import safeprint
from .transport import _write_llm_log
from .convert import openai_tools_to_claude
from .response import MockToolCall, MockResponse, tryparse, _parse_text_tool_calls
from .providers.claude import ClaudeSession, NativeClaudeSession
from .providers.openai import LLMSession, NativeOAISession
```

修改后（按行替换）:
```python
import os, re, json, time
from .keys import reload_taukeys
from .transport import safeprint, _write_llm_log
from .messages.schema import openai_tools_to_claude
from .messages.response import MockToolCall, MockResponse, tryparse, _parse_text_tool_calls
from .providers.claude import ClaudeSession, NativeClaudeSession
from .providers.openai import LLMSession, NativeOAISession
```

注意：`from .trim import safeprint` 与 `from .transport import _write_llm_log` 合并为单行 `from .transport import safeprint, _write_llm_log`（两者都已存在于 `transport.py`）。

- [ ] **Step 3: 验证 session.py 与 clients.py 可正常 import**

Run: `python -c "from core.llm.session import BaseSession; from core.llm.clients import ToolClient, NativeToolClient, MixinSession, resolve_session, resolve_client, fast_ask; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 4: Commit**

```bash
git add core/llm/session.py core/llm/clients.py
git commit -m "refactor(llm): update session/clients import paths to messages/"
```

---

## Task 7: 改 providers/{claude,openai}.py import

**Files:**
- Modify: `core/llm/providers/claude.py:3-6`
- Modify: `core/llm/providers/openai.py:3-8`

**Step 1:**

- [ ] **Step 1: 修改 `providers/claude.py` 的 4 行 import**

修改前 (`core/llm/providers/claude.py` 第 3-7 行):
```python
from ..trim import trim_messages_history, safeprint
from ..transport import auto_make_url, _record_usage, _stream_with_retry
from ..convert import _fix_messages, _drop_unsigned_thinking, _ensure_thinking_blocks, openai_tools_to_claude
from ..response import MockToolCall, MockResponse, _parse_text_tool_calls, _ensure_text_block
from ..session import BaseSession
```

修改后:
```python
from ..messages.history import trim_messages_history
from ..transport import safeprint, auto_make_url, _record_usage, _stream_with_retry
from ..messages.schema import _fix_messages, _drop_unsigned_thinking, _ensure_thinking_blocks, openai_tools_to_claude
from ..messages.response import MockToolCall, MockResponse, _parse_text_tool_calls, _ensure_text_block
from ..session import BaseSession
```

- [ ] **Step 2: 修改 `providers/openai.py` 的 import**

修改前 (`core/llm/providers/openai.py` 第 3-8 行):
```python
from ..trim import safeprint
from ..transport import auto_make_url, _record_usage, _stream_with_retry
from ..convert import (_try_parse_tool_args, _stamp_oai_cache_markers, _prepare_oai_tools,
                       _to_responses_input, _msgs_claude2oai, _fix_messages, _ensure_thinking_blocks)
from ..session import BaseSession
from .claude import NativeClaudeSession
```

修改后:
```python
from ..transport import safeprint, auto_make_url, _record_usage, _stream_with_retry
from ..messages.schema import (_try_parse_tool_args, _stamp_oai_cache_markers, _prepare_oai_tools,
                              _to_responses_input, _msgs_claude2oai, _fix_messages, _ensure_thinking_blocks)
from ..session import BaseSession
from .claude import NativeClaudeSession
```

- [ ] **Step 3: 验证 providers 可正常 import**

Run: `python -c "from core.llm.providers.claude import ClaudeSession, NativeClaudeSession; from core.llm.providers.openai import LLMSession, NativeOAISession; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 4: 验证 `core.llm` 公开符号全部仍可访问**

Run: `python -c "from core.llm import BaseSession, ClaudeSession, NativeClaudeSession, LLMSession, NativeOAISession, ToolClient, NativeToolClient, MixinSession, resolve_session, resolve_client, fast_ask, reload_taukeys, auto_make_url, openai_tools_to_claude, MockResponse, MockToolCall, MockFunction, tryparse, _load_taukeys, _record_usage; print(len({s.__name__ for s in [BaseSession, ClaudeSession, NativeClaudeSession, LLMSession, NativeOAISession, ToolClient, NativeToolClient, MixinSession, MockResponse, MockToolCall, MockFunction]}), 'classes ok')"`
Expected: 输出 `11 classes ok`（实际数字不重要，关键是"全部导入且无 ImportError"）

- [ ] **Step 5: Commit**

```bash
git add core/llm/providers/claude.py core/llm/providers/openai.py
git commit -m "refactor(llm): update providers/{claude,openai} import paths to messages/"
```

---

## Task 8: 改 scripts/smoke_llmcore.py 断言

**Files:**
- Modify: `scripts/smoke_llmcore.py:17-43`

**原因：** Task 5 的 `sys.modules` 兼容层让旧路径 import 仍可解析，但函数/类的 `__module__` 属性由其 `def` 语句所在文件决定——搬迁后必然从 `core.llm.{trim,convert,response}` 变成 `core.llm.messages.{history,schema,response}`。smoke 脚本里有 6 条相关断言需要同步改写。

**Step 1:**

- [ ] **Step 1: 修改 smoke 脚本的 import 行**

修改前 (`scripts/smoke_llmcore.py` 第 17-21 行):
```python
from core.llm.trim import compress_history_tags, trim_messages_history, safeprint
from core.llm.transport import _stream_with_retry, _write_llm_log
from core.llm.convert import (_fix_messages, _msgs_claude2oai, _to_responses_input,
                              _drop_unsigned_thinking, _ensure_thinking_blocks,
                              _stamp_oai_cache_markers, _prepare_oai_tools, _try_parse_tool_args)
from core.llm.keys import taukeys
```

修改后:
```python
from core.llm.messages.history import compress_history_tags, trim_messages_history
from core.llm.transport import _stream_with_retry, _write_llm_log, safeprint
from core.llm.messages.schema import (_fix_messages, _msgs_claude2oai, _to_responses_input,
                                       _drop_unsigned_thinking, _ensure_thinking_blocks,
                                       _stamp_oai_cache_markers, _prepare_oai_tools, _try_parse_tool_args)
from core.llm.keys import taukeys
```

- [ ] **Step 2: 修改 6 条 `__module__` 断言**

修改前 (`scripts/smoke_llmcore.py` 第 23-33 行):
```python
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
```

修改后:
```python
assert compress_history_tags.__module__.endswith('llm.messages.history'), compress_history_tags.__module__
assert auto_make_url.__module__.endswith('llm.transport'), auto_make_url.__module__
assert _stream_with_retry.__module__.endswith('llm.transport'), _stream_with_retry.__module__
assert _record_usage.__module__.endswith('llm.transport'), _record_usage.__module__
assert _write_llm_log.__module__.endswith('llm.transport'), _write_llm_log.__module__
assert _fix_messages.__module__.endswith('llm.messages.schema'), _fix_messages.__module__
assert _msgs_claude2oai.__module__.endswith('llm.messages.schema'), _msgs_claude2oai.__module__
assert openai_tools_to_claude.__module__.endswith('llm.messages.schema'), openai_tools_to_claude.__module__
assert MockResponse.__module__.endswith('llm.messages.response'), MockResponse.__module__
assert MockToolCall.__module__.endswith('llm.messages.response'), MockToolCall.__module__
assert tryparse.__module__.endswith('llm.messages.response'), tryparse.__module__
```

- [ ] **Step 3: 验证 smoke 脚本跑通**

Run: `python scripts/smoke_llmcore.py`
Expected: 输出 `[SMOKE-OK] ...` 包含 `history=core.llm.messages.history` `convert=core.llm.messages.schema` `response=core.llm.messages.response` 等新模块路径

- [ ] **Step 4: 验证旧测试仍绿**

Run: `pytest tests/test_taukey_path.py -v`
Expected: 全绿（仅 1 个或几个 test 通过）

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_llmcore.py
git commit -m "test(llm): update smoke_llmcore to assert messages/ subpackage paths"
```

---

## Task 9: 删旧文件 + 更新 __init__.py docstring + 终验

**Files:**
- Delete: `core/llm/convert.py`
- Delete: `core/llm/trim.py`
- Delete: `core/llm/response.py`
- Modify: `core/llm/__init__.py:1-16`（仅 docstring）

**Step 1:**

- [ ] **Step 1: 删除 3 个旧文件**

Run:
```bash
git rm core/llm/convert.py core/llm/trim.py core/llm/response.py
```
Expected: 三个文件被 `git rm` 标记为 deleted

- [ ] **Step 2: 更新 `__init__.py` 顶部 docstring**

修改前 (`core/llm/__init__.py` 第 1-16 行):
```python
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
```

修改后:
```python
"""Tau LLM layer — split out of the original monolithic LLM core module.

Layout (post-2026-06-30 refactor):
- keys.py         — taukey 加载/缓存
- transport.py    — URL 构造、SSE 重试、usage、日志、safeprint
- session.py      — BaseSession
- clients.py      — ToolClient / NativeToolClient / MixinSession / 工厂
- providers/      — 协议装订 + 流解析（claude / openai）
- messages/       — 横向职责：消息/工具 schema 转换、历史压缩、响应解析
                    (schema.py / history.py / response.py)

Public API (stable):
- Sessions:  BaseSession, ClaudeSession, LLMSession, NativeClaudeSession, NativeOAISession, MixinSession
- Clients:   ToolClient, NativeToolClient
- Factory:   resolve_session, resolve_client, fast_ask
- Keys:      reload_taukeys
- Response:  MockFunction, MockToolCall, MockResponse, tryparse
- Conv util: openai_tools_to_claude, auto_make_url

Internal helpers (prefix `_`) live in the submodules (messages/{schema,history,response},
transport, providers) — import them from there, not from this package. The two
exceptions below are kept on the facade only because out-of-package consumers
monkey-patch / read them: `_record_usage` (apps/common/cost_tracker),
`_load_taukeys` (plugins/langfuse_tracing).

Backward compat (via messages/__init__.py sys.modules alias):
- core.llm.convert   → core.llm.messages.schema
- core.llm.trim      → core.llm.messages.history
- core.llm.response  → core.llm.messages.response
"""
```

注意：第 17-27 行的 9 行 `from ... import ...` 主体**一字不动**。

- [ ] **Step 3: 终验 1 — 公开 API 完整**

Run:
```bash
python -c "
from core.llm import (
    BaseSession, ClaudeSession, LLMSession, NativeClaudeSession, NativeOAISession,
    ToolClient, NativeToolClient, MixinSession,
    resolve_session, resolve_client, fast_ask,
    reload_taukeys, auto_make_url, openai_tools_to_claude,
    MockFunction, MockToolCall, MockResponse, tryparse,
    _load_taukeys, _record_usage,
)
print('public api ok')
"
```
Expected: 输出 `public api ok`

- [ ] **Step 4: 终验 2 — 旧 import 路径仍解析（通过 sys.modules 兼容层）**

Run:
```bash
python -c "
from core.llm.convert import openai_tools_to_claude
from core.llm.trim import trim_messages_history
from core.llm.response import MockResponse
print('old path compat ok')
"
```
Expected: 输出 `old path compat ok`

- [ ] **Step 5: 终验 3 — smoke 脚本**

Run: `python scripts/smoke_llmcore.py`
Expected: `[SMOKE-OK] ...` 含新模块路径

- [ ] **Step 6: 终验 4 — 现有测试**

Run: `pytest tests/ -v`
Expected: 全绿

- [ ] **Step 7: 终验 5 — 外部 import 路径无残留**

Run:
```bash
git grep -nE "from core\.llm\.convert|from core\.llm\.trim|from core\.llm\.response" -- '*.py'
```
Expected: 0 命中（旧文件已删除，外部 import 已改为 `from core.llm.messages.*`）

- [ ] **Step 8: 终验 6 — 目录结构正确**

Run:
```bash
find core/llm -type f -name '*.py' | sort
```
Expected 输出:
```
core/llm/__init__.py
core/llm/clients.py
core/llm/keys.py
core/llm/messages/__init__.py
core/llm/messages/history.py
core/llm/messages/response.py
core/llm/messages/schema.py
core/llm/providers/__init__.py
core/llm/providers/claude.py
core/llm/providers/openai.py
core/llm/session.py
core/llm/transport.py
```
`convert.py` / `trim.py` / `response.py` 不再出现。

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "chore(llm): delete old convert/trim/response files; update facade docstring"
```

---

## 自审

**1. Spec 覆盖：**
- §2 目录结构 → Task 1 (建包) + Task 2-4 (搬迁) + Task 9 (删旧) ✅
- §3 职责映射 → Task 2-4 (按函数级搬迁，每个函数在新位置都有归属) ✅
- §4 数据流 → 不需要单独任务（数据流是描述性章节，已被搬迁任务覆盖）✅
- §5 错误处理（沿用现状）→ 全部任务都明确"业务逻辑不改" ✅
- §6 迁移步骤 → Task 1-9 一一对应（步骤 1=Task 1，步骤 2=Task 2，...，步骤 9=Task 9）✅
- §7 验收清单 → Task 9 Step 3-8 + 各任务的 verify step ✅

**2. Placeholder 扫描：** 0 命中。✅

**3. 类型/签名一致性：**
- `_parse_text_tool_calls` 在 Task 2 搬迁到 `messages.response`，Task 6 Step 2 改 import 为 `from .messages.response import _parse_text_tool_calls` —— 一致 ✅
- `safeprint` 在 Task 3 改为 `from core.llm.transport import safeprint`，Task 6/7 改 session/clients/providers 的 import 为 `from .transport import safeprint` —— 一致 ✅
- `openai_tools_to_claude` 在 Task 4 搬到 `messages.schema`，Task 5 在 `messages/__init__.py` re-export，Task 6/7 clients/providers 改为 `from .messages.schema import openai_tools_to_claude` —— 一致 ✅
- `trim_messages_history` 在 Task 3 搬到 `messages.history`，Task 6 session.py 改为 `from .messages.history import trim_messages_history` —— 一致 ✅
- `MockResponse` / `MockToolCall` / `MockFunction` / `tryparse` 在 Task 2 搬到 `messages.response`，Task 5 re-export，Task 6 clients.py 改为 `from .messages.response import ...` —— 一致 ✅

**4. self-review 后微调：** Task 8 标题原为 "chore"，改正为 "test"（smoke 脚本是验证性资产，commit 类型用 test 更准确）。