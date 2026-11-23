"""The versions of the project installed side by side by the launcher's updates.

An update never replaces the files of the version that runs: each one is a
whole release folder of its own (its Python included), in the data folder:

    <data>/versions/<version>/      a release, as its zip unpacks
    <data>/versions/<version>/installed.json    written last: without it the
                                    folder is an installation that did not finish

The release the player unzipped stays where it is and is never modified; at
start it hands over to the newest installed version (botw_launcher/handoff.py).
Older versions are kept until the player removes them: a seed the current
version cannot play any more is played with a version of its world
(core/worlds.py). The versions before this launcher have a console one
(tools/launcher.py), opened in a console window of its own.

Every version reads the same data folder. What makes this safe is that a seed's
game pack is built again whenever another version than the one that built it
plays the seed (tools/play_mods.py fresh_pack).
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from botw_client.paths import DATA, DATA_VARIABLE, RELEASE_MARKER, ROOT
from botw_client.version import VERSION, parse

VERSIONS = DATA / "versions"
COMPLETE = "installed.json"
ENTRY = "botw_launcher/__main__.py"
CONSOLE_ENTRY = "tools/launcher.py"     # the launcher of the versions before this one
# Set for a launcher that must stay the version it is: one a handoff started,
# or one the player opened for an older seed.
PINNED_VARIABLE = "BOTW_AP_PINNED"


@dataclass(frozen=True)
class Installed:
    version: str
    folder: Path

    @property
    def running(self) -> bool:
        return self.folder.resolve() == ROOT.resolve()

    @property
    def console(self) -> bool:
        """A version from before this launcher: its own runs in a console."""
        return not (self.folder / ENTRY).is_file()

    @property
    def plays(self) -> dict | None:
        """What its release.json states it plays (core/worlds.py), None when it
        says nothing: a version from before the statement."""
        try:
            said = json.loads((self.folder / RELEASE_MARKER).read_text(encoding="utf-8")).get("plays")
        except (OSError, ValueError, AttributeError):
            return None
        return said if isinstance(said, dict) else None


def installed(folder: Path | None = None) -> list[Installed]:
    """The versions installed whole and that have a launcher, of either kind,
    the newest first."""
    folder = VERSIONS if folder is None else folder
    found = []
    for entry in folder.iterdir() if folder.is_dir() else ():
        try:
            version = json.loads((entry / COMPLETE).read_text(encoding="utf-8"))["version"]
            parse(version)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if (entry / ENTRY).is_file() or (entry / CONSOLE_ENTRY).is_file():
            found.append(Installed(version, entry))
    return sorted(found, key=lambda one: parse(one.version), reverse=True)


def newest(than: str = VERSION, folder: Path | None = None) -> Installed | None:
    """The newest installed version with this kind of launcher, if it is newer than `than`."""
    every = [one for one in installed(folder) if not one.console]
    return every[0] if every and parse(every[0].version) > parse(than) else None


def find(version: str, folder: Path | None = None) -> Installed | None:
    return next((one for one in installed(folder) if one.version == version), None)


def python(folder: Path, windowed: bool = True) -> Path:
    """The Python of a release folder; this process's own for a source checkout."""
    if os.name == "nt":
        shipped = folder / "python" / ("pythonw.exe" if windowed else "python.exe")
    else:
        shipped = folder / "python" / "bin" / "python3"
    if shipped.is_file():
        return shipped
    own = Path(sys.executable)
    # A job reads and writes pipes: never pythonw, which has none.
    if os.name == "nt" and not windowed and own.name.lower() == "pythonw.exe":
        return own.with_name("python.exe")
    return own


def command(folder: Path, arguments: list[str] = (), windowed: bool = True) -> list[str]:
    """Start the launcher of a release folder. -I: no PYTHON* variable or user
    package of this computer reaches it."""
    if not (folder / ENTRY).is_file() and (folder / CONSOLE_ENTRY).is_file():
        return [str(python(folder, windowed=False)), "-I", str(folder / CONSOLE_ENTRY), *_console(arguments)]
    return [str(python(folder, windowed)), "-I", "-X", "utf8", str(folder / ENTRY), *arguments]


def _console(arguments: list[str]) -> list[str]:
    """What a console launcher understands of this one's arguments: a file to
    add, not a seed to select (it asks which one)."""
    rest = list(arguments)
    if "--seed" in rest[:-1]:
        at = rest.index("--seed")
        del rest[at:at + 2]
    return rest


def start(folder: Path, arguments: list[str] = (), data: Path | None = None) -> subprocess.Popen:
    """Open the launcher of `folder` in a process of its own, as the version it
    is; with `data`, on that data folder whatever the version would choose (an
    older version knows neither a moved data folder nor a checkout's)."""
    environment = {**os.environ, PINNED_VARIABLE: "1"}
    if data is not None:
        environment[DATA_VARIABLE] = str(data)
    console = not (folder / ENTRY).is_file()
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if console else 0
    return subprocess.Popen(command(folder, list(arguments)), cwd=folder, env=environment, creationflags=flags)


def remove(version: Installed) -> None:
    if version.running:
        raise ValueError(f"version {version.version} is the one running: it cannot remove itself")
    # The marker first: a folder left half removed is then an unfinished installation.
    (version.folder / COMPLETE).unlink(missing_ok=True)
    shutil.rmtree(version.folder)


def unfinished(folder: Path | None = None) -> list[Path]:
    """The folders an installation or a removal left unfinished."""
    folder = VERSIONS if folder is None else folder
    return [entry for entry in (folder.iterdir() if folder.is_dir() else ())
            if entry.is_dir() and not (entry / COMPLETE).is_file() and entry.resolve() != ROOT.resolve()]
