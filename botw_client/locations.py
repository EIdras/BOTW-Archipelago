"""The 5 Hz GameData location tracker used by the AP client."""
from __future__ import annotations

import csv
import time
import zlib
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from . import gamedata_table
from .shop_catalog import CATEGORY as SHOP_CATEGORY, FLAG_KIND as SHOP_FLAG_KIND
from .stall_catalog import CATEGORY as STALL_CATEGORY

ROOT = Path(__file__).resolve().parent.parent
MASTER_CSV = ROOT / "data" / "locations_master.csv"
# The CSV is append-only; a world schema knows its first N rows. 1: the seeds
# generated before the Divine Beast heart containers (149 rows); 2: + "Vah X
# Heart Container" (153 rows); 3: + 32 Beedle shop
# items (185 rows, botw_client/shop_catalog.py); 4: + 28 3D stall items (213
# rows, botw_client/stall_catalog.py). botw_world declares its schema in
# slot_data["world_schema"].
SCHEMA_LOCATION_COUNTS = {1: 149, 2: 153, 3: 185, 4: 213}
WORLD_SCHEMA = 4
# The Great Plateau's tower reveals its own map: its map is no item.
PLATEAU_TOWER_FLAG = "MapTower_07"
# Locations tracked by a saved s32 of their own (APShop_<id>), present only
# in packs built for a seed that has them.
CUSTOM_CATEGORIES = (SHOP_CATEGORY, STALL_CATEGORY)
EXPECTED_LOCATION_COUNT = SCHEMA_LOCATION_COUNTS[WORLD_SCHEMA]


def tower_activation_flag(map_flag: str) -> str:
    """The saved bool a tower's own objects follow in a pack where its map is an
    item (botw_patch/tower_maps.py): MapTower_NN then only shows the map, and
    this flag, set when the tower is activated, is its location."""
    if not map_flag.startswith("MapTower_"):
        raise ValueError(f"not a tower flag: {map_flag}")
    return "APTower_" + map_flag[len("MapTower_"):]


@dataclass(frozen=True)
class LocationTarget:
    name: str
    flag: str
    hash_u32: int
    kind: str = "bool"
    # Custom flags exist only in packs built with them (shops of a seed that
    # has them): absent from the game, the location is simply not tracked.
    optional: bool = False
    # A custom flag a pack may track this location by instead (a tower whose map
    # is an item: tower_activation_flag), when the game has it.
    pack_flag: str | None = None

    @property
    def pack_hash(self) -> int | None:
        return zlib.crc32(self.pack_flag.encode()) if self.pack_flag else None

    def in_pack(self) -> "LocationTarget":
        """The target as a pack that declares pack_flag tracks it."""
        return replace(self, flag=self.pack_flag, hash_u32=self.pack_hash, optional=True, pack_flag=None)


def load_targets(path: Path = MASTER_CSV,
                 world_schema: int = WORLD_SCHEMA) -> list[LocationTarget]:
    if world_schema not in SCHEMA_LOCATION_COUNTS:
        raise ValueError(f"unknown world_schema: {world_schema}")
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != EXPECTED_LOCATION_COUNT:
        raise ValueError(
            f"{EXPECTED_LOCATION_COUNT} locations expected, {len(rows)} found")
    rows = rows[:SCHEMA_LOCATION_COUNTS[world_schema]]
    targets = []
    for row in rows:
        if not row.get("gamedata_flag") or not row.get("flag_hash"):
            raise ValueError(f"location without GameData: {row.get('name')}")
        shop = row["category"] in CUSTOM_CATEGORIES
        tower = row["category"] == "Tower" and row["gamedata_flag"] != PLATEAU_TOWER_FLAG
        targets.append(LocationTarget(
            row["name"], row["gamedata_flag"], int(row["flag_hash"]) & 0xFFFFFFFF,
            SHOP_FLAG_KIND if shop else "bool", optional=shop,
            pack_flag=tower_activation_flag(row["gamedata_flag"]) if tower else None))
    if len({target.name for target in targets}) != len(targets):
        raise ValueError("duplicate location names")
    if len({target.hash_u32 for target in targets}) != len(targets):
        raise ValueError("duplicate location hashes")
    gamedata = gamedata_table.load()
    hashes = {flag_name: int(hash_value) & 0xFFFFFFFF
              for hash_value, (_, flag_name) in gamedata.items()}
    # Vanilla flags must match the game's table; custom ones are crc32 of their name.
    bad = [target.name for target in targets
           if (zlib.crc32(target.flag.encode()) if target.optional
               else hashes.get(target.flag)) != target.hash_u32]
    if bad:
        raise ValueError("inconsistent GameData flags/hashes: " + ", ".join(bad[:6]))
    return targets


# Another flag of the game that also checks a location. The Master Sword's
# pedestal: its sword can be taken as a dropped weapon, without the pull nor
# Get_MasterSword_Finish, once the game counts the sword as owned (seen in play; what
# picks that mode beyond IsGet_Weapon_Sword_070 is not known). The flag of its
# map actor (F-2, HashId 2427157272) says it left the pedestal, either way.
ALTERNATE_FLAGS = {"Master Sword Pedestal": "MainField_Weapon_Sword_070_2427157272"}

# Each tower's terminal (FldObj_DownloadTerminal_A_01 of its map unit, by its
# HashId) keeps a saved flag of its own once activated. Up to 0.2.5, with most
# copies of the DLC, a pack whose maps are items had the game read its own map
# units (botw_patch/stalls.py, MAP_ARCHIVE): a tower activated then set its
# terminal's flag but not its APTower_NN, and its terminal no longer offers to
# activate it. That flag also checks the tower.
TOWER_TERMINALS = {
    "MapTower_01": "MainField_FldObj_DownloadTerminal_A_01_3650282708",
    "MapTower_02": "MainField_FldObj_DownloadTerminal_A_01_3703935795",
    "MapTower_03": "MainField_FldObj_DownloadTerminal_A_01_1285797230",
    "MapTower_04": "MainField_FldObj_DownloadTerminal_A_01_2275687969",
    "MapTower_05": "MainField_FldObj_DownloadTerminal_A_01_1943274718",
    "MapTower_06": "MainField_FldObj_DownloadTerminal_A_01_2879079867",
    "MapTower_08": "MainField_FldObj_DownloadTerminal_A_01_2934598095",
    "MapTower_09": "MainField_FldObj_DownloadTerminal_A_01_2751434839",
    "MapTower_10": "MainField_FldObj_DownloadTerminal_A_01_219123603",
    "MapTower_11": "MainField_FldObj_DownloadTerminal_A_01_1669567698",
    "MapTower_12": "MainField_FldObj_DownloadTerminal_A_01_1475180658",
    "MapTower_13": "MainField_FldObj_DownloadTerminal_A_01_4138911080",
    "MapTower_14": "MainField_FldObj_DownloadTerminal_A_01_4111125397",
    "MapTower_15": "MainField_FldObj_DownloadTerminal_A_01_1620889332",
}


def alternate_targets(targets: list[LocationTarget]) -> list[LocationTarget]:
    """The ALTERNATE_FLAGS and TOWER_TERMINALS of the locations among
    `targets`, for the tracker."""
    names = {target.name for target in targets}
    hashes = {flag_name: int(hash_value) & 0xFFFFFFFF
              for hash_value, (_, flag_name) in gamedata_table.load().items()}
    flags = list(ALTERNATE_FLAGS.items()) + [
        (target.name, TOWER_TERMINALS[target.flag]) for target in targets if target.flag in TOWER_TERMINALS]
    return [LocationTarget(name, flag, hashes[flag])
            for name, flag in flags if name in names]


def known_hashes() -> np.ndarray:
    raw = gamedata_table.load()
    return np.array(sorted(int(key) & 0xFFFFFFFF for key in raw), dtype=np.uint32)


class LocationTracker:
    def __init__(self, process, index: dict[int, int],
                 targets: list[LocationTarget] | None = None, live=None):
        self.process = process
        self.targets = targets or load_targets()
        live_index = live.index if live is not None else {}

        def in_live(target):
            return target.hash_u32 in live_index.get(target.kind, {})

        # A pack where the towers' maps are items declares their activation
        # flags: a tower is then that flag, MapTower_NN being its map.
        self.targets = [target.in_pack() if target.pack_flag and target.pack_hash in live_index.get("bool", {})
                        else target for target in self.targets]

        # Custom (optional) flags: live GameData only, and only when present.
        self.unavailable = [target.name for target in self.targets
                            if target.optional and not in_live(target)]
        self.targets = [target for target in self.targets
                        if not target.optional or in_live(target)]
        missing = [target.flag for target in self.targets if (
            (target.optional or target.hash_u32 not in index) and not in_live(target))]
        if missing:
            raise RuntimeError(f"{len(missing)} AP flags missing from the index: "
                               + ", ".join(missing[:6]))
        self.addresses = sorted(
            ((target.hash_u32, index[target.hash_u32]) for target in self.targets
             if not target.optional and target.hash_u32 in index),
            key=lambda pair: pair[1])
        # bool: the value bit in byte +7; s32: the value word at +0x14 (LiveGdt).
        self.live_addresses = {
            target.hash_u32: (live.base + live_index[target.kind][target.hash_u32]
                              + (0x14 if target.kind == "s32" else 7), target.kind)
            for target in self.targets
            if target.optional or target.hash_u32 not in index
        }
        self.by_hash = {target.hash_u32: target for target in self.targets}
        self.low = self.addresses[0][1] if self.addresses else 0
        self.high = self.addresses[-1][1] + 8 if self.addresses else 0
        self.span = self.high - self.low
        if self.span >= 64 << 20:
            raise RuntimeError(f"AP range not contiguous ({self.span / 2**20:.1f} MiB)")
        self.previous: dict[int, int] | None = None

    def snapshot(self) -> dict[int, int]:
        started = time.perf_counter()
        if self.addresses:
            raw = self.process.read(self.low, self.span)
            if not raw or len(raw) != self.span:
                raise RuntimeError("incomplete AP GameData read")
            values = {
                hash_u32: int.from_bytes(
                    raw[address - self.low + 4:address - self.low + 8], "big")
                for hash_u32, address in self.addresses
            }
        else:
            values = {}
        for hash_u32, (address, kind) in self.live_addresses.items():
            raw = self.process.read(address, 4 if kind == "s32" else 1)
            if not raw:
                raise RuntimeError("incomplete live AP GameData read")
            values[hash_u32] = (int(int.from_bytes(raw, "big") != 0) if kind == "s32"
                                else raw[0] & 1)
        self.last_read_ms = (time.perf_counter() - started) * 1000
        return values

    def poll(self) -> list[str]:
        current = self.snapshot()
        if self.previous is None:
            changed = [self.by_hash[h].name for h, value in current.items() if value]
        else:
            changed = [self.by_hash[h].name for h, value in current.items()
                       if value and not self.previous.get(h, 0)]
        self.previous = current
        return list(dict.fromkeys(changed))     # a location seen by two of its flags
