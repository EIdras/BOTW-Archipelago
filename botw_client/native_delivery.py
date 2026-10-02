"""Cemu backend for generated, transaction-safe deliveries."""
from __future__ import annotations

from contextlib import nullcontext
import json
from pathlib import Path
import time
import zlib

from .backend import (
    BackendContractError,
    DeliveryCheckpoint,
    DeliveryCommand,
    DeliveryResult,
    DeliveryStatus,
)
from .rune_selection import equip_requirement


ROOT = Path(__file__).resolve().parent.parent
VERIFIED_BUILD = "8113c2ef27302dd8"
DEFAULT_CATALOG = (ROOT / ".build" / "ledger-validation" / VERIFIED_BUILD
                   / "delivery_catalog.json")
CURSOR_HASH = zlib.crc32(b"APReceivedCursor") & 0xFFFFFFFF
TOKEN_HASH = zlib.crc32(b"APSeedToken") & 0xFFFFFFFF
REJECT_HASH = zlib.crc32(b"APDeliveryRejectCounter") & 0xFFFFFFFF
GUARD_HASH = zlib.crc32(b"SaveProhibition") & 0xFFFFFFFF
# Frames left to the event that just committed to close. Its commit comes
# before GuardOFF and the event's own teardown; a request placed meanwhile was
# accepted and never ran (a step requested one frame after the previous commit).
SETTLE_FRAMES = 30


class NativeDeliveryCatalog:
    """Resolve one AP item/sub-step to an immutable generated EventFlow entry."""

    def __init__(self, source=DEFAULT_CATALOG):
        self.path = Path(source)
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"native catalog unreadable ({self.path}): {exc}") from exc
        if (self.data.get("schema") != 1 or self.data.get("cursor") !=
                "(received_index << 8) | step" or not self.data.get("flow")
                or not isinstance(self.data.get("items"), dict)):
            raise ValueError("unknown native catalog format")
        binding = self.data.get("binding")
        if binding is not None and (
                not isinstance(binding, dict)
                or not binding.get("entry")
                or not isinstance(binding.get("seed_token"), int)
                or not 0 < binding["seed_token"] <= 0x7FFFFFFF
                or binding.get("requires_cursor") != 0
                or binding.get("requires_token") != 0):
            raise ValueError("inconsistent native binding metadata")

    def binding(self) -> dict | None:
        value = self.data.get("binding")
        return dict(value) if value is not None else None

    def status_entry(self) -> str | None:
        """The seed pack's Archipelago key item entry (botw_patch/status_item.py)."""
        value = self.data.get("status_item")
        return str(value["entry"]) if isinstance(value, dict) and value.get("entry") else None

    def death_link_entry(self) -> tuple[str, str] | None:
        """(flow, entry) of the pack's DeathLink entry (botw_patch/death_link.py)."""
        value = self.data.get("death_link")
        if not isinstance(value, dict) or not value.get("entry") or not value.get("flow"):
            return None
        return str(value["flow"]), str(value["entry"])

    def death_link_flag(self) -> str | None:
        """The volatile flag the DeathLink entry leaves set on the deaths it causes."""
        value = self.data.get("death_link")
        return str(value["flag"]) if isinstance(value, dict) and value.get("flag") else None

    def attacker_names(self) -> dict[str, str]:
        """{actor: English name} of what can kill Link, from the player's game files."""
        value = self.data.get("death_link")
        names = value.get("attackers") if isinstance(value, dict) else None
        return {str(k): str(v) for k, v in names.items()} if isinstance(names, dict) else {}

    def steps(self, item_name: str, received_before: int = 0) -> list[dict]:
        item = self.data["items"].get(item_name)
        if item is None:
            reason = self.data.get("unsupported", {}).get(item_name,
                                                           "item missing from the catalog")
            raise KeyError(f"{item_name}: {reason}")
        variants = item.get("variants", {})
        if "default" in variants:
            selected = variants["default"]
        else:
            tiers = sorted(int(key) for key in variants)
            if not tiers:
                raise ValueError(f"{item_name}: no native variant")
            selected = variants[str(min(received_before, tiers[-1]))]
        if not isinstance(selected, list) or not selected:
            raise ValueError(f"{item_name}: empty native plan")
        count = len(selected)
        for number, step in enumerate(selected):
            if (step.get("step") != number or step.get("step_count") != count
                    or not step.get("entry") or not step.get("mutations")):
                raise ValueError(f"{item_name}: inconsistent step metadata")
        return selected

    def resolve(self, command: DeliveryCommand) -> tuple[str, dict]:
        steps = self.steps(command.item_name, command.received_before)
        if command.step_count != len(steps) or command.step >= len(steps):
            raise BackendContractError(
                f"{command.item_name}: command {command.step}/{command.step_count}, "
                f"catalog {len(steps)} steps")
        step = steps[command.step]
        if int(step.get("cursor_delta", -1)) != command.next_cursor - command.cursor:
            raise BackendContractError(
                f"{command.item_name}: invalid catalog cursor delta")
        return str(self.data["flow"]), step


class CemuNativeDeliveryBackend:
    """Submit exactly once, then derive the outcome from BOTW's live ledger.

    A seed-specific catalog may bind a zero ledger through a guarded native
    EventFlow setter. Foreign tokens are always refused.
    """

    def __init__(self, game, seed: str, slot: int, token: int, *,
                 catalog=DEFAULT_CATALOG, request=None, lock_factory=None,
                 commit_timeout: float = 30.0, poll_seconds: float = 0.05,
                 safe=None):
        if not seed or not isinstance(slot, int) or not 0 < token <= 0x7FFFFFFF:
            raise ValueError("invalid native AP identity")
        self.game = game
        self.seed = seed
        self.slot = slot
        self.token = token
        self.catalog = (catalog if isinstance(catalog, NativeDeliveryCatalog)
                        else NativeDeliveryCatalog(catalog))
        self._request = request
        self._lock_factory = lock_factory
        self.commit_timeout = commit_timeout
        self.poll_seconds = poll_seconds
        self._safe = safe
        self._committed_at = None

    def _frame(self):
        tick = getattr(self.game, "frame_tick", None)
        try:
            return int(tick()) if tick else None
        except Exception:  # noqa: BLE001 - unreadable counter: no settle known
            return None

    def _frames_since_commit(self):
        now = self._frame()
        if self._committed_at is None or now is None:
            return None
        return (now - self._committed_at) & 0xFFFFFFFF

    def _read_s32(self, hash_u32: int) -> int:
        live = getattr(self.game, "live", None)
        if live is None:
            raise RuntimeError("live GameData unavailable")
        value = live.get(hash_u32, "s32")
        if value is None:
            raise RuntimeError(f"native s32 flag not found ({hash_u32:08x})")
        return int(value)

    def _state(self) -> tuple[int, int, int]:
        return (self._read_s32(TOKEN_HASH), self._read_s32(CURSOR_HASH),
                self._read_s32(REJECT_HASH))

    def _guard(self) -> bool:
        live = getattr(self.game, "live", None)
        if live is None:
            raise RuntimeError("live GameData unavailable")
        value = live.get(GUARD_HASH, "bool")
        if value is None:
            raise RuntimeError("native save guard not found")
        return bool(value)

    def checkpoint(self) -> DeliveryCheckpoint:
        token, cursor, _ = self._state()
        binding = self.catalog.binding()
        if binding is not None and binding["seed_token"] != self.token:
            return DeliveryCheckpoint(f"catalog:{binding['seed_token']}", -1, cursor)
        if token == self.token:
            return DeliveryCheckpoint(self.seed, self.slot, cursor)
        return DeliveryCheckpoint(f"token:{token}", -1, cursor)

    def checked_locations(self) -> set[int]:
        return set()

    def _ready(self) -> bool:
        predicate = self._safe or getattr(self.game, "safe_for_delivery", None)
        try:
            return bool(predicate and predicate())
        except Exception:
            return False

    def _dependencies(self):
        request = self._request
        lock_factory = self._lock_factory
        if request is None:
            from tools.cemu.autonomous_eventflow import request
        if lock_factory is None:
            from .invoker_turn import publisher_turn
            lock_factory = publisher_turn
        return request, lock_factory

    def bind_session(self) -> DeliveryResult:
        """Persistently bind an untouched zero ledger to this AP identity."""
        token, cursor, _ = self._state()
        binding = self.catalog.binding()
        if binding is not None and binding["seed_token"] != self.token:
            return DeliveryResult(
                DeliveryStatus.SESSION_MISMATCH, cursor,
                f"catalog built for {binding['seed_token']}, token {self.token}")
        if token == self.token:
            return DeliveryResult(DeliveryStatus.ALREADY_APPLIED, cursor)
        if token != 0 or cursor != 0:
            return DeliveryResult(
                DeliveryStatus.SESSION_MISMATCH, cursor,
                f"BOTW ledger {token}/{cursor}; binding requires 0/0")
        if binding is None:
            return DeliveryResult(
                DeliveryStatus.SESSION_MISMATCH, cursor,
                "catalog without a native binding entry")
        if not self._ready():
            return DeliveryResult(
                DeliveryStatus.DEFERRED, cursor,
                getattr(self.game, "delivery_block_reason", "game busy"))

        request, lock_factory = self._dependencies()
        evidence = {}
        try:
            pid = int(self.game.process.pid)
            lock = lock_factory(pid) if lock_factory else nullcontext()
            with lock:
                try:
                    result = request(
                        self.game.process, self.game.cave, 0,
                        lambda value: evidence.update(value), custom_text=False,
                        flow=self.catalog.data["flow"], entry=binding["entry"])
                except Exception:
                    if evidence.get("status") in (None, "preflight", "not_ready"):
                        return DeliveryResult(
                            DeliveryStatus.DEFERRED, cursor,
                            "binding invoker not ready")
                    raise
                native_return = result.get("native_return")
                if native_return == 0:
                    token_now, cursor_now, _ = self._state()
                    if token_now != 0 or cursor_now != 0:
                        raise BackendContractError(
                            "ledger changed after an explicit binding refusal")
                    return DeliveryResult(
                        DeliveryStatus.DEFERRED, cursor_now,
                        "native binding explicitly refused")
                if native_return != 1:
                    return DeliveryResult(
                        DeliveryStatus.UNCERTAIN, cursor,
                        "unknown native binding acknowledgement")

                deadline = time.monotonic() + self.commit_timeout
                while time.monotonic() < deadline:
                    token_now, cursor_now, _ = self._state()
                    guard_now = self._guard()
                    if token_now == self.token and cursor_now == 0 and not guard_now:
                        return DeliveryResult(DeliveryStatus.APPLIED, cursor_now)
                    if cursor_now != 0 or token_now not in (0, self.token):
                        return DeliveryResult(
                            DeliveryStatus.UNCERTAIN, cursor_now,
                            f"ledger diverged during binding: {token_now}/{cursor_now}")
                    time.sleep(self.poll_seconds)
        except BackendContractError:
            raise
        except Exception as exc:
            # Once the native request was prepared, retrying could execute the
            # setter twice. Reconcile a completed write from the durable flags;
            # otherwise quarantine the result for the caller to stop safely.
            try:
                token_now, cursor_now, _ = self._state()
                guard_now = self._guard()
            except Exception:
                token_now, cursor_now, guard_now = token, cursor, True
            if token_now == self.token and cursor_now == 0 and not guard_now:
                return DeliveryResult(
                    DeliveryStatus.APPLIED, cursor_now,
                    f"binding committed despite an observation error: {exc}")
            return DeliveryResult(
                DeliveryStatus.UNCERTAIN, cursor_now,
                f"binding outcome unknown: {exc}")
        return DeliveryResult(
            DeliveryStatus.UNCERTAIN, cursor,
            "binding entry accepted without an observed commit")

    def _sync_selection(self, equip: int | None) -> str:
        """After a commit that selected a rune, make the live game show it.

        The save is already coherent: whatever happens here, the step stays
        APPLIED and is never replayed. See botw_client/rune_selection.py.
        """
        if equip is None:
            return ""
        sync = getattr(self.game, "sync_rune_selection", None)
        if sync is None:
            return "rune selection not synchronized: the game lacks this capability"
        try:
            return sync(equip).summary()
        except Exception as exc:  # noqa: BLE001 - the commit is already durable
            return f"rune selection not synchronized: {type(exc).__name__}: {exc}"

    def request_status_item(self) -> bool | None:
        """Ask the idempotent key item entry once: True once the game took the
        request, False when it is to be asked again later, None when the pack
        has no such entry. No cursor: the entry grants the item only when the
        pouch does not hold it."""
        entry = self.catalog.status_entry()
        if entry is None:
            return None
        # Accepted or unknown: the entry is harmless twice.
        return self._request_once(self.catalog.data["flow"], entry) is not False

    def request_death(self) -> bool | None:
        """Kill Link through the pack's DeathLink entry: True once the game took
        the request, False when it is to be asked again later, None when the
        pack has no such entry. An unknown outcome counts as taken: a death
        requested twice would kill twice."""
        found = self.catalog.death_link_entry()
        if found is None:
            return None
        return self._request_once(*found) is not False

    def killed_by_death_link(self) -> bool | None:
        """Is the DeathLink entry's flag set (a death it caused)? None when the
        pack has no flag or it cannot be read."""
        flag = self.catalog.death_link_flag()
        live = getattr(self.game, "live", None)
        if flag is None or live is None:
            return None
        value = live.get(zlib.crc32(flag.encode()) & 0xFFFFFFFF, "bool")
        return None if value is None else bool(value)

    def death_cause(self, slot: str) -> str:
        """The DeathLink cause for Link's death (botw_client/death_cause.py),
        read at once: the game's own query, its raw value and the attacker."""
        from . import death_cause as dc
        process, cave = self.game.process, self.game.cave

        def read(guest, size):
            return process.read(cave.base + guest, size)

        actor = dc.player(read)
        killer = dc.attacker(read, actor)
        cause = self._call(dc.DEAD_CAUSE_QUERY, 0)
        raw = self._call(dc.DEAD_CAUSE_RAW, actor) if actor is not None else None
        return dc.death_text(slot, cause, raw, killer, self.catalog.attacker_names())

    def last_attacker(self) -> str | None:
        """The name of the last actor that hurt Link (botw_client/death_cause.py)."""
        from . import death_cause as dc
        process, cave = self.game.process, self.game.cave

        def read(guest, size):
            return process.read(cave.base + guest, size)

        actor = dc.player(read)
        return dc.attacker(read, actor) if actor is not None else None

    def playing(self) -> bool:
        """Link in the world: no menu, inventory, dialogue, event or loading
        (the stateless guard of the presentations and the journal)."""
        from tools.cemu.presentation_ready import flag_reader, ready
        process, cave = self.game.process, self.game.cave
        if getattr(self, "_playing_for", None) is not process:
            self._playing_flags, self._playing_for = flag_reader(process, cave), process
        return ready(process, cave, self._playing_flags, allow_hudless=True)

    def cucco_swarm(self, stop=lambda: False) -> dict[str, int]:
        """Play the Cucco Swarm trap (botw_client/cucco_swarm.py): {outcome: count}."""
        from .cucco_swarm import CuccoSwarm
        process, cave = self.game.process, self.game.cave
        _request, lock_factory = self._dependencies()
        pid = int(process.pid)

        def read(guest, size):
            return process.read(cave.base + guest, size)

        def write(guest, data):
            if not process.write(cave.base + guest, data):
                raise RuntimeError(f"memory write failed at {guest:#x}")

        # One turn per attacker: the loop's deliveries and journal wait for
        # it, and never cut an attacker's calls in two (botw_client/invoker_turn.py).
        return CuccoSwarm(read, write, self._call,
                          turn=lambda: lock_factory(pid) if lock_factory else nullcontext(),
                          playing=self.playing).run(stop)

    def _call(self, address: int, *args, timeout: float = 1.0) -> int | None:
        """Call a game function from the cave's per-frame hook, as the event
        requests are made: its r3, or None when it could not be called."""
        process, cave = self.game.process, self.game.cave
        _request, lock_factory = self._dependencies()

        def word(host):
            raw = process.read(host, 4)
            return int.from_bytes(raw, "big") if raw and len(raw) == 4 else None

        try:
            with (lock_factory(int(process.pid)) if lock_factory else nullcontext()):
                if word(cave.pf_req) != 0:
                    return None
                before = word(cave.call_n)
                cave.call_pf(address, *args)
                try:
                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        if word(cave.call_n) != before:
                            return word(cave.call_ret)
                        time.sleep(0.005)
                    return None
                finally:
                    process.write(cave.pf_req, bytes(4))
        except Exception:  # noqa: BLE001 - lock busy, stale patch: no cause
            return None

    def _request_once(self, flow: str, entry: str) -> bool | None:
        """Request an idempotent entry of the session's pack: False when it was
        not placed (to ask again), True when accepted, None when unknown."""
        token, _cursor, _rejected = self._state()
        since = self._frames_since_commit()
        if (token != self.token or not self._ready()
                or (since is not None and since < SETTLE_FRAMES)):
            return False
        request, lock_factory = self._dependencies()
        pid = int(self.game.process.pid)
        with (lock_factory(pid) if lock_factory else nullcontext()):
            try:
                result = request(self.game.process, self.game.cave, 0, lambda _value: None,
                                 custom_text=False, flow=flow, entry=entry)
            except Exception:  # noqa: BLE001 - not placed: asked again
                return False
        if result.get("native_return") == 0:
            return False
        # The next delivery lets this event run and close first.
        self._committed_at = self._frame()
        return True if result.get("native_return") == 1 else None

    def deliver(self, command: DeliveryCommand) -> DeliveryResult:
        token, cursor, rejected = self._state()
        binding = self.catalog.binding()
        if binding is not None and binding["seed_token"] != self.token:
            return DeliveryResult(
                DeliveryStatus.SESSION_MISMATCH, cursor,
                f"catalog built for {binding['seed_token']}, token {self.token}")
        flow, step = self.catalog.resolve(command)
        # Read before submitting: a malformed setter must fail before any call.
        equip = equip_requirement(step)
        if token != self.token:
            return DeliveryResult(DeliveryStatus.SESSION_MISMATCH, cursor,
                                  f"BOTW token {token}, expected {self.token}")
        if cursor != command.cursor:
            raise BackendContractError(
                f"cursor changed before submission: {cursor}, expected {command.cursor}")
        if not self._ready():
            return DeliveryResult(DeliveryStatus.DEFERRED, cursor,
                                  getattr(self.game, "delivery_block_reason", "game busy"))
        since = self._frames_since_commit()
        if since is not None and since < SETTLE_FRAMES:
            return DeliveryResult(DeliveryStatus.DEFERRED, cursor,
                                  f"previous event closing ({since}/{SETTLE_FRAMES} frames)")
        if not (command.quiet and step.get("quiet_entry")) and any(
                m.get("kind") == "rune_download" for m in step.get("mutations", ())):
            # The download screen needs the pause menu built at once, or the
            # menu clears its request and the event waits forever
            # (botw_client/pause_menu.py).
            try:
                ready, reason = self.game.pause_menu_ready()
            except Exception as exc:  # noqa: BLE001 - unreadable: not now
                ready, reason = False, f"pause menu unreadable ({exc})"
            if not ready:
                return DeliveryResult(DeliveryStatus.DEFERRED, cursor,
                                      f"pause menu not ready: {reason}")

        request, lock_factory = self._dependencies()
        evidence = {}
        try:
            pid = int(self.game.process.pid)
            lock = lock_factory(pid) if lock_factory else nullcontext()
            with lock:
                try:
                    silent = command.quiet and step.get("quiet_entry")
                    # Silent twins and steps without a window live in their own
                    # flowchart, registered not to pause the game
                    # (botw_patch/delivery_flow.host_of); older catalogues
                    # kept them in the delivery flow.
                    result = request(
                        self.game.process, self.game.cave, command.index + 1,
                        lambda value: evidence.update(value), custom_text=False,
                        flow=(step.get("quiet_flow", flow) if silent
                              else step.get("flow", flow)),
                        entry=step["quiet_entry"] if silent else step["entry"])
                except Exception:
                    # Before "prepared", no call was placed. Once prepared, the
                    # request outcome can only be reconciled from the ledger.
                    if evidence.get("status") in (None, "preflight", "not_ready"):
                        return DeliveryResult(DeliveryStatus.DEFERRED, command.cursor,
                                              "native invoker not ready")
                    raise
                native_return = result.get("native_return")
                if native_return == 0:
                    token_now, cursor_now, _ = self._state()
                    if token_now != self.token or cursor_now != command.cursor:
                        raise BackendContractError(
                            "state changed after an explicit native refusal")
                    return DeliveryResult(DeliveryStatus.DEFERRED, cursor_now,
                                          "native request explicitly refused")
                if native_return != 1:
                    return DeliveryResult(DeliveryStatus.UNCERTAIN, command.cursor,
                                          "unknown native acknowledgement")

                deadline = time.monotonic() + self.commit_timeout
                while time.monotonic() < deadline:
                    token_now, cursor_now, rejected_now = self._state()
                    if token_now != self.token:
                        return DeliveryResult(
                            DeliveryStatus.UNCERTAIN, cursor_now,
                            "save token changed during the delivery")
                    if cursor_now == command.next_cursor:
                        self._committed_at = self._frame()
                        return DeliveryResult(DeliveryStatus.APPLIED, cursor_now,
                                              self._sync_selection(equip))
                    if cursor_now != command.cursor:
                        raise BackendContractError(
                            f"impossible native commit: {cursor_now}, expected "
                            f"{command.cursor} or {command.next_cursor}")
                    if rejected_now != rejected:
                        if rejected_now == rejected + 1:
                            self._committed_at = self._frame()
                            return DeliveryResult(
                                DeliveryStatus.INVENTORY_FULL, cursor_now,
                                f"inventory full for {step.get('capacity_actor')}")
                        raise BackendContractError(
                            f"reject counter advanced from {rejected} to {rejected_now}")
                    time.sleep(self.poll_seconds)
        except BackendContractError:
            raise
        except Exception:
            raise
        return DeliveryResult(DeliveryStatus.UNCERTAIN, command.cursor,
                              "entry accepted without an observed commit"
                              + (f" (requested {since} frames after the previous commit)"
                                 if since is not None else ""))
