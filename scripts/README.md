# scripts/

开发期工具集。**不在 wheel**（pyproject `exclude` 显式排除）。**不在用户运行路径**。
Agent 不可见；agent 在 SOP/工具中**只**通过 `core.tools.*` API 调用业务逻辑。

| 文件 | 这是什么 | 谁调它 |
|---|---|---|
| `smoke_*.py` (×6) | clean-subprocess 烟测，验证 import/wheel 边界 | CI / 开发者 |
| `test_*.py` (×1) | pytest 单元测试 | CI |
| `snapread.py` | 屏读/OCR 调试工具（一次性实验） | 开发者 |
| `as_probe.py` | AppleScript 探针 | macOS 自动化 SOP |
| `as_daily_appendix.py` | Reminders/Calendar 抓取脚本 | `memory/mac_automation_sop` |
| `api_examples/` | 直接调 `core.llm.transport` 的示范 | 第三方接入 demo |