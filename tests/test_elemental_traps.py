"""The Freeze, Fire and Lightning Strike traps: one actor of the game created on
Link by the client (botw_client/elemental_strike.py), and the client playing them."""
from __future__ import annotations

from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest

from botw_client import death_cause, elemental_strike
from botw_client.cucco_swarm import (CREATOR, HEAP_HOLDER, NEW_IN_HEAP, PACK_ADD, PACK_CTOR, PLAYER_INFO,
                                     REQUEST_CREATE)
from botw_client.runtime import NATIVE_TRAP_PATIENCE_SECONDS, BotwClientRuntime


class Memory:
    """The guest memory the trap reads and writes, and the calls it makes."""

    def __init__(self, link=(100.0, 50.0, 200.0)):
        self.words = {PLAYER_INFO: 0x2000, 0x2030: 0x3000, CREATOR: 0x4000, HEAP_HOLDER: 0x5000,
                      0x5010: 0x6000}
        for axis, value in enumerate(link):
            self.words[0x3000 + 0x204 + 0x10 * axis] = struct.unpack(">I", struct.pack(">f", value))[0]
        self.written, self.calls = {}, []

    def read(self, guest, size):
        return self.words.get(guest, 0).to_bytes(4, "big") if size == 4 else bytes(size)

    def write(self, guest, data):
        self.written[guest] = data

    def call(self, address, *args):
        self.calls.append((address, args))
        if address == NEW_IN_HEAP:
            return 0x10001000
        return 1 if address == REQUEST_CREATE else 0


class StrikeTests(unittest.TestCase):
    def test_each_effect_creates_its_actor_where_link_stands(self):
        for effect, actor, up in (("freeze", b"ExpandIceField\0", 0.5), ("fire", b"ExpandFireField\0", 0.5),
                                  ("lightning", b"LastBossThunder\0", 0.0)):
            with self.subTest(effect=effect):
                memory = Memory()
                self.assertEqual(elemental_strike.strike(memory.read, memory.write, memory.call, effect),
                                 {"ok": 1})
                self.assertEqual([address for address, _ in memory.calls],
                                 [NEW_IN_HEAP, PACK_CTOR, PACK_ADD, REQUEST_CREATE])
                request = memory.calls[-1][1]
                self.assertEqual(memory.written[request[1]], actor)
                self.assertEqual(request[3], 0)                      # no handle: the game's own
                places = [struct.unpack(">fff", data) for data in memory.written.values() if len(data) == 12]
                self.assertEqual(places, [(100.0, 50.0 + up, 200.0)])

    def test_no_player_no_strike(self):
        memory = Memory()
        memory.words[PLAYER_INFO] = 0
        self.assertEqual(elemental_strike.strike(memory.read, memory.write, memory.call, "fire"), {"player": 1})
        self.assertEqual(memory.calls, [])

    def test_not_while_the_traps_event_is_closing(self):
        from botw_client.native_delivery import SETTLE_FRAMES, CemuNativeDeliveryBackend
        backend = CemuNativeDeliveryBackend.__new__(CemuNativeDeliveryBackend)
        frame = [1000]
        backend.game = SimpleNamespace(frame_tick=lambda: frame[0])
        backend._committed_at = 970
        backend._drop_blocked = lambda: None
        turns = []
        backend._in_one_turn = lambda work: turns.append(work) or "ok"
        self.assertEqual(backend.elemental_strike("freeze"),
                         f"the trap's event closing (30/{SETTLE_FRAMES} frames of 1/30 s)")
        frame[0] = 970 + SETTLE_FRAMES
        self.assertEqual(backend.elemental_strike("freeze"), {})
        self.assertEqual(len(turns), 1)

    def test_the_bolt_kills_by_lightning_not_by_a_blast(self):
        # Measured in lab probe 56: cause 9 (a blast), raw 0x20006, LastBossThunder.
        self.assertEqual(death_cause.death_text("Zelda", 9, 0x20006, "LastBossThunder", {}),
                         "Zelda was struck by lightning")
        self.assertEqual(death_cause.death_text("Zelda", 9, 0x20006, None, {}), "Zelda was blown up")


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.lines, self.answers, self.effects = [], [], []
        self.runtime = BotwClientRuntime(
            "localhost:1", "Player", state_path=Path(self.directory.name) / "state.json",
            log=self.lines.append, game_factory=SimpleNamespace, tip_factory=object)
        self.runtime.game = SimpleNamespace(is_dead=lambda: False)
        self.runtime.deliveries = SimpleNamespace(backend=SimpleNamespace(
            elemental_strike=lambda effect: self.effects.append(effect) or self.answers.pop(0)))

    async def test_a_strike_waits_for_link_then_plays(self):
        self.answers[:] = ["Link not in the world", {"ok": 1}]
        self.runtime._native_traps.append("lightning")
        await self.runtime._native_trap_tick()
        self.assertEqual(self.runtime._native_traps, ["lightning"])
        await self.runtime._native_trap_tick()
        self.assertEqual(self.runtime._native_traps, [])
        self.assertEqual(self.effects, ["lightning", "lightning"])
        self.assertEqual(self.lines[-1], "Lightning Strike played: {'ok': 1}")

    async def test_a_strike_waiting_too_long_is_given_up(self):
        self.answers[:] = ["Link not in the world", "Link not in the world"]
        self.runtime._native_traps.append("freeze")
        await self.runtime._native_trap_tick()
        self.runtime._native_trap_since -= NATIVE_TRAP_PATIENCE_SECONDS + 1
        await self.runtime._native_trap_tick()
        self.assertEqual(self.runtime._native_traps, [])
        self.assertEqual(self.lines[-1], "Freeze given up: Link not in the world")


if __name__ == "__main__":
    unittest.main()
