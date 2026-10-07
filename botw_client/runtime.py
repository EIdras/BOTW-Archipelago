"""Resilient 5 Hz bridge between a BOTW process and an AP room."""
from __future__ import annotations

import asyncio
import copy
import json
import threading
import time
from pathlib import Path

from .backend import DeliveryCommand, DeliveryCoordinator, DeliveryStatus
from .game import BotwGame, GameNotReady
from .locations import SCHEMA_LOCATION_COUNTS, load_targets
from .paths import DATA
from .protocol import ArchipelagoClient, DeathLinkEvent, LocationInfo
from .session import session_token
from .message_text import clip_units, literal_metadata, literal_text, queued_text

POLL_SECONDS = 0.2
CHECK_RESEND_SECONDS = 2.0
BLOCK_REFRESH_SECONDS = 0.5
MESSAGE_MAX_CHARS = 39
MESSAGE_SETTLE_SECONDS = 4.0
# Reading time of a received item's journal line before its window.
JOURNAL_LEAD_SECONDS = 2.0
# Ticks a pickup notification may wait for Link back in the world (a menu, an
# entry closing) before it is given up.
PICKUP_ATTEMPTS = 600
# How long a received item waits for the server's own line before ours.
JOURNAL_SERVER_WAIT_SECONDS = 3.0
# How long a received item waits for its journal line to be shown: the tip
# frame can stay taken (the heat warning, as long as Link is in the heat); the
# item then comes without it, and its line follows once the frame is free.
JOURNAL_BLOCK_SECONDS = 8.0
# A release or a collect: the server's notice (PrintJSON Release, Collect) and
# the items it sends come within this many seconds of each other.
BULK_WINDOW_SECONDS = 15.0
# A received DeathLink: its journal line is read before Link dies. The entry
# leaves its flag set on the death it causes (botw_patch/death_link.py): such a
# death is never sent back. The flag counts for DEATHLINK_FLAG_SECONDS after
# the request, in case it stayed set on a survival; a pack without the flag
# falls back on the time alone (measured: Link dies in the frame the entry
# runs). A death still waiting after DEATHLINK_EXPIRY_SECONDS (Link busy in an
# event...) is dropped.
DEATHLINK_LEAD_SECONDS = 3.0
DEATHLINK_ECHO_SECONDS = 5.0
DEATHLINK_FLAG_SECONDS = 60.0
DEATHLINK_EXPIRY_SECONDS = 120.0
STATE_PATH = DATA / "client-state.json"
GOAL_LOCATION = "Defeat Calamity Ganon"
STATE_SCHEMA = 3
CLIENT_SCHEMA = 2
# The client schemas of BOTW seeds this client plays: 4 added the Gerudo Set, 5 the
# goal and the sanctum's requirements, 6 the new filler, 7 the weapons.
BOTW_CLIENT_SCHEMAS = (3, 4, 5, 6, 7)
# The mutations that present the item themselves: no AP window before them.
VANILLA_WINDOWS = ("get_demo_actor", "champion_actor", "rune_download", "trap", "native_trap",
                   "get_demo_bundle", "cook", "pouch_slot")
TERMINAL_ITEMS = {
    "Magnesis Terminal": "Magnesis",
    "Remote Bombs Terminal": "Remote Bomb",
    "Stasis Terminal": "Stasis",
    "Cryonis Terminal": "Cryonis",
}
RUNE_NAMES = tuple(TERMINAL_ITEMS.values())


def event_settle_seconds(name: str) -> float:
    """Fallback timing until a verified in-demo signal is instrumented."""
    if name.endswith(" Shrine"):
        # The scout cache removes the server round-trip: present while the
        # player is still in the shrine as soon as its clear flag rises.
        return 0.5
    if name.endswith(" Tower") or name.startswith("Divine Beast"):
        return 15.0
    if name.endswith(" Terminal"):
        return 8.0
    return 3.0


class FatalClientError(RuntimeError):
    """A deterministic error for which reconnecting would not help."""


def _session_defaults() -> dict:
    return {
        "applied": [],
        "shown": [],
        "steps": {},
        "apply_queue": [],
        "display_queue": [],
        "pending_checks": [],
        "location_display_queue": [],
        "location_shown": [],
        "presentation_completed": [],
        "location_presentation_completed": [],
        "message_queue": [],
        "pending_deathlinks": [],
        "pending_outgoing_death": False,
        "last_death_link": 0.0,
        "scouts": {},
        "goal_sent": False,
        "goal_observed": False,
        "observed_checks": [],
    }


def offline_duration(since: float | None, now: float | None = None) -> str:
    """How long the AP outage lasted, for the journal line."""
    if since is None:
        return ""
    seconds = int((time.monotonic() if now is None else now) - since)
    if seconds < 60:
        return f"after {max(seconds, 1)} s offline"
    return f"after {seconds // 60} min {seconds % 60:02d} s offline"


def replay_summary_lines(names: list[str], width: int = 40, lines: int = 4) -> list[str]:
    """Names with their counts, in order, wrapped into the AP window; what
    does not fit is counted on the last line ("and N more")."""
    counts: dict[str, int] = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1
    labels = [f"{name} x{count}" if count > 1 else name for name, count in counts.items()]
    rows: list[list[str]] = []
    for label in labels:
        if rows and len(", ".join(rows[-1] + [label])) <= width:
            rows[-1].append(label)
        else:
            rows.append([label[:width]])
    if len(rows) <= lines:
        return [", ".join(row) for row in rows]
    kept = rows[:lines]
    shown = sum(len(row) for row in kept)
    while True:
        rest = len(labels) - shown
        suffix = f"and {rest} more"
        last = ", ".join(kept[-1])
        if kept[-1] and len(f"{last} {suffix}") <= width:
            kept[-1] = [f"{last} {suffix}"]
            break
        if not kept[-1]:
            kept[-1] = [suffix]
            break
        kept[-1].pop()
        shown -= 1
    return [", ".join(row) for row in kept]


class StateStore:
    def __init__(self, path: Path = STATE_PATH):
        self.path = path
        try:
            self.data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.data = {"schema": STATE_SCHEMA, "sessions": {}}
        except (OSError, ValueError) as exc:
            raise FatalClientError(f"client state unreadable ({path}): {exc}") from exc
        schema = self.data.get("schema")
        if schema not in (1, 2, STATE_SCHEMA) or not isinstance(
                self.data.get("sessions"), dict):
            raise FatalClientError(f"unknown client state format: {path}")
        if schema in (1, 2):
            self.data["schema"] = STATE_SCHEMA
        self.current = None

    def select(self, seed: str, team: int, slot: int,
               data_package_checksum: str = "legacy"):
        key = json.dumps([seed, team, slot, data_package_checksum],
                         ensure_ascii=False)
        legacy_key = json.dumps([seed, team, slot], ensure_ascii=False)
        if (data_package_checksum == "legacy" and key not in self.data["sessions"]
                and legacy_key in self.data["sessions"]):
            self.data["sessions"][key] = copy.deepcopy(
                self.data["sessions"][legacy_key])
        self.current = self.data["sessions"].setdefault(key, _session_defaults())
        for field, default in _session_defaults().items():
            self.current.setdefault(field, copy.deepcopy(default))
        return self.current

    def save(self):
        if self.current is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        temporary.replace(self.path)


class BotwClientRuntime:
    def __init__(self, server: str, slot: str, password: str | None = None,
                 state_path: Path = STATE_PATH, log=print, *,
                 game_name: str | None = None, game_factory=BotwGame,
                 native_presentations=False, presentation_factory=None,
                 native_delivery=False, delivery_factory=None,
                 delivery_catalog_path=None, game_process_alive=None,
                 tip_factory=None, journal_chat=True, journal_everyone=False):
        # AP journal in the game's tip frame (botw_client/tip_channel.py).
        self.tip_factory = tip_factory
        self.tips = None
        self.journal_chat, self.journal_everyone = journal_chat, journal_everyone
        self._journal_notes: list[tuple[str, int | None]] = []
        self._journal_pages: list[tuple[str, int | None]] = []
        # Received items: their journal line goes before their presentation.
        self._journal_queued: set[int] = set()
        self._journal_times: dict[int, float] = {}
        self._journal_waiting: dict[int, float] = {}
        self._journal_queued_at: dict[int, float] = {}
        self._journal_current = None
        self._journal_retry_after = 0.0
        self._journal_started = time.time()
        self._journal_connected_once = False
        self.log = log
        self.game_process_alive = game_process_alive
        self.ap = ArchipelagoClient(server, slot, password, log=log)
        if game_name is not None:
            self.ap.game = game_name
        self.game = game_factory()
        # Native presentation path. No grants/ledger or legacy display
        # writes are enabled by choosing this path; DeathLink goes through
        # the native delivery backend.
        self.native_presentations = native_presentations
        self.native_delivery = native_delivery
        self.native_mode = native_presentations or native_delivery
        self.game.native_presentation_mode = self.native_mode
        self.presentation_factory = presentation_factory
        self.presentations = None
        self.delivery_factory = delivery_factory
        self.delivery_catalog_path = delivery_catalog_path
        self.deliveries = None
        self._presentation_status = None
        self._presentation_recovery_request = None
        self._ap_session_ready = False
        self.state_store = StateStore(state_path)
        self.state = None
        self.stop_event = asyncio.Event()
        self.safe_after = 0.0
        self.last_check_send = 0.0
        self._last_dead = None
        self._alive_seen = False
        self._reconnect_task = None
        self._reconnect_delay = 1.0
        # Start of the current AP outage (monotonic), announced once.
        self._offline_since = None
        # The Archipelago key item is asked once per game connection.
        self._status_item_done = False
        # The HUD's AP logo (botw_client/hud_indicator.py): colour when
        # connected, grey otherwise.
        self.hud = None
        self._hud_next = 0.0
        self._hud_error = None
        self._status_item_retry_after = 0.0
        # The Master Sword's pedestal to close (botw_patch/pedestal.py): its
        # flags while it is to be checked, the request made, the next try.
        self._pedestal_flags = None
        self._pedestal_requested = False
        self._pedestal_retry_after = 0.0
        # The sanctum's gate: checked every second; off for a pack without it.
        self._gate_unavailable = False
        self._gate_retry_after = 0.0
        self._session_identity = None
        self._session_locations = None
        self.lease_error = None
        self._next_message_after = 0.0
        self._last_game_cursor = None
        self._session_token = None
        self._deathlink_retry_after = 0.0
        self._deathlink_announced_at = None
        self._death_requested_at = None
        # Native traps (botw_client/cucco_swarm.py): the committed ones waiting
        # to be played, the one playing, and, once it is over, how long its
        # attackers may still be around (in game time: it stands still out of
        # the world), during which a death by them is the trap's, not sent as
        # a DeathLink.
        self._native_traps: list[str] = []
        # Pickup notifications of fillers received again, shown once their
        # delivery has committed and Link is back in the world.
        self._pickups: list[tuple[str, int]] = []
        self._native_trap_task = None
        self._swarm_left = 0.0
        self._swarm_clock = 0.0
        self._swarm_stop = threading.Event()
        self._next_delivery_wait_log = 0.0
        self._native_delivery_retry_after = 0.0
        self._native_session_bound = False

    def stop(self):
        self.stop_event.set()

    def _process_exit_error(self, exc):
        """Only classify known process-access failures after confirmed exit."""
        if self.game_process_alive is None or self.game_process_alive():
            return False
        current = exc
        seen = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if ((type(current) is RuntimeError and str(current) == 'Cemu process exited')
                    or (type(current) is TypeError and str(current) ==
                        "cannot convert 'NoneType' object to bytes")):
                self.log('Cemu closed: memory access ended, client stopping.')
                self.stop()
                return True
            current = current.__cause__
        return False

    async def _wait_or_stop(self, seconds: float):
        try:
            await asyncio.wait_for(self.stop_event.wait(), seconds)
        except asyncio.TimeoutError:
            pass

    def _restore_cached_scouts(self, expected_ids: set[int]) -> bool:
        raw = self.state.get("scouts", {})
        try:
            restored = {
                int(key): LocationInfo(*(int(value) for value in values))
                for key, values in raw.items()
            }
        except (TypeError, ValueError):
            return False
        if set(restored) != expected_ids:
            return False
        if any(info.location != location_id or not self.ap.item_name(info)
               for location_id, info in restored.items()):
            return False
        self.ap.scouted_locations = restored
        return True

    async def _load_scouts(self, names: list[str]):
        expected_ids = {self.ap.location_id_by_name[name] for name in names}
        if self._restore_cached_scouts(expected_ids):
            self.log(f"seed cache: {len(expected_ids)} placements")
            return
        try:
            scouts = await self.ap.scout_locations(names)
        except Exception as exc:
            raise ConnectionError(
                "cannot get the seed cache; AP session refused") from exc
        if set(scouts) != expected_ids:
            raise FatalClientError(
                f"incomplete scouts: {len(scouts)}/{len(expected_ids)}")
        self.state["scouts"] = {
            str(location_id): [info.item, info.location, info.player, info.flags]
            for location_id, info in scouts.items()
        }
        self.state_store.save()
        self.log(f"seed cache saved: {len(scouts)} placements")

    async def _connect_ap(self):
        self._ap_session_ready = False
        await self.ap.connect()
        try:
            await asyncio.wait_for(self.ap.data_package_event.wait(), 15.0)
        except asyncio.TimeoutError as exc:
            raise ConnectionError("BOTW data package not received within 15 s") from exc
        world_schema = self._world_schema()
        target_names = [target.name for target in load_targets(world_schema=world_schema)]
        slot_schema = int(self.ap.slot_data.get("client_schema", 0))
        expected_schema = (BOTW_CLIENT_SCHEMAS if self.ap.game == "Breath of the Wild"
                           else (CLIENT_SCHEMA,))
        if slot_schema not in expected_schema:
            raise FatalClientError(
                f"slot_data client_schema={slot_schema}; expected {expected_schema}. "
                + self._versions_hint())
        expected = set(target_names)
        if self.ap.game == "Breath of the Wild":
            expected.discard(GOAL_LOCATION)
        available = set(self.ap.location_id_by_name)
        if expected != available:
            missing = sorted(expected - available)
            extra = sorted(available - expected)
            raise FatalClientError(
                "data package incompatible: "
                f"{len(expected)} locations expected; "
                f"missing={missing[:4]}, extra={extra[:4]}")
        identity = (self.ap.seed_name or "unknown-seed", self.ap.team,
                    self.ap.slot, self.ap.data_package_checksum)
        if self._session_identity is not None and identity != self._session_identity:
            raise FatalClientError(
                "the room or the slot changed during the game; restart the client")
        self._session_identity = identity
        # Options may leave locations out of the seed (shops): only those of
        # the seed are scouted and sent.
        seed = getattr(self.ap, "seed_locations", set())
        target_names = [name for name in target_names
                        if name == GOAL_LOCATION or not seed
                        or self.ap.location_id_by_name[name] in seed]
        self._session_locations = set(target_names)
        self.state = self.state_store.select(*identity)
        self.ap.last_death_link = max(
            self.ap.last_death_link,
            float(self.state.get("last_death_link") or 0.0))
        await self._load_scouts(
            [name for name in target_names if name != GOAL_LOCATION])
        self._acknowledge_checks()
        await self.ap.sync()
        self._ap_session_ready = True

    async def _connect_game(self):
        self._status_item_done = False
        connect_task = asyncio.create_task(asyncio.to_thread(self.game.connect, self.log))
        try:
            await asyncio.shield(connect_task)
        except asyncio.CancelledError:
            # Indexing still owns the process handle until its worker returns.
            await connect_task
            raise
        token = session_token(self._session_identity)
        self._session_token = token
        if self.native_mode:
            from .presentation_session import NativePresentationSession
            self._close_presentations()
            try:
                if self.native_presentations:
                    factory = self.presentation_factory or NativePresentationSession
                    self.presentations = factory(
                        self.state_store.path, self._session_identity, self.game)
                if self.native_delivery:
                    from .native_delivery import CemuNativeDeliveryBackend
                    factory = self.delivery_factory or CemuNativeDeliveryBackend
                    kwargs = ({"catalog": self.delivery_catalog_path}
                              if self.delivery_catalog_path is not None else {})
                    if factory is CemuNativeDeliveryBackend:
                        kwargs["report"] = self.log
                    backend = factory(
                        self.game, self._session_identity[0],
                        self._session_identity[2], token, **kwargs)
                    self.deliveries = DeliveryCoordinator(backend)
                    checkpoint = backend.checkpoint()
                    self._native_session_bound = (
                        (checkpoint.seed, checkpoint.slot)
                        == (self._session_identity[0], self._session_identity[2]))
                if getattr(self.game, "cave", None) is not None:
                    from .hud_indicator import HudIndicator
                    self.hud = HudIndicator(self.game.process, self.game.cave)
                if self.tip_factory is not None:
                    self.tips = self.tip_factory(self.game)
                    self.log("AP journal: tip frame active")
                    # A tip on screen when the game loop restarted is shown
                    # again, not lost with the previous channel object.
                    if self._journal_current is not None:
                        self._journal_pages.insert(0, self._journal_current)
                        self._journal_current = None
                    # Announced once the game can show it (the AP connection
                    # comes first, while Cemu is still loading).
                    if not self._journal_connected_once:
                        self._journal_connected_once = True
                        self._journal_note(f"{{1}}Connected{{/}} to Archipelago: slot "
                                           f"{{2}}{self.ap.slot_name or self.ap.slot}{{/}}")
            except Exception as exc:
                self._close_presentations()
                raise FatalClientError(f'native mode unavailable: {exc}') from exc
            if self.native_delivery and self._native_session_bound:
                await self._reconcile_rune_selection()
            self.game.locations.previous = None
            self.safe_after = time.monotonic() + 2.0
            return
        try:
            await asyncio.to_thread(self.game.bind_ap_session, token)
        except RuntimeError as exc:
            raise FatalClientError(str(exc)) from exc
        # Start disarmed. _lease_loop only enables the mailbox 0x0BADF00E
        # selective Obj_DungeonClearSeal filter after all guards passed.
        self.game.set_blocking(False)
        self.game.cave.sub_disarm()
        self.game.locations.previous = None
        self.safe_after = time.monotonic() + 2.0

    async def _reconcile_rune_selection(self):
        """Repair a rune committed while no companion was there to sync it.

        A step is APPLIED once its cursor is saved and is never replayed, so a
        companion stopped between the commit and the selection sync would
        leave the running game without the rune on its wheel until a reload.
        The check is idempotent: it only acts when the live selection object
        disagrees with PlayerEquipItemType (botw_client/rune_selection.py).
        """
        sync = getattr(self.game, "sync_rune_selection", None)
        if sync is None:
            return
        try:
            outcome = await asyncio.to_thread(sync)
        except Exception as exc:  # noqa: BLE001 - a repair must not block the session
            self.log(f"connection: rune selection not checked ({exc})")
            return
        if outcome.status not in ("no_rune", "in_sync"):
            self.log(f"connection: {outcome.summary()}")

    async def _ensure_native_session(self) -> bool:
        if not self.native_delivery or self.deliveries is None:
            return True
        if self._native_session_bound:
            return True
        if time.monotonic() < self._native_delivery_retry_after:
            return False
        binder = getattr(self.deliveries.backend, "bind_session", None)
        if binder is None:
            raise FatalClientError("native backend without session binding")
        result = await asyncio.to_thread(binder)
        if result.status in (DeliveryStatus.APPLIED,
                             DeliveryStatus.ALREADY_APPLIED):
            self._native_session_bound = True
            self._native_delivery_retry_after = 0.0
            self.game.delivery_block_reason = 'session bound; waiting for the presentation conditions'
            self.log("BOTW save bound to the AP session")
            return True
        if result.status is DeliveryStatus.DEFERRED:
            self.game.delivery_block_reason = (
                'binding deferred; automatic retry'
                + (f' ({result.detail})' if result.detail else ''))
            self._native_delivery_retry_after = time.monotonic() + 0.5
            return False
        raise FatalClientError(
            f"native binding refused ({result.status.value}): {result.detail}")

    async def _lease_loop(self):
        """Renew the selective shrine-reward lease; disarm on every exit."""
        try:
            while not self.stop_event.is_set() and self.game.cave:
                if self.native_mode:
                    await asyncio.sleep(BLOCK_REFRESH_SECONDS)
                    continue
                if self.game.healthy():
                    self.game.set_blocking(True)
                else:
                    self.game.set_blocking(False)
                await asyncio.sleep(BLOCK_REFRESH_SECONDS)
        except Exception as exc:
            self.lease_error = exc
        finally:
            try:
                self.game.set_blocking(False)
                if self.game.cave and not self.native_mode:
                    self.game.cave.sub_disarm()
            except Exception:
                pass

    def _received_before(self, index: int, name: str) -> int:
        return sum(
            1 for prior_index, prior in self.ap.received_items.items()
            if prior_index < index and self.ap.item_name(prior) == name)

    def _has_save_ledger(self) -> bool:
        # Test doubles predating the optional fallback represent the ledger
        # implementation; the real BotwGame states availability explicitly.
        return bool(getattr(self.game, "save_ledger_available", True))

    def _delivery_position(self) -> tuple[int, int]:
        if self._has_save_ledger():
            return self.game.delivery_position()
        applied = {int(value) for value in self.state["applied"]}
        index = 0
        while index in applied:
            index += 1
        return index, int(self.state["steps"].get(str(index), 0))

    def _set_delivery_position(self, index: int, step: int = 0):
        if self._has_save_ledger():
            self.game.set_delivery_position(index, step)
            return
        self.state["steps"].clear()
        if step:
            self.state["steps"][str(index)] = step

    def _discover_received(self):
        if not getattr(self.ap, "items_synchronized", True):
            return
        if self.native_delivery:
            if self.deliveries is None:
                raise FatalClientError("native delivery backend missing")
            checkpoint = self.deliveries.backend.checkpoint()
            expected = (self._session_identity[0], self._session_identity[2])
            if (checkpoint.seed, checkpoint.cursor) == ("token:0", 0):
                # Seen in play: Link died on a new game just after its binding, and
                # the reload went back to the save from before it, untouched
                # again: it is bound again, as a new game is.
                if self._native_session_bound:
                    self.log("BOTW save reloaded from before its binding: binding it again")
                self._native_session_bound = False
                self._status_item_done = False      # the key item is gone with it
                return
            if (checkpoint.seed, checkpoint.slot) != expected:
                raise FatalClientError(
                    "BOTW save not bound to this AP session: "
                    f"{checkpoint.seed}/{checkpoint.slot}, expected "
                    f"{expected[0]}/{expected[1]}")
            cursor_index, cursor_step = checkpoint.cursor >> 8, checkpoint.cursor & 0xFF
            if cursor_index > len(self.ap.received_items):
                return
            # Highest index ever delivered: after a save reload moved the
            # cursor back, what lies below it is given back, not new. A state
            # written before this was tracked still knows its applied list:
            # the cursor it last saw.
            known = [int(value) for value in self.state["applied"]]
            high = max(cursor_index, max(known, default=-1) + 1)
            if high > int(self.state.get("delivered_high", 0)):
                self.state["delivered_high"] = high
                self.state_store.save()
            applied = set(range(cursor_index))
            desired_apply = [index for index in sorted(self.ap.received_items)
                             if index >= cursor_index]
            changed = self.state["apply_queue"] != desired_apply
            self.state["apply_queue"] = desired_apply
            if set(int(value) for value in self.state["applied"]) != applied:
                self.state["applied"] = sorted(applied)
                changed = True
            desired_steps = ({str(cursor_index): cursor_step}
                             if cursor_step else {})
            if self.state["steps"] != desired_steps:
                self.state["steps"] = desired_steps
                changed = True
            shown = {int(value) for value in self.state["shown"]}
            queued = {int(value) for value in self.state["display_queue"]}
            for index in sorted(self.ap.received_items):
                if index not in shown and index not in queued:
                    self.state["display_queue"].append(index)
                    queued.add(index)
                    changed = True
            if changed:
                self.state["display_queue"].sort()
                self.state_store.save()
            return
        if not self.native_presentations:
            try:
                self.game.bind_ap_session(self._session_token)
            except RuntimeError as exc:
                raise FatalClientError(str(exc)) from exc
        if self.native_presentations or not self._has_save_ledger():
            applied = {int(value) for value in self.state["applied"]}
            desired_apply = [index for index in sorted(self.ap.received_items)
                             if index not in applied]
            changed = self.state["apply_queue"] != desired_apply
            self.state["apply_queue"] = desired_apply
            shown = {int(value) for value in self.state["shown"]}
            queued = {int(value) for value in self.state["display_queue"]}
            for index in sorted(self.ap.received_items):
                if index not in shown and index not in queued:
                    self.state["display_queue"].append(index)
                    queued.add(index)
                    changed = True
            if changed:
                self.state["display_queue"].sort()
                self.state_store.save()
            return
        cursor_index, cursor_step = self._delivery_position()
        if self._last_game_cursor is not None and cursor_index < self._last_game_cursor:
            self.log(f"BOTW rollback detected: AP items resume at #{cursor_index}")
        self._last_game_cursor = cursor_index
        if cursor_index > len(self.ap.received_items):
            # ReceivedItems may still be arriving after Sync.
            return
        applied = set(range(cursor_index))
        shown = {int(value) for value in self.state["shown"]}
        display_queue = {int(value) for value in self.state["display_queue"]}
        desired_apply = [index for index in sorted(self.ap.received_items)
                         if index >= cursor_index]
        changed = self.state["apply_queue"] != desired_apply
        self.state["apply_queue"] = desired_apply
        if set(int(value) for value in self.state["applied"]) != applied:
            self.state["applied"] = sorted(applied)
            changed = True
        self.state["steps"] = ({str(cursor_index): cursor_step}
                               if cursor_step else {})
        for index in sorted(self.ap.received_items):
            if index not in shown and index not in display_queue:
                self.state["display_queue"].append(index)
                display_queue.add(index)
                changed = True
        if changed:
            self.state["display_queue"].sort()
            self.state_store.save()

    def _safe_now(self) -> bool:
        now = time.monotonic()
        if now < self.safe_after:
            self.game.delivery_block_reason = (
                f"event settling {self.safe_after - now:.1f}s")
            return False
        return self.game.safe_for_delivery()

    def _log_delivery_wait(self):
        queues = sum(len(self.state[name]) for name in (
            "apply_queue", "display_queue", "location_display_queue"))
        now = time.monotonic()
        if queues and now >= self._next_delivery_wait_log:
            reason = self.game.delivery_block_reason
            session = getattr(self, 'presentations', None)
            backend = getattr(session, 'backend', None)
            submission = getattr(backend, 'last_submission', None)
            native_wait = getattr(backend, 'wait_reason', None)
            if self._presentation_status in ('queued', 'waiting_ready') and isinstance(native_wait, str):
                # The client's gate may say ready while the presentation's holds:
                # its own reason, with what it sees.
                reason = native_wait
                detail = getattr(backend, 'wait_detail', None)
                detail = detail() if callable(detail) else None
                if isinstance(detail, str):
                    reason += f' ({detail})'
                elif native_wait.startswith('game not yet stable'):
                    # The client's gate said no: its reason.
                    reason += f' ({self.game.delivery_block_reason})'
            if (self._presentation_status in ('queued', 'waiting_ready')
                    and isinstance(submission, dict) and submission.get('status') == 'deferred'):
                reason = ('native resource unavailable; announcement not submitted, '
                          'automatic retry pending')
            elif (self._presentation_status in ('queued', 'waiting_ready')
                    and isinstance(submission, dict) and submission.get('status') == 'refused'):
                reason = ('native refusal without action; automatic retry once the '
                          'presentation conditions are back')
            if self._presentation_status in ('refused', 'uncertain'):
                reason = ('presentation queue blocked (' + self._presentation_status
                          + '); follow the /ap-replay command given')
                session = getattr(self, 'presentations', None)
                head = session.blocked_head() if session is not None else None
                if head and 'replay_after_incarnation' in head:
                    reason = ('replay already authorized; waiting for the restart '
                              'and the native presentation conditions; '
                              'do not repeat /ap-replay')
            self.log(f"deliveries waiting ({queues}): "
                     f"{reason}")
            self._next_delivery_wait_log = now + 5.0

    async def _apply_one_received(self):
        if not getattr(self.ap, "items_synchronized", True):
            return
        if not self.state["apply_queue"] or not self._safe_now():
            return
        index = int(self.state["apply_queue"][0])
        item = self.ap.received_items.get(index)
        if item is None:
            return
        name = self.ap.item_name(item)
        if not name:
            raise FatalClientError(f"AP item {item.item} without a name in the data package")
        if name not in self.game.item_map:
            raise FatalClientError(f"AP item without a BOTW action: {name}")
        before = self._received_before(index, name)
        cursor_index, step = self._delivery_position()
        if cursor_index != index:
            return
        action_count = self.game.item_action_count(name)
        if step > action_count:
            raise FatalClientError(
                f"AP cursor #{index}: invalid step {step}/{action_count}")
        if step < action_count:
            await asyncio.to_thread(self.game.apply_item_step, name, step, before)
            step += 1
            if step < action_count:
                await asyncio.to_thread(self._set_delivery_position, index, step)
            self.state_store.save()
        if step == action_count:
            await asyncio.to_thread(self._set_delivery_position, index + 1, 0)
            if index not in self.state["applied"]:
                self.state["applied"].append(index)
                self.state["applied"].sort()
            self.state["apply_queue"].remove(index)
            self.state["steps"].clear()
            self.state_store.save()
            self.log(f"item applied #{index}: {name}")

    async def _apply_one_received_native(self):
        if (not self.native_delivery or self.deliveries is None
                or not getattr(self.ap, "items_synchronized", True)
                or not self.state["apply_queue"]
                or time.monotonic() < self._native_delivery_retry_after):
            return
        checkpoint = await asyncio.to_thread(self.deliveries.backend.checkpoint)
        index, step = checkpoint.cursor >> 8, checkpoint.cursor & 0xFF
        if int(self.state["apply_queue"][0]) != index:
            return
        if (self.native_presentations
                and index not in self.state["presentation_completed"]):
            return
        item = self.ap.received_items.get(index)
        if item is None:
            return
        name = self.ap.item_name(item)
        if not name:
            raise FatalClientError(f"AP item {item.item} without a name in the data package")
        before = self._received_before(index, name)
        try:
            steps = self.deliveries.backend.catalog.steps(name, before)
        except (KeyError, ValueError) as exc:
            raise FatalClientError(f"AP item without a native delivery: {exc}") from exc
        if step >= len(steps):
            raise FatalClientError(
                f"AP cursor #{index}: invalid step {step}/{len(steps)}")
        restored = index < int(self.state.get("delivered_high", 0))
        quiet = restored or self._bulk(index)
        # A step hosted in the quiet flowchart has no window of its own
        # (Sheikah Sensor, horse gear): given quietly, it is named by the summary.
        catalog_flow = getattr(self.deliveries.backend.catalog, "data", {}).get("flow")
        windowless = steps[step].get("flow") not in (None, catalog_flow)
        silent = quiet and (bool(steps[step].get("quiet_entry")) or windowless)
        if (not restored and self._bulk(index) and not self.state.get("bulk_batch")
                and not getattr(self, "_bulk_told", False)):
            # Their lines are not shown: the journal says they are coming.
            count = sum(1 for value in self.state["apply_queue"] if self._bulk(int(value)))
            self._journal_note(f"{{1}}{count} items{{/}} of a release on their way, "
                               "listed once all are given")
            self._bulk_told = True
        # Dropped at Link's feet, the pouch full: what is left is the commit.
        dropped = (self.state.get("drop_cursor") == checkpoint.cursor
                   and bool(steps[step].get("drop_entry")))
        command = DeliveryCommand(
            self._session_identity[0], self._session_identity[2], index, name,
            step, len(steps), before, quiet=quiet,
            pickup=self._repeat_filler(index) and not dropped, drop=dropped)
        result = await asyncio.to_thread(self.deliveries.deliver, command)
        if result.status in (DeliveryStatus.APPLIED,
                             DeliveryStatus.ALREADY_APPLIED):
            if dropped:
                self.state.pop("drop_cursor", None)
                self.state_store.save()
            trap = next((m for m in steps[step].get("mutations", ())
                         if m.get("kind") in ("trap", "native_trap")), None)
            if trap is not None:
                if not silent:
                    # The trap has no window: the journal says what it did. Given
                    # back after a reload, it is spent without effect and without a word.
                    from .ap_journal import trap_line
                    self._journal_note(trap_line(name, trap["value"]))
                    if trap["kind"] == "native_trap":
                        # Committed: the client plays it (_native_trap_tick).
                        self._native_traps.append(trap["target"])
            elif silent and step == 0:
                # Given back, or sent by a release, without its window: named
                # in one AP summary.
                batch = "replay_batch" if restored else "bulk_batch"
                self.state.setdefault(batch, []).append(name)
                self.state_store.save()
            elif command.pickup:
                actor = self._pickup_actor(name)
                if actor:
                    self._pickups.append((actor, PICKUP_ATTEMPTS))
            self._native_delivery_retry_after = 0.0
            self._discover_received()
            self.log(f"native step committed #{index}/{step}: {name}"
                     + (f" ({result.detail})" if result.detail else ""))
            return
        if result.status is DeliveryStatus.DEFERRED:
            self.game.delivery_block_reason = (
                'delivery deferred; automatic retry'
                + (f' ({result.detail})' if result.detail else ''))
            self._native_delivery_retry_after = time.monotonic() + 0.5
            return
        if result.status is DeliveryStatus.INVENTORY_FULL:
            self.game.delivery_block_reason = result.detail or "inventory full"
            actor = steps[step].get("capacity_actor")
            if steps[step].get("drop_entry") and actor:
                # The game said "pouch full": the item falls at Link's feet
                # and the queue goes on (botw_client/item_drop.py). Created
                # first, committed after: a crash between gives it twice.
                outcome = await asyncio.to_thread(self.deliveries.backend.drop_item, actor)
                if outcome == "ok":
                    self.state["drop_cursor"] = checkpoint.cursor
                    self.state_store.save()
                    self._journal_note(f"Pouch full: {{1}}{name}{{/}} fell at your feet")
                    self.log(f"native step #{index}/{step}: {name} dropped at Link's feet")
                    self._native_delivery_retry_after = 0.0
                else:
                    self.log(f"native step #{index}/{step}: {name} not dropped ({outcome})")
                    self._native_delivery_retry_after = time.monotonic() + 5.0
                return
            self._native_delivery_retry_after = time.monotonic() + 5.0
            return
        raise FatalClientError(
            f"native delivery #{index}/{step} blocked ({result.status.value}): "
            f"{result.detail}")

    async def _show_one_location_reward(self) -> bool:
        if self.native_presentations:
            raise RuntimeError('Legacy display is disabled in native presentation mode')
        if not self.state["location_display_queue"] or not self._safe_now():
            return False
        location_id = int(self.state["location_display_queue"][0])
        info = self.ap.scouted_locations.get(location_id)
        if info is None:
            return False
        name = self.ap.item_name(info)
        if not name:
            name = f"Item #{info.item}"
        recipient, recipient_game = self.ap.sender(info)
        location = self.ap.location_name(location_id) or str(location_id)
        displayed = await asyncio.to_thread(
            self.game.show_location_reward, name, recipient, recipient_game, location)
        if displayed:
            self.state["location_display_queue"].remove(location_id)
            if location_id not in self.state["location_shown"]:
                self.state["location_shown"].append(location_id)
                self.state["location_shown"].sort()
            self.state_store.save()
            self.log(f"reward shown: {location} -> {name} ({recipient})")
            return True
        return False

    async def _show_one_received(self):
        if self.native_presentations:
            raise RuntimeError('Legacy display is disabled in native presentation mode')
        if not self.state["display_queue"] or not self._safe_now():
            return False
        index = int(self.state["display_queue"][0])
        item = self.ap.received_items.get(index)
        if item is None:
            return False
        # A local item found at one of our locations was already presented
        # using LocationInfo. Apply it, but do not open a duplicate window.
        if (item.player == self.ap.slot
                and item.location in {int(value) for value in self.state["location_shown"]}):
            displayed = True
        else:
            name = self.ap.item_name(item)
            sender, sender_game = self.ap.sender(item)
            delivery = self.game.item_map[name]["delivery"]
            extra = delivery.get("text") if delivery["kind"] == "manual_prompt" else None
            displayed = await asyncio.to_thread(
                self.game.show_received, name, sender, sender_game, extra)
        if displayed:
            self.state["display_queue"].remove(index)
            if index not in self.state["shown"]:
                self.state["shown"].append(index)
                self.state["shown"].sort()
            self.state_store.save()
            self.log(f"item shown #{index}: {self.ap.item_name(item)}")
            return True
        return False

    def _queue_location_display(self, name: str):
        location_id = self.ap.location_id_by_name[name]
        # Victory locations have no randomized item and cannot be scouted.
        if location_id not in self.ap.scouted_locations:
            return
        shown = {int(value) for value in self.state["location_shown"]}
        queued = {int(value) for value in self.state["location_display_queue"]}
        if location_id not in shown and location_id not in queued:
            self.state["location_display_queue"].append(location_id)

    def _acknowledge_checks(self):
        pending = self.state.get("pending_checks", [])
        kept = [name for name in pending
                if self.ap.location_id_by_name.get(name) not in self.ap.checked_locations]
        if kept != pending:
            self.state["pending_checks"] = kept
            self.state_store.save()

    async def _flush_checks(self):
        if not self.ap.connected:
            return
        self._acknowledge_checks()
        if not self.state["pending_checks"]:
            return
        now = time.monotonic()
        if now - self.last_check_send < CHECK_RESEND_SECONDS:
            return
        unresolved = await self.ap.send_checks(list(self.state["pending_checks"]))
        if unresolved:
            raise FatalClientError(
                "locations missing from the data package: " + ", ".join(unresolved))
        self.last_check_send = now

    def _versions_hint(self) -> str:
        """What to do when this version cannot play the room's seed."""
        from .version import VERSION
        made = self.ap.slot_data.get("world_version", "an earlier version")
        return (f"The seed was generated with the Breath of the Wild world {made}; this is {VERSION}: "
                "play it with the BOTW Archipelago release of the seed's version.")

    def _world_schema(self) -> int:
        """Location schema of the connected seed (see botw_client/locations.py)."""
        if self.ap.game == "Breath of the Wild":
            # Absent only in slot data older than the schema field: the oldest.
            schema = int(self.ap.slot_data.get("world_schema", 1))
            if schema not in SCHEMA_LOCATION_COUNTS:
                raise FatalClientError(
                    f"slot_data world_schema={schema}; {sorted(SCHEMA_LOCATION_COUNTS)} "
                    "accepted. " + self._versions_hint())
            return schema
        # Manual declares no schema: its data package tells which rows it has
        # (the newest schema all of whose names it knows).
        known = set(self.ap.location_id_by_name) | {GOAL_LOCATION}
        return max(schema for schema in SCHEMA_LOCATION_COUNTS
                   if schema == 1 or {target.name for target in load_targets(
                       world_schema=schema)} <= known)

    async def _poll_shops(self):
        """Seeing a Beedle's list hints the AP items he sells, looking at a
        stall's AP medallion hints its item (once per location)."""
        seed = getattr(self.ap, "seed_locations", set())
        poll = getattr(self.game, "poll_shop", None)
        if not seed or poll is None:
            return
        seen = await asyncio.to_thread(poll)
        hinted = self.state.setdefault("shop_hints", [])
        new = sorted((set(seen) & seed) - set(hinted) - self.ap.checked_locations)
        if new:
            await self.ap.send_hints(new)
            hinted.extend(new)
            self.state_store.save()
            self.log(f"shop seen: hints for {len(new)} item(s)")

    async def _poll_locations(self):
        names = await asyncio.to_thread(self.game.poll_locations)
        if names and self._session_locations is not None:
            # A check absent from this seed (older world schema) is not sent.
            ignored = [name for name in names if name not in self._session_locations]
            if ignored:
                self.log("not in this seed, ignored: " + ", ".join(ignored))
                names = [name for name in names if name in self._session_locations]
        if names:
            for name in names:
                if name not in self.state["observed_checks"]:
                    self.state["observed_checks"].append(name)
                if name == GOAL_LOCATION and self.ap.game == "Breath of the Wild":
                    self.state["goal_observed"] = True
                    continue
                vanilla_rune = TERMINAL_ITEMS.get(name)
                owns_rune = vanilla_rune and any(
                    self.ap.item_name(item) == vanilla_rune
                    for item in self.ap.received_items.values())
                if vanilla_rune and not owns_rune and not self.native_mode:
                    await asyncio.to_thread(self.game.suppress_terminal_rune, name)
                    self.log(f"vanilla rune suppressed: {vanilla_rune}")
                if name == "Great Plateau Tower" and not self.native_mode:
                    owns_sensor = any(
                        self.ap.item_name(item) == "Sheikah Sensor"
                        for item in self.ap.received_items.values())
                    if not owns_sensor:
                        await asyncio.to_thread(self.game.suppress_tower_sensor)
                        self.log("vanilla shrine sensor suppressed")
                if name not in self.state["pending_checks"]:
                    self.state["pending_checks"].append(name)
                    self._queue_location_display(name)
                    self.log(f"check detected: {name}")
                if name == "Master Sword Pedestal":
                    await self._close_pedestal()
            self.safe_after = max(
                self.safe_after,
                time.monotonic() + max(event_settle_seconds(name)
                                       for name in names))
            self.state_store.save()
        await self._flush_checks()
        if self._goal_reached() and self.ap.connected and not self.state.get("goal_sent"):
            await self.ap.send_goal()
            self.state["goal_sent"] = True
            self.state_store.save()
            self.log("Archipelago goal sent")

    def _known_checks(self) -> set[str]:
        known = set(self.state.get("observed_checks", []))
        known.update(self.ap.location_name(i) for i in self.ap.checked_locations)
        return known

    def _goal_reached(self) -> bool:
        """The seed's goal (botw_world/options.py): Ganon defeated, the four
        Divine Beasts freed, or the goal's shrines cleared."""
        slot_data = getattr(self.ap, "slot_data", None) or {}
        if "goal" in slot_data:                     # client schema 5
            goal, known = int(slot_data["goal"]), self._known_checks()
            if goal == 1:
                return sum(bool(n and n.startswith("Divine Beast")) for n in known) >= 4
            if goal == 2:
                return (sum(bool(n and n.endswith(" Shrine")) for n in known)
                        >= int(slot_data.get("goal_shrines", 60)))
        ganon = (self.state.get("goal_observed")
                 or GOAL_LOCATION in self.state["pending_checks"])
        return bool(ganon) and all(have >= need for _w, have, need in self._sanctum_requirements())

    def _sanctum_requirements(self) -> list[tuple[str, int, int]]:
        """What the seed asks before Ganon's sanctum opens, met or not: (what,
        have, need). Seeds of client schema 4 asked it through goal_type."""
        slot_data = getattr(self.ap, "slot_data", None) or {}
        if "goal" in slot_data:
            beasts = int(slot_data.get("sanctum_divine_beasts", 0))
            shrines = int(slot_data.get("sanctum_shrines", 0))
            sword = bool(slot_data.get("sanctum_master_sword"))
            runes = bool(slot_data.get("sanctum_runes"))
        else:
            goal_type = int(slot_data.get("goal_type", 0))
            beasts = int(slot_data.get("divine_beasts_required", 4)) if goal_type == 1 else 0
            shrines = int(slot_data.get("shrines_required", 40)) if goal_type == 2 else 0
            sword = bool(slot_data.get("ganon_master_sword"))
            runes = bool(slot_data.get("ganon_runes"))
        known = self._known_checks()
        received = {self.ap.item_name(item) for item in
                    (getattr(self.ap, "received_items", None) or {}).values()}
        out = []
        if beasts:
            out.append(("Divine Beasts freed",
                        sum(bool(n and n.startswith("Divine Beast")) for n in known), beasts))
        if shrines:
            out.append(("shrines cleared", sum(bool(n and n.endswith(" Shrine")) for n in known), shrines))
        if runes:
            out.append(("runes", len(received & set(RUNE_NAMES)), len(RUNE_NAMES)))
        if sword:
            out.append(("Master Sword", int("Master Sword" in received), 1))
        return out

    async def _close_pedestal(self):
        """Its sword maybe taken without the pull (botw_client/locations.ALTERNATE_FLAGS):
        the pedestal is closed as the pull closes it, by the pack's entry
        (botw_patch/pedestal.py), asked by _pedestal_tick when the game is
        ready. A pack built before it: the flag written live, for this session."""
        backend = getattr(self.deliveries, "backend", None) if self.deliveries else None
        catalog = getattr(backend, "catalog", None)
        found = catalog.pedestal_entry() if catalog is not None and hasattr(catalog, "pedestal_entry") else None
        if found is not None:
            if self._pedestal_flags is None:
                self._pedestal_flags, self._pedestal_requested = found[2], False
            return
        close = getattr(self.game, "close_master_sword_pedestal", None)
        if close is None:
            return
        try:
            if await asyncio.to_thread(close):
                self.log("Master Sword pedestal: its sword taken without the pull, pull marked done")
        except Exception as exc:  # noqa: BLE001 - the check is sent anyway
            self.log(f"Master Sword pedestal not closed: {exc}")

    async def _pedestal_tick(self):
        """The pedestal's entry asked while one of the pull's flags is unset,
        after the deliveries; checked again until the flags are all set."""
        flags = self._pedestal_flags
        if (not flags or self.deliveries is None or self.state is None or self.state["apply_queue"]
                or time.monotonic() < self._pedestal_retry_after):
            return
        try:
            still_open = await asyncio.to_thread(self.game.master_sword_pedestal_open, flags)
        except Exception as exc:  # noqa: BLE001 - asked again later
            self.log(f"Master Sword pedestal not read: {exc}")
            self._pedestal_retry_after = time.monotonic() + 5.0
            return
        if not still_open:
            if self._pedestal_requested:
                self.log("Master Sword pedestal closed: no pull from the next load of its area on")
            self._pedestal_flags = None
            return
        result = await asyncio.to_thread(self.deliveries.backend.request_pedestal_close)
        if result is False:
            self._pedestal_retry_after = time.monotonic() + 2.0
            return
        if not self._pedestal_requested:
            self.log("Master Sword pedestal: its sword taken without the pull, closing it as the pull does")
        self._pedestal_requested = True
        # Read again once the entry has run; asked again if it did not.
        self._pedestal_retry_after = time.monotonic() + 10.0

    async def _ganon_gate_tick(self):
        """The sanctum's gate (botw_patch/ganon_gate.py): opened once the seed's
        requirements are met; a refusal is explained in the AP journal."""
        if (self._gate_unavailable or time.monotonic() < self._gate_retry_after
                or not getattr(self.ap, "slot_data", None)):
            return
        self._gate_retry_after = time.monotonic() + 1.0
        gate = getattr(self.game, "ganon_gate", None)
        try:
            state = await asyncio.to_thread(gate) if gate is not None else None
        except Exception as exc:  # noqa: BLE001 - the gate must not stop the session
            self.log(f"sanctum gate unreadable: {exc}")
            return
        if state is None:
            self._gate_unavailable = True
            self.log("this pack has no sanctum gate: rebuild it with tools/play_seed.py")
            return
        is_open, refused = state
        missing = [need for need in self._sanctum_requirements() if need[1] < need[2]]
        if not missing and not is_open:
            await asyncio.to_thread(self.game.open_ganon_gate)
            self.log("sanctum unsealed: the seed's requirements are met")
        if refused:
            from .ap_journal import ganon_sealed_line
            self._journal_note(ganon_sealed_line(missing))
            await asyncio.to_thread(self.game.clear_ganon_refusal)
            self.log("sanctum refused: " + (", ".join(f"{h}/{n} {w}" for w, h, n in missing)
                                           or "now open"))

    @staticmethod
    def _message_pages(text: str) -> list[str]:
        """Return one safe center-channel message; never paginate a packet."""
        clean = " ".join(literal_text(text).split())
        if not clean:
            return []
        if len(clean.encode('utf-16-be')) > MESSAGE_MAX_CHARS * 2:
            clean = clip_units(clean, MESSAGE_MAX_CHARS - 3).rstrip() + "..."
        return [clean]

    def _collect_messages(self):
        changed = False
        while True:
            try:
                message = self.ap.messages.get_nowait()
            except asyncio.QueueEmpty:
                break
            text = queued_text(message.text)
            if text:
                self.state["message_queue"].append({
                    "text": text, "kind": literal_text(message.kind),
                    "nodes": literal_metadata(message.nodes), "received_at": time.time(),
                    "receiving": getattr(message, "receiving", None),
                    "sender": getattr(message, "sender", None),
                    "slot": getattr(message, "slot", None)})
            self.state["message_queue"] = self.state["message_queue"][-100:]
            changed = True
        if changed:
            self.state_store.save()

    async def _show_one_message(self):
        # The historical center channel has no owned lifecycle. Keep this guard
        # here as well as in the caller so a future scheduler cannot enable it.
        if (self.native_mode or not self.state["message_queue"] or not self._safe_now()
                or time.monotonic() < self._next_message_after):
            return
        entry = self.state["message_queue"][0]
        text = entry.get("text", "") if isinstance(entry, dict) else str(entry)
        pages = self._message_pages(text)
        if not pages or await asyncio.to_thread(self.game.show_ap_message, pages[0]):
            self.state["message_queue"].pop(0)
            self._next_message_after = time.monotonic() + MESSAGE_SETTLE_SECONDS
            self.state_store.save()

    async def _deathlink_tick(self):
        """DeathLink, both ways (native delivery only).

        Out: Link's death (game.is_dead, measured) is sent once, on its edge,
        or when AP comes back if it happened offline, with what killed him
        (botw_client/death_cause.py). A death the received DeathLink caused is
        not sent back.
        In: the latest received death waits for a safe moment, is announced
        in the journal, then kills Link through the pack's entry
        (botw_patch/death_link.py). The game's protections apply: Mipha's
        Grace or a fairy may save him, which spends the DeathLink."""
        state = self.state
        changed = False
        while True:
            try:
                event = self.ap.deathlinks.get_nowait()
            except asyncio.QueueEmpty:
                break
            if event.timestamp <= float(state.get("last_death_link") or 0.0):
                continue
            state["last_death_link"] = event.timestamp
            self.log(f"DeathLink received from {event.source}: {event.cause or '(no cause)'}")
            if self.ap.death_link_enabled:
                # Deaths received while one waits are one death.
                state["pending_deathlinks"] = [{
                    "time": event.timestamp, "source": event.source,
                    "cause": event.cause, "received_at": time.time()}]
                self._deathlink_announced_at = None
            changed = True
        if changed:
            self.state_store.save()

        try:
            dead = await asyncio.to_thread(self.game.is_dead)
        except Exception:  # noqa: BLE001 - health unreadable (loading): next tick
            return
        if not dead:
            self._alive_seen = True
        if (self.ap.death_link_enabled and self._alive_seen and dead
                and self._last_dead is False):
            if await self._killed_by_death_link():
                self.log("Link died of the received DeathLink: not sent back")
            elif await self._killed_by_trap():
                self.log("Link died of a Cucco Swarm trap: not sent as a DeathLink")
            else:
                cause = await self._death_cause()
                if self.ap.connected:
                    await self.ap.send_death(cause)
                else:
                    state["pending_outgoing_death"] = cause
                    self.state_store.save()
        self._last_dead = dead

        pending_out = state["pending_outgoing_death"]
        if self.ap.connected and self.ap.death_link_enabled and pending_out:
            await self.ap.send_death(pending_out if isinstance(pending_out, str)
                                     else f"{self.ap.slot_name} died in Hyrule")
            state["pending_outgoing_death"] = False
            self.state_store.save()

        pending = state["pending_deathlinks"]
        if (not pending or dead or self._swarming()
                or time.monotonic() < self._deathlink_retry_after):
            return
        event = pending[0]
        received = event.get("received_at")
        if (not self.ap.death_link_enabled or type(received) not in (int, float)
                or time.time() - received > DEATHLINK_EXPIRY_SECONDS):
            pending.clear()
            self._deathlink_announced_at = None
            self.state_store.save()
            return
        if self._deathlink_announced_at is None:
            if not await asyncio.to_thread(self.game.safe_for_delivery):
                return
            from .ap_journal import death_link_line
            self._journal_note(death_link_line(event["source"], event["cause"]))
            self._deathlink_announced_at = time.monotonic()
            return
        if time.monotonic() - self._deathlink_announced_at < DEATHLINK_LEAD_SECONDS:
            return
        request = getattr(getattr(self.deliveries, "backend", None), "request_death", None)
        result = await asyncio.to_thread(request) if request is not None else None
        if result is False:
            self._deathlink_retry_after = time.monotonic() + 1.0
            return
        pending.clear()
        self._deathlink_announced_at = None
        self.state_store.save()
        if result is None:
            self.log("DeathLink not applied: this pack has no DeathLink entry; "
                     "rebuild it with tools/play_seed.py")
            return
        self._death_requested_at = time.monotonic()
        self.log(f"DeathLink applied: {event['source']}")

    async def _killed_by_trap(self) -> bool:
        """Did a Cucco Swarm the client played kill Link? While its attackers may
        be around, a death whose last attacker is one of them is the trap's."""
        if not self._swarming() and self._swarm_left <= 0:
            return False
        from .cucco_swarm import ATTACKER
        ask = getattr(getattr(self.deliveries, "backend", None), "last_attacker", None)
        try:
            killer = await asyncio.to_thread(ask) if ask is not None else None
        except Exception:  # noqa: BLE001 - unreadable: a death like any other
            killer = None
        return killer == ATTACKER

    def _pickup_actor(self, name: str) -> str | None:
        """The actor of the game's pickup notification for this item, if the
        item map opts in ("pickup": rupees have their counter)."""
        entry = getattr(self.game, "item_map", {}).get(name) or {}
        return entry.get("display_actor") if entry.get("pickup") else None

    async def _pickup_tick(self):
        """One pickup notification per tick, once Link is back in the world.
        Never fatal: a notification refused or lost is only not seen."""
        if not self._pickups:
            return
        show = getattr(getattr(self.deliveries, "backend", None), "show_pickup", None)
        if show is None:
            self._pickups.clear()
            return
        actor, attempts = self._pickups[0]
        shown = await asyncio.to_thread(show, actor)
        if shown is False and attempts > 1:
            self._pickups[0] = (actor, attempts - 1)
            return
        self._pickups.pop(0)
        if shown is not True:
            self.log(f"pickup notification not shown: {actor}")

    async def _native_trap_tick(self):
        """Plays the committed native traps, one at a time. Not kept across a
        restart of the client: a trap committed but not played is spent."""
        from .cucco_swarm import ALIVE
        task = self._native_trap_task
        if task is None and self._swarm_left > 0:
            await self._swarm_window_tick()
        if task is not None:
            if not task.done():
                return
            self._native_trap_task = None
            try:
                self.log(f"Cucco Swarm played: {task.result()}")
            except Exception as exc:  # noqa: BLE001 - a trap never stops the client
                self.log(f"Cucco Swarm failed: {exc!r}")
            self._swarm_left, self._swarm_clock = ALIVE + 3.0, time.monotonic()
            return
        if not self._native_traps:
            return
        play = getattr(getattr(self.deliveries, "backend", None), "cucco_swarm", None)
        if play is None:
            self._native_traps.clear()
            return
        # No safety check of its own: the trap is queued at its commit, which
        # happened at a safe moment.
        effect = self._native_traps.pop(0)
        if effect != "cucco_swarm":
            self.log(f"native trap without an effect in this client: {effect}")
            return
        self._swarm_stop.clear()
        self._native_trap_task = asyncio.create_task(
            asyncio.to_thread(play, self._swarm_should_stop), name="Cucco Swarm")

    async def _swarm_window_tick(self):
        """The last attackers' time runs out only while Link is in the world:
        in a menu they stand still, and may still kill once it closes."""
        now, before = time.monotonic(), self._swarm_clock
        self._swarm_clock = now
        playing = getattr(getattr(self.deliveries, "backend", None), "playing", None)
        try:
            in_world = await asyncio.to_thread(playing) if playing is not None else True
        except Exception:  # noqa: BLE001 - unreadable (loading): time stands still
            in_world = False
        if in_world:
            self._swarm_left -= now - before

    def _swarming(self) -> bool:
        """A swarm is playing: it has the invoker, the loop's events wait."""
        task = self._native_trap_task
        return task is not None and not task.done()

    def _swarm_should_stop(self) -> bool:
        """Asked by the swarm's thread before each attacker."""
        if self.stop_event.is_set() or self._swarm_stop.is_set():
            return True
        try:
            return bool(self.game.is_dead())
        except Exception:  # noqa: BLE001 - unreadable: the stop of the loop decides
            return False

    async def _end_swarm(self):
        """The loop leaves: the swarm stops at its next attacker, and is waited
        for, so that it never uses a game connection being closed."""
        task = self._native_trap_task
        if task is None:
            return
        self._swarm_stop.set()
        await asyncio.wait([task])
        await self._native_trap_tick()

    async def _killed_by_death_link(self) -> bool:
        """Did the DeathLink we requested cause this death? A death within
        DEATHLINK_ECHO_SECONDS of the request is its; later, its flag says so.
        A death so recognised uses the request up.

        Seen in a room: a death in the second the DeathLink applied was sent
        back, its flag read as not set; the time alone keeps it home."""
        if self._death_requested_at is None:
            return False
        since = time.monotonic() - self._death_requested_at
        ask = getattr(getattr(self.deliveries, "backend", None), "killed_by_death_link", None)
        try:
            flag = await asyncio.to_thread(ask) if ask is not None else None
        except Exception:  # noqa: BLE001 - unreadable: the time decides
            flag = None
        ours = since < DEATHLINK_ECHO_SECONDS or bool(flag and since < DEATHLINK_FLAG_SECONDS)
        if ours:
            self._death_requested_at = None
        return ours

    async def _death_cause(self) -> str:
        """The cause sent with Link's death: what killed him, when the game says."""
        default = f"{self.ap.slot_name} died in Hyrule"
        read = getattr(getattr(self.deliveries, "backend", None), "death_cause", None)
        if read is None:
            return default
        try:
            return await asyncio.to_thread(read, self.ap.slot_name) or default
        except Exception:  # noqa: BLE001 - memory unreadable: the plain cause
            return default

    async def _reconnect_after(self, delay: float):
        await self._wait_or_stop(delay)
        if self.stop_event.is_set():
            return
        await self._connect_ap()

    async def _reconnect_tick(self):
        if self._reconnect_task is None:
            if self.ap.connected:
                self._reconnect_delay = 1.0
                return
            if self._offline_since is None:
                # Once per outage, not once per retry.
                self._offline_since = time.monotonic()
                self._journal_note("{0}Archipelago connection lost{/}: "
                                   "the game goes on, checks will be sent "
                                   "on reconnection.")
            self._reconnect_task = asyncio.create_task(
                self._reconnect_after(self._reconnect_delay),
                name="AP reconnect")
            return
        if not self._reconnect_task.done():
            return
        task, self._reconnect_task = self._reconnect_task, None
        try:
            await task
            if self.ap.connected:
                self.log("Archipelago reconnected; offline checks resumed")
                self._journal_note(f"{{1}}Reconnected{{/}} to Archipelago "
                                   f"{offline_duration(self._offline_since)}")
                self._offline_since = None
                self._reconnect_delay = 1.0
        except FatalClientError:
            raise
        except Exception as exc:
            self.log(f"Archipelago offline: {exc}; retrying in "
                     f"{self._reconnect_delay:.0f}s")
            await self.ap.close()
            self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)

    def _hud_tick(self):
        """The HUD logo follows the AP connection (at most twice a second)."""
        if self.hud is None or time.monotonic() < self._hud_next:
            return
        self._hud_next = time.monotonic() + 0.5
        online = bool(self.ap.connected)
        before = self.hud.shown
        try:
            done = self.hud.show(online)
        except Exception as exc:  # noqa: BLE001 - a HUD logo never stops the client
            if str(exc) != self._hud_error:
                self._hud_error = str(exc)
                self.log(f"HUD indicator unavailable: {exc}")
            return
        if done and before is None:
            self.log("HUD indicator: " + ("connected" if online else "offline"))

    async def _status_item_tick(self):
        """Once per game connection, after the deliveries: the pack's
        Archipelago key item (seed, slot, goal) if the pouch lacks it."""
        if (self._status_item_done or self.deliveries is None or self.state is None
                or self.state["apply_queue"]
                or time.monotonic() < self._status_item_retry_after):
            return
        ask = getattr(self.deliveries.backend, "request_status_item", None)
        result = await asyncio.to_thread(ask) if ask is not None else None
        if result is False:
            self._status_item_retry_after = time.monotonic() + 2.0
            return
        self._status_item_done = True
        if result:
            self.log("Archipelago key item (seed, slot, goal) checked in the inventory")

    # --- AP journal (tip frame) ------------------------------------------------

    def _journal_note(self, markup: str, tag: int | None = None):
        """A line of the client's own: connection status, console test, or the
        announcement of received item `tag` (kept whatever the backlog)."""
        if getattr(self, 'tip_factory', None) is not None:
            self._journal_notes.append((markup, tag))
            untagged = [n for n in self._journal_notes if n[1] is None]
            if len(untagged) > 20:
                self._journal_notes.remove(untagged[0])

    def _journal_next_pages(self) -> list[tuple[str, int | None]]:
        from .ap_journal import journal_line
        from .tip_channel import pages
        if self._journal_notes:
            markup, tag = self._journal_notes.pop(0)
            out = pages(markup)
            # The tag goes with the last page: announced once fully shown.
            return [(page, tag if i == len(out) - 1 else None) for i, page in enumerate(out)]
        from .ap_journal import is_received_item
        queue = self.state["message_queue"]
        position = 0
        while position < len(queue):
            entry = queue[position]
            received = entry.get("received_at") if isinstance(entry, dict) else None
            fresh = (type(received) in (int, float) and received >= self._journal_started
                     and time.time() - received <= 300)
            if fresh and is_received_item(entry, self.ap.slot):
                if not self._bulk_line(entry):
                    position += 1           # waits for its item's presentation
                    continue
                queue.pop(position)         # a release's item: the summary names it
                self.state_store.save()
                continue
            queue.pop(position)
            self.state_store.save()
            if not fresh:                   # only this session's, recent messages
                continue
            line = journal_line(entry, self.ap.slot, self.ap.render_node,
                                chat=self.journal_chat, everyone=self.journal_everyone)
            if line:
                return [(page, None) for page in pages(line)]
        return []

    async def _journal_tick(self):
        """One tip at a time; the next only once the game closed the last one."""
        tips = self.tips
        if tips is None:
            return
        status = await asyncio.to_thread(tips.poll)
        if status is None:
            return
        if status == "dropped" and self._journal_current is not None:
            self._journal_pages.insert(0, self._journal_current)
        self._journal_current = None
        if not self._journal_pages:
            self._journal_pages = self._journal_next_pages()
        if not self._journal_pages or time.monotonic() < self._journal_retry_after:
            return
        # Not _safe_now(), which waits for SAFE_STABLE_SECONDS of a still UI:
        # in_world() is the stateless presentation guard.
        if not await asyncio.to_thread(tips.in_world):
            self._journal_retry_after = time.monotonic() + 0.5
            return
        page, tag = self._journal_pages[0]
        result = await asyncio.to_thread(tips.submit, page)
        if result == "accepted":
            self._journal_current = self._journal_pages.pop(0)
            if tag is not None:
                announced = self.state.setdefault("journal_announced", [])
                if tag not in announced:
                    announced.append(tag)
                    self.state_store.save()
                self._journal_times[tag] = time.monotonic()
        elif result == "invalid":
            self.log("AP journal: page refused by the native channel, skipped")
            self._journal_pages.pop(0)
        else:
            self._journal_retry_after = time.monotonic() + 1.0

    def _received_announcement(self, index: int) -> str:
        """Presentation session hook: an item received from another player is
        first announced in the journal ("Alice sent Hookshot to Bob"), then
        shown by its vanilla window if its delivery has one (GetDemo: hearts,
        stamina, rupees), else by the usual AP window."""
        item = self.ap.received_items.get(index)
        if item is None:
            return 'present'
        if self._bulk(index):
            # Named by the summary window once given: its line is dropped.
            self._drop_received_line(item)
            return 'skip'
        if self.tips is None:
            return 'pending'
        if index not in self.state.setdefault("journal_announced", []):
            if index not in self._journal_queued:
                line = self._received_line(index, item)
                if line is None:
                    return 'pending'      # the server's line may still come
                self._journal_queued.add(index)
                self._journal_queued_at[index] = time.monotonic()
                self._journal_note(line, tag=index)
            queued = self._journal_queued_at.get(index)
            if queued is None or time.monotonic() - queued < JOURNAL_BLOCK_SECONDS:
                return 'pending'
            # The frame stays taken: the item does not wait for its line.
            return 'skip' if self._vanilla_window(index) or self._repeat_filler(index) else 'present'
        if self._repeat_filler(index):
            return 'skip'          # no window to read the line before: at once
        shown = self._journal_times.get(index)
        if shown is not None and time.monotonic() - shown < JOURNAL_LEAD_SECONDS:
            return 'pending'
        return 'skip' if self._vanilla_window(index) or self._repeat_filler(index) else 'present'

    def _received_line(self, index: int, item) -> str | None:
        """The server's own line for this item (PrintJSON ItemSend), taken out
        of the queue; after JOURNAL_SERVER_WAIT_SECONDS without one (items
        received offline, console /send), the same sentence in the server's
        format."""
        from .ap_journal import coloured, matches_item
        queue = self.state["message_queue"]
        for position, entry in enumerate(queue):
            if matches_item(entry, self.ap.slot, item):
                queue.pop(position)
                self.state_store.save()
                return coloured(entry, self.ap.render_node)
        first = self._journal_waiting.setdefault(index, time.monotonic())
        if time.monotonic() - first < JOURNAL_SERVER_WAIT_SECONDS:
            return None
        name = self.ap.item_name(item) or f"#{item.item}"
        me = self.ap.players.get(self.ap.slot, self.ap.slot_name)
        if item.player == 0:
            return f"{{1}}{name}{{/}} sent to {{2}}{me}{{/}} by the server"
        sender, game = self.ap.sender(item)
        location = self.ap.location_names_by_game.get(game, {}).get(item.location)
        where = f" ({location})" if location else ""
        if item.player == self.ap.slot:
            return f"{{2}}{me}{{/}} found their {{1}}{name}{{/}}{where}"
        return f"{{2}}{sender}{{/}} sent {{1}}{name}{{/}} to {{2}}{me}{{/}}{where}"

    def _repeat_filler(self, index: int) -> bool:
        """A filler item (AP flags 0: rupees, materials) received before: its
        journal line alone, delivered without a window nor a pause (its quiet
        entry). A unique, useful or progression item, or a first one, keeps its
        window."""
        item = self.ap.received_items.get(index)
        if item is None or getattr(item, "flags", None) != 0:
            return False
        name = self.ap.item_name(item)
        entry = getattr(getattr(self, "game", None), "item_map", {}).get(name)
        # Only the world's filler: an item cheated in (!getitem, /send) comes
        # with flags 0 too, and a Gerudo Set or a pouch upgrade received again
        # that way came quietly (seen in play). An elixir keeps the cooking's
        # window every time, and a weapon its get window ("window": "always").
        if entry is not None and (not (entry.get("pickup") or entry.get("generated_filler"))
                                  or entry.get("window") == "always"):
            return False
        return bool(name) and self._received_before(index, name) > 0

    def _vanilla_window(self, index: int) -> bool:
        """Its native delivery has a presentation of its own: the game's get
        window (GetDemo, an arrow bundle's or a cooked dish's too), the rune
        terminal's download screen, or, for a trap, the journal line that says
        what it did."""
        item = self.ap.received_items[index]
        name = self.ap.item_name(item)
        try:
            steps = self.deliveries.backend.catalog.steps(
                name, self._received_before(index, name))
        except (AttributeError, KeyError, ValueError):
            return False
        return any(m.get("kind") in VANILLA_WINDOWS
                   for step in steps for m in step.get("mutations", ()))

    def _close_presentations(self):
        self._presentation_notice = None
        self._presentation_recovery_request = None
        self._presentation_status = None
        if self.presentations is not None:
            self.presentations.close()
            self.presentations = None

    def handle_local_command(self, line):
        """Console only schedules work; the presentation worker owns its journal."""
        parts = line.split()
        if parts and parts[0] == '/ap-tip':
            if self.tip_factory is None:
                self.log('AP journal (tip frame) not available with this pack.')
            else:
                self._journal_note(line[len('/ap-tip'):].strip() or 'Archipelago journal test')
            return True
        if parts and parts[0] == '/ap-evt':
            self._event_trace_command(parts[1:])
            return True
        if parts and parts[0] == '/ap-deathlink':
            # Test: a DeathLink received from nobody, sent to nobody.
            if not self.ap.death_link_enabled:
                self.log('DeathLink is off in this seed.')
            else:
                self.ap.deathlinks.put_nowait(DeathLinkEvent(
                    time.time(), 'Console',
                    line[len('/ap-deathlink'):].strip() or 'DeathLink test'))
                self.log('DeathLink test: Link dies at the next safe moment.')
            return True
        if parts and parts[0] == '/ap-disconnect':
            # Test of the connection status: a real close, the usual
            # reconnection, its first attempt `seconds` later.
            try:
                seconds = float(parts[1]) if len(parts) > 1 else 10.0
            except ValueError:
                seconds = -1.0
            if not 1.0 <= seconds <= 300.0:
                self.log('Usage: /ap-disconnect [seconds, 1 to 300]')
            elif not self.ap.connected:
                self.log('Archipelago already disconnected.')
            else:
                self._reconnect_delay = seconds
                asyncio.get_running_loop().create_task(self.ap.close())
                self.log(f'Archipelago disconnection simulated; reconnecting in {seconds:.0f} s.')
            return True
        if not parts or parts[0] != '/ap-replay':
            return False
        if len(parts) != 2:
            self.log('Usage: /ap-replay <identifier shown with the blocked presentation>')
        elif not self.native_presentations or self.presentations is None:
            self.log('Replay unavailable: wait for the game connection and the blocked presentation.')
        elif self._presentation_recovery_request is not None:
            self.log('A replay request is already waiting to be handled.')
        else:
            self._presentation_recovery_request = (self.presentations, parts[1])
            self.log('Replay request received; wait for its confirmation before closing Cemu.')
        return True

    def _event_trace_command(self, args):
        """Console /ap-evt [n | reset]: the last requests the game's event
        manager saw (ours and its own), with their real flags (the runtime
        trace patch_event_request.asm, tools/cemu/event_request_trace.py)."""
        import os
        from tools.cemu import event_request_trace as trace
        cave = getattr(self.game, 'cave', None)
        if cave is None:
            self.log('Trace unavailable: wait for the game connection.')
            return
        try:
            log = Path(os.environ.get('BOTW_CEMU_LOG', '')).read_text(
                encoding='utf-8', errors='replace')
            address = trace.locate(log)
            if args and args[0] == 'reset':
                trace.reset(self.game.process, cave.base, address)
                self.log('request trace cleared')
                return
            count = int(args[0]) if args else 8
            data = trace.read_trace(self.game.process, cave.base, address)
        except Exception as exc:  # noqa: BLE001 - console diagnostic
            self.log(f'request trace unreadable: {exc}')
            return
        entered = [e for e in data['events'] if e['site'] == 'request_enter']
        outcome = {}
        for e in data['events']:
            if e['site'] != 'request_enter':
                outcome[e['sequence']] = e['site']
        self.log(f"{len(entered)} request(s) traced, {data['dropped']} dropped")
        for e in entered[-count:]:
            if not e.get('descriptor_hex'):
                self.log(f"#{e['sequence']} without a descriptor")
                continue
            fields = trace.descriptor_fields(bytes.fromhex(e['descriptor_hex']))
            after = outcome.get(e['sequence'] + 1, '?')
            self.log(f"#{e['sequence']} {fields['flow']}<{fields['entry']}> "
                     f"type={fields['type'] or '(empty)'} flags={fields['flags']:#x} "
                     f"-> {after.replace('request_', '')}")

    def _flush_replay_summary(self):
        """Once the items a reloaded save lost are given back, one AP window
        names them (in the presentation session's FIFO)."""
        if not self.state:
            return
        queue = self.state["apply_queue"]
        high = int(self.state.get("delivered_high", 0))
        if queue and int(queue[0]) < high:
            # A reload is being given back: an "Items restored" window still
            # waiting is a former reload's, which this one's supersedes (seen in
            # play: shown first, then the items it named came back again).
            self._withdraw_summaries("Items restored")
        for batch_name, title, done, log in (
                ("replay_batch", "Items restored", not (queue and int(queue[0]) < high),
                 "items restored after a load"),
                # Once none is left: a trap of the release strikes in between.
                ("bulk_batch", "Items received", not any(self._bulk(int(i)) for i in queue),
                 "items received at once (release, collect)")):
            batch = self.state.get(batch_name) or []
            if not batch or not done:
                continue
            number = int(self.state.get("summary_count", 0)) + 1
            self.state["summary_count"] = number
            self.state.setdefault("summary_queue", []).append({
                "key": f"summary/{number}", "title": title,
                "lines": replay_summary_lines(batch)})
            self.state[batch_name] = []
            self.state_store.save()
            self.log(f"{log}: {len(batch)}")
            if batch_name == "bulk_batch":
                self._bulk_told = False

    def _withdraw_summaries(self, title: str):
        """Drop the AP summaries of this title not yet shown; one the game was
        already asked for stays."""
        session = getattr(self, "presentations", None)
        pending = self.state.get("summary_queue") or []
        kept = [summary for summary in pending if summary["title"] != title
                or (session is not None and not session.withdraw(summary["key"]))]
        if len(kept) != len(pending):
            self.state["summary_queue"] = kept
            self.state_store.save()
            self.log(f"{len(pending) - len(kept)} former '{title}' window(s) superseded by this reload")

    def _mark_bulk(self):
        """The items a release or a collect sends at once: told by the server's
        notice, they come within BULK_WINDOW_SECONDS of it (a release: those
        of the released world). Given quietly, as items given back after a
        reload, and named by one AP window; a trap still strikes and a rune
        keeps its download screen. Items sent again by
        a connection have no arrival time: never taken for a release."""
        notices = getattr(self.ap, "bulk_notices", None)
        arrived = getattr(self.ap, "received_at", None)
        if not notices or not arrived or self.state is None:
            return
        bulk = set(self.state.get("bulk", []))
        added = False
        for at, world in notices:
            for index, when in arrived.items():
                item = self.ap.received_items.get(index)
                if (index in bulk or item is None or abs(when - at) > BULK_WINDOW_SECONDS
                        or (world is not None and item.player != world)):
                    continue
                bulk.add(index)
                added = True
        now = time.monotonic()
        notices[:] = [n for n in notices if now - n[0] <= 2 * BULK_WINDOW_SECONDS]
        if added:
            self.state["bulk"] = sorted(bulk)
            self.state_store.save()
            self.log(f"items of a release or a collect, given quietly: {len(bulk)}")

    def _keeps_presentation(self, item) -> bool:
        """A trap or a rune: never given quietly with a release."""
        name = self.ap.item_name(item)
        delivery = (getattr(self.game, "item_map", None) or {}).get(name, {}).get("delivery", {})
        return delivery.get("kind") in ("trap", "native_trap", "rune")

    def _bulk(self, index: int) -> bool:
        """Sent by a release or a collect, and given quietly (not a trap nor a rune)."""
        if not self.state or index not in self.state.get("bulk", ()):
            return False
        item = self.ap.received_items.get(index)
        return item is not None and not self._keeps_presentation(item)

    def _drop_received_line(self, item) -> None:
        from .ap_journal import matches_item
        queue = self.state["message_queue"]
        for position, entry in enumerate(queue):
            if matches_item(entry, self.ap.slot, item):
                queue.pop(position)
                self.state_store.save()
                return

    def _bulk_line(self, entry) -> bool:
        from .ap_journal import matches_item
        return any(matches_item(entry, self.ap.slot, self.ap.received_items[index])
                   for index in self.state.get("bulk", ()) if self._bulk(index))

    async def _native_presentation_tick(self):
        if self.presentations is None:
            raise FatalClientError('Native presentation session missing')
        self._flush_replay_summary()
        from .presentation_session import snapshot_ap
        ready = (self._ap_session_ready and self.ap.connected
                 and getattr(self.ap, 'items_synchronized', False))
        source = snapshot_ap(self.ap) if ready else None
        session = self.presentations
        recovery = self._presentation_recovery_request
        self._presentation_recovery_request = None
        async def advance():
            def work():
                if recovery is not None and recovery[0] is session:
                    try:
                        session.request_replay(recovery[1])
                    except ValueError as exc:
                        self.log(f'Replay refused: {exc}')
                    else:
                        self.log('Replay recorded: close Cemu, then start the game again. '
                                 'Only the announcement is replayed; this command gives no item.')
                return session.advance(self.state, source, self.game,
                    allow_submit=ready and time.monotonic() >= self.safe_after,
                    sources_ready=ready,
                    announce=(self._received_announcement
                              if getattr(self, 'tip_factory', None) is not None else None))
            return await asyncio.to_thread(work)
        task = asyncio.create_task(advance())
        try:
            status, changed = await asyncio.shield(task)
        except asyncio.CancelledError:
            # Do not close handles or release the journal while submit is
            # still running in a thread. Its outcome remains durably recorded.
            await task
            raise
        except Exception as exc:
            raise FatalClientError(f'presentation queue stopped: {exc}') from exc
        if changed:
            try:
                self.state_store.save()
            except Exception as exc:
                raise FatalClientError(f'presentation projection not saved: {exc}') from exc
        head = session.blocked_head() if status in ('uncertain', 'refused') else None
        notice = ((status, head['id'], head.get('attempts'),
                   head.get('replay_after_incarnation')) if head else None)
        if notice is not None and notice != getattr(self, '_presentation_notice', None):
            if head and 'replay_after_incarnation' in head:
                self.log(f'Presentation {status} ({head["id"]}): replay authorized, '
                         'waiting for a new Cemu and the game to be ready.')
            elif head:
                self.log(f'Presentation {status} ({head["id"]}, attempt {head.get("attempts", "?")}): queue blocked. '
                         f'To allow the announcement to be replayed after a restart: /ap-replay {head["id"]}')
        self._presentation_status = status
        self._presentation_notice = notice
        evidence_error = getattr(session.backend, 'evidence_error', None)
        if isinstance(evidence_error, str) and evidence_error != getattr(self, '_evidence_error', None):
            self.log(f'Presentation diagnostic not kept: {evidence_error}')
            self._evidence_error = evidence_error

    async def _active_loop(self):
        # Mailbox 0x0BADF00E guarantees this lease only matches
        # Obj_DungeonClearSeal. Older globally-blocking patches are rejected by
        # open_cave() before this point.
        self.lease_error = None
        if not self.native_mode:
            self.game.cave.sub_disarm()
        lease = asyncio.create_task(self._lease_loop(), name="BOTW shrine lease")
        try:
            while not self.stop_event.is_set() and self.game.cave:
                if self.lease_error:
                    raise self.lease_error
                await self._reconnect_tick()
                if not self.game.healthy():
                    raise GameNotReady("pointer resolver became unavailable")
                started = time.monotonic()
                session_bound = (not self.native_delivery
                                 or await self._ensure_native_session())
                if session_bound and (not self.native_mode or (
                        self._ap_session_ready and self.ap.connected
                        and getattr(self.ap, 'items_synchronized', False))):
                    await self._poll_locations()
                    await self._poll_shops()
                    self._discover_received()
                    self._collect_messages()
                    self._mark_bulk()
                    # A reload back to an unbound save unbinds the session.
                    session_bound = not self.native_delivery or self._native_session_bound
                # A swarm playing has the invoker for its 10 s: the events
                # (presentations, deliveries, the key item, a received
                # DeathLink) wait for its end; the journal and the death of
                # Link do not.
                swarming = self._swarming()
                if self.native_presentations and session_bound and not swarming:
                    await self._native_presentation_tick()
                if session_bound:
                    await self._journal_tick()
                self._hud_tick()
                if self.native_delivery:
                    if session_bound:
                        if not swarming:
                            await self._apply_one_received_native()
                            await self._pickup_tick()
                            self._log_delivery_wait()
                            await self._status_item_tick()
                            await self._pedestal_tick()
                        await self._ganon_gate_tick()
                        await self._native_trap_tick()
                        await self._deathlink_tick()
                elif not self.native_presentations:
                    displayed = await self._show_one_location_reward()
                    if not displayed:
                        displayed = await self._show_one_received()
                    if not displayed:
                        await self._apply_one_received()
                        await self._show_one_message()
                    self._log_delivery_wait()
                await self._wait_or_stop(max(
                    0.0, POLL_SECONDS - (time.monotonic() - started)))
        finally:
            await self._end_swarm()
            lease.cancel()
            try:
                await lease
            except asyncio.CancelledError:
                pass
            if self._reconnect_task:
                self._reconnect_task.cancel()
                try:
                    await self._reconnect_task
                except asyncio.CancelledError:
                    pass
                self._reconnect_task = None
            try:
                self.game.set_blocking(False)
                if self.game.cave and not self.native_mode:
                    self.game.cave.sub_disarm()
            except Exception:
                pass

    async def run(self):
        ap_delay = game_delay = 1.0
        try:
            while not self.stop_event.is_set():
                if not self.ap.connected:
                    try:
                        await self._connect_ap()
                        ap_delay = 1.0
                    except FatalClientError:
                        raise
                    except Exception as exc:
                        self.log(f"Archipelago unavailable: {exc}; retrying in {ap_delay:.0f}s")
                        await self.ap.close()
                        await self._wait_or_stop(ap_delay)
                        ap_delay = min(ap_delay * 2, 30.0)
                        continue
                if not self.game.cave:
                    try:
                        await self._connect_game()
                        game_delay = 1.0
                    except FatalClientError as exc:
                        if self._process_exit_error(exc):
                            break
                        raise
                    except Exception as exc:
                        if self._process_exit_error(exc):
                            break
                        self.log(f"BOTW unavailable: {exc}; retrying in {game_delay:.0f}s")
                        self._close_presentations()
                        self.game.close()
                        await self._wait_or_stop(game_delay)
                        game_delay = min(game_delay * 2, 15.0)
                        continue
                try:
                    await self._active_loop()
                except FatalClientError as exc:
                    if self._process_exit_error(exc):
                        break
                    raise
                except Exception as exc:
                    if self._process_exit_error(exc):
                        break
                    self.log(f"BOTW loop interrupted: {exc}")
                    self._close_presentations()
                    self.game.close()
                if not self.ap.connected:
                    self.game.set_blocking(False)
                    await self.ap.close()
        finally:
            if self.hud is not None:
                # The client stops: nothing is connected any more (a no-op
                # when Cemu is already gone).
                try:
                    self.hud.show(False)
                except Exception:  # noqa: BLE001
                    pass
            self._close_presentations()
            self.game.close()
            await self.ap.close()
