"""The Downpour and Yiga Ambush traps: the weather held by the pack
(tools/build_weather_native.py, botw_client/downpour.py), the Yiga squad created
by the client (botw_client/yiga_ambush.py), and the client playing them."""
from __future__ import annotations

import inspect
import math
from pathlib import Path
import random
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from botw_client import downpour, yiga_ambush
from botw_client.cucco_swarm import (CREATOR, HEAP_HOLDER, NEW_IN_HEAP, PACK_ADD, PACK_CTOR, PLAYER_INFO,
                                     REQUEST_CREATE)
from botw_client.runtime import NATIVE_TRAP_PATIENCE_SECONDS, BotwClientRuntime
from tools.build_weather_native import MAGIC, SET_WEATHER


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.build_native_from_source import generate
        cls.text = generate()["runtime/patch_apInject.asm"].decode("utf-8")

    def test_every_pack_holds_the_weather_at_the_head_of_the_invokers_block(self):
        block = self.text[self.text.index("apCheckCall:"):self.text.index("apDone:")]
        self.assertLess(block.index("apWeatherFrames@l(r12)"), block.index("apPfReq@l(r11)"))
        # The world manager as the game loads it (0x021c2d64), the setter through ctr.
        self.assertIn("lis   r3, 0x1048\n    lwz   r3, -0x4178(r3)", block)
        self.assertIn(f"lis   r12, 0x{SET_WEATHER >> 16:04x}\n    ori   r12, r12, 0x{SET_WEATHER & 0xFFFF:04x}",
                      block)
        # The world's frames: counted only when the manager's timer went below 4.
        self.assertIn("lwz   r12, 0x60c(r3)\n    cmpwi r12, 4\n    bge   apWeatherSet", block)
        # The ceiling, before the world: spent, it ends the hold whatever the timer says.
        self.assertLess(block.index("apWeatherPasses@l(r12)"), block.index("lwz   r12, 0x60c(r3)"))
        self.assertIn("li    r4, 0\n    lis   r12, apWeatherFrames@ha\n    stw   r4, apWeatherFrames@l(r12)",
                      block)
        # Every frame reaches it: the hook's blocks end in the invoker's.
        self.assertEqual(self.text.count("apCheckCall:"), 1)

    def test_the_fields_follow_the_tower_maps_where_the_client_writes_them(self):
        tail = self.text[self.text.index("apMapMagic:"):]
        words = [line for line in tail.split("\n")[:24]
                 if line.startswith((".int", ".string", ".align")) or line.endswith(":")]
        self.assertEqual(words[:15], [
            "apMapMagic:", ".int 0x4D4F5031", "apMapTower:", ".int 0xFFFFFFFF", "apTowerName:",
            '.string "APTower_"', ".align 4", "apWeatherMagic:", f".int 0x{MAGIC:08X}", "apWeatherType:",
            ".int 0", "apWeatherFrames:", ".int 0", "apWeatherPasses:", ".int 0"])
        # apMapTower at +9296; "APTower_" and its terminator, 9 bytes, aligned to 12.
        from tools.cemu import mailbox
        source = inspect.getsource(mailbox)
        self.assertIn("self.map_tower = version_addr + 9296", source)
        self.assertEqual(9296 + 4 + 12, 9312)
        for name, offset in (("weather_magic", 9312), ("weather_type", 9316), ("weather_frames", 9320),
                             ("weather_passes", 9324)):
            self.assertIn(f"self.{name} = version_addr + {offset}", source)
        self.assertEqual(mailbox.Cave.WEATHER_MAGIC, MAGIC)


class CaveTests(unittest.TestCase):
    def test_the_type_and_the_ceiling_are_written_before_the_frames(self):
        from tools.cemu.mailbox import Cave
        memory = Mock()
        memory.read.return_value = MAGIC.to_bytes(4, "big")
        cave = Cave(memory, 0x1000, 0)
        self.assertTrue(cave.force_weather(7, 2700))
        self.assertEqual([call.args for call in memory.write.call_args_list],
                         [(cave.weather_type, (7).to_bytes(4, "big")),
                          (cave.weather_passes, (2700 * 3).to_bytes(4, "big")),
                          (cave.weather_frames, (2700).to_bytes(4, "big"))])

    def test_a_patch_without_the_hold_is_left_alone(self):
        from tools.cemu.mailbox import Cave
        memory = Mock()
        memory.read.return_value = bytes(4)
        cave = Cave(memory, 0x1000, 0)
        self.assertFalse(cave.force_weather(2, 3600))
        self.assertIsNone(cave.weather_left())
        memory.write.assert_not_called()

    def test_the_frames_left_are_read_where_the_hook_counts_them(self):
        from tools.cemu.mailbox import Cave
        memory = Mock()
        cave = Cave(memory, 0x1000, 0)
        memory.read.side_effect = lambda address, size: (
            MAGIC.to_bytes(4, "big") if address == cave.weather_magic else (1234).to_bytes(4, "big"))
        self.assertEqual(cave.weather_left(), 1234)


class MarkTests(unittest.TestCase):
    """The backend marks a downpour with the pack's volatile flag, APDownpour."""

    def backend(self, flag="APDownpour"):
        from botw_client.native_delivery import CemuNativeDeliveryBackend
        live = SimpleNamespace(values={}, get=None, set=None)
        live.set = lambda key, value, kind: live.values.__setitem__(key, int(value)) or True
        live.get = lambda key, kind: live.values.get(key)
        weather = []
        cave = SimpleNamespace(force_weather=lambda kind, frames: weather.append((kind, frames)) or True,
                               weather_left=lambda: 77)
        backend = SimpleNamespace(game=SimpleNamespace(live=live, cave=cave),
                                  catalog=SimpleNamespace(downpour_flag=lambda: flag))
        for name in ("downpour", "downpour_state", "end_downpour", "_downpour_mark"):
            setattr(backend, name, getattr(CemuNativeDeliveryBackend, name).__get__(backend))
        return backend, live, weather

    def test_a_downpour_is_marked_and_its_state_read(self):
        import zlib
        backend, live, weather = self.backend()
        self.assertTrue(backend.downpour(7, 2700))
        self.assertEqual(weather, [(7, 2700)])
        self.assertEqual(live.values, {zlib.crc32(b"APDownpour"): 1})
        self.assertEqual(backend.downpour_state(), (77, True))
        live.values.clear()                         # a loaded save: the flag back to its default
        self.assertEqual(backend.downpour_state(), (77, None))
        live.values[zlib.crc32(b"APDownpour")] = 0
        self.assertEqual(backend.downpour_state(), (77, False))
        self.assertTrue(backend.end_downpour())
        self.assertEqual(weather[-1], (0, 0))

    def test_a_pack_without_the_flag_marks_nothing(self):
        backend, live, _weather = self.backend(flag=None)
        self.assertTrue(backend.downpour(2, 3600))
        self.assertEqual(live.values, {})
        self.assertEqual(backend.downpour_state(), (77, None))


class DownpourTests(unittest.TestCase):
    def test_rain_for_two_minutes_or_a_storm_for_ninety_seconds(self):
        seen = {downpour.choose(random.Random(seed)) for seed in range(40)}
        self.assertEqual(seen, {(2, 120 * 30), (7, 90 * 30)})
        self.assertEqual(downpour.name(7), "thunderstorm")
        self.assertEqual(downpour.name(2), "rain")


class Memory:
    """The guest memory the squad reads and writes, and the calls it makes."""

    def __init__(self, link=(100.0, 50.0, 200.0)):
        self.words = {PLAYER_INFO: 0x2000, 0x2030: 0x3000, CREATOR: 0x4000, HEAP_HOLDER: 0x5000,
                      0x5010: 0x6000}
        for axis, value in enumerate(link):
            self.words[0x3000 + 0x204 + 0x10 * axis] = struct.unpack(">I", struct.pack(">f", value))[0]
        self.written, self.calls, self.blocks = {}, [], 0

    def read(self, guest, size):
        return self.words.get(guest, 0).to_bytes(4, "big") if size == 4 else bytes(size)

    def write(self, guest, data):
        self.written[guest] = data

    def call(self, address, *args):
        self.calls.append((address, args))
        if address == NEW_IN_HEAP:
            self.blocks += 1
            return 0x10000000 + 0x1000 * self.blocks
        return 1 if address == REQUEST_CREATE else 0


class AmbushTests(unittest.TestCase):
    def test_two_footsoldiers_and_an_archer_around_link_each_in_its_own_block(self):
        memory = Memory()
        result = yiga_ambush.ambush(memory.read, memory.write, memory.call, squad=yiga_ambush.SQUAD,
                                    rng=random.Random(4))
        self.assertEqual(result, {"ok": 3})
        requests = [args for address, args in memory.calls if address == REQUEST_CREATE]
        self.assertEqual(len({args[1] for args in requests}), 3)          # three names
        self.assertEqual(len({args[4] for args in requests}), 3)          # three packs
        self.assertEqual([memory.written[args[1]] for args in requests],
                         [b"Enemy_Assassin_Junior\0", b"Enemy_Assassin_Junior\0",
                          b"Enemy_Assassin_Shooter_Junior\0"])
        self.assertTrue(all(args[3] == 0 for args in requests))          # no handle: the game's own
        places = [struct.unpack(">fff", data) for data in memory.written.values() if len(data) == 12]
        self.assertEqual(len(places), 3)
        for x, y, z in places:
            self.assertAlmostEqual(y, 51.0)
            self.assertTrue(6.0 <= math.hypot(x - 100.0, z - 200.0) <= 8.0)
        # The pack built before the request, in the block's own room: the place,
        # then the weapon, a string of type 5 as the game's creations add it.
        order = [address for address, _ in memory.calls]
        self.assertEqual(order[:6], [NEW_IN_HEAP, PACK_CTOR, PACK_ADD, PACK_ADD, REQUEST_CREATE,
                                     NEW_IN_HEAP])
        weapons = [args for address, args in memory.calls if address == PACK_ADD and args[4] == 5]
        self.assertEqual([(memory.written[args[1]], args[3]) for args in weapons],
                         [(b"Weapon_Sword_053\0", 17), (b"Weapon_Sword_053\0", 17),
                          (b"Weapon_Bow_040\0", 15)])
        self.assertTrue(all(memory.written[args[2]][:4] != bytes(4) for args in weapons))

    def test_a_blademaster_alone_one_time_in_ten(self):
        rng = random.Random(7)
        drawn = [yiga_ambush.draw(rng) for _ in range(2000)]
        share = drawn.count(yiga_ambush.BLADEMASTER_SQUAD) / len(drawn)
        self.assertAlmostEqual(share, 0.1, delta=0.03)
        self.assertEqual(set(drawn), {yiga_ambush.SQUAD, yiga_ambush.BLADEMASTER_SQUAD})
        self.assertEqual(yiga_ambush.BLADEMASTER_SQUAD, (("Enemy_Assassin_Middle", "Weapon_Lsword_074"),))

    def test_no_player_no_yiga(self):
        memory = Memory()
        memory.words[PLAYER_INFO] = 0
        self.assertEqual(yiga_ambush.ambush(memory.read, memory.write, memory.call), {"player": 1})
        self.assertEqual(memory.calls, [])

    def test_not_while_the_traps_event_is_closing(self):
        from botw_client.native_delivery import SETTLE_FRAMES, CemuNativeDeliveryBackend
        backend = CemuNativeDeliveryBackend.__new__(CemuNativeDeliveryBackend)
        frame = [1000]
        backend.game = SimpleNamespace(frame_tick=lambda: frame[0])
        backend._committed_at = 970                     # the trap's commit, 30 frames ago
        backend._drop_blocked = lambda: None
        turns = []
        backend._in_one_turn = lambda work: turns.append(work) or "ok"
        self.assertEqual(backend.yiga_ambush(), f"the trap's event closing (30/{SETTLE_FRAMES} frames of 1/30 s)")
        self.assertEqual(turns, [])
        frame[0] = 970 + SETTLE_FRAMES
        self.assertEqual(backend.yiga_ambush(), {})
        self.assertEqual(len(turns), 1)


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.lines = []
        self.runtime = BotwClientRuntime(
            "localhost:1", "Player", state_path=Path(self.directory.name) / "state.json",
            log=self.lines.append, game_factory=SimpleNamespace, tip_factory=object)
        self.weathers, self.answers, self.ended = [], [], []
        self.state = (3000, True)
        self.dead = False
        self.runtime.game = SimpleNamespace(is_dead=lambda: self.dead)
        self.runtime.deliveries = SimpleNamespace(backend=SimpleNamespace(
            downpour=lambda kind, frames: self.weathers.append((kind, frames)) or True,
            downpour_state=lambda: self.state,
            end_downpour=lambda: self.ended.append(1) or True,
            yiga_ambush=lambda: self.answers.pop(0)))

    async def start_downpour(self):
        self.runtime._native_traps.append("downpour")
        await self.runtime._native_trap_tick()
        self.assertTrue(self.runtime._downpour_active)

    async def test_a_downpour_goes_on_while_link_lives_in_the_same_save(self):
        await self.start_downpour()
        await self.runtime._downpour_tick()
        self.assertEqual(self.ended, [])
        self.assertTrue(self.runtime._downpour_active)

    async def test_a_loaded_save_ends_the_downpour(self):
        await self.start_downpour()
        self.state = (2900, False)
        await self.runtime._downpour_tick()
        self.assertEqual(self.ended, [1])
        self.assertFalse(self.runtime._downpour_active)
        self.assertEqual(self.lines[-1], "Downpour ended: a save was loaded")

    async def test_a_death_ends_the_downpour(self):
        await self.start_downpour()
        self.dead = True
        await self.runtime._downpour_tick()
        self.assertEqual(self.ended, [1])
        self.assertEqual(self.lines[-1], "Downpour ended: Link died")

    async def test_a_downpour_over_by_itself_is_left_alone(self):
        await self.start_downpour()
        self.state, self.dead = (0, False), True
        await self.runtime._downpour_tick()
        self.assertEqual(self.ended, [])
        self.assertFalse(self.runtime._downpour_active)
        self.assertRegex(self.lines[-1], r"^Downpour over by itself after \d+ s$")

    async def test_an_unreadable_mark_ends_nothing(self):
        await self.start_downpour()
        self.state = (2900, None)
        await self.runtime._downpour_tick()
        self.assertEqual(self.ended, [])
        self.assertTrue(self.runtime._downpour_active)

    async def test_a_downpour_writes_its_weather_once(self):
        self.runtime._native_traps.append("downpour")
        await self.runtime._native_trap_tick()
        self.assertEqual(len(self.weathers), 1)
        self.assertIn(self.weathers[0], {(2, 3600), (7, 2700)})
        self.assertEqual(self.runtime._native_traps, [])
        self.assertTrue(self.lines[-1].startswith("Downpour played"))

    async def test_under_fps_plus_plus_a_downpour_lasts_as_long(self):
        # 60 frames a second at a delta of x0.50: twice the frames, the same game time.
        self.runtime.game.game_delta = lambda: 0.5
        self.runtime._native_traps.append("downpour")
        await self.runtime._native_trap_tick()
        self.assertIn(self.weathers[0], {(2, 7200), (7, 5400)})
        self.assertRegex(self.lines[-1], r"^Downpour played: \w+ for (120|90) s of game time "
                                         r"\((7200|5400) frames at x0\.50\)$")

    async def test_an_ambush_waits_for_link_then_plays(self):
        self.answers[:] = ["Link not in the world", {"ok": 3}]
        self.runtime._native_traps.append("yiga_ambush")
        await self.runtime._native_trap_tick()
        self.assertEqual(self.runtime._native_traps, ["yiga_ambush"])
        await self.runtime._native_trap_tick()
        self.assertEqual(self.runtime._native_traps, [])
        self.assertEqual(self.lines[-1], "Yiga Ambush played: {'ok': 3}")

    async def test_an_ambush_waiting_too_long_is_given_up(self):
        self.answers[:] = ["Link not in the world", "Link not in the world"]
        self.runtime._native_traps.append("yiga_ambush")
        await self.runtime._native_trap_tick()
        self.runtime._native_trap_since -= NATIVE_TRAP_PATIENCE_SECONDS + 1
        await self.runtime._native_trap_tick()
        self.assertEqual(self.runtime._native_traps, [])
        self.assertEqual(self.lines[-1], "Yiga Ambush given up: Link not in the world")


if __name__ == "__main__":
    unittest.main()
