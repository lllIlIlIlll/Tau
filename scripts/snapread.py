#!/usr/bin/env python3
"""
snapread.py - 截屏 + 本地 OCR 流水线 (macOS)
==============================================

设计目标
--------
封装 macOS 原生截屏 + Apple Vision OCR, 提供零依赖 CLI:
  1. `snapread snap`        - 交互式选区/窗口截屏 → OCR → 终端输出 / 落盘
  2. `snapread snap-region` - 指定矩形区域截屏 → OCR
  3. `snapread snap-window` - 通过 AppleScript 激活窗口 → 截屏 → OCR
  4. `snapread --help`      - 帮助

设计原则
--------
- **零外部 Python 依赖**: 仅用 stdlib (subprocess, argparse, json, pathlib)
- **复用本机工具链**:
  - `screencapture` (系统自带, -i 交互 / -R 矩形 / -l 窗口ID / -o 无阴影)
  - `shortcuts run` 或 AppleScript 调起 Apple Vision (`/usr/bin/python3 -m ...` 不行, 用 osascript 走 Vision.framework)
  - 备选: `tesseract` (若 homebrew 已装, 见 l3 §8.4)
- **管道化**: PNG → OCR 文本, 中间不落盘可走 - (stdout)
- **错误友好**: 截屏/OCR 失败返回非零退出码 + stderr 说明

为什么需要 snapread (价值公式)
------------------------------
- **AI 训练数据无法覆盖**: macOS 截屏 + Vision OCR 流程是端到端本地 CLI,
  现有 AI 模型无法替代"对着屏幕任何矩形区域一键 OCR"
- **持久收益**:
  - 替代 ljqCtrl_sop 中 pyautogui 截图失败的场景
  - 接入 daily_report (跨日模板复盘、滑动验证码)
  - 接入 web_setup_sop (DOM 不可见时抓控件文本)
  - 集成 vision_sop 形成 "截图 → OCR → 输入" 全闭环

验收 (待 code_run 修复后实测)
-----------------------------
1. `python3 snapread.py --help` 退出码 0, 输出子命令列表
2. `python3 snapread.py snap-region 100,100,800,600` 在 macOS 上:
   - 调 `screencapture -R 100,100,800,600 -o /tmp/x.png`
   - 调 `shortcuts run "Extract Text from Image"` 或 osascript Vision
   - 输出 ≥80% 准确率文字
3. `python3 snapread.py snap` 交互模式可截屏当前选区

依赖 (系统级, 无需 pip install)
-------------------------------
- macOS 12+ (含 Apple Vision.framework)
- `screencapture` 系统自带 (/usr/sbin/screencapture)
- 可选: homebrew tesseract (`brew install tesseract`) 走 --engine tesseract
- 可选: macOS Shortcuts 创建一个 "Extract Text from Image" (Image → Extract Text)
  - 步骤: Shortcuts app → + → "Extract Text from Image" → Run from CLI: `shortcuts run "Extract Text from Image" --input-path <png>`

作者
----
- MiniMax-M3 自主智能体 (R5 2026-06-24)
- 基于 ../memory/l3_capability_inventory.md v1.1/v1.2 screencapture+Vision 标注
- 替代/补充 ../memory/ljqCtrl_sop.md 的 pyautogui 截图方案

历史
----
- 2026-06-24: 初版 (R5), 含 4 个子命令 + 2 个 OCR 引擎
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple


# ---------- 核心工具函数 ----------

def screencapture_region(x: int, y: int, w: int, h: int, out_path: Path) -> Tuple[bool, str]:
    """截屏指定矩形区域。

    使用 `screencapture -R x,y,w,h -o <path>` (macOS 12+)
    -o: 截屏不含窗口阴影
    """
    cmd = ["/usr/sbin/screencapture", "-R", f"{x},{y},{w},{h}", "-o", str(out_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False, f"screencapture 失败 (rc={result.returncode}): {result.stderr}"
        if not out_path.exists() or out_path.stat().st_size == 0:
            return False, "screencapture 成功但未生成文件 (可能用户取消)"
        return True, str(out_path)
    except FileNotFoundError:
        return False, "screencapture 不存在 (非 macOS?)"
    except subprocess.TimeoutExpired:
        return False, "screencapture 超时 (10s)"


def screencapture_interactive(out_path: Path) -> Tuple[bool, str]:
    """交互式截屏 (鼠标选区或单窗)。"""
    cmd = ["/usr/sbin/screencapture", "-i", "-o", str(out_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return False, f"screencapture 交互失败 (rc={result.returncode}): {result.stderr}"
        if not out_path.exists() or out_path.stat().st_size == 0:
            return False, "交互截屏取消 (用户按 ESC 或未选区)"
        return True, str(out_path)
    except subprocess.TimeoutExpired:
        return False, "交互截屏超时 (60s)"


def screencapture_window(window_title: str, out_path: Path) -> Tuple[bool, str]:
    """截屏指定标题的窗口。先用 AppleScript 找窗口 ID, 再 screencapture -l <wid>。"""
    # AppleScript: 获取第一个匹配标题的窗口 ID
    as_script = f'''
    tell application "System Events"
        set procs to (every process whose name is not "loginwindow")
        repeat with p in procs
            try
                set wins to (every window of p whose name contains "{window_title}")
                if (count of wins) > 0 then
                    return id of front window of p
                end if
            end try
        end repeat
        return -1
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", as_script],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0 or not result.stdout.strip().lstrip('-').isdigit():
            return False, f"未找到窗口 (title 含 '{window_title}'): {result.stderr.strip()}"
        wid = result.stdout.strip()
        cmd = ["/usr/sbin/screencapture", "-l", wid, "-o", str(out_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False, f"screencapture 窗口失败: {result.stderr}"
        return True, str(out_path)
    except subprocess.TimeoutExpired:
        return False, "AppleScript 或 screencapture 超时"


# ---------- OCR 引擎 ----------

def ocr_via_shortcuts(png_path: Path) -> Tuple[bool, str]:
    """OCR 引擎 A: macOS Shortcuts 'Extract Text from Image' (Apple Vision)。"""
    # 用户需先在 Shortcuts app 创建一个名为 "Extract Text from Image" 的快捷指令
    # 步骤: Shortcuts → + → 搜索 "Extract Text from Image" → 添加 → 保存
    cmd = ["shortcuts", "run", "Extract Text from Image", "--input-path", str(png_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return False, f"shortcuts 失败 (rc={result.returncode}): {result.stderr.strip()}"
        return True, result.stdout
    except FileNotFoundError:
        return False, "shortcuts CLI 不存在 (需 macOS 12+)"
    except subprocess.TimeoutExpired:
        return False, "shortcuts OCR 超时 (30s)"


def ocr_via_tesseract(png_path: Path, lang: str = "eng+chi_sim") -> Tuple[bool, str]:
    """OCR 引擎 B: Tesseract (homebrew, 需 brew install tesseract tesseract-lang)。"""
    cmd = ["tesseract", str(png_path), "-", "-l", lang]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return False, f"tesseract 失败 (rc={result.returncode}): {result.stderr.strip()}"
        return True, result.stdout
    except FileNotFoundError:
        return False, "tesseract 未安装 (brew install tesseract tesseract-lang)"
    except subprocess.TimeoutExpired:
        return False, "tesseract OCR 超时 (30s)"


def ocr_via_vision_osascript(png_path: Path) -> Tuple[bool, str]:
    """OCR 引擎 C: 直接 AppleScript 调 Vision.framework (无需 Shortcuts)。"""
    # 注意: 此方法需要 macOS 13+, 且 Vision 不能直接通过 AppleScript 调, 实际需 Swift
    # 此处保留接口但返回 false 提示用户用 Shortcuts
    as_script = f'''
    use framework "Vision"
    use framework "Foundation"
    use scripting additions

    set theImage to POSIX file "{png_path}" as alias
    set theURL to current application's NSURL's fileURLWithPath:(POSIX path of theImage)
    set theRequest to current application's VNRecognizeTextRequest's alloc()'s init()
    theRequest's setRecognitionLevel:(current application's VNRequestTextRecognitionLevelAccurate)
    theRequest's setUsesLanguageCorrection:true
    theRequest's setRecognitionLanguages:(current application's NSArray's arrayWithObject:"zh-Hans")

    set theHandler to current application's VNImageRequestHandler's alloc()'s initWithURL:theURL options:(current application's NSDictionary's dictionary())
    theHandler's performRequests:((current application's NSArray's arrayWithObject:theRequest)) |error|:(missing value)
    set theResults to theRequest's results()
    set theText to ""
    repeat with anObs in theResults
        set theText to theText & (anObs's topCandidates:1's firstObject()'s |string|() as text) & linefeed
    end repeat
    return theText
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", as_script],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return False, f"Vision OCR 失败: {result.stderr.strip()[:200]}"
        return True, result.stdout
    except subprocess.TimeoutExpired:
        return False, "Vision OCR 超时 (30s)"


OCR_ENGINES = {
    "shortcuts": ("macOS Shortcuts (Apple Vision, 需先创建 'Extract Text from Image')", ocr_via_shortcuts),
    "tesseract": ("Tesseract (homebrew, brew install tesseract tesseract-lang)", ocr_via_tesseract),
    "vision":    ("Apple Vision via AppleScript (macOS 13+, 实验性)", ocr_via_vision_osascript),
}


# ---------- CLI 子命令 ----------

def cmd_snap(args) -> int:
    """交互式截屏 → OCR。"""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_png = Path(f.name)
    try:
        ok, msg = screencapture_interactive(tmp_png)
        if not ok:
            print(f"[snap] 失败: {msg}", file=sys.stderr)
            return 1
        print(f"[snap] 已截屏: {msg}", file=sys.stderr)
        return _run_ocr(tmp_png, args)
    finally:
        if not args.keep and tmp_png.exists():
            tmp_png.unlink()


def cmd_snap_region(args) -> int:
    """截屏矩形区域 → OCR。x,y,w,h 像素。"""
    try:
        x, y, w, h = (int(v) for v in args.geometry.split(","))
    except ValueError:
        print(f"[snap-region] 格式错误: {args.geometry} (期望 x,y,w,h)", file=sys.stderr)
        return 2
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_png = Path(f.name)
    try:
        ok, msg = screencapture_region(x, y, w, h, tmp_png)
        if not ok:
            print(f"[snap-region] 失败: {msg}", file=sys.stderr)
            return 1
        print(f"[snap-region] 已截屏: {msg}", file=sys.stderr)
        return _run_ocr(tmp_png, args)
    finally:
        if not args.keep and tmp_png.exists():
            tmp_png.unlink()


def cmd_snap_window(args) -> int:
    """截屏指定标题的窗口 → OCR。"""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_png = Path(f.name)
    try:
        ok, msg = screencapture_window(args.title, tmp_png)
        if not ok:
            print(f"[snap-window] 失败: {msg}", file=sys.stderr)
            return 1
        print(f"[snap-window] 已截屏: {msg}", file=sys.stderr)
        return _run_ocr(tmp_png, args)
    finally:
        if not args.keep and tmp_png.exists():
            tmp_png.unlink()


def _run_ocr(png_path: Path, args) -> int:
    """公共 OCR 流程: 选引擎 → 输出。"""
    engine = args.engine
    if engine == "auto":
        # 优先 shortcuts > vision > tesseract
        for eng in ("shortcuts", "vision", "tesseract"):
            ok, text = OCR_ENGINES[eng][1](png_path)
            if ok:
                engine_name = OCR_ENGINES[eng][0]
                print(f"[ocr] 引擎: {engine_name}", file=sys.stderr)
                return _emit(text, args, png_path)
        print("[ocr] 所有引擎失败", file=sys.stderr)
        return 3
    elif engine in OCR_ENGINES:
        ok, text = OCR_ENGINES[engine][1](png_path)
        if not ok:
            print(f"[ocr] {engine} 失败: {text}", file=sys.stderr)
            return 1
        return _emit(text, args, png_path)
    else:
        print(f"[ocr] 未知引擎: {engine} (可选: auto, {', '.join(OCR_ENGINES)})", file=sys.stderr)
        return 2


def _emit(text: str, args, png_path: Path) -> int:
    """输出 OCR 结果到 stdout 或文件。"""
    if args.out:
        out = Path(args.out)
        out.write_text(text, encoding="utf-8")
        print(f"[emit] 写入: {out} ({len(text)} 字符)", file=sys.stderr)
    else:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    if args.save_image:
        # 保留截屏供调试
        import shutil
        dest = Path(args.save_image)
        shutil.copy(png_path, dest)
        print(f"[emit] 截屏已保留: {dest}", file=sys.stderr)
    return 0


# ---------- main ----------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="snapread",
        description="截屏 + 本地 OCR 流水线 (macOS, 零 Python 依赖)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  snapread snap                          # 交互选区截屏 → OCR
  snapread snap-region 100,100,800,600   # 截屏指定矩形
  snapread snap-window "Chrome"          # 截屏标题含 Chrome 的窗口
  snapread snap -e tesseract -o out.txt   # 用 tesseract 引擎, 落盘
  snapread snap --keep --save-image x.png # 保留截屏文件

引擎选择:
  auto      按 shortcuts > vision > tesseract 顺序尝试 (默认)
  shortcuts macOS Shortcuts 'Extract Text from Image' (Apple Vision)
  vision    Apple Vision via AppleScript (实验性, macOS 13+)
  tesseract Tesseract (brew install tesseract tesseract-lang)
        """,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # 公共参数
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-e", "--engine", default="auto",
                        help="OCR 引擎 (auto/shortcuts/vision/tesseract)")
    common.add_argument("-o", "--out", default=None, help="输出到文件 (默认 stdout)")
    common.add_argument("--keep", action="store_true", help="保留临时截屏文件")
    common.add_argument("--save-image", default=None, metavar="PATH",
                        help="额外保存截屏到此路径")

    sub.add_parser("snap", parents=[common], help="交互式截屏 → OCR")
    sr = sub.add_parser("snap-region", parents=[common], help="截屏矩形区域 → OCR")
    sr.add_argument("geometry", help="x,y,w,h (像素)")
    sw = sub.add_parser("snap-window", parents=[common], help="截屏指定标题窗口 → OCR")
    sw.add_argument("title", help="窗口标题 (含匹配)")

    args = parser.parse_args()

    dispatch = {
        "snap": cmd_snap,
        "snap-region": cmd_snap_region,
        "snap-window": cmd_snap_window,
    }
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
