# pyproject.toml 同步修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `pyproject.toml` 与代码现状严格对齐,同步更新 README.md 和 launcher 描述中过期的 GUI 库名(PyQt5 → PySide6),并使 `uv sync --extra ui` 一次装齐所有 UI 后端。

**Architecture:** 最小修复 — 不拆 `ui` extras、不动打包边界、不加 metadata。在 3 个文件 5 处编辑内完成;最终落地为 1 个原子 commit。

**Tech Stack:** Python ≥3.10,<3.14 · uv 包管理 · setuptools 构建 · 无新依赖引入

## Global Constraints

- Python 版本: `>=3.10,<3.14` (pyproject.toml:11)
- 包管理器: uv (不用 pip/venv/poetry) — 来自 [[uv-default-package-manager]]
- 提交语言: 英文(commit message) / 中文(spec + 对话)
- 单对外 commit: 最终落地为 `chore(pyproject): 同步修复 deps + 文档`
- 不拆 `ui` extras、不动 `[build-system]` / `[tool.setuptools.*]` / `requires-python` / `all-apps`
- 不修 CLAUDE.md / CONTRIBUTING.md / 任何运行时代码 / `apps/` 下任何文件
- PySide6 版本下界: `>=6.5`(对应 Python 3.10-3.12 LTS 兼容;3.13 由 6.7+ 覆盖)
- 实施期间如需中间 commit,执行最终任务时 `git reset --soft HEAD~N && git commit -m "<对外 commit>"` 合并为单 commit

## 工作目录

仓库根: `/Users/x404/Tau/.worktrees/tau-v2.0.0`
所有路径相对此根。

---

## 任务总览

| Task | 主题 | 文件 | 验证手段 |
|---|---|---|---|
| 1 | pyproject.toml 依赖修正 | `pyproject.toml` | grep + `uv lock --check` |
| 2 | README.md 同步 | `README.md` | grep 命中数 |
| 3 | launcher desc 同步 + 最终 commit | `tau_cli/commands/_launchers.py` | `python -m tau_cli list` 输出 |

---

### Task 1: 修正 `pyproject.toml` 依赖

**Files:**
- Modify: `pyproject.toml:13-29` (dependencies 与 ui extras 两块)

**Interfaces:**
- Consumes: 当前 `pyproject.toml` 内容(已读取)
- Produces: pyproject.toml 中 streamlit 不再出现在 `dependencies`,`ui` extras 出现 `PySide6>=6.5`

**实施步骤:**

- [ ] **Step 1: 静态一致性 baseline**

执行:

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
grep -n 'streamlit' pyproject.toml
grep -n 'PySide6' pyproject.toml || echo "no PySide6 yet (expected)"
```

预期:
- `streamlit` 在 pyproject.toml 中命中 **2 处**(一行在 dependencies,一行在 ui)
- `PySide6` 命中 0 处

记录此 baseline,后续 Task 1 完成后再次执行验证归零/出现。

- [ ] **Step 2: 编辑 pyproject.toml — 从 dependencies 移除 streamlit**

定位: `pyproject.toml:18` 的 `"streamlit>=1.58.0",` 行。

执行 Edit(精确替换,不改注释):

old_string:
```
    "simple-websocket-server>=0.4",   # TMWebDriver.py
    "streamlit>=1.58.0",
]
```

new_string:
```
    "simple-websocket-server>=0.4",   # TMWebDriver.py
]
```

- [ ] **Step 3: 编辑 pyproject.toml — ui extras 新增 PySide6**

定位: `pyproject.toml:29`(`aiohttp>=3.9` 注释行末尾,`]` 前)。

执行 Edit:

old_string:
```
    "aiohttp>=3.9",                   # apps/pet/bridge.py
]
```

new_string:
```
    "aiohttp>=3.9",                   # apps/pet/bridge.py
    "PySide6>=6.5",                   # apps/gui/app.py
]
```

- [ ] **Step 4: 视觉确认 diff**

执行:

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
git diff pyproject.toml
```

预期 diff 仅含 2 处变更:
1. `dependencies` 中删除一行 `    "streamlit>=1.58.0",`
2. `ui` extras 中新增一行 `    "PySide6>=6.5",                   # apps/gui/app.py`

**绝不应包含:** 任何其他 deps 改动、metadata 变动、setuptools 变动、注释风格变动。

- [ ] **Step 5: 验证 pyproject.toml 仍合法**

执行:

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
uv lock --check 2>&1 | tail -20
```

预期: 退出码 = 0(或输出 "Lock file satisfies pyproject.toml")。若 `uv lock --check` 报错指出 PySide6 解析失败,进入"异常处理 A"。

**异常处理 A: PySide6 解析失败**

如果 uv 报告 PySide6 与当前 Python(可能 3.13)不兼容,执行:

```bash
uv python list  # 看当前实际 Python 版本
```

若确实是 3.13,把版本下界从 `>=6.5` 提升到 `>=6.7`:

```diff
-    "PySide6>=6.5",                   # apps/gui/app.py
+    "PySide6>=6.7",                   # apps/gui/app.py
```

重新执行 Step 5 验证。

- [ ] **Step 6: 静态一致性 post-check**

执行:

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
grep -n 'streamlit' pyproject.toml
grep -n 'PySide6' pyproject.toml
```

预期:
- `streamlit` 命中 **1 处**(只在 `ui` extras 中)
- `PySide6` 命中 **1 处**(只在 `ui` extras 中)

- [ ] **Step 7: 暂存 pyproject.toml(暂不 commit)**

执行:

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
git add pyproject.toml
git status
```

预期: `Changes to be committed:` 下列出 `modified: pyproject.toml`,**不应**包含其他文件(Task 2/3 之后再 commit)。

**Task 1 交付:** pyproject.toml 修正并暂存,通过 `uv lock --check`。

---

### Task 2: 同步 `README.md`

**Files:**
- Modify: `README.md:57-58` (安装指引后的 ui extras 清单)
- Modify: `README.md:89` (启动命令注释中的 GUI 行)
- Modify: `README.md:118` (前端表格的 GUI 行)

**Interfaces:**
- Consumes: Task 1 完成的 pyproject.toml
- Produces: README.md 中不再有 "PyQt5" 字样,ui extras 清单与 pyproject 对齐

- [ ] **Step 1: baseline grep**

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
grep -n 'PyQt5' README.md
```

预期: README.md 中 "PyQt5" 命中 **2 处**(L89 与 L118)。

- [ ] **Step 2: 修改 L57 区域 — ui extras 清单**

定位 README.md:55-60 区域(原内容):

```
uv pip install -e ".[ui]"            # 核心 + UI 依赖
cp taukey_template.py .tau/taukey.py  # 填入你的 LLM API Key
```

执行 Edit(精确字符串匹配,不要含周围行号):

old_string:
```
uv pip install -e ".[ui]"            # 核心 + UI 依赖
cp taukey_template.py .tau/taukey.py  # 填入你的 LLM API Key
```
```

new_string:
```
uv pip install -e ".[ui]"            # 核心 + UI 依赖
cp taukey_template.py .tau/taukey.py  # 填入你的 LLM API Key
```

> `.[ui]` 会一次性安装以下 UI 后端(可单独 pip 装其一):
> - streamlit   (Web,  apps/web/streamlit/)
> - pywebview   (Hub/Launch 桌面壳, apps/hub/)
> - textual     (TUI,  apps/tui/app.py)
> - aiohttp     (Pet,  apps/pet/bridge.py)
> - PySide6     (GUI,  apps/gui/app.py)

⚠️ 注意: 清单顺序刻意按 pyproject.toml `ui` extras 顺序排列,便于 cross-check。

- [ ] **Step 3: 修改 L89 — 启动命令注释**

定位 README.md:89 行,原内容:

```
tau gui        # 桌面聊天界面(PyQt5)
```

执行 Edit:

old_string:
```
tau gui        # 桌面聊天界面(PyQt5)
```

new_string:
```
tau gui        # 桌面聊天界面(PySide6)
```

- [ ] **Step 4: 修改 L118 — 前端表格**

定位 README.md:118 行,原内容:

```
| GUI | `tau gui` | PyQt5 桌面聊天(气泡高亮、拖拽、历史搜索) |
```

执行 Edit:

old_string:
```
| GUI | `tau gui` | PyQt5 桌面聊天(气泡高亮、拖拽、历史搜索) |
```

new_string:
```
| GUI | `tau gui` | PySide6 桌面聊天(气泡高亮、拖拽、历史搜索) |
```

- [ ] **Step 5: 视觉确认 diff**

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
git diff README.md
```

预期 diff 包含:
1. L57 区域新增 7 行(ui extras 清单)
2. L89 替换 `(PyQt5)` → `(PySide6)`
3. L118 表格列替换 `PyQt5 桌面聊天` → `PySide6 桌面聊天`

**绝不应包含:** 其他段落变动、链接变动、emoji 变动。

- [ ] **Step 6: 静态一致性 post-check**

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
grep -n 'PyQt5' README.md && echo "FAIL: PyQt5 still present" || echo "OK: PyQt5 removed"
```

预期: `OK: PyQt5 removed`(grep 退出码 1,fallthrough 到 OK)。

- [ ] **Step 7: 暂存 README.md(暂不 commit)**

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
git add README.md
git status
```

预期: `Changes to be committed:` 下列出 `modified: pyproject.toml` + `modified: README.md`。

**Task 2 交付:** README.md 同步并暂存,无 PyQt5 残留。

---

### Task 3: 同步 `_launchers.py` desc + 落地最终 commit

**Files:**
- Modify: `tau_cli/commands/_launchers.py:22` (gui launcher desc 字符串)

**Interfaces:**
- Consumes: Task 1/2 暂存但未 commit 的 pyproject.toml + README.md
- Produces: 全仓库 `grep -rEn 'PyQt5' .` 命中数 = 0;最终对外 1 个 commit

- [ ] **Step 1: baseline grep 全仓**

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
grep -rEn 'PyQt5' . --include='*.py' --include='*.toml' --include='*.md' 2>/dev/null | grep -v '\.venv/' | grep -v '__pycache__' | grep -v 'tau.egg-info'
```

预期: 命中 **1 处**:`tau_cli/commands/_launchers.py:22`(desc 字符串)。

- [ ] **Step 2: 修改 _launchers.py L22**

定位: `tau_cli/commands/_launchers.py:22`,原 desc:

```python
        "desc": "启动基于 PyQt5 的完整桌面聊天界面(气泡代码高亮、文件拖拽、历史搜索)",
```

执行 Edit:

old_string:
```
        "desc": "启动基于 PyQt5 的完整桌面聊天界面(气泡代码高亮、文件拖拽、历史搜索)",
```

new_string:
```
        "desc": "启动基于 PySide6 的完整桌面聊天界面(气泡代码高亮、文件拖拽、历史搜索)",
```

- [ ] **Step 3: 静态一致性 post-check — 全仓 PyQt5 = 0**

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
grep -rEn 'PyQt5' . --include='*.py' --include='*.toml' --include='*.md' 2>/dev/null | grep -v '\.venv/' | grep -v '__pycache__' | grep -v 'tau.egg-info' && echo "FAIL: PyQt5 still present" || echo "OK: no PyQt5 anywhere"
```

预期: `OK: no PyQt5 anywhere`(grep 命中为空,退出码 1,fallthrough 到 OK)。

- [ ] **Step 4: 验证 launcher desc 实际生效**

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
uv sync --extra ui 2>&1 | tail -3
python -m tau_cli list 2>&1 | grep -i 'gui'
```

预期:
- `uv sync --extra ui` 退出码 = 0(PySide6 实际安装)
- `python -m tau_cli list` 输出包含一行描述含 "PySide6"(精确匹配 `_launchers.py` 的 desc 串)

**异常处理 B: `python -m tau_cli list` 抛 ImportError**

若 PySide6 解析失败导致 list 命令异常,执行:

```bash
python -c "import tau_cli; print(tau_cli.__file__)"
```

确认 tau_cli 包可导入。常见原因是 `apps/` 被 exclude 但 launcher 通过 `importlib` 动态加载,某些平台需要 PYTHONPATH 调整;若仍失败,回退到只验证 desc 字符串内容(`grep -n 'PySide6' tau_cli/commands/_launchers.py`)作为间接验证。

- [ ] **Step 5: 暂存 _launchers.py**

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
git add tau_cli/commands/_launchers.py
git status
```

预期: 3 个 modified 文件全部 staged:
- `modified: pyproject.toml`
- `modified: README.md`
- `modified: tau_cli/commands/_launchers.py`

**绝不应**有其他文件(untracked 或 modified)。

- [ ] **Step 6: 落地最终对外 commit**

执行:

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
git commit -m "chore(pyproject): 同步修复 deps + 文档

- pyproject.toml: 移除 base deps 中重复的 streamlit
- pyproject.toml: ui extras 新增 PySide6>=6.5 (apps/gui 用)
- README.md: GUI PyQt5 → PySide6;补 ui extras 组件清单
- tau_cli/commands/_launchers.py: gui desc PyQt5 → PySide6"
```

预期: 1 个 commit 落地,包含 3 文件改动。

- [ ] **Step 7: 验证 commit 内容**

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
git log -1 --stat
```

预期: commit 标题如上,stat 输出 3 文件变更;**只有**这 3 个。

- [ ] **Step 8: 最终烟雾测试**

```bash
cd /Users/x404/Tau/.worktrees/tau-v2.0.0
python -c "import core.paths, core.taumain, TMWebDriver, TMWebDriver.simphtml, tau_cli; print('imports OK')"
python -c "import streamlit, pywebview, textual, aiohttp, PySide6; print('ui deps OK')"
```

预期: 两行 `... OK` 输出,退出码 = 0。

**Task 3 交付:** 全 3 文件改动以 1 个原子 commit 落地,所有静态与运行时验证通过。

---

## 自审

**1. Spec 覆盖检查**

| Spec 要求 | 任务 |
|---|---|
| 移除 `dependencies` 中 streamlit | Task 1 Step 2 |
| `ui` extras 加 PySide6≥6.5 | Task 1 Step 3 |
| `uv lock --check` 验证 | Task 1 Step 5 |
| README.md L57 ui extras 清单 | Task 2 Step 2 |
| README.md L89 注释 | Task 2 Step 3 |
| README.md L118 表格 | Task 2 Step 4 |
| `_launchers.py` L22 desc | Task 3 Step 2 |
| 单对外 commit | Task 3 Step 6 |
| 全仓 PyQt5 = 0 | Task 3 Step 3 |
| `python -m tau_cli list` 验证 | Task 3 Step 4 |
| 烟雾测试 | Task 3 Step 8 |

**无遗漏。**

**2. 占位符扫描:** 无 TBD / TODO / "implement later" / "fill in"。所有代码块、命令、期望输出均完整。

**3. 类型/接口一致性:** 各 Step 之间无相互引用类型,纯文本编辑 + 命令验证,无签名漂移风险。

## 关联引用

- [[uv-default-package-manager]] — 所有命令以 uv 为前提
- [[tau-structure-philosophy]] — `apps/` 被 exclude 是有意设计,Task 3 Step 4 异常处理 B 因此可能触发

## 执行交付选项

Plan 已保存到 `docs/superpowers/plans/2026-06-27-pyproject-sync-deps.md`。

两种执行方式:

1. **Subagent-Driven(推荐)** — 每个 Task 派一个新 subagent,Task 间做 review,迭代快
2. **Inline Execution** — 在当前会话直接执行,带 checkpoint

请选择执行方式。