"""Logs: what the launcher did, as much of it as the
player wants to see, and the archive to send with a bug report."""
from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from ... import logs
from ...core import seeds
from .. import dialogs, theme
from ..context import Context
from ..widgets import Button, LogView, label, open_folder
from . import Page

# What the player chooses, and the level it shows from.
CHOICES = (("Errors only", "ERROR"), ("Warnings and errors", "WARNING"),
           ("Main steps", "INFO"), ("Everything", "DEBUG"))


class LogsPage(Page):
    def __init__(self, parent: tk.Misc, context: Context):
        super().__init__(parent, "Logs")
        self.context = context
        names = [text for text, _level in CHOICES]
        levels = [level for _text, level in CHOICES]
        chosen = context.settings.log_level if context.settings.log_level in levels else "INFO"
        self.level = tk.StringVar(value=names[levels.index(chosen)])
        choice = ttk.Combobox(self.header, textvariable=self.level, values=names, state="readonly", width=20)
        choice.bind("<<ComboboxSelected>>", lambda _e: self._level_changed())
        choice.pack(side="right")
        label(self.header, "Show", "muted").pack(side="right", padx=theme.px(0, 8))

        bottom = tk.Frame(self.body, bg=theme.WINDOW)
        bottom.pack(side="bottom", fill="x", pady=theme.px(12, 0))
        Button(bottom, "Open the logs' folder", lambda: open_folder(logs.FOLDER)).pack(side="left")
        Button(bottom, "Save a diagnostic...", self.export).pack(side="left", padx=theme.px(8, 0))
        label(bottom, "The full log is always written to the file, whatever is shown here.",
              "muted").pack(side="left", padx=theme.px(14, 0))
        self.view = LogView(self.body)
        self.view.pack(fill="both", expand=True)
        context.records.added.connect(self._added)
        self._fill()

    def _threshold(self) -> int:
        level = dict(CHOICES)[self.level.get()]
        return logging.getLevelName(level)

    def _fill(self) -> None:
        self.view.clear()
        threshold = self._threshold()
        for level, line in self.context.records.kept:
            if level >= threshold:
                self.view.add(line)

    def _added(self, level: int, line: str) -> None:
        if level >= self._threshold():
            self.view.add(line)

    def _level_changed(self) -> None:
        self.context.settings.log_level = dict(CHOICES)[self.level.get()]
        self.context.save_settings()
        self._fill()

    def export(self) -> None:
        """A zip of the logs and of the last session of the seed last selected."""
        chosen = filedialog.asksaveasfilename(
            title="Save a diagnostic", parent=self, initialdir=str(Path.home()), defaultextension=".zip",
            initialfile=f"botw-archipelago-diagnostic-{datetime.now():%Y%m%d-%H%M%S}.zip",
            filetypes=[("Zip", "*.zip")])
        if not chosen:
            return
        seed = self.context.settings.last_seed
        try:
            logs.export_diagnostic(Path(chosen), seeds.folder_of(seed) if seed else None)
        except OSError as exc:
            dialogs.tell(self, "The diagnostic was not saved", str(exc), "warning")
            return
        dialogs.tell(self, "Diagnostic saved", f"{chosen}\n\nIt holds the launcher's logs and settings and the last "
                                   "session of your last seed. Folder names of this computer appear in it; no "
                                   "password does.")
