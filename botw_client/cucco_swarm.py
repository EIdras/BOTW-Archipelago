"""The Cucco Swarm trap: the angry cuccos' swarm on Link, without a cucco.

In the game, a cucco hit often enough gets angry, and its AI (KokkoAngry)
brings the swarm: for a while, it creates attackers (Kokko_Simple) around its
target and gives each one that target. The trap plays that part itself, with
the game's own functions, called from the cave's per-frame invoker (read in
the Wii U EUR v208 executable, measured in lab probes 14 to 14c):

  * creation: ActorCreator::requestCreateActor (REQUEST_CREATE) with the
    ActorCreator (*CREATOR), the actor heap (*(*HEAP_HOLDER + 0x10)), a
    BaseProcHandle {unit, flag}, and an InstParamPack {u32 0; Buffer} built by
    PACK_CTOR and PACK_ADD(buffer, &position, &SafeString "@P", 0xc, 4), as the
    angry cucco's base AI builds it (0x02559078);
  * the attacker ready (HANDLE_READY), its actor (HANDLE_PROC), its AI tree at
    actor + 0x390, the variable AttackTargetActorLink found by AI_VARIABLE
    (an ActorLink, its BaseProcLink at + 4), Link's link copied into it by
    LINK_ASSIGN: {link data at player + 0x58, id at player + 0x50, 0}, as the
    angry cucco's callback does (0x026e5ffc); then the attacker let go
    (HANDLE_RELEASE);
  * the rhythm and the place of the angry cucco's parameters (Animal_Kokko_A,
    Kokko.baiprog, KokkoAngry): born in a box of CREATE_AREA half-extents
    centred BASE_OFFSET above Link, outside PROHIBITED_AREA, one every
    INTERVAL for DURATION. An attacker lives ALIVE seconds (SimpleRushAttack).

The invoker makes one call per frame and an attacker takes about eight: the
swarm is thinner than the game's (measured: 38 attackers in 10 s, from every
side, 1.5 hearts lost, no slowdown). Memory comes from the actor heap
(NEW_IN_HEAP): the plain operator new returns 0 on the invoker's thread.

The swarm lives in game time: while Link is not in the world (a menu, the
inventory, a dialogue, a loading), it creates nothing and its time stands
still. The per-frame invoker goes on in the menus: an attacker requested
there was born frozen and the whole swarm fell on Link at once when the menu
closed (seen in play). It gives up after PAUSE_LIMIT of waiting.

Each attacker is made in one turn of the invoker (`turn`, the client's
botw_client/invoker_turn.py): the client's other users of the invoker wait
for it, and none of them comes between an attacker's calls.
"""
from __future__ import annotations

from contextlib import ExitStack, nullcontext
import random
import struct
import time
from typing import Callable

NEW_IN_HEAP = 0x0308E5A0
PACK_CTOR = 0x031F9818
PACK_ADD = 0x031F9870
REQUEST_CREATE = 0x037B5E8C
HANDLE_READY = 0x0378C788
HANDLE_PROC = 0x0378C87C
HANDLE_RELEASE = 0x0378C980
AI_VARIABLE = 0x0315BCE4
LINK_ASSIGN = 0x0378DC60
CREATOR = 0x1047C2B8
HEAP_HOLDER = 0x10463F6C
PLAYER_INFO = 0x10463F38
SAFESTRING_VTABLE = 0x10263910
ATTACKER = "Kokko_Simple"
TARGET_VARIABLE = "AttackTargetActorLink"
BASE_OFFSET = (0.0, 5.5, 0.0)
CREATE_AREA = (10.0, 4.0, 10.0)
PROHIBITED_AREA = (5.0, 5.0, 5.0)
DURATION = 300 / 30                # CreateContinueTime, in frames
INTERVAL = 5 / 30                  # CreateNewActorInterval
ALIVE = 70 / 30                    # the attacker's AliveTime
PAUSE_LIMIT = 120.0                # seconds out of the world before the swarm gives up
HANDLES = 16                       # a handle whose attacker never came is never reused
MEMORY = 0x400


def birthplace(centre, rng: random.Random):
    """A point of the creation box around `centre`, outside the prohibited box."""
    while True:
        offset = tuple(rng.uniform(-a, a) for a in CREATE_AREA)
        if not all(abs(o) < p for o, p in zip(offset, PROHIBITED_AREA)):
            return tuple(c + b + o for c, b, o in zip(centre, BASE_OFFSET, offset))


class CuccoSwarm:
    """read(guest, size) -> bytes, write(guest, data), call(address, *args) -> r3 or None,
    turn() -> the context of one turn of the invoker, playing() -> Link in the world."""

    def __init__(self, read: Callable, write: Callable, call: Callable, *,
                 turn: Callable = nullcontext, playing: Callable[[], bool] = lambda: True,
                 rng: random.Random | None = None, clock=time.monotonic, sleep=time.sleep):
        self.read, self.write, self.call, self.turn = read, write, call, turn
        self.playing = playing
        self.rng = rng or random.Random()
        self.clock, self.sleep = clock, sleep

    def u32(self, guest: int) -> int | None:
        raw = self.read(guest, 4)
        return int.from_bytes(raw, "big") if raw and len(raw) == 4 else None

    def player(self) -> int | None:
        info = self.u32(PLAYER_INFO)
        return self.u32(info + 0x30) if info else None

    def link_position(self, player: int):
        raw = [self.read(player + offset, 4) for offset in (0x204, 0x214, 0x224)]
        if not all(raw) or any(len(r) != 4 for r in raw):
            return None
        return tuple(struct.unpack(">f", r)[0] for r in raw)

    def prepare(self) -> bool:
        """The swarm's memory and constants; False when the game is not ready."""
        player = self.player()
        self.creator = self.u32(CREATOR)
        holder = self.u32(HEAP_HOLDER)
        self.heap = self.u32(holder + 0x10) if holder else None
        link_data = self.u32(player + 0x58) if player else None
        link_id = self.u32(player + 0x50) if player else None
        if not (player and self.creator and self.heap and link_data):
            return False
        base = self.call(NEW_IN_HEAP, MEMORY, self.heap, 4)
        if not base:
            return False
        self.pack, self.name, key_text, self.key, self.value = (
            base, base + 0x100, base + 0x120, base + 0x130, base + 0x140)
        var_name, self.var_key, self.out, self.source = (
            base + 0x150, base + 0x170, base + 0x180, base + 0x190)
        self.handles = [base + 0x200 + 8 * index for index in range(HANDLES)]
        self.write(base, bytes(MEMORY))
        self.write(self.name, ATTACKER.encode() + b"\0")
        self.write(key_text, b"@P\0")
        self.write(self.key, struct.pack(">II", key_text, SAFESTRING_VTABLE))
        self.write(var_name, TARGET_VARIABLE.encode() + b"\0")
        self.write(self.var_key, struct.pack(">II", var_name, SAFESTRING_VTABLE))
        self.write(self.source, struct.pack(">IIB", link_data, link_id, 0))
        return True

    def attacker(self, where) -> str:
        """One attacker born at `where`: 'ok', or the step that failed."""
        if not self.handles:
            return "handles"
        handle = self.handles[0]
        self.write(self.value, struct.pack(">fff", *where))
        self.write(self.pack, bytes(4))
        self.write(handle, bytes(8))
        if self.call(PACK_CTOR, self.pack + 4) is None:
            return "busy"
        if self.call(PACK_ADD, self.pack + 4, self.value, self.key, 0xC, 4) is None:
            return "busy"
        if self.call(REQUEST_CREATE, self.creator, self.name, self.heap, handle,
                     self.pack, 0, 1) != 1:
            # Placed or not, the handle may be in use: never again.
            self.handles.pop(0)
            return "request"
        deadline = self.clock() + 1.0
        while not (self.call(HANDLE_READY, handle) or 0) & 0xFF:
            if self.clock() > deadline:
                self.handles.pop(0)
                return "ready"
        actor = self.call(HANDLE_PROC, handle)
        tree = self.u32(actor + 0x390) if actor else None
        variable = None
        if tree and self.call(AI_VARIABLE, tree, self.out, self.var_key):
            found = self.u32(self.out)
            variable = self.u32(found) if found else None
        if variable:
            self.call(LINK_ASSIGN, variable + 4, self.source)
        self.call(HANDLE_RELEASE, handle)
        return "ok" if variable else "target"

    def run(self, stop: Callable[[], bool] = lambda: False) -> dict[str, int]:
        """The whole swarm: {outcome: count}, {'not_ready': 1} when it could not start."""
        if not self.prepare():
            return {"not_ready": 1}
        results: dict[str, int] = {}
        played = waited = 0.0
        while played < DURATION and not stop():
            began = self.clock()
            try:
                in_world = bool(self.playing())
            except Exception:  # noqa: BLE001 - unreadable (loading): not in the world
                in_world = False
            if not in_world:
                if waited >= PAUSE_LIMIT:
                    results["paused"] = results.get("paused", 0) + 1
                    break
                self.sleep(INTERVAL)
                waited += self.clock() - began
                continue
            with ExitStack() as held:
                try:
                    held.enter_context(self.turn())
                except Exception:  # noqa: BLE001 - another publisher: the next one
                    outcome = "busy"
                else:
                    player = self.player()
                    centre = self.link_position(player) if player else None
                    outcome = (self.attacker(birthplace(centre, self.rng)) if centre
                               else "player")
            results[outcome] = results.get(outcome, 0) + 1
            rest = INTERVAL - (self.clock() - began)
            if rest > 0:
                self.sleep(rest)
            played += self.clock() - began
        return results
