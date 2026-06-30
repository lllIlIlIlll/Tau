# CLAUDE.md — Tau 开发约定

> 用 Claude Code / AI 改 Tau 源码前读这一页。只列 **Tau 专属**约定;通用代码标准见下方权威来源,不在此重复。

## 权威标准(先读,别另起一套)

- **代码质量** → [`memory/code_review_principles.md`](memory/code_review_principles.md):15 条「什么是好代码」+ 4 问自检。
- **贡献 / 审查门槛** → [`CONTRIBUTING.md`](CONTRIBUTING.md):刻意严格,大多数 AI 生成代码无法原样通过——**以它为准,不要降级到通用准则**。

## Tau 硬约束

- **结构勿大重排**:`core/`、`TMWebDriver/` 等顶层模块有意保留;前端一律在 `apps/`(`common/tui/web/im/gui/pet/desktop/hub`)。不要为「更整洁」搬动顶层目录。
- **包管理用 `uv`**:不用 pip / venv / poetry。
- **`memory/` 是白名单**:`.py` 是工具(Agent import 调用)、`.md` 是 SOP(Agent 阅读执行)。新增或删除条目要**同步**改 `.gitignore` 的 `!memory/...` 解禁项,否则不入库。
- **CLAUDE.md ≠ Tau 运行时**:本文件只供开发期的 Claude Code 阅读;Tau 运行时 Agent 读的是 `assets/prompts/sys_prompt.txt` + `memory/`,改运行时行为请改那里。

## 工作方式

- 动手前先说清**假设与取舍**;不确定就问,别静默猜或静默选。
- 改动**外科手术式**:每行改动都能追溯到需求,不顺手「改进」无关代码。
- 宣称「完成 / 修好」前先**实测验证**(before/after 对比),用证据说话,不靠推断。
