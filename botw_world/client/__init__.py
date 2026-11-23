"""The BOTW Archipelago window, opened from the Archipelago Launcher.

Archipelago runs this in its own Python and installs nothing for a world. The
project's code travels inside the apworld (payload.zip, added when the release
is built) and is unpacked once; the libraries Archipelago lacks (oead, numpy,
evfl, rstb) are downloaded once from PyPI, the wheels of this system (Windows
or Linux, x86-64) each checked against the sha256 pinned in wheels.json
(tools/pin_client_wheels.py). Both go to
Archipelago's cache folder, apart from the player's data folder, which the
project finds as a release does (botw_client/paths.py) and the player may move.

One window at a time: a second launch hands its seed file to the open window
(inbox) and leaves.

Nothing here is imported when Archipelago starts: only when the window opens.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import pkgutil
import shutil
import sys
import sysconfig
import time
from typing import Callable
import urllib.request
import zipfile

PAYLOAD = "payload.zip"
PINS = "wheels.json"
DOWNLOAD_LIMIT = 200 * 1024 * 1024
RELEASES = "https://github.com/EIdras/BOTW-Archipelago/releases"
PLATFORMS = {"win-amd64": "win_amd64", "linux-x86_64": "linux_x86_64"}     # wheels.json's, by Python build

Progress = Callable[[str, int, int], None]      # what, done, total (bytes)


class SetupError(Exception):
    """What the player reads when the client cannot be set up."""


def home() -> Path:
    """Where the client's libraries and code are unpacked: Archipelago's cache."""
    try:
        from Utils import cache_path
        return Path(cache_path("botw"))
    except ImportError:         # outside Archipelago (tests)
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".cache")
        return Path(base) / "Archipelago" / "Cache" / "botw"


def python_tag() -> str:
    return f"cp{sys.version_info.major}{sys.version_info.minor}"


def _resource(name: str) -> bytes | None:
    try:
        return pkgutil.get_data(__name__, name)
    except OSError:
        return None


# ---- one window -------------------------------------------------------------

class Instance:
    """The lock of the one open window, held until the process ends (a crash
    releases it), and its inbox: what later launches ask it to open."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.inbox = folder / "inbox"
        self._handle = None

    def claim(self) -> bool:
        self.folder.mkdir(parents=True, exist_ok=True)
        handle = open(self.folder / "window.lock", "a+b")
        try:
            if sys.platform == "win32":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._handle = handle
        return True

    def forward(self, arguments: list[str]) -> None:
        """Ask the open window to come forward, and to open the file given."""
        self.inbox.mkdir(parents=True, exist_ok=True)
        request = self.inbox / f"{time.time_ns()}-{os.getpid()}.json"
        temporary = request.with_suffix(".tmp")
        temporary.write_bytes(json.dumps({"arguments": arguments}).encode("utf-8"))
        temporary.replace(request)

    def requests(self) -> list[list[str]]:
        """The requests waiting, oldest first, taken out of the inbox."""
        found = []
        for request in sorted(self.inbox.glob("*.json")) if self.inbox.is_dir() else ():
            try:
                arguments = json.loads(request.read_bytes())["arguments"]
                request.unlink()
            except (OSError, ValueError, KeyError):
                continue
            if isinstance(arguments, list) and all(isinstance(entry, str) for entry in arguments):
                found.append(arguments)
        return found


# ---- libraries and code -----------------------------------------------------

def platform_key(build: str | None = None) -> str | None:
    """The wheels in wheels.json this Python runs, or None when there are none:
    by the build of the Python, not the processor (an x64 Archipelago on an ARM
    laptop runs the x64 wheels)."""
    return PLATFORMS.get(build if build is not None else sysconfig.get_platform())


def _pins(pins: dict, build: str | None = None) -> list[dict]:
    """The wheels of this system and Python, or why there are none."""
    key = platform_key(build)
    if key is None:
        raise SetupError("The BOTW Archipelago client runs on Windows and Linux (x86-64) only.")
    tag = python_tag()
    wheels = []
    for name, entry in pins["libraries"].items():
        wheel = entry["wheels"].get(key, {}).get(tag)
        if wheel is None:
            raise SetupError(f"This Archipelago runs Python {sys.version_info.major}.{sys.version_info.minor}, "
                             f"which this version of BOTW Archipelago does not support yet.\n\n"
                             f"Install the newest botw.apworld: {RELEASES}")
        wheels.append({"name": name, **wheel})
    return wheels


def _fetch(url: str, size: int, progress: Callable[[int], None]) -> bytes:
    context = None
    try:
        import certifi
        import ssl
        context = ssl.create_default_context(cafile=certifi.where())
    except (ImportError, OSError):
        pass
    data = bytearray()
    with urllib.request.urlopen(url, timeout=60, context=context) as response:
        while chunk := response.read(256 * 1024):
            data += chunk
            if len(data) > max(size, 1) * 2 or len(data) > DOWNLOAD_LIMIT:
                raise SetupError(f"{url}: larger than expected")
            progress(len(data))
    return bytes(data)


def _extract(archive: zipfile.ZipFile, target: Path) -> None:
    """Every member inside `target`, none above it."""
    root = target.resolve()
    for member in archive.infolist():
        destination = (target / member.filename).resolve()
        if destination != root and root not in destination.parents:
            raise SetupError(f"unexpected file in an archive: {member.filename}")
    archive.extractall(target)


def _prune(folder: Path, kept: str) -> None:
    for entry in folder.iterdir() if folder.is_dir() else ():
        if entry.name != kept:
            shutil.rmtree(entry, ignore_errors=True)


def libraries_folder(base: Path, wheels: list[dict]) -> Path:
    key = hashlib.sha256("\n".join(sorted(wheel["sha256"] for wheel in wheels)).encode()).hexdigest()[:16]
    return base / "libraries" / key


def install_libraries(base: Path, wheels: list[dict], progress: Progress = lambda *_: None,
                      fetch=_fetch) -> Path:
    """The wheels unpacked as pip would, once; the folder."""
    target = libraries_folder(base, wheels)
    if (target / ".complete").is_file():
        return target
    temporary = target.with_name(target.name + ".partial")
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True)
    total, done = sum(wheel["size"] for wheel in wheels), 0
    for wheel in wheels:
        label = f"{wheel['name']} ({wheel['size'] // 1024 // 1024 or 1} MB)"
        progress(label, done, total)
        try:
            data = fetch(wheel["url"], wheel["size"], lambda got, start=done: progress(label, start + got, total))
        except SetupError:
            raise
        except OSError as exc:
            raise SetupError(f"Could not download {wheel['name']}: {getattr(exc, 'reason', exc)}.\n\n"
                             f"Check your internet connection, then try again.") from exc
        if hashlib.sha256(data).hexdigest() != wheel["sha256"]:
            raise SetupError(f"{wheel['file']} is not the file this version expects: nothing was installed.")
        _extract(zipfile.ZipFile(io.BytesIO(data)), temporary)
        # As pip installs it: <name>.data/platlib (oead's C++ runtime) goes to the root.
        for kept in temporary.glob("*.data/*lib"):
            for entry in kept.iterdir():
                if not (temporary / entry.name).exists():
                    entry.rename(temporary / entry.name)
        done += wheel["size"]
    (temporary / ".complete").touch()
    temporary.rename(target)
    _prune(target.parent, target.name)
    return target


def install_project(base: Path, payload: bytes) -> Path:
    """The project's code unpacked once per version; the folder."""
    target = base / "project" / hashlib.sha256(payload).hexdigest()[:16]
    if not (target / ".complete").is_file():
        temporary = target.with_name(target.name + ".partial")
        shutil.rmtree(temporary, ignore_errors=True)
        _extract(zipfile.ZipFile(io.BytesIO(payload)), temporary)
        (temporary / ".complete").touch()
        shutil.rmtree(target, ignore_errors=True)
        temporary.rename(target)
    _prune(target.parent, target.name)
    return target


def _checkout() -> Path | None:
    """Run from a source checkout (the world folder linked into Archipelago,
    no payload): the checkout itself."""
    root = Path(__file__).resolve().parents[2]
    return root if (root / "botw_launcher").is_dir() and (root / "botw_client").is_dir() else None


def ready(base: Path) -> tuple[Path, Path] | None:
    """The libraries and the project, when nothing needs to be done first."""
    pins, payload = _resource(PINS), _resource(PAYLOAD)
    try:
        libraries = libraries_folder(base, _pins(json.loads(pins)))
    except SetupError:
        return None
    if payload is None:
        project = _checkout()
    else:
        project = base / "project" / hashlib.sha256(payload).hexdigest()[:16]
    if project is None or not (libraries / ".complete").is_file():
        return None
    if payload is not None and not (project / ".complete").is_file():
        return None
    return libraries, project


def install(base: Path, progress: Progress = lambda *_: None) -> tuple[Path, Path]:
    pins, payload = _resource(PINS), _resource(PAYLOAD)
    if pins is None:
        raise SetupError("This copy of botw.apworld has no client: install it from the releases page.\n\n"
                         + RELEASES)
    libraries = install_libraries(base, _pins(json.loads(pins)), progress)
    if payload is not None:
        progress("the BOTW Archipelago files", 1, 1)
        return libraries, install_project(base, payload)
    project = _checkout()
    if project is None:
        raise SetupError("This copy of botw.apworld has no client: install it from the releases page.\n\n"
                         + RELEASES)
    return libraries, project


def activate(libraries: Path, project: Path) -> None:
    """The project and its libraries importable; jobs' children inherit the path."""
    for entry in (str(project), str(libraries)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


# ---- the window -------------------------------------------------------------

def main(*arguments: str) -> None:
    base = home()
    instance = Instance(base)
    if not instance.claim():
        instance.forward(list(arguments))
        return
    found = ready(base)
    if found is None:
        from .setup_window import run_setup
        found = run_setup(lambda progress: install(base, progress))
        if found is None:
            return
    world = Path(__file__).parents[2]       # ...\botw.apworld\botw\client\__init__.py
    if world.suffix == ".apworld" and world.is_file():
        os.environ["BOTW_AP_APWORLD"] = str(world)      # what an update replaces (core/updates.py)
    activate(*found)
    from botw_launcher.tk.app import run
    run(list(arguments), requests=instance.requests)
