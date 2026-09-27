"""Load and validate the AP item -> BOTW action map."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS_JSON = ROOT / "botw_world" / "data" / "items.json"
MAP_JSON = ROOT / "data" / "item_map.json"


class ItemMapError(RuntimeError):
    pass


def load_item_map(path: Path = MAP_JSON) -> dict[str, dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("items", [])
    names = [entry.get("name") for entry in entries]
    duplicates = [name for name, count in Counter(names).items() if count > 1]
    if duplicates:
        raise ItemMapError(f"items dupliques dans la carte: {duplicates}")
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
        raise ItemMapError(f"carte incomplete: absents={missing}, en trop={extra}")

    allowed = {"actors", "progressive_actors", "flags", "rune", "counter",
               "counter_at_least", "getdemo_actor", "champion_actor", "manual_prompt"}
    gamedata = json.loads((ROOT / "data" / "gamedata.json").read_text(
        encoding="utf-8"))
    flag_types = {flag_name: kind for kind, flag_name in gamedata.values()}
    for name, entry in mapping.items():
        delivery = entry.get("delivery", {})
        kind = delivery.get("kind")
        if kind not in allowed:
            raise ItemMapError(f"{name}: delivery.kind invalide")
        if not entry.get("display_actor"):
            raise ItemMapError(f"{name}: display_actor absent")
        if not entry.get("evidence"):
            raise ItemMapError(f"{name}: evidence absent")
        actors = delivery.get("actors", [])
        if kind in ("getdemo_actor", "champion_actor"):
            actors = [delivery.get("actor")]
        if kind in ("actors", "progressive_actors") and not actors:
            raise ItemMapError(f"{name}: aucun acteur")
        if kind in ("getdemo_actor", "champion_actor") and not actors[0]:
            raise ItemMapError(f"{name}: acteur GetDemo absent")
        if kind == "champion_actor" and actors[0] not in {
                'Obj_HeroSoul_Rito', 'Obj_HeroSoul_Goron',
                'Obj_HeroSoul_Gerudo', 'Obj_HeroSoul_Zora'}:
            raise ItemMapError(f"{name}: acteur de Prodige de base inconnu")
        for actor in [entry["display_actor"], *actors]:
            try:
                actor.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ItemMapError(f"{name}: acteur non ASCII: {actor}") from exc
        if kind == "flags":
            writes = delivery.get("writes", [])
            if not writes:
                raise ItemMapError(f"{name}: aucune ecriture de flag")
            for flag, _ in writes:
                if flag_types.get(flag) != "bool":
                    raise ItemMapError(f"{name}: flag bool inconnu: {flag}")
        elif kind == "rune":
            flag = delivery.get("flag")
            equip_type = delivery.get("equip_type")
            if flag_types.get(flag) != "bool":
                raise ItemMapError(f"{name}: flag de rune inconnu: {flag}")
            if not isinstance(equip_type, int) or equip_type < 0:
                raise ItemMapError(f"{name}: type d'équipement de rune invalide")
            # The terminal's Demo_OpenItemDownloadDemo ItemType (Demo003_0
            # Item01..04: Remote Bomb 0, Magnesis 1, Stasis 2, Cryonis 3).
            if delivery.get("download_type") not in (0, 1, 2, 3):
                raise ItemMapError(f"{name}: type de téléchargement de rune invalide")
            if flag_types.get("PlayerEquipItemType") != "s32":
                raise ItemMapError("PlayerEquipItemType absent des GameData s32")
        elif kind in ("counter", "counter_at_least"):
            flag = delivery.get("flag")
            if flag_types.get(flag) != delivery.get("type"):
                raise ItemMapError(f"{name}: compteur/type inconnu: {flag}")
    return len(expected), len(mapping) - len(expected)


def progressive_index(item_name: str, received_before: int, size: int) -> int:
    """Select the next piece; duplicate overflow is idempotently capped."""
    if item_name not in load_item_map():
        raise ItemMapError(f"item inconnu: {item_name}")
    return min(max(received_before, 0), size - 1)
