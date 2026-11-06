"""The game's interface screens and their panes, read from the client.

Panes are found from the UI manager at 0x1047E650: its screen table (+0x18,
count +0x14), each screen's layout (+0x18) and root pane (layout +0x0c);
children in an intrusive list (count +0x10, sentinel +0x14); name at +0x80.
Some screens hold the root pane at +0x18 directly: a layout is told apart by
the words 0x1c, -1, -1, 0xf at +0x150. A load rebuilds the screens, so an
address found here is checked again (by name) before any write.
"""
from __future__ import annotations

from typing import Iterator

MANAGER = 0x1047E650
NAME = 0x80


class UiPanes:
    def __init__(self, process, cave):
        self.process, self.cave = process, cave

    def read(self, guest: int, size: int) -> bytes | None:
        raw = self.process.read(self.cave.base + guest, size)
        return raw if raw is not None and len(raw) == size else None

    def word(self, guest: int) -> int:
        raw = self.read(guest, 4)
        return int.from_bytes(raw, "big") if raw else 0

    def name(self, pane: int) -> str:
        raw = self.read(pane + NAME, 24)
        return raw.split(b"\0")[0].decode("ascii", "replace") if raw else ""

    def is_layout(self, address: int) -> bool:
        return bool(address) and (self.word(address + 0x150) == 0x1c
                                  and self.word(address + 0x154) == 0xFFFFFFFF
                                  and self.word(address + 0x158) == 0xFFFFFFFF
                                  and self.word(address + 0x15c) == 0x0F)

    def children(self, pane: int) -> list[int]:
        count, out = self.word(pane + 0x10), []
        if 0 < count < 400:
            sentinel, current = pane + 0x14, self.word(pane + 0x14)
            for _ in range(count + 2):
                if not current or current == sentinel:
                    break
                out.append(current)
                current = self.word(current)
        return out

    def find(self, root: int, name: str, depth: int = 0, seen=None) -> int | None:
        seen = set() if seen is None else seen
        if not root or root in seen or depth > 16:
            return None
        seen.add(root)
        if self.name(root) == name:
            return root
        for child in self.children(root):
            found = self.find(child, name, depth + 1, seen)
            if found:
                return found
        return None

    def screens(self) -> Iterator[tuple[int, int]]:
        """(screen, root pane) of every screen that exists now."""
        manager = self.word(MANAGER)
        table, count = self.word(manager + 0x18), self.word(manager + 0x14)
        if not manager or not table or not 0 < count < 400:
            return
        for index in range(count):
            screen = self.word(table + 4 * index)
            if not screen:
                continue
            layout = self.word(screen + 0x18)
            yield screen, (self.word(layout + 0x0c) if self.is_layout(layout) else layout)

    def screen_with(self, pane_name: str) -> tuple[int, int] | None:
        """(screen, pane) of the first screen holding a pane of that name."""
        for screen, root in self.screens():
            pane = self.find(root, pane_name)
            if pane:
                return screen, pane
        return None
