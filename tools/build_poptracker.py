"""The PopTracker pack of Breath of the Wild for Archipelago.

    venv\\Scripts\\python tools\\build_poptracker.py [--content <base game content>] [--output <folder>]

PopTracker (https://github.com/black-sliver/PopTracker) shows the map with
every location of the world, coloured by what the items received allow
(the world's own logic, botw_world/catalog.requirements), and follows the
multiworld itself (its "AP" button: items received, locations checked).

The pack is built, not shipped: its map is the game's, assembled from the
player's own base game (UI/MapTex, tools/maptex.py), so that no file of the
game enters the repository; without it (a .wud/.wua game) the map is a plain
grid. Everything else comes from the world: items, locations, logic
(botw_world), positions (data/location_positions.json). The static parts are
in tools/poptracker/. Written to PACK_FOLDER: a release's own "PopTracker"
folder, where the player finds it and installs it in PopTracker by hand (the
launcher asks before building the first one: not everyone uses PopTracker);
<data>/poptracker in a source checkout.

Docs: doc/PACKS.md and doc/AUTOTRACKING.md of the PopTracker repository.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from botw_client.paths import DATA, RELEASE_MARKER  # noqa: E402
from tools import maptex  # noqa: E402
from tools.bitemico import write_png  # noqa: E402

STATIC = ROOT / "tools/poptracker"
POSITIONS = ROOT / "data/location_positions.json"
PACK_NAME = "botw_archipelago"
PACK_FOLDER = ROOT / "PopTracker" if (ROOT / RELEASE_MARKER).is_file() else DATA / "poptracker"
MAP = "Hyrule"
SCALE = 0.2                       # map pixels per world unit (MapTex2: 200 px a section)
# The map is cut to the locations, this many pixels around them: the sea and
# the borders it leaves out hold none, and PopTracker shows the rest larger.
MARGIN = 50
SOURCE_FILES = ("tools/build_poptracker.py", "tools/maptex.py", "tools/uitex.py", "data/location_positions.json",
                "tools/poptracker/scripts/init.lua", "tools/poptracker/scripts/logic.lua",
                "tools/poptracker/scripts/autotracking/archipelago.lua")


def catalog():
    """botw_world.catalog without its package's __init__ (which needs Archipelago)."""
    if "botw_world" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "botw_world", ROOT / "botw_world/__init__.py",
            submodule_search_locations=[str(ROOT / "botw_world")])
        sys.modules["botw_world"] = importlib.util.module_from_spec(spec)
    from botw_world import catalog as module
    return module


def code(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower().replace("'", "")).strip("_")


# --- Items --------------------------------------------------------------------

# Items shown, in rows: (name, icon label, colour). Fillers and traps are not.
RUNE, ARMOR, CHAMPION, GEAR, LIFE, EVENT, MAP_COLOUR = ("#2f6fae", "#3d7a3f", "#b08a2e", "#6b6f7d",
                                                       "#a8323a", "#6d4a9c", "#c07a2a")
ROWS = [
    [("Paraglider", "GLD", GEAR), ("Magnesis", "MAG", RUNE), ("Remote Bomb", "BOMB", RUNE),
     ("Stasis", "STA", RUNE), ("Cryonis", "CRY", RUNE), ("Sheikah Sensor", "SNS", RUNE)],
    [("Revali's Gale", "REV", CHAMPION), ("Daruk's Protection", "DAR", CHAMPION),
     ("Urbosa's Fury", "URB", CHAMPION), ("Mipha's Grace", "MIP", CHAMPION),
     ("Master Sword", "MS", GEAR), ("Hylian Shield", "HYL", GEAR)],
    [("Flamebreaker Set", "FIRE", ARMOR), ("Zora Set", "ZORA", ARMOR), ("Gerudo Set", "GER", ARMOR),
     ("Warm Doublet", "WARM", ARMOR), ("Snowquill Set", "SNOW", ARMOR), ("Desert Voe Set", "VOE", ARMOR)],
    [("Rubber Set", "RUB", ARMOR), ("Progressive Climbing Gear", "CLM", ARMOR),
     ("Progressive Stealth Set", "STL", ARMOR), ("Barbarian Set", "BARB", ARMOR),
     ("Ancient Set", "ANC", ARMOR), ("Radiant Set", "RAD", ARMOR)],
    [("Heart Container", "HC", LIFE), ("Stamina Vessel", "STAM", LIFE),
     ("Champion's Tunic", "TUN", GEAR), ("Ancient Bridle", "BRDL", GEAR),
     ("Ancient Saddle", "SADL", GEAR), ("Korok Mask", "KRK", ARMOR)],
    [("Master Cycle Zero", "MCZ", GEAR), ("Travel Medallion", "TRV", GEAR), ("Epona", "EPO", GEAR),
     ("Weapon Pouch Upgrade", "WPN", LIFE), ("Bow Pouch Upgrade", "BOW", LIFE),
     ("Shield Pouch Upgrade", "SHLD", LIFE)],
]
# The tower maps (the world's tower_maps option), in the order of their towers.
MAP_ROWS = [
    [("Hebra Map", "HEB", MAP_COLOUR), ("Tabantha Map", "TAB", MAP_COLOUR), ("Gerudo Map", "GER", MAP_COLOUR),
     ("Wasteland Map", "WST", MAP_COLOUR), ("Woodland Map", "WOOD", MAP_COLOUR), ("Central Map", "CEN", MAP_COLOUR),
     ("Dueling Peaks Map", "DUEL", MAP_COLOUR)],
    [("Lake Map", "LAKE", MAP_COLOUR), ("Eldin Map", "ELD", MAP_COLOUR), ("Akkala Map", "AKK", MAP_COLOUR),
     ("Lanayru Map", "LAN", MAP_COLOUR), ("Hateno Map", "HAT", MAP_COLOUR), ("Faron Map", "FAR", MAP_COLOUR),
     ("Ridgeland Map", "RDG", MAP_COLOUR)],
]
BEAST_ROW = [("Freed - Divine Beast Vah Ruta", "RUTA"), ("Freed - Divine Beast Vah Rudania", "RUDA"),
             ("Freed - Divine Beast Vah Medoh", "MEDO"), ("Freed - Divine Beast Vah Naboris", "NABO")]

# 5 x 7 capitals and digits, one string a row.
FONT = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11110 00001 00001 01110 00001 00001 11110",
}


def rgb(colour: str) -> np.ndarray:
    return np.array([int(colour[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.int32)


def icon(label: str, colour: str, size: int = 48) -> np.ndarray:
    """A label for an item the game draws no icon of: white letters on nothing,
    like the game's own (masks it colours white), a bar of its family's colour
    under them. (size, size, 4) RGBA."""
    scale = 2
    width = len(label) * 5 * scale + (len(label) - 1) * scale
    left, top = (size - width) // 2, (size - 7 * scale) // 2 - 3
    glyph = np.zeros((size, size), dtype=bool)
    for index, char in enumerate(label):
        for row, bits in enumerate(FONT[char].split()):
            for column, bit in enumerate(bits):
                if bit == "1":
                    px = left + index * 6 * scale + column * scale
                    py = top + row * scale
                    glyph[py:py + scale, px:px + scale] = True
    outline = np.zeros_like(glyph)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            outline |= np.roll(np.roll(glyph, dy, 0), dx, 1)
    image = np.zeros((size, size, 4), dtype=np.uint8)
    image[outline] = (15, 15, 15, 200)
    image[glyph] = (255, 255, 255, 255)
    bar = top + 7 * scale + 4
    image[bar:bar + 3, left:left + width, :3] = rgb(colour)
    image[bar:bar + 3, left:left + width, 3] = 255
    return image


def dot(colour: str, filled: bool, size: int = 32) -> np.ndarray:
    y, x = np.mgrid[0:size, 0:size]
    distance = np.hypot(x - (size - 1) / 2, y - (size - 1) / 2)
    image = np.zeros((size, size, 4), dtype=np.int32)
    ring = (distance <= size / 2 - 1) & (distance > size / 2 - 5)
    disc = distance <= size / 2 - 1 if filled else ring
    image[disc, :3] = rgb(colour) if filled else 120
    image[disc, 3] = 255
    image[ring, :3] = np.minimum(rgb(colour) + 60, 255) if filled else 160
    return image.astype(np.uint8)


def png(image: np.ndarray) -> bytes:
    """An RGBA image as PNG bytes (tools/bitemico.write_png)."""
    height, width, _ = image.shape
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "image.png"
        write_png(path, width, height, np.ascontiguousarray(image).tobytes())
        return path.read_bytes()


# The game's icons, which the player may add (ICONS_FOLDER, subfolders too):
# the files are matched by name, whatever the wiki that serves them calls them
# ("Zora Armor - BotW Icon.png", "BotW_Zora_Armor_Icon.png" and "Zora-armor.png"
# all give zoraarmor; "Revali-gale.png" is Revali's Gale). An image of each item,
# or of each piece for a progressive one, in order of delivery; the first name
# found wins. What is missing keeps its badge.
ICON_NAMES = {
    "paraglider": ["Paraglider"], "magnesis": ["Magnesis"],
    "remote_bomb": ["Remote Bomb", "Remote Bombs", "Remote Bomb Round", "Remote Bomb Cube"],
    "stasis": ["Stasis"], "cryonis": ["Cryonis"], "sheikah_sensor": ["Sheikah Sensor", "Sheikah Sensor+", "Sheikah Slate", "Sheikah Slate2"],
    "revalis_gale": ["Revali's Gale"], "daruks_protection": ["Daruk's Protection"],
    "urbosas_fury": ["Urbosa's Fury"], "miphas_grace": ["Mipha's Grace"],
    "master_sword": ["Master Sword"], "hylian_shield": ["Hylian Shield"],
    "flamebreaker_set": ["Flamebreaker Armor"], "zora_set": ["Zora Armor"],
    "gerudo_set": ["Gerudo Top", "Gerudo Veil"], "warm_doublet": ["Warm Doublet"],
    "snowquill_set": ["Snowquill Tunic"], "desert_voe_set": ["Desert Voe Spaulder"],
    "rubber_set": ["Rubber Armor"], "barbarian_set": ["Barbarian Armor"],
    "ancient_set": ["Ancient Cuirass"], "radiant_set": ["Radiant Shirt"],
    "heart_container": ["Heart Container"],
    "stamina_vessel": ["Stamina Vessel", "Energizing5"],         # the full stamina wheel
    "champions_tunic": ["Champion's Tunic"], "ancient_bridle": ["Ancient Bridle"],
    "ancient_saddle": ["Ancient Saddle"], "korok_mask": ["Korok Mask"],
    "master_cycle_zero": ["Master Cycle Zero", "Master Cycle Rune", "Master Cycle"],
    "travel_medallion": ["Travel Medallion"], "epona": ["Epona"],
    "weapon_pouch_upgrade": ["Weapon Pouch Upgrade", "Weapon Pouch"],
    "bow_pouch_upgrade": ["Bow Pouch Upgrade", "Bow Pouch"],
    "shield_pouch_upgrade": ["Shield Pouch Upgrade", "Shield Pouch"],
    "progressive_climbing_gear_1": ["Climbing Gear"], "progressive_climbing_gear_2": ["Climber's Bandanna"],
    "progressive_climbing_gear_3": ["Climbing Boots"],
    "progressive_stealth_set_1": ["Stealth Chest Guard"], "progressive_stealth_set_2": ["Stealth Mask"],
    "progressive_stealth_set_3": ["Stealth Tights"],
    "freed_divine_beast_vah_ruta": ["Vah Ruta", "Divine Beast Vah Ruta", "Ruta Emblem"],
    "freed_divine_beast_vah_rudania": ["Vah Rudania", "Divine Beast Vah Rudania", "Rudania Emblem"],
    "freed_divine_beast_vah_medoh": ["Vah Medoh", "Divine Beast Vah Medoh", "Medoh Emblem"],
    "freed_divine_beast_vah_naboris": ["Vah Naboris", "Divine Beast Vah Naboris", "Naboris Emblem"],
    "shrines_cleared": ["Shrine", "Map Shrine", "Shrine of Trials", "Spirit Orb"],
    # The squares' images in a place's popup: the map's own icons.
    "dot_shrine": ["Map Shrine"], "dot_shop": ["Map Store"], "dot_stall": ["Map Store"],
}
ICONS_FOLDER = DATA / "poptracker/icons"
# The game's own interface icons (tools/uitex.py, from the player's update):
# what it draws in 2D for a few items, the effect icons its armour shows in the
# inventory, its map's icons. Under the player's icons, over the labels.
UI_ICONS = {
    "heart_container": "Nt_HeartNew_00^f", "stamina_vessel": "Nt_PauseIconGanbari_04^f",
    "sheikah_sensor": "Nt_SeekSensorIcon_00^s",
    "master_sword": "Nt_PauseIcon_00^s", "hylian_shield": "Nt_PauseIcon_02^s",
    "flamebreaker_set": "Nt_PauseIconFire_00^t", "zora_set": "Nt_PauseIconSwim_00^t",
    "rubber_set": "Nt_PauseIconElect_00^t", "warm_doublet": "Nt_PauseIconCool_00^t",
    "snowquill_set": "Nt_PauseIconCool_00^t", "desert_voe_set": "Nt_PauseIconHot_00^t",
    "barbarian_set": "Nt_PauseIconAttack_00^t", "ancient_set": "Nt_PauseIconKodai_00^t",
    "gerudo_set": "Nt_PauseIcon_03^s", "radiant_set": "Nt_PauseIcon_03^s",
    "champions_tunic": "Nt_PauseIcon_03^s",
    "weapon_pouch_upgrade": "Nt_PauseIcon_00^s", "bow_pouch_upgrade": "Nt_PauseIcon_01^s",
    "shield_pouch_upgrade": "Nt_PauseIcon_02^s", "epona": "Nt_MapHorseIconL_00^t",
    **{f"progressive_climbing_gear_{n}": "Nt_PauseIconMountain_00^t" for n in (1, 2, 3)},
    **{f"progressive_stealth_set_{n}": "Nt_PauseIconNoise_00^t" for n in (1, 2, 3)},
    "freed_divine_beast_vah_rudania": "Nt_IconSinJuNew_00^d",
    "freed_divine_beast_vah_ruta": "Nt_IconSinJuNew_01^d",
    "freed_divine_beast_vah_medoh": "Nt_IconSinJuNew_02^d",
    "freed_divine_beast_vah_naboris": "Nt_IconSinJuNew_03^d",
    "shrines_cleared": "Nt_MapDungeonNew_00^t",
    "dot_shrine": "Nt_MapDungeonNew_00^t", "dot_tower": "Nt_MapTowerNew_00^t",
    "dot_shop": "Nt_MapHatago_00^t", "dot_stall": "Nt_YorozuIcon_00^t", "dot_goal": "Nt_MapCastle_00^t",
    "dot_rune_terminal": "Nt_PauseIconKodai_00^t", "dot_divine_beast": "Nt_IconSinJuNew_01^d",
    "dot_master_sword": "Nt_PauseIcon_00^s",
}


# The icons of every item of the grid, published apart from the code: the
# game draws no image of most items, and only stand-ins of the others (an
# armour's effect, an inventory tab, white masks). The file attached to the
# GitHub release "tracker-icons" (never committed: the images are Nintendo's,
# not under the project's licence); the launcher fetches it once into
# ICONS_FOLDER/release, the maintainer makes it from a folder of icons with
# --package-icons. The game's own icons stay for the map's squares, and for
# the grid when offline.
RELEASE_ICONS = tuple(key for key in ICON_NAMES if not key.startswith("dot_"))
ICONS_URL = "https://github.com/EIdras/BOTW-Archipelago/releases/download/tracker-icons/tracker-icons.zip"
ICONS_LIMIT = 4 << 20             # bytes: the zip holds a few small PNG


def package_icons(folder: Path, target: Path) -> list[str]:
    """The release's zip of RELEASE_ICONS, from `folder`; returns those not found."""
    found = game_icons(folder)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for key in RELEASE_ICONS:
            if key in found:
                archive.writestr(f"{ICON_NAMES[key][0]}.png", found[key])
    return [ICON_NAMES[key][0] for key in RELEASE_ICONS if key not in found]


def fetch_icons(folder: Path = ICONS_FOLDER, url: str = ICONS_URL) -> bool:
    """The release's icons, once, into folder/release: True when fetched.
    Nothing when they are there already or the player has their own."""
    import io
    import urllib.request
    target = folder / "release"
    if target.is_dir() or all(key in game_icons(folder) for key in RELEASE_ICONS):
        return False
    from botw_client.protocol import tls_context       # a new Windows lacks GitHub's root
    with urllib.request.urlopen(url, timeout=15, context=tls_context()) as response:
        data = response.read(ICONS_LIMIT + 1)
    if len(data) > ICONS_LIMIT:
        raise ValueError("tracker icons: archive too large")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = {}
        for member in archive.infolist():
            name = member.filename
            if (member.is_dir() or "/" in name or "\\" in name or ".." in name
                    or not name.lower().endswith(".png")):
                raise ValueError(f"tracker icons: unexpected file {name!r}")
            files[name] = archive.read(member)
    staging = folder / "release.partial"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    for name, content in files.items():
        (staging / name).write_bytes(content)
    staging.rename(target)
    return True


def update_content() -> Path | None:
    """The update's content folder: the launcher profile's copy, else Cemu's."""
    try:
        from tools import cemu_profile
        content = cemu_profile.update() / "content"
        if content.is_dir():
            return content
    except Exception:  # noqa: BLE001 - no profile: Cemu's own
        pass
    try:
        from tools.cemu_install import detect
        return detect().update / "content"
    except Exception:  # noqa: BLE001 - no Cemu: no interface icons
        return None


def ui_icons(content: Path | None) -> dict[str, np.ndarray]:
    """{image key: RGBA} of UI_ICONS; a progressive piece gets its number."""
    if content is None:
        return {}
    from tools import uitex
    try:
        textures = uitex.textures(content)
    except (OSError, KeyError, ValueError):
        return {}
    found = {}
    for key, name in UI_ICONS.items():
        try:
            image = uitex.decode(textures[name])
        except (KeyError, ValueError):
            continue
        piece = re.search(r"_(\d)$", key)
        found[key] = numbered(image, piece.group(1)) if key.startswith("progressive_") and piece else image
    return found


def numbered(image: np.ndarray, digit: str) -> np.ndarray:
    """The icon with a piece's number in its lower right corner."""
    image = image.copy()
    height, width = image.shape[:2]
    scale = max(1, height // 24)
    left, top = width - 6 * scale, height - 8 * scale
    for row, bits in enumerate(FONT[digit].split()):
        for column, bit in enumerate(bits):
            if bit == "1":
                y, x = top + row * scale, left + column * scale
                image[y - 1:y + scale + 1, x - 1:x + scale + 1] = (15, 15, 15, 230)
    for row, bits in enumerate(FONT[digit].split()):
        for column, bit in enumerate(bits):
            if bit == "1":
                y, x = top + row * scale, left + column * scale
                image[y:y + scale, x:x + scale] = (255, 220, 90, 255)
    return image
NOISE = re.compile(r"botw|breathofthewild|icon|file")


def icon_key(text: str) -> str:
    text = text.lower().replace("'s ", " ").replace("'", "")
    return NOISE.sub("", re.sub(r"[^a-z0-9]+", "", text))


def game_icons(folder: Path) -> dict[str, bytes]:
    """{image key: PNG bytes} of the icons found in `folder` and its subfolders.
    A name met twice keeps its plain file before its "+" one (the Champions'
    Ballad's upgraded powers)."""
    if not folder.is_dir():
        return {}
    files = {}
    for path in sorted((path for path in folder.rglob("*") if path.suffix.lower() == ".png"),
                       key=lambda path: ("+" in path.stem, path.as_posix())):
        files.setdefault(icon_key(path.stem), path)
    found = {}
    for key, names in ICON_NAMES.items():
        for name in names:
            path = files.get(icon_key(name))
            if path is not None:
                found[key] = path.read_bytes()
                break
    return found


def items(cat, icons: dict[str, bytes] | None = None) -> tuple[list, dict, dict]:
    """items.json, the images (an icon's PNG bytes, else a badge), and the AP id
    -> code map of the tracked items."""
    icons = icons or {}
    rows = {row["name"]: row for row in cat.ITEMS}
    entries, images, ids = [], {}, {}

    def image(path, key, label, colour):
        images[path] = icons.get(key) if key in icons else icon(label, colour)

    for name, label, colour in [entry for row in ROWS + MAP_ROWS for entry in row]:
        item = rows[name]
        item_code = code(name)
        ids[item["id"]] = item_code
        path = f"images/items/{item_code}.png"
        count = int(item.get("count", 1))
        if name.startswith("Progressive "):
            stages = []
            for stage in range(1, count + 1):
                stage_path = f"images/items/{item_code}_{stage}.png"
                image(stage_path, f"{item_code}_{stage}", label[:3] + str(stage), colour)
                stages.append({"name": f"{name} ({stage}/{count})", "img": stage_path,
                               "codes": item_code, "inherit_codes": True})
            entries.append({"name": name, "type": "progressive", "allow_disabled": True,
                            "loop": False, "stages": stages})
            continue
        image(path, item_code, label, colour)
        if count > 1:
            entries.append({"name": name, "type": "consumable", "img": path, "codes": item_code,
                            "min_quantity": 0, "max_quantity": count})
        else:
            entries.append({"name": name, "type": "toggle", "img": path, "codes": item_code})
    for name, label in BEAST_ROW:
        path = f"images/items/{code(name)}.png"
        image(path, code(name), label, EVENT)
        entries.append({"name": name, "type": "toggle", "img": path, "codes": code(name)})
    image("images/items/shrines_cleared.png", "shrines_cleared", "SHR", EVENT)
    entries.append({"name": "Shrines cleared", "type": "consumable",
                    "img": "images/items/shrines_cleared.png", "codes": "shrines_cleared",
                    "min_quantity": 0, "max_quantity": 120})
    # Toggled by the auto-tracker so that the rules are evaluated again.
    images["images/items/seed_loaded.png"] = icon("AP", EVENT)
    entries.append({"name": "Seed loaded", "type": "toggle",
                    "img": "images/items/seed_loaded.png", "codes": "seed_loaded"})
    return entries, images, ids


# --- Locations -------------------------------------------------------------------

DOT = {"Shrine": "#3a8fd6", "Tower": "#e08a2c", "Divine Beast": "#c94a4a", "Shop": "#2fa36b",
       "Stall": "#2fa36b", "Great Fairy": "#d65fb5", "Master Sword": "#e6d23a",
       "Rune Terminal": "#3ac0c9", "Goal": "#ffffff"}


def place_of(row: dict) -> str:
    """The map square a location belongs to: a stable's two Beedle items, a
    stall's, a Divine Beast and its heart, a plateau shrine and its terminal."""
    name, kinds = row["name"], set(row["category"].split("|"))
    if kinds & {"Shop", "Stall"}:
        return re.sub(r" Item \d+$", "", name)
    if "Divine Beast Heart" in kinds:
        return "Divine Beast " + name.replace(" Heart Container", "")
    return name


def world_requirements(cat, row: dict) -> tuple:
    """requirements(row), an event "Freed - Divine Beast X" counted as the world
    counts it (botw_world, create_regions: the beast reachable, not checked):
    the beast's own groups. A heart container is picked up before the beast's
    control unit is."""
    rows = {other["name"]: other for other in cat.LOCATIONS}
    out = []
    for names, count in cat.requirements(row):
        if any(name.startswith("Freed - ") for name in names):
            if len(names) != 1:
                raise ValueError(f"{row['name']}: an event among alternatives")
            out.extend(world_requirements(cat, rows[names[0][len("Freed - "):]]))
        else:
            out.append((names, count))
    return tuple(dict.fromkeys(out))


def world_map_keys(cat, row: dict) -> tuple[str, ...]:
    """map_keys(row), and those of the Divine Beast an event names, as
    world_requirements counts the beast."""
    rows = {other["name"]: other for other in cat.LOCATIONS}
    keys = list(cat.map_keys(row))
    for names, _count in cat.requirements(row):
        for name in names:
            if name.startswith("Freed - "):
                keys += world_map_keys(cat, rows[name[len("Freed - "):]])
    return tuple(dict.fromkeys(keys))


def crop_box(positions: dict) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the map shown, in pixels of the whole map."""
    xs, ys = zip(*(maptex.pixel(x, z, SCALE) for x, z in positions.values()))
    width, height = int(12000 * SCALE), int(10000 * SCALE)
    return (max(0, min(xs) - MARGIN), max(0, min(ys) - MARGIN),
            min(width, max(xs) + MARGIN), min(height, max(ys) + MARGIN))


def locations(cat, positions: dict, origin: tuple[int, int] = (0, 0)) -> tuple[list, dict, dict, dict]:
    """locations.json, the AP id -> section path map, the Lua requirement table,
    and the maps each location asks for when the maps are region keys."""
    places: dict[str, dict] = {}
    sections, requirements, maps = {}, {}, {}
    for row in cat.LOCATIONS:
        name = row["name"]
        kinds = set(row["category"].split("|"))
        key = place_of(row)
        if "Rune Terminal" in kinds:
            # Before its plateau shrine: one square for both.
            key = next(r["name"] for r in cat.LOCATIONS if "Shrine" in r["category"]
                       and positions[r["name"]] == positions[name])
        kind = next(k for k in DOT if k in kinds) if kinds & set(DOT) else "Shrine"
        x, y = maptex.pixel(*positions[name], SCALE)
        x, y = x - origin[0], y - origin[1]
        place = places.setdefault(key, {
            "name": key, "chest_unopened_img": f"images/dots/{code(kind)}.png",
            "chest_opened_img": "images/dots/opened.png",
            "map_locations": [{"map": MAP, "x": x, "y": y}], "sections": []})
        section = {"name": name, "item_count": 1}
        if name == cat.GOAL_LOCATION:
            section["access_rules"] = [["$botw_ganon"]]
        else:
            section["access_rules"] = [[f"$botw_access|{row['id']}"]]
            requirements[row["id"]] = world_requirements(cat, row)
            sections[row["id"]] = f"@{key}/{name}"
            keys = world_map_keys(cat, row)
            if keys:
                # Optional, in brackets: without its maps, a location is a
                # sequence break (yellow), not out of reach (botw_maps).
                section["access_rules"][0].append(f"[$botw_maps|{row['id']}]")
                maps[row["id"]] = keys
        if kinds & {"Shop", "Stall"}:
            # Shown when the seed has it (one of a place's items is enough).
            section["visibility_rules"] = [[f"$botw_in_seed|{row['id']}"]]
            place.setdefault("visibility_rules", []).append([f"$botw_in_seed|{row['id']}"])
        place["sections"].append(section)
    return list(places.values()), sections, requirements, maps


def lua_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, dict):
        return "{" + ", ".join(f"[{lua_value(k)}] = {lua_value(v)}" for k, v in value.items()) + "}"
    return "{" + ", ".join(lua_value(v) for v in value) + "}"


def data_lua(cat, item_ids: dict, sections: dict, requirements: dict, maps: dict | None = None) -> str:
    def groups(value):
        return [[[code(name) for name in names], count] for names, count in value]

    goal = next(row for row in cat.LOCATIONS if row["name"] == cat.GOAL_LOCATION)
    goal_section = f"@{place_of(goal)}/{goal['name']}"
    by_name = {row["name"]: row["id"] for row in cat.LOCATIONS}
    beasts = {by_name[name[len("Freed - "):]]: code(name) for name, _ in BEAST_ROW}
    shrines = [row["id"] for row in cat.LOCATIONS if "Shrine" in row["category"]]
    lines = ["-- Generated by tools/build_poptracker.py from the world (botw_world): do not edit.",
             f"ITEM_CODES = {lua_value(item_ids)}",
             f"LOCATION_SECTIONS = {lua_value(sections)}",
             "REQUIREMENTS = {"]
    lines += [f"  [{location_id}] = {lua_value(groups(value))},"
              for location_id, value in sorted(requirements.items())]
    lines += ["}", "MAP_KEYS = {"]
    lines += [f"  [{location_id}] = {lua_value([code(name) for name in names])},"
              for location_id, names in sorted((maps or {}).items())]
    lines += ["}",
              f"GOAL_REQUIREMENTS = {lua_value(groups(cat.requirements(goal)))}",
              # Not an AP location: cleared by the slot's goal status.
              f"GOAL_SECTION = {lua_value(goal_section)}",
              f"RUNES = {lua_value([code(name) for name in cat.RUNES])}",
              f"BEAST_EVENTS = {lua_value(beasts)}",
              f"SHRINES = {lua_value(shrines)}", ""]
    return "\n".join(lines)


def layouts() -> dict:
    grid = [[code(name) for name, _label, _colour in row] for row in ROWS]
    grid.append([code(name) for name, _ in BEAST_ROW] + ["shrines_cleared"])
    grid += [[code(name) for name, _label, _colour in row] for row in MAP_ROWS]
    return {
        "item_grid": {"type": "itemgrid", "item_margin": "3,3", "item_size": "40,40",
                      "h_alignment": "center", "rows": grid},
        "tracker_default": {"type": "container", "background": "#00000000", "content": {
            "type": "dock", "dropshadow": True, "content": [
                {"type": "dock", "dock": "left", "v_alignment": "stretch", "content": [
                    {"type": "group", "header": "Items", "dock": "top",
                     "content": {"type": "layout", "key": "item_grid"}},
                    {"type": "group", "header": "Pinned locations", "content": {
                        "type": "recentpins", "style": "wrapped", "h_alignment": "stretch",
                        "v_alignment": "stretch", "compact": True}}]},
                {"type": "map", "maps": [MAP]}]}},
        "tracker_broadcast": {"type": "layout", "key": "item_grid"},
    }


# --- The map ------------------------------------------------------------------

def plain_map() -> np.ndarray:
    """No base game folder to read: a grid of the map's sections."""
    width, height = int(12000 * SCALE), int(10000 * SCALE)
    image = np.full((height, width, 3), (34, 42, 52), dtype=np.uint8)
    step = int(maptex.SECTION * SCALE)
    image[::step, :] = (70, 82, 96)
    image[:, ::step] = (70, 82, 96)
    return image


def base_content() -> Path | None:
    """The base game's content folder: the one of the Cemu the launcher's profile
    was made from (tools/cemu_profile.game), else of the default Cemu."""
    try:
        from tools import cemu_profile
        game = cemu_profile.game()
    except Exception:  # noqa: BLE001 - no profile yet: Cemu's own settings
        try:
            from tools.cemu_install import detect
            game = detect().game
        except Exception:  # noqa: BLE001 - no Cemu found: the plain map
            return None
    content = game.parent.parent / "content"
    return content if game.suffix.lower() == ".rpx" and content.is_dir() else None


def build(content: Path | None, output: Path, icons: Path = ICONS_FOLDER) -> tuple[Path, bool]:
    cat = catalog()
    positions = json.loads(POSITIONS.read_text(encoding="utf-8"))
    files: dict[str, bytes] = {}
    for path in sorted(STATIC.rglob("*.lua")):
        files[path.relative_to(STATIC).as_posix()] = path.read_bytes()
    found = {**ui_icons(update_content()), **game_icons(icons)}
    item_entries, images, item_ids = items(cat, found)
    left, top, right, bottom = crop_box(positions)
    place_entries, sections, requirements, maps = locations(cat, positions, (left, top))
    files["scripts/data.lua"] = data_lua(cat, item_ids, sections, requirements, maps).encode()
    for kind, colour in DOT.items():
        images[f"images/dots/{code(kind)}.png"] = found.get(f"dot_{code(kind)}", dot(colour, True))
    images["images/dots/opened.png"] = dot("#777777", False)
    game_map = False
    if content is not None:
        try:
            image = maptex.assemble(content)
            game_map = True
        except (OSError, ValueError):
            image = plain_map()
    else:
        image = plain_map()
    alpha = np.full(image.shape[:2] + (1,), 255, dtype=np.uint8)
    images["images/map.png"] = np.concatenate([image, alpha], 2)[top:bottom, left:right]
    files.update({path: value if isinstance(value, bytes) else png(value)
                  for path, value in images.items()})
    files["items/items.json"] = json.dumps(item_entries, indent=1).encode()
    files["locations/locations.json"] = json.dumps(place_entries, indent=1).encode()
    files["maps/maps.json"] = json.dumps([{
        "name": MAP, "location_size": 30, "location_border_thickness": 3,
        "img": "images/map.png"}], indent=1).encode()
    files["layouts/tracker.json"] = json.dumps(layouts(), indent=1).encode()
    files["manifest.json"] = json.dumps({
        "name": "Breath of the Wild Archipelago", "game_name": cat.GAME,
        "package_uid": PACK_NAME, "package_version": cat.WORLD_VERSION,
        "platform": "wiiu", "author": "EIdras", "min_poptracker_version": "0.26.2",
        "variants": {"map": {"display_name": "Map tracker", "flags": ["ap"]}}}, indent=1).encode()
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"{PACK_NAME}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    return target, game_map


def stamp(content: Path | None) -> str:
    """What the pack was built from: its sources, the world, the map's source, the icons."""
    import hashlib
    digest = hashlib.sha256()
    for name in (*SOURCE_FILES, "botw_world/catalog.py", "botw_world/data/items.json",
                 "botw_world/data/locations.json", "botw_world/data/logic.csv",
                 "botw_world/archipelago.json"):
        digest.update((ROOT / name).read_bytes())
    digest.update(str(content).encode() + str(update_content()).encode())
    for key, data in sorted(game_icons(ICONS_FOLDER).items()):
        digest.update(key.encode() + data)
    return digest.hexdigest()


STAMP = DATA / "poptracker/stamp.txt"            # what the pack in PACK_FOLDER was built from
DECLINED = DATA / "poptracker/declined.txt"      # the stamp the player said no to


def build_command() -> str:
    """The command that builds the pack, from the launcher's folder."""
    python = Path(sys.executable)
    try:
        python = python.relative_to(ROOT)
    except ValueError:
        pass
    return f"{python} -I tools\\build_poptracker.py"


def fetch_icons_said(say) -> None:
    try:
        if fetch_icons():
            say("PopTracker: the release's icons fetched")
    except Exception as exc:  # noqa: BLE001 - offline: the game's icons and labels
        say(f"PopTracker: the release's icons not fetched ({exc})")


def plain_map_reason(content: Path | None) -> str:
    """Why the map is a plain grid, said after the pack's path."""
    if content is None:
        return (" (plain map: no base game folder found, as with a .wud/.wua game or a drive not "
                "connected)")
    return f" (plain map: the base game could not be read in {content}; the next session builds it again)"


def built_stamp(content: Path | None, game_map: bool) -> str:
    """The stamp a pack just built records: without the game's map read, the one
    of no game, so that the next session builds the map again (a drive
    disconnected while it was read)."""
    return stamp(content if game_map else None)


def ensure_pack(say=print, confirm=lambda prompt: True) -> None:
    """The launcher's step, one line at each launch whatever happens: the pack
    in PACK_FOLDER is kept up to date with what it is made of. The first one in
    the folder is built only if the player wants it (`confirm`), and a no is
    remembered until the pack would change. Never blocks the game."""
    target = PACK_FOLDER / f"{PACK_NAME}.zip"
    try:
        content = base_content()
        outdated = target.is_file()
        if outdated:
            fetch_icons_said(say)
        current = stamp(content)
        if outdated and STAMP.is_file() and STAMP.read_text(encoding="utf-8") == current:
            say(f"PopTracker pack: up to date, not rebuilt ({target})")
            return
        if not outdated:
            if DECLINED.is_file() and DECLINED.read_text(encoding="utf-8") == current:
                say("PopTracker pack: not built, as you answered (asked again with the next version). "
                    f"To build it, run in this folder: {build_command()}")
                return
            say("PopTracker pack: none in this folder yet. PopTracker is an optional map tracker "
                "that follows the room (see the PopTracker guide).")
            if not confirm("Build the PopTracker pack? (a few seconds)"):
                DECLINED.parent.mkdir(parents=True, exist_ok=True)
                DECLINED.write_text(current, encoding="utf-8")
                say("PopTracker pack: not built. You will be asked again with the next version; "
                    f"to build it before, run in this folder: {build_command()}")
                return
            fetch_icons_said(say)
            current = stamp(content)
        target, game_map = build(content, PACK_FOLDER)
        STAMP.parent.mkdir(parents=True, exist_ok=True)
        STAMP.write_text(built_stamp(content, game_map), encoding="utf-8")
        DECLINED.unlink(missing_ok=True)
        say(f"PopTracker pack {'rebuilt, it was out of date' if outdated else 'built'}: {target}"
            + ("" if game_map else plain_map_reason(content)))
        say("  To use it, drag this file onto PopTracker's window"
            + (" again, to replace the one it has." if outdated else "."))
    except Exception as exc:  # noqa: BLE001 - the tracker is an extra
        say(f"PopTracker pack: not built ({exc})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--content", type=Path, help="the base game's content folder (default: Cemu's)")
    parser.add_argument("--output", type=Path, default=PACK_FOLDER)
    parser.add_argument("--icons", type=Path, default=ICONS_FOLDER,
                        help="a folder of the game's icons, PNG, named after the items")
    parser.add_argument("--package-icons", type=Path,
                        help="write the release's icon zip from --icons, and stop")
    args = parser.parse_args()
    if args.package_icons:
        missing = package_icons(args.icons, args.package_icons)
        print(f"icons: {args.package_icons}" + (f" (not found: {', '.join(missing)})" if missing else ""))
        sys.exit(0)
    if args.icons == ICONS_FOLDER:
        fetch_icons_said(print)                         # as the launcher does; not over another folder
    content = args.content or base_content()
    target, game_map = build(content, args.output, args.icons)
    if args.output.resolve() == PACK_FOLDER.resolve() and args.icons == ICONS_FOLDER:
        STAMP.parent.mkdir(parents=True, exist_ok=True)
        STAMP.write_text(built_stamp(content, game_map), encoding="utf-8")     # the launcher's pack
    missing = sorted(set(ICON_NAMES) - set(game_icons(args.icons)) - set(ui_icons(update_content())))
    if missing:
        print(f"no icon in {args.icons} nor in the game ({len(missing)}), a label instead: "
              + ", ".join(ICON_NAMES[key][0] for key in missing))
    print(f"pack: {target}" + ("" if game_map else plain_map_reason(content)))
    print("To use it, drag this file onto PopTracker's window.")
