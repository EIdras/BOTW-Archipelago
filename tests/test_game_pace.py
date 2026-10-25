"""The game's pace in the session's log (botw_client/game_pace.py) and the
game's delta it reads (botw_client/paranoia.py game_delta)."""
import struct
import unittest

from botw_client import game_pace
from botw_client import paranoia as pa


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class PaceTests(unittest.TestCase):
    def lines(self, counts, delta=1.0):
        """What is logged over windows of WINDOW seconds, the cave's counter at
        each of `counts` (one count per window, the first one at the start)."""
        clock, counter = Clock(), [counts[0]]
        pace = game_pace.Pace(lambda: counter[0], lambda: delta, clock=clock)
        out = [pace.sample()]
        for count in counts[1:]:
            clock.now += game_pace.WINDOW / 2
            out.append(pace.sample())                       # within the window: nothing
            clock.now += game_pace.WINDOW / 2
            counter[0] = count & 0xFFFFFFFF
            out.append(pace.sample())
        return [line for line in out if line]

    @staticmethod
    def at(*rates, start=0):
        """The counter's values for these frames a second, window after window."""
        counts = [start]
        for rate in rates:
            counts.append(counts[-1] + int(rate * game_pace.WINDOW))
        return counts

    def test_the_first_pace_then_only_its_changes(self):
        self.assertEqual(self.lines(self.at(30, 31, 29)), [
            "game pace: 30 frames a second at a delta of x1.00: game time x1.00 of wall time"])
        self.assertEqual(len(self.lines(self.at(30, 60, 60, 30))), 3)

    def test_fps_plus_plus_and_a_turbo(self):
        # FPS++: more frames, a smaller delta, the same game time; a turbo: a faster game.
        self.assertEqual(self.lines(self.at(60), delta=0.5), [
            "game pace: 60 frames a second at a delta of x0.50: game time x1.00 of wall time"])
        self.assertIn("game time x3.00 of wall time", self.lines(self.at(90))[0])
        self.assertEqual(self.lines(self.at(30), delta=None), [
            "game pace: 30 frames a second, delta unreadable"])

    def test_a_pause_or_another_cemu_is_no_pace(self):
        self.assertEqual(self.lines(self.at(0, 0)), [])
        # Cemu restarted: its counter starts again, lower.
        self.assertEqual(self.lines([5000, 20]), [])
        # The counter wrapping around is still a pace.
        self.assertEqual(len(self.lines(self.at(30, start=0xFFFFFF00))), 1)


class DeltaTests(unittest.TestCase):
    def test_the_frame_rate_managers_delta(self):
        memory = {pa.VFR: (0x48000000).to_bytes(4, "big"),
                  0x48000000 + pa.VFR_DELTA: struct.pack(">f", 0.5)}
        self.assertEqual(pa.game_delta(lambda guest, size: memory.get(guest)), 0.5)
        memory[0x48000000 + pa.VFR_DELTA] = struct.pack(">f", 9.0)    # out of range
        self.assertIsNone(pa.game_delta(lambda guest, size: memory.get(guest)))
        memory[pa.VFR] = (0x00001000).to_bytes(4, "big")              # not a pointer to the heaps
        self.assertIsNone(pa.game_delta(lambda guest, size: memory.get(guest)))
        self.assertIsNone(pa.game_delta(lambda guest, size: None))


if __name__ == "__main__":
    unittest.main()
