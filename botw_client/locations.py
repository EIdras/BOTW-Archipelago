"""The 5 Hz GameData location tracker used by the AP client."""
from __future__ import annotations

import csv
import json
import time
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .shop_catalog import CATEGORY as SHOP_CATEGORY, FLAG_KIND as SHOP_FLAG_KIND
from .stall_catalog import CATEGORY as STALL_CATEGORY

ROOT = Path(__file__).resolve().parent.parent
MASTER_CSV = ROOT / "data" / "locations_master.csv"
GAMEDATA_JSON = ROOT / "data" / "gamedata.json"
# The CSV is append-only; a world schema knows its first N rows. 1: the seeds
# generated before the Divine Beast heart containers (149 rows, lab seed
# 20260916); 2: + "Vah X Heart Container" (153 rows); 3: + 32 Beedle shop
# items (185 rows, botw_client/shop_catalog.py); 4: + 28 3D stall items (213
# rows, botw_client/stall_catalog.py). botw_world declares its schema in
# slot_data["world_schema"].
SCHEMA_LOCATION_COUNTS = {1: 149, 2: 153, 3: 185, 4: 213}
WORLD_SCHEMA = 4
# Locations tracked by a saved s32 of their own (APShop_<id>), present only
# in packs built for a seed that has them.
CUSTOM_CATEGORIES = (SHOP_CATEGORY, STALL_CATEGORY)
EXPECTED_LOCATION_COUNT = SCHEMA_LOCATION_COUNTS[WORLD_SCHEMA]


@dataclass(frozen=True)
class LocationTarget:
    name: str
    flag: str
    hash_u32: int
    kind: str = "bool"
    # Custom flags exist only in packs built with them (shops of a seed that
    # has them): absent from the game, the location is simply not tracked.
    optional: bool = False


def load_targets(path: Path = MASTER_CSV,
                 world_schema: int = WORLD_SCHEMA) -> list[LocationTarget]:
    if world_schema not in SCHEMA_LOCATION_COUNTS:
        raise ValueError(f"world_schema inconnu: {world_schema}")
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != EXPECTED_LOCATION_COUNT:
        raise ValueError(
            f"{EXPECTED_LOCATION_COUNT} locations attendues, {len(rows)} trouvees")
    rows = rows[:SCHEMA_LOCATION_COUNTS[world_schema]]
    targets = []
    for row in rows:
        if not row.get("gamedata_flag") or not row.get("flag_hash"):
            raise ValueError(f"location sans GameData: {row.get('name')}")
        shop = row["category"] in CUSTOM_CATEGORIES
        targets.append(LocationTarget(
            row["name"], row["gamedata_flag"], int(row["flag_hash"]) & 0xFFFFFFFF,
            SHOP_FLAG_KIND if shop else "bool", optional=shop))
    if len({target.name for target in targets}) != len(targets):
        raise ValueError("noms de locations dupliques")
    if len({target.hash_u32 for target in targets}) != len(targets):
        raise ValueError("hash de locations dupliques")
    gamedata = json.loads(GAMEDATA_JSON.read_text(encoding="utf-8"))
    hashes = {flag_name: int(hash_value) & 0xFFFFFFFF
              for hash_value, (_, flag_name) in gamedata.items()}
    # Vanilla flags must match the game's table; custom ones are crc32 of their name.
    bad = [target.name for target in targets
           if (zlib.crc32(target.flag.encode()) if target.optional
               else hashes.get(target.flag)) != target.hash_u32]
    if bad:
        raise ValueError("flags/hash GameData incoherents: " + ", ".join(bad[:6]))
    return targets


def known_hashes(path: Path = GAMEDATA_JSON) -> np.ndarray:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return np.array(sorted(int(key) & 0xFFFFFFFF for key in raw), dtype=np.uint32)


class LocationTracker:
    def __init__(self, process, index: dict[int, int],
                 targets: list[LocationTarget] | None = None, live=None):
        self.process = process
        self.targets = targets or load_targets()
        live_index = live.index if live is not None else {}

        def in_live(target):
            return target.hash_u32 in live_index.get(target.kind, {})

        # Custom (optional) flags: live GameData only, and only when present.
        self.unavailable = [target.name for target in self.targets
                            if target.optional and not in_live(target)]
        self.targets = [target for target in self.targets
                        if not target.optional or in_live(target)]
        missing = [target.flag for target in self.targets if (
            (target.optional or target.hash_u32 not in index) and not in_live(target))]
        if missing:
            raise RuntimeError(f"{len(missing)} flags AP absents de l'index: "
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
            raise RuntimeError(f"plage AP non contigue ({self.span / 2**20:.1f} Mio)")
        self.previous: dict[int, int] | None = None

    def snapshot(self) -> dict[int, int]:
        started = time.perf_counter()
        if self.addresses:
            raw = self.process.read(self.low, self.span)
            if not raw or len(raw) != self.span:
                raise RuntimeError("lecture GameData AP incomplete")
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
                raise RuntimeError("lecture GameData vivant AP incomplete")
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
        return changed
