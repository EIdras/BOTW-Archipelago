"""The seeds prepared on this computer: listing, adding, rebuilding, deleting.

A prepared seed is a folder of <data>/play-seeds named after the seed
(tools/play_seed.py): the player's copy of the slot file or zip, analysis.json
(what the seed is), the client's state, the sessions' logs, and a pointer to its
game pack in <data>/packs-from-source.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable

from tools import cemu_profile, play_seed

Say = Callable[[str], None]
SEED_FILE_PATTERNS = "*.apbotw *.apbotw.json *.zip"
SESSION_STAMP = "%Y%m%dT%H%M%S.%fZ"     # a session folder's name (tools/play_session.py)


@dataclass(frozen=True)
class PreparedSeed:
    name: str
    slot: str                       # the player's name in the multiworld
    world_version: str              # the world's version that generated it, "" if not recorded
    world_schema: int | None        # the shape of its world, which says the versions that play it
    playable: bool                  # this version can play it (tools/play_seed.py check_compatible)
    last_played: datetime | None
    prepared: datetime
    from_zip: bool                  # prepared from the seed's whole zip, not a slot file alone
    client_schema: int | None = None    # not recorded for the seeds prepared before 0.4.0

    @property
    def folder(self) -> Path:
        return folder_of(self.name)

    @property
    def last_used(self) -> datetime:
        return self.last_played or self.prepared


@dataclass(frozen=True)
class SeedFile:
    """A slot file or a seed's zip the player picked, before it is prepared."""
    path: Path
    seed: str
    players: tuple[str, ...]        # the Breath of the Wild players in it
    world_version: str
    world_schema: int | None
    unplayable: str                 # why this version cannot play it, "" when it can
    client_schema: int | None = None


@dataclass(frozen=True)
class Deletion:
    """What deleting a seed removes."""
    seed: str
    paths: tuple[Path, ...]
    size: int
    with_pack: bool
    with_hosted_progress: bool      # the .apsave of a game hosted on this computer


def folder_of(name: str) -> Path:
    return play_seed.PLAY_SEEDS / name


def _report(folder: Path) -> dict:
    return json.loads((folder / "analysis.json").read_text(encoding="utf-8"))


def _last_session(folder: Path) -> datetime | None:
    stamps = sorted(path.name for path in (folder / "sessions").glob("*")) \
        if (folder / "sessions").is_dir() else []
    try:
        return datetime.strptime(stamps[-1], SESSION_STAMP).replace(tzinfo=timezone.utc) if stamps else None
    except ValueError:
        return None


def read(name: str) -> PreparedSeed | None:
    from botw_client import compatibility
    folder = folder_of(name)
    try:
        report = _report(folder)
        audit = report["audit"]
        slot = audit["slots"][str(report.get("botw_slot", 1))]
        prepared = datetime.fromtimestamp((folder / "analysis.json").stat().st_mtime, timezone.utc)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    schema, client = audit.get("world_schema"), audit.get("client_schema")
    return PreparedSeed(name, slot, audit.get("world_version") or "", schema,
                        schema is None or compatibility.plays(compatibility.statement(), schema, client),
                        _last_session(folder), prepared, play_seed.hostable(report), client)


def prepared() -> list[PreparedSeed]:
    """The prepared seeds, the last used first."""
    folders = play_seed.PLAY_SEEDS.iterdir() if play_seed.PLAY_SEEDS.is_dir() else ()
    seeds = [seed for seed in (read(folder.name) for folder in folders) if seed is not None]
    return sorted(seeds, key=lambda seed: seed.last_used, reverse=True)


def inspect(path: Path) -> SeedFile:
    """What a file the player picked is; ValueError when it is not a seed of this game."""
    from tools.build_pack_from_source import slot_manifests
    path = path.resolve()
    try:
        manifests = slot_manifests(path)
        seed = manifests[0]["seed"]
    except (OSError, ValueError, KeyError, IndexError) as exc:
        raise ValueError(f"Not a Breath of the Wild slot file or seed: {path.name}") from exc
    ours = [manifest for manifest in manifests if manifest.get("game") == play_seed.GAME]
    if not ours:
        raise ValueError(f"No Breath of the Wild player in this seed: {path.name}")
    slot_data = ours[0].get("slot_data", {})
    try:
        play_seed.check_compatible(slot_data)
        unplayable = ""
    except ValueError as exc:
        unplayable = str(exc)
    return SeedFile(path, seed, tuple(manifest["slot_name"] for manifest in ours),
                    slot_data.get("world_version") or "", slot_data.get("world_schema"), unplayable,
                    slot_data.get("client_schema"))


def is_prepared(file: SeedFile) -> bool:
    """This very file is already prepared (the same seed from another file is not)."""
    folder = folder_of(file.seed)
    copy = folder / file.path.name
    return (folder / "analysis.json").is_file() and copy.is_file() \
        and play_seed.sha(copy) == play_seed.sha(file.path)


def prepare(file: SeedFile, slot: str, say: Say = print) -> str:
    """Prepare the seed of `file` for the player `slot`: its folder and its game
    pack, built over the mods the player's Cemu runs (tools/play_mods.py). A
    file already prepared only has its pack brought up to date. The seed's name."""
    from botw_patch.game_files import ModConflict
    from tools import play_mods
    if is_prepared(file):
        refresh(file.seed, say)
        return file.seed
    mods = play_mods.prepare(say)
    say(f"Building the game pack of seed {file.seed} for {slot}...")
    try:
        play_seed.prepare(file.path, slot_name=slot if len(file.players) > 1 else None,
                          layers=mods.layers, mem2_end=mods.mem2_end)
    except ModConflict as conflict:
        play_mods.leave_out(mods, conflict, say)
        play_mods.fresh_pack(folder_of(file.seed), mods, say)
    return file.seed


def refresh(name: str, say: Say = print) -> None:
    """Bring a prepared seed's pack up to date: built again when it is missing,
    was built by another version of the project, or over other mods than the
    player's Cemu runs now. Does nothing otherwise."""
    from tools import play_mods
    play_mods.fresh_pack(folder_of(name), play_mods.prepare(say), say)


def rebuild(name: str, say: Say = print) -> None:
    """Build a prepared seed's pack again, whatever its state."""
    from botw_patch.game_files import ModConflict
    from tools import play_mods
    mods = play_mods.prepare(say)
    say(f"Building the game pack of seed {name} again...")
    while True:         # each conflict leaves one of the player's packs out
        try:
            play_seed.refresh(folder_of(name), mods.layers, mods.mem2_end)
            return
        except ModConflict as conflict:
            play_mods.leave_out(mods, conflict, say)


def newer_world(name: str) -> str | None:
    """The world's version that generated the seed, when it is newer than this version."""
    try:
        return play_seed.newer_world(_report(folder_of(name)).get("audit", {}))
    except (OSError, ValueError):
        return None


def deletion(name: str) -> Deletion:
    folder = folder_of(name)
    paths = play_seed.seed_paths(folder)
    return Deletion(name, tuple(paths), sum(map(play_seed.size, paths)), len(paths) > 1,
                    any(folder.glob("*.apsave")))


def delete(name: str) -> None:
    """Delete a prepared seed: its folder and its pack, never the game's saves."""
    # A session open on the seed writes in its folder.
    if cemu_profile.cemu_running():
        raise RuntimeError("Close Cemu before deleting a seed.")
    try:
        play_seed.delete(folder_of(name))
    except OSError as exc:
        raise OSError(f"Seed {name} is not entirely deleted ({exc}): close what uses it, "
                      "then delete it again.") from exc


def remove_unused_packs() -> tuple[int, int]:
    """Remove the game packs no seed selects any more (a seed folder deleted by
    hand, a build that did not finish); how many, and the bytes freed."""
    return play_seed.remove_orphans()
