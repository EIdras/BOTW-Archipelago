"""Can the pause menu be built at once? Read-only, as the game decides it.

The rune terminal's download screen (Demo_OpenItemDownloadDemo) asks the UI
to build the pause menu (screen 0x1F) and then writes its request at
0x1053F754. The menu's constructor (0x02F7EE70) clears that request. The
loader (0x03058E84) builds the menu at once only when the map (screen 0x2A)
is idle and loaded and the inventory (screen 0x22) is loaded; otherwise the
menu is built a few frames later, after the request, which it clears: it
opens as an ordinary menu and the download screen waits forever. Measured on
26/09: vanilla terminal after the menu had been opened (11a,
20260926T184407.328329Z, request kept) and our delivery right after loading
a save (download-probe 20260926T210314, request cleared as the menu appeared).

The map rests only while the HUD is hidden (download-probe 20260926T212850:
its state is 2 in play, 0 some frames into an event or the menu). So the
client waits for map and inventory *loaded* before requesting a rune
download, and the delivery event waits for the map to rest before opening
the screen (botw_patch/delivery_flow.DOWNLOAD_SETTLE). `at_rest` adds the
rest condition, for the probe.
"""
from __future__ import annotations

UI_MANAGER = 0x1047E650
MAP_SCREEN, INVENTORY_SCREEN = 0x2A, 0x22
MAP_IDLE_BYTES = 0x95                  # s8 +0x95 <= 0 and s8 +0x96 == 0 (0x03A3E4DC)
MAP_LOADER, INVENTORY_LOADER = 0x21AC, 0x9080
LOADER_STATE = 0xD8                    # 0x02F359F0 on loader + 0xD8
LOADER_READY = 13                      # its +0x124 when loaded, with +0x100 == 0


def _u32(raw):
    return int.from_bytes(raw, "big") if raw and len(raw) == 4 else None


def _s8(value):
    return value - 0x100 if value & 0x80 else value


def pause_menu_ready(read, *, at_rest: bool = False) -> tuple[bool, str]:
    """read(guest, size) -> bytes | None. (ready, reason when not)."""
    def w32(address):
        return _u32(read(address, 4))

    manager = w32(UI_MANAGER)
    if not manager:
        return False, "interface du jeu illisible"
    count, table = w32(manager + 0x14), w32(manager + 0x18)
    if not table or count is None or count <= MAP_SCREEN:
        return False, "table d'écrans illisible"

    def loaded(screen, offset):
        loader = w32(screen + offset)
        if not loader:          # no loader: the game counts it as ready
            return True
        state = loader + LOADER_STATE
        return w32(state + 0x100) == 0 and w32(state + 0xFC + 0x28) == LOADER_READY

    game_map = w32(table + 4 * MAP_SCREEN)
    if game_map:
        idle = read(game_map + MAP_IDLE_BYTES, 2)
        if at_rest and (not idle or len(idle) != 2 or _s8(idle[1]) != 0 or _s8(idle[0]) > 0):
            return False, "carte en cours d'utilisation"
        if not loaded(game_map, MAP_LOADER):
            return False, "carte pas encore chargée"
    inventory = w32(table + 4 * INVENTORY_SCREEN)
    if inventory and not loaded(inventory, INVENTORY_LOADER):
        return False, "inventaire pas encore chargé"
    return True, ""
