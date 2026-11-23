"""What the pages share: the settings,
the job runner, the releases, and the window's few services."""
from __future__ import annotations

from collections import deque
import logging
from pathlib import Path
from typing import Callable
import webbrowser

from botw_client.paths import DATA

from .. import settings as settings_file, versions
from ..core import updates, worlds
from ..options import Options
from .events import Signal, background, later
from .job_runner import JobRunner

logger = logging.getLogger(__name__)
TITLE = "BOTW Archipelago"


class Records(logging.Handler):
    """The launcher's log records, kept for the Logs page; delivered to the
    window's thread whatever thread logged them."""
    MAX = 5000

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
        self.kept: deque[tuple[int, str]] = deque(maxlen=self.MAX)
        self.added = Signal()

    def emit(self, record: logging.LogRecord) -> None:
        entry = (record.levelno, self.format(record))
        later(lambda: self._add(entry))

    def _add(self, entry: tuple[int, str]) -> None:
        """In the window's thread: kept and announced at once, so that a page
        filled from `kept` in between never shows it twice."""
        self.kept.append(entry)
        self.added.emit(*entry)


class Releases:
    """The releases on GitHub, as far as the last read knows, and what each
    plays (core/worlds.py): to open a seed this version cannot play."""

    def __init__(self, context: "Context"):
        self.context = context
        self.found: list[updates.Release] = []
        self.checking = False
        self.status = ""
        self.changed = Signal()

    def known(self) -> dict[str, dict | None]:
        """What each version that can play a seed here plays: the zips' and a newer botw.apworld."""
        return worlds.known(updates.usable(self.found), versions.installed())

    def check(self, then: Callable[[], None] | None = None) -> None:
        if self.checking:
            return
        self.checking = True

        def read(found: list[updates.Release]) -> None:
            self.found, self.status = found, ""
            finish()

        def failed(error: Exception) -> None:
            self.status = f"The releases could not be read: {error}"
            finish()

        def finish() -> None:
            self.checking = False
            self.changed.emit()
            if then is not None:
                then()
        background(lambda: updates.with_statements(updates.releases()), read, failed)

    def newer(self) -> updates.Release | None:
        """The release to update to, as far as the last read knows."""
        return updates.newer(self.found, self.context.settings.prereleases)

    def is_update(self, version: str) -> bool:
        """`version` is a newer botw.apworld: it replaces this one, it does not open beside."""
        release = updates.named(self.found, version)
        return release is not None and release.kind == "apworld"

    def update(self, release: updates.Release) -> None:
        """Replace the botw.apworld Archipelago loads by the release's; then
        Archipelago is to be opened again."""
        version = release.version
        if updates.installed_apworld() is None:
            self.context.notice.emit(
                f"Download botw.apworld {version} from the releases page, then install it with the Archipelago "
                "Launcher's Install APWorld.", [("Release page", lambda: webbrowser.open(release.page
                                                                                         or updates.RELEASES_PAGE))])
            return
        if self.context.jobs.busy:
            self.context.notice.emit(f"Wait for the current task to end, then install version {version}.", [])
            return

        def done(succeeded: bool, payload) -> None:
            if succeeded:
                self.context.notice.emit(
                    f"Version {version} is installed. Close Archipelago, this window and the Archipelago "
                    "Launcher, then open it again to use it.", [("Close this window", self.context.quit)])
            else:
                self.context.notice.emit(f"Version {version} was not installed: {payload}", [])
        from dataclasses import asdict
        self.context.jobs.start("install-apworld", {"release": asdict(release)},
                                f"Installing version {version}", done)

    def open_with(self, version: str, arguments: tuple[str, ...], why: str = "") -> None:
        """Open a seed with the launcher of `version`, installed first when needed;
        a newer botw.apworld is installed in place of this one."""
        installed = versions.find(version)
        if installed is not None:
            self._open(installed, arguments, why)
            return

        def found() -> None:
            release = updates.named(self.found, version)
            if release is None:
                self.context.notice.emit(f"Version {version} cannot be downloaded. {self.status} "
                                         f"It can be installed by hand from {updates.RELEASES_PAGE}.", [])
                return
            if release.kind == "apworld":
                self.update(release)
                return
            if self.context.jobs.busy:
                self.context.notice.emit(f"Wait for the current task to end, then open version {version}.", [])
                return

            def done(succeeded: bool, payload) -> None:
                if not succeeded:
                    self.context.notice.emit(f"Version {version} was not installed: {payload}", [])
                elif (made := versions.find(version)) is not None:
                    self._open(made, arguments, why)
            from dataclasses import asdict
            self.context.jobs.start("install-update", {"release": asdict(release)},
                                    f"Installing version {version}", done)
        if updates.named(self.found, version) is not None:
            found()
        else:
            self.check(found)

    def _open(self, version: versions.Installed, arguments: tuple[str, ...], why: str) -> None:
        question = (f"Open the seed with version {version.version}?\n\nThis window closes and the launcher "
                    "of that version opens, in a console window. Open BOTW Archipelago again to come back "
                    "to this version.")
        from .dialogs import ask
        if ask(None, f"Open version {version.version}?", f"{why}\n\n{question}" if why
                       else question, yes=f"Open version {version.version}"):
            self.context.restart(version.folder, arguments, DATA)


class Context:
    def __init__(self, options: Options, records: Records, entry: Callable, quit: Callable[[], None]):
        """`entry`: the jobs' child function (tk/job_runner.py); `quit`: closes the window."""
        self.options = options
        self.records = records
        self.settings = settings_file.load()
        self.jobs = JobRunner(entry)
        self.releases = Releases(self)
        self.seeds_changed = Signal()       # a seed was added, rebuilt or deleted
        self.notice = Signal()              # a sentence for the banner, and its actions [(text, call)]
        self._quit = quit

    def save_settings(self) -> None:
        try:
            settings_file.save(self.settings)
        except OSError as exc:
            logger.warning("settings not saved: %s", exc)

    def quit(self) -> None:
        self.save_settings()
        self._quit()

    def restart(self, folder: Path, arguments: tuple[str, ...] = (), data: Path | None = None) -> None:
        """Close this window and open the launcher of `folder` (an older version)."""
        self.save_settings()
        logger.info("opening %s", folder)
        versions.start(folder, list(arguments), data)
        self._quit()
