# assets/external/

外部宿主资产（不进 wheel）。当前仅 1 个文件 + 0 个子目录（`tmwd_cdp_bridge/` 已随 TMWebDriver consolidation 迁出）。

| 文件 | 这是什么 | 谁调它 |
|---|---|---|
| `agent_bbs.py` | 独立 FastAPI 公告板应用（`python agent_bbs.py`） | 用户手动启停；与 Tau 框架**无 import 依赖** |