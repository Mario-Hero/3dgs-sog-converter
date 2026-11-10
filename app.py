#!/usr/bin/env python3
"""Entry point for the 3DGS -> SOG converter GUI.

Language selection:
    python app.py              # auto: follow OS language / SOG_LANG
    python app.py --lang zh    # force Chinese
    python app.py --lang en    # force English
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    from sog_converter import __version__

    parser = argparse.ArgumentParser(
        description="3DGS → SOG 转换器 / 3DGS → SOG Converter",
    )
    parser.add_argument(
        "--lang", choices=("auto", "zh", "en"), default="auto",
        metavar="auto|zh|en",
        help="界面语言 / UI language: auto（跟随系统 / follow OS）, zh, en",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"3DGS SOG Converter {__version__}",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)

    from sog_converter import i18n

    i18n.set_language(args.lang)

    try:
        import tkinter  # noqa: F401
    except ImportError:
        sys.stderr.write(i18n.t("err_tkinter"))
        sys.exit(1)

    from sog_converter.gui import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()
