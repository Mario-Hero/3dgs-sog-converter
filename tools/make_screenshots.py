#!/usr/bin/env python3
"""Regenerate the README screenshots (Chinese + English) by launching the GUI
in a separate process, locating its window, and cropping it.

Usage:
    py -3 tools/make_screenshots.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    for lang in ("zh", "en"):
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "shot_one.py"), lang],
            check=True,
        )


if __name__ == "__main__":
    main()
