"""Core conversion logic for the 3DGS -> SOG converter.

This module has no GUI dependency. It shells out to the open source
`@playcanvas/splat-transform` CLI and can be imported by other tools or tests.

All file writes go through a temporary `.sog` file followed by an atomic
``os.replace`` so a failed conversion never damages an existing output.
User-facing strings are translated through :mod:`sog_converter.i18n`.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence

from . import i18n

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
    "load_cli_config",
    "plan_jobs",
    "run_conversion",
    "save_cli_config",
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
                raise ValueError(i18n.t("err_target_positive"))
            return str(value)
        if self.decimate_mode == "percent":
            value = int(self.decimate_value)
            if not 1 <= value <= 99:
                raise ValueError(i18n.t("err_percent_range"))
            return f"{value}%"
        raise ValueError(i18n.t("err_unknown_mode", mode=self.decimate_mode))

    def validate(self) -> None:
        if not 0 <= int(self.webp_effort) <= 9:
            raise ValueError(i18n.t("err_webp_range"))
        self.decimate_arg()
        if not self.replace_source and self.output_dir is None:
            raise ValueError(i18n.t("err_output_required"))
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


CONFIG_NAME = ".3dgs_sog_converter.json"


def _config_path() -> Path:
    return Path.home() / CONFIG_NAME


def load_cli_config() -> Optional[str]:
    """Return a previously saved manual tool path, if still valid."""
    try:
        path = _config_path()
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        cli = data.get("cli")
        if cli and Path(cli).expanduser().is_file():
            return str(Path(cli).expanduser())
    except (OSError, ValueError):
        pass
    return None


def save_cli_config(cli: str) -> None:
    """Persist a manually chosen tool path for future launches."""
    try:
        path = _config_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data["cli"] = str(cli)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def _cli_names() -> List[str]:
    """Candidate executable names, preferring a Windows launcher."""
    if os.name == "nt":
        return [
            "splat-transform.cmd",
            "splat-transform.exe",
            "splat-transform.bat",
            "splat-transform",
        ]
    return ["splat-transform"]


def _prefer_cmd(path: str) -> str:
    """On Windows, prefer the .cmd launcher over an extensionless bash script."""
    if os.name == "nt":
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".cmd", ".exe", ".bat", ".ps1"):
            cand = path + ".cmd"
            if os.path.isfile(cand):
                return cand
    return path


def _candidate_cli_dirs() -> List[str]:
    """Directories likely to contain a global splat-transform install."""
    dirs: List[str] = []

    # npm global prefix: on Windows the launcher lives directly in this dir.
    try:
        proc = subprocess.run(
            ["npm", "prefix", "-g"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15,
        )
        if proc.returncode == 0:
            d = proc.stdout.strip()
            if d and Path(d).is_dir():
                dirs.append(d)
    except (OSError, subprocess.SubprocessError):
        pass

    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.append(os.path.join(appdata, "npm"))
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        dirs.append(os.path.join(localappdata, "npm"))

    # WorkBuddy bundled Node versions (this machine's layout).
    for d in sorted(
        glob.glob(str(Path.home() / ".workbuddy" / "binaries" / "node"
                     / "versions" / "*")), reverse=True
    ):
        if os.path.isdir(d):
            dirs.append(d)

    for d in ("C:\\Program Files\\nodejs", "C:\\nodejs", "C:\\ProgramData\\npm"):
        if os.path.isdir(d):
            dirs.append(d)

    seen: set = set()
    out: List[str] = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def find_cli() -> Optional[str]:
    """Locate splat-transform, honouring overrides then common install paths.

    Resolution order:
        1. ``SPLAT_TRANSFORM`` environment variable
        2. a tool path saved through the GUI "Locate tool" button
        3. the system ``PATH`` (preferring the Windows ``.cmd`` launcher)
        4. well-known global-install directories (npm prefix, AppData, etc.)
    """
    override = os.environ.get("SPLAT_TRANSFORM")
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return _prefer_cmd(str(path))
        found = shutil.which(override)
        if found:
            return _prefer_cmd(found)

    cfg = load_cli_config()
    if cfg:
        return _prefer_cmd(cfg)

    for name in _cli_names():
        found = shutil.which(name)
        if found:
            return _prefer_cmd(found)

    exts = (".cmd", ".exe", ".bat", ".ps1", "") if os.name == "nt" else ("",)
    for d in _candidate_cli_dirs():
        for ext in exts:
            cand = os.path.join(d, "splat-transform" + ext)
            if os.path.isfile(cand):
                return _prefer_cmd(cand)
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
        raise ConversionError(i18n.t("err_launch", error=exc)) from exc

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
        raise ConversionError(i18n.t("err_exit_code", code=return_code))


def _convert_job(
    job: Job, opts: Options, cli: str, log: LogFn, cancel: CancelFn
) -> Result:
    source, target = job.source, job.target

    if source.resolve() == target.resolve():
        return Result(source, target, "skipped", i18n.t("skip_same_file"))

    if not opts.overwrite_existing and target.exists():
        return Result(source, target, "skipped", i18n.t("skip_exists"))

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
                log(i18n.t("log_step1", value=decimate))
                _run(cmd, log, cancel)
                if not intermediate.is_file():
                    raise ConversionError(i18n.t("err_no_intermediate"))
                sog_source = intermediate

            cmd = [cli]
            if opts.use_cpu:
                cmd += ["-g", "cpu"]
            cmd += ["--webp-effort", str(int(opts.webp_effort))]
            cmd += [str(sog_source), str(tmp_out)]
            log(i18n.t("log_step2") if decimate else i18n.t("log_step_single"))
            _run(cmd, log, cancel)

        if not tmp_out.is_file() or tmp_out.stat().st_size == 0:
            raise ConversionError(i18n.t("err_empty_output"))

        os.replace(str(tmp_out), str(target))
        size_mb = target.stat().st_size / 1048576
        message = i18n.t("done", name=target.name, size=size_mb)

        if opts.replace_source and source.suffix.lower() != OUTPUT_SUFFIX:
            try:
                source.unlink()
                message += i18n.t("deleted")
            except OSError as exc:
                message += i18n.t("delete_failed", error=exc)
            log(i18n.t("warn_replace"))
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
        emit(i18n.t("log_job", index=index, total=total, path=job.source))
        result = _convert_job(job, opts, cli, emit, check)
        report.results.append(result)
        emit(i18n.t("log_result", status=result.status, message=result.message))
        if progress:
            progress(index, total, result)
    return report
