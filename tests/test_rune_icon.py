"""After a rune's "+", the HUD is made to ask its rune icon again (botw_client/rune_icon.py)."""
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
import zlib

from botw_client.backend import DeliveryCommand, DeliveryStatus
from botw_client.native_delivery import CemuNativeDeliveryBackend
from botw_client.rune_icon import SHORTCUT_PANE, SHOWN_RUNE, refresh_rune_icon
from botw_client.rune_selection import SyncOutcome
from botw_client.ui_panes import MANAGER

SCREEN = 0x1200


class Memory:
    """Sparse guest memory (cave base 0)."""

    def __init__(self):
        self.bytes, self.writes = {}, []

    def read(self, address, size):
        return bytes(self.bytes.get(address + i, 0) for i in range(size))

    def write(self, address, data):
        self.writes.append((address, bytes(data)))
        for i, value in enumerate(data):
            self.bytes[address + i] = value
        return True

    def word(self, address, value):
        self.write(address, struct.pack(">I", value))


def shortcut_memory(shown):
    """Manager > one screen > layout > RootPane > Pa_MainU_00, the screen holding `shown`."""
    m = Memory()
    manager, table, layout, root, part = 0x1000, 0x1100, 0x2000, 0x3000, 0x3200
    m.word(MANAGER, manager)
    m.word(manager + 0x14, 1)
    m.word(manager + 0x18, table)
    m.word(table, SCREEN)
    m.word(SCREEN + 0x18, layout)
    for offset, value in ((0x150, 0x1c), (0x154, 0xFFFFFFFF), (0x158, 0xFFFFFFFF),
                          (0x15c, 0x0F)):
        m.word(layout + offset, value)
    m.word(layout + 0x0c, root)
    for pane, name in ((root, "RootPane"), (part, SHORTCUT_PANE)):
        m.write(pane + 0x80, name.encode() + b"\0")
    m.word(root + 0x10, 1)
    m.word(root + 0x14, part)
    m.word(part, root + 0x14)
    m.word(part + 0x10, 0)
    m.word(SCREEN + SHOWN_RUNE, shown)
    m.writes.clear()
    return m


CAVE = SimpleNamespace(base=0)


class RefreshTests(unittest.TestCase):
    def test_the_rune_shown_is_forgotten_so_the_game_asks_its_icon_again(self):
        m = shortcut_memory(shown=3)
        self.assertEqual(refresh_rune_icon(m, CAVE, 3), "rune icon asked again")
        self.assertEqual(m.writes, [(SCREEN + SHOWN_RUNE, b"\xff\xff\xff\xff")])

    def test_another_rune_shown_is_left_alone(self):
        m = shortcut_memory(shown=1)
        self.assertIn("shows rune 0x1, not 0", refresh_rune_icon(m, CAVE, 0))
        self.assertEqual(m.writes, [])

    def test_no_shortcut_screen_writes_nothing(self):
        m = Memory()
        self.assertIn("not there", refresh_rune_icon(m, CAVE, 3))
        self.assertEqual(m.writes, [])


class DeliveryTests(unittest.TestCase):
    """The backend asks it after a "+" only, once the step is committed."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.catalog = Path(temporary.name) / "catalog.json"
        setter = {"kind": "set_s32", "target": "PlayerEquipItemType", "value": 3}

        def item(entry, kind, flag):
            return {"variants": {"default": [{
                "step": 0, "step_count": 1, "cursor_delta": 256, "entry": entry,
                "capacity_actor": None, "mutations": [
                    {"kind": kind, "target": flag, "value": 2}, setter]}]}}
        self.catalog.write_text(json.dumps({
            "schema": 1, "cursor": "(received_index << 8) | step", "flow": "Demo007_1",
            "items": {"Stasis+": item("APD_UP", "rune_power_up", "IsGet_Obj_StopTimerLv2"),
                      "Stasis": item("APD_STA", "rune_download", "IsGet_Obj_StopTimer")}}),
            encoding="utf-8")
        self.values = {self.flag("APSeedToken"): 123, self.flag("APReceivedCursor"): 256,
                       self.flag("APDeliveryRejectCounter"): 0}
        self.refreshed = []

        def refresh(rune):
            self.refreshed.append(rune)
            return "rune icon asked again"
        live = SimpleNamespace(get=lambda hash_u32, kind: self.values.get(hash_u32))
        self.game = SimpleNamespace(
            live=live, process=SimpleNamespace(pid=1), cave=object(),
            sync_rune_selection=lambda expected: SyncOutcome("synced", expected),
            pause_menu_ready=lambda: (True, ""), refresh_rune_icon=refresh)

    @staticmethod
    def flag(name):
        return zlib.crc32(name.encode()) & 0xFFFFFFFF

    def deliver(self, name):
        def request(*args, **kwargs):
            self.values[self.flag("APReceivedCursor")] = 512
            return {"native_return": 1}
        backend = CemuNativeDeliveryBackend(
            self.game, "seed", 2, 123, catalog=self.catalog, request=request,
            lock_factory=None, safe=lambda: True, commit_timeout=0.1, poll_seconds=0)
        return backend.deliver(DeliveryCommand("seed", 2, 1, name, 0, 1, 0))

    def test_a_rune_upgrade_refreshes_the_icon_of_its_rune(self):
        result = self.deliver("Stasis+")
        self.assertEqual(result.status, DeliveryStatus.APPLIED)
        self.assertEqual(self.refreshed, [3])
        self.assertIn("synced", result.detail)
        self.assertIn("rune icon asked again", result.detail)

    def test_a_rune_download_does_not(self):
        result = self.deliver("Stasis")
        self.assertEqual(result.status, DeliveryStatus.APPLIED)
        self.assertEqual(self.refreshed, [])

    def test_a_failing_refresh_never_turns_a_commit_into_an_error(self):
        def broken(_rune):
            raise TypeError("lecture impossible")
        self.game.refresh_rune_icon = broken
        result = self.deliver("Stasis+")
        self.assertEqual(result.status, DeliveryStatus.APPLIED)
        self.assertIn("TypeError", result.detail)


if __name__ == "__main__":
    unittest.main()
