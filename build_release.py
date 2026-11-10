#!/usr/bin/env python3
"""Build a self-contained, zero-dependency Windows release.

What it produces (under ``release/``):
    dist/3dgs_sog_converter.exe      frozen GUI (Python + tkinter + Tcl/Tk)
    release/3dgs-sog-converter-win64/
        ├── 3dgs_sog_converter.exe   the GUI, double-click to run
        ├── tools/
        │   ├── node.exe             portable Node runtime
        │   ├── splat-transform/     @playcanvas/splat-transform package
        │   └── splat-transform.cmd  launcher → bundled node + cli.mjs
        ├── README.txt
        └── LICENSE
    release/3dgs-sog-converter-win64.zip

End users only unzip and double-click the .exe — Python and Node are bundled.

Requirements on the build machine:
    * a Python with tkinter and PyInstaller (``pip install pyinstaller``)
    * a Node install that has ``@playcanvas/splat-transform`` (auto-detected
      from the WorkBuddy bundled Node, ``splat-transform`` on PATH, or the
      ``SPLAT_NODE_DIR`` environment variable)

Usage:
    python build_release.py            # full build + zip
    python build_release.py --stage    # rebuild only the staging folder (skip PyInstaller)
    python build_release.py --zip      # rebuild only the zip from an existing staging folder
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RELEASE = ROOT / "release"
DIST = RELEASE / "dist"
BUILD = RELEASE / "build"
PKG_NAME = "3dgs-sog-converter-win64"
STAGE = RELEASE / PKG_NAME
EXE_NAME = "3dgs_sog_converter.exe"

# Files that never matter at runtime and only bloat the package.
IGNORE_SUFFIXES = (".map", ".md", ".d.ts", ".ts", ".tsbuildinfo")
IGNORE_DIRS = {"@types", ".github", "test", "tests", "__tests__", "docs"}


def log(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def find_node_dir() -> Path:
    """Locate a Node install that bundles splat-transform."""
    env = os.environ.get("SPLAT_NODE_DIR")
    candidates = []
    if env:
        candidates.append(Path(env))
    # WorkBuddy bundled Node versions (newest first).
    base = Path.home() / ".workbuddy" / "binaries" / "node" / "versions"
    if base.is_dir():
        candidates.extend(sorted(base.iterdir(), reverse=True))
    # node.exe on PATH → its folder, plus the npm global root.
    node_exe = shutil.which("node")
    if node_exe:
        candidates.append(Path(node_exe).resolve().parent)

    for cand in candidates:
        if not cand or not cand.is_dir():
            continue
        has_node = (cand / "node.exe").is_file() or (cand / "node").is_file()
        pkg = cand / "node_modules" / "@playcanvas" / "splat-transform" / "bin" / "cli.mjs"
        if has_node and pkg.is_file():
            return cand
    raise SystemExit(
        "Could not find a Node install with @playcanvas/splat-transform.\n"
        "Install it (npm i -g @playcanvas/splat-transform) or set SPLAT_NODE_DIR."
    )


def build_exe() -> Path:
    log("running PyInstaller …")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed",
        "--name", "3dgs_sog_converter",
        "--clean", "--noconfirm",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        str(ROOT / "app.py"),
    ]
    subprocess.run(cmd, check=True)
    exe = DIST / EXE_NAME
    if not exe.is_file():
        raise SystemExit(f"PyInstaller did not produce {exe}")
    log(f"exe: {exe} ({exe.stat().st_size/1048576:.1f} MB)")
    return exe


def _ignore(dirname: str, names: list[str]):
    ignored = []
    for n in names:
        if n in IGNORE_DIRS:
            ignored.append(n)
        elif n.lower().endswith(IGNORE_SUFFIXES):
            ignored.append(n)
    return ignored


def write_launcher(tools: Path) -> None:
    launcher = tools / "splat-transform.cmd"
    launcher.write_text(
        "@ECHO off\r\n"
        "SETLOCAL\r\n"
        'SET "HERE=%~dp0"\r\n'
        '"%HERE%node.exe" "%HERE%splat-transform\\bin\\cli.mjs" %*\r\n',
        encoding="utf-8",
        newline="",
    )


def write_readme(stage: Path) -> None:
    text = (
        "3DGS → SOG Converter (portable, Windows 64-bit)\r\n"
        "=================================================\r\n"
        "\r\n"
        "无需安装任何东西，解压后双击 3dgs_sog_converter.exe 即可运行。\r\n"
        "No installation needed — unzip and double-click 3dgs_sog_converter.exe.\r\n"
        "\r\n"
        "包含 / Bundled:\r\n"
        "  * Python 运行时与 tkinter（已打包进 exe）/ Python + tkinter (frozen in the exe)\r\n"
        "  * Node 运行时 (tools\\node.exe) / Node runtime\r\n"
        "  * splat-transform (tools\\splat-transform) / the conversion engine\r\n"
        "\r\n"
        "用法 / Usage:\r\n"
        "  1. 双击 3dgs_sog_converter.exe 打开界面。\r\n"
        "     Double-click 3dgs_sog_converter.exe to open the GUI.\r\n"
        "  2. 左上角选择导出格式：压缩 SOG (.sog) 或 压缩 PLY (.compressed.ply)。\r\n"
        "     Pick the export format at the top-left: SOG or compressed PLY.\r\n"
        "  3. 添加文件/文件夹，选择输出目录，点“开始转换”。\r\n"
        "     Add files/folder, choose an output folder, then click Start.\r\n"
        "\r\n"
        "界面语言跟随系统，也可用命令行强制：\r\n"
        "The UI follows the OS language; override it via command line:\r\n"
        "  3dgs_sog_converter.exe --lang zh\r\n"
        "  3dgs_sog_converter.exe --lang en\r\n"
        "\r\n"
        "转换引擎来自 PlayCanvas splat-transform (MIT)。\r\n"
        "Conversion engine: PlayCanvas splat-transform (MIT).\r\n"
    )
    (stage / "README.txt").write_text(text, encoding="utf-8", newline="")


def stage_package() -> Path:
    node_dir = find_node_dir()
    log(f"node dir: {node_dir}")
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    tools = STAGE / "tools"
    tools.mkdir()

    # 1) frozen GUI
    exe = DIST / EXE_NAME
    if not exe.is_file():
        raise SystemExit(f"{exe} missing — run a full build first")
    shutil.copy2(exe, STAGE / EXE_NAME)

    # 2) portable Node runtime (node.exe + any top-level runtime files)
    log("copying node.exe …")
    shutil.copy2(node_dir / "node.exe", tools / "node.exe")

    # 3) splat-transform package (with its nested node_modules)
    src_pkg = node_dir / "node_modules" / "@playcanvas" / "splat-transform"
    log("copying splat-transform package (this can take a moment) …")
    shutil.copytree(src_pkg, tools / "splat-transform", ignore=_ignore)

    # 4) launcher + docs
    write_launcher(tools)
    write_readme(STAGE)
    lic = ROOT / "LICENSE"
    if lic.is_file():
        shutil.copy2(lic, STAGE / "LICENSE")

    log("staging done")
    return STAGE


def make_zip() -> Path:
    zip_path = RELEASE / f"{PKG_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    log(f"zipping → {zip_path} …")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(RELEASE))
    log(f"zip: {zip_path} ({zip_path.stat().st_size/1048576:.1f} MB)")
    return zip_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the portable release.")
    ap.add_argument("--stage", action="store_true", help="only rebuild the staging folder")
    ap.add_argument("--zip", action="store_true", help="only rebuild the zip")
    args = ap.parse_args()

    RELEASE.mkdir(exist_ok=True)
    if args.zip:
        make_zip()
        return
    if not args.stage:
        build_exe()
    stage_package()
    make_zip()


if __name__ == "__main__":
    main()
