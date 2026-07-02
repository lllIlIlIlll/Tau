# core/agent 子包重构 — 设计文档

> 日期: 2026-06-30
> 范围: `core/{agent_loop,handler,taumain}.py` 重组进 `core/agent/` 子包，外部零破坏、行为零变化
> 参考: https://github.com/earendil-works/pi/tree/main/packages/agent（仅职责分层思路）
> 类型: E-组织型（纯结构重排，不引入 Pi 新能力）

---

## 1. 背景与目标

Tau 的 agent 层（`core/{agent_loop,handler,taumain}.py`，共 ~744 行）是对标 Pi `packages/agent` 的下一层。上一轮 [`core/llm/`](specs/2026-06-30-core-llm-refactor-design.md) 重构已对齐 Pi `packages/ai`（LLM/协议层）；本轮把 agent 层按 Pi `packages/agent` 的**分层与子包边界**重新归位。

Pi `packages/agent` 的分层骨架（单向依赖，无环）：

```
types        ← 契约（AgentMessage/Tool/Context/State/events/loop-config）
loop         ← 无状态循环原语（runAgentLoop：turn/tool-call/dispatch/parallel/钩子）
session      ← 会话树+持久化（storage/repo 分离）        ← Tau 无此层
domain utils ← compaction / skills / prompt-templates / messages / truncate
harness      ← 顶层有状态编排器（组合 loop+session+compaction+resources+hooks）
```

本轮**只借"分层 + 子包"组织思路，不借 Pi 的功能**（session 持久化 / compaction / skills / typed events / ExecutionEnv / proxy 一律不引入）。

### 现状问题

- `agent_loop.py`（133 行）把**循环原语**（`agent_runner_loop` / `BaseHandler.dispatch` / `StepOutcome`）与**输出整形工具**（`json_default` / `get_pretty_json` / `_clean_content` / `_compact_tool_args`）混在一处。
- `handler.py`（320 行）`TauHandler` 是 god-class（工具适配器 `do_*` + plan 模式 + `turn_end_callback` 策略 + `_get_anchor_prompt` 提示词 + 记忆管理），但本轮**不拆 god-class**（见非目标）。
- `taumain.py`（291 行）`Tau` 类把"编排器 + LLM 会话管理 + 任务队列/线程 + 三种入口 + 流式 + sys_prompt 装配"全混——本轮作为 Pi `harness` 的对应物整体搬入 `runtime.py`，不内部分拆。
- 三个文件平铺在 `core/` 顶层，与已子包化的 `core/llm/` 不对称，且为未来 session/compaction/skills 留不下落点。

### 目标

- 把 `agent_loop / handler / taumain` 三文件重组进 `core/agent/` 子包，拆为 **`loop` / `format` / `handler` / `runtime`** 四模块 + `__init__`。
- 抽出 `format.py` 作为 loop 与 handler 共用的输出整形叶子（唯一的职责切分点）。
- **行为零变化**：每个搬移的函数体一字不改，仅文件位置与 import 行变更。
- **外部零破坏**：`from core.taumain import Tau` / `from core.handler import TauHandler` 继续可用（shim 保活）；`python -m core.taumain` / `python core/taumain.py` 启动路径不变。

### 非目标

- **不引入** session 持久化 / compaction 算法 / skills 系统 / typed event 流 / ExecutionEnv / proxy（E-组织型，零新功能）。
- **不拆 `TauHandler` god-class**：`do_*` 工具适配器 vs 策略/plan 模式/记忆 的深度切分是后续独立 spec（候选 C 方案）。
- **不建 `prompts.py`**：Tau 无 prompt-template/skills 系统；`_get_anchor_prompt`/`_fold_earlier` 是 `TauHandler` 内部策略（强耦合其 `self.history_info`/`self.working`/`self.current_turn`/`self.parent`），抽出会改签名——属重设计，留原处；`get_system_prompt` 是 runtime 装配职责，留 `runtime.py`。
- 不动 `core/llm/`、`core/tools/`、`core/paths.py` 业务逻辑（仅可能的 import 路径同步）。
- 不改 `assets/prompts/` 运行时提示词、不改外部调用方（`apps/*`、`plugins/*`、`scripts/*`、`tau_cli/*`）。
- 不引入 typed events / Result 类型 / 钩子改造；现有 `_hook('tool_before', ...)` 字符串钩子协议原样保留。

---

## 2. 目录结构

```
core/
├── __init__.py        # 空（不动；保持极简，import core.paths 不得拖起 agent 栈）
├── paths.py           # 不动
├── llm/               # 不动（已 Pi/ai 对齐）
├── tools/             # 不动（工具实现，已分文件）
├── taumain.py         # ← 入口 shim：re-export from agent.runtime + __main__ 委托
├── handler.py         # ← shim：re-export TauHandler from agent.handler
├── agent_loop.py      # ← 删除（无外部用户）
└── agent/             # ← 新子包
    ├── __init__.py     # 公开 API re-export
    ├── loop.py         # 无状态循环原语
    ├── format.py       # 输出整形叶子（loop+handler 共用）
    ├── handler.py      # TauHandler（完整保留）
    └── runtime.py      # Tau 类 + get_system_prompt + load_tool_schema + 模块init + main()
```

### 依赖方向（无环，镜像 Pi）

```
format  ←  loop  ←  handler  ←  runtime
(leaf)   (原语)   (适配器+策略)  (编排器)
```

- `format.py`：纯 stdlib，无内部依赖（叶子）。
- `loop.py`：仅依赖 `format`（输出整形）+ `plugins.hooks`（可选 `_hook`）。**不** import `handler` / `runtime`。
- `handler.py`：依赖 `loop`（`BaseHandler` / `StepOutcome`）+ `format`（`json_default`）+ `core.tools.*` / `core.paths`。
- `runtime.py`：依赖 `loop`（`agent_runner_loop`）+ `handler`（`TauHandler`）+ `core.tools.utils` / `core.paths` / `core.llm.*`。

`loop.py` 源码不 import `handler` / `runtime`（依赖方向单向，符合 Pi「loop 无状态、不依赖上层」原则——指源码级依赖方向，非 import 时副作用）。包 facade 为 eager re-export（与 [core/llm 重构](specs/2026-06-30-core-llm-refactor-design.md) 一致）：`import core.agent.<任意子模块>` 会先执行 `core/agent/__init__.py`，其中 `from .runtime import Tau` 触发 runtime 模块级 init（`load_tool_schema()` 等）——这与现状 `import core.taumain` 的副作用**完全等价**，无新增。

---

## 3. 职责映射（逐函数级）

### 3.1 `agent_loop.py`（拆为 `loop.py` + `format.py`）

| 当前符号 | 目标位置 | 角色 | 处理 |
|---|---|---|---|
| `StepOutcome`（dataclass） | `agent/loop.py` | 步骤结果契约 | 原样搬 |
| `BaseHandler`（`turn_end_callback` / `dispatch`） | `agent/loop.py` | 工具分发机制（被 `TauHandler` 继承） | 原样搬 |
| `try_call_generator` / `exhaust` | `agent/loop.py` | 生成器工具 | 原样搬 |
| `agent_runner_loop` | `agent/loop.py` | 无状态 turn 循环 | 原样搬；新增 `from .format import json_default, get_pretty_json, _clean_content, _compact_tool_args` |
| `json_default` | `agent/format.py` | set→list / 兜底 str | 原样搬 |
| `get_pretty_json` | `agent/format.py` | 工具 args 美化打印 | 原样搬 |
| `_clean_content` | `agent/format.py` | 流输出 code block 收缩/标签过滤 | 原样搬 |
| `_compact_tool_args` | `agent/format.py` | 非 verbose 模式工具 args 压缩 | 原样搬 |

`loop.py` 内 `agent_runner_loop` 仍调用上述四个 format 函数——改为 `from .format import ...`，函数体不变。

### 3.2 `handler.py` → `agent/handler.py`（整体搬，仅改 import 行）

`TauHandler` **完整保留**（所有 `do_*` 适配器、plan 模式方法、`turn_end_callback`、`_get_anchor_prompt`、`_fold_earlier`、`_extract_*` 等一字不动）。

| 项 | 处理 |
|---|---|
| 类体 / 所有方法 | 原样搬 |
| `from .agent_loop import BaseHandler, StepOutcome, json_default` | → `from .loop import BaseHandler, StepOutcome` + `from .format import json_default` |
| 其余 import（`from .tools.utils import ...`、`from .tools.code_run import ...`、`from .tools.file_io import ...`、`from .tools.web import ...`、`from .paths import MEMORY`） | 相对路径前缀由 `core/` 变 `core/agent/`，故 `from .tools...` / `from .paths` → `from ..tools...` / `from ..paths`（多升一级） |

> ⚠️ 注意相对 import 升级：`handler.py` 从 `core/handler.py` 移到 `core/agent/handler.py` 后，对 `core.tools.*` / `core.paths` 的相对引用要从 `.` 改 `..`。`runtime.py` 同理。**这是唯一需要逐行核对的改动点**，git grep 可全量覆盖。

### 3.3 `taumain.py` → `agent/runtime.py`（整体搬 + `__main__` 提取）

| 项 | 处理 |
|---|---|
| 模块级 init（`load_tool_schema()` / `lang_suffix` / `mem_dir`/`mem_txt`/`mem_insight` 创建 / `cdp_cfg` 写入） | 原样搬（仍模块级，import 时执行——与现状一致） |
| `get_system_prompt()` | 原样搬（runtime 装配职责） |
| `load_tool_schema()`（函数） | 原样搬 |
| `Tau` 类（`__init__` / `load_llm_sessions` / `next_llm` / `list_llms` / `get_llm_name` / `abort` / `put_task` / `_handle_slash_cmd` / `run`） | 原样搬 |
| `if __name__ == '__main__':` 块（argparse + 三模式 CLI/--task/--reflect） | 包成 `def main():` 后 `if __name__ == '__main__': main()`（行为等价，仅给 shim 一个可调入口） |
| `from .agent_loop import agent_runner_loop` | → `from .loop import agent_runner_loop` |
| `from .handler import TauHandler` | 不变（同子包内） |
| `from .llm... import` / `from .tools... import` / `from .paths import` | `.` → `..`（升一级） |

### 3.4 shim 与删除

| 文件 | 处理 | 内容 |
|---|---|---|
| `core/taumain.py` | 改为入口 shim | `from core.agent.runtime import Tau, get_system_prompt, load_tool_schema, main`（显式 re-export）+ `if __name__ == '__main__': main()` |
| `core/handler.py` | 改为 shim | `from core.agent.handler import TauHandler` |
| `core/agent_loop.py` | **删除** | 无外部用户（`git grep` 验证：仅 `core/handler.py`、`core/taumain.py` 内部引用，均已迁入子包） |
| `core/agent/__init__.py` | 新建 | 精简 facade，只 re-export 公开 API：`agent_runner_loop, BaseHandler, StepOutcome`（loop）/ `TauHandler`（handler）/ `Tau`（runtime）。`format` 四函数（含 `_clean_content` 等私有）留 `format` 子模块；`get_system_prompt` / `load_tool_schema` / `main` 留 `runtime` 子模块——shim 与按需方直接 `from core.agent.<sub> import`，不进 facade（遵循 llm 重构『`_` 与内部 helper 留子模块』约定；`core.agent_loop` 无外部用户，format 无需公开兼容） |

### 关键不变量

- `core/taumain.py` 与 `core/handler.py` **必须作为真实文件留在 `core/` 顶层**——`taumain` 被 `python -m core.taumain` / `python core/taumain.py` 当脚本启动（[start_scheduler.sh](start_scheduler.sh)、[start_autonomous.sh](start_autonomous.sh)、[tau_cli/commands/_launchers.py](tau_cli/commands/_launchers.py)、各 SOP），脚本直跑读的是文件而非 import 系统，**不能**纯靠 `sys.modules` 别名替代。
- `core/__init__.py` **保持空**——不能 eager-import `core.agent` 来注册别名，否则 `import core.paths`（被 `tests/`、`memory/*.py`、`reflect/scheduler.py` 使用）会拖起整个 agent+llm 重栈。
- 上述两点合起来决定：**兼容策略用 shim 文件，不用 `sys.modules` 别名**（与 [core/llm 重构](specs/2026-06-30-core-llm-refactor-design.md) 不同——那边 `core.llm.convert` 只被包内 `__init__` 引用，外部消费 `from core.llm import X`，故 `sys.modules` 可行；agent 层外部消费子模块路径 + 脚本启动，故必须 shim）。
- `format.py` 四个函数都是**纯函数**，从 `agent_loop.py` 文件级搬出**一字不改**。
- `TauHandler` 的所有方法、`agent_runner_loop` 的循环体、`Tau` 类的方法体——**行为等价**，仅文件位置 + import 行 + 相对路径层级变更。
- `runtime.py` 模块级副作用（`load_tool_schema()` 等）在 import 时执行——与现状 `import core.taumain` 触发完全一致，无新增副作用。

---

## 4. 数据流（一个 turn，标注新边界）

```
apps/* ──from core.taumain import Tau──▶ [core/taumain.py shim] ──▶ core.agent.runtime.Tau
   │
   │  runtime.Tau.run() 起 agent_runner_loop（from core.agent.loop）
   ▼
core.agent.loop.agent_runner_loop(client, sys_prompt, query, handler, TOOLS_SCHEMA, ...)
   ├─ client.chat(messages, tools) ────────▶ core/llm（LLM 协议层，不动）
   ├─ format._clean_content(response) ─────▶ core.agent.format（输出整形，loop 内调用）
   ├─ format.get_pretty_json(args) ────────▶ core.agent.format
   ├─ format._compact_tool_args(...) ──────▶ core.agent.format
   ├─ handler.dispatch(tool_name, args) ───▶ core.agent.handler.TauHandler.do_*
   │        └─ do_code_run / do_file_* / do_web_* ─▶ core/tools/*（工具实现，不动）
   ├─ handler.turn_end_callback(...) ──────▶ core.agent.handler（summary/危险提示/记忆注入/plan hint）
   └─ yield chunks ────────────────────────▶ runtime 流式分帧 → display_queue → apps/*
```

横切：`_hook('agent_before'/'turn_before'/'tool_before'/...)` 字符串钩子由 `loop.py` 原样触发（`plugins.hooks` 可选依赖不变）。

---

## 5. 错误处理 / 兼容（沿用现状，不重新设计）

- **启动兼容**：
  - `python -m core.taumain --reflect ...`：shim 以 `__main__` 运行，`from core.agent.runtime import main` 解析（包上下文存在），`main()` 执行。✅ 主路径（[start_scheduler.sh](start_scheduler.sh)、[start_autonomous.sh](start_autonomous.sh) 验证）。
  - `python core/taumain.py`（直接脚本，[tau_cli/commands/_launchers.py](tau_cli/commands/_launchers.py)、SOPs 用）：shim 以 `__main__` 无包上下文运行。**迁移验收需实测此路径**——若当前可用，shim 视情况加 `sys.path` 修正（见 §6 步骤 8）以保平价；若当前因相对 import 不可用，则维持现状（不在本次扩展）。
- **import 兼容**：`from core.taumain import Tau`、`from core.handler import TauHandler`、`from core.agent_loop import X`（无外部用户，删除后断）——前两者靠 shim；后者 `git grep` 确认零外部引用后删。
- **钩子协议**：`_hook(...)` 字符串协议、`!!!Error:` 流中断协议、`tryparse` JSON fallback——全部随代码原样搬迁，不动。
- **回滚**：每步独立 commit；任一步出错 `git revert <sha>`，无数据/无外部状态迁移。

---

## 6. 迁移步骤（按风险递增，每步独立 commit）

> 每步附最小验证命令；全部用 [pipe-exit-code-pitfall](memory/pipe-exit-code-pitfall.md) 教训——退出码别用管道测。

1. **建子包骨架**：`mkdir -p core/agent` + 空 `__init__.py`。
   - 验证：`python -c "import core.agent"` 通过（空包可 import）。

2. **搬 + 拆 `agent_loop.py` → `loop.py` + `format.py`**：
   - 建 `core/agent/format.py`：原样搬 `json_default` / `get_pretty_json` / `_clean_content` / `_compact_tool_args`（纯函数，无内部依赖）。
   - 建 `core/agent/loop.py`：原样搬 `StepOutcome` / `BaseHandler` / `try_call_generator` / `exhaust` / `agent_runner_loop`；顶部加 `from .format import json_default, get_pretty_json, _clean_content, _compact_tool_args`。
   - **暂保留** `core/agent_loop.py`（内部消费者尚未切换）。
   - 验证：`python -c "from core.agent.loop import agent_runner_loop, BaseHandler, StepOutcome; from core.agent.format import json_default, get_pretty_json, _clean_content, _compact_tool_args"`。

3. **搬 `handler.py` → `core/agent/handler.py`**：
   - 原样复制类体；改 import：`from .agent_loop import BaseHandler, StepOutcome, json_default` → `from .loop import BaseHandler, StepOutcome` + `from .format import json_default`；`from .tools...` / `from .paths` → `from ..tools...` / `from ..paths`。
   - **暂保留** `core/handler.py`。
   - 验证：`python -c "from core.agent.handler import TauHandler"`。

4. **搬 `taumain.py` → `core/agent/runtime.py`**：
   - 原样复制；`if __name__ == '__main__'` 块包成 `def main():` 后接 `if __name__ == '__main__': main()`；改 import：`from .agent_loop import agent_runner_loop` → `from .loop import agent_runner_loop`；`from .llm...` / `from .tools...` / `from .paths` → `from ..llm...` / `from ..tools...` / `from ..paths`；`from .handler import TauHandler` 不变（同包）。
   - **暂保留** `core/taumain.py`。
   - 验证：`python -c "from core.agent.runtime import Tau, main, get_system_prompt, load_tool_schema"`。

5. **写 `core/agent/__init__.py`**（精简 facade，只放公开 API）：
   ```python
   from .loop import agent_runner_loop, BaseHandler, StepOutcome
   from .handler import TauHandler
   from .runtime import Tau
   ```
   - `format` 四函数留 `format` 子模块；`get_system_prompt` / `load_tool_schema` / `main` 留 `runtime` 子模块——均不进 facade，按需方直接 `from core.agent.<sub> import`。
   - 验证：`python -c "import core.agent; print(core.agent.Tau, core.agent.TauHandler, core.agent.agent_runner_loop)"`。

6. **替换 shim**：
   - `core/taumain.py` → 3 行 shim：`from core.agent.runtime import Tau, get_system_prompt, load_tool_schema, main`（显式 `# noqa`）+ `if __name__ == '__main__': main()`。
   - `core/handler.py` → 1 行 shim：`from core.agent.handler import TauHandler  # noqa`。
   - 验证：`python -c "from core.taumain import Tau; from core.handler import TauHandler; print('shims OK')"`。

7. **删 `core/agent_loop.py`**：
   - 删除前 `git grep -nE "from core\.agent_loop|from \.agent_loop|from \.\.agent_loop"` 应**无残留**（内部引用已迁子包）。
   - `rm core/agent_loop.py`。
   - 验证：上述 grep 返回空；`python -c "import core"` 仍 OK。

8. **启动路径 + smoke 实测**：
   - `python -m core.taumain --help`（或 `--reflect` dry-run）退出码 0。
   - `python core/taumain.py --help`（直接脚本）——**若失败且当前可用**，给 shim 加 `sys.path` 修正保平价：
     ```python
     import os, sys
     if __package__ in (None, ''):
         sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
     ```
   - `python scripts/smoke_tau.py`（[scripts/smoke_tau.py](scripts/smoke_tau.py)：`from core.handler import TauHandler` + tools）跑通。
   - `python scripts/smoke_packaging.py`（[scripts/smoke_packaging.py](scripts/smoke_packaging.py)：顶层 `core.taumain` import）跑通。
   - `pytest tests/` 全绿。

9. **before/after 行为对比**：重构前后各跑一次完整 turn（同一 prompt + 同一 LLM 配置），输出字节级一致（允许时间戳等非确定性片段）。

10. **更新文档结构说明**：
    - [README.md:136](README.md#L136) `core/` 行数注释：`agent_loop · handler · taumain · llm/ · tools/` → `agent/{loop,format,handler,runtime} · llm/ · tools/`。
    - [README.md:94](README.md#L94) `core/taumain.py` 引用——经 shim 仍有效，可加注「实现在 core/agent/runtime」。
    - `tau_cli/__init__.py` docstring `from core.handler import TauHandler` 示例——经 shim 仍可用，补注真实路径 `core.agent.handler`。
    - `docs/GETTING_STARTED.md` 若提 core/ 结构，同步。

### 回滚预案

每步独立 commit；任一步出错 `git revert <sha>` 即可。无数据库 / 无外部状态 / 无不可逆操作。

---

## 7. 验收清单

- [ ] `core/agent/{__init__,loop,format,handler,runtime}.py` 就位，依赖方向 `format ← loop ← handler ← runtime` 无环
- [ ] `from core.taumain import Tau` 通过（shim）
- [ ] `from core.handler import TauHandler` 通过（shim）
- [ ] `from core.agent import Tau, TauHandler, agent_runner_loop, BaseHandler, StepOutcome` 通过（包 facade）
- [ ] `core/agent/loop.py` 源码不含对上层子模块的引用（`grep -nE 'from \.handler|from \.runtime' core/agent/loop.py` 返回空——依赖方向单向）
- [ ] `core/agent_loop.py` 物理删除；`git grep -nE "from core\.agent_loop|from \.agent_loop"` 返回空
- [ ] `python -m core.taumain --help` 退出码 0
- [ ] `python core/taumain.py --help` 直接脚本路径：与重构前平价（若前可用则后可用）
- [ ] [scripts/smoke_tau.py](scripts/smoke_tau.py) 跑通
- [ ] [scripts/smoke_packaging.py](scripts/smoke_packaging.py) 跑通（`core.taumain` 顶层 import）
- [ ] `pytest tests/` 全绿（含 [tests/test_core_paths.py](tests/test_core_paths.py)、[tests/test_taukey_path.py](tests/test_taukey_path.py)）
- [ ] before/after 一次完整 turn 输出一致
- [ ] 外部调用方（`apps/*`、`plugins/*`、`scripts/*`、`tau_cli/*`、`reflect/*`、`memory/*.py`）import 路径零修改
- [ ] `core/llm/` / `core/tools/` / `core/paths.py` 业务逻辑零修改

---

## 8. 参考

- Pi `packages/agent` 目录结构：https://github.com/earendil-works/pi/tree/main/packages/agent
- 本地副本（离线对照）：`/Users/x404/agents/pi/packages/agent/src/`
- Tau 结构哲学（[[tau-structure-philosophy]]）：`core/` 是有意保留的顶层模块，子包划分不违反；前端在 `apps/`
- 上一轮对齐（`core/llm/` ↔ Pi `packages/ai`）：[2026-06-30-core-llm-refactor-design.md](specs/2026-06-30-core-llm-refactor-design.md)
- 兼容手法差异：llm 重构用 `sys.modules` 别名（包内引用）；本重构用 shim 文件（外部子模块引用 + 脚本启动）
