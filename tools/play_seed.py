"""Prepare a generated AP seed for play: audit, identity, bound pack.

    python tools/play_seed.py <AP_xxx.zip | xxx.apbotw> [--slot <player name>]
                              [--content <update/content> --rpx <U-King.rpx>]

The seed may be a solo seed or a multiworld with other games and players. The
game pack is built for one Breath of the Wild slot, from either:
  * the seed's zip, as generated (its BOTW slot; --slot when it has several).
    Where Archipelago is (a source checkout's runtime), the whole seed is
    checked, and tools/play_session.py can host it on a local AP server;
  * the slot's own file (<seed>_P<n>_<name>.apbotw, inside the zip, or downloaded
    from the room's page; .apbotw.json for seeds generated before), to
    play in a room hosted elsewhere, archipelago.gg for instance.

1. audits the slot: manifest hash, one placement per location, and, from the
   zip, its agreement with the seed's data;
2. copies the file into play-seeds/<seed>/ of the data folder
   (botw_client/paths.py; a local server keeps its
   .apsave next to that copy, so progress survives between sessions);
3. reads the session identity the server will give the slot (seed, team 0,
   slot, DataPackage checksum written by the world) and its token;
4. preserves an existing audited analysis.json on resume, builds the pack
   from project sources and the game's update, and selects it in
   play-pack.json;
5. writes the GameData flag table the client reads, from the same update
   (botw_client/gamedata_table.py).

The update is the copy in the isolated Cemu profile (tools/cemu_profile.py),
the one the game runs from; --content and --rpx name another one.

One person cannot play two BOTW slots of a seed alone: one slot's Paraglider
may sit behind the other slot's Cryonis terminal.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import time
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
os.environ["SKIP_REQUIREMENTS_UPDATE"] = "1"
sys.path.insert(0, str(ROOT))

from botw_client.paths import BUILD, DATA  # noqa: E402
from tools.cemu.guest import MEM2_END  # noqa: E402

# The Archipelago runtime of a source checkout, to read a seed's zip.
sys.path.insert(0, str(BUILD / "ap-runtime"))

PLAY_SEEDS = DATA / "play-seeds"
PACKS = DATA / "packs-from-source"
ORPHAN_AGE = 600        # seconds: see orphan_packs
SCOPE = "generated_ap_seed"
CLIENT_SCHEMAS = (3, 4, 5, 6, 7, 8, 9, 10, 11, 12)    # 4: the Gerudo Set; 5: the goal and the sanctum; 6: the
#                                                      new filler; 7: the weapons; 8: the travel items; 9: Epona;
#                                                      10: maps; 11: the Downpour, Yiga Ambush and
#                                                      Paranoia traps; 12: the travel points
GAME = "Breath of the Wild"
_ROWS = json.loads((ROOT / "botw_world/data/locations.json").read_text(encoding="utf-8"))
# Every location but the goal, shops apart: they depend on beedle_shop_items
# and stall_items.
PLACEMENTS = sum(1 for row in _ROWS if row["category"] not in ("Goal", "Shop", "Stall"))


def expected_placements(slot_data: dict) -> int:
    from botw_client import shop_catalog, stall_catalog
    # stall_items: a number of stalls' items in all; seeds generated before it
    # had stall_shop_items on each stall.
    stalls = (int(slot_data["stall_items"]) if "stall_items" in slot_data
              else len(stall_catalog.MERCHANTS) * int(slot_data.get("stall_shop_items", 0)))
    return (PLACEMENTS + len(shop_catalog.MERCHANTS) * int(slot_data.get("beedle_shop_items", 0)) + stalls)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_manifest(manifest: dict) -> dict:
    """A BOTW slot file, checked against its own content hash."""
    manifest = dict(manifest)
    claimed = manifest.pop("content_sha256", None)
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(payload).hexdigest() != claimed:
        raise ValueError("wrong slot manifest hash")
    if manifest.get("game") != GAME:
        raise ValueError("not a Breath of the Wild slot file")
    check_compatible(manifest.get("slot_data", {}))
    return manifest


def check_compatible(slot_data: dict) -> None:
    """This version can play a seed of its own world schema, whatever the world's
    version that generated it; otherwise the player needs that version. An
    earlier schema is not played: its pack would take Purah's upgrades and the
    Champions' Ballad's powers away, without their locations."""
    from botw_client.locations import WORLD_SCHEMA
    from botw_client.version import VERSION
    if (slot_data.get("world_schema") != WORLD_SCHEMA
            or slot_data.get("client_schema") not in CLIENT_SCHEMAS):
        made = slot_data.get("world_version", "an earlier version")
        raise ValueError(f"this seed was generated with the Breath of the Wild world {made}, which this "
                         f"version ({VERSION}) cannot play: use the BOTW Archipelago release of the seed's version")


def newer_world(audit: dict) -> str | None:
    """The world's version that generated the seed, when it is newer than this one."""
    from botw_client.version import VERSION, parse
    made = audit.get("world_version")
    return made if made and parse(made) > parse(VERSION) else None


def archipelago_here() -> bool:
    """Archipelago's server code is importable (the runtime of a source
    checkout): a seed's zip can then be checked whole, and hosted."""
    import importlib.util
    return importlib.util.find_spec("MultiServer") is not None


def hostable(report: dict) -> bool:
    """A prepared seed can be hosted here: prepared from its whole zip."""
    audit = report.get("audit", {})
    return bool(audit.get("hostable", str(report.get("archive", "")).lower().endswith(".zip")))


def read_seed(path: Path, slot_name: str | None = None) -> tuple[dict, dict]:
    """(audit, identity) of the seed's BOTW slot, from its zip or its slot file.

    Without Archipelago here, a zip is read as the slot files it holds."""
    from botw_client.session import data_package_checksum, session_token
    from tools.build_pack_from_source import slot_manifests
    manifests = [verified_manifest(m) for m in slot_manifests(path)]
    if slot_name is not None:
        manifests = [m for m in manifests if m["slot_name"] == slot_name]
    if not manifests:
        raise ValueError("no Breath of the Wild slot"
                         + (f" named {slot_name}" if slot_name else "") + " in this seed")
    if len(manifests) > 1:
        raise ValueError("several Breath of the Wild slots in this seed; choose one with --slot: "
                         + ", ".join(m["slot_name"] for m in manifests))
    manifest = manifests[0]
    slot, name = manifest["slot"], manifest["slot_name"]
    placements = len(manifest["placements"])
    checksum = manifest.get("data_package_checksum")
    team, players = 0, None
    whole = path.suffix.lower() == ".zip" and archipelago_here()
    if whole:
        with warnings.catch_warnings():
            # Archipelago's compiled speedups are not built here: its Python fallback serves.
            warnings.filterwarnings("ignore", message="_speedups not available")
            from MultiServer import Context
        with zipfile.ZipFile(path) as archive:
            multidata = Context.decompress(archive.read(
                next(n for n in archive.namelist() if n.endswith(".archipelago"))))
        connect = multidata["connect_names"].get(name)
        if manifest["seed"] != multidata["seed_name"] or connect is None or connect[1] != slot:
            raise ValueError("slot manifest inconsistent with the seed")
        team, players = int(connect[0]), len(multidata["connect_names"])
        placements = len(multidata["locations"][slot])
        # The DataPackage the server will send, embedded in the seed.
        package = multidata["datapackage"][GAME]
        served = data_package_checksum(
            GAME, {int(v): k for k, v in package["item_name_to_id"].items()},
            package["location_name_to_id"])
        if checksum is not None and checksum != served:
            raise ValueError("the slot file and the seed disagree on the game's data")
        checksum = served
    if not checksum:
        raise ValueError("this slot file comes from an older version of the world: "
                         "prepare the seed from its zip")
    expected = expected_placements(manifest["slot_data"])
    if placements != expected:
        raise ValueError(f"{placements} placements, {expected} expected")
    identity = {"seed": manifest["seed"], "team": team, "slot": slot,
                "data_package_checksum": checksum}
    identity["token"] = session_token((manifest["seed"], team, slot, checksum))
    audit = {"seed": manifest["seed"], "slots": {str(slot): name}, "placements": placements,
             "world_schema": manifest["slot_data"].get("world_schema"),
             "world_version": manifest["slot_data"].get("world_version"), "players": players,
             "hostable": whole}
    return audit, identity


def game_update() -> tuple[Path, Path]:
    """The update's content and U-King.rpx in the isolated Cemu profile."""
    from tools import cemu_profile
    update = cemu_profile.update()
    if not (update / "content").is_dir():
        raise ValueError("no isolated Cemu profile to build the pack from: create it first "
                         "(tools/cemu_profile.py --cemu <Cemu.exe>), or name --content and --rpx")
    return update / "content", update / "code" / "U-King.rpx"


def prepare(source: Path, *, content: Path | None = None, rpx: Path | None = None,
            slot_name: str | None = None, layers: list[dict] = (),
            mem2_end: int = MEM2_END) -> tuple[Path, Path]:
    # layers: the player's graphic packs the pack is built over, mem2_end: the end of the
    # game's main memory with them (tools/play_mods.py, tools/cemu/guest.py).
    if (content is None) != (rpx is None):
        raise ValueError("name both --content and --rpx, or neither")
    if content is None:
        content, rpx = game_update()
    audit, identity = read_seed(source, slot_name)
    folder = PLAY_SEEDS / audit["seed"]
    archive = folder / source.name
    folder.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        if sha(archive) != sha(source):
            raise ValueError(f"another archive is already there for this seed: {archive}")
    else:
        shutil.copy2(source, archive)
    report = folder / "analysis.json"
    from tools.build_pack_from_source import build, load_seed, seed_slot
    from tools.play_pack import select_pack
    slot = identity["slot"]
    if report.exists():
        if seed_slot(report) != slot:
            raise ValueError(f"this seed is already prepared for another slot: {folder}")
        binding = load_seed(report, slot)
        if binding["seed"] != audit["seed"] or binding["token"] != identity["token"]:
            raise ValueError("existing analysis differs from the seed")
    else:
        data = {"schema": 1, "status": "passed", "scope": SCOPE, "botw_slot": slot,
                "archive": str(archive), "archive_sha256": sha(archive),
                "audit": audit, "delivery": {"sessions": {str(slot): identity}}}
        report.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pack = build(content, rpx, report, slot, PACKS, resource_gate=True, event_gate=True, layers=layers,
                 mem2_end=mem2_end,
                 progress=lambda step, steps, name: print(f"  [{step}/{steps}] {name}", flush=True))
    select_pack(folder, pack)
    from botw_client.gamedata_table import build as build_gamedata_table
    build_gamedata_table(content)
    return report, pack


def refresh(folder: Path, layers: list[dict] = (), mem2_end: int = MEM2_END) -> Path:
    """Build the pack of a prepared seed again, from its own copy of the seed
    and the current sources, over the player's graphic packs `layers`
    (tools/play_mods.py); the pack it replaces goes when no seed uses it."""
    from tools.play_pack import selected_pack, selections
    report = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    try:
        previous = selected_pack(folder)
    except (OSError, ValueError, RuntimeError):
        previous = None
    slot_name = report["audit"]["slots"][str(report.get("botw_slot", 1))]
    _, pack = prepare(Path(report["archive"]), slot_name=slot_name, layers=layers, mem2_end=mem2_end)
    if (previous is not None and previous != pack and previous.parent == PACKS.resolve()
            and previous not in selections(PLAY_SEEDS)):
        shutil.rmtree(previous)
    return pack


def pointed_pack(folder: Path) -> Path | None:
    """The pack a seed's play-pack.json names, unchecked (tools/play_pack.py
    checks it before a session): it may be gone or changed."""
    try:
        pointer = json.loads((folder / "play-pack.json").read_text(encoding="utf-8"))
        # Schema 1, written by source checkouts before the data folder, is
        # relative to the project.
        base = {1: ROOT, 2: DATA}.get(pointer["schema"])
        return (base / pointer["pack"]).resolve() if base is not None else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def seed_paths(folder: Path) -> list[Path]:
    """What deleting a prepared seed removes: the pack it selects and that
    pack's copy installed in the Cemu profile, unless another seed selects it,
    then its folder (the seed's copy, the client's state, a local server's
    .apsave, the sessions' logs). The game's saves, in the profile, stay."""
    from tools.cemu_profile import PACK_PREFIX, PORTABLE
    pack = pointed_pack(folder)
    others = {pointed_pack(other) for other in folder.parent.iterdir() if other != folder}
    paths = []
    if pack is not None and pack.parent == PACKS.resolve() and pack not in others:
        paths += [PORTABLE / "graphicPacks" / (PACK_PREFIX + pack.name), pack]
    return [path for path in paths + [folder] if path.is_dir()]


def delete(folder: Path) -> list[Path]:
    """Delete a prepared seed (seed_paths), its folder last and, in it, its
    analysis.json: until then the launcher lists the seed, to delete again
    what a file in use kept. What it removed."""
    paths = seed_paths(folder)
    for path in paths:
        if path == folder and not linked(folder):
            for entry in sorted(folder.iterdir(), key=lambda entry: entry.name == "analysis.json"):
                remove(entry)
        remove(path)
    return paths


def linked(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def remove(path: Path) -> None:
    """Remove a file, a folder with all it holds, or a link: never what it leads to."""
    if path.is_dir() and not linked(path):
        shutil.rmtree(path, onexc=writable)     # removes the links inside, not what they lead to
        return
    try:
        path.unlink()
    except PermissionError as error:
        writable(os.unlink, str(path), error)


def writable(function, path: str, error: BaseException) -> None:
    # A copy keeps the read-only attribute of a downloaded seed (shutil.copy2),
    # which Windows refuses to delete as it is. A file in use stays refused.
    if function not in (os.unlink, os.rmdir) or not isinstance(error, PermissionError):
        raise error
    os.chmod(path, stat.S_IWRITE)
    function(path)


def orphan_packs() -> list[Path]:
    """The packs of PACKS no prepared seed selects, left by a seed folder
    deleted by hand or by a build that did not finish; none while a selection
    is unreadable, as its pack could be any of them. Only folders named as a
    pack is, older than ORPHAN_AGE: a younger one may be a build another
    launcher is writing."""
    try:
        used = set()
        for folder in PLAY_SEEDS.iterdir() if PLAY_SEEDS.is_dir() else ():
            pack = pointed_pack(folder)
            if pack is None and (folder / "play-pack.json").exists():
                return []
            used.add(pack)
        packs = sorted(PACKS.iterdir()) if PACKS.is_dir() else []
    except OSError:
        return []
    orphans = []
    for pack in packs:
        try:
            if (re.fullmatch("[0-9a-f]{16}", pack.name) and pack.is_dir() and not linked(pack)
                    and pack.resolve() not in used and time.time() - pack.stat().st_mtime > ORPHAN_AGE):
                orphans.append(pack)
        except OSError:
            continue
    return orphans


def remove_orphans() -> tuple[int, int]:
    """Remove orphan_packs(): how many went and the bytes they freed. One that
    a file in use keeps goes another time."""
    count = freed = 0
    for pack in orphan_packs():
        bytes_ = size(pack)
        try:
            remove(pack)
        except OSError:
            continue
        count, freed = count + 1, freed + bytes_
    return count, freed


def size(path: Path) -> int:
    """The bytes remove(path) frees: what a link leads to apart."""
    try:
        if linked(path):
            return 0
        if path.is_dir():
            return sum(size(entry) for entry in path.iterdir())
        return path.lstat().st_size
    except OSError:
        return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("seed", type=Path, help="the seed's zip, or the slot's .apbotw file")
    parser.add_argument("--content", type=Path,
                        help="the update's content folder (default: the Cemu profile's copy)")
    parser.add_argument("--rpx", type=Path, help="the update's U-King.rpx, with --content")
    parser.add_argument("--slot", help="the BOTW player's name, when the seed has several")
    arguments = parser.parse_args()
    report, pack = prepare(arguments.seed.resolve(), content=arguments.content,
                           rpx=arguments.rpx, slot_name=arguments.slot)
    print(report)
    print(pack)
