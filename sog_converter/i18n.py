"""Bilingual (Chinese / English) string table and language selection.

Language priority, highest first:

1. ``--lang zh|en`` passed on the command line
2. ``SOG_LANG`` environment variable
3. OS display language (Windows UI language, then POSIX locale)
4. English fallback

The module is deliberately tiny and dependency free so both ``core.py``
and ``gui.py`` can use it without importing tkinter.
"""

from __future__ import annotations

import locale
import os
from typing import Dict, Optional

ZH = "zh"
EN = "en"
AUTO = "auto"
SUPPORTED = (ZH, EN)

STRINGS: Dict[str, Dict[str, str]] = {
    "zh": {
        # ---- core ----
        "err_target_positive": "目标点数必须大于 0",
        "err_percent_range": "保留百分比必须在 1 到 99 之间",
        "err_unknown_mode": "未知的压缩模式: {mode}",
        "err_webp_range": "WebP 压缩强度必须在 0 到 9 之间",
        "err_output_required": "请指定输出目录",
        "err_launch": "无法启动 splat-transform: {error}",
        "err_exit_code": "命令退出码 {code}",
        "err_no_intermediate": "减点步骤未生成中间 PLY 文件",
        "err_empty_output": "SOG 输出为空或不存在",
        "skip_same_file": "输出与输入为同一文件",
        "skip_exists": "目标文件已存在（未勾选覆盖）",
        "done": "完成 -> {name} ({size:.2f} MB)",
        "deleted": "；原文件已删除",
        "delete_failed": "；原文件删除失败：{error}",
        "warn_replace": "  警告: 覆盖源文件模式已启用",
        "log_step1": "[1/2] 减点 -> {value}",
        "log_step2": "[2/2] 编码 SOG",
        "log_step_single": "[1/1] 编码 SOG",
        "log_job": "--- [{index}/{total}] {path} ---",
        "log_result": "  [{status}] {message}",
        # ---- gui: chrome ----
        "app_title": "3DGS → SOG Converter",
        "cli_detecting": "检测工具中…",
        "btn_locate_tool": "定位工具…",
        "lbl_format": "导出格式:",
        "fmt_sog": "压缩 SOG (.sog)",
        "fmt_compressed_ply": "压缩 PLY (.compressed.ply)",
        "dlg_locate_tool": "选择 splat-transform 可执行文件",
        "dlg_tool_filetypes": "可执行文件",
        "log_cli_set": "已指定转换工具: {cli}",
        "cli_missing": "✗ 未找到 splat-transform",
        "cli_ok": "✓ {version}",
        "frame_input": " 1. 输入（文件或文件夹） ",
        "frame_output": " 2. 输出 ",
        "frame_options": " 3. 压缩选项 ",
        "frame_log": " 日志 ",
        "btn_add_files": "添加文件…",
        "btn_add_folder": "添加文件夹…",
        "btn_remove": "移除选中",
        "btn_clear": "清空",
        "chk_recursive": "包含子文件夹",
        "lbl_output_dir": "输出目录:",
        "btn_browse": "浏览…",
        "btn_open": "打开",
        "chk_overwrite": "覆盖已存在的输出文件",
        "chk_replace": "覆盖源文件：输出到源目录同名 .sog，成功后删除原文件",
        "lbl_decimate": "压缩点数:",
        "radio_keep": "保持原样",
        "radio_count": "指定数量",
        "radio_percent": "保留百分比",
        "chk_filter": "剔除极低透明度高斯 (opacity > 0.02，仅在减点时生效)",
        "lbl_webp": "WebP 压缩强度 (0–9):",
        "chk_cpu": "强制 CPU 压缩（无可用 GPU 时勾选）",
        "btn_start": "开始转换",
        "btn_cancel": "取消",
        "status_ready": "就绪",
        "status_running": "转换中…",
        "status_cancelling": "取消中…",
        "status_cancelled": "已取消",
        "status_error": "出错",
        "status_done": "完成",
        "time_format": "已用 {elapsed} · 剩余 {remain}",
        "time_idle": "已用 --:-- · 剩余 --:--",
        # ---- gui: dialogs ----
        "dlg_open_files": "选择 3DGS 文件",
        "dlg_filetypes": "3DGS 文件",
        "dlg_all_files": "所有文件",
        "dlg_open_folder": "选择包含 3DGS 文件的文件夹",
        "dlg_output": "选择输出目录",
        "info_output_missing": "输出目录尚不存在。",
        "err_no_cli": "未找到 splat-transform，请先安装（见 README）。",
        "warn_no_input": "请先添加文件或文件夹。",
        "warn_no_sources": "未找到可转换的 .ply / .spz / .splat / .ksplat 文件。",
        "err_no_points": "请填写目标点数或保留百分比",
        "err_points_int": "点数与百分比必须是整数",
        "warn_replace_body": (
            "「覆盖源文件」会把转换结果写到原文件所在目录，并在转换成功后\n"
            "直接删除原始文件（不可恢复）。\n\n"
            "建议先对少量文件试用，并保留原始素材备份。\n\n确定启用吗？"
        ),
        "confirm_replace_body": (
            "即将对 {count} 个文件执行「覆盖源文件」，原始文件会被直接删除（不可恢复）：\n\n"
            "{preview}{more}\n\n确定继续吗？"
        ),
        "confirm_more": "… 共 {count} 个文件",
        "warn_some_failed": "完成，但有 {failed} 个任务失败，请查看日志。",
        "info_all_skipped": "没有文件被转换（目标文件均已存在）。\n可勾选「覆盖已存在的输出文件」。",
        # ---- gui: log ----
        "log_hint": "提示: 首次使用请先安装 Node.js 与 @playcanvas/splat-transform（见 README）。",
        "log_cli_missing": (
            "错误: 未找到 splat-transform。请执行 npm install -g @playcanvas/splat-transform，"
            "或设置环境变量 SPLAT_TRANSFORM 指向可执行文件。"
        ),
        "log_cli_found": "已找到转换工具: {cli} ({version})",
        "log_added_files": "已添加 {count} 个文件",
        "log_added_folder": "已添加文件夹: {path}",
        "log_start": "开始转换，共 {count} 个任务。",
        "log_cancel_request": "收到取消请求，等待当前步骤结束…",
        "log_cancelled": "已取消。",
        "log_error": "错误: {message}",
        "log_finish": "全部完成：成功 {converted}，跳过 {skipped}，失败 {failed}，共 {total}。",
        # ---- app ----
        "err_tkinter": (
            "错误：当前 Python 未包含 tkinter。\n"
            "  Windows / macOS：请从 python.org 安装官方版本并勾选 tcl/tk。\n"
            "  Linux：请安装 python3-tk（Debian/Ubuntu）或对应发行版软件包。\n"
        ),
        "arg_help": "界面语言：auto（跟随系统）、zh（中文）、en（英文）",
    },
    "en": {
        # ---- core ----
        "err_target_positive": "Target splat count must be greater than 0",
        "err_percent_range": "Keep percentage must be between 1 and 99",
        "err_unknown_mode": "Unknown compression mode: {mode}",
        "err_webp_range": "WebP effort must be between 0 and 9",
        "err_output_required": "Please choose an output directory",
        "err_launch": "Failed to start splat-transform: {error}",
        "err_exit_code": "Command exited with code {code}",
        "err_no_intermediate": "Decimation step produced no intermediate PLY file",
        "err_empty_output": "SOG output is empty or missing",
        "skip_same_file": "Output and input are the same file",
        "skip_exists": "Target already exists (overwrite is off)",
        "done": "Done -> {name} ({size:.2f} MB)",
        "deleted": "; original file deleted",
        "delete_failed": "; failed to delete original file: {error}",
        "warn_replace": "  Warning: replace-source mode is enabled",
        "log_step1": "[1/2] Decimate -> {value}",
        "log_step2": "[2/2] Encode SOG",
        "log_step_single": "[1/1] Encode SOG",
        "log_job": "--- [{index}/{total}] {path} ---",
        "log_result": "  [{status}] {message}",
        # ---- gui: chrome ----
        "app_title": "3DGS → SOG Converter",
        "cli_detecting": "Detecting tool…",
        "btn_locate_tool": "Locate tool…",
        "lbl_format": "Export format:",
        "fmt_sog": "Compressed SOG (.sog)",
        "fmt_compressed_ply": "Compressed PLY (.compressed.ply)",
        "dlg_locate_tool": "Select the splat-transform executable",
        "dlg_tool_filetypes": "Executables",
        "log_cli_set": "Converter set: {cli}",
        "cli_missing": "✗ splat-transform not found",
        "cli_ok": "✓ {version}",
        "frame_input": " 1. Input (files or folders) ",
        "frame_output": " 2. Output ",
        "frame_options": " 3. Compression options ",
        "frame_log": " Log ",
        "btn_add_files": "Add files…",
        "btn_add_folder": "Add folder…",
        "btn_remove": "Remove selected",
        "btn_clear": "Clear",
        "chk_recursive": "Include subfolders",
        "lbl_output_dir": "Output folder:",
        "btn_browse": "Browse…",
        "btn_open": "Open",
        "chk_overwrite": "Overwrite existing output files",
        "chk_replace": "Replace source: write a same-named .sog next to the source, then delete the original file",
        "lbl_decimate": "Splat count:",
        "radio_keep": "Keep all",
        "radio_count": "Target count",
        "radio_percent": "Keep percentage",
        "chk_filter": "Drop near-invisible Gaussians (opacity > 0.02, decimation only)",
        "lbl_webp": "WebP effort (0–9):",
        "chk_cpu": "Force CPU compression (use when no GPU is available)",
        "btn_start": "Start conversion",
        "btn_cancel": "Cancel",
        "status_ready": "Ready",
        "status_running": "Converting…",
        "status_cancelling": "Cancelling…",
        "status_cancelled": "Cancelled",
        "status_error": "Error",
        "status_done": "Done",
        "time_format": "Elapsed {elapsed} · Remaining {remain}",
        "time_idle": "Elapsed --:-- · Remaining --:--",
        # ---- gui: dialogs ----
        "dlg_open_files": "Select 3DGS files",
        "dlg_filetypes": "3DGS files",
        "dlg_all_files": "All files",
        "dlg_open_folder": "Select a folder containing 3DGS files",
        "dlg_output": "Select output folder",
        "info_output_missing": "The output folder does not exist yet.",
        "err_no_cli": "splat-transform not found. Install it first (see README).",
        "warn_no_input": "Please add files or folders first.",
        "warn_no_sources": "No convertible .ply / .spz / .splat / .ksplat files found.",
        "err_no_points": "Please enter a target count or a keep percentage",
        "err_points_int": "Counts and percentages must be integers",
        "warn_replace_body": (
            "Replace-source mode writes the output next to each source file and,\n"
            "after a successful conversion, permanently deletes the original file\n"
            "(not recoverable).\n\n"
            "Try it on a few files first and keep a separate backup of your source assets.\n\nContinue?"
        ),
        "confirm_replace_body": (
            "Replace-source mode will run on {count} file(s). Originals will be permanently deleted (not recoverable):\n\n"
            "{preview}{more}\n\nContinue?"
        ),
        "confirm_more": "… {count} files total",
        "warn_some_failed": "Finished, but {failed} task(s) failed. Check the log.",
        "info_all_skipped": "Nothing was converted (all targets already exist).\nEnable 'Overwrite existing output files' to replace them.",
        # ---- gui: log ----
        "log_hint": "Hint: first-time setup requires Node.js and @playcanvas/splat-transform (see README).",
        "log_cli_missing": (
            "Error: splat-transform not found. Run npm install -g @playcanvas/splat-transform, "
            "or set the SPLAT_TRANSFORM environment variable to the executable."
        ),
        "log_cli_found": "Converter found: {cli} ({version})",
        "log_added_files": "Added {count} file(s)",
        "log_added_folder": "Added folder: {path}",
        "log_start": "Starting {count} task(s).",
        "log_cancel_request": "Cancel requested, waiting for the current step to finish…",
        "log_cancelled": "Cancelled.",
        "log_error": "Error: {message}",
        "log_finish": "Finished: {converted} converted, {skipped} skipped, {failed} failed, {total} total.",
        # ---- app ----
        "err_tkinter": (
            "Error: this Python build has no tkinter.\n"
            "  Windows / macOS: install the official python.org build with tcl/tk enabled.\n"
            "  Linux: install python3-tk (Debian/Ubuntu) or the equivalent package.\n"
        ),
        "arg_help": "UI language: auto (follow OS), zh (Chinese), en (English)",
    },
}

_current = EN
_explicit: Optional[str] = None


def normalize(language: str) -> Optional[str]:
    """Map zh / zh-CN / zh_TW / en / en-US ... to 'zh' or 'en'."""
    value = (language or "").strip().lower().replace("_", "-")
    if value.startswith("zh"):
        return ZH
    if value.startswith("en"):
        return EN
    return None


def detect_system_language() -> str:
    """Best-effort OS language detection."""
    override = os.environ.get("SOG_LANG", "").strip()
    if override:
        detected = normalize(override)
        if detected:
            return detected

    if os.name == "nt":
        try:
            import ctypes

            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0xFFFF
            # Chinese (Simplified / Traditional / Singapore / Macau / Hong Kong, China)
            if lang_id in (0x0804, 0x0404, 0x0C04, 0x1004, 0x1404):
                return ZH
            if lang_id:
                return EN
        except (AttributeError, OSError):
            pass

    for key in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        detected = normalize(os.environ.get(key, ""))
        if detected:
            return detected
    try:
        detected = normalize(locale.getlocale()[0] or "")
        if detected:
            return detected
    except (ValueError, TypeError):
        pass
    return EN


def set_language(language: str = AUTO) -> str:
    """Set active language. Accepts auto / zh / en (and locale-like variants)."""
    global _current, _explicit
    if language == AUTO or not language:
        _current = detect_system_language()
        _explicit = None
    else:
        selected = normalize(language)
        if selected is None:
            raise ValueError(f"Unsupported language: {language}")
        _current = selected
        _explicit = selected
    return _current


def get_language() -> str:
    return _current


def get_explicit_language() -> Optional[str]:
    """Return the command-line override, if any (used in the log)."""
    return _explicit


def t(key: str, **kwargs) -> str:
    """Translate a key, falling back to English and finally to the key itself."""
    table = STRINGS.get(_current, STRINGS[EN])
    text = table.get(key) or STRINGS[EN].get(key) or key
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return text


def available_keys() -> set:
    return set(STRINGS[ZH]) | set(STRINGS[EN])
