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
import shutil
import sys
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
SCOPE = "generated_ap_seed"
CLIENT_SCHEMAS = (3, 4, 5, 6, 7, 8, 9, 10, 11)    # 4: the Gerudo Set; 5: the goal and the sanctum; 6: the
#                                                  new filler; 7: the weapons; 8: the travel items; 9: Epona;
#                                                  10: maps; 11: the Downpour, Yiga Ambush and
#                                                  Paranoia traps
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
    """This version can play a seed whose schemas it knows, whatever the world's
    version that generated it; otherwise the player needs that version."""
    from botw_client.locations import SCHEMA_LOCATION_COUNTS
    from botw_client.version import VERSION
    if (slot_data.get("world_schema") not in SCHEMA_LOCATION_COUNTS
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
