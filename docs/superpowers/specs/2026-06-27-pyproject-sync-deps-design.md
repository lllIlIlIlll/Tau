# pyproject.toml 同步修复设计

> 日期: 2026-06-27
> 分支: `tau-v2.0.0`
> 范围: 最小修复 + 与 pyproject 直接相关的文档同步

## 背景

`pyproject.toml` 与代码现状存在两处不一致(依赖本身),且三处面向用户的描述仍指向过期的 GUI 库。

### 不一致清单

| # | 位置 | 现状 | 实际 |
|---|---|---|---|
| 1 | `pyproject.toml` `dependencies` | 包含 `streamlit>=1.58.0` | streamlit 仅 `apps/web/streamlit/` 用,应只属于 `ui` extras |
| 2 | `pyproject.toml` `ui` extras | 缺少 PySide6 | `apps/gui/app.py` 第 21 行 `from PySide6.QtWidgets import ...` 实际依赖 |
| 3 | `README.md` L89/L118 | 写"PyQt5" | 代码用 PySide6 |
| 4 | `tau_cli/commands/_launchers.py` L22 | desc 字符串写"PyQt5" | 代码用 PySide6 |
| 5 | `README.md` L57 | `uv pip install -e ".[ui]"` 旁未列出 UI 组件 | 用户不知该 extras 实际装了哪些 UI 后端 |

注: `all-apps` extras 已正确覆盖 `apps/im/*` 实际 import 的 SDK 名(`python-telegram-bot`、`qq-botpy`、`pycryptodome`、`qrcode`、`lark-oapi`、`wecom-aibot-sdk`、`dingtalk-stream`),无需调整。

## 目标

1. `pyproject.toml` 与代码现状严格一致
2. 用户安装 `.[ui]` 后,GUI/TUI/Web/Pet/Hub 全部可用
3. README 与 launcher 描述同步到 PySide6

## 非目标

- 不拆 `ui` extras(避免范围蔓延)
- 不增加 metadata(`authors` / `urls` / `classifiers`)
- 不动 `[build-system]` / `[tool.setuptools.*]`(已正确)
- 不动 `requires-python`(已正确)
- 不修 CLAUDE.md(已检查,无过期依赖描述)
- 不修 `all-apps`(已正确)

## 设计

### 1. `pyproject.toml`

**依赖去重:**

```diff
 dependencies = [
     "requests>=2.28",                 # core/llm/transport.py
     "beautifulsoup4>=4.12",           # TMWebDriver/simphtml.py
     "bottle>=0.12",                   # TMWebDriver/TMWebDriver.py
     "simple-websocket-server>=0.4",   # TMWebDriver/TMWebDriver.py
-    "streamlit>=1.58.0",
 ]
```

理由: `streamlit` 仅 `apps/web/streamlit/app*.py` 使用,而 `apps/` 被 `[tool.setuptools.packages.find]` exclude,不会进 wheel;但 `streamlit` 作为 base dep 会在 `pip install tau` 时强制拉取,与"按需安装 UI"的注释意图不符。

**ui extras 补 PySide6:**

```diff
 ui = [
     "streamlit>=1.58.0",              # apps/web/streamlit/
     "pywebview>=4.0",
     "textual>=0.70",                  # apps/tui/app.py
     "aiohttp>=3.9",                   # apps/pet/bridge.py
+    "PySide6>=6.5",                   # apps/gui/app.py
 ]
```

理由: `apps/gui/app.py` 顶部注释明示 "依赖: pip install PySide6",运行时硬依赖。版本下界 `6.5` 对应 Python 3.10+ 兼容的稳定 LTS 分支。

### 2. `README.md`

- **L57 区域** (开发安装指引): 在 `uv pip install -e ".[ui]"` 的 bash 示例**关闭后**,追加一段 blockquote 说明,列出本 extras 实际安装的 UI 后端,使 `.[ui]` 不再是黑盒:

  ```diff
  uv pip install -e ".[ui]"            # 核心 + UI 依赖
  cp taukey_template.py .tau/taukey.py  # 填入你的 LLM API Key
  ```
  +
  +> `.[ui]` 会一次性安装以下 UI 后端(可单独 pip 装其一):
  +> - streamlit   (Web,  apps/web/streamlit/)
  +> - pywebview   (Hub/Launch 桌面壳, apps/hub/)
  +> - textual     (TUI,  apps/tui/app.py)
  +> - aiohttp     (Pet,  apps/pet/bridge.py)
  +> - PySide6     (GUI,  apps/gui/app.py)

- **L89 启动命令注释**: `tau gui  # 桌面聊天界面(PyQt5)` → `tau gui  # 桌面聊天界面(PySide6)`
- **L118 前端表格**: `PyQt5 桌面聊天(...)` → `PySide6 桌面聊天(...)`

### 3. `tau_cli/commands/_launchers.py`

**L22** desc 字符串:

```diff
-        "desc": "启动基于 PyQt5 的完整桌面聊天界面(气泡代码高亮、文件拖拽、历史搜索)",
+        "desc": "启动基于 PySide6 的完整桌面聊天界面(气泡代码高亮、文件拖拽、历史搜索)",
```

理由: `tau list` 输出的 desc 串直接影响终端用户体验;与代码 + README 保持一致是单一事实来源的最低要求。

## 不影响清单

| 文件 | 是否改动 |
|---|---|
| `core/` | ❌ |
| `tau_cli/cli.py` | ❌ |
| `tau_cli/commands/*.py` (除 `_launchers.py` L22) | ❌ |
| `TMWebDriver/` | ❌ |
| `memory/` | ❌ |
| `reflect/` | ❌ |
| `apps/` | ❌ |
| `CLAUDE.md` | ❌ |
| `CONTRIBUTING.md` | ❌ |
| `uv.lock` | ❌ (不主动改;`uv lock` 由验证步骤生成) |
| `pyproject.toml` 中的 `all-apps` / `build-system` / `requires-python` / `setuptools.*` | ❌ |

## 验证计划

1. **静态一致性**
   - `grep -rEn 'PyQt5' . --include='*.py' --include='*.toml' --include='*.md'` 命中数 = 0(改前应 ≥ 3)
   - `grep -n 'streamlit' pyproject.toml` 命中数 = 1(改前 = 2)
   - `grep -n 'PySide6' pyproject.toml` 命中数 ≥ 1(改前 = 0)

2. **依赖解析**
   - `uv lock --check` 退出码 = 0
   - `uv sync --extra ui` 退出码 = 0,实际安装 PySide6 ≥ 6.5

3. **导入烟雾测试**
   - `python -c "import core.paths, core.taumain, TMWebDriver, TMWebDriver.simphtml, tau_cli"` 退出码 = 0
   - `python -c "import streamlit, pywebview, textual, aiohttp, PySide6"` 退出码 = 0

4. **launcher desc 一致性**
   - `python -m tau_cli list` 输出中 `gui` 行的 desc 含 "PySide6"

## 风险与回滚

- **风险 1: PySide6 ≥ 6.5 与 Python 3.10/3.11/3.12/3.13 兼容性**
  - PySide6 6.5+ 官方支持 Python 3.9-3.12,3.13 自 6.7+ 支持
  - 缓解: 若 `uv lock` 报告 Python 3.13 解析冲突,下界降为 `>=6.7` 或保持 `>=6.5` 信任上游兼容性
- **风险 2: `uv.lock` 与 pyproject 不同步**
  - 缓解: `uv lock` 由验证步骤自动同步;若 CI 失败,本地先跑 `uv lock` 再提交
- **回滚**: 单 commit revert 即可,改动面小(3 文件,5 处编辑)

## 实施分块

按"原子性 + 易审查"原则,合并为 **1 个 commit**:

```
chore(pyproject): 同步修复 deps + 文档

- pyproject.toml: 移除 base deps 中重复的 streamlit
- pyproject.toml: ui extras 新增 PySide6>=6.5 (apps/gui 用)
- README.md: GUI PyQt5 → PySide6;补 ui extras 组件清单
- tau_cli/commands/_launchers.py: gui desc PyQt5 → PySide6
```

不拆多 commit: 所有改动都属于"pyproject 同步"主题,逻辑上一体。

## 关联引用

- [[uv-default-package-manager]] — Python 默认 uv,验证步骤以此为前提
- [[tau-structure-philosophy]] — apps/ 顶层模块不在 pyproject wheel 中,但源码散落