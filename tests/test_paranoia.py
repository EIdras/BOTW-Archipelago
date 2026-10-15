"""The Paranoia trap (botw_client/paranoia.py): a Guardian created behind Link,
turned towards him, woken, and deleted through its own link before it fires."""
from __future__ import annotations

import math
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest

from botw_client import paranoia as pa
from botw_client.cucco_swarm import (CREATOR, HEAP_HOLDER, NEW_IN_HEAP, PACK_ADD, PACK_CTOR, PLAYER_INFO,
                                     REQUEST_CREATE)
from botw_client.runtime import BotwClientRuntime

PROC, DATA, IDENT = 0x46000000, 0x41000000, 0x383


def word(value: float) -> int:
    return struct.unpack(">I", struct.pack(">f", value))[0]


class Game:
    """The guest memory and the game's functions the trap calls."""

    def __init__(self, *, ready_after=2, link=True, gone=False, fps=None, delta=None):
        self.words = {PLAYER_INFO: 0x2000, 0x2030: 0x3000, CREATOR: 0x4000, HEAP_HOLDER: 0x5000,
                      0x5010: 0x6000, PROC + pa.LINK_ID: IDENT, PROC + pa.LINK_DATA: DATA}
        for axis, value in enumerate((100.0, 50.0, 200.0)):         # Link's place
            self.words[0x3000 + pa.POSITION + 0x10 * axis] = word(value)
        for axis, value in enumerate((1.0, 0.0, 0.0)):              # facing +X
            self.words[0x3000 + pa.FORWARD + 0x10 * axis] = word(value)
        if link:
            self.words[DATA + 0x3C], self.words[DATA + 0x40] = IDENT, PROC
        if delta is not None:                                     # the frame-rate manager
            self.words[pa.VFR], self.words[0x48000000 + pa.VFR_DELTA] = 0x48000000, word(delta)
        self.gone, self.ready_after, self.fps = gone, ready_after, fps
        self.written, self.calls, self.now = {}, [], 0.0

    def read(self, guest, size):
        return self.words.get(guest, 0).to_bytes(4, "big") if size == 4 else bytes(size)

    def write(self, guest, data):
        self.written[guest] = data

    def call(self, address, *args):
        self.calls.append((address, args))
        if address == NEW_IN_HEAP:
            return 0x30000000
        if address == HANDLE_READY_ADDRESS:
            self.ready_after -= 1
            return 1 if self.ready_after < 0 else 0
        if address == pa.HANDLE_PROC:
            return PROC
        if address == pa.WAKE and self.gone:
            self.words[DATA + 0x3C] = 0x999                        # defeated: its data reused
        return 1

    def clock(self):
        return self.now

    def frame(self):
        """The cave's frame counter: `fps` frames a second of wall time."""
        return int(self.now * self.fps + 1e-6) & 0xFFFFFFFF

    def sleep(self, seconds):
        self.now += seconds

    def called(self, address):
        return [args for a, args in self.calls if a == address]


HANDLE_READY_ADDRESS = pa.HANDLE_READY


class PlaceTests(unittest.TestCase):
    def test_behind_link_turned_towards_him(self):
        self.assertEqual(pa.DISTANCE, 15.0)
        where, yaw = pa.behind((100.0, 50.0, 200.0), (0.0, 0.0, 2.0))     # facing +Z, any length
        self.assertEqual(where, (100.0, 50.0, 185.0))
        self.assertAlmostEqual(yaw, 0.0)
        where, yaw = pa.behind((100.0, 50.0, 200.0), (1.0, 0.0, 0.0))
        self.assertEqual(where, (85.0, 50.0, 200.0))
        # Its +Z (sin yaw, 0, cos yaw), measured so in the game: towards Link.
        self.assertAlmostEqual(math.sin(yaw), 1.0)


class TrapTests(unittest.TestCase):
    def play(self, game, stop=lambda: False):
        return pa.Paranoia(game.read, game.write, game.call, clock=game.clock, sleep=game.sleep,
                           frames=game.frame if game.fps else None).run(stop)

    def test_created_with_place_and_rotation_woken_and_deleted_at_its_time(self):
        game = Game()
        self.assertTrue(self.play(game).startswith("deleted after "))
        (request,) = game.called(REQUEST_CREATE)
        base = 0x30000000
        self.assertEqual(request, (0x4000, base + pa.NAME, 0x6000, base + pa.HANDLE, base, 0, 1))
        self.assertEqual(game.written[base + pa.NAME], b"Enemy_Guardian_A_Fixed_Moss\0")
        self.assertEqual(game.written[base + pa.R_TEXT], b"@R\0")
        self.assertEqual(struct.unpack(">fff", game.written[base + pa.P_VALUE]), (85.0, 50.0, 200.0))
        self.assertAlmostEqual(struct.unpack(">fff", game.written[base + pa.R_VALUE])[1], math.pi / 2, 5)
        self.assertEqual([args[1:] for args in game.called(PACK_ADD)],
                         [(base + pa.P_VALUE, base + pa.P_KEY, 0xC, 4),
                          (base + pa.R_VALUE, base + pa.R_KEY, 0xC, 4)])
        self.assertEqual(game.called(pa.WAKE), [(PROC, 0)])
        self.assertEqual(game.called(pa.DELETE_LATER), [(PROC, 2)])
        self.assertEqual(game.called(pa.HANDLE_DELETE), [])
        # Deleted LIFETIME after its waking, not before.
        order = [a for a, _ in game.calls]
        self.assertLess(order.index(pa.WAKE), order.index(pa.DELETE_LATER))
        self.assertGreaterEqual(game.now, pa.LIFETIME)
        self.assertLess(pa.LIFETIME, 7.1)

    def test_it_strikes_once_woken_and_never_without_its_link(self):
        for game, strikes in ((Game(), 1), (Game(link=False), 0), (Game(ready_after=10_000), 0)):
            seen = []
            pa.Paranoia(game.read, game.write, game.call, clock=game.clock, sleep=game.sleep).run(
                struck=lambda: seen.append(game.called(pa.WAKE)))
            self.assertEqual(len(seen), strikes)
            if seen:
                self.assertEqual(seen[0], [(PROC, 0)])           # after its waking

    def test_a_guardian_without_its_link_is_deleted_before_it_wakes(self):
        game = Game(link=False)
        self.assertEqual(self.play(game), "no link")
        self.assertEqual(game.called(pa.WAKE), [])
        self.assertEqual(game.called(pa.HANDLE_DELETE), [(0x30000000 + pa.HANDLE,)])

    def test_a_guardian_gone_before_its_time_is_left_alone(self):
        game = Game(gone=True)
        self.assertTrue(self.play(game).startswith("gone after "))
        self.assertEqual(game.called(pa.DELETE_LATER), [])

    def test_stopped_the_guardian_is_deleted_at_once(self):
        game = Game()
        woken = []

        def stop():
            if game.called(pa.WAKE) and not woken:
                woken.append(game.now)
            return bool(woken)
        self.assertTrue(self.play(game, stop).startswith("deleted after "))
        self.assertLess(game.now - woken[0], pa.LIFETIME)

    def test_never_ready_it_is_deleted_through_its_handle(self):
        game = Game(ready_after=10_000)
        self.assertEqual(self.play(game), "not ready")
        self.assertEqual(game.called(pa.WAKE), [])
        self.assertEqual(game.called(pa.HANDLE_DELETE), [(0x30000000 + pa.HANDLE,)])

    def woken_for(self, game):
        """The wall time from its waking to its deletion, and the outcome."""
        outcome = self.play(game)
        order = [a for a, _ in game.calls]
        self.assertLess(order.index(pa.WAKE), order.index(pa.DELETE_LATER))
        return game.now, outcome

    def test_its_time_is_the_games_in_a_turbo(self):
        # Paced on a vsync three times faster: 90 frames a second at a delta of 1.
        now, outcome = self.woken_for(Game(fps=90, delta=1.0))
        self.assertLess(now, pa.LIFETIME / 3 + 0.2)
        self.assertIn("speed x1.00", outcome)

    def test_its_time_is_the_wall_clock_under_fps_plus_plus(self):
        # 60 frames a second, each worth half a frame of 1/30 s.
        now, outcome = self.woken_for(Game(fps=60, delta=0.5))
        self.assertGreaterEqual(now, pa.LIFETIME - 0.1)
        self.assertLess(now, pa.LIFETIME + 0.2)
        self.assertIn("speed x0.50", outcome)

    def test_a_slow_game_is_cut_by_the_wall_clock(self):
        # 15 frames a second at a delta read as 1: half the game time; the wall decides.
        now, outcome = self.woken_for(Game(fps=15, delta=1.0))
        self.assertLess(now, pa.LIFETIME + 0.2)
        self.assertTrue(outcome.startswith("deleted after 3."), outcome)

    def test_an_unreadable_delta_counts_frames_of_1_30_s(self):
        now, outcome = self.woken_for(Game(fps=90))
        self.assertLess(now, pa.LIFETIME / 3 + 0.2)
        self.assertIn("delta unreadable", outcome)
        for value in (0.0, 9.0):                    # out of its range: unreadable too
            self.assertIn("delta unreadable", self.woken_for(Game(fps=90, delta=value))[1])

    def test_no_player_no_guardian(self):
        game = Game()
        game.words[PLAYER_INFO] = 0
        self.assertEqual(self.play(game), "player")
        self.assertEqual(game.called(REQUEST_CREATE), [])
        self.assertEqual(game.called(PACK_CTOR), [])


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_paranoia_plays_on_a_thread_and_holds_the_loops_events(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        lines = []
        runtime = BotwClientRuntime(
            "localhost:1", "Player", state_path=Path(directory.name) / "state.json",
            log=lines.append, game_factory=SimpleNamespace, tip_factory=object)
        runtime.game = SimpleNamespace(is_dead=lambda: False)
        stops = []
        runtime.deliveries = SimpleNamespace(backend=SimpleNamespace(
            paranoia=lambda stop, struck: stops.append(stop) or "deleted"))
        runtime._native_traps.append("paranoia")
        await runtime._native_trap_tick()
        self.assertEqual(runtime._native_trap_task.get_name(), "Paranoia")
        await runtime._native_trap_task
        await runtime._native_trap_tick()
        self.assertEqual(lines[-1], "Paranoia played: deleted")      # as the backend says it
        self.assertEqual(stops, [runtime._swarm_should_stop])


if __name__ == "__main__":
    unittest.main()
