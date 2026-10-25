"""The game's pace, for the session's log: its frames a second (the cave's
counter over the wall clock) and its delta per frame, the game's own time in
frames of 1/30 s (botw_client/paranoia.py game_delta()). The console runs 30
frames a second at x1.00; FPS++ runs more frames at a smaller delta (30/fps),
the same game time; a vsync faster than the console's (a turbo), more frames
at x1.00: a faster game. The client's waits counted in frames depend on it."""
from __future__ import annotations

import time
from typing import Callable

from .paranoia import FRAME_RATE

WINDOW = 10.0           # seconds of wall time per measure
CHANGE = 0.2            # frames a second that moved by a fifth: logged again
DELTA_CHANGE = 0.1


class Pace:
    """sample() at each turn of the client's loop: a line for the log when the
    pace is first measured or has changed, else None. frames() -> the cave's
    counter, delta() -> the game's delta or None (unreadable)."""

    def __init__(self, frames: Callable[[], int], delta: Callable[[], float | None],
                 clock=time.monotonic):
        self.frames, self.delta, self.clock = frames, delta, clock
        self.start: tuple[float, int] | None = None
        self.logged: tuple[float, float | None] | None = None

    def sample(self) -> str | None:
        now, frame = self.clock(), int(self.frames())
        if self.start is None:
            self.start = (now, frame)
            return None
        began, first = self.start
        if now - began < WINDOW:
            return None
        self.start = (now, frame)
        step = (frame - first) & 0xFFFFFFFF
        if not step or step >= 0x10000:     # paused, or a new counter (another Cemu)
            return None
        rate, delta = step / (now - began), self.delta()
        if self.logged is not None:
            rate_before, delta_before = self.logged
            if (abs(rate - rate_before) <= CHANGE * rate_before
                    and (delta is None) == (delta_before is None)
                    and (delta is None or abs(delta - delta_before) <= DELTA_CHANGE)):
                return None
        self.logged = (rate, delta)
        if delta is None:
            return f"game pace: {rate:.0f} frames a second, delta unreadable"
        return (f"game pace: {rate:.0f} frames a second at a delta of x{delta:.2f}: "
                f"game time x{rate * delta / FRAME_RATE:.2f} of wall time")
