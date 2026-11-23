"""The launcher's log, and the diagnostic archive a player sends with a report.

Everything is written to <data>/logs/launcher.log at DEBUG level, whatever the
player chose to see in the Logs page: the file is for the developer, the page
for the player. It holds the launcher's own records and every line a job
printed (botw_launcher/jobs.py); a play session also keeps its own files in the
seed's folder (tools/play_session.py). Never log a room's password.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import platform
import sys
import zipfile

from botw_client.paths import DATA, RELEASE_MARKER, ROOT
from botw_client.version import VERSION

FOLDER = DATA / "logs"
FILE = "launcher.log"
ROOT_LOGGER = "botw_launcher"
FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
MAX_BYTES = 2 * 2**20
BACKUPS = 4
# Of a session's folder, what a diagnostic takes; a Cemu log can be large.
SESSION_FILES = ("session.json", "client.log", "stderr.log", "cemu.log")


def setup(folder: Path = FOLDER) -> logging.Logger:
    """Open the log file; safe to call once in each process."""
    logger = logging.getLogger(ROOT_LOGGER)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / FILE, maxBytes=MAX_BYTES, backupCount=BACKUPS,
                                      encoding="utf-8")
    except OSError:
        # No log file (a read-only or missing drive) must not prevent playing.
        handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(handler)
    logger.info("---- launcher started: %s", ", ".join(environment()))
    return logger


def environment() -> list[str]:
    """What a developer needs to know of the computer to read a log."""
    kind = "release" if (ROOT / RELEASE_MARKER).is_file() else "source checkout"
    return [f"version {VERSION} ({kind})", f"Python {platform.python_version()}",
            platform.platform(), f"root {ROOT}", f"data {DATA}"]


def last_session(seed_folder: Path) -> Path | None:
    sessions = sorted((seed_folder / "sessions").glob("*")) if (seed_folder / "sessions").is_dir() else []
    return sessions[-1] if sessions else None


def export_diagnostic(target: Path, seed_folder: Path | None = None, folder: Path = FOLDER) -> Path:
    """Zip what a bug report needs: the launcher's logs and settings, the
    release's identity and, of the seed given, its last session and what the
    seed is (not the seed itself). Returns `target`."""
    members: list[tuple[Path, str]] = [(path, f"logs/{path.name}") for path in sorted(folder.glob(f"{FILE}*"))]
    members += [(DATA / "launcher" / "settings.json", "settings.json"),
                (ROOT / RELEASE_MARKER, RELEASE_MARKER)]
    if seed_folder is not None:
        members.append((seed_folder / "analysis.json", f"seed/{seed_folder.name}/analysis.json"))
        session = last_session(seed_folder)
        if session is not None:
            members += [(session / name, f"seed/{seed_folder.name}/{session.name}/{name}")
                        for name in SESSION_FILES]
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("environment.txt", "\n".join(environment()) + "\n")
        for path, name in members:
            if path.is_file():
                archive.write(path, name)
    return target
