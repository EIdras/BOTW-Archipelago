"""Settings: updates, the PopTracker pack, the game
profile, and what this version is."""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk
import webbrowser

from botw_client.paths import RELEASE_MARKER, ROOT
from botw_client.version import VERSION

from ...core import profile, updates
from .. import theme
from ..context import Context
from ..widgets import Button, label, open_folder
from . import ScrollingPage


class SettingsPage(ScrollingPage):
    def __init__(self, parent: tk.Misc, context: Context):
        super().__init__(parent, "Settings")
        self.context = context
        self._updates(self.add_card("Updates"))
        self._tracker(self.add_card("PopTracker pack"))
        self._profile(self.add_card("Game profile"))
        context.releases.changed.connect(self._show_update)
        context.jobs.finished.connect(self._job_finished)

    def _job_finished(self, *_outcome) -> None:
        if self.current:
            self.shown()

    def shown(self) -> None:
        self._show_update()
        self._show_tracker()
        self._show_profile()

    @staticmethod
    def _buttons(parent: tk.Misc, *buttons: tuple[str, object]) -> list[Button]:
        line = tk.Frame(parent, bg=theme.SURFACE)
        line.pack(fill="x", pady=theme.px(12, 0))
        made = []
        for index, (text, command) in enumerate(buttons):
            button = Button(line, text, command)
            button.pack(side="left", padx=theme.px(8 if index else 0, 0))
            made.append(button)
        return made

    # ---- updates ------------------------------------------------------------

    def _updates(self, card: tk.Frame) -> None:
        kind = "release" if (ROOT / RELEASE_MARKER).is_file() else "from the source code"
        label(card, f"BOTW Archipelago {VERSION} ({kind})").pack(fill="x")
        self.update_status = label(card, role="muted", wrap=True)
        self.update_status.pack(fill="x", pady=theme.px(2, 0))
        self.check_button, _notes, self.install_button = self._buttons(
            card, ("Check now", self.context.releases.check),
            ("Release notes", lambda: webbrowser.open(updates.RELEASES_PAGE)),
            ("Install", self._install))
        for text, name in (("Look for updates when the launcher starts", "check_updates"),
                           ("Offer pre-releases too", "prereleases")):
            self._option(card, text, name)

    def _option(self, parent: tk.Misc, text: str, name: str) -> None:
        value = tk.BooleanVar(value=getattr(self.context.settings, name))

        def changed(*_args) -> None:
            setattr(self.context.settings, name, value.get())
            self.context.save_settings()
            self._show_update()
        value.trace_add("write", changed)
        box = ttk.Checkbutton(parent, text=text, variable=value)
        box.pack(anchor="w", pady=theme.px(8, 0) if name == "check_updates" else 0)
        box.value = value           # kept with its box

    def _show_update(self) -> None:
        releases = self.context.releases
        if releases.checking:
            status = "Looking for updates..."
        elif releases.status:
            status = releases.status
        elif not releases.found:
            status = "Not checked yet."
        elif (newer := releases.newer()) is not None and updates.installed_apworld() is not None:
            status = f"Version {newer.version} is out: Install replaces this one in Archipelago."
        elif newer is not None:
            status = (f"Version {newer.version} is out: download its botw.apworld from the release notes, then "
                      "install it with the Archipelago Launcher's Install APWorld.")
        else:
            status = "This is the newest version."
        self.update_status.configure(text=status)
        self.check_button.set(enabled=not releases.checking)
        installable = (updates.installed_apworld() is not None and not releases.checking
                       and releases.newer() is not None)
        self.install_button.set(text=f"Install version {releases.newer().version}" if installable else "Install",
                                kind="primary", enabled=installable and not self.context.jobs.busy)
        if installable:
            self.install_button.pack(side="left", padx=theme.px(8, 0))
        else:
            self.install_button.pack_forget()

    def _install(self) -> None:
        newer = self.context.releases.newer()
        if newer is not None:
            self.context.releases.update(newer)

    # ---- PopTracker ---------------------------------------------------------

    def _tracker(self, card: tk.Frame) -> None:
        label(card, "PopTracker is an optional map tracker that follows the room. Its pack for this game is "
                    "built here, from your own game files.", "muted", wrap=True).pack(fill="x")
        self.tracker_status = label(card, wrap=True)
        self.tracker_status.pack(fill="x", pady=theme.px(8, 0))
        self.tracker_button, self.tracker_folder = self._buttons(
            card, ("Build the pack", self._build_tracker),
            ("Open its folder", lambda: open_folder(self._tracker_pack().parent)))

    @staticmethod
    def _tracker_pack() -> Path:
        # Imported when needed: the module draws icons and loads numpy.
        from tools import build_poptracker
        return build_poptracker.PACK_FOLDER / f"{build_poptracker.PACK_NAME}.zip"

    def _show_tracker(self) -> None:
        pack = self._tracker_pack()
        built = pack.is_file()
        self.tracker_status.configure(text=f"Built: {pack}\nIt is kept up to date each time you play."
                                      if built else "Not built.")
        self.tracker_button.set(text="Build it again" if built else "Build the pack",
                                enabled=profile.exists() and not self.context.jobs.busy)
        self.tracker_folder.set(enabled=built)

    def _build_tracker(self) -> None:
        def done(succeeded: bool, payload) -> None:
            if not succeeded:
                self.context.notice.emit(f"The PopTracker pack was not built: {payload}", [])
        self.context.jobs.start("poptracker", {}, "Building the PopTracker pack", done)

    # ---- the game profile ---------------------------------------------------

    def _profile(self, card: tk.Frame) -> None:
        self.profile_facts = label(card, wrap=True)
        self.profile_facts.pack(fill="x")
        (self.profile_folder,) = self._buttons(card, ("Open its folder",
                                                      lambda: open_folder(profile.summary().folder)))

    def _show_profile(self) -> None:
        summary = profile.summary()
        self.profile_folder.set(enabled=summary is not None)
        self.profile_facts.configure(
            text=f"Copied from: {summary.source_cemu}\nGame: {summary.game}\nYour saves of the Archipelago game "
                 "are in this profile, apart from your own Cemu's." if summary
            else "Not created yet: the Play page makes it.")
