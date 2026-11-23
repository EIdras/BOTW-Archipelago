"""The releases before 0.4.0, installed side by side for the seeds of theirs.

Until 0.4.0, a release was a zip with its own Python and a console launcher
(tools/launcher.py). A seed only such a version plays (core/worlds.py) is
played with it: the window downloads it on demand into the data folder and
opens its launcher in a console window of its own, on the same data folder.

    <data>/versions/<version>/      a release, as its zip unpacks
    <data>/versions/<version>/installed.json    written last: without it the
                                    folder is an installation that did not finish

They are kept until the player removes them (Storage). Every version reads the
same data folder. What makes this safe is that a seed's game pack is built
again whenever another version than the one that built it plays the seed
(tools/play_mods.py fresh_pack).
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
from botw_client.version import parse

VERSIONS = DATA / "versions"
COMPLETE = "installed.json"
ENTRY = "tools/launcher.py"     # the console launcher of a release before 0.4.0


@dataclass(frozen=True)
class Installed:
    version: str
    folder: Path

    @property
    def running(self) -> bool:
        return self.folder.resolve() == ROOT.resolve()

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
    """The versions installed whole, with their launcher, the newest first."""
    folder = VERSIONS if folder is None else folder
    found = []
    for entry in folder.iterdir() if folder.is_dir() else ():
        try:
            version = json.loads((entry / COMPLETE).read_text(encoding="utf-8"))["version"]
            parse(version)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if (entry / ENTRY).is_file():
            found.append(Installed(version, entry))
    return sorted(found, key=lambda one: parse(one.version), reverse=True)


def find(version: str, folder: Path | None = None) -> Installed | None:
    return next((one for one in installed(folder) if one.version == version), None)


def python(folder: Path) -> Path:
    """The Python of a release folder; this process's own otherwise, never
    pythonw: a console launcher reads and writes its console."""
    shipped = folder / "python" / "python.exe"
    if shipped.is_file():
        return shipped
    own = Path(sys.executable)
    if os.name == "nt" and own.name.lower() == "pythonw.exe":
        return own.with_name("python.exe")
    return own


def command(folder: Path, arguments: list[str] = ()) -> list[str]:
    """Start the launcher of a release folder. -I: no PYTHON* variable or user
    package of this computer reaches it."""
    return [str(python(folder)), "-I", str(folder / ENTRY), *_console(arguments)]


def _console(arguments: list[str]) -> list[str]:
    """What a console launcher understands of this one's arguments: a file to
    add, not a seed to select (it asks which one)."""
    rest = list(arguments)
    if "--seed" in rest[:-1]:
        at = rest.index("--seed")
        del rest[at:at + 2]
    return rest


def start(folder: Path, arguments: list[str] = (), data: Path | None = None) -> subprocess.Popen:
    """Open the launcher of `folder` in a console window of its own; with
    `data`, on that data folder whatever the version would choose (an older
    version knows neither a moved data folder nor a checkout's)."""
    environment = dict(os.environ)
    if data is not None:
        environment[DATA_VARIABLE] = str(data)
    return subprocess.Popen(command(folder, list(arguments)), cwd=folder, env=environment,
                            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))


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
