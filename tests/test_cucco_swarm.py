"""The Cucco Swarm trap (botw_client/cucco_swarm.py) and how the client plays it."""
import asyncio
from contextlib import contextmanager
from pathlib import Path
import random
import struct
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from botw_client import cucco_swarm as cs
from botw_client.runtime import BotwClientRuntime

PLAYER, INFO, CREATOR, HOLDER, HEAP = 0x40000000, 0x41000000, 0x42000000, 0x43000000, 0x44000000
BASE, ACTOR, TREE, FOUND, VARIABLE = 0x45000000, 0x46000000, 0x47000000, 0x48000000, 0x49000000


class Game:
    """Sparse guest memory and a per-frame invoker that answers as the game did."""

    def __init__(self, ready_after=0):
        self.memory = {}
        self.calls = []
        self.ready_after = ready_after
        self.put(cs.PLAYER_INFO, struct.pack(">I", INFO))
        self.put(INFO + 0x30, struct.pack(">I", PLAYER))
        self.put(PLAYER + 0x204, struct.pack(">f", 100.0))
        self.put(PLAYER + 0x214, struct.pack(">f", 50.0))
        self.put(PLAYER + 0x224, struct.pack(">f", -20.0))
        self.put(PLAYER + 0x50, struct.pack(">I", 2))
        self.put(PLAYER + 0x58, struct.pack(">I", 0x41B81EC4))
        self.put(cs.CREATOR, struct.pack(">I", CREATOR))
        self.put(cs.HEAP_HOLDER, struct.pack(">I", HOLDER))
        self.put(HOLDER + 0x10, struct.pack(">I", HEAP))
        self.put(ACTOR + 0x390, struct.pack(">I", TREE))
        self.put(FOUND, struct.pack(">I", VARIABLE))

    def put(self, guest, data):
        for offset, byte in enumerate(data):
            self.memory[guest + offset] = byte

    def read(self, guest, size):
        return bytes(self.memory.get(guest + i, 0) for i in range(size))

    def call(self, address, *args):
        self.calls.append((address, args))
        if address == cs.NEW_IN_HEAP:
            return BASE
        if address == cs.HANDLE_READY:
            self.ready_after -= 1
            return 1 if self.ready_after < 0 else 0
        if address == cs.HANDLE_PROC:
            return ACTOR
        if address == cs.AI_VARIABLE:
            self.put(args[1], struct.pack(">I", FOUND))
            return 1
        return 1


class SwarmTests(unittest.TestCase):
    def test_attackers_are_born_in_the_box_outside_the_prohibited_one(self):
        rng = random.Random(4)
        for _ in range(2000):
            point = cs.birthplace((100.0, 50.0, -20.0), rng)
            offset = (point[0] - 100.0, point[1] - 55.5, point[2] + 20.0)
            self.assertTrue(all(abs(o) <= a for o, a in zip(offset, cs.CREATE_AREA)))
            self.assertFalse(all(abs(o) < p for o, p in zip(offset, cs.PROHIBITED_AREA)))

    def test_one_attacker_is_created_targeted_at_link_and_let_go(self):
        game = Game(ready_after=2)
        swarm = cs.CuccoSwarm(game.read, game.put, game.call)
        self.assertTrue(swarm.prepare())
        self.assertEqual(game.calls, [(cs.NEW_IN_HEAP, (cs.MEMORY, HEAP, 4))])
        self.assertEqual(game.read(swarm.name, 13), b"Kokko_Simple\0")
        self.assertEqual(game.read(swarm.source, 9), struct.pack(">IIB", 0x41B81EC4, 2, 0))
        game.calls.clear()
        self.assertEqual(swarm.attacker((1.0, 2.0, 3.0)), "ok")
        handle = swarm.handles[0]
        self.assertEqual([address for address, _ in game.calls], [
            cs.PACK_CTOR, cs.PACK_ADD, cs.REQUEST_CREATE, cs.HANDLE_READY, cs.HANDLE_READY,
            cs.HANDLE_READY, cs.HANDLE_PROC, cs.AI_VARIABLE, cs.LINK_ASSIGN, cs.HANDLE_RELEASE])
        calls = dict(game.calls)
        self.assertEqual(calls[cs.PACK_ADD], (swarm.pack + 4, swarm.value, swarm.key, 0xC, 4))
        self.assertEqual(calls[cs.REQUEST_CREATE],
                         (CREATOR, swarm.name, HEAP, handle, swarm.pack, 0, 1))
        self.assertEqual(calls[cs.AI_VARIABLE], (TREE, swarm.out, swarm.var_key))
        self.assertEqual(calls[cs.LINK_ASSIGN], (VARIABLE + 4, swarm.source))
        self.assertEqual(struct.unpack(">fff", game.read(swarm.value, 12)), (1.0, 2.0, 3.0))

    def test_an_attacker_that_never_comes_never_lends_its_handle_again(self):
        game = Game(ready_after=10 ** 6)
        clock = iter(range(0, 10 ** 6))
        swarm = cs.CuccoSwarm(game.read, game.put, game.call, clock=lambda: next(clock))
        swarm.prepare()
        first = swarm.handles[0]
        self.assertEqual(swarm.attacker((0.0, 0.0, 0.0)), "ready")
        self.assertNotIn(first, swarm.handles)

    def test_the_swarm_does_not_start_without_link(self):
        game = Game()
        game.put(INFO + 0x30, bytes(4))
        self.assertEqual(cs.CuccoSwarm(game.read, game.put, game.call).run(), {"not_ready": 1})
        self.assertEqual(game.calls, [])

    def test_the_swarm_lasts_its_time_at_its_rhythm(self):
        game = Game()
        now = [0.0]

        def clock():
            now[0] += 0.01
            return now[0]

        swarm = cs.CuccoSwarm(game.read, game.put, game.call, clock=clock,
                              sleep=lambda seconds: now.__setitem__(0, now[0] + seconds))
        results = swarm.run()
        self.assertEqual(set(results), {"ok"})
        # One attacker every INTERVAL at most, for DURATION (the fake clock ticks per read).
        self.assertTrue(45 <= results["ok"] <= cs.DURATION / cs.INTERVAL + 1, results)

    def test_each_attacker_is_made_in_one_turn_of_the_invoker(self):
        game = Game()
        held = []
        call = game.call

        def tracked(address, *args):
            if address != cs.NEW_IN_HEAP:
                held.append(turns[-1])
            return call(address, *args)

        turns = [False]

        @contextmanager
        def turn():
            turns.append(True)
            yield
            turns.append(False)

        stops = iter([False, False, True])
        results = cs.CuccoSwarm(game.read, game.put, tracked, turn=turn).run(lambda: next(stops))
        self.assertEqual(results, {"ok": 2})
        self.assertEqual(turns.count(True), 2)
        self.assertTrue(held and all(held))

    def fake_time(self):
        now = [0.0]

        def clock():
            now[0] += 0.01
            return now[0]

        return now, clock, lambda seconds: now.__setitem__(0, now[0] + seconds)

    def test_out_of_the_world_the_swarm_creates_nothing_and_its_time_stands_still(self):
        game = Game()
        now, clock, sleep = self.fake_time()
        # A menu open for the swarm's first 30 s: nothing is born, and the
        # whole swarm comes after it closes.
        swarm = cs.CuccoSwarm(game.read, game.put, game.call, clock=clock, sleep=sleep,
                              playing=lambda: now[0] > 30.0)
        results = swarm.run()
        self.assertTrue(45 <= results["ok"], results)
        self.assertGreater(now[0], 30.0 + cs.DURATION)
        requests = [a for a, _ in game.calls if a == cs.REQUEST_CREATE]
        self.assertEqual(len(requests), results["ok"])

    def test_a_swarm_out_of_the_world_too_long_gives_up(self):
        game = Game()
        _now, clock, sleep = self.fake_time()
        swarm = cs.CuccoSwarm(game.read, game.put, game.call, clock=clock, sleep=sleep,
                              playing=lambda: False)
        self.assertEqual(swarm.run(), {"paused": 1})
        self.assertNotIn(cs.REQUEST_CREATE, [a for a, _ in game.calls])

    def test_a_turn_refused_skips_the_attacker(self):
        game = Game()

        def turn():
            raise RuntimeError("Another presentation publisher is active")

        stops = iter([False, True])
        swarm = cs.CuccoSwarm(game.read, game.put, game.call, turn=turn)
        self.assertEqual(swarm.run(lambda: next(stops)), {"busy": 1})
        self.assertEqual([address for address, _ in game.calls], [cs.NEW_IN_HEAP])


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.game = SimpleNamespace(dead=False, is_dead=lambda: self.game.dead,
                                    safe_for_delivery=lambda: True)
        self.runtime = BotwClientRuntime(
            "localhost:1", "Player", state_path=Path(self.directory.name) / "state.json",
            log=lambda _: None, game_factory=lambda: self.game, tip_factory=object)
        self.runtime.game = self.game
        self.runtime.state = self.runtime.state_store.select("seed", 0, 1)
        self.runtime.ap = SimpleNamespace(deathlinks=asyncio.Queue(), death_link_enabled=True,
                                          connected=True, slot_name="Player",
                                          send_death=AsyncMock())
        self.played = []
        self.attacker = "Kokko_Simple"
        self.runtime.deliveries = SimpleNamespace(backend=SimpleNamespace(
            cucco_swarm=lambda stop: self.played.append(stop) or {"ok": 30},
            last_attacker=lambda: self.attacker, killed_by_death_link=lambda: False,
            death_cause=lambda slot: f"{slot} was slain"))

    async def play(self):
        self.runtime._native_traps.append("cucco_swarm")
        await self.runtime._native_trap_tick()
        await self.runtime._native_trap_task
        await self.runtime._native_trap_tick()

    async def test_a_committed_swarm_is_played_once(self):
        await self.play()
        self.assertEqual(len(self.played), 1)
        self.assertEqual(self.runtime._native_traps, [])
        self.assertIsNone(self.runtime._native_trap_task)
        self.assertGreater(self.runtime._swarm_left, 0.0)

    async def death(self):
        await self.runtime._deathlink_tick()
        self.game.dead = True
        await self.runtime._deathlink_tick()

    async def test_a_death_by_the_swarm_is_not_sent(self):
        await self.play()
        await self.death()
        self.runtime.ap.send_death.assert_not_awaited()

    async def test_a_death_by_something_else_during_the_swarm_is_sent(self):
        self.attacker = "Enemy_Bokoblin_Junior"
        await self.play()
        await self.death()
        self.runtime.ap.send_death.assert_awaited_once()

    async def test_a_death_by_a_cucco_once_the_swarm_is_over_is_sent(self):
        await self.play()
        self.runtime._swarm_left = 0.0
        await self.death()
        self.runtime.ap.send_death.assert_awaited_once()

    async def test_the_attackers_time_stands_still_out_of_the_world(self):
        in_world = [False]
        self.runtime.deliveries.backend.playing = lambda: in_world[0]
        await self.play()
        left = self.runtime._swarm_left
        self.runtime._swarm_clock -= 60.0           # a menu open for a minute
        await self.runtime._native_trap_tick()
        self.assertEqual(self.runtime._swarm_left, left)
        await self.death()                          # the menu closes, a cucco kills
        self.runtime.ap.send_death.assert_not_awaited()
        in_world[0] = True
        self.runtime._swarm_clock -= 60.0           # a minute of play
        await self.runtime._native_trap_tick()
        self.assertLessEqual(self.runtime._swarm_left, 0.0)

    async def start_blocking_swarm(self):
        """A swarm that plays until it is told to stop."""
        started, stopped = threading.Event(), threading.Event()

        def swarm(stop):
            started.set()
            while not stop():
                threading.Event().wait(0.01)
            stopped.set()
            return {"ok": 3}

        self.runtime.deliveries.backend.cucco_swarm = swarm
        self.runtime._native_traps.append("cucco_swarm")
        await self.runtime._native_trap_tick()
        await asyncio.to_thread(started.wait, 2.0)
        return stopped

    async def test_the_loop_leaving_stops_the_swarm_and_waits_for_it(self):
        stopped = await self.start_blocking_swarm()
        self.assertTrue(self.runtime._swarming())
        await self.runtime._end_swarm()
        self.assertTrue(stopped.is_set())
        self.assertIsNone(self.runtime._native_trap_task)
        self.assertFalse(self.runtime._swarming())

    async def test_the_swarm_stops_when_link_dies(self):
        stopped = await self.start_blocking_swarm()
        self.game.dead = True
        await asyncio.wait_for(self.runtime._native_trap_task, 2.0)
        self.assertTrue(stopped.is_set())

    async def test_a_received_death_link_waits_for_the_swarm(self):
        requested = []
        self.runtime.deliveries.backend.request_death = lambda: requested.append(1) or True
        self.runtime.state["pending_deathlinks"] = [{
            "time": 1.0, "source": "Other", "cause": "", "received_at": __import__("time").time()}]
        self.runtime._deathlink_announced_at = 0.0     # announced long ago
        await self.start_blocking_swarm()
        await self.runtime._deathlink_tick()
        self.assertEqual(requested, [])
        await self.runtime._end_swarm()
        await self.runtime._deathlink_tick()
        self.assertEqual(requested, [1])


if __name__ == "__main__":
    unittest.main()
