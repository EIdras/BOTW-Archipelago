"""Help: the player's guides (core/guides.py), read in
the window. A link to another guide or to a heading is followed in the page,
a web link opens in the browser."""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from urllib.parse import unquote, urlsplit

from ...core import guides
from .. import theme
from ..context import Context
from ..markdown_view import MarkdownView
from ..widgets import Button, open_folder, open_link
from . import Page


class HelpPage(Page):
    def __init__(self, parent: tk.Misc, context: Context):
        super().__init__(parent, "Help")
        self.context = context
        self.current_guide: Path | None = None
        self.history: list[tuple[Path, float]] = []     # the guide and where it was read, for Back
        self.back_button = Button(self.header, "Back", self.back)
        self.back_button.pack(side="right")
        self.list = tk.Frame(self.body, bg=theme.SIDEBAR, width=theme.px(210))
        self.list.pack(side="left", fill="y", padx=theme.px(0, 18))
        self.list.pack_propagate(False)
        self.entries: dict[Path, Button] = {}
        self.view = MarkdownView(self.body, self.follow)
        self.view.pack(side="left", fill="both", expand=True)

    def shown(self) -> None:
        if not self.entries:
            width = round(186 * self.winfo_fpixels("1i") / 96)
            for guide in guides.guides():
                entry = Button(self.list, guides.title(guide), lambda guide=guide: self.open(guide), "nav",
                               width=width, anchor="w", padding=(12, 7))
                entry.pack(padx=theme.px(12), pady=theme.px(1, 0))
                self.entries[guide] = entry
            if self.entries:
                tk.Frame(self.list, bg=theme.SIDEBAR, height=theme.px(10)).pack()
        if self.current_guide is None and self.entries:
            self.open(next(iter(self.entries)), remember=False)
        self.back_button.set(enabled=bool(self.history))

    def open(self, guide: Path, heading: str = "", remember: bool = True) -> None:
        if remember and self.current_guide is not None:
            self.history.append((self.current_guide, self.view.text.yview()[0]))
        if guide != self.current_guide:
            self.current_guide = guide
            self.view.show(guides.text(guide), guide.parent)
        for path, entry in self.entries.items():
            entry.set(kind="nav-current" if path == guide else "nav")
        self.view.text.yview_moveto(0)
        if heading:
            self.view.update_idletasks()
            self.view.scroll_to(heading)
        self.back_button.set(enabled=bool(self.history))

    def back(self) -> None:
        if self.history:
            guide, position = self.history.pop()
            self.open(guide, remember=False)
            self.view.update_idletasks()
            self.view.text.yview_moveto(position)

    def follow(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme in guides.WEB:
            open_link(url)
            return
        path = unquote(parts.path)
        target = (self.current_guide.parent / path).resolve() if path else self.current_guide
        if target.suffix == ".md" and target.is_file():
            self.open(target, parts.fragment)
        elif target.exists():
            open_folder(target)
        else:
            self.context.notice.emit(f"{path} is not in this copy of BOTW Archipelago.", [])
