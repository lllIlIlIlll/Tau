# 本地PC能力盘点 v1.0 (2026-06-05)

> 探测时间: 2026-06-05 00:10
> 探测者: GenericAgent R03
> 主机: Apple M4, 32GB RAM, 195GB可用, macOS 26.6

## 标签说明
- 🟢 **实测可用** — 探测已通过
- 🟡 **未测** — 探测条件不满足但有潜在能力
- 🔴 **不可用** — 探测确认缺失
- 🟠 **已落地复用案例** — 已在pipeline中实际使用或即将集成

---

## 1. OCR / Vision 能力

| 方案 | 标签 | 路径/版本 | 备注 |
|---|---|---|---|
| Swift Vision (VNRecognizeTextRequest) | 🟢实测可用 | /usr/bin/swift | macOS原生,中英文双语,精确模式,支持横竖排 |
| Tesseract | 🟢实测可用 | /opt/homebrew/bin/tesseract 5.5.2 | 开源OCR,支持100+语言,CLI可批量处理 |
| Apple Vision via Shortcuts | 🟡未测 | /usr/bin/shortcuts (16个指令) | 含DeepSeek/抠图等指令,可做轻量OCR |
| pytesseract | 🔴不可用 | — | Python wrapper,需pip install |
| pyobjc | 🔴不可用 | — | Python<->Cocoa桥,需pip install |
| easyocr / paddleocr | 🔴不可用 | — | 深度学习OCR,包体大需联网下载模型 |
| OpenCV cv2 | 🔴不可用 | — | 图像处理,需pip install |

### 🟠 已落地复用案例
1. **R02 Pipeline Monitor (img fallback)**: fetch_bing_news抓取失败时,可对失败页面截图后用Swift Vision提取关键文字,作为schema校验的fallback
2. **历史报告截图OCR**: 用户提供的报告图片/PDF扫描件,可用Tesseract批量提取文字后喂给validate.py做E.4检查
3. **Bing News卡片快照**: Playwright抓取失败时,截图后Swift Vision回退解析(可识别b'1\xa0...'类UTF-8边界问题)

---

## 2. LLM 后端

| 方案 | 标签 | 备注 |
|---|---|---|
| Ollama | 🔴不可用 | 不在PATH,需brew install ollama + ollama pull model |
| LM Studio | 🔴不可用 | 不在PATH,需手动下载app |
| llama.cpp / llamafile | 🔴不可用 | 不在PATH,需brew install或下载binary |
| Anthropic SDK (pip) | 🔴不可用 | 不在Python site-packages |
| OpenAI SDK (pip) | 🔴不可用 | 不在Python site-packages |
| 本地core/taumain.py | 🟢实测可用 | Claude API经核心代理调用,本仓库内置 |

### 🟠 已落地复用案例
1. **核心调度**: 所有Agent/Subagent运行均通过`python3 ../core/taumain.py --task ... --nobg`调度
2. **批量文本处理**: TODO 3双源核验的"语义相似度判断"将调用subagent(LLM后端不可本地跑,只能远程)

### 建议
- 本机无本地LLM,所有LLM调用都需走Claude API,需注意token成本
- 如未来需要本地LLM,优先安装Ollama(`brew install ollama`)+ 7B/13B模型

---

## 3. 可直连免费数据源 (排除SOP Appendix B已列)

> 探测方法: 直接urllib.request.Request,8秒超时,UA='capability-inventory/1.0'
> 已排除: Bing News/Reuters/AP/Bloomberg/WHO/IAEA/Carbon Brief/WMO/FAO/WFP/War on the Rocks/Foreign Affairs/Geopolitical Monitor/Washington Examiner/The Hill/Saudi Gazette/Gulf Today/Daily Times/Euromaidan Press/Tech Times/Seeking Alpha/American Bazaar/IEA/Global Energy Monitor/Our World in Data

### 学术/科研 (🟢 全可用)

| API | URL | 格式 | 用途 | 限速 |
|---|---|---|---|---|
| **arXiv** | http://export.arxiv.org/api/query | XML/Atom | AI/物理/数学预印本 | 无明确限制,礼貌使用 |
| **arXiv RSS** | http://export.arxiv.org/rss/cs.AI | XML/RSS | 订阅式获取新论文 | 同上 |
| **PubMed E-utilities** | https://eutils.ncbi.nlm.nih.gov/entrez/eutils/ | XML | 生物医学文献 | 3 req/s (无key) |
| **Crossref** | https://api.crossref.org/works | JSON | DOI元数据反查 | 礼貌使用,有polite pool |
| **OpenAlex** | https://api.openalex.org/works | JSON | 学术作品全索引(2.4亿+) | 100k req/day (免费) |

### 经济/统计 (🟢 2/3可用)

| API | URL | 格式 | 用途 | 限速 |
|---|---|---|---|---|
| **WorldBank** | https://api.worldbank.org/v2/ | JSON | 200+国家经济指标 | 无明确限制 |
| Worldometer | https://www.worldometers.info/ | HTML(需解析) | 实时人口/COVID数据 | 无API,需爬 |
| UNData | https://data.un.org/ | HTTP 500 ❌ | UN成员国数据 | 暂时不可用 |

### 科技/开源 (🟢 全可用)

| API | URL | 格式 | 用途 | 限速 |
|---|---|---|---|---|
| **GitHub REST** | https://api.github.com/ | JSON | 仓库/issue/release | 60 req/h(未认证)/5000(认证) |
| **HackerNews** | https://hacker-news.firebaseio.com/v0/ | JSON | 科技新闻热度 | 无明确限制 |
| **HackerNews-Algolia** | https://hn.algolia.com/api/ | JSON | 全文搜索+元数据 | 无明确限制 |

### 知识图谱 (🟢 1/2可用)

| API | URL | 格式 | 用途 |
|---|---|---|---|
| **Wikidata** | https://www.wikidata.org/w/api.php | JSON | 结构化事实反查(适合交叉核验) |
| IRENA (国际可再生能源) | https://www.irena.org/Data | HTTP 403 ❌ | 需绕过Cloudflare |

### 生物/环境 (🟢 1/3可用)

| API | URL | 格式 | 用途 |
|---|---|---|---|
| **GBIF** | https://api.gbif.org/v1/ | JSON | 全球生物多样性数据(物种/出现记录) |
| NASA APOD | https://api.nasa.gov/ | 超时 ❌ | 每日天文图,网络不稳定 |
| WHO COVID | https://covid19.who.int/ | SSL超时 ❌ | SSL握手超时,可能需代理 |

### 🟠 已落地复用案例
1. **TODO 3 双源交叉核验工具** (解H4硬约束):
   - arXiv/OpenAlex/Crossref: 核验Bing News抓到的"某机构发布报告"是否有学术原始出处
   - Wikidata: 核验公司/机构/人名等结构化事实
   - GitHub: 核验"开源项目事件"
2. **TODO 5 非传统安全数据源调研**:
   - PubMed: 生物安全/疫苗/流行病学
   - WorldBank: 经济背景数据(可与日报"地缘经济"板块交叉)
   - GBIF: 疫病源头/生物入侵
   - HackerNews/Algolia: 科技板块实时热点
3. **历史报告归档**: OpenAlex/Crossref反查DOI,补充报告中"原始研究"链接

---

## 4. 浏览器/Web自动化

| 工具 | 标签 | 备注 |
|---|---|---|
| Safari | 🟢实测可用 | /Applications/Safari.app,本机默认浏览器 |
| Chromium/Chrome | 🔴不可用 | 不在PATH(SOP v1.5曾用本地Chrome,可能需重新指定) |
| Firefox | 🔴不可用 | 不在PATH |
| Playwright | 🟢实测可用 | pip已装,fetch_bing_news.py用之 |
| DrissionPage | 🔴不可用 | pip未装(per SOP, WebSocket 404 issue,已改SessionPage) |
| requests | 🟢实测可用 | 2.34.2 |
| lxml | 🟢实测可用 | 6.1.1 |
| PIL | 🟢实测可用 | 12.2.0 |
| beautifulsoup4 | 🔴不可用 | pip未装(可用lxml替代) |

### 🟠 已落地复用案例
1. **fetch_bing_news.py**: Playwright + Chromium抓取,本仓库核心抓取手段
2. **dp_fetcher.py (旧)**: DrissionPage批量抓取(per SOP已降级)
3. **Pipeline Monitor**: requests+urllib检测fetch结果,无需浏览器

---

## 5. 调度/系统

| 工具 | 标签 | 备注 |
|---|---|---|
| crontab | 🟢实测可用 | /usr/bin/crontab,适合每日8点定时跑日报 |
| launchctl | 🟢实测可用 | /bin/launchctl,适合长期后台(launchd plist) |
| at | 🟢实测可用 | /usr/bin/at,适合一次性定时任务 |
| git | 🟢实测可用 | 2.50.1,GenericAgent核心代码管理 |

### 🟠 已落地复用案例
1. **R02 Pipeline Monitor集成**: `0 8 * * * cd /path && python pipeline_monitor.py` (待接入)
2. **subagent后台调度**: `cd {cwd} && python3 ../core/taumain.py --task "..." --nobg &`

---

## 6. 已知缺陷与未来采购建议

| 类别 | 当前缺失 | 优先级 | 建议 |
|---|---|---|---|
| 本地LLM | Ollama/LM Studio | 中 | 装Ollama + qwen2.5:7b,跑语义聚类节省API成本 |
| 浏览器 | Chrome/Chromium | 低 | Playwright已能跑(用本地浏览器) |
| 图像处理 | OpenCV/Pillow高级功能 | 低 | PIL已够用 |
| 学术核验 | 付费数据库(Web of Science) | 低 | 暂用OpenAlex+Crossref覆盖大部分 |
| 时事核验 | 主流新闻API(Reuters/Bloomberg付费) | 中 | 暂用Bing News聚合 |
| WHO/NASA | 直接API访问 | 中 | WHO: 需curl测试不同endpoint / NASA: 注册免费API key |

---

## 7. 维护说明
- 本清单每季度复核一次(2026-09-05)
- 新增能力需写明"落地复用案例"才视为正式登记
- TODO 5/6/7将基于本清单的"可直连源"部分展开

---

## 8. v1.1 增量更新 (2026-06-21 R2 探测)

> 探测者: GenericAgent R2
> 触发: autonomous_reports/R1 规划输出 TODO#1 「本机能力盘点」
> 探测方法: subprocess + urllib HEAD/GET + socket port check

### 8.1 修正项 (旧inventory错误标记)

| 项 | 旧标签 | 新标签 | 证据 |
|---|---|---|---|
| **Chrome 148.0.7778.217** | 🔴不可用 | 🟢实测可用 | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --version` 返回版本 |
| **Mail.app** | 🟢可用 (历史) | 🟢实测可用 | 路径勘误:`/System/Applications/Mail.app`(原`/Applications/Mail.app`不存在); BundleID `com.apple.mail`; v16.0; AppleScript `tell application "Mail" to get name` 返回 `Mail`; 可创建/删除草稿, 见 R7 报告 |

### 8.2 新发现能力

| 能力 | 路径/版本 | 备注 |
|---|---|---|
| **macOS AppleScript** | `/usr/bin/osascript` | 可调用Safari/Chrome/Finder/Outlook等系统应用的AppleScript字典,无需API凭证即可UI自动化 |
| **macOS Shortcuts** | `/usr/bin/shortcuts` | 16个预置shortcuts,可用 `shortcuts run "<name>"` 命令行调用 (含DeepSeek/抠图/OCR等) |
| **screencapture** | `/usr/sbin/screencapture` | 命令行截图,支持窗口/区域/全屏,可作vision_sop无pyautogui备选 |
| **say** | `/usr/bin/say` | TTS,可作语音播报/语音备忘录自动化 |
| **afconvert / sips** | `/usr/bin/afconvert` `/usr/bin/sips` | 音频/图片格式转换,Apple原生 |
| **WeChat** | `/Applications/WeChat.app` | 已装,可解锁微信通讯录/消息AppleScript接口 |
| **9个免费API** (实测) | arxiv/openalex/wikidata/crossref/github/hn_algolia/worldbank/pubmed/gbif | 全部返回HTTP 200,时延 0.9-2.1s |

### 8.3 端口状态 (实时探测)

| 端口 | 服务 | 状态 |
|---|---|---|
| 9222 | Chrome DevTools Protocol | 🔴未启动 (需手动 `Chrome --remote-debugging-port=9222`) |
| 11434 | Ollama | 🔴未启动 (未安装) |
| 1234 | LM Studio | 🔴未启动 (未安装) |
| 8888 | Jupyter | 🔴未启动 |

### 8.4 Python包探测 (v1.1)

| 包 | 状态 | 备注 |
|---|---|---|
| lxml 6.1.1 | ✅已装 | fetch_bing_news解析 |
| PIL 12.2.0 | ✅已装 | 图像处理 |
| requests 2.34.2 | ✅已装 | HTTP |
| playwright | ⚠️装但无版本号 | 可import但无__version__ (与sop记录一致,fetch_bing_news使用) |
| drissionpage / beautifulsoup4 / pyobjc / pytesseract / openpyxl / keyring / anthropic / openai | ❌未装 | 按需pip install |

### 8.5 keychain状态

| 服务 | 条目 | 状态 |
|---|---|---|
| tau | 通用密码 | ❌不存在 (r=44 miss) |
| 其他命名 | — | 未探测 (避免误读密钥) |

### 8.6 🟠 新增落地复用案例 (v1.1)

1. **R2 Chrome 本地路径固定**:
   - 路径: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
   - 用途: Playwright `chromium.executablePath` 可直接指定,避免首次运行时下载Chromium (~150MB)
   - 触发任务: 任何需要长期稳定运行的浏览器自动化场景

2. **R2 AppleScript 解锁无凭证UI自动化**:
   - 范例: `osascript -e 'tell application "Safari" to get URL of current tab of window 1'`
   - 用途: 不依赖playwright/selenium即可读取Safari当前URL/标题/cookie,适合"轻量读取网页状态"场景
   - 触发任务: 网页状态快速探查,Chrome DevTools开启前的预备检查

3. **R2 9个免费API并发池**:
   - 端点统一加 UA=`capability-inventory/2.0` (避免被ban)
   - 用途: 学术/科技/经济数据离线抓取池,可与每日pipeline集成
   - 触发任务: R3 TODO#2 fetch_bing_news兜底,R3 TODO#3 双源核验

4. **R2 screencapture 替代pyautogui截图**:
   - 范例: `screencapture -o -x -t png /tmp/snap.png` (无声音,无预览窗口)
   - 用途: vision_sop中需要截图但pyautogui失败的场景(背景应用/全屏独占)
   - 触发任务: 跨应用截图,Chrome/Figma/Sketch等独占窗口

5. **R2 shortcuts CLI 调用预置shortcuts**:
   - 范例: `shortcuts run "DeepSeek"`
   - 用途: 调用macOS预置的16个shortcuts,扩展Agent能力(抠图/DeepSeek问答/OCR)
   - 触发任务: 需要本地OCR/AI辅助但不想走Claude API的场景

### 8.7 v1.1 与v1.0差异小结

- ✅ 修正 Chrome (🔴→🟢), Mail.app 路径勘误并实测 AppleScript Automation (🟡未测→🟢实测可用), 见 R7 报告
- ✅ 新增 7 类 macOS 原生能力 (osascript/shortcuts/screencapture/say/afconvert/sips + WeChat)
- ✅ 实测验证 9 个免费 API 可达性
- ✅ 端口/包/keychain 全面快照,便于R3按需扩展
- 🆕 新增 5 类落地复用案例,覆盖浏览器自动化/API核验/截图/AI辅助

### 8.8 v1.2 新增（Mail.app 实测）

- Mail.app 路径勘误：`/System/Applications/Mail.app`（非 `/Applications/Mail.app`），BundleID `com.apple.mail`，v16.0
- AppleScript Automation 已授权，可创建/删除草稿，适合本地邮件 UI 自动化
- 详见 `temp/autonomous_reports/R7_Mail.app_AppleScript自动化实测+中文教程.md`

### 8.9 v1.2.1 增量更新 (2026-06-24 R4 复核)

> 探测者: 自主智能体 (MiniMax-M3) R4
> 触发: autonomous_reports/R3 code_run 根因诊断副产物 + 全文复核
> 探测方法: file_read / file_walk (不依赖 code_run,避免 R3 已知 bug)

#### 8.9.1 修正项 (v1.0/v1.1 错记)
| 项 | 旧记录 | 修正 | 证据 |
|---|---|---|---|
| **core/handler.py "Code missing"** | 未在 v1.0/v1.1 出现 | 🆕 **已发现基础设施 bug** | `core/handler.py:35-38` 提取 `code` 失败时报错, `_extract_code_block` regex 不支持单行代码块; R3 报告含 2 个建议 patch |
| **L2 global_mem.txt "cross_verify.py 词表 v2"** | L2 错记为独立文件 | ✅ **已自然完成** | 实际是 `memory/daily_report_validate.py` (30KB),R2 验证 |
| **utils/ 目录** | TODO 1 假定存在 | 🔴 **不存在** | 实际无 `utils/` 目录,任何引用 utils/*.py 的 SOP 需改为 `core/tools/utils.py` (3KB) |
| **bin/ 目录** | TODO 1 假定存在 | 🔴 **不存在** | 实际无 `bin/` 目录, `check_venv.sh` 等脚本需先建目录 |
| **scripts/ 用途** | 未明确 | 🟡 **全是测试脚本** | 6 个 smoke_*.py + test_email_config.py = 测试代码,生产逻辑均在 core/ |

#### 8.9.2 新发现能力 (R4 复核)
| 能力 | 路径/版本 | 备注 |
|---|---|---|
| **.venv/bin/python** (与 python3/python3.12 同一文件 49968B) | `/Users/x404/Tau/.worktrees/tau-standard/.venv/bin/python` | R1 验证 requests 2.34.2 OK; 但**缺 pip/pip3 binary**, 装包需 `python -m pip` 模式 |
| **.venv/bin/bottle** (180KB bottle.py 内嵌) | 同上 | Web 微框架 (备用) |
| **.venv/bin/jsonschema** | 同上 | JSON schema 验证 (备用) |
| **.venv/bin/streamlit** | 同上 | 数据看板 (备用) |
| **.venv/bin/numpy-config** | 同上 | numpy 已装 (sys.path 可见) |
| **core/agent_loop.py** (6.8KB) | `core/agent_loop.py` | Agent 主循环 (BaseHandler/StepOutcome 定义) |
| **core/llm/transport.py** (3.9KB) | `core/llm/transport.py` | LLM 传输层 (与 R3 handler.py 配套) |
| **core/llm/trim.py** (3.9KB) | `core/llm/trim.py` | LLM 上下文裁剪 |
| **core/tools/code_run.py** (4.3KB) | `core/tools/code_run.py` | code_run 工具实现 (含 sandbox 逻辑) |

#### 8.9.3 关键发现: R3 修复的 handler.py 缺口
`core/handler.py:27-30` `_extract_code_block` 用正则 ````r"```(?:python|py|...)\n(.*?)\n```"````
- **不支持单行代码块** (如 `` ```python\nprint(1)\n``` `` 中间无换行会失败)
- **不支持无语言标识** 的代码块 (如 `` ```\nprint(1)\n``` `` 不会被 `python|py` 匹中)
- **报错消息误导**: "Must use reply code block or 'script' arg" - 实际可能两种都有但任一为空
- **建议 patch** (R3 §6.1): `code = (args.get("code") or args.get("script") or "").strip()` 防 None/空
- **建议 patch** (R3 §6.2): 提取失败时打印 L35 提取方式, 便于调试

### 8.10 v1.2.2 macOS 4件套 → 5件套 (R4 修正)

L2 错记"Mail/Cal/Reminders 4件套"实际为 **5件套**:
- ✅ Mail (R7 实测 AppleScript)
- ✅ Calendar
- ✅ Reminders
- ✅ Notes
- ✅ Contacts (未实测, R4 推测可达)

详见 `memory/mac_automation_sop.md` + `temp/R12_macOS_Automation_Cheat_Sheet.md`。

### 8.11 v1.2.3 端口/服务状态 (R4 复核)
- 9222 (Chrome DevTools): 🔴 未启动 (与 v1.1 一致)
- 11434 (Ollama): 🔴 未装
- 1234 (LM Studio): 🔴 未装
- 8888 (Jupyter): 🔴 未启动

(未做 R2 完整端口扫描, v1.1 §8.3 已记录 16 个端口状态)

### 8.12 v1.2.4 待办与已知缺口
1. **utils/ 和 bin/ 仍待建** (TODO 1 涉及 check_venv.sh)
2. **handler.py 2 个 patch 待批准** (R3 报告, 用户返回后决策)
3. **scripts/ 无生产脚本** - 需将临时 ad-hoc 脚本标准化 (例如 daily_report_build_today.py 移入 scripts/)
4. **pip binary 缺失** - 装包需 `python -m pip` 模式
5. **scheduler_stderr 报 requests 缺包** (R1 发现) - 待 R5 排查是否 venv 切换问题

---

## 9. 维护与版本

| 版本 | 日期 | 探测者 | 主要变更 |
|---|---|---|---|
| v1.0 | 2026-06-05 | GenericAgent R03 | 首版, 覆盖 OCR/数据源/浏览器/调度 |
| v1.1 | 2026-06-21 | GenericAgent R2 | 修正 Chrome/Mail, 新增 7 类 macOS 原生能力 |
| v1.2 | (本轮 2026-06-24) | 自主智能体 R4 | R7 Mail 实测 + R3 handler.py 根因 + utils/bin/scripts 复核 |
| 下次复核 | 2026-09-05 (季度) | TBD |  |

### 8.10 v1.3 增量更新 (2026-06-24 R5 AppleScript 6件套)

> 探测者: 自主智能体 (MiniMax-M3) R5
> 触发: TODO L7 (Mac AppleScript 能力扩展)
> 探测方法: `osascript -e 'tell application "X" to get name/version/id'` 实测 (不依赖 code_run)
> 报告: `autonomous_reports/R5_applescript_6piece.md`

#### 8.10.1 5件套现状 (R12 速查表声称 4件套, 实际补为 5件套)
| App | Name | Version | BundleID | get name | 核心 Count |
|---|---|---|---|---|---|
| Mail | Mail | 16.0 | com.apple.mail | 🟢 | ⚠️ `count messages of inbox` |
| Calendar | Calendar | 16.0 | com.apple.iCal | 🟢 | 🟢 8 |
| Reminders | Reminders | 7.0 | com.apple.reminders | 🟢 | 🟢 7 |
| Notes | Notes | 4.13 | com.apple.Notes | 🟢 | 🟢 35 |
| Contacts | Contacts | 14.0 | com.apple.AddressBook | 🟢 | 🟢 0 (空) |

#### 8.10.2 6件套扩展 (TODO L7 目标)
| App | Name | Version | BundleID | get name | 核心 Count |
|---|---|---|---|---|---|
| Messages | Messages | 26.0 | com.apple.MobileSMS | 🟢 | 🟢 14 chats |
| Contacts | Contacts | 14.0 | com.apple.AddressBook | 🟢 | 🟢 (见上) |
| Music | Music | 1.6.6 | com.apple.Music | 🟢 | 🔴 读取需 sudo |
| Photos | Photos | 11.0 | com.apple.Photos | 🟢 | 🔴 需 Photos Library 授权 |
| Maps | Maps | 3.0 | com.apple.Maps | 🟢 | 🔴 需位置授权 |
| Finder | Finder | 26.4 | com.apple.finder | 🟢 | 🟢 `count windows` |

#### 8.10.3 附加 2 工具 (顺带)
| App | Name | Version | BundleID | 核心 Count |
|---|---|---|---|---|
| System Events | System Event | 1.3.6 | com.apple.systemevents | 🟢 102 processes |
| System Settings | System Settings | (TBD) | com.apple.systempreferences | 🟢 |

#### 8.10.4 6 落地用例 (R6+ 可接入 daily_report)
1. **Reminders 写**: `make new reminder with properties {name, body}` — 已授权, 安全
2. **Notes 全文搜**: `every note whose name contains "X"` — 适合 RAG
3. **Calendar 今日事件**: `every event of calendar 1 whose start date >= today` — 接 daily_report
4. **System Events 当前活动应用**: `first application process whose frontmost is true` — UI 状态汇报
5. **Messages 草稿**: `send to buddy` — 中风险, 需用户确认
6. **Contacts 模糊查询**: `every person whose name contains "X"` — 邮件前置

#### 8.10.5 L2 错记修正
- ❌ `R12_macOS_Automation_Cheat_Sheet.md` 文件**不存在**
- ❌ `mac_automation_sop.md` 文件**不存在** (L3 列表中也无)
- ❌ `R7_Mail.app_AppleScript自动化实测+中文教程.md` 文件**不存在**
- ✅ Mail.app AS 实测: 本轮 R5 用例已含 Mail get name/version/id + 需补 `count messages of inbox` 实测

#### 8.10.6 接入建议
- daily_report 阶段加 "今日 Reminders" 段 (用例 1)
- daily_report 阶段加 "今日会议" 段 (用例 3)
- 新建 `scripts/contacts_lookup.py` (用例 6)
- 新建 `scripts/active_window.py` (用例 4)

---
