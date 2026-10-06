"""The French names of the world's locations and items, from the game's own texts.

    venv\\Scripts\\python tools\\build_names_fr.py [--content <update content folder>]

Archipelago shows the English names; the French game often names the same place
otherwise (Tah Muhl Shrine is the Sanctuaire de Ta'Mur). Every name of the game is
read from its message archives, English and French, under the same label
(StaticMsg/LocationMarker for places, ActorType/<kind>_Name for items); what only
Archipelago names (traps, "Item 1", the terminals) is translated here. Writes
botw_world/docs/names_fr.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import oead  # noqa: E402

from botw_patch.resources import unpack  # noqa: E402
from botw_patch.shop_items import read_labels  # noqa: E402

UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
OUTPUT = ROOT / "botw_world/docs/names_fr.md"
STALLS = {"General Stall": "magasin", "Fruit Stall": "étal de fruits", "Arrow Stall": "étal de flèches",
          "Materials Stall": "étal de matériaux", "Mushroom Stall": "étal de champignons"}
# Archipelago's own items, which the game does not name.
OWN_ITEMS = {"Weapon Shatter": "Arme brisée (piège)", "Rupoor": "Rubis maudit (piège)",
             "Hearts Down": "Cœurs en moins (piège)", "Strip Down": "Déshabillage (piège)"}
# Traps named after something of the game: (actor or label, suffix).
GAME_TRAPS = {"Blood Moon": "Lune de sang (piège)", "Cucco Swarm": "Nuée de cocottes (piège)"}


def plain(text: str) -> str:
    """The text without its control codes (0x0E, group, type, size in bytes, then
    the payload): French names open with one, their grammatical gender."""
    out, i = [], 0
    while i < len(text):
        if text[i] == "\x0e" and i + 3 < len(text):
            i += 4 + ord(text[i + 3]) // 2
            continue
        out.append(text[i])
        i += 1
    return "".join(out).rstrip("\x00")


def messages(content: Path, language: str) -> dict[tuple[str, str], str]:
    boot = oead.Sarc(unpack((content / f"Pack/Bootup_{language}.pack").read_bytes()))
    archive = oead.Sarc(unpack(bytes(boot.get_file(f"Message/Msg_{language}.product.ssarc").data)))
    out = {}
    for member in archive.get_files():
        if member.name.startswith(("StaticMsg/", "ActorType/")) and member.name.endswith(".msbt"):
            for label, text in read_labels(bytes(member.data)).items():
                out[(member.name, label)] = plain(text)
    return out


class Names:
    def __init__(self, content: Path):
        self.en, self.fr = messages(content, "EUen"), messages(content, "EUfr")
        markers = [(k, v) for k, v in self.en.items() if k[0] == "StaticMsg/LocationMarker.msbt"]
        self.place_key = {v: k for k, v in markers}
        self.actor_key = {k[1][:-len("_Name")]: k for k in self.en
                          if k[0].startswith("ActorType/") and k[1].endswith("_Name")}

    def place(self, english: str) -> str:
        return self.fr[self.place_key[english]]

    def actor(self, actor: str) -> str:
        return self.fr[self.actor_key[actor]]


def location_fr(names: Names, row: dict) -> str:
    name, category = row["name"], row["category"]
    if category in ("Shrine", "Tower", "Divine Beast"):
        return names.place(name)
    if category == "Great Fairy":
        fairy = name.removeprefix("Great Fairy ")
        actor = next(a for a in names.actor_key if a.startswith("Npc_DressFairy_")
                     and names.en[names.actor_key[a]] == fairy)
        return f"Grande fée {names.actor(actor)}"
    if category == "Divine Beast Heart":
        beast = names.place(f"Divine Beast {name.removesuffix(' Heart Container')}")
        return f"{beast} : {names.actor('Obj_HeartUtuwa_A_01')}"
    if category == "Master Sword":
        return f"{names.actor('Weapon_Sword_070')} (socle)"
    if category == "Rune Terminal":
        rune = {"Magnesis": "Obj_Magnetglove", "Remote Bombs": "Obj_RemoteBomb",
                "Stasis": "Obj_StopTimer", "Cryonis": "Obj_IceMaker"}[name.removesuffix(" Terminal")]
        return f"{names.actor(rune)} (pierre guide du Plateau)"
    if category == "Goal":
        return f"Vaincre {names.actor('Enemy_Ganon')}"
    place, _, rest = name.partition(" - ")
    item = rest.rsplit(" ", 1)[1]
    if category == "Shop":
        return f"{names.place(place)} : Beedle, objet {item}"
    stall = rest.removesuffix(f" Item {item}")
    return f"{names.place(place)} : {STALLS[stall]}, objet {item}"


def item_fr(names: Names, entry: dict) -> str:
    name, delivery = entry["name"], entry.get("delivery", {})
    if name in OWN_ITEMS:
        return OWN_ITEMS[name]
    if name in GAME_TRAPS:
        return GAME_TRAPS[name]
    if name == "Sheikah Sensor":
        return names.actor("Obj_SheikSensor")
    if name == "Fairy Tonic":
        return names.actor("Item_Cook_C_16")
    if delivery.get("kind") == "cook":
        # As the game names a dish: its base name, then its effect's
        # (StaticMsg/CookEffect, "Hasty " in English, " tempo" in French).
        effect = next(key for key, text in names.en.items()
                      if key[0] == "StaticMsg/CookEffect.msbt" and key[1].endswith("_Name")
                      and text and name.startswith(text))
        return names.actor(entry["display_actor"]) + names.fr[effect]
    actors = delivery.get("actors") or [delivery.get("actor") or entry.get("display_actor")]
    if delivery.get("kind") == "rune":
        actors = [entry["display_actor"]]
    if delivery.get("kind") == "progressive_actors":
        return " → ".join(names.actor(a) for a in actors) + " (progressif)"
    return ", ".join(names.actor(a) for a in actors)


def table(rows: list[tuple[str, str]]) -> list[str]:
    out = ["| English | Français |", "|---|---|"]
    out += [f"| {en} | {fr} |" for en, fr in rows]
    return out


def build(content: Path) -> str:
    names = Names(content)
    world = json.loads((ROOT / "botw_world/data/locations.json").read_text(encoding="utf-8"))
    item_map = json.loads((ROOT / "data/item_map.json").read_text(encoding="utf-8"))["items"]
    lines = ["# Noms en français", "",
             "Archipelago affiche les noms anglais du jeu. Voici leurs équivalents dans le jeu en français, lus dans "
             "les textes du jeu (`tools/build_names_fr.py`) ; seuls les noms propres à Archipelago (pièges, "
             "objets des boutiques) sont traduits à la main.", ""]
    groups = {}
    for row in world:
        groups.setdefault(row["category"], []).append(row)
    titles = {"Shrine": "Sanctuaires", "Tower": "Tours", "Great Fairy": "Grandes fées",
              "Divine Beast": "Créatures divines", "Divine Beast Heart": "Réceptacles des Créatures divines",
              "Master Sword": "Épée de légende", "Rune Terminal": "Pierres guides du Plateau",
              "Goal": "But", "Shop": "Boutiques de Beedle", "Stall": "Étals des villages"}
    lines += ["## Lieux", ""]
    for category, title in titles.items():
        rows = sorted((r["name"], location_fr(names, r)) for r in groups.get(category, ()))
        if rows:
            lines += [f"### {title}", "", *table(rows), ""]
    lines += ["## Objets", "", *table([(e["name"], item_fr(names, e)) for e in item_map]), ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, default=UPDATE)
    args = parser.parse_args()
    OUTPUT.write_text(build(args.content), encoding="utf-8", newline="\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
