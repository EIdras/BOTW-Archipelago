"""The sign at a closed region's border, with region_lock: the world's fog thickens over
the last START metres before the region, and the game's own « You can't go any farther. »
stays in the center of the screen from WARN metres on (inside the region as well), let go
LEAVE metres farther (asked again, the message plays its sound again), and while Link is out
of play (playing(): a menu, a dialogue, an event, a loading, or dead), whose screens close it
again and again, its sound each time (seen in play under a dialogue, and at a game over). Back
in play, or after a return, it waits SETTLE seconds: the end of a dialogue and of the return's
fade closed it again and again as well, playing() already true (seen in play). Closed by the game
while held (a window opens, the HUD is hidden), the hold stops by itself and counts it
(closures(): tools/build_center_hold_native.py); the message is then asked again only after
BACKOFF seconds, twice as long at each closure in a row up to BACKOFF_MAX, back to BACKOFF once
held STEADY seconds: each start plays its sound.

A closed region is one of the map's areas (tools/map_regions.py: one per tower, as the
game cuts its map in MapTower.sbeco) that botw_client/region_lock.py reached() leaves
out. Only in the MainField, once Link's position follows the stage: the engine names the
current map (ksys::StageInfo: type 0x1054f644, name 0x1054f670), in the MainField the
grid cell of Link's position; after a change of type, the position follows 0.45 to 1.6 s
later, at once by more than JUMP metres (measured on the type, the name and the
position, lab/journal/etude_verrou_regions.md, measure 9).

Link's position: the player actor's matrix (cucco_swarm.py reads it the same way).

The fog: the world's environment manager (ksys::world::EnvMgr, the world manager's
element 6) holds a direct fog that its setter setFogDirect (0x0364c3c0, called by the
flows' EventSetFogDirect) writes: ratio, near, far, three switches, and a timer of world
frames counted down by the manager, the game's fog back at 0. Written here as the setter
writes it, the timer HOLD frames ahead, again at every tick: the fog lapses by itself if
the client stops. It replaces the game's fog, a light one from the ramp's start (at 0, the
world cleared at once: seen in play). The message: the pack's center message hold (tools/build_center_hold_native.py),
MARGIN passes ahead at every tick, 0 when Link goes away.

With a RegionReturn (botw_client/region_return.py), Link standing in a closed region is sent
back out; the closed regions are not read again while it runs (they follow the paraglider), and
the message is let go meanwhile.
"""
from __future__ import annotations

import math
import struct
import time
from typing import Callable

from tools.build_center_hold_native import BORDER_MESSAGE
from tools.cemu.guest import in_guest

from .cucco_swarm import PLAYER_INFO

START = 30.0              # metres before a closed region where the fog begins
WARN = 10.0               # metres before it where the message shows
LEAVE = 1.5               # metres beyond WARN where it is let go
PLAY_SECONDS = 0.3        # playing() read so often near a border (the screens' catalog)
SETTLE = 1.5              # seconds in play before the message, after out of play or a return
BACKOFF = 3.0             # seconds the message is let go once the game closed it while held
BACKOFF_MAX = 24.0        # ... doubled at each closure in a row, up to so long
STEADY = 10.0             # seconds held without a closure: BACKOFF again
LIGHT = (0.1, -60.0, 500.0)   # the fog at START: ratio, near, far
WALL = (1.0, 0.0, 20.0)       # at the border and inside
HOLD = 30                 # world frames the fog's timer is written ahead
MARGIN = 30               # passes of the per-frame hook the message is asked for ahead (0.5 s at 60)
CLOSED_SECONDS = 1.0      # the closed regions are read again so often (a dozen flags)
JUMP = 50.0               # metres: the position following a change of stage
SETTLE_SECONDS = 3.0      # ... or so long after it, whatever the position does

MAP_TYPE = 0x1054F644     # ksys::StageInfo, two sead::FixedSafeString<32> buffers
MAP_NAME = 0x1054F670
MAIN_FIELD = "MainField"
WORLD_MGR = 0x1047BE88
MGR_COUNT, MGR_ARRAY, ENV_INDEX = 0x45C, 0x464, 6
FOG, FOG_TIMER = 0x3CEB0, 0x3CF0C       # ratio, near, far; the timer
SWITCHES = 0x3CF13                       # InstantSW, NearUse, FarUse (u8 each)
SET_FOG_DIRECT = 0x0364C3C0              # its code, which places these fields
SET_FOG_CODE = bytes.fromhex("3d830004 38000002 900ccf0c d42cceb0 98ac0063 98cc0065 d04c0004 "
                             "d06c0008 988c0064 4e800020")


class Areas:
    """The map's areas by region: per 2 m row of the grid, its segments (x0, x1, region)."""

    def __init__(self, grid, names: dict[int, str]):
        self.divisor, self.rows = grid.divisor, []
        for index in range(grid.rows):
            x, row = -5000, []
            for value, length in grid.row(index):
                if value in names:
                    row.append((x, x + length, names[value]))
                x += length
            self.rows.append(row)
        self.regions = frozenset(names.values())

    def _row(self, z: float) -> int:
        return int(math.floor((z + 4000) / self.divisor))

    def region_at(self, x: float, z: float) -> str | None:
        index = self._row(z)
        if 0 <= index < len(self.rows):
            for x0, x1, region in self.rows[index]:
                if x0 <= x < x1:
                    return region
        return None

    def nearest(self, x: float, z: float, regions, limit: float) -> tuple[str, float] | None:
        """(region, metres) of the nearest of `regions` within `limit`, 0 inside; None beyond."""
        best, here = None, self._row(z)
        for step in range(int(limit // self.divisor) + 2):
            for index in {here - step, here + step}:
                if not 0 <= index < len(self.rows):
                    continue
                z0 = index * self.divisor - 4000
                dz = max(z0 - z, 0.0, z - (z0 + self.divisor))
                for x0, x1, region in self.rows[index]:
                    if region in regions:
                        d = math.hypot(max(x0 - x, 0.0, x - x1), dz)
                        if d <= limit and (best is None or d < best[1]):
                            best = (region, d)
        return best


def load_areas() -> Areas:
    """The areas of the profile's update, which packs are built from (tools/cemu_profile.py)."""
    from tools import cemu_profile
    from tools.map_regions import area_regions, map_towers
    grid = map_towers(cemu_profile.update() / "content")
    return Areas(grid, area_regions(grid))


def ramp(distance: float) -> tuple[float, float, float]:
    """The fog at `distance` metres: ratio and near in a straight line, far geometrically
    (measured as even to the eye, lab/journal/etude_verrou_regions.md)."""
    t = min(1.0, max(0.0, 1.0 - distance / START))
    return (LIGHT[0] + (WALL[0] - LIGHT[0]) * t, LIGHT[1] + (WALL[1] - LIGHT[1]) * t,
            LIGHT[2] * (WALL[2] / LIGHT[2]) ** t)


def cell(position) -> str:
    """The grid cell the engine names the MainField's map after (setCurrentMapNameForFieldPos)."""
    return f"{chr((int(position[0]) + 5000) // 1000 + ord('A'))}-{chr((int(position[2]) + 4000) // 1000 + ord('1'))}"


class RegionBorder:
    """read(guest, size) -> bytes or None, write(guest, data) -> bool, hold(index, passes) ->
    bool (mailbox Cave.hold_center), closed() -> the closed regions or None (nothing shown),
    back: a RegionReturn or None, playing() -> bool Link in play and alive (None: always),
    closures() -> the hold's count of messages closed by the game, or None. tick() reads,
    decides, and writes the fog
    and the message."""

    def __init__(self, read: Callable, write: Callable, hold: Callable, areas: Areas,
                 closed: Callable, *, back=None, playing=None, closures=None, clock=time.monotonic):
        self.read, self.write, self.hold, self.areas = read, write, hold, areas
        self.back, self.playing, self.closures_source = back, playing, closures
        self.play, self.play_at = False, None
        self.settled_at, self.backoff_until = 0.0, 0.0
        self.closures, self.counted, self.backoff, self.held_since = 0, None, BACKOFF, None
        self.closed_source, self.clock = closed, clock
        self.closed, self.closed_at = None, None
        self.kind = self.settle = self.last = None
        self.fog = self.message = False
        self.code_ok = None
        self.state = {}

    def u32(self, guest: int) -> int | None:
        raw = self.read(guest, 4)
        return int.from_bytes(raw, "big") if raw and len(raw) == 4 else None

    def text(self, guest: int) -> str | None:
        raw = self.read(guest, 32)
        return raw.split(b"\0", 1)[0].decode("ascii", "replace") if raw else None

    def position(self):
        info = self.u32(PLAYER_INFO)
        player = self.u32(info + 0x30) if in_guest(info) else None
        if not in_guest(player):
            return None
        raw = [self.read(player + offset, 4) for offset in (0x204, 0x214, 0x224)]
        if not all(r and len(r) == 4 for r in raw):
            return None
        position = tuple(struct.unpack(">f", r)[0] for r in raw)
        return position if all(math.isfinite(c) and abs(c) < 10000 for c in position) else None

    def in_field(self, kind, name, position) -> bool:
        """The MainField, its position up to date: the name is Link's cell, and after a change
        of type, the position jumped or SETTLE_SECONDS passed."""
        now = self.clock()
        if kind != self.kind:
            self.kind, self.settle = kind, (self.last, now) if self.kind is not None else None
        self.last = position or self.last
        if kind != MAIN_FIELD or position is None or name != cell(position):
            return False
        if self.settle:
            before, since = self.settle
            if before is None or math.dist(before, position) > JUMP or now - since >= SETTLE_SECONDS:
                self.settle = None
        return self.settle is None

    def env(self) -> int | None:
        """The live EnvMgr, looked up at every use (a stage load may move it)."""
        if self.code_ok is None:
            code = self.read(SET_FOG_DIRECT, len(SET_FOG_CODE))
            if code is None:
                return None
            self.code_ok = code == SET_FOG_CODE
        world = self.u32(WORLD_MGR)
        if not self.code_ok or not in_guest(world) or (self.u32(world + MGR_COUNT) or 0) <= ENV_INDEX:
            return None
        array = self.u32(world + MGR_ARRAY)
        env = self.u32(array + 4 * ENV_INDEX) if in_guest(array) else None
        return env if in_guest(env) else None

    def show(self, fog, message: bool) -> None:
        """Write the fog (None: let the game's back) and ask for the message (or let it go)."""
        if fog is not None:
            env = self.env()
            self.fog = bool(env) and bool(
                self.write(env + FOG, struct.pack(">3f", *fog))
                and self.write(env + SWITCHES, bytes((0, 1, 1)))
                and self.write(env + FOG_TIMER, struct.pack(">i", HOLD)))
        elif self.fog:
            env = self.env()
            if env:
                self.write(env + FOG_TIMER, struct.pack(">i", 0))
            self.fog = False
        if message:
            self.message = bool(self.hold(BORDER_MESSAGE, MARGIN))
        elif self.message:
            self.hold(BORDER_MESSAGE, 0)
            self.message = False

    def tick(self) -> dict:
        now = self.clock()
        if (self.closed_at is None or now - self.closed_at >= CLOSED_SECONDS) and not (self.back and self.back.busy):
            self.closed, self.closed_at = self.closed_source(), now
        kind, name, position = self.text(MAP_TYPE), self.text(MAP_NAME), self.position()
        field = self.in_field(kind, name, position)
        region = self.areas.region_at(position[0], position[2]) if field else None
        nearest = None
        if field and self.closed:
            nearest = self.areas.nearest(position[0], position[2], self.closed, START)
        near = bool(nearest) and nearest[1] <= WARN + (LEAVE if self.message else 0.0)
        playing = near and self.in_play(now)
        back = self.back.tick(position, self.closed, field=field, playing=playing) if self.back else None
        self.watch(now)
        quiet = (near and not playing) or bool(self.back and self.back.hush)
        if quiet:
            self.settled_at = None
        elif self.settled_at is None:
            self.settled_at = now + SETTLE
        fog = ramp(nearest[1]) if nearest else None
        message = playing and not quiet and now >= max(self.settled_at, self.backoff_until)
        self.show(fog, message)
        self.held_since = (self.held_since or now) if self.message else None
        if self.held_since is not None and now - self.held_since >= STEADY:
            self.backoff = BACKOFF
        self.state = dict(stage=kind, map=name, field=field, position=position, region=region,
                          closed=sorted(self.closed) if self.closed is not None else None,
                          nearest=nearest, fog=fog, message=message, near=near, playing=playing,
                          closures=self.closures, backoff=self.backoff_until - now, back=back)
        return self.state

    def watch(self, now) -> None:
        """The held message closed by the game, as the hold counts it (from its first read: the
        cave keeps its count across reloads; lower, a new cave, counted from there): asked again
        after the back-off only."""
        count = self.closures_source() if self.closures_source else None
        if count is None:
            return
        if self.counted is not None and count > self.counted:
            self.closures += count - self.counted
            self.backoff_until = now + self.backoff
            self.backoff = min(self.backoff * 2, BACKOFF_MAX)
        self.counted = count

    def in_play(self, now) -> bool:
        """playing(), read again after PLAY_SECONDS; unreadable: out of play."""
        if self.playing is None:
            return True
        if self.play_at is None or now - self.play_at >= PLAY_SECONDS:
            try:
                self.play = bool(self.playing())
            except Exception:  # noqa: BLE001 - a loading: out of play
                self.play = False
            self.play_at = now
        return self.play

    def release(self) -> None:
        """The game's fog back and the message let go, at once; the return put back."""
        if self.back:
            self.back.release()
        self.show(None, False)
