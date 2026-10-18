"""The towers of a seed whose maps are items (the world's tower_maps option).

A tower's own objects follow its flag MapTower_NN through the LinkTagAnd tags of
its DLC map unit, three of them (five at Faron, whose two more clear its storm
and its Keese): the tower's body and its far model, its wings, its terminal and
its travel point. The tower's event (Demo004_0, entry Demo004_0_NN) signals the
first tag, which sets the flag. The game's map shows the tower's area
(Ecosystem/MapTower.sbeco, tools/map_regions.py) while the flag is true: the
executable names MapTower_01..15 next to that file. Nothing else reads these
flags, but Demo004_0's jingle once all 15 are set (scanned: the map units of the
base game and the DLC, every event, the packs).

When the maps are items, a tower's tags save its own flag instead, APTower_NN
(botw_client/locations.tower_activation_flag), declared in GameData and in the
save format: activating the tower sets it, the client counts it as the tower's
location, and MapTower_NN is left to the map item, which sets it. The Great
Plateau's tower is unchanged: its map is no item.
"""
from __future__ import annotations

from pathlib import Path
import tempfile

import oead

from botw_client.locations import tower_activation_flag
from botw_patch.resources import ResourceBuilder, digest, unpack, vanilla_digest
from botw_patch.stalls import AOC_PREFIX, TABLE_PREFIX

BOOTUP = "Pack/Bootup.pack"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
TAG = "LinkTagAnd"
# MapTower_NN: (region, map cell, HashId of its tags), read from the DLC's units.
TOWERS = {
    "01": ("Hebra", "C-2", (315504497, 1473371418, 3525389978)),
    "02": ("Tabantha", "B-4", (395919510, 3177104653, 3964276278)),
    "03": ("Gerudo", "B-6", (863578363, 2281662155, 4177544537)),
    "04": ("Wasteland", "C-7", (531111635, 1291382148, 3623679564)),
    "05": ("Woodland", "F-3", (845054308, 1352640606, 3095975803)),
    "06": ("Central", "E-5", (257842162, 642639504, 1623692830)),
    "08": ("Dueling Peaks", "G-6", (144532091, 636083628, 1750014335)),
    "09": ("Lake", "E-7", (92838883, 196598090, 1678365072)),
    "10": ("Eldin", "H-3", (871302355, 978151362, 3327351862)),
    "11": ("Akkala", "I-3", (1006148319, 2423860383, 2833205111)),
    "12": ("Lanayru", "H-4", (315541433, 2353069242, 2605152492)),
    "13": ("Hateno", "H-7", (282718492, 1039013581, 4107393406)),
    "14": ("Faron", "G-8", (1400750113, 1780810934, 2417838655, 2901086104, 3811117595)),
    "15": ("Ridgeland", "D-4", (2881494353, 3267901479, 3925213304)),
}
MAP_HASHES = {
    "C-2": "dbd7a7f2a227bdca41f7a30ef9528e8c11dc19e8432b002b3ec01fa3b6ce1a0f",
    "B-4": "9bbd64ff2bf3063a1607e4b0190e60ee1a5348d128326f2dfe182b49686dacf6",
    "B-6": "c1ace4d3282293650d4b3fa43dc1564094e4432c77b8e9ab7069ca28860a7cac",
    "C-7": "7ed28f66b9b7283cc6f70c761a926ad556a027a1e43a2cc2daf0e970e7bf1807",
    "F-3": "470bff5bf7d31fccc0f07172491960824cc448801b6a229ef4ea6b46a575732d",
    "E-5": "f1966d89a9cd4d1338a757fd665d1277637c041da7021f266fabd4069faef98c",
    "G-6": "2aebf7fd5192aae8b4cfce6ef9a4eb201445917a762c06dd6c2ac976e26addb3",
    "E-7": "9580d3c7edecc6f8b1dd8c149c2e74b3b37dd42ab41623c70d6e439cef1939d7",
    "H-3": "7266574584182bec51f98506f5996bb943290b13f892ff53296e4c018b166f21",
    "I-3": "d2fc9160bba05cb95a1b083cdf873de7d7d74b0025fe178768ac6338830ab5cd",
    "H-4": "db3730d8f85a618aa3fd7146dde65134e1bdc233629540c1f2012885bed157ef",
    "H-7": "e25fca97c455da6d1912b9766d567b0214acb52d3d01165af089678d184213ab",
    "G-8": "8e76a9a37a6234ec239aeb4063bd38e6d5f05a002e1ab4ddf0e5a0587d8d7ef4",
    "D-4": "4e3496b57dc4ba7e5bea6580033b7ddd17e21e7f970a0a7b0cdfbf5adad89226",
}
FLAGS = tuple(tower_activation_flag(f"MapTower_{number}") for number in TOWERS)
SOURCE_FILES = ("botw_patch/tower_maps.py", "botw_client/locations.py")


def unit(cell: str) -> str:
    return f"Map/MainField/{cell}/{cell}_Static.smubin"


def patch_map(raw: bytes, numbers: list[str]) -> tuple[bytes, dict]:
    """One map unit with the tags of its towers saving their own flag."""
    doc = oead.byml.from_binary(unpack(raw))
    objects = list(doc["Objs"])
    detail = {}
    for number in numbers:
        _region, _cell, tags = TOWERS[number]
        flag, own = f"MapTower_{number}", tower_activation_flag(f"MapTower_{number}")
        found = [o for o in objects if str(o["UnitConfigName"]) == TAG and "!Parameters" in o
                 and "SaveFlag" in o["!Parameters"] and str(o["!Parameters"]["SaveFlag"]) == flag]
        if sorted(int(o["HashId"]) for o in found) != sorted(tags):
            raise ValueError(f"{flag}: unexpected tags {sorted(int(o['HashId']) for o in found)}")
        for obj in found:
            obj["!Parameters"]["SaveFlag"] = own
        detail[flag] = {"flag": own, "tags": sorted(tags)}
    new = oead.byml.Hash()
    for key in doc.keys():
        new[key] = oead.byml.Array(objects) if key == "Objs" else doc[key]
    out = bytes(oead.byml.to_binary(new, big_endian=True, version=2))
    return bytes(oead.yaz0.compress(out)), detail


def generate(files: dict[str, bytes], aoc: Path) -> tuple[dict[str, bytes], list[dict]]:
    """The towers' map units (onto the stalls' when a stall shares the unit),
    their size in the table, and their flags in GameData and the save format."""
    from tools.build_game_data_mod import modify_gamedata_flags, modify_saveformat

    for name in (TABLE, BOOTUP):
        if name not in files:
            raise ValueError(f"{name} expected in the overlay")
    cells: dict[str, list[str]] = {}
    for number, (_region, cell, _tags) in TOWERS.items():
        cells.setdefault(cell, []).append(number)
    changes = []
    # A file the antivirus still holds may outlive the build here: the system's
    # temporary folder takes it, rather than failing the pack.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        stage = Path(temp)
        for name, raw in files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        builder = ResourceBuilder(stage)
        for cell, numbers in sorted(cells.items()):
            vanilla = (aoc / unit(cell)).read_bytes()
            if vanilla_digest(vanilla) != MAP_HASHES[cell]:
                raise ValueError(f"unexpected DLC map: {unit(cell)}")
            source = files.get(AOC_PREFIX + unit(cell), vanilla)
            new, detail = patch_map(source, numbers)
            builder.account(TABLE_PREFIX + unit(cell), new, vanilla)
            files[AOC_PREFIX + unit(cell)] = new
            changes.append({"resource": AOC_PREFIX + unit(cell), "towers": detail})
        builder.patch_archive(BOOTUP, {
            "GameData/gamedata.ssarc": lambda raw: (
                modify_gamedata_flags(raw, FLAGS, is_save=True, kind="bool"), list(FLAGS)),
            "GameData/savedataformat.ssarc": lambda raw: (
                modify_saveformat(raw, FLAGS), ["register the towers' own flags"]),
        })
        changes.extend(builder.changes)
        files.update(builder.finish())
    return files, changes
