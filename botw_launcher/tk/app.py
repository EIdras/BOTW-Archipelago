"""The window: a sidebar of pages, a banner for notices, the pages, and the
bar of the task that runs. tk comes with every Python, Archipelago's own
included: this is the window the Archipelago launcher opens."""
from __future__ import annotations

import logging
from pathlib import Path
import shutil
import sys
import tkinter as tk
from tkinter import messagebox, ttk
import traceback
import webbrowser
from typing import Callable

from botw_client.paths import ROOT
from botw_client.version import VERSION

from .. import logs, versions
from ..core import output, seeds, storage, updates
from ..options import Options
from ..versions import RELEASE_MARKER
from . import dialogs, events, theme
from .context import TITLE, Context, Records
from .events import background
from .pages import Page
from .pages.help import HelpPage
from .pages.hints import HintsPage
from .pages.logs import LogsPage
from .pages.play import JOB as PLAY_JOB, PlayPage
from .pages.settings import SettingsPage
from .pages.storage import StoragePage
from .widgets import Button, human_size, label

logger = logging.getLogger(__name__)
ICON = Path(__file__).resolve().parents[1] / "assets" / "icon.png"
APP_ID = "BOTWArchipelago.Launcher"
SIDEBAR_WIDTH = 210
MIN_SIZE = (900, 600)


class Banner(tk.Frame):
    """A notice above the pages, with its actions and a close button."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent, bg=theme.SELECTED)
        self.text = label(self, wrap=True, bg=theme.SELECTED)
        self.text.pack(side="left", fill="x", expand=True, padx=theme.px(14, 8), pady=theme.px(10))
        self.actions = tk.Frame(self, bg=theme.SELECTED)
        self.actions.pack(side="left", padx=theme.px(0, 8))
        Button(self, "✕", self.hide, "nav-current", padding=(10, 5)).pack(side="right", padx=theme.px(0, 8))

    def show_notice(self, text: str, actions: list[tuple[str, Callable[[], None]]] = ()) -> None:
        self.text.configure(text=text)
        for child in self.actions.winfo_children():
            child.destroy()
        for index, (name, call) in enumerate(actions):
            Button(self.actions, name, lambda call=call: (self.hide(), call()),
                   "secondary" if index else "primary").pack(side="left", padx=theme.px(8, 0))
        self.pack(fill="x", padx=theme.px(28), pady=theme.px(14, 0), before=self.master.pages)

    def hide(self) -> None:
        self.pack_forget()


class ActivityBar(tk.Frame):
    """The task that runs: its title, its last line, its progress, and Cancel."""

    def __init__(self, parent: tk.Misc, cancel: Callable[[], None]):
        super().__init__(parent, bg=theme.SURFACE, highlightthickness=1, highlightbackground=theme.BORDER)
        text = tk.Frame(self, bg=theme.SURFACE)
        text.pack(side="left", fill="x", expand=True, padx=theme.px(28, 12), pady=theme.px(10))
        self.title = label(text, role="heading")
        self.title.pack(fill="x")
        self.detail = label(text, role="muted")
        self.detail.pack(fill="x")
        self.bar = ttk.Progressbar(text, mode="indeterminate", style="Horizontal.TProgressbar")
        self.bar.pack(fill="x", pady=theme.px(6, 0))
        self.cancel = Button(self, "Cancel", cancel)
        self.cancel.pack(side="right", padx=theme.px(0, 28))

    def begin(self, title: str) -> None:
        self.title.configure(text=title)
        self.detail.configure(text="")
        self.bar.configure(mode="indeterminate", value=0)
        self.bar.start(15)
        self.bar.pack(fill="x", pady=theme.px(6, 0))
        self.cancel.set(text="Cancel")
        self.pack(side="bottom", fill="x", before=self.master.pages)

    def progress(self, step: int, steps: int, name: str) -> None:
        self.bar.stop()
        self.bar.configure(mode="determinate", maximum=max(steps, 1), value=step)
        self.detail.configure(text=name)

    def settle(self, text: str) -> None:
        """A session plays: no more progress to show, and Cancel stops the client."""
        self.bar.stop()
        self.bar.pack_forget()
        self.title.configure(text=text)
        self.detail.configure(text="")
        self.cancel.set(text="Stop the client")

    def hide(self) -> None:
        self.bar.stop()
        self.pack_forget()


class MainWindow:
    def __init__(self, root: tk.Tk, context: Context):
        self.root, self.context = root, context
        self._playing = False
        root.title(TITLE)
        self.scale = scale = root.winfo_fpixels("1i") / 96
        width, height = context.settings.window_size
        root.geometry(f"{round(max(width, MIN_SIZE[0]) * scale)}x{round(max(height, MIN_SIZE[1]) * scale)}")
        root.minsize(*(round(size * scale) for size in MIN_SIZE))

        sidebar = tk.Frame(root, bg=theme.SIDEBAR, width=round(SIDEBAR_WIDTH * scale))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        label(sidebar, TITLE, "brand").pack(anchor="w", padx=theme.px(20), pady=theme.px(22, 16))
        main = tk.Frame(root, bg=theme.WINDOW)
        main.pack(side="left", fill="both", expand=True)
        self.activity = ActivityBar(main, self._cancel)
        self.pages = tk.Frame(main, bg=theme.WINDOW)
        main.pages = self.pages
        self.banner = Banner(main)
        self.pages.pack(fill="both", expand=True)

        self.play_page = PlayPage(self.pages, context)
        entries: list[tuple[str, Page]] = [
            ("Play", self.play_page),
            ("Hints", HintsPage(self.pages, context, self.play_page)),
            ("Storage", StoragePage(self.pages, context)),
            ("Logs", LogsPage(self.pages, context)),
            ("Settings", SettingsPage(self.pages, context)),
        ]
        self.help_page = HelpPage(self.pages, context)
        self.nav: dict[str, tuple[Button, Page]] = {}
        for name, page in entries:
            button = Button(sidebar, name, lambda name=name: self.show(name), "nav",
                            width=round((SIDEBAR_WIDTH - 24) * scale),
                            anchor="w", padding=(14, 8))
            button.pack(padx=theme.px(12), pady=theme.px(1))
            self.nav[name] = (button, page)
        label(sidebar, f"Version {VERSION}", "small", bg=theme.SIDEBAR).pack(side="bottom", anchor="w", padx=theme.px(20),
                                                                            pady=theme.px(6, 16))
        help_button = Button(sidebar, "Help", lambda: self.show("Help"), "nav",
                             width=round((SIDEBAR_WIDTH - 24) * scale),
                             anchor="w", padding=(14, 8))
        help_button.pack(side="bottom", padx=theme.px(12))
        self.nav["Help"] = (help_button, self.help_page)
        for _button, page in self.nav.values():
            page.place(relx=0, rely=0, relwidth=1, relheight=1)

        context.notice.connect(self.banner.show_notice)
        context.jobs.started.connect(self._job_started)
        context.jobs.event.connect(self._job_event)
        context.jobs.line.connect(self._job_line)
        context.jobs.finished.connect(self._job_finished)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._keys()
        self.show("Play")
        root.after(0, self._after_start)

    def _keys(self) -> None:
        """Up and Down walk the seeds, Ctrl+O adds one, Alt+Left goes back in
        Help, Ctrl+1 to Ctrl+5 open the pages, Escape closes the notice."""
        root = self.root

        def typing() -> bool:
            return isinstance(root.focus_get(), (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text))

        def on_seeds() -> bool:
            play = self.play_page
            return play.current and play.view is play.seeds and not typing()

        self.shortcuts = {
            "<Up>": lambda: self.play_page.seeds.step(-1) if on_seeds() else None,
            "<Down>": lambda: self.play_page.seeds.step(1) if on_seeds() else None,
            "<Control-o>": lambda: self.play_page.seeds.choose_file() if on_seeds() else None,
            "<Alt-Left>": lambda: self.help_page.back() if self.help_page.current else None,
            "<Escape>": self.banner.hide,
            **{f"<Control-Key-{index}>": lambda name=name: self.show(name) for index, name in enumerate(self.nav, 1)},
        }
        for key, action in self.shortcuts.items():
            root.bind(key, lambda _event, action=action: action())

    def show(self, name: str) -> None:
        for other, (button, page) in self.nav.items():
            button.set(kind="nav-current" if other == name else "nav")
            page.current = other == name
        page = self.nav[name][1]
        page.tkraise()
        page.shown()

    def watch(self, requests: Callable[[], list[list[str]]]) -> None:
        """Later launches while this window is open: it comes forward and adds
        the seed file they carry (the apworld's single window)."""
        for arguments in requests():
            self.come_forward()
            options = Options.parse(arguments)
            if options.file is not None:
                self.show("Play")
                self.play_page.add_file(options.file)
        self.root.after(500, self.watch, requests)

    def come_forward(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(300, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    # ---- start --------------------------------------------------------------

    def _after_start(self) -> None:
        options = self.context.options
        if options.file is not None:
            self.play_page.add_file(options.file)
        background(self._tidy, self._tidied)
        if self.context.settings.check_updates:
            self.context.releases.check(self._announce)

    def _announce(self) -> None:
        """A newer release, once at start, unless the player said no to it."""
        settings = self.context.settings
        newer = self.context.releases.newer()
        if newer is None or newer.version == settings.skipped_version:
            return

        def skip() -> None:
            settings.skipped_version = newer.version
            self.context.save_settings()
        actions = [("Release notes", lambda: webbrowser.open(newer.page or updates.RELEASES_PAGE)),
                   ("Not this one", skip)]
        if updates.installed_apworld() is not None:
            actions.insert(0, ("Install", lambda: self.context.releases.update(newer)))
        self.context.notice.emit(f"Version {newer.version} is out.", actions)

    @staticmethod
    def _tidy() -> tuple[int, int]:
        """A move of the data finished, unfinished installations and the packs no
        seed uses removed: never in a source checkout."""
        if not (ROOT / RELEASE_MARKER).is_file():
            return 0, 0
        try:
            storage.finish_relocation()
        except OSError as exc:
            logger.warning("the previous data folder is not removed yet: %s", exc)
        for folder in versions.unfinished():
            logger.info("removing an unfinished installation: %s", folder)
            shutil.rmtree(folder, ignore_errors=True)
        return seeds.remove_unused_packs()

    @staticmethod
    def _tidied(removed: tuple[int, int]) -> None:
        count, freed = removed
        if count:
            logger.info("removed %d game pack(s) no seed uses any more (%s)", count, human_size(freed))

    # ---- the running job ----------------------------------------------------

    def _cancel(self) -> None:
        if self._playing and not dialogs.ask(
                self.root, "Stop the client?", "Close Cemu instead to end the session and save its progress.",
                yes="Stop the client", no="Keep playing", danger=True):
            return
        self.context.jobs.cancel()

    def _job_started(self, _name: str, title: str) -> None:
        self._playing = False
        self.activity.begin(title)

    def _job_event(self, event: dict) -> None:
        if event["event"] == "progress":
            self.activity.progress(event["step"], event["steps"], event["label"])
        elif event["event"] == "stage" and event.get("stage") == output.CEMU:
            self._playing = True
            self.activity.settle("Playing: close Cemu to end the session")

    def _job_line(self, text: str) -> None:
        if not self._playing and text.strip():
            self.activity.detail.configure(text=text.strip()[:140])

    def _job_finished(self, *_outcome) -> None:
        self._playing = False
        self.activity.hide()

    # ---- closing ------------------------------------------------------------

    def close(self) -> None:
        jobs = self.context.jobs
        if jobs.busy:
            if jobs.name == PLAY_JOB and self._playing:
                title, text = ("A play session is running", "Close Cemu first: the session then ends by itself "
                               "and saves its progress. Quitting now stops the client at once, without that.")
            else:
                title, text = "A task is in progress", "Quitting cancels it."
            if not dialogs.ask(self.root, title, text, yes="Quit anyway", no="Stay", danger=True):
                return
            jobs.cancel()
        self.context.settings.window_size = [round(self.root.winfo_width() / self.scale),
                                             round(self.root.winfo_height() / self.scale)]
        self.context.save_settings()
        self.root.destroy()


def run(arguments: list[str], entry: Callable | None = None,
        requests: Callable[[], list[list[str]]] | None = None) -> int:
    """Open the window and run until it closes. `entry`: the jobs' child
    function (tk/child.py run by default). `requests`: the arguments of later
    launches, polled (the apworld keeps one window open)."""
    if entry is None:
        from .child import run as entry
    records = Records()     # first: the log's opening line is on the Logs page too
    logging.getLogger(logs.ROOT_LOGGER).addHandler(records)
    logs.setup()
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        try:     # drawn at the screen's scale, not stretched blurry by Windows
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk(className="BOTW Archipelago")
    theme.apply(root)
    try:
        icon = tk.PhotoImage(file=str(ICON))
        root.iconphoto(True, icon)
    except tk.TclError:
        pass
    root.report_callback_exception = _report_unexpected
    context = Context(Options.parse(arguments), records, entry, root.destroy)
    window = MainWindow(root, context)
    if requests is not None:
        root.after(500, window.watch, requests)
    theme.dark_title_bar(root)
    events.pump(root)
    root.mainloop()
    return 0


def _report_unexpected(kind, error, trace) -> None:
    logger.error("unexpected error\n%s", "".join(traceback.format_exception(kind, error, trace)))
    text = f"{error!r}\n\nThe details are in the logs folder; they help a bug report."
    try:
        dialogs.tell(tk._default_root, "Something unexpected happened", text, "error")
    except tk.TclError:     # the window itself is what failed
        messagebox.showerror(TITLE, f"Something unexpected happened: {text}")
