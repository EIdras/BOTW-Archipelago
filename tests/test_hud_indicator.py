"""The HUD's AP logo follows the connection (client side)."""
from pathlib import Path
import struct
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from botw_client.hud_indicator import FLAGS, MANAGER, HudIndicator
from botw_client.hud_protocol import OFFLINE, ONLINE, PART_PANE


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


def hud_memory():
    """Manager > screens (one empty) > layout > RootPane > N_All_00 > part > logos."""
    m = Memory()
    manager, table, screen, layout = 0x1000, 0x1100, 0x1200, 0x2000
    m.word(MANAGER, manager)
    m.word(manager + 0x14, 2)
    m.word(manager + 0x18, table)
    m.word(table + 4, screen)
    m.word(screen + 0x18, layout)
    for offset, value in ((0x150, 0x1c), (0x154, 0xFFFFFFFF), (0x158, 0xFFFFFFFF),
                          (0x15c, 0x0F)):
        m.word(layout + offset, value)
    panes = {"RootPane": 0x3000, "N_All_00": 0x3200, PART_PANE: 0x3400,
             OFFLINE: 0x3600, ONLINE: 0x3800}
    m.word(layout + 0x0c, panes["RootPane"])
    tree = {"RootPane": ["N_All_00"], "N_All_00": [PART_PANE], PART_PANE: [OFFLINE, ONLINE]}
    for name, pane in panes.items():
        m.write(pane + 0x80, name.encode() + b"\0")
        children = [panes[c] for c in tree.get(name, [])]
        m.word(pane + 0x10, len(children))
        sentinel = pane + 0x14
        m.word(sentinel, children[0] if children else sentinel)
        for child, following in zip(children, children[1:] + [sentinel]):
            m.word(child, following)
    m.write(panes[OFFLINE] + FLAGS, b"\x01")     # grey shown by default
    m.write(panes[ONLINE] + FLAGS, b"\x00")
    m.writes.clear()
    return m, panes


def visible(m, pane):
    return m.read(pane + FLAGS, 1)[0] & 1


class IndicatorTests(unittest.TestCase):
    def test_colour_when_online_grey_otherwise_one_write_per_change(self):
        m, panes = hud_memory()
        hud = HudIndicator(m, SimpleNamespace(base=0))
        self.assertTrue(hud.show(True))
        self.assertEqual((visible(m, panes[ONLINE]), visible(m, panes[OFFLINE])), (1, 0))
        writes = len(m.writes)
        self.assertTrue(hud.show(True))
        self.assertEqual(len(m.writes), writes)          # nothing to change
        self.assertTrue(hud.show(False))
        self.assertEqual((visible(m, panes[ONLINE]), visible(m, panes[OFFLINE])), (0, 1))

    def test_moved_panes_are_looked_up_again_not_written_blind(self):
        m, panes = hud_memory()
        now = [0.0]
        hud = HudIndicator(m, SimpleNamespace(base=0), clock=lambda: now[0])
        self.assertTrue(hud.show(True))
        m.write(panes[ONLINE] + 0x80, b"Other\0")         # screen rebuilt elsewhere
        m.writes.clear()
        self.assertFalse(hud.show(False))
        self.assertEqual(m.writes, [])
        m.write(panes[ONLINE] + 0x80, ONLINE.encode() + b"\0")
        self.assertFalse(hud.show(False))                # looked up at most every 2 s
        now[0] = 3.0
        self.assertTrue(hud.show(False))
        self.assertEqual(visible(m, panes[OFFLINE]), 1)

    def test_a_pack_without_the_part_writes_nothing(self):
        m, panes = hud_memory()
        m.write(panes[PART_PANE] + 0x80, b"Pa_Other_00\0")
        m.writes.clear()
        hud = HudIndicator(m, SimpleNamespace(base=0))
        self.assertFalse(hud.show(True))
        self.assertEqual(m.writes, [])


class RuntimeTests(unittest.TestCase):
    def test_runtime_follows_the_connection_and_logs_once(self):
        from botw_client.runtime import BotwClientRuntime
        with tempfile.TemporaryDirectory() as folder:
            logs = []
            runtime = BotwClientRuntime("localhost:1", "test",
                                        state_path=Path(folder) / "state.json",
                                        game_factory=Mock, log=logs.append)
            m, panes = hud_memory()
            runtime.hud = HudIndicator(m, SimpleNamespace(base=0))
            runtime.ap.connected = True
            runtime._hud_tick()
            self.assertEqual(visible(m, panes[ONLINE]), 1)
            runtime._hud_tick()                          # throttled, same state
            runtime.ap.connected = False
            runtime._hud_next = 0.0
            runtime._hud_tick()
            self.assertEqual(visible(m, panes[OFFLINE]), 1)
            self.assertEqual([line for line in logs if "HUD" in line],
                             ["indicateur HUD : connecté"])


if __name__ == "__main__":
    unittest.main()
