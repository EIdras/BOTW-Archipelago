"""Load and validate the AP item -> BOTW action map."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS_JSON = ROOT / "botw_world" / "data" / "items.json"
MAP_JSON = ROOT / "data" / "item_map.json"
# The traps the client plays itself (native_trap), by effect name.
NATIVE_EFFECTS = {"cucco_swarm"}


class ItemMapError(RuntimeError):
    pass


def load_item_map(path: Path = MAP_JSON) -> dict[str, dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("items", [])
    # A renamed item keeps its former names: a seed generated before still
    # names it so (the names come from the seed's DataPackage).
    entries = entries + [{**entry, "name": former} for entry in entries
                         for former in entry.get("former_names", ())]
    names = [entry.get("name") for entry in entries]
    duplicates = [name for name, count in Counter(names).items() if count > 1]
    if duplicates:
        raise ItemMapError(f"duplicate items in the item map: {duplicates}")
    return {entry["name"]: entry for entry in entries}


def validate_item_map(items_path: Path = ITEMS_JSON,
                      map_path: Path = MAP_JSON) -> tuple[int, int]:
    mapping = load_item_map(map_path)
    # The world's filler (generated to fill the pool) is mapped but not listed.
    fillers = {name for name, entry in mapping.items() if entry.get("generated_filler")}
    expected = {entry["name"] for entry in json.loads(
        items_path.read_text(encoding="utf-8"))} - fillers
    mapped = set(mapping) - fillers
    missing = sorted(expected - mapped)
    extra = sorted(mapped - expected)
    if missing or extra:
        raise ItemMapError(f"incomplete item map: missing={missing}, extra={extra}")

    # A pickup twin only for a filler: the client takes it for a filler
    # received again (runtime._repeat_filler).
    world = {entry["name"]: entry for entry in json.loads(items_path.read_text(encoding="utf-8"))}
    useful = sorted(name for name, entry in mapping.items() if entry.get("pickup") and (
        world.get(name, {}).get("progression") or world.get(name, {}).get("useful")))
    if useful:
        raise ItemMapError(f"pickup notification for an item that is not a filler: {useful}")

    allowed = {"actors", "progressive_actors", "flags", "rune", "counter",
               "counter_at_least", "getdemo_actor", "champion_actor", "manual_prompt", "trap",
               "native_trap", "arrows", "cook", "pouch_slot"}
    from .gamedata_table import load
    gamedata = load()
    flag_types = {flag_name: kind for kind, flag_name in gamedata.values()}
    for name, entry in mapping.items():
        delivery = entry.get("delivery", {})
        kind = delivery.get("kind")
        if kind not in allowed:
            raise ItemMapError(f"{name}: invalid delivery.kind")
        if not entry.get("display_actor"):
            raise ItemMapError(f"{name}: display_actor missing")
        actors = delivery.get("actors", [])
        if kind in ("getdemo_actor", "champion_actor", "arrows"):
            actors = [delivery.get("actor")]
        if kind == "cook":
            actors = list(delivery.get("ingredients", []))
            if not 1 <= len(actors) <= 5 or not all(actors):
                raise ItemMapError(f"{name}: a dish takes 1 to 5 ingredients")
        if kind in ("actors", "progressive_actors") and not actors:
            raise ItemMapError(f"{name}: no actor")
        if kind in ("getdemo_actor", "champion_actor", "arrows") and not actors[0]:
            raise ItemMapError(f"{name}: GetDemo actor missing")
        if kind == "champion_actor" and actors[0] not in {
                'Obj_HeroSoul_Rito', 'Obj_HeroSoul_Goron',
                'Obj_HeroSoul_Gerudo', 'Obj_HeroSoul_Zora'}:
            raise ItemMapError(f"{name}: unknown base champion actor")
        for actor in [entry["display_actor"], *actors]:
            try:
                actor.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ItemMapError(f"{name}: non-ASCII actor: {actor}") from exc
        if kind == "flags":
            writes = delivery.get("writes", [])
            if not writes:
                raise ItemMapError(f"{name}: no flag write")
            for flag, _ in writes:
                if flag_types.get(flag) != "bool":
                    raise ItemMapError(f"{name}: unknown bool flag: {flag}")
        elif kind == "rune":
            flag = delivery.get("flag")
            equip_type = delivery.get("equip_type", 0)
            if flag_types.get(flag) != "bool":
                raise ItemMapError(f"{name}: unknown rune flag: {flag}")
            if not isinstance(equip_type, int) or equip_type < 0:
                raise ItemMapError(f"{name}: invalid rune equip type")
            # The terminal's Demo_OpenItemDownloadDemo ItemType (Demo003_0
            # Item01..04: Remote Bomb 0, Magnesis 1, Stasis 2, Cryonis 3; the
            # Master Cycle Zero's 5, Demo645_0 Event63).
            if delivery.get("download_type") not in (0, 1, 2, 3, 5):
                raise ItemMapError(f"{name}: invalid rune download type")
            if flag_types.get("PlayerEquipItemType") != "s32":
                raise ItemMapError("PlayerEquipItemType missing from the s32 GameData")
        elif kind == "trap":
            if not str(delivery.get("entry", "")).startswith("APTrap") or not delivery.get("text"):
                raise ItemMapError(f"{name}: a trap needs an APTrap entry and a text")
            if delivery.get("host") not in (None, "Demo007_1"):
                raise ItemMapError(f"{name}: a trap is hosted in OperationGuide or Demo007_1")
        elif kind == "pouch_slot":
            from .delivery_plan import POUCHES
            pouch = POUCHES.get(delivery.get("pouch"))
            if pouch is None:
                raise ItemMapError(f"{name}: unknown pouch")
            if flag_types.get(pouch.counter) != "s32" or any(
                    flag_types.get(flag) != "bool" for flag in pouch.flags):
                raise ItemMapError(f"{name}: unknown pouch counter or Hestu flag")
        elif kind == "native_trap":
            if delivery.get("effect") not in NATIVE_EFFECTS or not delivery.get("text"):
                raise ItemMapError(f"{name}: a native trap needs a known effect and a text")
        elif kind in ("counter", "counter_at_least"):
            flag = delivery.get("flag")
            if flag_types.get(flag) != delivery.get("type"):
                raise ItemMapError(f"{name}: unknown counter or type: {flag}")
    return len(expected), len(mapping) - len(expected)


def progressive_index(item_name: str, received_before: int, size: int) -> int:
    """Select the next piece; duplicate overflow is idempotently capped."""
    if item_name not in load_item_map():
        raise ItemMapError(f"unknown item: {item_name}")
    return min(max(received_before, 0), size - 1)
