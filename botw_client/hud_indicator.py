"""The AP connection indicator of the HUD, client side.

The pack adds a part to the HUD with two logos (botw_patch/hud_layout.py):
grey (offline, shown by default) and colour (online). The client shows the
one matching the AP connection by writing their visible bit (pane +0x44, bit
0). Measured in the game: the part exists in screen 0x25, its logos are its
children, and the game never rewrote our bits over 10 s: one write per change
is enough, no hook, no per-frame write.

Panes are found from the UI manager at 0x1047E650: its screen
table (+0x18, count +0x14), each screen's layout (+0x18) and root pane
(layout +0x0c); children in an intrusive list (count +0x10, sentinel +0x14);
name at +0x80. The addresses are checked by name before every write: a screen
rebuilt by a load moves them, and they are then looked up again.
"""
from __future__ import annotations

import time

from .hud_protocol import OFFLINE, ONLINE, PART_PANE

MANAGER = 0x1047E650
FLAGS, NAME = 0x44, 0x80
VISIBLE = 0x01
LOOKUP_EVERY = 2.0          # seconds between two lookups while not found


class HudIndicator:
    def __init__(self, process, cave, *, clock=time.monotonic):
        self.process, self.cave, self.clock = process, cave, clock
        self.panes: dict[str, int] | None = None
        self.shown: bool | None = None       # the state written last
        self._next_lookup = 0.0

    # --- memory -----------------------------------------------------------------

    def _read(self, guest: int, size: int) -> bytes | None:
        raw = self.process.read(self.cave.base + guest, size)
        return raw if raw is not None and len(raw) == size else None

    def _word(self, guest: int) -> int:
        raw = self._read(guest, 4)
        return int.from_bytes(raw, "big") if raw else 0

    def _name(self, pane: int) -> str:
        raw = self._read(pane + NAME, 24)
        return raw.split(b"\0")[0].decode("ascii", "replace") if raw else ""

    def _is_layout(self, address: int) -> bool:
        return bool(address) and (self._word(address + 0x150) == 0x1c
                                  and self._word(address + 0x154) == 0xFFFFFFFF
                                  and self._word(address + 0x158) == 0xFFFFFFFF
                                  and self._word(address + 0x15c) == 0x0F)

    def _children(self, pane: int) -> list[int]:
        count, out = self._word(pane + 0x10), []
        if 0 < count < 400:
            sentinel, current = pane + 0x14, self._word(pane + 0x14)
            for _ in range(count + 2):
                if not current or current == sentinel:
                    break
                out.append(current)
                current = self._word(current)
        return out

    def _find(self, root: int, name: str, depth: int = 0, seen=None) -> int | None:
        seen = set() if seen is None else seen
        if not root or root in seen or depth > 16:
            return None
        seen.add(root)
        if self._name(root) == name:
            return root
        for child in self._children(root):
            found = self._find(child, name, depth + 1, seen)
            if found:
                return found
        return None

    # --- lookup -------------------------------------------------------------------

    def locate(self) -> dict[str, int] | None:
        """The two logos, below our part in whichever screen holds it."""
        manager = self._word(MANAGER)
        table, count = self._word(manager + 0x18), self._word(manager + 0x14)
        if not manager or not table or not 0 < count < 400:
            return None
        for index in range(count):
            screen = self._word(table + 4 * index)
            if not screen:
                continue
            layout = self._word(screen + 0x18)
            root = self._word(layout + 0x0c) if self._is_layout(layout) else layout
            part = self._find(root, PART_PANE)
            if part:
                panes = {name: self._find(part, name) for name in (ONLINE, OFFLINE)}
                return panes if all(panes.values()) else None
        return None

    def _valid(self) -> bool:
        return self.panes is not None and all(
            self._name(pane) == name for name, pane in self.panes.items())

    # --- state --------------------------------------------------------------------

    def show(self, online: bool) -> bool:
        """Show the logo of `online`; True once both bits say so."""
        if not self._valid():
            self.panes, self.shown = None, None
            now = self.clock()
            if now < self._next_lookup:
                return False
            self._next_lookup = now + LOOKUP_EVERY
            self.panes = self.locate()
            if self.panes is None:
                return False
        wanted = {ONLINE: online, OFFLINE: not online}
        for name, pane in self.panes.items():
            raw = self._read(pane + FLAGS, 1)
            if raw is None:
                self.panes = None
                return False
            value = (raw[0] | VISIBLE) if wanted[name] else (raw[0] & ~VISIBLE)
            if value != raw[0] and not self.process.write(
                    self.cave.base + pane + FLAGS, bytes([value])):
                self.panes = None
                return False
        self.shown = online
        return True
