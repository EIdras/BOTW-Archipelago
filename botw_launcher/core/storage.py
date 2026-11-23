"""What the launcher keeps on disk, how much, and moving it to another folder.

Everything the project writes for the player is in one data folder
(botw_client/paths.py). A release's player can move it, to another drive for
instance: the folder is copied, checked, then named in location.json, a file
that stays in the default folder for every version to find the data again.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
from typing import Callable

from botw_client import paths
from botw_client.paths import DATA, ROOT
from tools import play_seed

from . import profile

Say = Callable[[str], None]
Progress = Callable[[int, int, str], None]      # step, steps, what the step is

# The data folder's entries, by what they are for the player: (label, hint, entries).
CATEGORIES = (
    ("Game profile", "Cemu, the game's update, the DLC and your saves", ("cemu-validation",)),
    ("Seeds", "Your seeds, their progress and their session logs", ("play-seeds",)),
    ("Game packs", "The modified game files of each seed", ("packs-from-source", "play-speed-packs")),
    ("Installed versions", "The versions of BOTW Archipelago installed by updates", ("versions", "downloads")),
    ("PopTracker", "The map tracker's pack and icons", ("poptracker",)),
    ("Launcher", "Logs and settings", ("logs", "launcher")),
)
OTHER = ("Other files", "Caches the tools build again when missing")
PREVIOUS = "previous"       # in location.json: the folder a move left to remove


@dataclass(frozen=True)
class Usage:
    label: str
    hint: str
    paths: tuple[Path, ...]
    size: int


def usage(data: Path = DATA) -> list[Usage]:
    """The data folder's size by category; walks every file, so not for the window's thread."""
    known = {name for _label, _hint, names in CATEGORIES for name in names}
    rows = [Usage(label, hint, tuple(data / name for name in names),
                  sum(play_seed.size(data / name) for name in names))
            for label, hint, names in CATEGORIES]
    others = tuple(entry for entry in (data.iterdir() if data.is_dir() else ())
                   if entry.name not in known and entry.name != paths.LOCATION_FILE)
    rows.append(Usage(*OTHER, others, sum(map(play_seed.size, others))))
    return rows


def free_space(folder: Path) -> int:
    """The bytes free on the drive of `folder`, which need not exist yet."""
    while not folder.exists() and folder != folder.parent:
        folder = folder.parent
    return shutil.disk_usage(folder).free


def _pointer() -> Path:
    return paths.default_data_folder() / paths.LOCATION_FILE


def _holds_only_the_pointer(folder: Path) -> bool:
    return all(entry.name == paths.LOCATION_FILE for entry in folder.iterdir())


def destination(picked: Path) -> Path:
    """The data folder to make from the folder the player picked: that folder
    when it is empty, else a folder of its own inside it."""
    picked = picked.resolve()
    if not picked.exists() or _holds_only_the_pointer(picked):
        return picked
    return picked / paths.RELEASE_FOLDER


def relocation_refusal(target: Path | None = None) -> str | None:
    """Why the data cannot be moved (to `target`, when given); None when it can."""
    if os.environ.get(paths.DATA_VARIABLE):
        return f"The data folder is set by the {paths.DATA_VARIABLE} variable of this computer."
    if not (ROOT / paths.RELEASE_MARKER).is_file():
        return "Not from the source code: its data stays in its .build folder."
    if target is None:
        return None
    target, data = target.resolve(), DATA.resolve()
    if target == data:
        return "The data is already in this folder."
    if target.is_relative_to(data) or data.is_relative_to(target):
        return "Choose a folder outside the current data folder."
    if target.exists() and not (target.is_dir() and _holds_only_the_pointer(target)):
        return f"{target} is not empty."
    if profile.cemu_running():
        return "Close Cemu before moving the data."
    return None


def relocate(target: Path, say: Say = print, progress: Progress = lambda *_: None) -> Path:
    """Move the data folder to `target`: copy, check, switch, then remove the
    old one. Until the switch the old folder is untouched: a failure or a
    cancellation leaves the launcher as it was."""
    refusal = relocation_refusal(target)
    if refusal:
        raise ValueError(refusal)
    target, data = target.resolve(), DATA.resolve()
    entries = [entry for entry in sorted(data.iterdir()) if entry.name != paths.LOCATION_FILE]
    needed = sum(map(play_seed.size, entries))
    if free_space(target) < needed:
        raise OSError(f"Not enough room in {target}: {needed / 2**30:.1f} GB are needed.")
    target.mkdir(parents=True, exist_ok=True)
    for step, entry in enumerate(entries, 1):
        progress(step, len(entries) + 1, f"Copying {entry.name}")
        if entry.is_dir():
            shutil.copytree(entry, target / entry.name, symlinks=True)
        else:
            shutil.copy2(entry, target / entry.name)
        if play_seed.size(target / entry.name) != play_seed.size(entry):
            raise OSError(f"The copy of {entry.name} differs from the original: nothing was changed.")
    _rebase_seed_archives(target / "play-seeds", data, target)
    progress(len(entries) + 1, len(entries) + 1, "Removing the old folder")
    _write_pointer(target, previous=data)
    finish_relocation()
    say(f"The data is now in {target}.")
    return target


def _rebase_seed_archives(seeds: Path, old: Path, new: Path) -> None:
    """A seed's analysis.json names its archive by its full path."""
    for report in seeds.glob("*/analysis.json") if seeds.is_dir() else ():
        content = json.loads(report.read_text(encoding="utf-8"))
        archive = Path(content.get("archive", ""))
        if archive.is_absolute() and archive.is_relative_to(old):
            content["archive"] = str(new / archive.relative_to(old))
            report.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_pointer(data: Path, previous: Path | None = None) -> None:
    pointer = _pointer()
    content = {} if data == paths.default_data_folder().resolve() else {"data": str(data)}
    if previous is not None:
        content[PREVIOUS] = str(previous)
    if not content:
        pointer.unlink(missing_ok=True)
        return
    pointer.parent.mkdir(parents=True, exist_ok=True)
    temporary = pointer.with_suffix(".tmp")
    temporary.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, pointer)


def finish_relocation() -> bool:
    """Remove what a move left in the previous folder: files in use then (the
    version that was running) can go once another process runs. True when
    nothing is left to remove."""
    pointer = _pointer()
    try:
        content = json.loads(pointer.read_text(encoding="utf-8"))
        previous = Path(content[PREVIOUS])
    except (OSError, ValueError, KeyError, TypeError):
        return True
    current = paths.chosen_data_folder(pointer.parent) or pointer.parent
    # Never the folder in use, whatever the file says.
    if previous.resolve() == current.resolve() or ROOT.resolve().is_relative_to(previous.resolve()):
        return False
    left = False
    for entry in previous.iterdir() if previous.is_dir() else ():
        if entry.name == paths.LOCATION_FILE:
            continue
        try:
            play_seed.remove(entry) if entry.is_dir() else entry.unlink()
        except OSError:
            left = True         # still open somewhere: tried again at the next start
    if left:
        return False
    if previous.is_dir() and not any(previous.iterdir()):
        previous.rmdir()
    _write_pointer(current.resolve())
    return True
