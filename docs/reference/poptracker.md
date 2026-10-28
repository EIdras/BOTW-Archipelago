# PopTracker pack

[PopTracker](https://github.com/black-sliver/PopTracker) shows the map of Hyrule with every location of the world,
colored by what the items received allow, and follows the multiworld by itself: its "AP" button connects to the room
with the slot's name, then items received and locations checked appear as they happen.

## Building and installing

The pack is built on the player's machine, never shipped: its map is the game's own, assembled from the player's base
game, so that no file of the game is in the repository.

- The pack is written to `PACK_FOLDER`: the release's own `PopTracker` folder (`<data>/poptracker` in a source
  checkout). The player installs it in PopTracker by hand (dragging the zip onto its window): finding PopTracker's
  packs folder depends on too much (a portable PopTracker, Documents moved to OneDrive...).
- Before each session the launcher says in one line where the pack stands (`ensure_pack`): up to date, rebuilt
  because what it is made of changed (the stamp, `<data>/poptracker/stamp.txt`), not built as the player answered,
  or not built and why. When the folder has no pack yet, it asks first (not everyone uses PopTracker); a no is
  remembered in `<data>/poptracker/declined.txt` until the stamp changes. A failure never blocks the game.
- By hand: `venv\Scripts\python tools\build_poptracker.py` (`--content <base game content>`, `--output <folder>`),
  `python\python.exe -I tools\build_poptracker.py` in a release.

## What it is made of

- **The map** (`tools/maptex.py`): the base game's `UI/MapTex/MainField`, one Yaz0 BFRES a section (Z, A..K by 0..9,
  1000 world units each; the MainField spans x -6000..6000, z -5000..5000). Each holds one Wii U texture: BC1
  (`0x431`), tile mode 4, addressed as `tools/bitemico.py` does (for 64-bit blocks, the micro-tile order is
  x0 y0 x1 x2 y1 y2, checked on the map's roads). The layer `MapTex2` (200 px a section) gives a 2400 x 2000 map. A
  section's variants (`_0`, `_16`...) are other states of the place; the plain name is used. Without a base game
  folder (a `.wud`/`.wua` game), the map is a plain grid.
- **Positions** (`data/location_positions.json`, built by `tools/build_location_positions.py` from the DLC's map
  units, checked by a test): shrines and towers from their `LocationMarker`, a rune terminal at its plateau shrine,
  a Divine Beast and its heart at the beast's marker during its quest, the Great Fairies at their fountain, Beedle at
  his NPC, a stall at its merchant, the Master Sword at its pedestal, Ganon at Hyrule Castle. One square on the map
  can hold several locations: a stable's two Beedle items, a stall's, a beast and its heart, a plateau shrine and its
  terminal.
- **Logic**: `botw_world/catalog.requirements`, the world's own, generated into `scripts/data.lua`; a location is
  reachable when each of its groups is met by one of its items. An event "Freed - Divine Beast X" counts as the world
  counts it, the beast reachable (its own groups), not checked: a heart container is picked up before the beast's
  control unit. The region maps (`catalog.map_keys`, `MAP_KEYS` in `data.lua`) are an optional rule in brackets,
  `[$botw_maps|<id>]`: when the slot data's `tower_maps` is `region_keys` (2) and a map is missing, the location is a
  sequence break (yellow), possible but out of logic. The maps have their own two rows in the item grid. Ganon's square follows the sanctum's requirements of the slot data, which count, as the game's gate
  does, the Divine Beasts freed and the shrines cleared: their squares, checked by Archipelago or by hand. Ganon is no
  AP location: his square is checked when the server's status of the slot (`_read_client_status_<team>_<slot>`, read
  and watched) says the goal is reached. Once a slot is released (on its goal, with the room's default), every
  location is checked: the whole map is grey.
- **Items**: the items that matter for the logic or the player. The game draws no icon of most of them (the
  inventory renders them from their models), so each image comes from the first of:
  1. the player's own icons, PNG, in `<data>/poptracker/icons` (`--icons`, subfolders too), found by name
     (`ICON_NAMES`: "Zora-armor.png" is the Zora Set's, "Climber-bandanna.png" the second piece of the climbing gear;
     a possessive "'s" is ignored, a "+" icon only stands in for a missing plain one; near ones where a wiki has none:
     the Sheikah Slate for the sensor, the full stamina wheel "Energizing5", the Champions' Ballad emblems);
  2. the game's own interface icons (`tools/uitex.py`, `UI_ICONS`), from the update's `Pack/Bootup.pack` >
     `Layout/Common.sblarc`: the HUD's heart and stamina wheel, the sensor, the four Divine Beasts, the inventory's
     tab icons (sword, bow, shield, armour; the pouch upgrades take the first three), the map's horse for Epona, the
     effect icons its armour shows (fire, swimming, shock, cold, heat, climbing, noise, attack, ancient), the map's icons (shrine, tower, stable, store, castle) for the squares. Most
     are masks the game colours: they come out white. A progressive piece gets its number;
  3. a label drawn by the builder, in the same style.

  The game draws no image of most items, and only stand-ins of the others (an armour's effect, an inventory tab,
  white masks): the icons of every item of the grid (`RELEASE_ICONS`, 45) are published apart from the code: `tracker-icons.zip`, the file attached to the GitHub release
  `tracker-icons` (Nintendo's images, never committed). The launcher fetches it once into
  `<data>/poptracker/icons/release` (`fetch_icons`: PNG files only, no paths, 4 MB at most); offline, the labels
  stay. The maintainer makes it from a folder of icons: `tools/build_poptracker.py --icons <folder> --package-icons
  tracker-icons.zip`. Removing that file withdraws the images without touching the code or its history.

  Wii U BFLIM: the image, then a 0x28-byte footer (`FLIM`, `imag`: size, format, a byte with the tile mode in its low
  5 bits and the swizzle in its high 3); formats A8, LA8 (luminance first), RGBA8, BC1, BC3, BC4, BC5; tile modes 2
  and 4, the pitch being AddrLib's alignment (the footer has none). The icons are never in the repository. Fillers
  and traps are not shown.
- **Shops and stalls**: shown only when the connected seed has them (its missing and checked locations).
- **Static parts**: `tools/poptracker/scripts/` (`init.lua`, `logic.lua`, `autotracking/archipelago.lua`).

`tests/test_poptracker.py` checks the pack's files; its Lua was also run against a fake PopTracker (an Archipelago
session, then what the logic answers).
