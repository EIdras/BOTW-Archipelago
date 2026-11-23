"""Questions and messages in the window's own colours, in place of the
system's grey boxes. Each waits for its answer, the window behind it
inactive: Enter gives the highlighted answer, Escape the cautious one.
Without a parent, the window's (tkinter's default root). A dialog can hold
a field: a line to type (ask_text) or a list to pick from (choose)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from . import theme
from .widgets import Button, label

WRAP = 440      # the text's width, at a 96 dpi screen's scale


class Dialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc | None, title: str, text: str, role: str,
                 answers: list[tuple[str, object, str]], default: object, cancel: object,
                 field: Callable[[tk.Misc], tk.Widget] | None = None):
        """`answers`: (text, value, kind) from left to right; Enter gives the
        focused one (`default` first), Escape and the close button `cancel`.
        `field` makes the widget shown under the text, focused first."""
        owner = (parent or tk._default_root).winfo_toplevel()
        super().__init__(owner, bg=theme.WINDOW)
        self.withdraw()
        self.title(title)
        self.resizable(False, False)
        self.transient(owner)
        self.result, self._cancel = cancel, cancel
        body = tk.Frame(self, bg=theme.WINDOW)
        body.pack(fill="both", expand=True, padx=theme.px(24), pady=theme.px(20))
        label(body, title, "heading", bg=theme.WINDOW).pack(anchor="w")
        label(body, text, role, bg=theme.WINDOW, wraplength=theme.px(WRAP)).pack(fill="x", pady=theme.px(8, 0))
        self.field = field(body) if field else None
        if self.field is not None:
            self.field.pack(fill="x", pady=theme.px(12, 0))
        line = tk.Frame(body, bg=theme.WINDOW)
        line.pack(fill="x", pady=theme.px(18, 0))
        self.buttons = {}
        for text_, value, kind in reversed(answers):
            button = Button(line, text_, lambda value=value: self.answer(value), kind)
            button.pack(side="right", padx=theme.px(0, 8 if self.buttons else 0))
            self.buttons[value] = button
        self.default = default
        self.protocol("WM_DELETE_WINDOW", self.escape)
        self.bind("<Escape>", lambda _event: self.escape())
        self.bind("<Return>", lambda event: self.enter(event.widget))
        self._place(owner)
        (self.buttons[default] if self.field is None else self.field).focus_set()

    def escape(self) -> None:
        self.answer(self._cancel)

    def enter(self, widget: tk.Misc) -> None:
        """Enter: a focused answer gives itself (its own binding), else the default."""
        if not isinstance(widget, Button):
            self.answer(self.default)

    def _place(self, owner: tk.Misc) -> None:
        self.update_idletasks()
        x = owner.winfo_rootx() + (owner.winfo_width() - self.winfo_reqwidth()) // 2
        y = owner.winfo_rooty() + (owner.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        theme.dark_title_bar(self)

    def answer(self, value) -> None:
        self.result = value
        self.grab_release()
        self.destroy()

    def wait(self):
        try:
            self.grab_set()
        except tk.TclError:     # another application holds the grab: still modal enough
            pass
        self.wait_window()
        return self.result


def ask(parent: tk.Misc | None, title: str, text: str, yes: str = "OK", no: str = "Cancel",
        danger: bool = False) -> bool:
    """A question: True for `yes`. A dangerous one (danger) is not the default."""
    answers = [(no, False, "secondary"), (yes, True, "danger" if danger else "primary")]
    return Dialog(parent, title, text, "", answers, default=False if danger else True, cancel=False).wait()


def tell(parent: tk.Misc | None, title: str, text: str, role: str = "") -> None:
    """A message: role "warning" or "error" colours its text."""
    Dialog(parent, title, text, role, [("OK", True, "primary")], default=True, cancel=True).wait()


def ask_text(parent: tk.Misc | None, title: str, text: str, yes: str = "OK", initial: str = "") -> str | None:
    """A line the player types, stripped; None when they cancel or leave it empty."""
    value = tk.StringVar(value=initial)
    field = lambda body: ttk.Entry(body, textvariable=value, width=50)
    answered = Dialog(parent, title, text, "", [("Cancel", False, "secondary"), (yes, True, "primary")],
                      default=True, cancel=False, field=field).wait()
    return (value.get().strip() or None) if answered else None


def choose(parent: tk.Misc | None, title: str, text: str, choices: list[str], yes: str = "OK") -> str | None:
    """One of `choices` (the first offered), or None when the player cancels."""
    value = tk.StringVar(value=choices[0])
    field = lambda body: ttk.Combobox(body, textvariable=value, values=choices, state="readonly", width=40)
    answered = Dialog(parent, title, text, "", [("Cancel", False, "secondary"), (yes, True, "primary")],
                      default=True, cancel=False, field=field).wait()
    return value.get() if answered else None
