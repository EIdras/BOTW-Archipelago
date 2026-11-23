"""The small window shown while the client sets itself up, the first time and
after an update: what it downloads, how far it is, and what went wrong.

The project's code is not unpacked yet: this window stands alone, in the
colours of the main one (botw_launcher/tk/theme.py)."""
from __future__ import annotations

import json
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk
import traceback
from typing import Callable

from . import SetupError

TITLE = "BOTW Archipelago"
WINDOW, TEXT, MUTED, ERROR = "#12151c", "#e6e9ef", "#8b94a6", "#e57373"
ACCENT, ACCENT_HOVER, SECONDARY, SECONDARY_HOVER = "#2f6a91", "#3a7dab", "#272e3c", "#313a4b"
FAMILY = "Segoe UI" if sys.platform == "win32" else "TkDefaultFont"


def getting() -> str:
    """What the window says it does, with the size of this system's libraries
    as wheels.json pins them (about 14 MB on Windows, 18 MB on Linux)."""
    try:
        from . import PINS, _pins, _resource
        size = sum(wheel["size"] for wheel in _pins(json.loads(_resource(PINS))))
    except Exception:  # noqa: BLE001 - the work itself says what is wrong
        return "Getting the libraries the game files need, once."
    return f"Getting the libraries the game files need, once (about {max(1, round(size / 2 ** 20))} MB)."


def run_setup(work: Callable) -> object | None:
    """`work(progress)` in a thread, the window showing its progress; its
    result, or None when the player closed the window."""
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk(className=TITLE)
    window = SetupWindow(root, work)
    root.mainloop()
    return window.result


class SetupWindow:
    def __init__(self, root: tk.Tk, work: Callable):
        self.root, self.work, self.result = root, work, None
        self.events: queue.Queue = queue.Queue()
        scale = root.winfo_fpixels("1i") / 96
        root.title(TITLE)
        root.configure(bg=WINDOW)
        root.resizable(False, False)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Setup.Horizontal.TProgressbar", troughcolor=SECONDARY, background=ACCENT,
                        bordercolor=WINDOW, lightcolor=ACCENT, darkcolor=ACCENT)
        frame = tk.Frame(root, bg=WINDOW, padx=round(24 * scale), pady=round(20 * scale))
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="Setting up BOTW Archipelago", bg=WINDOW, fg=TEXT,
                 font=(FAMILY, 13, "bold"), anchor="w").pack(fill="x")
        self.detail = tk.Label(frame, text=getting(),
                               bg=WINDOW, fg=MUTED, font=(FAMILY, 10), anchor="w", justify="left",
                               wraplength=round(420 * scale))
        self.detail.pack(fill="x", pady=(round(6 * scale), round(12 * scale)))
        self.bar = ttk.Progressbar(frame, style="Setup.Horizontal.TProgressbar", maximum=1000,
                                   length=round(420 * scale))
        self.bar.pack(fill="x")
        self.status = tk.Label(frame, text="", bg=WINDOW, fg=MUTED, font=(FAMILY, 9), anchor="w")
        self.status.pack(fill="x", pady=(round(6 * scale), 0))
        self.buttons = tk.Frame(frame, bg=WINDOW)
        self.buttons.pack(fill="x", pady=(round(14 * scale), 0))
        self.retry = self._button("Try again", ACCENT, ACCENT_HOVER, self.start)
        self._button("Close", SECONDARY, SECONDARY_HOVER, root.destroy).pack(side="right")
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        root.bind("<Escape>", lambda _event: root.destroy())
        self.start()
        root.after(50, self.pump)

    def _button(self, text: str, colour: str, hover: str, command: Callable) -> tk.Button:
        button = tk.Button(self.buttons, text=text, command=command, bg=colour, fg=TEXT, activebackground=hover,
                           activeforeground=TEXT, relief="flat", borderwidth=0, padx=14, pady=5,
                           font=(FAMILY, 10), cursor="hand2")
        button.bind("<Enter>", lambda _event: button.configure(bg=hover))
        button.bind("<Leave>", lambda _event: button.configure(bg=colour))
        return button

    def start(self) -> None:
        self.retry.pack_forget()
        self.detail.configure(text=getting(), fg=MUTED)
        self.bar.configure(value=0)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            self.events.put(("done", self.work(lambda *step: self.events.put(("progress", step)))))
        except SetupError as exc:
            self.events.put(("failed", str(exc)))
        except Exception as exc:  # noqa: BLE001 - shown, not lost in a closed console
            self.events.put(("failed", f"Something unexpected happened: {exc!r}\n\n"
                                       + "".join(traceback.format_exception(exc))[-600:]))

    def pump(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    what, done, total = value
                    self.bar.configure(value=round(1000 * done / total) if total else 0)
                    self.status.configure(text=f"Downloading {what}…" if done < total else f"Unpacking {what}…")
                elif kind == "done":
                    self.result = value
                    self.root.destroy()
                    return
                else:
                    self.detail.configure(text=value, fg=ERROR)
                    self.status.configure(text="")
                    self.retry.pack(side="right", padx=(round(8 * self.root.winfo_fpixels('1i') / 96), 0))
        except queue.Empty:
            pass
        self.root.after(50, self.pump)
