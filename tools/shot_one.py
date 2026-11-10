#!/usr/bin/env python3
"""Capture a single-language screenshot of the GUI *inside* its own process.

Doing the capture in-process keeps the DPI context consistent with the window
itself, so ``GetWindowRect`` returns the real, unscaled size (cross-process
capture from a DPI-unaware caller sees a virtualized, wrong rect).

Usage:
    py -3 tools/shot_one.py zh
    py -3 tools/shot_one.py en
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ctypes import windll  # noqa: E402
import win32con  # noqa: E402
import win32gui  # noqa: E402
import win32ui  # noqa: E402
from PIL import Image  # noqa: E402

from sog_converter import i18n  # noqa: E402
from sog_converter.gui import ConverterApp  # noqa: E402

LANG = sys.argv[1] if len(sys.argv) > 1 else "auto"
i18n.set_language(LANG)

app = ConverterApp()
app.update_idletasks()
app.update()
app.after(350)
app.update_idletasks()

hwnd = app.winfo_id()
left, top, right, bottom = win32gui.GetWindowRect(hwnd)
width, height = right - left, bottom - top

hwnd_dc = win32gui.GetWindowDC(hwnd)
mfc = win32ui.CreateDCFromHandle(hwnd_dc)
save = mfc.CreateCompatibleDC()
bitmap = win32ui.CreateBitmap()
bitmap.CreateCompatibleBitmap(mfc, width, height)
save.SelectObject(bitmap)
# PW_RENDERFULLCONTENT (2): paint the whole window incl. the title bar.
windll.user32.PrintWindow(hwnd, save.GetSafeHdc(), 2)

info = bitmap.GetInfo()
bits = bitmap.GetBitmapBits(True)
img = Image.frombuffer(
    "RGB", (info["bmWidth"], info["bmHeight"]), bits, "raw", "BGRX", 0, 1
)

out = ROOT / "assets" / f"screenshot-{LANG}.png"
img.save(out)
print(f"saved {out} ({img.width}x{img.height})")

for cleaner in (save.DeleteDC,
                lambda: win32gui.DeleteObject(bitmap.GetHandle()),
                lambda: win32gui.ReleaseDC(hwnd, hwnd_dc)):
    try:
        cleaner()
    except Exception:
        pass
app.destroy()
