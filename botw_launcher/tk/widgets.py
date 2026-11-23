"""The window's pieces: rounded buttons, labels by role, cards, the log, the
steps of a session, a scrolling area. Colours come from theme.py."""
from __future__ import annotations

from datetime import datetime
import logging
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import font as tkfont, ttk
import webbrowser

from . import theme

logger = logging.getLogger(__name__)

# A button's colours by kind: (background, hovered, text).
KINDS = {"primary": (theme.ACCENT, theme.ACCENT_HOVER, theme.TEXT),
         "secondary": (theme.SECONDARY, theme.SECONDARY_HOVER, theme.TEXT),
         "danger": (theme.SECONDARY, theme.DANGER, theme.TEXT),
         "nav": (theme.SIDEBAR, theme.HOVER, theme.TEXT),
         "nav-current": (theme.SELECTED, theme.SELECTED, theme.TEXT)}


def human_size(size: int) -> str:
    for unit, scale in (("GB", 2**30), ("MB", 2**20)):
        if size >= scale:
            return f"{size / scale:.1f} {unit}"
    return f"{size / 2**10:.0f} KB"


def human_day(moment: datetime | None) -> str:
    return moment.astimezone().strftime("%d %b %Y") if moment else "never"


def system_environment() -> dict[str, str]:
    """This process's variables, for a program of the system's: without the
    library path Archipelago's Linux AppImage sets for its own libraries, which
    that program would load in place of the system's (as Archipelago does)."""
    environment = dict(os.environ)
    environment.pop("LD_LIBRARY_PATH", None)
    return environment


def _xdg_open(target: str) -> bool:
    try:
        subprocess.Popen(["xdg-open", target], env=system_environment())
    except OSError as exc:
        logger.warning("%s could not be opened: %s", target, exc)
        return False
    return True


def open_folder(path: Path | None) -> None:
    if path is None:
        return
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - a folder of the player's, opened in the explorer
    else:
        _xdg_open(str(path))


def open_link(url: str) -> None:
    """A web page, in the player's browser."""
    if sys.platform == "win32" or not _xdg_open(url):
        webbrowser.open(url)


def background_of(widget: tk.Misc) -> str:
    try:
        return widget.cget("background")
    except tk.TclError:
        return theme.SURFACE


class Button(tk.Canvas):
    """A rounded button. kind: primary, secondary, danger, nav, nav-current.
    Reached with Tab, pressed with Enter or Space; outlined while it has the focus.
    `padding` at a 96 dpi screen's scale; `width`, when given, in pixels."""
    RADIUS = 7

    def __init__(self, parent: tk.Misc, text: str, command=None, kind: str = "secondary",
                 width: int | None = None, anchor: str = "center", padding: tuple[int, int] = (14, 7)):
        self._font = tkfont.Font(font=theme.FONTS["button"])
        self._padding, self._anchor, self._fixed = theme.px(*padding), anchor, width
        height = self._font.metrics("linespace") + 2 * self._padding[1]
        super().__init__(parent, height=height, highlightthickness=0, bd=0, background=background_of(parent),
                         cursor="hand2", takefocus=1)
        self.command, self.kind, self.text, self.enabled, self._hover = command, kind, text, True, False
        self._focused = False
        self.bind("<Enter>", lambda _e: self._hovered(True))
        self.bind("<Leave>", lambda _e: self._hovered(False))
        self.bind("<ButtonRelease-1>", self._clicked)
        self.bind("<FocusIn>", lambda _e: self._focus(True))
        self.bind("<FocusOut>", lambda _e: self._focus(False))
        for key in ("<Return>", "<KP_Enter>", "<space>"):
            self.bind(key, lambda _e: self.invoke())
        self.bind("<Configure>", lambda _e: self._draw())
        self._size()

    def _size(self) -> None:
        width = self._fixed or self._font.measure(self.text) + 2 * self._padding[0]
        self.configure(width=width)
        self._draw()

    def set(self, text: str | None = None, kind: str | None = None, enabled: bool | None = None) -> None:
        if text is not None and text != self.text:
            self.text = text
            self._size()
        if kind is not None:
            self.kind = kind
        if enabled is not None:
            self.enabled = enabled
            self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def _hovered(self, hover: bool) -> None:
        self._hover = hover
        self._draw()

    def _focus(self, focused: bool) -> None:
        self._focused = focused
        self._draw()

    def invoke(self) -> None:
        if self.enabled and self.command is not None:
            self.command()

    def _clicked(self, event) -> None:
        if 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            self.invoke()

    def _draw(self) -> None:
        self.delete("all")
        width, height = max(self.winfo_width(), int(self.cget("width"))), int(self.cget("height"))
        if self.winfo_width() > 1:
            width = self.winfo_width()
        normal, hovered, foreground = KINDS[self.kind]
        if not self.enabled:
            fill, foreground = (theme.DISABLED if self.kind not in ("nav",) else theme.SIDEBAR), theme.DISABLED_TEXT
        else:
            fill = hovered if self._hover else normal
        r = min(theme.px(self.RADIUS), height // 2)
        points = (r, 0, width - r, 0, width, 0, width, r, width, height - r, width, height, width - r, height,
                  r, height, 0, height, 0, height - r, 0, r, 0, 0)
        ring = self._focused and self.enabled
        self.create_polygon(points, smooth=True, fill=fill, outline=theme.FOCUS if ring else fill,
                            width=max(1, theme.px(2)) if ring else 1)
        x = width / 2 if self._anchor == "center" else self._padding[0]
        self.create_text(x, height / 2, text=self.text, fill=foreground, font=self._font,
                         anchor="center" if self._anchor == "center" else "w")


def label(parent: tk.Misc, text: str = "", role: str = "", wrap: bool = False, **options) -> tk.Label:
    """A label of a role (theme.ROLES); `wrap`: its lines follow its width."""
    font = theme.FONTS.get(role if role in ("heading", "title", "small", "brand") else "body")
    options.setdefault("bg", background_of(parent))
    made = tk.Label(parent, text=text, fg=theme.ROLES.get(role, theme.TEXT), font=font, anchor="w",
                    justify="left", **options)
    if wrap:
        made.bind("<Configure>", lambda event: made.configure(wraplength=max(event.width - 4, 50)))
    return made


def set_role(widget: tk.Label, role: str) -> None:
    widget.configure(fg=theme.ROLES.get(role, theme.TEXT))


def card(parent: tk.Misc, title: str = "", padding: int = 16) -> tuple[tk.Frame, tk.Frame]:
    """A card: its outer frame (to place) and its body (to fill)."""
    outer = tk.Frame(parent, bg=theme.SURFACE, highlightthickness=1, highlightbackground=theme.BORDER)
    body = tk.Frame(outer, bg=theme.SURFACE)
    body.pack(fill="both", expand=True, padx=theme.px(padding), pady=theme.px(padding))
    if title:
        label(body, title, "heading").pack(anchor="w", pady=theme.px(0, 8))
    return outer, body


def row(parent: tk.Misc, *widgets, gap: int = 8, pady=(10, 0)) -> tk.Frame:
    """A row of widgets, built by the callables given (each takes the row);
    gap and pady at a 96 dpi screen's scale."""
    frame = tk.Frame(parent, bg=background_of(parent))
    frame.pack(fill="x", pady=theme.px(*pady) if isinstance(pady, tuple) else theme.px(pady))
    made = []
    for build in widgets:
        if build is None:
            tk.Frame(frame, bg=background_of(parent)).pack(side="left", fill="x", expand=True)
            continue
        widget = build(frame)
        widget.pack(side="left", padx=theme.px(0, gap))
        made.append(widget)
    return frame


class LogView(tk.Frame):
    MAX_LINES = 5000

    def __init__(self, parent: tk.Misc):
        super().__init__(parent, bg=theme.FIELD, highlightthickness=1, highlightbackground=theme.BORDER)
        self.text = tk.Text(self, bg=theme.FIELD, fg=theme.TEXT, insertbackground=theme.TEXT, relief="flat",
                            font=theme.FONTS["mono"], wrap="word", state="disabled", padx=theme.px(10), pady=theme.px(8),
                            selectbackground=theme.ACCENT, highlightthickness=0, borderwidth=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        self.text.tag_configure("found", background=theme.FOUND)
        self.text.tag_configure("current", background=theme.FOUND_CURRENT)
        self.needle, self.match = "", -1

    def add(self, line: str) -> None:
        self._insert([(line, None)])

    def add_parts(self, parts: list) -> None:
        """A line in parts, (text, kind, item flags): coloured as Archipelago's clients do."""
        self._insert([(str(text), theme.part_colour(kind, int(flags))) for text, kind, flags in parts])

    def _insert(self, chunks: list[tuple[str, str | None]]) -> None:
        at_end = self.text.yview()[1] >= 0.999
        self.text.configure(state="normal")
        start = self.text.index("end-1c")
        for text, colour in chunks:
            if colour is not None:
                self.text.tag_configure(colour, foreground=colour)
            self.text.insert("end", text, (colour,) if colour else ())
        self.text.insert("end", "\n")
        if self.needle:
            self._mark(start)
        excess = int(self.text.index("end-1c").split(".")[0]) - self.MAX_LINES
        if excess > 0:
            self.text.delete("1.0", f"{excess + 1}.0")
        self.text.configure(state="disabled")
        if at_end:
            self.text.see("end")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.match = -1

    def search(self, needle: str) -> int:
        """Marks where `needle` is (case ignored) and shows the last place; how many there are."""
        self.text.tag_remove("found", "1.0", "end")
        self.text.tag_remove("current", "1.0", "end")
        self.needle, self.match = needle, -1
        if needle:
            self._mark("1.0")
        found = len(self.text.tag_ranges("found")) // 2
        if found:
            self.step(-1)
        return found

    def step(self, delta: int = -1) -> None:
        """Shows the place found before (-1) or after (1) the one shown, round."""
        ranges = self.text.tag_ranges("found")
        if not ranges:
            return
        count = len(ranges) // 2
        self.match = count - 1 if self.match < 0 else (self.match + delta) % count
        self.text.tag_remove("current", "1.0", "end")
        start, end = ranges[2 * self.match], ranges[2 * self.match + 1]
        self.text.tag_add("current", start, end)
        self.text.see(start)

    def _mark(self, start: str) -> None:
        length = tk.IntVar(self)
        while True:
            at = self.text.search(self.needle, start, "end", nocase=True, count=length)
            if not at or not length.get():
                return
            start = f"{at}+{length.get()}c"
            self.text.tag_add("found", at, start)


class StepBar(tk.Frame):
    """The steps of a session, each a dot and its name: pending, active, done
    or problem."""
    COLOURS = {"pending": theme.BORDER, "active": theme.ACCENT_HOVER, "done": theme.OK,
               "problem": theme.WARNING, "failed": theme.ERROR}

    def __init__(self, parent: tk.Misc, steps: list[tuple[str, str]]):
        super().__init__(parent, bg=background_of(parent))
        self.states: dict[str, str] = {}
        self.dots: dict[str, tuple[tk.Canvas, int]] = {}
        for index, (key, name) in enumerate(steps):
            if index:
                tk.Frame(self, bg=theme.BORDER, height=theme.px(2), width=theme.px(28)).pack(side="left",
                                                                                               padx=theme.px(8))
            size = theme.px(12)
            dot = tk.Canvas(self, width=size, height=size, bg=background_of(parent), highlightthickness=0)
            item = dot.create_oval(1, 1, size - 1, size - 1, fill=theme.BORDER, outline="")
            dot.pack(side="left", padx=theme.px(0, 6))
            label(self, name, "muted").pack(side="left")
            self.dots[key] = (dot, item)
        self.reset()

    def reset(self) -> None:
        for key in self.dots:
            self.set_state(key, "pending")

    def set_state(self, key: str, state: str) -> None:
        self.states[key] = state
        dot, item = self.dots[key]
        dot.itemconfigure(item, fill=self.COLOURS[state])

    def stop(self, failed: bool = False) -> None:
        """The session ended: an active step is left failed, or pending."""
        for key, state in self.states.items():
            if state == "active":
                self.set_state(key, "failed" if failed else "pending")


class VerticalScroll(tk.Frame):
    """Its `inner` frame scrolls when taller than the area."""

    def __init__(self, parent: tk.Misc, bg: str | None = None):
        bg = bg or background_of(parent)
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", lambda _e: self._fit())
        self.canvas.bind("<Configure>", lambda event: (self.canvas.itemconfigure(self._window, width=event.width),
                                                       self._fit()))
        self.canvas.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))

    def _fit(self) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        needed = self.inner.winfo_reqheight() > self.canvas.winfo_height()
        if needed and not self.bar.winfo_ismapped():
            self.bar.pack(side="right", fill="y")
        elif not needed and self.bar.winfo_ismapped():
            self.bar.pack_forget()
            self.canvas.yview_moveto(0)

    def see(self, widget: tk.Misc) -> None:
        """Scroll as little as needed for `widget`, a child of `inner`, to show whole."""
        self.update_idletasks()
        total = max(self.inner.winfo_height(), 1)
        top, bottom = widget.winfo_y(), widget.winfo_y() + widget.winfo_height()
        first, last = (fraction * total for fraction in self.canvas.yview())
        if top < first:
            self.canvas.yview_moveto(top / total)
        elif bottom > last:
            self.canvas.yview_moveto((bottom - (last - first)) / total)

    def _wheel(self, event) -> None:
        if self.bar.winfo_ismapped():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
