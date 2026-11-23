"""The Hints page: what the room has hinted for this slot, and asking for more.

The client follows the slot's hints in the room (botw_client/protocol.py
observer) during a play session; the page keeps the last ones in the seed's
folder, to be read when no session runs. Asking goes through the session's
console, as a player types it in the room's chat: it costs hint points.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from .. import theme
from ..context import Context
from ..widgets import Button, label
from . import Page
from .play import PlayPage

logger = logging.getLogger(__name__)

FILE = "hints.json"
SUGGESTIONS = 300
COLUMNS = (("item", "Item", 170), ("receiving", "For", 100), ("location", "Location", 220),
           ("finding", "In the world of", 110), ("entrance", "Entrance", 80), ("status", "Status", 80))
STATUS = {10: "No priority", 20: "Avoid", 30: "Priority", 40: "Found"}
SHOWN = ("All hints", "Your items", "In your world")


def names() -> tuple[list[str], list[str]]:
    """The world's item and location names, offered while typing."""
    from tools.build_poptracker import catalog
    world = catalog()
    items = sorted({row["name"] for row in world.ITEMS})
    locations = sorted({row["name"] for row in world.LOCATIONS} | {row["name"] for row in world.CHESTS})
    return items, locations


def save(folder: Path, hints: list[dict]) -> None:
    try:
        (folder / FILE).write_text(json.dumps(hints, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("hints not kept: %s", exc)


def load(folder: Path) -> list[dict]:
    try:
        hints = json.loads((folder / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [hint for hint in hints if isinstance(hint, dict)] if isinstance(hints, list) else []


class HintsPage(Page):
    def __init__(self, parent: tk.Misc, context: Context, play: PlayPage):
        super().__init__(parent, "Hints")
        self.context, self.play = context, play
        self.hints: list[dict] = []
        self.seed_name = ""
        self.live = False
        self._names: tuple[list[str], list[str]] | None = None

        ask = tk.Frame(self.body, bg=theme.WINDOW)
        ask.pack(fill="x")
        self.kind = tk.StringVar(value="item")
        for value, text in (("item", "An item of yours"), ("location", "A location of your world")):
            ttk.Radiobutton(ask, text=text, value=value, variable=self.kind, style="Page.TRadiobutton",
                            command=self._suggest).pack(side="left", padx=theme.px(0, 14))
        line = tk.Frame(self.body, bg=theme.WINDOW)
        line.pack(fill="x", pady=theme.px(8, 0))
        self.name = ttk.Combobox(line)
        self.name.pack(side="left", fill="x", expand=True, padx=theme.px(0, 8))
        self.name.bind("<KeyRelease>", self._typed)
        self.name.bind("<Return>", lambda _e: self.ask())
        self.ask_button = Button(line, "Ask for a hint", self.ask, "primary")
        self.ask_button.pack(side="left")
        self.note = label(self.body, role="muted", wrap=True)
        self.note.pack(fill="x", pady=theme.px(6, 14))

        view = tk.Frame(self.body, bg=theme.WINDOW)
        view.pack(fill="x", pady=theme.px(0, 8))
        self.state = label(view, role="muted")
        self.state.pack(side="left")
        self.hide_found = tk.BooleanVar(value=False)
        ttk.Checkbutton(view, text="Hide found", variable=self.hide_found, command=self.refresh,
                        style="Page.TCheckbutton").pack(side="right")
        self.shown_kind = tk.StringVar(value=SHOWN[0])
        ttk.Combobox(view, textvariable=self.shown_kind, values=SHOWN, state="readonly",
                     width=16).pack(side="right", padx=theme.px(0, 14))
        self.shown_kind.trace_add("write", lambda *_: self.refresh())

        table = tk.Frame(self.body, bg=theme.FIELD, highlightthickness=1, highlightbackground=theme.BORDER)
        table.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table, columns=[key for key, _t, _w in COLUMNS], show="headings",
                                  selectmode="browse")
        for key, text, width in COLUMNS:
            self.table.heading(key, text=text, anchor="w")
            self.table.column(key, width=theme.px(width), minwidth=theme.px(60), anchor="w", stretch=True)
        for kind, colour in theme.ITEMS.items():
            self.table.tag_configure(kind, foreground=colour)
        self.table.tag_configure("found", foreground=theme.MUTED)
        bar = ttk.Scrollbar(table, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.table.pack(side="left", fill="both", expand=True)

        play.session.hints.connect(self.update_hints)
        context.jobs.started.connect(lambda *_: self._ready())
        context.jobs.finished.connect(lambda *_: self._finished())
        context.jobs.event.connect(lambda event: self._ready() if event.get("event") == "stage" else None)

    # --- What the room says --------------------------------------------------

    def update_hints(self, hints: list[dict]) -> None:
        """The slot's hints, as the room has them now (a play session)."""
        seed = self.play.session.seed
        self.hints, self.live = list(hints), True
        if seed is not None:
            self.seed_name = seed.name
            save(seed.folder, self.hints)
        self.refresh()

    def _finished(self) -> None:
        self.live = False
        self._ready()
        self.refresh()

    def shown(self) -> None:
        if not self.live:
            selected = self.play.seeds.selected
            if selected is not None and selected.name != self.seed_name:
                self.seed_name, self.hints = selected.name, load(selected.folder)
        self._ready()
        self._suggest()
        self.refresh()

    def visible(self) -> list[dict]:
        """The hints shown, as the filters choose them: the ones still to find first."""
        shown = self.shown_kind.get()
        rows = [hint for hint in self.hints
                if (shown != SHOWN[1] or hint.get("mine")) and (shown != SHOWN[2] or hint.get("in_my_world"))
                and not (self.hide_found.get() and hint.get("found"))]
        return sorted(rows, key=lambda hint: (bool(hint.get("found")), -int(hint.get("status") or 0),
                                              str(hint.get("item", "")).lower()))

    def refresh(self) -> None:
        self.table.delete(*self.table.get_children())
        for hint in self.visible():
            found = bool(hint.get("found"))
            status = "Found" if found else STATUS.get(int(hint.get("status") or 0), "")
            values = [hint.get(key, "") for key, _t, _w in COLUMNS[:-1]] + [status]
            tag = "found" if found else theme.item_kind(int(hint.get("flags") or 0))
            self.table.insert("", "end", values=values, tags=(tag,))
        total, left = len(self.hints), sum(1 for hint in self.hints if not hint.get("found"))
        if not self.seed_name:
            text = "No seed chosen: the hints of the seed selected on the Play page show here."
        elif not self.hints:
            text = (f"No hint yet for seed {self.seed_name}." if self.live else
                    f"No hint known for seed {self.seed_name}: they show here once you play it.")
        else:
            when = "in the room now" if self.live else "when you last played"
            text = f"Seed {self.seed_name}: {total} hints, {left} still to find ({when})."
        self.state.configure(text=text)

    # --- Asking for one ------------------------------------------------------

    def ask(self) -> None:
        name = self.name.get().strip()
        if not name:
            self.name.focus_set()
            return
        if self.play.session.ask_hint(self.kind.get() == "location", name):
            self.note.configure(text=f"Asked for {name}: the room's answer shows in the session's log, "
                                     "and the hint here.", fg=theme.MUTED)
            self.name.set("")
        else:
            self._ready()

    def _ready(self) -> None:
        if self.play.session.can_ask():
            self.ask_button.set(enabled=True)
            self.note.configure(text="A hint costs hint points, as in the room's chat; the room says how "
                                     "many you have.", fg=theme.MUTED)
        else:
            self.ask_button.set(enabled=False)
            self.note.configure(text="Hints are asked during a play session, once Cemu has started.",
                                fg=theme.MUTED)

    def _suggest(self) -> None:
        self._typed()

    def _typed(self, event=None) -> None:
        if event is not None and event.keysym in ("Return", "Up", "Down", "Escape"):
            return
        if self._names is None:
            try:
                self._names = names()
            except Exception as exc:  # noqa: BLE001 - suggestions are a help, not a need
                logger.warning("no names to suggest: %s", exc)
                self._names = ([], [])
        items, locations = self._names
        typed = self.name.get().strip().lower()
        pool = locations if self.kind.get() == "location" else items
        self.name.configure(values=[name for name in pool if typed in name.lower()][:SUGGESTIONS])
