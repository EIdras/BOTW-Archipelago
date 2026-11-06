"""The AP connection indicator of the HUD, client side.

The pack adds a part to the HUD with two logos (botw_patch/hud_layout.py):
grey (offline, shown by default) and colour (online). The client shows the
one matching the AP connection by writing their visible bit (pane +0x44, bit
0). Measured in the game: the part exists in screen 0x25, its logos are its
children, and the game never rewrote our bits over 10 s: one write per change
is enough, no hook, no per-frame write.

Panes are found as botw_client/ui_panes.py reads them. The addresses are
checked by name before every write: a screen rebuilt by a load moves them,
and they are then looked up again.
"""
from __future__ import annotations

import time

from .hud_protocol import OFFLINE, ONLINE, PART_PANE
from .ui_panes import MANAGER, NAME, UiPanes  # noqa: F401 - MANAGER, NAME: this module's API

FLAGS = 0x44
VISIBLE = 0x01
LOOKUP_EVERY = 2.0          # seconds between two lookups while not found


class HudIndicator(UiPanes):
    def __init__(self, process, cave, *, clock=time.monotonic):
        super().__init__(process, cave)
        self.clock = clock
        self.panes: dict[str, int] | None = None
        self.shown: bool | None = None       # the state written last
        self._next_lookup = 0.0

    # --- lookup -------------------------------------------------------------------

    def locate(self) -> dict[str, int] | None:
        """The two logos, below our part in whichever screen holds it."""
        found = self.screen_with(PART_PANE)
        if found is None:
            return None
        panes = {name: self.find(found[1], name) for name in (ONLINE, OFFLINE)}
        return panes if all(panes.values()) else None

    def _valid(self) -> bool:
        return self.panes is not None and all(
            self.name(pane) == name for name, pane in self.panes.items())

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
            raw = self.read(pane + FLAGS, 1)
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
