"""The window's pages, one per entry of the sidebar."""
from __future__ import annotations

import tkinter as tk

from .. import theme
from ..widgets import VerticalScroll, card, label


class Page(tk.Frame):
    """A page: its title, then its body. `shown()` is called each time it is
    brought to the front."""
    current = False     # the page in front: the pages are stacked, all of them mapped

    def __init__(self, parent: tk.Misc, title: str):
        super().__init__(parent, bg=theme.WINDOW)
        self.header = tk.Frame(self, bg=theme.WINDOW)
        self.header.pack(fill="x", padx=theme.px(28), pady=theme.px(22, 14))
        self.title = label(self.header, title, "title")
        self.title.pack(side="left")
        self.body = tk.Frame(self, bg=theme.WINDOW)
        self.body.pack(fill="both", expand=True, padx=theme.px(28), pady=theme.px(0, 22))

    def shown(self) -> None:
        pass


class ScrollingPage(Page):
    """A page of cards, which scrolls when taller than the window: fill `cards`."""

    def __init__(self, parent: tk.Misc, title: str):
        super().__init__(parent, title)
        scroll = VerticalScroll(self.body, bg=theme.WINDOW)
        scroll.pack(fill="both", expand=True)
        self.cards = scroll.inner

    def add_card(self, title: str) -> tk.Frame:
        outer, body = card(self.cards, title)
        outer.pack(fill="x", pady=theme.px(0, 16), padx=theme.px(0, 4))
        return body
