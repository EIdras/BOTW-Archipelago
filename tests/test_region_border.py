"""region_lock's sign at a closed region's border (botw_client/region_border.py): the map's
areas, Link's place as the engine reads it, the fog and the held message."""
from __future__ import annotations

import struct
import unittest

from botw_client import region_border as rb
from botw_client.cucco_swarm import PLAYER_INFO


class Grid:
    """A tower grid of 2 m rows, the West area left of x = 0, the East one right of it."""
    rows, divisor = 4000, 2

    def row(self, index):
        return [(0, 5000), (1, 5000)]


class Memory:
    def __init__(self):
        self.bytes, self.writes = {}, []

    def put(self, guest, data):
        for i, b in enumerate(data):
            self.bytes[guest + i] = b

    def read(self, guest, size):
        try:
            return bytes(self.bytes[guest + i] for i in range(size))
        except KeyError:
            return None

    def write(self, guest, data):
        self.writes.append((guest, bytes(data)))
        self.put(guest, data)
        return True


INFO, PLAYER, WORLD, ARRAY, ENV = 0x20000000, 0x30000000, 0x21000000, 0x22000000, 0x23000000


def game(position, kind="MainField", name=None):
    memory = Memory()
    memory.put(PLAYER_INFO, INFO.to_bytes(4, "big"))
    memory.put(INFO + 0x30, PLAYER.to_bytes(4, "big"))
    place(memory, position, kind, name)
    memory.put(rb.SET_FOG_DIRECT, rb.SET_FOG_CODE)
    memory.put(rb.WORLD_MGR, WORLD.to_bytes(4, "big"))
    memory.put(WORLD + rb.MGR_COUNT, (7).to_bytes(4, "big"))
    memory.put(WORLD + rb.MGR_ARRAY, ARRAY.to_bytes(4, "big"))
    memory.put(ARRAY + 4 * rb.ENV_INDEX, ENV.to_bytes(4, "big"))
    return memory


def place(memory, position, kind="MainField", name=None):
    for offset, value in zip((0x204, 0x214, 0x224), position):
        memory.put(PLAYER + offset, struct.pack(">f", value))
    memory.put(rb.MAP_TYPE, kind.encode().ljust(32, b"\0"))
    memory.put(rb.MAP_NAME, (name or rb.cell(position)).encode().ljust(32, b"\0"))


class Clock:
    now = 100.0

    def __call__(self):
        return self.now


def border(memory, closed=frozenset({"East"}), clock=None):
    holds = []
    sign = rb.RegionBorder(memory.read, memory.write, lambda index, passes: holds.append((index, passes)) or True,
                           rb.Areas(Grid(), {0: "West", 1: "East"}), lambda: closed, clock=clock or Clock())
    return sign, holds


class AreaTests(unittest.TestCase):
    def test_the_region_at_a_point_and_the_nearest_closed_one(self):
        areas = rb.Areas(Grid(), {0: "West", 1: "East"})
        self.assertEqual(areas.region_at(-20.0, 0.0), "West")
        self.assertEqual(areas.region_at(20.0, 0.0), "East")
        self.assertEqual(areas.nearest(-20.0, 0.0, {"East"}, 30.0), ("East", 20.0))
        self.assertEqual(areas.nearest(5.0, 0.0, {"East"}, 30.0), ("East", 0.0))
        self.assertIsNone(areas.nearest(-40.0, 0.0, {"East"}, 30.0))
        self.assertIsNone(areas.nearest(-20.0, 0.0, {"North"}, 30.0))

    def test_the_game_s_areas_are_named_after_their_towers(self):
        try:
            areas = rb.load_areas()
        except (OSError, ValueError) as exc:
            self.skipTest(f"no update in the Cemu profile: {exc}")
        self.assertEqual(len(areas.regions), 15)
        self.assertEqual(areas.region_at(-560.0, 1694.9), "Great Plateau")    # its tower
        self.assertEqual(areas.region_at(-788.6, 442.0), "Central")
        self.assertNotIn("Hyrule Castle", areas.regions)                      # inside Central's area


class RampTests(unittest.TestCase):
    def test_from_light_at_start_to_the_wall_at_the_border(self):
        self.assertEqual(rb.ramp(rb.START), rb.LIGHT)
        self.assertEqual(rb.ramp(rb.START * 2), rb.LIGHT)
        for got, wanted in zip(rb.ramp(0.0), rb.WALL):
            self.assertAlmostEqual(got, wanted)
        ratio, near, far = rb.ramp(rb.START / 2)
        self.assertAlmostEqual(ratio, 0.5)
        self.assertAlmostEqual(far, (rb.LIGHT[2] * rb.WALL[2]) ** 0.5)

    def test_the_cell_the_engine_names(self):
        self.assertEqual(rb.cell((-20.0, 0.0, 0.0)), "E-5")
        self.assertEqual(rb.cell((-4999.0, 0.0, 3999.0)), "A-8")


class SignTests(unittest.TestCase):
    def test_the_fog_then_the_message_then_both_let_go(self):
        memory = game((-20.0, 100.0, 0.0))
        sign, holds = border(memory)
        state = sign.tick()
        self.assertTrue(state["field"])
        self.assertEqual((state["region"], state["nearest"]), ("West", ("East", 20.0)))
        self.assertFalse(state["message"])
        fog = struct.pack(">3f", *rb.ramp(20.0))
        self.assertEqual(memory.writes, [(ENV + rb.FOG, fog), (ENV + rb.SWITCHES, bytes((0, 1, 1))),
                                         (ENV + rb.FOG_TIMER, struct.pack(">i", rb.HOLD))])
        self.assertEqual(holds, [])
        place(memory, (-5.0, 100.0, 0.0))
        self.assertTrue(sign.tick()["message"])
        self.assertEqual(holds, [(46, rb.MARGIN)])
        place(memory, (-100.0, 100.0, 0.0))
        memory.writes.clear()
        state = sign.tick()
        self.assertEqual((state["nearest"], state["fog"], state["message"]), (None, None, False))
        self.assertEqual(memory.writes, [(ENV + rb.FOG_TIMER, struct.pack(">i", 0))])
        self.assertEqual(holds[-1], (46, 0))

    def test_nothing_without_region_lock_or_a_readable_flag(self):
        memory = game((-5.0, 100.0, 0.0))
        sign, holds = border(memory, closed=None)
        self.assertIsNone(sign.tick()["nearest"])
        self.assertEqual((memory.writes, holds), ([], []))

    def test_no_fog_written_through_an_unknown_setter(self):
        memory = game((-20.0, 100.0, 0.0))
        memory.put(rb.SET_FOG_DIRECT, bytes(len(rb.SET_FOG_CODE)))
        sign, _ = border(memory)
        sign.tick()
        self.assertEqual(memory.writes, [])

    def test_out_of_the_main_field_or_its_position_behind_nothing_shows(self):
        memory = game((-5.0, 100.0, 0.0), kind="CDungeon", name="Dungeon072")
        sign, holds = border(memory)
        self.assertFalse(sign.tick()["field"])
        place(memory, (-5.0, 100.0, 0.0), name="A-1")       # the name not yet Link's cell
        self.assertFalse(sign.tick()["field"])
        self.assertEqual((memory.writes, holds), ([], []))

    def test_after_a_change_of_stage_the_position_must_jump_or_time_pass(self):
        clock = Clock()
        memory = game((-5.0, 100.0, 0.0), kind="CDungeon", name="Dungeon072")
        sign, _ = border(memory, clock=clock)
        sign.tick()
        place(memory, (-5.0, 100.0, 0.0))                   # MainField, the shrine's position
        self.assertFalse(sign.tick()["field"])
        clock.now += 1.0
        place(memory, (-80.0, 100.0, 0.0))                  # the jump: more than JUMP metres
        self.assertTrue(sign.tick()["field"])
        place(memory, (-5.0, 100.0, 0.0), kind="CDungeon", name="Dungeon072")
        sign.tick()
        place(memory, (-5.0, 100.0, 0.0))
        clock.now += 1.0
        self.assertFalse(sign.tick()["field"])
        clock.now += rb.SETTLE_SECONDS
        self.assertTrue(sign.tick()["field"])

    def test_release_lets_the_game_s_fog_and_the_message_go(self):
        memory = game((-5.0, 100.0, 0.0))
        sign, holds = border(memory)
        sign.tick()
        memory.writes.clear()
        sign.release()
        self.assertEqual(memory.writes, [(ENV + rb.FOG_TIMER, struct.pack(">i", 0))])
        self.assertEqual(holds[-1], (46, 0))


class RuntimeTests(unittest.TestCase):
    def runtime(self, slot):
        from types import SimpleNamespace
        from botw_client.runtime import BotwClientRuntime
        runtime = BotwClientRuntime.__new__(BotwClientRuntime)
        runtime.ap, runtime._border, runtime._border_zone, runtime._border_gap = (
            SimpleNamespace(slot_data=slot), None, None, 0.0)
        runtime.lines = []
        runtime.log = runtime.lines.append
        return runtime

    def test_the_console_reports_the_sign_and_the_longest_gap(self):
        runtime = self.runtime({"region_lock": 1})
        self.assertIn("not started", runtime._border_report())
        sign, _ = border(game((-20.0, 100.0, 0.0)))
        sign.tick()
        runtime._border, runtime._border_gap = sign, 0.34
        report = runtime._border_report()
        self.assertIn("region West", report)
        self.assertIn("nearest closed: East, 20.0 m", report)
        self.assertIn("0.34 s", report)
        self.assertEqual(runtime._border_gap, 0.0)
        self.assertIn("off in this slot", self.runtime({})._border_report())

    def test_the_log_tells_each_zone_once(self):
        runtime = self.runtime({"region_lock": 1})
        for state in ({"nearest": ("East", 25.0), "message": False}, {"nearest": ("East", 22.0), "message": False},
                      {"nearest": ("East", 8.0), "message": True}, {"nearest": None, "message": False}):
            runtime._log_border(state)
        self.assertEqual(len(runtime.lines), 3)
        self.assertIn("East closed, 25 m away: fog", runtime.lines[0])
        self.assertIn("message", runtime.lines[1])
        self.assertIn("no closed region near", runtime.lines[2])


if __name__ == "__main__":
    unittest.main()
