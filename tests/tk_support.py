"""Tk for the window's tests. A Python built without it (a Linux system Python
often is) or a computer with no display (a Linux CI runner) skips those tests
instead of failing them."""
from __future__ import annotations

import unittest

try:
    import tkinter as tk
except ImportError:
    tk = None


def require_tkinter() -> None:
    if tk is None:
        raise unittest.SkipTest("this Python has no tkinter")


def hidden_root():
    """A withdrawn Tk root; the test is skipped where Tk cannot open one."""
    require_tkinter()
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise unittest.SkipTest(f"Tk cannot open a window here: {error}") from None
    root.withdraw()
    return root
