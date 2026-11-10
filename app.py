#!/usr/bin/env python3
"""Entry point for the 3DGS -> SOG converter GUI."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    try:
        import tkinter  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "错误：当前 Python 未包含 tkinter。\n"
            "  Windows / macOS：请从 python.org 安装官方版本并勾选 tcl/tk。\n"
            "  Linux：请安装 python3-tk（Debian/Ubuntu）或对应发行版软件包。\n"
        )
        sys.exit(1)

    from sog_converter.gui import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()
