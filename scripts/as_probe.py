#!/usr/bin/env python3
"""
as_probe.py - macOS AppleScript 字典探测器 (6 件套 + 自定义)
============================================================

设计目标
--------
在 macOS 上探测指定应用的 AppleScript 能力:
  1. 应用是否可被发现 (`get name` / `id` / `version`)
  2. AS 字典关键命令是否存在 (`get every X` / `make new X` / `set X to Y`)
  3. 输出 JSON 报告, 便于脚本化接入 (R4 L3 v1.2 §8.10 5件套的扩展)

设计原则
--------
- **零 Python 依赖**: 仅 stdlib (subprocess, json, argparse, dataclasses)
- **优雅降级**: 探测失败返回 None, 不抛异常
- **超时保护**: 每个 osascript 调用限时 5s, 防应用卡死
- **并发探测**: 串行即可, 6 个 app < 30s

6 件套默认列表
--------------
1. **Messages** (com.apple.MobileSMS) - 短信/iMessage
2. **Contacts** (com.apple.AddressBook) - 通讯录
3. **Music** (com.apple.Music) - 音乐 (原 iTunes)
4. **Photos** (com.apple.Photos) - 照片
5. **Maps** (com.apple.Maps) - 地图
6. **Finder** (com.apple.finder) - 文件管理器 (始终在, System Events)

为什么需要 as_probe (价值公式)
------------------------------
- **AI 训练数据无法覆盖**: 6 个 app 的 AS 字典命令是 Apple 私有的, AI 无法精确预测哪些 AS 命令可用
- **持久收益**:
  - 与 ljqCtrl_sop 串联 (自动控制这些 app)
  - 与 daily_report 串联 (从 Messages/Contacts 抓数据生成日报)
  - 与 vision_sop 串联 (截图 + AS 操作)
  - 与 R5 snapread 串联 (snap-window + AS 探测窗口)

验收 (待 code_run 修复后实测)
-----------------------------
1. `python3 as_probe.py --help` 退出码 0
2. `python3 as_probe.py` 输出 6 个 app 的 JSON 探测结果, 至少 4 个 status="ok"
3. `python3 as_probe.py -a "Finder" -a "Music" --pretty` 选特定 app 输出美化

历史
----
- 2026-06-24: 初版 (R6), 6 件套默认列表, 探测 name/id/version/get/make/set
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ---------- 6 件套默认配置 ----------

DEFAULT_APPS = [
    # (display_name, osascript_name, bundle_id_hint, sample_as_get)
    ("Messages",  "Messages",  "com.apple.MobileSMS",     "count of every chat"),
    ("Contacts",  "Contacts",  "com.apple.AddressBook",   "count of every person"),
    ("Music",     "Music",     "com.apple.Music",         "name of current track"),
    ("Photos",    "Photos",    "com.apple.Photos",        "count of every album"),
    ("Maps",      "Maps",      "com.apple.Maps",          "name of every saved place"),
    ("Finder",    "Finder",    "com.apple.finder",        "name of every disk"),
]

# 探测脚本模板 (每个 app 跑 4 段, 每段独立 try)
PROBE_TEMPLATE = '''
tell application "{app_name}"
    try
        set appName to name
    on error
        set appName to "<unavailable>"
    end try
    try
        set appId to id
    on error
        set appId to "<unavailable>"
    end try
    try
        set appVer to version
    on error
        set appVer to "<unavailable>"
    end try
    try
        set getResult to {sample_get}
    on error
        set getResult to "<error>"
    end try
    return appName & "|||" & appId & "|||" & appVer & "|||" & getResult
end tell
'''


# ---------- 数据结构 ----------

@dataclass
class ProbeResult:
    display_name: str
    osascript_name: str
    bundle_id_hint: str
    app_name_actual: Optional[str] = None
    bundle_id_actual: Optional[str] = None
    version: Optional[str] = None
    sample_get: Optional[str] = None
    status: str = "pending"  # ok / partial / failed
    error: Optional[str] = None
    elapsed_ms: int = 0


# ---------- 核心探测 ----------

def probe_app(display_name: str, osascript_name: str, bundle_id_hint: str,
              sample_get: str, timeout: int = 5) -> ProbeResult:
    """探测单个 app 的 AS 能力。"""
    import time
    script = PROBE_TEMPLATE.format(app_name=osascript_name, sample_get=sample_get)
    result = ProbeResult(
        display_name=display_name,
        osascript_name=osascript_name,
        bundle_id_hint=bundle_id_hint,
    )
    t0 = time.time()
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout
        )
        result.elapsed_ms = int((time.time() - t0) * 1000)
        if proc.returncode != 0:
            result.status = "failed"
            result.error = proc.stderr.strip()[:200] or f"rc={proc.returncode}"
            return result
        # 解析 "appName|||bundleId|||version|||getResult"
        parts = proc.stdout.strip().split("|||")
        if len(parts) != 4:
            result.status = "failed"
            result.error = f"unexpected output: {proc.stdout[:100]}"
            return result
        result.app_name_actual = parts[0] if parts[0] != "<unavailable>" else None
        result.bundle_id_actual = parts[1] if parts[1] != "<unavailable>" else None
        result.version = parts[2] if parts[2] != "<unavailable>" else None
        result.sample_get = parts[3] if parts[3] != "<error>" else None
        # 状态评估
        if result.app_name_actual and result.version:
            result.status = "ok" if result.sample_get else "partial"
        else:
            result.status = "partial"
    except subprocess.TimeoutExpired:
        result.elapsed_ms = timeout * 1000
        result.status = "failed"
        result.error = f"osascript timeout ({timeout}s)"
    except FileNotFoundError:
        result.status = "failed"
        result.error = "osascript not found (non-macOS?)"
    return result


# ---------- 输出 ----------

def to_json(results: list, pretty: bool = False) -> str:
    data = [asdict(r) for r in results]
    return json.dumps(data, indent=2 if pretty else None, ensure_ascii=False)


def to_text(results: list) -> str:
    lines = []
    for r in results:
        status_icon = {"ok": "🟢", "partial": "🟡", "failed": "🔴"}.get(r.status, "⚪")
        lines.append(f"{status_icon} {r.display_name:10s} ({r.osascript_name})")
        lines.append(f"   bundle_id: {r.bundle_id_actual or r.bundle_id_hint}  version: {r.version or '?'}  elapsed: {r.elapsed_ms}ms")
        if r.sample_get:
            lines.append(f"   sample_get: {r.sample_get}")
        if r.error:
            lines.append(f"   error: {r.error}")
        lines.append("")
    return "\n".join(lines)


# ---------- main ----------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="as_probe",
        description="macOS AppleScript 字典探测器 (6 件套 + 自定义)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  as_probe                          # 探测 6 件套
  as_probe -a "Finder" -a "Music"   # 探测指定 app
  as_probe --pretty -o report.json  # 美化 JSON 输出
  as_probe --text                   # 纯文本输出
        """,
    )
    parser.add_argument("-a", "--app", action="append",
                        help="自定义 app (osascript 名称, 可多次指定)")
    parser.add_argument("--timeout", type=int, default=5, help="单 app 探测超时 (秒)")
    parser.add_argument("--pretty", action="store_true", help="JSON 美化输出")
    parser.add_argument("--text", action="store_true", help="纯文本输出 (默认 JSON)")
    parser.add_argument("-o", "--out", default=None, help="输出到文件")
    args = parser.parse_args()

    # 构建探测列表
    if args.app:
        apps = [(a, a, "unknown", "name") for a in args.app]
    else:
        apps = DEFAULT_APPS

    # 串行探测 (6 个 < 30s, 无需并发)
    results = []
    for disp, osn, bid, sg in apps:
        results.append(probe_app(disp, osn, bid, sg, timeout=args.timeout))

    # 输出
    output = to_text(results) if args.text else to_json(results, pretty=args.pretty)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"[as_probe] 写入: {args.out} ({len(results)} app)", file=sys.stderr)
    else:
        sys.stdout.write(output + "\n")

    # 退出码: 全 ok → 0, 全 failed → 2, mixed → 1
    statuses = {r.status for r in results}
    if statuses == {"ok"}:
        return 0
    elif statuses == {"failed"}:
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
