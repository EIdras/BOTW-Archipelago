"""The sign at a closed region's border, with region_lock: the world's fog thickens over
the last START metres before the region, and the game's own « You can't go any farther. »
stays in the center of the screen from WARN metres on (inside the region as well).

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
the client stops. It replaces the game's fog (a small step at the ramp's start, left as
it is). The message: the pack's center message hold (tools/build_center_hold_native.py),
MARGIN passes ahead at every tick, 0 when Link goes away.
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
LIGHT = (0.0, -60.0, 500.0)   # the fog at START: ratio, near, far
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
    bool (mailbox Cave.hold_center), closed() -> the closed regions or None (nothing shown).
    tick() reads, decides, and writes the fog and the message."""

    def __init__(self, read: Callable, write: Callable, hold: Callable, areas: Areas,
                 closed: Callable, *, clock=time.monotonic):
        self.read, self.write, self.hold, self.areas = read, write, hold, areas
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
        if self.closed_at is None or now - self.closed_at >= CLOSED_SECONDS:
            self.closed, self.closed_at = self.closed_source(), now
        kind, name, position = self.text(MAP_TYPE), self.text(MAP_NAME), self.position()
        field = self.in_field(kind, name, position)
        region = self.areas.region_at(position[0], position[2]) if field else None
        nearest = None
        if field and self.closed:
            nearest = self.areas.nearest(position[0], position[2], self.closed, START)
        fog = ramp(nearest[1]) if nearest else None
        message = bool(nearest) and nearest[1] <= WARN
        self.show(fog, message)
        self.state = dict(stage=kind, map=name, field=field, position=position, region=region,
                          closed=sorted(self.closed) if self.closed is not None else None,
                          nearest=nearest, fog=fog, message=message)
        return self.state

    def release(self) -> None:
        """The game's fog back and the message let go, at once."""
        self.show(None, False)
