"""Keep BOTW's live rune selection object in step with PlayerEquipItemType.

The game keeps the selected rune twice: in the saved GameData integer
``PlayerEquipItemType`` and in a runtime object, the singleton
``*(0x10463798)``. The object is initialised from the GameData only when the
player is created. A delivery that writes the GameData therefore leaves the
object on its previous value: the rune is owned and saved, but absent from the
HUD, the wheel and L until the player selects it in the inventory or reloads.
Measured: after a grant the object stayed at -1 while the GameData held 2; the
inventory's activation wrote the request field, and the game's per-frame
update applied it.

This module does not write the object. It asks the game to select the rune
through its own request function ``0x02A2D6D4(object, type)``, the same one the
inventory uses; the per-frame update then applies it and writes the GameData
itself. The persistent delivery transaction is not involved: if a request is
lost, reloading the save re-initialises the object from the committed value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time
import zlib

SELECTION_GLOBAL = 0x10463798
REQUEST_FUNCTION = 0x02A2D6D4
FIELDS = {"flags_4c": 0x4C, "flags_50": 0x50, "requested": 0x1D0,
          "current": 0x1D4, "previous": 0x1D8}
EQUIP_FLAG = "PlayerEquipItemType"
EQUIP_HASH = zlib.crc32(EQUIP_FLAG.encode()) & 0xFFFFFFFF
# Rune values written by delivery steps (item_map.json): Bombs 0, Magnesis 2,
# Stasis 3, Cryonis 4; 1 is the cube bomb. The Master Cycle Zero is 6 (a save
# with it in hand, 07/10), selected only when no rune is (select_if_none).
MOTORCYCLE = 6
RUNE_TYPES = frozenset(range(5)) | {MOTORCYCLE}
_HEAP = range(0x10000000, 0x50000000)


def _signed(value: int) -> int:
    return value - (1 << 32) if value & 0x80000000 else value


@dataclass(frozen=True)
class SelectionState:
    pointer: int
    requested: int
    current: int
    previous: int
    flags_4c: int
    flags_50: int

    def as_dict(self) -> dict:
        return {"pointer": hex(self.pointer), "requested_1d0": self.requested,
                "current_1d4": self.current, "previous_1d8": self.previous,
                "flags_4c": hex(self.flags_4c), "flags_50": hex(self.flags_50)}


def equip_requirement(step: dict) -> int | None:
    """The rune a delivery step selects, from its catalog mutations."""
    values = [m.get("value") for m in step.get("mutations", ())
              if m.get("kind") == "set_s32" and m.get("target") == EQUIP_FLAG]
    if not values:
        return None
    if len(values) != 1 or values[0] not in RUNE_TYPES:
        raise ValueError(f"unexpected {EQUIP_FLAG} setter in the step: {values}")
    return int(values[0])


def select_requirement(step: dict) -> int | None:
    """The rune a delivery step selects only when none is in hand (the Master
    Cycle Zero), from its catalog mutations."""
    values = [m.get("value") for m in step.get("mutations", ()) if m.get("kind") == "select_if_none"]
    if not values:
        return None
    if len(values) != 1 or values[0] not in RUNE_TYPES:
        raise ValueError(f"unexpected select_if_none in the step: {values}")
    return int(values[0])


def read_state(read_u32) -> SelectionState | None:
    """Read the object twice with ``read_u32(guest_address)``; never write.

    Returns None when the object does not exist yet (title screen, loading)
    or when two reads disagree or hold values the game never stores there.
    """
    def once():
        pointer = read_u32(SELECTION_GLOBAL)
        if pointer not in _HEAP:
            return None
        raw = {name: read_u32(pointer + offset) for name, offset in FIELDS.items()}
        return SelectionState(
            pointer, _signed(raw["requested"]), _signed(raw["current"]),
            _signed(raw["previous"]), raw["flags_4c"], raw["flags_50"])
    first = once()
    if first is None or once() != first:
        return None
    if not all(-1 <= value <= 7 for value in
               (first.requested, first.current, first.previous)):
        return None
    return first


@dataclass
class SyncOutcome:
    """What reconcile() observed and did. ``status`` values:

    ``no_rune``      GameData holds no deliverable rune; nothing to do
    ``unavailable``  object absent or unreadable; nothing requested
    ``in_sync``      object already current on the GameData value
    ``synced``       request issued (or already pending) and applied
    ``pending``      request accepted, not yet applied when the wait ended
    ``refused``      the injected request was not executed
    ``mismatch``     GameData differs from the value the caller committed
    ``kept``         select_if_none: a rune was already in hand, left there
    """
    status: str
    equip: int | None = None
    before: SelectionState | None = None
    after: SelectionState | None = None
    requested: bool = False
    detail: str = ""
    history: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in ("no_rune", "in_sync", "synced", "kept")

    def summary(self) -> str:
        text = f"rune selection {self.status}"
        if self.equip is not None:
            text += f" (type {self.equip})"
        return text + (f": {self.detail}" if self.detail else "")


class RuneSelectionSync:
    """Reconcile the live selection object with the committed GameData.

    ``read_u32(address)`` reads a big-endian guest word, ``read_equip()`` the
    GameData integer, and ``request(type)`` asks the injected code to call the
    game's request function: True when the call ran, False when the injected
    code refused it, None without an answer in time.
    """

    def __init__(self, read_u32, read_equip, request, *,
                 apply_timeout: float = 3.0, poll_seconds: float = 0.05,
                 clock=time.monotonic, sleep=time.sleep):
        self.read_u32 = read_u32
        self.read_equip = read_equip
        self.request = request
        self.apply_timeout = apply_timeout
        self.poll_seconds = poll_seconds
        self.clock = clock
        self.sleep = sleep

    def reconcile(self, expected: int | None = None) -> SyncOutcome:
        equip = self.read_equip()
        if expected is not None and equip != expected:
            # A different value means the player or the game changed it after
            # the commit: never overwrite a later choice with an older one.
            return SyncOutcome("mismatch", equip,
                               detail=f"GameData {equip}, commit {expected}")
        if equip not in RUNE_TYPES:
            return SyncOutcome("no_rune", equip)
        return self._apply(equip)

    def select_if_none(self, rune: int) -> SyncOutcome:
        """Select `rune` when the Slate has none in hand (PlayerEquipItemType
        -1), as the inventory does: the game writes the GameData itself. A rune
        in hand stays (``kept``). Measured: the Master Cycle Zero owned, nothing
        selected, the Slate had no module to use until the inventory chose it."""
        equip = self.read_equip()
        if equip != -1:
            return SyncOutcome("kept", equip)
        return self._apply(rune)

    def _apply(self, equip: int) -> SyncOutcome:
        """Have the game select `equip` and wait for its per-frame update."""
        before = read_state(self.read_u32)
        if before is None:
            return SyncOutcome("unavailable", equip, detail="selection object unreadable")
        outcome = SyncOutcome("pending", equip, before=before)
        if before.current == equip:
            outcome.status, outcome.after = "in_sync", before
            return outcome
        if before.requested != equip:
            answer = self.request(equip)
            if answer is False:
                outcome.status = "refused"
                outcome.detail = "native request refused by the injected code"
                return outcome
            # None: no answer yet; the request may still run next frame, so
            # the application below is what decides.
            outcome.requested = True
        deadline = self.clock() + self.apply_timeout
        while True:
            state = read_state(self.read_u32)
            if state is not None and (not outcome.history or outcome.history[-1] != state):
                outcome.history.append(state)
            outcome.after = state
            if state is not None and state.current == equip:
                outcome.status = "synced"
                return outcome
            if self.clock() >= deadline:
                outcome.detail = "request waiting for the game to apply it"
                return outcome
            self.sleep(self.poll_seconds)
