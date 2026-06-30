#!/usr/bin/env python3
"""
as_daily_appendix.py
--------------------
Daily Report AppleScript Appendix Generator
R8 落地: 从 macOS Reminders / Calendar 读取当日待办与日程,
输出 JSON 供 daily_report Phase 2 整编时作为附加附录合并。

位置: scripts/as_daily_appendix.py
依赖: 仅 Python 标准库 + macOS osascript
用法:
    python scripts/as_daily_appendix.py reminders         # 人读格式
    python scripts/as_daily_appendix.py calendar --json   # JSON 格式
    python scripts/as_daily_appendix.py both --json       # 合并 JSON

输出 JSON 结构(与 report_data.json 扁平 schema 对齐, additive):
    {
      "as_appendix": {
        "generated_at": "2026-06-24T10:00:00+08:00",
        "reminders": [
          {"name": "...", "due": "...", "priority": "low/normal/high", "list": "..."}
        ],
        "calendar": [
          {"summary": "...", "start": "...", "end": "...", "calendar": "...", "location": "..."}
        ]
      }
    }
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


APP_NAME = "as_daily_appendix"
VERSION = "1.0.0"


def run_applescript(script: str) -> tuple[str, str, int]:
    """执行 AppleScript,返回 (stdout, stderr, rc)。"""
    proc = subprocess.run(
        ["osascript", "-"],
        input=script,
        text=True,
        capture_output=True,
        encoding="utf-8",
    )
    return proc.stdout.strip(), proc.stderr.strip(), proc.returncode


def get_reminders() -> list[dict[str, Any]]:
    """读取 Reminders.app 中未完成的 reminders。

    AppleScript 返回 TSV 文本: 每行一个 reminder,字段按 tab 分隔。
    使用 tab/换行而非逗号/大括号,避免 AppleScript list 文本化时的歧义。
    """
    script = r'''
tell application "Reminders"
    set out to {}
    repeat with r in reminders
        if completed of r is false then
            set rName to name of r
            try
                set rDue to due date of r as string
            on error
                set rDue to ""
            end try
            try
                set rPri to priority of r as string
            on error
                set rPri to "0"
            end try
            try
                set rList to name of container of r
            on error
                set rList to ""
            end try
            set end of out to (rName & "\t" & rDue & "\t" & rPri & "\t" & rList)
        end if
    end repeat
    set txt to ""
    repeat with lineStr in out
        set txt to txt & lineStr & "\n"
    end repeat
    return txt
end tell
'''
    out, err, rc = run_applescript(script)
    if rc != 0:
        raise RuntimeError(f"Reminders AppleScript failed: {err or out}")

    items: list[dict[str, Any]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        while len(parts) < 4:
            parts.append("")
        name, due, pri, list_name = parts[:4]
        # AppleScript priority: 0=none, 1-4=low, 5=normal, 6-9=high (旧版); 新版可能为 integer
        try:
            p = int(pri) if pri.isdigit() else 0
        except ValueError:
            p = 0
        if p == 0:
            level = "normal"
        elif p <= 4:
            level = "low"
        elif p >= 6:
            level = "high"
        else:
            level = "normal"
        items.append({
            "name": name,
            "due": due,
            "priority": level,
            "list": list_name,
        })
    return items


def get_calendar_events() -> list[dict[str, Any]]:
    """读取 Calendar.app 中今日事件。

    同样返回 TSV 文本,每行一个事件,字段按 tab 分隔。
    """
    script = r'''
tell application "Calendar"
    set todayStart to (current date)
    set time of todayStart to 0
    set todayEnd to todayStart + 1 * days
    set out to {}
    repeat with c in calendars
        set calName to title of c
        repeat with e in (every event of c whose start date ≥ todayStart and start date < todayEnd)
            set eSummary to summary of e
            try
                set eStart to start date of e as string
            on error
                set eStart to ""
            end try
            try
                set eEnd to end date of e as string
            on error
                set eEnd to ""
            end try
            try
                set eLoc to location of e
            on error
                set eLoc to ""
            end try
            set end of out to (eSummary & "\t" & eStart & "\t" & eEnd & "\t" & calName & "\t" & eLoc)
        end repeat
    end repeat
    set txt to ""
    repeat with lineStr in out
        set txt to txt & lineStr & "\n"
    end repeat
    return txt
end tell
'''
    out, err, rc = run_applescript(script)
    if rc != 0:
        raise RuntimeError(f"Calendar AppleScript failed: {err or out}")

    items: list[dict[str, Any]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        while len(parts) < 5:
            parts.append("")
        summary, start, end, cal_name, location = parts[:5]
        items.append({
            "summary": summary,
            "start": start,
            "end": end,
            "calendar": cal_name,
            "location": location,
        })
    return items


def build_payload(reminders: list, events: list) -> dict[str, Any]:
    return {
        "as_appendix": {
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "reminders": reminders,
            "calendar": events,
        }
    }


def human_format(reminders: list, events: list) -> str:
    lines: list[str] = []
    lines.append("=" * 50)
    lines.append("Reminders (今日未完成)")
    lines.append("=" * 50)
    if not reminders:
        lines.append("(无)")
    else:
        for r in reminders:
            due = f" [{r['due']}]" if r["due"] else ""
            lines.append(f"• [{r['priority']}] {r['name']}{due} (@{r['list']})")

    lines.append("")
    lines.append("=" * 50)
    lines.append("Calendar (今日事件)")
    lines.append("=" * 50)
    if not events:
        lines.append("(无)")
    else:
        for e in events:
            loc = f" 📍{e['location']}" if e["location"] else ""
            lines.append(f"• {e['summary']} [{e['start']} - {e['end']}]{loc} (@{e['calendar']})")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Daily Report AppleScript Appendix Generator"
    )
    parser.add_argument(
        "command",
        choices=["reminders", "calendar", "both"],
        help="要采集的数据类型",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式(默认人读格式)",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    args = parser.parse_args()

    try:
        reminders = get_reminders() if args.command in ("reminders", "both") else []
        events = get_calendar_events() if args.command in ("calendar", "both") else []
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        if args.command == "reminders":
            payload = {"as_appendix": {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(), "reminders": reminders, "calendar": []}}
        elif args.command == "calendar":
            payload = {"as_appendix": {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(), "reminders": [], "calendar": events}}
        else:
            payload = build_payload(reminders, events)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(human_format(reminders, events))

    return 0


if __name__ == "__main__":
    sys.exit(main())
