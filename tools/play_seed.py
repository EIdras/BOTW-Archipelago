"""Prepare a generated AP seed for play: audit, identity, bound pack.

    python tools/play_seed.py <AP_xxx.zip | xxx.apbotw.json> --content <update/content> --rpx <U-King.rpx>
                              [--slot <player name>]

The seed may be a solo seed or a multiworld with other games and players. The
game pack is built for one Breath of the Wild slot, from either:
  * the seed's zip, as generated (its BOTW slot; --slot when it has several).
    It also lets tools/play_session.py host the seed on a local AP server;
  * the slot's own file (<seed>_P<n>_<name>.apbotw.json, inside the zip), to
    play in a room hosted elsewhere, archipelago.gg for instance.

1. audits the slot: manifest hash, one placement per location, and, from the
   zip, its agreement with the seed's data;
2. copies the file into play-seeds/<seed>/ of the data folder
   (botw_client/paths.py; a local server keeps its
   .apsave next to that copy, so progress survives between sessions);
3. reads the session identity the server will give the slot (seed, team 0,
   slot, DataPackage checksum written by the world) and its token;
4. preserves an existing audited analysis.json on resume, builds the pack
   from project sources and explicit dumps, and selects it in play-pack.json;
5. writes the GameData flag table the client reads, from the same update
   (botw_client/gamedata_table.py).

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
import zipfile

ROOT = Path(__file__).resolve().parents[1]
os.environ["SKIP_REQUIREMENTS_UPDATE"] = "1"
sys.path.insert(0, str(ROOT))

from botw_client.paths import BUILD, DATA  # noqa: E402

# The Archipelago runtime of a source checkout, to read a seed's zip.
sys.path.insert(0, str(BUILD / "ap-runtime"))

PLAY_SEEDS = DATA / "play-seeds"
PACKS = DATA / "packs-from-source"
SCOPE = "generated_ap_seed"
GAME = "Breath of the Wild"
_ROWS = json.loads((ROOT / "botw_world/data/locations.json").read_text(encoding="utf-8"))
# Every location but the goal, shops apart: they depend on beedle_shop_items
# and stall_shop_items.
PLACEMENTS = sum(1 for row in _ROWS if row["category"] not in ("Goal", "Shop", "Stall"))


def expected_placements(slot_data: dict) -> int:
    from botw_client import shop_catalog, stall_catalog
    return (PLACEMENTS
            + len(shop_catalog.MERCHANTS) * int(slot_data.get("beedle_shop_items", 0))
            + len(stall_catalog.MERCHANTS) * int(slot_data.get("stall_shop_items", 0)))


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
    return manifest


def read_seed(path: Path, slot_name: str | None = None) -> tuple[dict, dict]:
    """(audit, identity) of the seed's BOTW slot, from its zip or its slot file."""
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
    if path.suffix.lower() == ".zip":
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
             "world_schema": manifest["slot_data"].get("world_schema"), "players": players,
             "hostable": path.suffix.lower() == ".zip"}
    return audit, identity


def prepare(source: Path, *, content: Path, rpx: Path,
            slot_name: str | None = None) -> tuple[Path, Path]:
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
    pack = build(content, rpx, report, slot, PACKS,
                 resource_gate=True, event_gate=True)
    select_pack(folder, pack)
    from botw_client.gamedata_table import build as build_gamedata_table
    build_gamedata_table(content)
    return report, pack


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("seed", type=Path, help="the seed's zip, or the slot's .apbotw.json file")
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--rpx", type=Path, required=True)
    parser.add_argument("--slot", help="the BOTW player's name, when the seed has several")
    arguments = parser.parse_args()
    report, pack = prepare(arguments.seed.resolve(), content=arguments.content,
                           rpx=arguments.rpx, slot_name=arguments.slot)
    print(report)
    print(pack)
