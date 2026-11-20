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
from tools import maptex, poptracker_regions  # noqa: E402
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
SOURCE_FILES = ("tools/build_poptracker.py", "tools/maptex.py", "tools/uitex.py", "tools/bitemico.py",
                "tools/poptracker_regions.py",
                "tools/map_regions.py", "data/location_positions.json",
                "tools/poptracker/scripts/init.lua", "tools/poptracker/scripts/logic.lua",
                "tools/poptracker/scripts/autotracking/archipelago.lua", "tools/poptracker/scripts/uat.lua")


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
    [("Paraglider", "GLD", GEAR), ("Magnesis", "MAG", RUNE), ("Progressive Remote Bomb", "BOMB", RUNE),
     ("Progressive Stasis", "STA", RUNE), ("Cryonis", "CRY", RUNE),
     ("Progressive Sheikah Sensor", "SNS", RUNE)],
    [("Progressive Revali's Gale", "REV", CHAMPION), ("Progressive Daruk's Protection", "DAR", CHAMPION),
     ("Progressive Urbosa's Fury", "URB", CHAMPION), ("Progressive Mipha's Grace", "MIP", CHAMPION),
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
# The regions panel (tools/poptracker_regions.py): a tile a region of the tower
# maps (the world's tower_maps option), laid out as Hyrule; the Great Plateau's,
# where the game starts, always lit. Its label stands for its map when the pack
# is built without the game's.
START_REGION = "Great Plateau"
REGION_MARKER = 46                # a region's diamond on the big map (regions_on_map), a check's square 30
REGION_PANEL = [["Hebra", "Woodland", "Eldin", "Akkala"],
                ["Tabantha", "Ridgeland", "Central", "Lanayru"],
                ["Gerudo", START_REGION, "Dueling Peaks", "Hateno"],
                ["Wasteland", "Lake", "Faron"]]
REGION_LABELS = {"Hebra": "HEB", "Woodland": "WOOD", "Eldin": "ELD", "Akkala": "AKK", "Tabantha": "TAB",
                 "Ridgeland": "RDG", "Central": "CEN", "Lanayru": "LAN", "Gerudo": "GER", START_REGION: "PLAT",
                 "Dueling Peaks": "DUEL", "Hateno": "HAT", "Wasteland": "WST", "Lake": "LAKE", "Faron": "FAR"}
# The items whose second copy is their "+" (Purah's upgrades, the Champions'
# Ballad's powers): shown in two stages, the item then its "+".
UPGRADED = ("Progressive Remote Bomb", "Progressive Stasis", "Progressive Sheikah Sensor",
            "Progressive Revali's Gale", "Progressive Daruk's Protection",
            "Progressive Urbosa's Fury", "Progressive Mipha's Grace")
BEAST_ROW = [("Freed - Divine Beast Vah Ruta", "RUTA"), ("Freed - Divine Beast Vah Rudania", "RUDA"),
             ("Freed - Divine Beast Vah Medoh", "MEDO"), ("Freed - Divine Beast Vah Naboris", "NABO")]

# 5 x 7 capitals and digits, one string a row.
FONT = {
    "+": "00000 00100 00100 11111 00100 00100 00000",
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


def glyphs(text: str, scale: int, pad: int = 0) -> np.ndarray:
    """The text in FONT, a space as wide as a letter: a bool mask (7 * scale
    high), `pad` pixels around it."""
    width = len(text) * 6 * scale - scale
    mask = np.zeros((7 * scale + 2 * pad, width + 2 * pad), dtype=bool)
    for index, char in enumerate(text):
        for row, bits in enumerate(FONT[char].split() if char != " " else ()):
            for column, bit in enumerate(bits):
                if bit == "1":
                    px = pad + index * 6 * scale + column * scale
                    py = pad + row * scale
                    mask[py:py + scale, px:px + scale] = True
    return mask


def icon(label: str, colour: str, size: int = 48) -> np.ndarray:
    """A label for an item the game draws no icon of: white letters on nothing,
    like the game's own (masks it colours white), a bar of its family's colour
    under them. (size, size, 4) RGBA."""
    scale = 2
    letters = glyphs(label, scale)
    width = letters.shape[1]
    left, top = (size - width) // 2, (size - 7 * scale) // 2 - 3
    glyph = np.zeros((size, size), dtype=bool)
    glyph[top:top + 7 * scale, left:left + width] = letters
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
    "progressive_remote_bomb_1": ["Remote Bomb", "Remote Bombs", "Remote Bomb Round", "Remote Bomb Cube"],
    "progressive_remote_bomb_2": ["Remote Bomb+", "Remote Bombs+"],
    "progressive_stasis_2": ["Stasis+"], "cryonis": ["Cryonis"],
    "progressive_revalis_gale_1": ["Revali's Gale"], "progressive_revalis_gale_2": ["Revali's Gale+"],
    "progressive_daruks_protection_1": ["Daruk's Protection"],
    "progressive_daruks_protection_2": ["Daruk's Protection+"],
    "progressive_urbosas_fury_1": ["Urbosa's Fury"], "progressive_urbosas_fury_2": ["Urbosa's Fury+"],
    "progressive_miphas_grace_1": ["Mipha's Grace"], "progressive_miphas_grace_2": ["Mipha's Grace+"],
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
    # The Sensor's HUD icon, all its waves lit; the Sensor+'s, with its own "+".
    "progressive_sheikah_sensor_1": "Nt_SeekSensorIcon_04^s",
    "progressive_sheikah_sensor_2": "Nt_SeekSensorIconP_04^s",
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
    "dot_rune_upgrade": "Nt_PauseIconKodai_00^t", "dot_champions_ballad": "Nt_IconSinJuNew_03^d",
    "dot_master_sword": "Nt_PauseIcon_00^s",
}
# White masks the game colours itself: the Sensor in the Slate's blue, its "+" in green.
UI_TINTS = {"progressive_sheikah_sensor_1": (70, 190, 255),
            "progressive_sheikah_sensor_2": (110, 230, 110)}
# The inventory's own icons of the runes (UI/StockItem, tools/bitemico.py, from the
# player's update), in colour; the "+" ones no wiki draws, and Stasis, whose wiki icon
# is not square (PopTracker stretches it). Under the player's icons, over the interface's.
STOCK_ICONS = {"magnesis": "Obj_Magnetglove", "cryonis": "Obj_IceMaker",
               "progressive_remote_bomb_1": "Obj_RemoteBombBall", "progressive_remote_bomb_2": "Obj_RemoteBombBall2",
               "progressive_stasis_1": "Obj_StopTimer", "progressive_stasis_2": "Obj_StopTimerLv2"}


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
    """{image key: RGBA} of UI_ICONS; a progressive piece gets its number, a "+" its sign."""
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
        if key in UI_TINTS:
            # Coloured, the Sensor's own two icons tell its stages apart: no number.
            image = image.copy()
            image[..., :3] = (image[..., :3] * (np.array(UI_TINTS[key]) / 255)).astype(np.uint8)
        elif key in {f"{code(name)}_2" for name in UPGRADED}:
            image = numbered(image, "+")
        elif key.startswith("progressive_") and piece:
            image = numbered(image, piece.group(1))
        found[key] = image
    return found


def stock_icons(content: Path | None) -> dict[str, np.ndarray]:
    """{image key: RGBA} of STOCK_ICONS."""
    if content is None:
        return {}
    from tools import bitemico
    found = {}
    for key, actor in STOCK_ICONS.items():
        try:
            icon = bitemico.load(content / f"UI/StockItem/{actor}.sbitemico")
            found[key] = trimmed(np.frombuffer(bytes(icon.read_rgba()), np.uint8).reshape(icon.height, icon.width, 4))
        except (OSError, ValueError):
            continue
    return found


def trimmed(image: np.ndarray) -> np.ndarray:
    """The image cut to what it draws, square: the inventory leaves a margin the wikis' icons have not."""
    rows, columns = np.nonzero(image[..., 3])
    top, bottom, left, right = rows.min(), rows.max() + 1, columns.min(), columns.max() + 1
    side = max(bottom - top, right - left)
    square = np.zeros((side, side, 4), np.uint8)
    y, x = (side - (bottom - top)) // 2, (side - (right - left)) // 2
    square[y:y + bottom - top, x:x + right - left] = image[top:bottom, left:right]
    return square


def numbered(image: np.ndarray, digit: str) -> np.ndarray:
    """The icon with a piece's number (or a "+") in its lower right corner."""
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
    """The name of an icon file, without what a wiki adds; a "+" one (an
    upgraded rune or power) stays apart from the plain one."""
    plus = "+" in text
    text = text.lower().replace("'s ", " ").replace("'", "")
    return NOISE.sub("", re.sub(r"[^a-z0-9]+", "", text)) + ("+" if plus else "")


def game_icons(folder: Path) -> dict[str, bytes]:
    """{image key: PNG bytes} of the icons found in `folder` and its subfolders."""
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

    for name, label, colour in [entry for row in ROWS for entry in row]:
        item = rows[name]
        item_code = code(name)
        ids[item["id"]] = item_code
        path = f"images/items/{item_code}.png"
        count = int(item.get("count", 1))
        if name.startswith("Progressive ") or name in UPGRADED:
            stages = []
            for stage in range(1, count + 1):
                stage_path = f"images/items/{item_code}_{stage}.png"
                if name in UPGRADED:
                    # The item, then its "+".
                    plain = name.removeprefix("Progressive ")
                    badge, title = (label, plain) if stage == 1 else (label[:3] + "+", plain + "+")
                else:
                    badge, title = label[:3] + str(stage), f"{name} ({stage}/{count})"
                image(stage_path, f"{item_code}_{stage}", badge, colour)
                stages.append({"name": title, "img": stage_path,
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
    for region, name in sorted(cat.MAPS.items()):
        # Shown by the regions panel (region_items).
        ids[rows[name]["id"]] = code(name)
        entries.append({"name": name, "type": "toggle", "img": region_image(region, "tile", "lit"),
                        "codes": code(name)})
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


def region_image(region: str, kind: str, state: str) -> str:
    return f"images/regions/{code(region)}_{kind}_{state}.png"


def region_items(cat, drawn: poptracker_regions.Drawn | None) -> tuple[list, dict]:
    """The regions panel's items and images. A region's tile and piece combine its
    map (left: received) and its "reached" toggle (right), which botw_update_regions
    (scripts/logic.lua) keeps: its map received and, with region_lock, the region
    reached. Without the game's map, labelled tiles and no mini-map."""
    def tile(region, state):
        return drawn.tiles[region, state] if drawn else \
            poptracker_regions.label_tile(icon(REGION_LABELS[region], MAP_COLOUR), state)

    start = region_image(START_REGION, "tile", "lit")
    images = {start: tile(START_REGION, "lit")}
    entries = [{"name": START_REGION, "type": "static", "img": start, "codes": f"{code(START_REGION)}_tile"}]
    if drawn:
        images["images/regions/hyrule.png"] = drawn.background
        entries.append({"name": "Hyrule", "type": "static", "img": "images/regions/hyrule.png",
                        "codes": "hyrule_regions"})
    for region, item in sorted(cat.MAPS.items()):
        map_code = code(item)
        entries.append({"name": f"{region} reached", "type": "toggle", "img": region_image(region, "tile", "lit"),
                        "codes": f"{map_code}_reached"})
        for kind in ("tile", "piece") if drawn else ("tile",):
            for state in poptracker_regions.STATES:
                images[region_image(region, kind, state)] = \
                    drawn.pieces[region, state][2] if kind == "piece" else tile(region, state)
            # Not received, whatever the right toggle says: grey.
            looks = {(False, False): "off", (True, False): "cut", (False, True): "off", (True, True): "lit"}
            entries.append({"name": item, "type": "composite_toggle", "codes": f"{map_code}_{kind}",
                            "item_left": map_code, "item_right": f"{map_code}_reached",
                            "images": [{"left": left, "right": right, "img": region_image(region, kind, state),
                                        "img_mods": "none"} for (left, right), state in looks.items()]})
    return entries, images


# --- Locations -------------------------------------------------------------------

DOT = {"Shrine": "#3a8fd6", "Tower": "#e08a2c", "Divine Beast": "#c94a4a", "Shop": "#2fa36b",
       "Stall": "#2fa36b", "Great Fairy": "#d65fb5", "Master Sword": "#e6d23a",
       "Rune Terminal": "#3ac0c9", "Rune Upgrade": "#3ac0c9", "Champions' Ballad": "#c94a4a",
       "Goal": "#ffffff", "Korok": "#8fc73e", "Chest": "#c8a050", "Dungeon Chest": "#9b7be0"}
# The small marks of korok_sanity and chest_sanity, up to 2 289 of them, a check's
# square 30: a Korok a diamond, a chest a square; a shrine's or a Divine Beast's
# chests one square together, beside it (DUNGEON_OFFSET pixels).
SMALL = {"Korok": ("diamond", 18), "Chest": ("rect", 12), "Dungeon Chest": ("rect", 14)}
DUNGEON_OFFSET = 18
# The map's categories, each shown or hidden by a toggle of the "Map" group, all
# shown at first: {name: the kinds of DOT it shows}. The regions' markers apart.
CATEGORIES = {"Shrines": ("Shrine", "Rune Terminal"), "Towers": ("Tower",), "Shops": ("Shop", "Stall"),
              "Others": ("Divine Beast", "Great Fairy", "Master Sword", "Rune Upgrade", "Champions' Ballad",
                         "Goal"),
              "Koroks": ("Korok",), "Chests": ("Chest",), "Dungeon Chests": ("Dungeon Chest",)}
SHOW_REGIONS = "show_regions"
# Link on the map, told by the client through UAT (botw_client/uat.py, scripts/uat.lua): his
# mark in the cell of LINK_CELL world units he stands in (link_marks), and with the "Follow"
# toggle the view of the region he enters (region_views).
SHOW_LINK, FOLLOW_REGION = "show_link", "follow_region"
LINK_ROW, LINK_COL = "link_row", "link_col"
LINK_CELL = 100
LINK_SIZE = 44                    # pixels of his mark (a check's square 30)
LINK_COLOUR = "#20ffff"           # his buttons' and Universal Tracker's mark (link_dot)
LINK_ICON_SIZE = 56               # map pixels of Universal Tracker's mark (maps.json)
LINK_ARROWS = 16                  # its arrows, one a turn (botw_world/tracker.py ARROWS)
# The game map's own mark of Link: an arrow (a mask) and its shadow.
ARROW_TEXTURES = ("Nt_MapPlayerIconNew_00^s", "Nt_MapPlayerIconNewSh_00^s")
ARROW_NARROWING = 0.7


def shown(kind: str) -> str:
    """The code of the toggle that shows a kind of DOT on the map."""
    return next(f"show_{code(name)}" for name, kinds in CATEGORIES.items() if kind in kinds)


def toggle_codes() -> list[str]:
    """The codes of the "Map" group's toggles: the categories, the regions' markers, then
    Link's mark and the view following his region."""
    return [shown(kinds[0]) for kinds in CATEGORIES.values()] + [SHOW_REGIONS, SHOW_LINK, FOLLOW_REGION]


# --- The "Map" group's buttons -------------------------------------------------

BUTTON_SIZE = 64                  # pixels of a button's image (PopTracker shows it at 32)
GOLD = "#d4af37"                  # the regions' markers' ring (regions_on_map)
# A category's icon on its button, from the player's update: an interface texture
# (white masks, the map's own, large), a cell of the map's stamps (the star, the
# chest), or an inventory icon (the Korok seed, in colour). The dungeons' chests:
# the chest with a shrine's icon in its corner (button_icons).
BUTTON_ICONS = {"Shrines": "Nt_MapDungeonNewL_00^t", "Towers": "Nt_MapTowerNewL_00^t",
                "Shops": "Nt_RupeeIconNew_00^l", "Koroks": "Obj_KorokNuts",
                "Others": ("Nt_MapStampIconMarge_00^f", 4), "Chests": ("Nt_MapStampIconMarge_00^f", 5)}


def button_icons(content: Path | None) -> dict[str, np.ndarray]:
    """{category: RGBA} of BUTTON_ICONS, those the update has."""
    if content is None:
        return {}
    from tools import bitemico, uitex
    found = {}
    try:
        textures = uitex.textures(content)
    except (OSError, KeyError, ValueError):
        textures = {}
    for name, source in BUTTON_ICONS.items():
        try:
            if isinstance(source, tuple):
                strip = uitex.decode(textures[source[0]])
                side = strip.shape[0]
                image = strip[:, source[1] * side:(source[1] + 1) * side]
            elif source.startswith("Obj_"):
                item = bitemico.load(content / f"UI/StockItem/{source}.sbitemico")
                image = np.frombuffer(bytes(item.read_rgba()), np.uint8).reshape(item.height, item.width, 4)
            else:
                image = uitex.decode(textures[source])
            found[name] = trimmed(image)
        except (OSError, KeyError, ValueError):
            continue
    if "Chests" in found and "Shrines" in found:
        found["Dungeon Chests"] = badged(found["Chests"], found["Shrines"], DOT["Shrine"])
    return found


def badged(glyph: np.ndarray, badge: np.ndarray, colour: str) -> np.ndarray:
    """`glyph` with `badge` (a white mask) in its lower right corner, in `colour`
    on a dark outline. RGBA."""
    size = glyph.shape[0] * 2
    canvas = resized(glyph, size)                           # premultiplied
    side = size * 11 // 20
    mask = resized(badge, side)[..., 3] / 255
    padded = np.pad(mask, 3)
    outline = mask.copy()
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            outline = np.maximum(outline, padded[3 + dy:3 + dy + side, 3 + dx:3 + dx + side])
    area = canvas[size - side:, size - side:]
    for alpha, tint in ((outline, rgb("#10161a")), (mask, rgb(colour))):
        area[..., :3] = tint * alpha[..., None] + area[..., :3] * (1 - alpha[..., None])
        area[..., 3] = 255 * alpha + area[..., 3] * (1 - alpha)
    canvas[..., :3] /= np.maximum(canvas[..., 3:4] / 255, 1e-6)
    return np.clip(canvas, 0, 255).astype(np.uint8)


def resized(image: np.ndarray, side: int) -> np.ndarray:
    """A square RGBA image at side x side, each pixel the mean of what it covers
    (alpha premultiplied); a small one doubled first, so as not to blur it."""
    while image.shape[0] < side:
        image = image.repeat(2, 0).repeat(2, 1)
    size = image.shape[0]
    edges = np.arange(side + 1) * size / side
    source = np.arange(size)[None, :]
    weights = np.clip(np.minimum(edges[1:, None], source + 1) - np.maximum(edges[:-1, None], source), 0, None)
    weights /= weights.sum(1, keepdims=True)
    pixels = image.astype(np.float64)
    pixels[..., :3] *= pixels[..., 3:4] / 255
    return np.einsum("ij,jkc,lk->ilc", weights, pixels, weights)


def button(glyph: np.ndarray | None, colour: str, label: str, size: int = BUTTON_SIZE) -> np.ndarray:
    """A button of the "Map" group: a rounded dark square framed in its category's
    colour, its icon in the middle (`label` in letters without one). RGBA."""
    y, x = np.mgrid[0:size, 0:size] + 0.5
    radius, half = size * 0.22, size / 2 - 0.5
    qx, qy = np.abs(x - size / 2) - (half - radius), np.abs(y - size / 2) - (half - radius)
    distance = (np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0)
                - radius)                                   # < 0 inside the rounded square
    inside = np.clip(0.5 - distance, 0, 1)
    ring = np.clip(np.minimum(distance + size * 0.07, 0.5 - distance), 0, 1) * inside
    top, bottom = rgb("#3a4a55"), rgb("#161e24")
    out = (top + (bottom - top) * (y / size)[..., None]) * (1 - ring[..., None]) + rgb(colour) * ring[..., None]
    if glyph is None:
        glyph = icon(label, colour, 48)
    side = round(size * 0.62)
    mark = resized(trimmed(glyph), side)
    at = (size - side) // 2
    area = out[at:at + side, at:at + side]
    out[at:at + side, at:at + side] = mark[..., :3] + area * (1 - mark[..., 3:4] / 255)
    return np.dstack([np.clip(out, 0, 255), inside * 255]).astype(np.uint8)


def diamond(colour: str = GOLD, size: int = 48) -> np.ndarray:
    """A region's marker as the big map draws it: a diamond in a gold ring. RGBA."""
    y, x = np.mgrid[0:size, 0:size] + 0.5
    distance = np.abs(x - size / 2) + np.abs(y - size / 2)
    edge = size / 2 - 1
    image = np.zeros((size, size, 4))
    image[..., :3] = np.where((distance > edge - 7)[..., None], rgb(colour), rgb("#c94a4a"))
    image[..., 3] = np.clip(edge - distance + 0.5, 0, 1) * 255
    return image.astype(np.uint8)


def link_dot(colour: str = LINK_COLOUR, size: int = 48) -> np.ndarray:
    """Link's mark, with no heading to show: a dot in a white ring, on a soft shadow that
    keeps it seen on the sea. RGBA."""
    y, x = np.mgrid[0:size, 0:size] + 0.5
    distance = np.hypot(x - size / 2, y - size / 2) / (size / 2)      # 1 at the edge
    dot = np.clip((0.48 - distance) * size / 2 + 0.5, 0, 1)[..., None]
    ring = np.clip((0.68 - distance) * size / 2 + 0.5, 0, 1)
    shadow = np.clip((1 - distance) / 0.32, 0, 1) * 0.6
    image = np.zeros((size, size, 4))
    image[..., :3] = (rgb(colour) * dot + 255 * (1 - dot)) * ring[..., None]
    image[..., 3] = np.maximum(ring, shadow) * 255
    return image.astype(np.uint8)


def rotated(image: np.ndarray, degrees: float) -> np.ndarray:
    """A square image (floats, alpha premultiplied) turned clockwise about its centre, bilinear."""
    size = image.shape[0]
    y, x = np.mgrid[0:size, 0:size] + 0.5 - size / 2
    angle = np.radians(degrees)
    sx = x * np.cos(angle) + y * np.sin(angle) + size / 2 - 0.5     # where each pixel comes from
    sy = y * np.cos(angle) - x * np.sin(angle) + size / 2 - 0.5
    x0, y0 = np.floor(sx).astype(int), np.floor(sy).astype(int)
    fx, fy = (sx - x0)[..., None], (sy - y0)[..., None]
    padded = np.pad(image, ((1, 1), (1, 1), (0, 0)))

    def at(row, column):
        return padded[np.clip(row + 1, 0, size + 1), np.clip(column + 1, 0, size + 1)]
    return (at(y0, x0) * (1 - fx) * (1 - fy) + at(y0, x0 + 1) * fx * (1 - fy)
            + at(y0 + 1, x0) * (1 - fx) * fy + at(y0 + 1, x0 + 1) * fx * fy)


def link_arrows(content: Path | None, size: int = 64) -> dict[str, np.ndarray]:
    """Universal Tracker's mark facing each of LINK_ARROWS ways, clockwise from up the map: the
    game map's own arrow in LINK_COLOUR, framed in white, on its shadow; the dot without them."""
    try:
        from tools import uitex
        textures = uitex.textures(content) if content is not None else {}
        arrow, shadow = (uitex.decode(textures[name]) for name in ARROW_TEXTURES)
    except (OSError, KeyError, ValueError):
        return {f"images/link/{turn:02d}.png": link_dot(size=size) for turn in range(LINK_ARROWS)}
    # Square about the centre, room for the shadow at any turn.
    rows, columns = np.nonzero(shadow[..., 3] > 4)
    centre = shadow.shape[0] / 2
    half = int(np.ceil(np.hypot(rows + 0.5 - centre, columns + 0.5 - centre).max())) + 1
    window = slice(int(centre) - half, int(centre) + half)
    # Narrowed: as wide as the game draws it, turned, it no longer shows where it points.
    across = (np.arange(size) + 0.5 - size / 2) / ARROW_NARROWING + size / 2 - 0.5
    masks = [np.array([np.interp(across, np.arange(size), row, left=0, right=0)
                       for row in resized(image[window, window], size)[..., 3] / 255])
             for image in (arrow, shadow)]
    pointed, dark = masks[0], np.clip(masks[1] * 2, 0, 0.85)
    frame = pointed.copy()                                   # the arrow grown by 2.5 pixels
    padded = np.pad(pointed, 3)
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if dx * dx + dy * dy <= 6.25:
                frame = np.maximum(frame, padded[3 + dy:3 + dy + size, 3 + dx:3 + dx + size])
    rgb_, alpha = np.zeros((size, size, 3)), dark.copy()     # premultiplied: black, white, colour
    for colour, cover in (((255, 255, 255), frame), (rgb(LINK_COLOUR), pointed)):
        rgb_ = np.array(colour) * cover[..., None] + rgb_ * (1 - cover[..., None])
        alpha = cover + alpha * (1 - cover)
    image = np.dstack([rgb_, alpha])
    arrows = {}
    for turn in range(LINK_ARROWS):
        turned = rotated(image, turn * 360 / LINK_ARROWS)
        cover = np.clip(turned[..., 3:4], 0, 1)
        straight = np.where(cover > 0, turned[..., :3] / np.maximum(cover, 1e-6), 0)
        arrows[f"images/link/{turn:02d}.png"] = np.dstack(
            [np.clip(straight, 0, 255), cover * 255]).round().astype(np.uint8)
    return arrows


def magnifier(colour: str = LINK_COLOUR, size: int = 48) -> np.ndarray:
    """The "Follow" button's icon: a magnifying glass. RGBA."""
    y, x = np.mgrid[0:size, 0:size] + 0.5
    centre, radius, width = size * 0.4, size * 0.27, size * 0.09
    ring = width - np.abs(np.hypot(x - centre, y - centre) - radius)
    along = ((x - centre) + (y - centre)) / np.sqrt(2)               # the handle, down to the right
    across = np.abs((x - centre) - (y - centre)) / np.sqrt(2)
    handle = np.minimum(np.minimum(width * 1.2 - across, along - radius), size * 0.8 - along)
    image = np.zeros((size, size, 4))
    image[..., :3] = rgb("#ffffff")
    image[..., 3] = np.clip(np.maximum(ring, handle) + 0.5, 0, 1) * 255
    return image.astype(np.uint8)


def map_toggles(icons: dict[str, np.ndarray]) -> tuple[list, dict]:
    """The "Map" group's toggles, all on at first, and their buttons' images."""
    entries, images = [], {}
    looks = {name: (icons.get(name), DOT[kinds[0]]) for name, kinds in CATEGORIES.items()}
    looks["Regions"] = (diamond(), GOLD)
    looks["Link"] = (link_dot(), LINK_COLOUR)
    looks["Follow"] = (magnifier(), LINK_COLOUR)
    for (name, (glyph, colour)), item in zip(looks.items(), toggle_codes()):
        path = f"images/buttons/{item}.png"
        images[path] = button(glyph, colour, name[:3].upper())
        entries.append({"name": f"Show {name}", "type": "toggle", "img": path, "codes": item,
                        "initial_active_state": True})
    return entries, images


def place_of(row: dict) -> str:
    """The map square a location belongs to: a stable's two Beedle items, a
    stall's, a Divine Beast and its heart, a plateau shrine and its terminal,
    Purah's three upgrades."""
    name, kinds = row["name"], set(row["category"].split("|"))
    if kinds & {"Shop", "Stall"}:
        return re.sub(r" Item \d+$", "", name)
    if "Rune Upgrade" in kinds:
        return name.rsplit(" - ", 1)[0]
    if "Divine Beast Heart" in kinds:
        return "Divine Beast " + name.replace(" Heart Container", "")
    return name


def world_requirements(cat, row: dict) -> tuple:
    """requirements(row), an event "Freed - Divine Beast X" counted as the world
    counts it (botw_world, create_regions: the beast reachable, not checked):
    the beast's own groups. A heart container is picked up before the beast's
    control unit is. Every shrine cleared (a chest's ALL_SHRINES): the count of
    shrines cleared (botw_update_events)."""
    rows = {other["name"]: other for other in cat.LOCATIONS}
    out = []
    groups = cat.requirements(row)
    cleared = [names for names, _count in groups if names[0].startswith("Cleared - ")]
    if cleared:
        out.append((("Shrines cleared",), len(cleared)))
    for names, count in groups:
        if names in cleared:
            continue
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


def world_regions(cat, row: dict) -> tuple[str, ...]:
    """With region_lock, the regions a location needs to reach (botw_world,
    location_rule): its own but the Great Plateau, always reached, and those of
    its maps (world_map_keys), a quest's or a Divine Beast's."""
    opened = {item: region for region, item in cat.MAPS.items()}
    names = [row["region"]] + [opened[name] for name in world_map_keys(cat, row)]
    return tuple(name for name in dict.fromkeys(names) if name != "Great Plateau")


def crop_box(positions: dict) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the map shown, in pixels of the whole map."""
    xs, ys = zip(*(maptex.pixel(x, z, SCALE) for x, z in positions.values()))
    width, height = int(12000 * SCALE), int(10000 * SCALE)
    return (max(0, min(xs) - MARGIN), max(0, min(ys) - MARGIN),
            min(width, max(xs) + MARGIN), min(height, max(ys) + MARGIN))


def locations(cat, positions: dict, origin: tuple[int, int] = (0, 0)) -> tuple[list, dict, dict, dict, dict]:
    """locations.json, the AP id -> section path map, the Lua requirement table,
    the maps each location asks for when the maps are region keys, and the
    regions it asks to reach with region_lock."""
    places: dict[str, dict] = {}
    kind_of: dict[str, str] = {}            # a place's kind of DOT, its first location's
    sections, requirements, maps, regions = {}, {}, {}, {}

    def rules(row: dict, key: str, section: dict) -> None:
        """A location's logic: its requirements and its maps, then its regions."""
        section["access_rules"] = [[f"$botw_access|{row['id']}"]]
        requirements[row["id"]] = world_requirements(cat, row)
        sections[row["id"]] = f"@{key}/{row['name']}"
        keys = world_map_keys(cat, row)
        if keys:
            maps[row["id"]] = keys
        reached(row, section)

    def reached(row: dict, section: dict) -> None:
        """With region_lock, the regions a location asks for, the goal's too."""
        reach = world_regions(cat, row)
        if reach:
            # With region_lock, its regions out of reach, a location is out of
            # reach (botw_regions). Optional, in brackets: without its maps, a
            # sequence break (yellow, botw_maps). Ganon asks for no map, nor do the towers
            # without towers_need_maps.
            section["access_rules"][0] += [f"$botw_regions|{row['id']}", f"[$botw_maps|{row['id']}]"]
            regions[row["id"]] = reach

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
        kind_of.setdefault(key, kind)
        place = places.setdefault(key, {
            "name": key, "chest_unopened_img": f"images/dots/{code(kind)}.png",
            "chest_opened_img": "images/dots/opened.png",
            "map_locations": [{"map": MAP, "x": x, "y": y}], "sections": []})
        section = {"name": name, "item_count": 1}
        if name == cat.GOAL_LOCATION:
            section["access_rules"] = [["$botw_ganon"]]
            reached(row, section)
        else:
            rules(row, key, section)
        if kinds & {"Shop", "Stall"}:
            # Shown when the seed has it (one of a place's items is enough).
            section["visibility_rules"] = [[f"$botw_in_seed|{row['id']}"]]
            place.setdefault("visibility_rules", []).append([f"$botw_in_seed|{row['id']}"])
        place["sections"].append(section)
    # A place is shown with its category (map_toggles).
    for key, place in places.items():
        place["visibility_rules"] = [[shown(kind_of[key]), *rule] for rule in place.get("visibility_rules", [[]])]
    # korok_sanity's Koroks and chest_sanity's chests, a small mark each (SMALL),
    # shown once connected to a seed that has it (botw_seed_has): none before, nor
    # in a seed without them. A chest of a shrine or a Divine Beast, whose position
    # is inside it, is in its dungeon's mark, beside the dungeon's square.
    for key, kind, rows, (world_x, world_z) in small_marks(cat, positions):
        x, y = maptex.pixel(world_x, world_z, SCALE)
        shape, size = SMALL[kind]
        place = places[key] = {
            "name": key, "chest_unopened_img": f"images/dots/{code(kind)}.png",
            "chest_opened_img": "images/dots/opened.png", "visibility_rules": [],
            "map_locations": [{"map": MAP, "x": x - origin[0], "y": y - origin[1], "size": size, "shape": shape}],
            "sections": []}
        for row in rows:
            has = f"$botw_seed_has|{row['id']}"
            section = {"name": row["name"], "item_count": 1, "visibility_rules": [[has]]}
            rules(row, key, section)
            place["sections"].append(section)
            place["visibility_rules"].append([shown(kind), has])
    return list(places.values()), sections, requirements, maps, regions


def small_marks(cat, positions: dict) -> list[tuple[str, str, list, list]]:
    """The small marks: (name, kind of SMALL, locations, [x, z] as positions'),
    a Korok's, a chest's of the surface, and a dungeon's chests together."""
    dungeons: dict[str, list] = {}
    for row in cat.CHESTS:
        if row.get("dungeon"):
            dungeons.setdefault(row["dungeon"], []).append(row)
    marks = [(row["name"], "Korok" if row["category"] == "Korok" else "Chest", [row],
              [row["position"][0], row["position"][2]])
             for row in cat.KOROKS + cat.CHESTS if not row.get("dungeon")]
    return marks + [(f"{dungeon} Chests", "Dungeon Chest", rows,
                     [value + DUNGEON_OFFSET / SCALE for value in positions[dungeon]])
                    for dungeon, rows in dungeons.items()]


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


def data_lua(cat, item_ids: dict, sections: dict, requirements: dict, maps: dict | None = None,
             regions: dict | None = None) -> str:
    def groups(value):
        return [[[code(name) for name in names], count] for names, count in value]

    goal = next(row for row in cat.LOCATIONS if row["name"] == cat.GOAL_LOCATION)
    goal_section = f"@{place_of(goal)}/{goal['name']}"
    by_name = {row["name"]: row["id"] for row in cat.LOCATIONS}
    beasts = {by_name[name[len("Freed - "):]]: code(name) for name, _ in BEAST_ROW}
    shrines = [row["id"] for row in cat.LOCATIONS if "Shrine" in row["category"]]
    towers = {row["id"]: code(cat.MAPS[row["region"]]) for row in cat.LOCATIONS
              if "Tower" in cat.categories(row) and row["region"] in cat.MAPS}
    lines = ["-- Generated by tools/build_poptracker.py from the world (botw_world): do not edit.",
             f"ITEM_CODES = {lua_value(item_ids)}",
             f"LOCATION_SECTIONS = {lua_value(sections)}",
             "REQUIREMENTS = {"]
    lines += [f"  [{location_id}] = {lua_value(groups(value))},"
              for location_id, value in sorted(requirements.items())]
    lines += ["}", "MAP_KEYS = {"]
    lines += [f"  [{location_id}] = {lua_value([code(name) for name in names])},"
              for location_id, names in sorted((maps or {}).items())]
    lines += ["}", "REGION_KEYS = {"]
    lines += [f"  [{location_id}] = {lua_value(names)},"
              for location_id, names in sorted((regions or {}).items())]
    lines += ["}",
              # region_lock: the map that opens each region, and the regions
              # inside another's area, reached with it.
              f"REGION_MAPS = {lua_value({region: code(item) for region, item in sorted(cat.MAPS.items())})}",
              f"INNER_REGIONS = {lua_value(cat.INNER_REGIONS)}",
              # towers_need_maps: the map each tower asks for, its region's.
              f"TOWER_MAPS = {lua_value(towers)}",
              f"GOAL_REQUIREMENTS = {lua_value(groups(cat.requirements(goal)))}",
              # Not an AP location: cleared by the slot's goal status.
              f"GOAL_SECTION = {lua_value(goal_section)}",
              f"RUNES = {lua_value([code(name) for name in cat.RUNES])}",
              f"BEAST_EVENTS = {lua_value(beasts)}",
              f"SHRINES = {lua_value(shrines)}", ""]
    return "\n".join(lines)


def layouts(cat, drawn: poptracker_regions.Drawn | None = None) -> dict:
    grid = [[code(name) for name, _label, _colour in row] for row in ROWS]
    grid.append([code(name) for name, _ in BEAST_ROW] + ["shrines_cleared"])
    tiles = [[f"{code(region)}_tile" if region == START_REGION else f"{code(cat.MAPS[region])}_tile"
              for region in row] for row in REGION_PANEL]
    width, height = poptracker_regions.TILE
    regions = {"type": "layout", "key": "region_tiles"}
    if drawn:
        # The mini-map: Hyrule, then a piece a region over it, where it lies. The
        # tiles stay for a map not read, and for the broadcast view.
        background = drawn.background.shape
        pieces = [{"type": "item", "item": "hyrule_regions", "canvas_left": 0, "canvas_top": 0,
                   "width": background[1], "height": background[0]}]
        for region, item in sorted(cat.MAPS.items()):
            left, top, image = drawn.pieces[region, "lit"]
            pieces.append({"type": "item", "item": f"{code(item)}_piece", "canvas_left": left, "canvas_top": top,
                           "width": image.shape[1], "height": image.shape[0]})
        regions = {"type": "canvas", "width": background[1], "height": background[0], "content": pieces}
    return {
        "item_grid": {"type": "itemgrid", "item_margin": "3,3", "item_size": "40,40",
                      "h_alignment": "center", "rows": grid},
        "map_toggles": {"type": "itemgrid", "item_margin": "3,3", "item_size": "32,32", "h_alignment": "center",
                        "rows": [toggle_codes()[:4], toggle_codes()[4:8], toggle_codes()[8:]]},
        "region_tiles": {"type": "itemgrid", "item_margin": "3,3", "item_size": f"{width},{height}",
                         "h_alignment": "center", "rows": tiles},
        "tracker_default": {"type": "container", "background": "#00000000", "content": {
            "type": "dock", "dropshadow": True, "content": [
                {"type": "dock", "dock": "left", "v_alignment": "stretch", "content": [
                    {"type": "group", "header": "Items", "dock": "top",
                     "content": {"type": "layout", "key": "item_grid"}},
                    {"type": "group", "header": "Shown on the map", "dock": "top",
                     "content": {"type": "layout", "key": "map_toggles"}},
                    {"type": "group", "header": "Regions", "dock": "top", "content": regions},
                    {"type": "group", "header": "Pinned locations", "content": {
                        "type": "recentpins", "style": "wrapped", "h_alignment": "stretch",
                        "v_alignment": "stretch", "compact": True}}]},
                {"type": "map", "maps": [MAP]}]}},
        "tracker_broadcast": {"type": "array", "orientation": "vertical", "content": [
            {"type": "layout", "key": "item_grid"}, {"type": "layout", "key": "region_tiles"}]},
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


def region_lookup() -> poptracker_regions.Lookup | None:
    """The region at map pixels, from the update's tower areas; None without them."""
    update = update_content()
    if update is None:
        return None
    try:
        return poptracker_regions.tower_areas(update, SCALE, maptex.ORIGIN)
    except (OSError, ValueError, KeyError):
        return None


def regions_panel(cat, image: np.ndarray, box: tuple[int, int, int, int],
                  lookup: poptracker_regions.Lookup | None) -> poptracker_regions.Drawn | None:
    """The regions panel drawn from the game's map and the update's tower areas;
    None without them (labelled tiles, no mini-map)."""
    if lookup is None:
        return None
    try:
        return poptracker_regions.draw(image, lookup, box, sorted(cat.MAPS), START_REGION)
    except (OSError, ValueError, KeyError):
        return None


def region_pixels(lookup: poptracker_regions.Lookup | None, box: tuple[int, int, int, int]) -> np.ndarray | None:
    """The region of each pixel of the map shown (names, None outside); None without the tower areas."""
    if lookup is None:
        return None
    left, top, right, bottom = box
    try:
        return lookup(np.arange(left, right), np.arange(top, bottom))
    except (OSError, ValueError, KeyError):
        return None


def region_views(where: np.ndarray | None, margin: float = 0.9) -> dict[str, list]:
    """{region: [zoom, x, y]}: the view of the map shown that frames a region, its zoom (1, the
    whole map; PopTracker's "Zoom" hint) and its centre in pixels ("Pan")."""
    if where is None:
        return {}
    height, width = where.shape
    views = {}
    for region in sorted(set(where.ravel()) - {None}):
        ys, xs = np.nonzero(where == region)
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        zoom = max(1.0, margin * min(width / (x1 - x0), height / (y1 - y0)))
        views[region] = [round(zoom, 2), int((x0 + x1) // 2), int((y0 + y1) // 2)]
    return views


def link_marks(where: np.ndarray | None, box: tuple[int, int, int, int]) -> tuple[dict, list]:
    """Link's mark: the grid of LINK_CELL world units over the map shown, as scripts/uat.lua
    finds his cell from his position (LINK_GRID), and the location of his mark, one spot a cell
    holding land (`where`, every cell without it). A spot is shown when the hidden counters
    link_row and link_col are its row and column, from 1 (0: nowhere), and the toggle on."""
    left, top, right, bottom = box
    cell = LINK_CELL * SCALE
    rows, cols = int(np.ceil((bottom - top) / cell)), int(np.ceil((right - left) / cell))
    grid = {"origin_x": maptex.ORIGIN[0], "origin_z": maptex.ORIGIN[1], "scale": SCALE,
            "left": left, "top": top, "cell": cell, "rows": rows, "cols": cols}
    spots = []
    for row in range(rows):
        for col in range(cols):
            y0, x0 = int(row * cell), int(col * cell)
            if where is not None and (where[y0:int(y0 + cell), x0:int(x0 + cell)] == None).all():  # noqa: E711
                continue
            spots.append({"map": MAP, "x": int(x0 + cell / 2), "y": int(y0 + cell / 2), "size": LINK_SIZE,
                          "border_thickness": 4, "shape": "diamond",
                          "restrict_visibility_rules": [[f"{LINK_ROW}:{row + 1}", f"{LINK_COL}:{col + 1}"]],
                          "force_invisibility_rules": [[f"{LINK_ROW}:{row + 2}"], [f"{LINK_COL}:{col + 2}"]]})
    # Blue, the colour of no check: a section only to look ({}); scripts/uat.lua adds a white glow
    # (Highlight). PopTracker draws shapes in its own colours, those of its player's settings:
    # no image, no colour of the pack's own, and two sections are drawn in two colours.
    return grid, [{"name": "Link", "visibility_rules": [[SHOW_LINK]],
                   "sections": [{"name": "Link", "access_rules": [["{}"]]}],
                   "map_locations": spots}]


def link_counters(grid: dict) -> list:
    """The hidden counters of Link's cell (link_marks)."""
    return [{"name": name, "type": "consumable", "img": "images/dots/opened.png", "codes": item,
             "min_quantity": 0, "max_quantity": grid[size] + 1}
            for name, item, size in (("Link's row", LINK_ROW, "rows"), ("Link's column", LINK_COL, "cols"))]


def view_lua(views: dict, grid: dict) -> str:
    return "\n".join(["-- Generated by tools/build_poptracker.py: do not edit.",
                      f"MAP_NAME = {lua_value(MAP)}",
                      f"REGION_VIEWS = {lua_value(views)}",
                      f"LINK_GRID = {lua_value(grid)}",
                      f"FOLLOW_REGION, LINK_ROW, LINK_COL = {lua_value(FOLLOW_REGION)}, "
                      f"{lua_value(LINK_ROW)}, {lua_value(LINK_COL)}", ""])


def regions_on_map(cat, crop: np.ndarray, places: list, where: np.ndarray | None) -> list:
    """The regions drawn on the big map (`crop`, RGB, changed in place) and their
    markers, locations of no check: a large diamond in a gold ring a region, red
    its map not received, yellow received but out of reach with region_lock, and
    once the region is open checked (grey) by botw_update_regions, the Great
    Plateau's from the start: green would read as a check in logic. Hidden when
    the towers reveal the maps (botw_regions_shown). None without the tower areas
    (`where`, region_pixels)."""
    if where is None:
        return []
    checks = [(spot["x"], spot["y"]) for place in places for spot in place["map_locations"]]
    regions = [START_REGION, *sorted(cat.MAPS)]
    drawn = poptracker_regions.on_map(crop, where, regions, checks, lambda text: glyphs(text, 3, 2))
    markers = []
    for region, (x, y) in drawn.items():
        rules = []
        if region != START_REGION:
            item = code(cat.MAPS[region])
            rules = [[item, f"[{item}_reached]"]]
        markers.append({
            "name": f"{region} Region", "visibility_rules": [["$botw_regions_shown", SHOW_REGIONS]],
            "sections": [{"name": "Region", "access_rules": rules}],
            "map_locations": [{"map": MAP, "x": x, "y": y, "size": REGION_MARKER, "border_thickness": 4,
                               "shape": "diamond"}]})
    return markers


def build(content: Path | None, output: Path, icons: Path = ICONS_FOLDER) -> tuple[Path, bool]:
    cat = catalog()
    positions = json.loads(POSITIONS.read_text(encoding="utf-8"))
    files: dict[str, bytes] = {}
    for path in sorted(STATIC.rglob("*.lua")):
        files[path.relative_to(STATIC).as_posix()] = path.read_bytes()
    update = update_content()
    found = {**ui_icons(update), **stock_icons(update), **game_icons(icons)}
    item_entries, images, item_ids = items(cat, found)
    left, top, right, bottom = crop_box({**positions, **{name: at for name, _kind, _rows, at
                                                         in small_marks(cat, positions)}})
    place_entries, sections, requirements, maps, regions = locations(cat, positions, (left, top))
    files["scripts/data.lua"] = data_lua(cat, item_ids, sections, requirements, maps, regions).encode()
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
    lookup = region_lookup()
    where = region_pixels(lookup, (left, top, right, bottom))
    crop = np.ascontiguousarray(image[top:bottom, left:right])
    # The region markers keep clear of the checks, not of the small marks, mostly hidden.
    markers = regions_on_map(cat, crop, [place for place in place_entries
                                         if "shape" not in place["map_locations"][0]], where)
    grid, link = link_marks(where, (left, top, right, bottom))
    files["scripts/view.lua"] = view_lua(region_views(where), grid).encode()
    item_entries += link_counters(grid)
    # Universal Tracker's map (botw_world/tracker.py): Link's mark, where the grid finds him.
    files["maps/link_grid.json"] = json.dumps(dict(grid, arrows=LINK_ARROWS)).encode()
    images["images/link.png"] = link_dot(size=64)
    images.update(link_arrows(update))
    alpha = np.full(crop.shape[:2] + (1,), 255, dtype=np.uint8)
    images["images/map.png"] = np.concatenate([crop, alpha], 2)
    drawn = regions_panel(cat, image, (left, top, right, bottom), lookup) if game_map else None
    region_entries, region_images = region_items(cat, drawn)
    item_entries += region_entries
    images.update(region_images)
    toggle_entries, toggle_images = map_toggles(button_icons(update))
    item_entries += toggle_entries
    images.update(toggle_images)
    files.update({path: value if isinstance(value, bytes) else png(value)
                  for path, value in images.items()})
    files["items/items.json"] = json.dumps(item_entries, indent=1).encode()
    files["locations/locations.json"] = json.dumps(place_entries, indent=1).encode()
    files["locations/regions.json"] = json.dumps(markers, indent=1).encode()
    files["locations/link.json"] = json.dumps(link, indent=1).encode()
    files["maps/maps.json"] = json.dumps([{
        "name": MAP, "location_size": 30, "location_border_thickness": 3,
        "location_icon_size": LINK_ICON_SIZE,   # Universal Tracker's own, PopTracker skips it
        "img": "images/map.png"}], indent=1).encode()
    files["layouts/tracker.json"] = json.dumps(layouts(cat, drawn), indent=1).encode()
    files["manifest.json"] = json.dumps({
        "name": "Breath of the Wild Archipelago", "game_name": cat.GAME,
        "package_uid": PACK_NAME, "package_version": cat.WORLD_VERSION,
        "platform": "wiiu", "author": "EIdras", "min_poptracker_version": "0.26.2",
        "variants": {"map": {"display_name": "Map tracker", "flags": ["ap", "uat"]}}}, indent=1).encode()
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
                 "botw_world/data/locations.json", "botw_world/data/logic.csv", "botw_world/data/koroks.json",
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
        return (" (plain map: no base game folder found, as with a .wud/.wua/title.tmd game or a "
                "drive not connected)")
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
    missing = sorted(set(ICON_NAMES) - set(game_icons(args.icons)) - set(ui_icons(update_content()))
                     - set(stock_icons(update_content())))
    if missing:
        print(f"no icon in {args.icons} nor in the game ({len(missing)}), a label instead: "
              + ", ".join(ICON_NAMES[key][0] for key in missing))
    print(f"pack: {target}" + ("" if game_map else plain_map_reason(content)))
    print("To use it, drag this file onto PopTracker's window.")
