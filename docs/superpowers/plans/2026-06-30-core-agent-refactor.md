# core/agent 子包重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `core/{agent_loop,handler,taumain}.py`（~744 行）重组进 `core/agent/` 子包（`loop` / `format` / `handler` / `runtime` 四模块 + facade），行为零变化、外部零破坏。

**Architecture:** 镜像 Pi `packages/agent` 分层（`format ← loop ← handler ← runtime`，单向依赖无环）；`core/taumain.py` 与 `core/handler.py` 降为薄 shim 保活外部子模块入口；`core/agent_loop.py` 删除。兼容用 shim 文件（非 `sys.modules`），因为 `taumain` 被当脚本直跑、且 `core/__init__.py` 必须保持空。

**Tech Stack:** Python 3（Tau 既有栈）、pytest、既有 `scripts/smoke_*.py`、`uv`（包管理）。

**Spec:** [docs/superpowers/specs/2026-06-30-core-agent-refactor-design.md](../specs/2026-06-30-core-agent-refactor-design.md)

## Global Constraints

（每个 task 的需求都隐含以下约束，逐字引自 spec §1/§3.4/§5）

- **行为零变化**：搬移的函数体一字不改；仅文件位置、import 行、相对路径层级（`.` → `..`）变更。
- **外部零破坏**：`apps/*`、`plugins/*`、`scripts/*`、`tau_cli/*`、`reflect/*`、`memory/*.py` 的 import 路径零修改——靠 shim 保活 `from core.taumain import Tau` / `from core.handler import TauHandler`。
- **`core/__init__.py` 保持空**：不得 eager-import `core.agent`（否则 `import core.paths` 拖起 agent+llm 重栈）。
- **兼容用 shim 文件**：`core/taumain.py`、`core/handler.py` 留为薄 re-export；**不**用 `sys.modules` 别名。
- **不引入 Pi 新能力**：不加 session 持久化 / compaction / skills / typed events / ExecutionEnv / proxy。
- **不拆 `TauHandler` god-class**：所有 `do_*` 适配器、plan 模式、`turn_end_callback`、`_get_anchor_prompt` 原样留 `handler.py`。
- **不动** `core/llm/`、`core/tools/`、`core/paths.py`、`assets/prompts/` 业务逻辑。
- **包管理用 `uv`**（不用 pip/venv/poetry）。
- **测退出码别用管道**（`cmd | tee f; echo $?` 的 `$?` 是 tee 的——见 [pipe-exit-code-pitfall](memory/pipe-exit-code-pitfall.md)）；用 `; echo $?` 或直接 `pytest`。

---

## File Structure

| 文件 | 操作 | 职责 |
|---|---|---|
| `core/agent/__init__.py` | 新建 | 精简 facade：re-export `agent_runner_loop, BaseHandler, StepOutcome, TauHandler, Tau` |
| `core/agent/format.py` | 新建 | 输出整形叶子（`json_default`/`get_pretty_json`/`_clean_content`/`_compact_tool_args`），loop+handler 共用 |
| `core/agent/loop.py` | 新建 | 无状态循环原语（`StepOutcome`/`BaseHandler`/`try_call_generator`/`exhaust`/`agent_runner_loop`） |
| `core/agent/handler.py` | 新建 | `TauHandler`（完整保留，仅改 import 行） |
| `core/agent/runtime.py` | 新建 | `Tau` 类 + `get_system_prompt` + `load_tool_schema` + 模块 init + `main()` |
| `core/taumain.py` | 改为 shim | `from core.agent.runtime import Tau, get_system_prompt, load_tool_schema, main` + `__main__` 委托 |
| `core/handler.py` | 改为 shim | `from core.agent.handler import TauHandler` |
| `core/agent_loop.py` | **删除** | 无外部用户 |
| `tests/test_core_agent_layout.py` | 新建 | 结构不变量（shim/facade/依赖方向/format 叶子/agent_loop 已删） |

依赖方向（无环）：`format ← loop ← handler ← runtime`。`loop.py` 源码不 import `handler`/`runtime`（grep 可测）。

---

### Task 1: 子包骨架 + `format.py`（输出整形叶子）

**Files:**
- Create: `core/agent/__init__.py`（空骨架）
- Create: `core/agent/format.py`
- Create: `tests/test_core_agent_layout.py`

**Interfaces:**
- Produces: `core.agent.format.{json_default, get_pretty_json, _clean_content, _compact_tool_args}`——纯函数，后续 `loop.py` / `handler.py` import。

- [ ] **Step 0: 基线——确认现有测试/smoke 全绿（重构前安全网）**

Run: `uv run pytest tests/ -q; echo "pytest_exit=$?"`
Expected: 全绿（`pytest_exit=0`）。记录基线。
Run: `uv run python scripts/smoke_packaging.py; echo "smoke_exit=$?"`
Expected: `smoke_exit=0`。
（若 `smoke_packaging.py` 需特殊环境跑不通，记录在案，不阻塞——后续 task 仅以 pytest + smoke_tau 为准。）

- [ ] **Step 1: 写失败测试（`format` 叶子）**

Create `tests/test_core_agent_layout.py`:
```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_core_agent_layout.py -q; echo "exit=$?"`
Expected: FAIL（`ModuleNotFoundError: No module named 'core.agent'`），`exit` 非 0。

- [ ] **Step 3: 建子包骨架 + `format.py`**

建空骨架：
```bash
mkdir -p core/agent && : > core/agent/__init__.py
```

Create `core/agent/format.py`（从 `core/agent_loop.py` 第 31/37/109/123 行起的 4 个函数**逐字搬移**，仅加模块 docstring + 必要 import）：
```python
"""输出整形工具：loop 与 handler 共用的纯函数。
逐字搬自原 core/agent_loop.py（行为零变化），不依赖 agent 包内其它模块。"""
import json, os, re


def json_default(o):
    return list(o) if isinstance(o, set) else str(o)


def get_pretty_json(data):
    if isinstance(data, dict) and "script" in data:
        data = data.copy(); data["script"] = data["script"].replace("; ", ";\n  ")
    return json.dumps(data, indent=2, ensure_ascii=False).replace('\\n', '\n')


def _clean_content(text):
    if not text: return ''
    def _shrink_code(m):
        lines = m.group(0).split('\n')
        lang = lines[0].replace('```','').strip()
        body = [l for l in lines[1:-1] if l.strip()]
        if len(body) <= 6: return m.group(0)
        preview = '\n'.join(body[:5])
        return f'```{lang}\n{preview}\n  ... ({len(body)} lines)\n```'
    text = re.sub(r'```[\s\S]*?```', _shrink_code, text)
    for p, repl in ((r'<file_content>[\s\S]*?</file_content>', ''), (r'<tool_(?:use|call)>[\s\S]*?</tool_(?:use|call)>', ''), (r'(\r?\n){3,}', '\n\n')):
        text = re.sub(p, repl, text)
    return text.strip()


def _compact_tool_args(name, args):
    a = {k: v for k, v in args.items() if k != '_index'}
    for k in ('path',):
        if k in a: a[k] = os.path.basename(a[k])
    if name == 'update_working_checkpoint': s = a.get('key_info', ''); return (s[:60]+'...') if len(s)>60 else s
    if name == 'ask_user':
        q = str(a.get('question', ''))
        cs = a.get('candidates') or []
        if cs: q += '\ncandidates:\n' + '\n'.join(f'- {c}' for c in cs)
        return q
    s = json.dumps(a, ensure_ascii=False); return (s[:120]+'...') if len(s)>120 else s
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_core_agent_layout.py::test_format_leaf_importable -q; echo "exit=$?"`
Expected: PASS，`exit=0`。

- [ ] **Step 5: 提交**

```bash
git add core/agent/__init__.py core/agent/format.py tests/test_core_agent_layout.py
git commit -m "refactor(agent): 建 core/agent 子包骨架 + 抽 format 叶子（json_default/get_pretty_json/_clean_content/_compact_tool_args）"
```

---

### Task 2: `loop.py`（无状态循环原语）

**Files:**
- Create: `core/agent/loop.py`

**Interfaces:**
- Consumes: `core.agent.format.{json_default, get_pretty_json, _clean_content, _compact_tool_args}`（Task 1）
- Produces: `core.agent.loop.{StepOutcome, BaseHandler, try_call_generator, exhaust, agent_runner_loop}`——`handler.py` / `runtime.py` 后续 import。

- [ ] **Step 1: 追加失败测试**

Append to `tests/test_core_agent_layout.py`:
```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_core_agent_layout.py::test_loop_module_importable -q; echo "exit=$?"`
Expected: FAIL（`ModuleNotFoundError: No module named 'core.agent.loop'`）。

- [ ] **Step 3: 建 `loop.py`（从 `agent_loop.py` 逐字搬 + 加 format import）**

从 `core/agent_loop.py` **逐字搬移**以下符号（行为不变，不改函数体）：
- 文件头的 import + `_hook` 兜底（第 1–5 行）
- `@dataclass` + `class StepOutcome`（第 6–10 行）
- `def try_call_generator`（第 11–14 行）
- `class BaseHandler`（第 16–29 行）
- `def exhaust`（第 32–35 行）
- `def agent_runner_loop`（第 42–107 行）

**搬移后在文件顶部 import 区追加一行**（`agent_runner_loop` 内部用这四个函数）：
```python
from .format import json_default, get_pretty_json, _clean_content, _compact_tool_args
```

**不要**搬 `json_default`/`get_pretty_json`/`_clean_content`/`_compact_tool_args`（已在 `format.py`）。

完整顶栏应为：
```python
import json, re, os
from dataclasses import dataclass
from typing import Any, Optional
try: from plugins.hooks import trigger as _hook
except ImportError: _hook = lambda *a, **k: None
from .format import json_default, get_pretty_json, _clean_content, _compact_tool_args
```
（之后接逐字搬来的 `@dataclass class StepOutcome` … 到 `agent_runner_loop` 函数末尾。）

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_core_agent_layout.py::test_loop_module_importable tests/test_core_agent_layout.py::test_loop_no_upper_deps -q; echo "exit=$?"`
Expected: PASS，`exit=0`。

- [ ] **Step 5: 提交**

```bash
git add core/agent/loop.py tests/test_core_agent_layout.py
git commit -m "refactor(agent): 搬 loop 原语到 core/agent/loop.py（agent_runner_loop/BaseHandler/StepOutcome，import format 叶子）"
```

---

### Task 3: `handler.py` → `core/agent/handler.py`

**Files:**
- Create: `core/agent/handler.py`
- （保留 `core/handler.py` 不动——Task 6 才替换为 shim）

**Interfaces:**
- Consumes: `core.agent.loop.{BaseHandler, StepOutcome}`、`core.agent.format.json_default`（Task 1/2）、`core.tools.*`、`core.paths.MEMORY`
- Produces: `core.agent.handler.TauHandler`——`runtime.py` 后续 import；`core/handler.py` shim 后续 re-export。

- [ ] **Step 1: 追加失败测试**

Append to `tests/test_core_agent_layout.py`:
```python
def test_handler_module_importable():
    from core.agent.handler import TauHandler
    assert TauHandler.__module__ == "core.agent.handler"
    # BaseHandler 子类契约（确保继承自 loop.BaseHandler，非旧 agent_loop）
    from core.agent.loop import BaseHandler
    assert issubclass(TauHandler, BaseHandler)
    for do in ("do_code_run", "do_file_read", "do_file_write", "do_file_patch",
               "do_web_scan", "do_web_execute_js", "do_ask_user", "do_no_tool"):
        assert hasattr(TauHandler, do), f"TauHandler 缺 {do}"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_core_agent_layout.py::test_handler_module_importable -q; echo "exit=$?"`
Expected: FAIL（`ModuleNotFoundError: No module named 'core.agent.handler'`）。

- [ ] **Step 3: 建 `core/agent/handler.py`（逐字搬 `TauHandler` + 改 import 行）**

把 `core/handler.py` 第 13–320 行 `class TauHandler(BaseHandler):` 整体（含全部方法）**逐字复制**到 `core/agent/handler.py`，类体一字不改。

文件顶栏（替换原 `core/handler.py` 第 1–11 行的 import 块）：
```python
import os, re, json, sys
if sys.stdout is None: sys.stdout = open(os.devnull, "w")
if sys.stderr is None: sys.stderr = open(os.devnull, "w")

from .loop import BaseHandler, StepOutcome
from .format import json_default
from ..tools.utils import (smart_format, consume_file, log_memory_access,
                           expand_file_refs, get_global_memory)
from ..tools.code_run import code_run, ask_user
from ..tools.file_io import file_read, file_patch, file_write
from ..tools.web import web_scan, web_execute_js
from ..paths import MEMORY
```

**改动点核对**（相对原 `core/handler.py`）：
- `from .agent_loop import BaseHandler, StepOutcome, json_default` → 拆为 `from .loop import BaseHandler, StepOutcome` + `from .format import json_default`
- `from .tools.utils import ...` → `from ..tools.utils import ...`（升一级）
- `from .tools.code_run import ...` → `from ..tools.code_run import ...`
- `from .tools.file_io import ...` → `from ..tools.file_io import ...`
- `from .tools.web import ...` → `from ..tools.web import ...`
- `from .paths import MEMORY` → `from ..paths import MEMORY`

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_core_agent_layout.py::test_handler_module_importable -q; echo "exit=$?"`
Expected: PASS，`exit=0`。

- [ ] **Step 5: 提交**

```bash
git add core/agent/handler.py tests/test_core_agent_layout.py
git commit -m "refactor(agent): 搬 TauHandler 到 core/agent/handler.py（相对 import .tools/.paths 升 ..）"
```

---

### Task 4: `taumain.py` → `core/agent/runtime.py`

**Files:**
- Create: `core/agent/runtime.py`
- （保留 `core/taumain.py` 不动——Task 6 才替换为 shim）

**Interfaces:**
- Consumes: `core.agent.loop.agent_runner_loop`、`core.agent.handler.TauHandler`（Task 2/3）、`core.tools.utils`、`core.paths`、`core.llm.*`
- Produces: `core.agent.runtime.{Tau, get_system_prompt, load_tool_schema, main}`——facade 与 shim 后续 re-export。

- [ ] **Step 1: 追加失败测试**

Append to `tests/test_core_agent_layout.py`:
```python
def test_runtime_module_importable():
    from core.agent.runtime import Tau, get_system_prompt, load_tool_schema, main
    assert Tau.__module__ == "core.agent.runtime"
    assert callable(get_system_prompt) and callable(load_tool_schema) and callable(main)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_core_agent_layout.py::test_runtime_module_importable -q; echo "exit=$?"`
Expected: FAIL（`ModuleNotFoundError: No module named 'core.agent.runtime'`）。

- [ ] **Step 3: 建 `core/agent/runtime.py`（逐字搬 + 改 import + 包 `main()`）**

把 `core/taumain.py` 第 1–179 行（imports + 模块级 init + `load_tool_schema` + 全局变量 + `get_system_prompt` + `class Tau`）**逐字复制**到 `core/agent/runtime.py`，仅改 import 行：

**import 块改动**（相对原 `core/taumain.py` 第 1–19 行）：
- `from .llm.keys import reload_taukeys` → `from ..llm.keys import reload_taukeys`
- `from .llm.clients import ...` → `from ..llm.clients import ...`
- `from .llm.providers.openai import ...` → `from ..llm.providers.openai import ...`
- `from .llm.providers.claude import ...` → `from ..llm.providers.claude import ...`
- `from .agent_loop import agent_runner_loop` → `from .loop import agent_runner_loop`
- `from .handler import TauHandler` → **不变**（同子包 `core/agent/handler.py`）
- `from .tools.utils import ...` → `from ..tools.utils import ...`
- `from .paths import TAU_HOME, MEMORY, ASSETS, TEMP` → `from ..paths import TAU_HOME, MEMORY, ASSETS, TEMP`
- `from plugins.hooks import discover_and_load` → **不变**（绝对 import）

**把第 181 行起的 `if __name__ == '__main__':` 块（第 181–291 行）改为 `def main():` 函数**：
- 把 `if __name__ == '__main__':` 这行替换为 `def main():`
- 其下函数体（含 `import argparse` / `from datetime import datetime` / `parser = ...` / 三分支 `if args.task`/`elif args.reflect`/`else`）**保持原 4 空格缩进不动**——原 `__main__` 块的守卫在 col 0、体在 col 4（恰为函数体层级），把守卫换成 `def main():` 后体就是函数体，**不要左移**（左移 4 会到 col 0 → `IndentationError`）。即：只换头，不换体。
- 文件末尾追加：
  ```python


  if __name__ == '__main__':
      main()
  ```

  说明：块内对模块全局（`script_dir` / `TEMP` / `TAU_HOME` / `Tau` / `load_tool_schema` 等）的引用在 `main()` 内仍按模块作用域解析，行为等价；块内赋值（`agent`/`args`/`parser`/`_reflect_args` 等）成为 `main()` 局部变量，与原 `__main__` 块语义一致。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_core_agent_layout.py::test_runtime_module_importable -q; echo "exit=$?"`
Expected: PASS，`exit=0`。

- [ ] **Step 5: 回归——`agent_loop.py`/`handler.py`/`taumain.py` 旧文件仍可用（双轨期）**

Run: `uv run python -c "from core.taumain import Tau; from core.handler import TauHandler; from core.agent_loop import agent_runner_loop; print('legacy paths OK')"; echo "exit=$?"`
Expected: 打印 `legacy paths OK`，`exit=0`（旧路径尚未替换，仍指向旧实现——双轨期安全）。

- [ ] **Step 6: 提交**

```bash
git add core/agent/runtime.py tests/test_core_agent_layout.py
git commit -m "refactor(agent): 搬 Tau 到 core/agent/runtime.py（相对 import 升 ..；__main__ 块包成 main()）"
```

---

### Task 5: 包 facade `core/agent/__init__.py`

**Files:**
- Modify: `core/agent/__init__.py`（原空骨架）

**Interfaces:**
- Produces: `core.agent` 包公开 API（`Tau` / `TauHandler` / `agent_runner_loop` / `BaseHandler` / `StepOutcome`）。

- [ ] **Step 1: 追加失败测试**

Append to `tests/test_core_agent_layout.py`:
```python
def test_facade_exports():
    import core.agent
    for sym in ("Tau", "TauHandler", "agent_runner_loop", "BaseHandler", "StepOutcome"):
        assert hasattr(core.agent, sym), f"core.agent facade 缺 {sym}"
    # facade 符号指向子模块（非空 re-export）
    assert core.agent.Tau.__module__ == "core.agent.runtime"
    assert core.agent.TauHandler.__module__ == "core.agent.handler"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_core_agent_layout.py::test_facade_exports -q; echo "exit=$?"`
Expected: FAIL（`core.agent` 无 `Tau` 属性）。

- [ ] **Step 3: 写 facade**

Overwrite `core/agent/__init__.py`:
```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_core_agent_layout.py::test_facade_exports -q; echo "exit=$?"`
Expected: PASS，`exit=0`。

- [ ] **Step 5: 提交**

```bash
git add core/agent/__init__.py tests/test_core_agent_layout.py
git commit -m "feat(agent): 写 core/agent 包 facade（精简 re-export Tau/TauHandler/loop 三件）"
```

---

### Task 6: 替换 shim（`core/taumain.py` + `core/handler.py`）—— 活切换

**Files:**
- Modify: `core/taumain.py` → 入口 shim
- Modify: `core/handler.py` → shim

**Interfaces:**
- Produces: `from core.taumain import Tau` / `from core.handler import TauHandler` 经 shim 指向 `core.agent.runtime` / `core.agent.handler`（`__module__` 断言验证）。

- [ ] **Step 1: 追加失败测试**

Append to `tests/test_core_agent_layout.py`:
```python
def test_shim_taumain_redirects():
    from core.taumain import Tau
    assert Tau.__module__ == "core.agent.runtime"  # shim 必须指向新实现


def test_shim_handler_redirects():
    from core.handler import TauHandler
    assert TauHandler.__module__ == "core.agent.handler"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_core_agent_layout.py::test_shim_taumain_redirects tests/test_core_agent_layout.py::test_shim_handler_redirects -q; echo "exit=$?"`
Expected: FAIL（旧文件 `Tau.__module__ == 'core.taumain'` / `'core.handler'`）。

- [ ] **Step 3: 替换 `core/handler.py` 为 shim**

Overwrite `core/handler.py`（清空原 320 行）:
```python
"""兼容 shim —— TauHandler 实现已迁至 core.agent.handler。
外部 `from core.handler import TauHandler` 继续可用（零修改）。"""
from core.agent.handler import TauHandler  # noqa: F401
```

- [ ] **Step 4: 替换 `core/taumain.py` 为入口 shim**

Overwrite `core/taumain.py`（清空原 291 行）:
```python
"""入口 shim —— Tau 运行时已迁至 core.agent.runtime。
保留在 core/ 顶层是因为它被当脚本/模块直跑：
  python -m core.taumain --reflect ...   (start_scheduler.sh / start_autonomous.sh)
  python core/taumain.py --task ...      (tau_cli / SOPs)
脚本直跑读文件而非 import 系统，故不能纯靠 sys.modules 别名。"""
from core.agent.runtime import Tau, get_system_prompt, load_tool_schema, main  # noqa: F401

if __name__ == '__main__':
    main()
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_core_agent_layout.py::test_shim_taumain_redirects tests/test_core_agent_layout.py::test_shim_handler_redirects -q; echo "exit=$?"`
Expected: PASS，`exit=0`。

- [ ] **Step 6: 提交**

```bash
git add core/taumain.py core/handler.py tests/test_core_agent_layout.py
git commit -m "refactor(agent): core/taumain.py + core/handler.py 降为 shim（活切换到 core.agent.*，外部零修改）"
```

---

### Task 7: 删除 `core/agent_loop.py`

**Files:**
- Delete: `core/agent_loop.py`

**Interfaces:**
- 前置：所有内部引用已迁子包（`core/agent/handler.py` 与 `core/agent/runtime.py` 用 `from .loop`；旧 `core/handler.py`/`core/taumain.py` 已是 shim）。

- [ ] **Step 1: 确认无外部引用**

Run: `git grep -nE "from core\.agent_loop|from \.agent_loop|from \.\.agent_loop|core/agent_loop\.py"; echo "exit=$?"`
Expected: 仅可能命中 `docs/`/`README`（叙述性），**不得**有任何 `from .agent_loop import` / `from core.agent_loop import` 代码引用。若有代码残留，先修（迁到 `core.agent.loop`）再继续。

（`git grep` 无匹配时 `exit=1`，正常——以"输出无代码引用"为准，别用 `$?` 判断。）

- [ ] **Step 2: 追加失败测试**

Append to `tests/test_core_agent_layout.py`:
```python
def test_agent_loop_module_removed():
    """core.agent_loop 模块应已删除（无真实文件）。"""
    import importlib.util
    spec = importlib.util.find_spec("core.agent_loop")
    assert spec is None, f"core.agent_loop 仍存在: {spec}"
```

- [ ] **Step 3: 跑测试确认失败（模块仍在）**

Run: `uv run pytest tests/test_core_agent_layout.py::test_agent_loop_module_removed -q; echo "exit=$?"`
Expected: FAIL（`core.agent_loop` 仍可 find_spec）。

- [ ] **Step 4: 删除**

```bash
git rm core/agent_loop.py
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_core_agent_layout.py::test_agent_loop_module_removed -q; echo "exit=$?"`
Expected: PASS，`exit=0`。

- [ ] **Step 6: 提交**

```bash
git commit -m "chore(agent): 删除 core/agent_loop.py（无外部用户，实现已迁 core/agent/loop.py）"
```

---

### Task 8: 全量验证 + 脚本启动平价

**Files:**
- 可能 Modify: `core/taumain.py`（仅当直接脚本启动需 `sys.path` 修正时）
- 无新建测试（用既有 smoke + 结构测试套件）

**Interfaces:** 无（验证 gate）。

- [ ] **Step 1: 结构测试套件全绿**

Run: `uv run pytest tests/test_core_agent_layout.py -q; echo "exit=$?"`
Expected: 全部结构测试 PASS（format/loop×2/handler/runtime/facade/shim×2/agent_loop_removed 共 9 项），`exit=0`。

- [ ] **Step 2: 既有测试全绿（回归）**

Run: `uv run pytest tests/ -q; echo "exit=$?"`
Expected: 全绿，`exit=0`（含 `tests/test_core_paths.py` / `tests/test_taukey_path.py`）。

- [ ] **Step 3: smoke 套件**

Run: `uv run python scripts/smoke_tau.py; echo "smoke_tau=$?"`
Expected: `smoke_tau=0`（`from core.handler import TauHandler` + tools 全可用）。

Run: `uv run python scripts/smoke_packaging.py; echo "smoke_pack=$?"`
Expected: `smoke_pack=0`（顶层 `core.taumain` 可 import）。

Run: `uv run python scripts/smoke_llmcore.py; echo "smoke_llm=$?"`
Expected: `smoke_llm=0`（确认未波及 llm 层）。

- [ ] **Step 4: 模块启动（主路径）**

Run: `uv run python -m core.taumain --help 2>&1 | head -5; echo "exit=$?"`
Expected: 打印 argparse help（`--task` / `--reflect` / `--input` / `--llm_no` 等），`exit=0`。这覆盖 [start_scheduler.sh](start_scheduler.sh) / [start_autonomous.sh](start_autonomous.sh) 的 `-m core.taumain` 路径。

- [ ] **Step 5: 直接脚本启动（平价检查）**

Run: `cd core && uv run python taumain.py --help 2>&1 | head -5; echo "exit=$?"; cd ..`
Expected: 同样打印 argparse help，`exit=0`。

**若失败**（`ModuleNotFoundError: No module named 'core'` 等）：给 `core/taumain.py` shim 加 `sys.path` 修正保平价——在 docstring 后、import 前插入：
```python
import os, sys
if __package__ in (None, ''):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```
重跑 Step 5 直到 `exit=0`。这覆盖 [tau_cli/commands/_launchers.py](tau_cli/commands/_launchers.py) 的 `python {PROJECT_DIR}/core/taumain.py` 路径。

- [ ] **Step 6: 行为平价（手动 sanity）**

在有 `.tau/taukey.py` 配置的环境，跑一个确定性小任务前后对比：
```bash
# 重构后
echo '用 code_run 算 1+1 并报告结果' | uv run python -m core.taumain 2>&1 | tail -20
```
Expected: 工具执行链路正常（`code_run` 调用 → 返回 `2` → 正常 turn 结束），与重构前行为一致（若 Task 1 Step 0 已存基线则对照；否则确认工具能正常触发与返回）。

- [ ] **Step 7: 提交（仅当 Step 5 改了 shim）**

若 Step 5 加了 `sys.path` 修正：
```bash
git add core/taumain.py
git commit -m "fix(agent): taumain shim 加 sys.path 修正，保 python core/taumain.py 直接启动平价"
```
否则跳过提交（纯验证 gate）。

---

### Task 9: 文档同步

**Files:**
- Modify: `README.md`
- Modify: `tau_cli/__init__.py`（docstring）

**Interfaces:** 无。

- [ ] **Step 1: 写失败测试（文档结构描述）**

Append to `tests/test_core_agent_layout.py`:
```python
def test_readme_structure_updated():
    src = open("README.md", encoding="utf-8").read()
    # 新结构在 README 里出现
    assert "core/agent/" in src or "agent/{loop" in src
    # 旧三文件平铺描述已更新（不再把 agent_loop 当独立顶层模块列）
    assert "agent_loop · handler · taumain" not in src
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_core_agent_layout.py::test_readme_structure_updated -q; echo "exit=$?"`
Expected: FAIL（README 仍是旧描述）。

- [ ] **Step 3: 更新 README 结构行**

[README.md:136](README.md#L136) 附近 `core/` 行数注释，把：
```
├── core/         # 智能体内核 ~1.8K 行:agent_loop · handler · taumain · llm/ · tools/
```
改为：
```
├── core/         # 智能体内核:agent/{loop,format,handler,runtime} · taumain(handler shim) · llm/ · tools/
```

[README.md:94](README.md#L94) 附近的 `core/taumain.py` 引用保留（经 shim 仍有效），可加注：
```
tau cli        # CLI 对话,最轻量(core/taumain.py → shim of core/agent/runtime)
```

- [ ] **Step 4: 更新 `tau_cli/__init__.py` docstring**

找到 `from core.handler import TauHandler` 示例注释（`tau_cli/__init__.py:4` 附近），补注真实路径：
```
核心类请直接从真实模块导入，例如 `from core.handler import TauHandler`
（shim；真实实现 core.agent.handler）。
```

- [ ] **Step 5: 跑测试确认通过 + 全量回归**

Run: `uv run pytest tests/test_core_agent_layout.py -q; echo "exit=$?"`
Expected: 全绿。

Run: `uv run pytest tests/ -q; echo "exit=$?"`
Expected: 全绿。

- [ ] **Step 6: 提交**

```bash
git add README.md tau_cli/__init__.py tests/test_core_agent_layout.py
git commit -m "docs(agent): 同步 core/ 结构说明（agent/ 子包 + shim 注记）"
```

---

## 完成判据（spec §7 验收对应）

Task 1–9 全绿后，逐条核对 [spec §7 验收清单](../specs/2026-06-30-core-agent-refactor-design.md)：
- [ ] shim 保活（`from core.taumain import Tau` / `from core.handler import TauHandler`）
- [ ] facade 导出（`from core.agent import Tau, TauHandler, agent_runner_loop, BaseHandler, StepOutcome`）
- [ ] `core/agent/loop.py` 源码不含 `from .handler` / `from .runtime`（依赖方向单向）
- [ ] `core/agent_loop.py` 物理删除，`git grep` 无代码引用
- [ ] `python -m core.taumain --help` + `python core/taumain.py --help` 均 `exit=0`
- [ ] `scripts/smoke_tau.py` / `scripts/smoke_packaging.py` / `scripts/smoke_llmcore.py` 全绿
- [ ] `pytest tests/` 全绿
- [ ] 外部调用方 import 路径零修改（`git diff main -- apps/ plugins/ scripts/ tau_cli/ reflect/ memory/*.py` 应只有文档/注记改动，无 import 行变更）
