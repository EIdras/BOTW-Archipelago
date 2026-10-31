"""Link sent back out of a closed region, with region_lock: the game's own return of the Great
Plateau, aimed at the last safe ground he stood on outside the closed regions.

The plateau's return (measured, lab/journal/etude_verrou_regions.md): at 0x02d16eb8, with
IsGet_PlayerStole2 at 0 (no paraglider yet) and Link outside a box of .rodata (PLATEAU_BOX), the
player copies the box's destination (the clifftop of the start) into his safe ground, player
+0x1d14, then sends him there: an animation, off the bike, a fade. The safe ground is where Link
last stood, never in the water nor in the air. Here, once that safe ground lies in a closed region
with Link on it, the destination becomes the last safe ground kept outside, CLEAR metres at least
from every closed region (beyond the border's message), and the flag goes to 0 (the box emptied when Link is in it); both are put
back as soon as the safe ground holds the target, the return going on by itself. A raw write of
the flag is volatile (tools/cemu/livegdt.py): the save keeps the paraglider.

Each return costs 4 quarter hearts and kills at 4 or less: they are given in advance when it
would kill, and Link's life from before is written back once it has hit (the player actor's life,
player +0x540, of which CurrentHart is the copy). The return ends when Link is put down on the
target; the hit, just after, is still watched for COOLDOWN seconds. Meanwhile the border's message
is let go (hush): shown again through the return's fade, it would play its sound again and again.

Nothing is sent while Link is out of play (a menu, a dialogue, an event, a loading) or dead: the
engine returns no dead Link, and a game over was aimed at again and again (seen in play). With no
safe ground known outside (a save loaded in a closed region), the return goes to the clifftop of
the start, as the game's own, once Link has stood FALLBACK_SECONDS in the closed region; never when
the clifftop lies in a closed region itself.
"""
from __future__ import annotations

from collections import deque
import math
import struct
import time
from typing import Callable

from tools.cemu.guest import in_guest

from .cucco_swarm import PLAYER_INFO
from .region_border import WARN
from .travel_points import PARAGLIDER

SAFE_GROUND = 0x1D14      # player: the engine's safe ground, x, y, z
LIFE = 0x540              # player: the actor's life, s32, quarter hearts
LIFE_FLAG = "CurrentHart"
PLATEAU_BOX = 0x101E07F8  # .rodata, read at 0x02d16eec: x min, x max, z min, z max
PLATEAU_RETURN = PLATEAU_BOX + 0x10       # read at 0x02d16f3c: the return's destination
VANILLA = bytes.fromhex("c4c80000 c3af0000 44af0000 45160000 c47f6ea2 437d50b6 44e0133b")
EMPTY_BOX = struct.pack(">f", 1e30)       # as x min: every point lies outside the plateau
CLIFFTOP = struct.unpack(">3f", VANILLA[16:])    # the game's own destination
ON_GROUND = 2.5           # metres between Link and his safe ground (1.3 on a stopped bike)
NEAR = 200.0              # metres: a safe ground farther from Link is a stale read
CLEAR = WARN + 2.0        # metres at least between the target and every closed region
KEPT = 0.1                # metres between two safe grounds kept outside
HISTORY = 2000
JUMP = 50.0               # metres between two ticks: a load, never a crossing
HELD = 0.05               # metres: the engine holds the target
RETURN_SECONDS = 4.0      # the return's hold and Link put down awaited so long
ARRIVED = 2.0             # metres between Link and the target: put down
FLAG_SECONDS = 0.5        # the flag at 0 so long at most, without the hold (an instant is enough)
COOLDOWN = 1.0            # seconds after a return without a new one, its hit watched
DAMAGE = 4                # quarter hearts: what each return costs (measured 4 out of 4)
FALLBACK_SECONDS = 3.0    # Link on a closed region's ground, none known outside: the clifftop after so long


def inside_box(position) -> bool:
    x0, x1, z0, z1 = struct.unpack(">4f", VANILLA[:16])
    return x0 <= position[0] <= x1 and z0 <= position[2] <= z1


def report(state) -> str:
    """/ap-border's line on the return."""
    if not state:
        return "  return: not running"
    target = ("(" + ", ".join(f"{c:.1f}" for c in state["target"]) + ")") if state["target"] else "none"
    plateau = {True: "as the game has it", False: "UNKNOWN content, return off", None: "unread"}
    ground = state.get("ground")
    return (f"  return: {state['phase']}, {state['kept']} safe grounds kept outside, last target {target},"
            f" last result {state['result'] or 'none'}; plateau's return {plateau[state['plateau']]};"
            f" safe ground {f'in {ground[0]}, {ground[1]:.1f} m from Link' if ground else 'unread'}")


class RegionReturn:
    """read and write as region_border.RegionBorder's, get(flag, kind) the live value or None,
    set_flag(flag, value) -> bool a raw write of a bool. tick(position, closed) with Link's
    position in the MainField (None elsewhere) and the closed regions; busy while a return is
    aimed or landing: the closed regions must not be read again meanwhile (they follow the flag)."""

    def __init__(self, read: Callable, write: Callable, get: Callable, set_flag: Callable, areas,
                 *, clock=time.monotonic):
        self.read, self.write, self.get, self.set_flag = read, write, get, set_flag
        self.areas, self.clock = areas, clock
        self.outside = deque(maxlen=HISTORY)
        self.position = None
        self.vanilla = None
        self.phase, self.until = "idle", 0.0
        self.lowered = self.aimed = False
        self.target = self.before = self.expected = None
        self.region, self.fallback, self.lost_since = None, False, None
        self.started = 0.0
        self.held = self.hit = self.landed = False
        self.result = None
        self.unsent, self.missed = {}, (0, {})  # Link in a closed region, no return: why, in ticks
        self.state = {}

    @property
    def busy(self) -> bool:
        return self.phase in ("aimed", "landing")

    @property
    def hush(self) -> bool:
        """A return under way or just over: the border's message let go."""
        return self.busy or self.landed

    def u32(self, guest: int) -> int | None:
        raw = self.read(guest, 4)
        return int.from_bytes(raw, "big") if raw and len(raw) == 4 else None

    def player(self) -> int | None:
        info = self.u32(PLAYER_INFO)
        player = self.u32(info + 0x30) if in_guest(info) else None
        return player if in_guest(player) else None

    def ground(self, player):
        raw = self.read(player + SAFE_GROUND, 12) if player else None
        if not raw or len(raw) != 12:
            return None
        ground = struct.unpack(">3f", raw)
        return ground if all(math.isfinite(c) and abs(c) < 10000 for c in ground) else None

    def life(self, player) -> int | None:
        """The actor's life, when CurrentHart agrees (else the offset is not the one measured)."""
        raw = self.read(player + LIFE, 4) if player else None
        if not raw or len(raw) != 4:
            return None
        life = struct.unpack(">i", raw)[0]
        return life if life == self.get(LIFE_FLAG, "s32") else None

    def repair(self) -> bool | None:
        """The plateau's return as the game has it; left aimed by a client that stopped, put back.
        False for any other content (another executable): nothing is written then; None unread."""
        raw = self.read(PLATEAU_BOX, len(VANILLA))
        if raw is None:
            return None
        if raw == VANILLA:
            return True
        if raw[4:16] == VANILLA[4:16] and raw[:4] in (VANILLA[:4], EMPTY_BOX):
            return bool(self.write(PLATEAU_BOX, VANILLA))
        return False

    def put_back(self) -> None:
        """The flag first, then the box and its destination once the flag is back: while it is
        low, a return lands on the target, not on the clifftop."""
        if self.lowered and self.set_flag(PARAGLIDER, 1):
            self.lowered = False
        if self.aimed and not self.lowered and self.write(PLATEAU_BOX, VANILLA):
            self.aimed = False

    def track(self, position, ground, closed) -> None:
        if position is None or (self.position and math.dist(self.position, position) > JUMP):
            self.outside.clear()
        self.position = position
        if ground and self.areas.region_at(ground[0], ground[2]) not in (closed or ()):
            if not self.outside or math.dist(self.outside[-1], ground) > KEPT:
                self.outside.append(ground)

    def clearance(self, point, closed) -> float:
        """Metres between `point` and the nearest closed region, CLEAR at most."""
        nearest = self.areas.nearest(point[0], point[2], closed, CLEAR)
        return nearest[1] if nearest else CLEAR

    def choose(self, closed):
        """The last safe ground kept CLEAR metres from every closed region, else the clearest."""
        kept = [p for p in self.outside if self.areas.region_at(p[0], p[2]) not in closed]
        target = next((p for p in reversed(kept) if self.clearance(p, closed) >= CLEAR), None)
        return target or (max(kept, key=lambda p: self.clearance(p, closed)) if kept else None)

    def send(self, now, player, position, region, closed) -> None:
        self.target, self.fallback = self.choose(closed), False
        if self.target is None:
            if self.lost_since is None:
                self.lost_since = now
            if (now - self.lost_since < FALLBACK_SECONDS
                    or self.areas.region_at(CLIFFTOP[0], CLIFFTOP[2]) in closed):
                self.result = "waiting: no safe ground known outside"
                return
            self.target, self.fallback = CLIFFTOP, True
        self.before = self.life(player)
        if self.before is None or self.before <= 0:
            self.target, self.result = None, ("waiting: Link dead" if self.before is not None
                                              else "waiting: life unread or not CurrentHart's")
            return                      # read again at the next tick
        self.region, self.lost_since = region, None
        self.expected = self.before + DAMAGE if 0 < self.before <= DAMAGE else self.before
        if self.expected != self.before and not self.write(player + LIFE, struct.pack(">i", self.expected)):
            self.finish(now, "life not written")
            return
        self.started, self.held, self.hit, self.landed = now, False, False, False
        self.aimed = True
        if (self.write(PLATEAU_RETURN, struct.pack(">3f", *self.target))
                and (not inside_box(position) or self.write(PLATEAU_BOX, EMPTY_BOX))
                and self.set_flag(PARAGLIDER, 0)):
            self.lowered = True
            self.phase = "aimed"
        else:
            self.put_back()
            self.give_back(player)
            self.finish(now, "write refused")

    def give_back(self, player) -> None:
        """Link's life from before, after the return's damage or in place of the advance; never to
        a dead Link, nor the advance to a life the game has changed since (a death, a respawn)."""
        if not (player and self.before is not None and (self.hit or self.expected != self.before)):
            return
        raw = self.read(player + LIFE, 4)
        life = struct.unpack(">i", raw)[0] if raw and len(raw) == 4 else None
        if life is not None and life > 0 and (self.hit or life == self.expected):
            self.write(player + LIFE, struct.pack(">i", self.before))

    def finish(self, now, result) -> None:
        self.result = result
        self.phase, self.until = "cooldown", now + COOLDOWN

    def watch(self, player) -> None:
        """The return's hit (DAMAGE at least, after the hold): Link's life from before, at once."""
        life = self.read(player + LIFE, 4) if player and self.held and not self.hit else None
        if life and len(life) == 4 and struct.unpack(">i", life)[0] <= self.expected - DAMAGE:
            self.hit = True
            self.give_back(player)

    def follow(self, now, player, position, ground) -> None:
        """The return aimed: the flag back once the engine holds the target (or after
        FLAG_SECONDS), over once Link is put down on it."""
        if not self.held and ground and math.dist(ground, self.target) < HELD:
            self.held = True
            self.phase = "landing"
        if self.held or now - self.started >= FLAG_SECONDS:
            self.put_back()
        self.watch(player)
        if self.held and (self.hit or (position and math.dist(position, self.target) < ARRIVED)):
            self.landed = True
            self.finish(now, "returned")
        elif now - self.started >= RETURN_SECONDS:
            self.put_back()
            if not self.hit:
                self.give_back(player)
            self.finish(now, "not put down" if self.held else "no return")

    def tick(self, position, closed, *, field=True, playing=True) -> dict:
        """position: Link's, read at every tick; field: it is the MainField's, up to date;
        playing: Link in play and alive (no return sent otherwise)."""
        now = self.clock()
        if self.vanilla is None:
            self.vanilla = self.repair()
        player = self.player()
        ground = self.ground(player)
        if self.busy:
            self.follow(now, player, position, ground)
        else:
            self.put_back()                     # a write refused before: again
            if self.landed:
                self.watch(player)
            if self.phase == "cooldown" and now >= self.until:
                if self.landed and not self.hit:
                    self.give_back(player)      # the advance, no hit seen
                self.phase, self.landed = "idle", False
        position = position if field else None
        if not (position and ground and math.dist(ground, position) < NEAR):
            ground = None
        self.track(position, ground, closed)
        where = self.areas.region_at(ground[0], ground[2]) if ground else None
        if (self.phase == "idle" and self.vanilla and closed and where in closed and playing
                and math.dist(ground, position) < ON_GROUND):
            if self.get(PARAGLIDER, "bool") != 1:
                self.result = "waiting: no paraglider (the game's own return)"
            elif self.lowered or self.aimed or self.read(PLATEAU_BOX, len(VANILLA)) != VANILLA:
                self.result = "waiting: the plateau's return not as the game has it"
            else:
                self.send(now, player, position, where, closed)
        elif not self.busy:
            self.lost_since = None              # the clifftop only after so long on end
        self.miss(position, ground, closed, playing)
        self.state = dict(phase=self.phase, kept=len(self.outside), target=self.target,
                          result=self.result, plateau=self.vanilla, missed=self.missed,
                          ground=(where, math.dist(ground, position)) if ground else None,
                          region=self.region, fallback=self.fallback)
        return self.state

    def miss(self, position, ground, closed, playing=True) -> None:
        """Link in a closed region and no return: why, counted until he leaves or one is sent."""
        inside = bool(closed) and position and self.areas.region_at(position[0], position[2]) in closed
        if inside and not self.busy:
            if self.phase == "cooldown":
                why = "cooldown"
            elif not playing:
                why = "out of play or dead"
            elif ground is None:
                why = "safe ground unread"
            elif self.areas.region_at(ground[0], ground[2]) not in closed:
                why = "safe ground outside"
            elif math.dist(ground, position) >= ON_GROUND:
                why = "Link off his safe ground"
            else:
                why = self.result or "waiting"
            self.unsent[why] = self.unsent.get(why, 0) + 1
        elif self.unsent:
            self.missed, self.unsent = (self.missed[0] + 1, self.unsent), {}

    def release(self) -> None:
        """The flag and the plateau's return as the game has them, at once."""
        self.put_back()
        if self.busy:
            self.phase = "idle"
