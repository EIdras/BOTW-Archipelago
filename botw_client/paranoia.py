"""The Paranoia trap: a Guardian takes aim at Link, and is gone before it fires.

A Decayed Guardian (Enemy_Guardian_A_Fixed_Moss) is created DISTANCE behind Link,
turned towards him: the game's own Guardian sees him at once, beeps, plays its
music and points its red laser at him. Before its shot, the client deletes it:
it vanishes, its music fades out. Measured in the lab (probes 19d to 19f,
11-12/10): it fires about 7.1 s after its waking; deleted at 7.1 s, it had just
begun to fire and the shot never left; here, at LIFETIME.

What the client calls, from the cave's per-frame invoker (read in the Wii U EUR
v208 executable, as zeldaret/botw has them):

  * the creation of the Cucco Swarm's attackers (botw_client/cucco_swarm.py),
    with a handle and an InstParamPack holding the place (@P) and the rotation
    (@R: a Vec3 of 0xc bytes, type 4, in radians, as the game's own creations
    add it, 0x02a03a6c; read back: its +Z is (sin yaw, 0, cos yaw));
  * the handle ready (HANDLE_READY), the proc (HANDLE_PROC), woken
    (BaseProc::wakeUp, WAKE): created with a handle, it sleeps until then;
  * the deletion: BaseProc::deleteLater(proc, 2) (DELETE_LATER). Not through the
    handle: within 2 s of the wake, the game itself unlinks the handle's unit
    (measured), and BaseProcHandle::deleteProc then deletes nothing (seen: the
    Guardian stayed and fired again and again). The proc is named by its own
    link instead, as the swarm names Link: its id (+ LINK_ID) and its
    BaseProcLinkData (+ LINK_DATA), which holds the id followed by the proc while
    the proc lives, and is reused under another id once it is gone (measured:
    still valid 0.4 s after the deletion, reused at 1 s). The proc is deleted
    only while its link data still holds it.

A Guardian whose link cannot be found is deleted through its handle before its
wake, while the unit still holds it: it never wakes. A Guardian that is gone
before its time (defeated, or its area unloaded) is left alone. When the client
stops, or Link dies, the Guardian is deleted at once.

LIFETIME is the Guardian's own time, the game's: the cave's frame counter
(`frames`) times the game's delta per frame, in frames of 1/30 s, read from its
frame-rate manager (*VFR + VFR_DELTA: frames between two vsyncs over the
nominal, as it computes it at 0x037932f0; 30/fps under FPS++, which writes
there). A game paced on a faster vsync (a turbo) runs faster at a delta of 1:
the Guardian, measured in wall time, fired again and again there (seen in
play, at about 90 frames a second). The wall clock stays a ceiling: whichever
comes first deletes it, so a Guardian slowed down (a struggling emulator) or a
delta misread is deleted early, never late. The outcome says what was measured.

Each step is one turn of the invoker (botw_client/invoker_turn.py); the client
holds its other events for the Guardian's few seconds, as for the swarm.
"""
from __future__ import annotations

from contextlib import nullcontext
import math
import struct
import time
from typing import Callable

from tools.cemu.guest import in_heap

from .cucco_swarm import (CREATOR, HEAP_HOLDER, NEW_IN_HEAP, PACK_ADD, PACK_CTOR, PLAYER_INFO,
                          REQUEST_CREATE, SAFESTRING_VTABLE)

GUARDIAN = "Enemy_Guardian_A_Fixed_Moss"
# Metres behind Link: at 25 m (lab probes), a Guardian once stood in a wall and never saw him
# (seen in play, 13/10); nearer, a wall behind him is less likely.
DISTANCE = 15.0
LIFETIME = 6.9                  # seconds of game time from its waking to its deletion (it fires at about 7.1)
READY_LIMIT = 10.0              # seconds for the game to create it
PAUSE_LIMIT = 120.0             # seconds out of the world before the trap gives up
HANDLE_READY = 0x0378C788
HANDLE_PROC = 0x0378C87C
HANDLE_DELETE = 0x0378C734
WAKE = 0x0378A540
DELETE_LATER = 0x0378A374
LINK_ID, LINK_DATA = 0x50, 0x58
LINK_WORDS = 24                 # where the link data's id and proc are looked for
VFR, VFR_DELTA = 0x1047C258, 0x1C   # the frame-rate manager (as 0x02dae85c loads it) and its delta
DELTA_RANGE = (0.1, 4.0)        # a delta outside it is taken for unreadable (then 1)
FRAME_RATE = 30.0
POLL = 0.05
POSITION, FORWARD = 0x204, 0x200    # Link's matrix: place and +Z (x; y, z every 0x10)
MEMORY = 0x200
# The block's layout: the InstParamPack's room first (the game builds it over
# whatever lies there), then the name, the two keys and their values, the handle.
NAME, P_TEXT, P_KEY, P_VALUE, HANDLE = 0x100, 0x140, 0x150, 0x160, 0x180
R_TEXT, R_KEY, R_VALUE = 0x1A0, 0x1B0, 0x1C0


def game_delta(read: Callable) -> float | None:
    """The game's delta per frame, in frames of 1/30 s, or None (unreadable):
    read(guest, size) -> bytes."""
    raw = read(VFR, 4)
    vfr = int.from_bytes(raw, "big") if raw and len(raw) == 4 else None
    raw = read(vfr + VFR_DELTA, 4) if in_heap(vfr) else None
    if not raw or len(raw) != 4:
        return None
    value = struct.unpack(">f", raw)[0]
    return value if DELTA_RANGE[0] <= value <= DELTA_RANGE[1] else None


def behind(position, forward, distance: float = DISTANCE):
    """The place `distance` behind Link, and the yaw that turns its +Z to him."""
    norm = math.hypot(forward[0], forward[2]) or 1.0
    dx, dz = forward[0] / norm, forward[2] / norm
    where = (position[0] - distance * dx, position[1], position[2] - distance * dz)
    return where, math.atan2(dx, dz)


class Paranoia:
    """read(guest, size) -> bytes, write(guest, data), call(address, *args) -> r3 or
    None, turn() -> the context of one turn of the invoker, playing() -> Link in
    the world; as the swarm's."""

    def __init__(self, read: Callable, write: Callable, call: Callable, *,
                 turn: Callable = nullcontext, playing: Callable[[], bool] = lambda: True,
                 frames: Callable[[], int] | None = None, clock=time.monotonic, sleep=time.sleep):
        """frames() -> the cave's frame counter (none: the wall clock alone)."""
        self.read, self.write, self.call, self.turn = read, write, call, turn
        self.playing, self.frames, self.clock, self.sleep = playing, frames, clock, sleep

    def u32(self, guest: int) -> int | None:
        raw = self.read(guest, 4)
        return int.from_bytes(raw, "big") if raw and len(raw) == 4 else None

    def vector(self, address: int):
        raw = [self.read(address + 0x10 * axis, 4) for axis in range(3)]
        if not all(raw) or any(len(r) != 4 for r in raw):
            return None
        return tuple(struct.unpack(">f", r)[0] for r in raw)

    def in_turn(self, work, *, patience: float = 2.0):
        """work() in one turn of the invoker, asked again while the invoker is busy."""
        deadline = self.clock() + patience
        while True:
            try:
                with self.turn():
                    return work()
            except Exception:  # noqa: BLE001 - another publisher: once more
                if self.clock() > deadline:
                    raise
                self.sleep(0.02)

    def wait_for_world(self, stop) -> bool:
        waited = 0.0
        while not stop():
            try:
                if self.playing():
                    return True
            except Exception:  # noqa: BLE001 - unreadable (a loading): not in the world
                pass
            if waited >= PAUSE_LIMIT:
                return False
            self.sleep(0.1)
            waited += 0.1
        return False

    def create(self) -> tuple[str, int | None]:
        """The Guardian requested behind Link: ('ok', handle) or (why not, None)."""
        info = self.u32(PLAYER_INFO)
        player = self.u32(info + 0x30) if info else None
        position = self.vector(player + POSITION) if player else None
        forward = self.vector(player + FORWARD) if player else None
        creator, holder = self.u32(CREATOR), self.u32(HEAP_HOLDER)
        heap = self.u32(holder + 0x10) if holder else None
        if not (position and forward and creator and heap):
            return "player", None
        base = self.call(NEW_IN_HEAP, MEMORY, heap, 4)
        if not base:
            return "memory", None
        where, yaw = behind(position, forward)
        self.write(base, bytes(MEMORY))
        self.write(base + NAME, GUARDIAN.encode("ascii") + b"\0")
        for text, key, value, data in ((P_TEXT, P_KEY, P_VALUE, where), (R_TEXT, R_KEY, R_VALUE, (0.0, yaw, 0.0))):
            self.write(base + text, (b"@P" if text == P_TEXT else b"@R") + b"\0")
            self.write(base + key, struct.pack(">II", base + text, SAFESTRING_VTABLE))
            self.write(base + value, struct.pack(">fff", *data))
        if self.call(PACK_CTOR, base + 4) is None:
            return "busy (pack)", None
        for key, value in ((P_KEY, P_VALUE), (R_KEY, R_VALUE)):
            if self.call(PACK_ADD, base + 4, base + value, base + key, 0xC, 4) is None:
                return "busy (place)", None
        handle = base + HANDLE
        if self.call(REQUEST_CREATE, creator, base + NAME, heap, handle, base, 0, 1) != 1:
            return "request", None
        return "ok", handle

    def link(self, proc: int) -> tuple[int, int] | None:
        """(id, address of the id in the link data, the proc right after it), or None."""
        ident, data = self.u32(proc + LINK_ID), self.u32(proc + LINK_DATA)
        if ident is None or not data:
            return None
        for index in range(LINK_WORDS - 1):
            at = data + 4 * index
            if self.u32(at) == ident and self.u32(at + 4) == proc:
                return ident, at
        return None

    def delta(self) -> float | None:
        """The game's delta per frame, in frames of 1/30 s, or None."""
        return game_delta(self.read)

    def frame(self) -> int | None:
        try:
            return int(self.frames()) if self.frames else None
        except Exception:  # noqa: BLE001 - unreadable: no game time this poll
            return None

    def live(self, stop) -> str:
        """LIFETIME of game time or of wall time, whichever first (or a stop):
        what was measured."""
        started, game, frames, weighted, misread = self.clock(), 0.0, 0, 0.0, 0
        last = self.frame()
        while not stop():
            self.sleep(POLL)
            now = self.frame()
            if last is not None and now is not None:
                step = (now - last) & 0xFFFFFFFF
                if step < 0x10000:              # a counter that went back: not counted
                    delta = self.delta()
                    if delta is None:
                        misread += 1
                        delta = 1.0
                    game += step * delta / FRAME_RATE
                    frames += step
                    weighted += step * delta
            last = now
            if game >= LIFETIME or self.clock() - started >= LIFETIME:
                break
        speed = f"x{weighted / frames:.2f}" if frames else "unknown"
        return (f"{game:.1f} s of game time ({frames} frames, speed {speed}"
                + (f", delta unreadable {misread} times" if misread else "")
                + f"), {self.clock() - started:.1f} s of wall time")

    def linked(self, proc: int, link: tuple[int, int]) -> bool:
        ident, at = link
        return self.u32(at) == ident and self.u32(at + 4) == proc

    def run(self, stop: Callable[[], bool] = lambda: False,
            struck: Callable[[], None] = lambda: None) -> str:
        """The whole trap: 'deleted' or 'gone' (before its time) after what was
        measured of its time, or why it did not play. struck() once it is
        woken: it takes aim at Link."""
        if not self.wait_for_world(stop):
            return "not in the world"
        outcome, handle = self.in_turn(self.create)
        if handle is None:
            return outcome
        deadline = self.clock() + READY_LIMIT
        while not (self.in_turn(lambda: self.call(HANDLE_READY, handle)) or 0) & 0xFF:
            if self.clock() > deadline or stop():
                # Never woken: the handle's unit still holds it.
                self.in_turn(lambda: self.call(HANDLE_DELETE, handle))
                return "not ready"
            self.sleep(0.02)

        def wake():
            proc = self.call(HANDLE_PROC, handle)
            link = self.link(proc) if proc else None
            if link is None:
                self.call(HANDLE_DELETE, handle)
                return proc, None
            self.call(WAKE, proc, 0)
            return proc, link
        proc, link = self.in_turn(wake)
        if link is None:
            return "no link"
        struck()
        measured = self.live(stop)

        def delete():
            if not self.linked(proc, link):
                return "gone"
            return "deleted" if self.call(DELETE_LATER, proc, 2) == 1 else "refused"
        return f"{self.in_turn(delete, patience=5.0)} after {measured}"
