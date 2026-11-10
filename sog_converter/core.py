"""Core conversion logic for the 3DGS -> SOG converter.

This module has no GUI dependency. It shells out to the open source
`@playcanvas/splat-transform` CLI and can be imported by other tools or tests.

All file writes go through a temporary `.sog` file followed by an atomic
``os.replace`` so a failed conversion never damages an existing output.
"""

from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence

__all__ = [
    "Cancelled",
    "ConversionError",
    "Job",
    "Options",
    "Report",
    "Result",
    "cli_version",
    "collect_inputs",
    "find_cli",
    "plan_jobs",
    "run_conversion",
]

INPUT_SUFFIXES = {".ply", ".spz", ".splat", ".ksplat"}
OUTPUT_SUFFIX = ".sog"
TMP_MARKER = "__tmp__"

LogFn = Callable[[str], None]
CancelFn = Callable[[], None]


class ConversionError(RuntimeError):
    """A conversion step failed."""


class Cancelled(Exception):
    """Raised by the cancel callback to abort a running conversion."""


def _noop(_: str) -> None:
    return None


def _never_cancel() -> None:
    return None


@dataclass
class Options:
    """All settings exposed by the GUI."""

    output_dir: Optional[Path] = None
    overwrite_existing: bool = False
    replace_source: bool = False
    decimate_mode: str = "keep"  # keep | count | percent
    decimate_value: int = 400000
    filter_low_opacity: bool = True
    webp_effort: int = 6
    use_cpu: bool = False

    def decimate_arg(self) -> Optional[str]:
        if self.decimate_mode == "keep":
            return None
        if self.decimate_mode == "count":
            value = int(self.decimate_value)
            if value <= 0:
                raise ValueError("目标点数必须大于 0")
            return str(value)
        if self.decimate_mode == "percent":
            value = int(self.decimate_value)
            if not 1 <= value <= 99:
                raise ValueError("保留百分比必须在 1 到 99 之间")
            return f"{value}%"
        raise ValueError(f"未知的压缩模式: {self.decimate_mode}")

    def validate(self) -> None:
        if not 0 <= int(self.webp_effort) <= 9:
            raise ValueError("WebP 压缩强度必须在 0 到 9 之间")
        self.decimate_arg()
        if not self.replace_source and self.output_dir is None:
            raise ValueError("请指定输出目录")
        if not self.replace_source:
            self.output_dir = Path(self.output_dir).expanduser()


@dataclass
class Job:
    source: Path
    target: Path


@dataclass
class Result:
    source: Path
    target: Path
    status: str  # converted | skipped | failed
    message: str = ""


@dataclass
class Report:
    results: List[Result] = field(default_factory=list)

    @property
    def converted(self) -> int:
        return sum(1 for r in self.results if r.status == "converted")

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == "skipped")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "failed")

    @property
    def total(self) -> int:
        return len(self.results)


def find_cli() -> Optional[str]:
    """Locate splat-transform, honouring an explicit override."""
    override = os.environ.get("SPLAT_TRANSFORM")
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return str(path)
        found = shutil.which(override)
        if found:
            return found
    for name in ("splat-transform", "splat-transform.cmd", "splat-transform.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def cli_version(cli: str) -> str:
    try:
        proc = subprocess.run(
            [cli, "--version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        text = (proc.stdout + proc.stderr).strip()
        return text.splitlines()[0] if text else "unknown"
    except (OSError, subprocess.SubprocessError, IndexError):
        return "unknown"


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in INPUT_SUFFIXES and TMP_MARKER not in path.name


def collect_inputs(paths: Iterable[str | Path], recursive: bool = True) -> List[Path]:
    """Expand a mix of files and folders into a sorted, de-duplicated file list."""
    found: List[Path] = []
    seen = set()

    def add(item: Path) -> None:
        key = str(item.resolve()).lower()
        if key not in seen:
            seen.add(key)
            found.append(item)

    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            iterator = path.rglob("*") if recursive else path.glob("*")
            for child in iterator:
                if child.is_file() and is_supported(child):
                    add(child)
        elif path.is_file() and is_supported(path):
            add(path)
    return sorted(found, key=lambda p: str(p).lower())


def plan_jobs(sources: Sequence[Path], opts: Options) -> List[Job]:
    """Compute output paths, de-duplicating collisions inside one batch."""
    jobs: List[Job] = []
    used: set = set()
    for source in sources:
        if opts.replace_source:
            target = source.with_suffix(OUTPUT_SUFFIX)
            out_dir = source.parent
        else:
            out_dir = Path(opts.output_dir)
            target = out_dir / (source.stem + OUTPUT_SUFFIX)

        key = str(target.resolve()).lower()
        if key in used:
            index = 2
            while True:
                candidate = out_dir / f"{source.stem}_{index}{OUTPUT_SUFFIX}"
                if str(candidate.resolve()).lower() not in used:
                    target = candidate
                    used.add(str(target.resolve()).lower())
                    break
                index += 1
        else:
            used.add(key)
        jobs.append(Job(source=Path(source), target=target))
    return jobs


_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _run(cmd: Sequence[str], log: LogFn, cancel: CancelFn) -> None:
    """Run a command, stream its output to log, and support mid-flight cancel."""
    log("$ " + subprocess.list2cmdline(list(cmd)))
    try:
        proc = subprocess.Popen(
            list(cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
    except OSError as exc:
        raise ConversionError(f"无法启动 splat-transform: {exc}") from exc

    try:
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            cancel()
            line = _ANSI.sub("", raw_line).replace("\r", "").rstrip()
            if line:
                log("  " + line)
        return_code = proc.wait()
    except Cancelled:
        proc.kill()
        proc.wait()
        raise
    finally:
        if proc.stdout is not None:
            proc.stdout.close()

    if return_code != 0:
        raise ConversionError(f"命令退出码 {return_code}")


def send_to_trash(path: Path) -> bool:
    """Move a file to the OS recycle bin. Returns False when unsupported."""
    if os.name != "nt":
        return False

    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_uint16),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    FO_DELETE = 3
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040
    FOF_NOERRORUI = 0x0400

    # pFrom must be double-NUL terminated; create_unicode_buffer adds the last one.
    buffer = ctypes.create_unicode_buffer(str(path.resolve()) + "\0")
    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = ctypes.cast(buffer, wintypes.LPCWSTR)
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    op.fAnyOperationsAborted = False
    op.hNameMappings = None
    op.lpszProgressTitle = None

    try:
        result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        return result == 0 and not op.fAnyOperationsAborted
    except (AttributeError, OSError):
        return False


def _convert_job(
    job: Job, opts: Options, cli: str, log: LogFn, cancel: CancelFn
) -> Result:
    source, target = job.source, job.target

    if source.resolve() == target.resolve():
        return Result(source, target, "skipped", "输出与输入为同一文件")

    if not opts.overwrite_existing and target.exists():
        return Result(source, target, "skipped", "目标文件已存在（未勾选覆盖）")

    tmp_out = target.with_name(f".{target.stem}.{TMP_MARKER}{OUTPUT_SUFFIX}")
    if tmp_out.exists():
        tmp_out.unlink()

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="sog_convert_") as work:
            sog_source: Path = source

            decimate = opts.decimate_arg()
            if decimate is not None:
                # --decimate must be the final action and must write a .ply file,
                # so the SOG encoding is always a second invocation.
                intermediate = Path(work) / "decimated.ply"
                scratch = Path(work) / "scratch"
                cmd = [cli, str(source), "-N"]
                if opts.filter_low_opacity:
                    cmd += ["-V", "opacity,gt,0.02"]
                cmd += ["-d", decimate, "--scratch-dir", str(scratch), str(intermediate)]
                log(f"[1/2] 减点 -> {decimate}")
                _run(cmd, log, cancel)
                if not intermediate.is_file():
                    raise ConversionError("减点步骤未生成中间 PLY 文件")
                sog_source = intermediate

            cmd = [cli]
            if opts.use_cpu:
                cmd += ["-g", "cpu"]
            cmd += ["--webp-effort", str(int(opts.webp_effort))]
            cmd += [str(sog_source), str(tmp_out)]
            log("[2/2] 编码 SOG" if decimate else "[1/1] 编码 SOG")
            _run(cmd, log, cancel)

        if not tmp_out.is_file() or tmp_out.stat().st_size == 0:
            raise ConversionError("SOG 输出为空或不存在")

        os.replace(str(tmp_out), str(target))
        size_mb = target.stat().st_size / 1048576
        message = f"完成 -> {target.name} ({size_mb:.2f} MB)"

        if opts.replace_source and source.suffix.lower() != OUTPUT_SUFFIX:
            if send_to_trash(source):
                message += "；原文件已移入回收站"
            else:
                message += "；原文件未删除（回收站不可用，请手动处理）"
            log("  警告: 覆盖源文件模式已启用")
        return Result(source, target, "converted", message)

    except Cancelled:
        raise
    except (ConversionError, OSError, ValueError) as exc:
        return Result(source, target, "failed", str(exc))
    finally:
        if tmp_out.exists():
            try:
                tmp_out.unlink()
            except OSError:
                pass


def run_conversion(
    jobs: Sequence[Job],
    opts: Options,
    cli: str,
    log: Optional[LogFn] = None,
    cancel: Optional[CancelFn] = None,
    progress: Optional[Callable[[int, int, Result], None]] = None,
) -> Report:
    """Convert all jobs sequentially and return a summary report."""
    emit = log or _noop
    check = cancel or _never_cancel
    report = Report()
    total = len(jobs)

    for index, job in enumerate(jobs, start=1):
        check()
        emit(f"--- [{index}/{total}] {job.source} ---")
        result = _convert_job(job, opts, cli, emit, check)
        report.results.append(result)
        emit(f"  [{result.status}] {result.message}")
        if progress:
            progress(index, total, result)
    return report
