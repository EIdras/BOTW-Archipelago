"""Storage: where the data is, what takes room in it,
and what can be removed or moved."""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog

from botw_client.paths import DATA, RELEASE_MARKER, ROOT
from botw_client.version import VERSION

from ... import versions
from ...core import seeds, storage
from .. import dialogs, theme
from ..context import Context
from ..events import background
from ..widgets import Button, human_size, label, open_folder
from . import ScrollingPage


class StoragePage(ScrollingPage):
    def __init__(self, parent: tk.Misc, context: Context):
        super().__init__(parent, "Storage")
        self.context = context

        where = self.add_card("Data folder")
        label(where, str(DATA), wrap=True).pack(fill="x")
        self.free = label(where, role="muted")
        self.free.pack(fill="x", pady=theme.px(2, 0))
        buttons = tk.Frame(where, bg=theme.SURFACE)
        buttons.pack(fill="x", pady=theme.px(12, 0))
        Button(buttons, "Open", lambda: open_folder(DATA)).pack(side="left")
        refusal = storage.relocation_refusal()
        self.move_button = Button(buttons, "Move to another folder...", self.move)
        self.move_button.set(enabled=refusal is None)
        self.move_button.pack(side="left", padx=theme.px(8, 0))
        if refusal:
            label(where, refusal, "muted", wrap=True).pack(fill="x", pady=theme.px(8, 0))

        used = self.add_card("What takes room")
        self.table = tk.Frame(used, bg=theme.SURFACE)
        self.table.pack(fill="x")
        self.table.columnconfigure(1, weight=1)
        buttons = tk.Frame(used, bg=theme.SURFACE)
        buttons.pack(fill="x", pady=theme.px(12, 0))
        self.unused_button = Button(buttons, "Remove unused game packs", self.remove_unused_packs)
        self.unused_button.pack(side="left")
        Button(buttons, "Measure again", self.measure).pack(side="left", padx=theme.px(8, 0))

        kept = self.add_card("Installed versions")
        label(kept, "Updates are installed next to each other. An older version is only needed for a seed the "
                    "current one cannot play.", "muted", wrap=True).pack(fill="x")
        self.versions = tk.Frame(kept, bg=theme.SURFACE)
        self.versions.pack(fill="x", pady=theme.px(8, 0))

        # Measuring walks the game profile's thousands of files: done when the page is
        # first shown, then again only once something may have changed it.
        self.stale = True
        context.jobs.finished.connect(self._changed)
        context.seeds_changed.connect(self._changed)

    def _changed(self, *_signal) -> None:
        self.stale = True
        if self.current:
            self.shown()

    def shown(self) -> None:
        self.free.configure(text=f"{human_size(storage.free_space(DATA))} free on this drive")
        self._list_versions()
        if self.stale:
            self.measure()

    def measure(self) -> None:
        self.stale = False
        self._clear(self.table)
        label(self.table, "Measuring...", "muted").grid(row=0, column=0, sticky="w")
        background(storage.usage, self._measured,
                   lambda error: self._show_rows([], f"Not measured: {error}"))

    def _measured(self, rows: list[storage.Usage]) -> None:
        self._show_rows(rows)

    def _show_rows(self, rows: list[storage.Usage], problem: str = "") -> None:
        self._clear(self.table)
        if problem:
            label(self.table, problem, "error", wrap=True).grid(row=0, column=0, columnspan=3, sticky="ew")
            return
        for index, usage in enumerate(rows):
            label(self.table, usage.label).grid(row=index, column=0, sticky="w", padx=theme.px(0, 18), pady=theme.px(2))
            label(self.table, usage.hint, "muted").grid(row=index, column=1, sticky="w", pady=theme.px(2))
            label(self.table, human_size(usage.size)).grid(row=index, column=2, sticky="e", pady=theme.px(2))
        tk.Frame(self.table, bg=theme.BORDER, height=1).grid(row=len(rows), column=0, columnspan=3, sticky="ew",
                                                             pady=theme.px(6, 4))
        total = sum(usage.size for usage in rows)
        label(self.table, "Total", "heading").grid(row=len(rows) + 1, column=0, sticky="w")
        label(self.table, human_size(total), "heading").grid(row=len(rows) + 1, column=2, sticky="e")

    def _list_versions(self) -> None:
        self._clear(self.versions)
        found = versions.installed()
        if not any(version.running for version in found):
            where = "release" if (ROOT / RELEASE_MARKER).is_file() else "from the source code"
            label(self.versions, f"Version {VERSION}  (running, {where})").pack(fill="x", pady=theme.px(3))
        for version in found:
            line = tk.Frame(self.versions, bg=theme.SURFACE)
            line.pack(fill="x", pady=theme.px(2))
            label(line, f"Version {version.version}" + ("  (running)" if version.running else "")).pack(side="left")
            remove = Button(line, "Remove", lambda version=version: self.remove_version(version), "danger")
            remove.set(enabled=not version.running)
            remove.pack(side="right")

    @staticmethod
    def _clear(frame: tk.Frame) -> None:
        for child in frame.winfo_children():
            child.destroy()

    def remove_unused_packs(self) -> None:
        count, freed = seeds.remove_unused_packs()
        self.context.notice.emit(f"Removed {count} unused game pack{'s' if count != 1 else ''} "
                                 f"({human_size(freed)})." if count else "No unused game pack to remove.", [])
        self.measure()

    def remove_version(self, version: versions.Installed) -> None:
        if not dialogs.ask(self, f"Remove version {version.version}?", "A seed only that version can play will "
                           "need it installed again.", yes="Remove", danger=True):
            return
        try:
            versions.remove(version)
        except (OSError, ValueError) as exc:
            dialogs.tell(self, f"Version {version.version} was not removed", str(exc), "warning")
        self._changed()

    def move(self) -> None:
        picked = filedialog.askdirectory(title="Move the launcher's data to...", parent=self)
        if not picked:
            return
        target = storage.destination(Path(picked))
        refusal = storage.relocation_refusal(target)
        if refusal or self.context.jobs.busy:
            dialogs.tell(self, "The data cannot be moved there", refusal or "Wait for the current task to end.",
                         "warning")
            return
        if dialogs.ask(self, "Move the data?", f"Everything goes to\n{target}\n\nThe game profile, your seeds "
                       "and your saves are copied there, checked, then removed from the current folder. The "
                       "window closes when it is done.", yes="Move"):
            self.context.jobs.start("move-data", {"target": str(target)}, "Moving the data", self._moved)

    def _moved(self, succeeded: bool, payload) -> None:
        if not succeeded:
            dialogs.tell(self, "The data was not moved", f"{payload}\n\nNothing was changed.", "warning")
            return
        # This process still reads the old folder: every path is settled at start.
        dialogs.tell(self, "The data is moved", "The window closes now: open BOTW Archipelago again.")
        self.context.quit()
