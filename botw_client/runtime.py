"""Resilient 5 Hz bridge between a BOTW process and an AP room."""
from __future__ import annotations

import asyncio
import copy
import json
import time
from pathlib import Path

from .backend import DeliveryCommand, DeliveryCoordinator, DeliveryStatus
from .game import BotwGame, GameNotReady
from .locations import SCHEMA_LOCATION_COUNTS, load_targets
from .protocol import ArchipelagoClient, LocationInfo
from .session import session_token
from .message_text import clip_units, literal_metadata, literal_text, queued_text

POLL_SECONDS = 0.2
CHECK_RESEND_SECONDS = 2.0
BLOCK_REFRESH_SECONDS = 0.5
MESSAGE_MAX_CHARS = 39
MESSAGE_SETTLE_SECONDS = 4.0
# Reading time of a received item's journal line before its window.
JOURNAL_LEAD_SECONDS = 2.0
# How long a received item waits for the server's own line before ours.
JOURNAL_SERVER_WAIT_SECONDS = 3.0
STATE_PATH = Path(__file__).resolve().parent.parent / ".botw_client_state.json"
GOAL_LOCATION = "Defeat Calamity Ganon"
STATE_SCHEMA = 3
CLIENT_SCHEMA = 2
TERMINAL_ITEMS = {
    "Magnesis Terminal": "Magnesis",
    "Remote Bombs Terminal": "Remote Bomb",
    "Stasis Terminal": "Stasis",
    "Cryonis Terminal": "Cryonis",
}


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
        return f"après {max(seconds, 1)} s de coupure"
    return f"après {seconds // 60} min {seconds % 60:02d} de coupure"


def replay_summary_lines(names: list[str], width: int = 40, lines: int = 4) -> list[str]:
    """Names with their counts, in order, wrapped into the AP window; what
    does not fit is counted on the last line ("et N autres")."""
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
        suffix = f"et {rest} autre{'s' if rest > 1 else ''}"
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
            raise FatalClientError(f"etat client illisible ({path}): {exc}") from exc
        schema = self.data.get("schema")
        if schema not in (1, 2, STATE_SCHEMA) or not isinstance(
                self.data.get("sessions"), dict):
            raise FatalClientError(f"format d'etat client inconnu: {path}")
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
        # Experimental presentation-only path. No grants/ledger/DeathLink or
        # legacy display writes are enabled by choosing this path.
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
        self._session_identity = None
        self._session_locations = None
        self.lease_error = None
        self._next_message_after = 0.0
        self._last_game_cursor = None
        self._session_token = None
        self._deathlink_retry_after = 0.0
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
                self.log('Cemu fermé : fin des accès mémoire et arrêt du client.')
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
            self.log(f"cache de seed: {len(expected_ids)} affectations")
            return
        try:
            scouts = await self.ap.scout_locations(names)
        except Exception as exc:
            raise ConnectionError(
                "impossible d'obtenir le cache de seed; session AP refusee") from exc
        if set(scouts) != expected_ids:
            raise FatalClientError(
                f"scouts incomplets: {len(scouts)}/{len(expected_ids)}")
        self.state["scouts"] = {
            str(location_id): [info.item, info.location, info.player, info.flags]
            for location_id, info in scouts.items()
        }
        self.state_store.save()
        self.log(f"cache de seed enregistre: {len(scouts)} affectations")

    async def _connect_ap(self):
        self._ap_session_ready = False
        await self.ap.connect()
        try:
            await asyncio.wait_for(self.ap.data_package_event.wait(), 15.0)
        except asyncio.TimeoutError as exc:
            raise ConnectionError("data package BOTW non recu en 15 s") from exc
        world_schema = self._world_schema()
        target_names = [target.name for target in load_targets(world_schema=world_schema)]
        slot_schema = int(self.ap.slot_data.get("client_schema", 0))
        expected_schema = 3 if self.ap.game == "Breath of the Wild" else CLIENT_SCHEMA
        if slot_schema != expected_schema:
            raise FatalClientError(
                f"slot_data client_schema={slot_schema}; {expected_schema} attendu. "
                "Installer le nouvel APWorld et regenerer la seed.")
        expected = set(target_names)
        if self.ap.game == "Breath of the Wild":
            expected.discard(GOAL_LOCATION)
        available = set(self.ap.location_id_by_name)
        if expected != available:
            missing = sorted(expected - available)
            extra = sorted(available - expected)
            raise FatalClientError(
                "data package incompatible: "
                f"{len(expected)} locations attendues; "
                f"absentes={missing[:4]}, en trop={extra[:4]}")
        identity = (self.ap.seed_name or "seed-inconnue", self.ap.team,
                    self.ap.slot, self.ap.data_package_checksum)
        if self._session_identity is not None and identity != self._session_identity:
            raise FatalClientError(
                "la room ou le slot a change pendant la partie; relancer le client")
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
                    self.log("journal AP : cadre des conseils actif")
                    # A tip on screen when the game loop restarted is shown
                    # again, not lost with the previous channel object.
                    if self._journal_current is not None:
                        self._journal_pages.insert(0, self._journal_current)
                        self._journal_current = None
                    # Announced once the game can show it (the AP connection
                    # comes first, while Cemu is still loading).
                    if not self._journal_connected_once:
                        self._journal_connected_once = True
                        self._journal_note(f"{{1}}Connecté{{/}} à Archipelago : slot "
                                           f"{{2}}{self.ap.slot_name or self.ap.slot}{{/}}")
            except Exception as exc:
                self._close_presentations()
                raise FatalClientError(f'mode natif indisponible: {exc}') from exc
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
            self.log(f"connexion : sélection de rune non vérifiée ({exc})")
            return
        if outcome.status not in ("no_rune", "in_sync"):
            self.log(f"connexion : {outcome.summary()}")

    async def _ensure_native_session(self) -> bool:
        if not self.native_delivery or self.deliveries is None:
            return True
        if self._native_session_bound:
            return True
        if time.monotonic() < self._native_delivery_retry_after:
            return False
        binder = getattr(self.deliveries.backend, "bind_session", None)
        if binder is None:
            raise FatalClientError("backend natif sans liaison de session")
        result = await asyncio.to_thread(binder)
        if result.status in (DeliveryStatus.APPLIED,
                             DeliveryStatus.ALREADY_APPLIED):
            self._native_session_bound = True
            self._native_delivery_retry_after = 0.0
            self.game.delivery_block_reason = 'session liee ; attente des conditions de presentation'
            self.log("sauvegarde BOTW liée à la session AP")
            return True
        if result.status is DeliveryStatus.DEFERRED:
            self.game.delivery_block_reason = (
                'liaison differee ; nouvelle tentative automatique'
                + (f' ({result.detail})' if result.detail else ''))
            self._native_delivery_retry_after = time.monotonic() + 0.5
            return False
        raise FatalClientError(
            f"liaison native refusée ({result.status.value}) : {result.detail}")

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
                raise FatalClientError("backend de livraison native absent")
            checkpoint = self.deliveries.backend.checkpoint()
            expected = (self._session_identity[0], self._session_identity[2])
            if (checkpoint.seed, checkpoint.slot) != expected:
                raise FatalClientError(
                    "sauvegarde BOTW non liée à cette session AP : "
                    f"{checkpoint.seed}/{checkpoint.slot}, attendu "
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
            self.log(f"rollback BOTW detecte: reprise des objets AP a #{cursor_index}")
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
                f"temporisation evenement {self.safe_after - now:.1f}s")
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
            if self._presentation_status == 'waiting_ready' and isinstance(native_wait, str):
                reason = native_wait
            if (self._presentation_status in ('queued', 'waiting_ready')
                    and isinstance(submission, dict) and submission.get('status') == 'deferred'):
                reason = ('ressource native indisponible ; annonce non soumise, '
                          'reprise automatique en attente')
            elif (self._presentation_status in ('queued', 'waiting_ready')
                    and isinstance(submission, dict) and submission.get('status') == 'refused'):
                reason = ('refus natif sans action ; reprise automatique apres '
                          'retour aux conditions de presentation')
            if self._presentation_status in ('refused', 'uncertain'):
                reason = ('file de presentation bloquee (' + self._presentation_status
                          + ') ; suivre la commande /ap-replay indiquee')
                session = getattr(self, 'presentations', None)
                head = session.blocked_head() if session is not None else None
                if head and 'replay_after_incarnation' in head:
                    reason = ('reprise deja autorisee ; attente du redemarrage '
                              'et des conditions natives de presentation ; '
                              'ne pas repeter /ap-replay')
            self.log(f"livraisons en attente ({queues}): "
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
            raise FatalClientError(f"item AP {item.item} sans nom dans le data package")
        if name not in self.game.item_map:
            raise FatalClientError(f"item AP sans action BOTW: {name}")
        before = self._received_before(index, name)
        cursor_index, step = self._delivery_position()
        if cursor_index != index:
            return
        action_count = self.game.item_action_count(name)
        if step > action_count:
            raise FatalClientError(
                f"curseur AP #{index} etape {step}/{action_count} invalide")
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
            self.log(f"objet applique #{index}: {name}")

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
            raise FatalClientError(f"item AP {item.item} sans nom dans le data package")
        before = self._received_before(index, name)
        try:
            steps = self.deliveries.backend.catalog.steps(name, before)
        except (KeyError, ValueError) as exc:
            raise FatalClientError(f"item AP sans livraison native: {exc}") from exc
        if step >= len(steps):
            raise FatalClientError(
                f"curseur AP #{index} étape {step}/{len(steps)} invalide")
        quiet = index < int(self.state.get("delivered_high", 0))
        command = DeliveryCommand(
            self._session_identity[0], self._session_identity[2], index, name,
            step, len(steps), before, quiet=quiet)
        result = await asyncio.to_thread(self.deliveries.deliver, command)
        if result.status in (DeliveryStatus.APPLIED,
                             DeliveryStatus.ALREADY_APPLIED):
            if quiet and step == 0 and steps[step].get("quiet_entry"):
                # Given back without its window: named in one AP summary.
                self.state.setdefault("replay_batch", []).append(name)
                self.state_store.save()
            self._native_delivery_retry_after = 0.0
            self._discover_received()
            self.log(f"étape native commitée #{index}/{step}: {name}"
                     + (f" ({result.detail})" if result.detail else ""))
            return
        if result.status is DeliveryStatus.DEFERRED:
            self.game.delivery_block_reason = (
                'livraison differee ; nouvelle tentative automatique'
                + (f' ({result.detail})' if result.detail else ''))
            self._native_delivery_retry_after = time.monotonic() + 0.5
            return
        if result.status is DeliveryStatus.INVENTORY_FULL:
            self.game.delivery_block_reason = result.detail or "inventaire plein"
            self._native_delivery_retry_after = time.monotonic() + 5.0
            return
        raise FatalClientError(
            f"livraison native #{index}/{step} bloquée ({result.status.value}) : "
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
            name = f"Objet #{info.item}"
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
            self.log(f"recompense affichee: {location} -> {name} ({recipient})")
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
            self.log(f"objet affiche #{index}: {self.ap.item_name(item)}")
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
                "locations absentes du data package: " + ", ".join(unresolved))
        self.last_check_send = now

    def _world_schema(self) -> int:
        """Location schema of the connected seed (see botw_client/locations.py)."""
        if self.ap.game == "Breath of the Wild":
            # Absent only in slot data older than the schema field: the oldest.
            schema = int(self.ap.slot_data.get("world_schema", 1))
            if schema not in SCHEMA_LOCATION_COUNTS:
                raise FatalClientError(
                    f"slot_data world_schema={schema}; {sorted(SCHEMA_LOCATION_COUNTS)} "
                    "acceptes. Installer le nouveau client ou regenerer la seed.")
            return schema
        # Manual declares no schema: its data package tells which rows it has
        # (the newest schema all of whose names it knows).
        known = set(self.ap.location_id_by_name) | {GOAL_LOCATION}
        return max(schema for schema in SCHEMA_LOCATION_COUNTS
                   if schema == 1 or {target.name for target in load_targets(
                       world_schema=schema)} <= known)

    async def _poll_shops(self):
        """Seeing a Beedle's list hints the AP items he sells (once per location)."""
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
            self.log(f"boutique vue : indices pour {len(new)} objet(s)")

    async def _poll_locations(self):
        names = await asyncio.to_thread(self.game.poll_locations)
        if names and self._session_locations is not None:
            # A check absent from this seed (older world schema) is not sent.
            ignored = [name for name in names if name not in self._session_locations]
            if ignored:
                self.log("hors de cette seed, ignore: " + ", ".join(ignored))
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
                    self.log(f"rune vanilla neutralisee: {vanilla_rune}")
                if name == "Great Plateau Tower" and not self.native_mode:
                    owns_sensor = any(
                        self.ap.item_name(item) == "Sheikah Sensor"
                        for item in self.ap.received_items.values())
                    if not owns_sensor:
                        await asyncio.to_thread(self.game.suppress_tower_sensor)
                        self.log("detecteur de sanctuaire vanilla neutralise")
                if name not in self.state["pending_checks"]:
                    self.state["pending_checks"].append(name)
                    self._queue_location_display(name)
                    self.log(f"check detecte: {name}")
            self.safe_after = max(
                self.safe_after,
                time.monotonic() + max(event_settle_seconds(name)
                                       for name in names))
            self.state_store.save()
        await self._flush_checks()
        if (self.state.get("goal_observed") or GOAL_LOCATION in names
                or GOAL_LOCATION in self.state["pending_checks"]):
            known = set(self.state.get("observed_checks", []))
            known.update(self.ap.location_name(i) for i in self.ap.checked_locations)
            goal_type = int(self.ap.slot_data.get("goal_type", 0))
            beasts = sum(bool(n and n.startswith("Divine Beast")) for n in known)
            shrines = sum(bool(n and n.endswith(" Shrine")) for n in known)
            if goal_type == 1 and beasts < int(self.ap.slot_data.get("divine_beasts_required", 4)):
                return
            if goal_type == 2 and shrines < int(self.ap.slot_data.get("shrines_required", 40)):
                return
            if self.ap.connected and not self.state.get("goal_sent"):
                await self.ap.send_goal()
                self.state["goal_sent"] = True
                self.state_store.save()
                self.log("objectif Archipelago envoye")

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
        changed = False
        while True:
            try:
                event = self.ap.deathlinks.get_nowait()
            except asyncio.QueueEmpty:
                break
            if event.timestamp <= float(self.state.get("last_death_link") or 0.0):
                continue
            self.state["pending_deathlinks"].append({
                "time": event.timestamp, "source": event.source,
                "cause": event.cause})
            self.state["last_death_link"] = event.timestamp
            self.log(f"DeathLink mis en attente: {event.source} — {event.cause}")
            changed = True
        if changed:
            self.state_store.save()

        dead = await asyncio.to_thread(self.game.is_dead)
        if not dead:
            self._alive_seen = True
        if (self.ap.death_link_enabled and self._alive_seen and dead
                and self._last_dead is False):
            if self.ap.connected:
                await self.ap.send_death(f"{self.ap.slot_name} est mort dans Hyrule")
            else:
                self.state["pending_outgoing_death"] = True
                self.state_store.save()
        self._last_dead = dead

        if (self.ap.connected and self.ap.death_link_enabled
                and self.state["pending_outgoing_death"]):
            await self.ap.send_death(f"{self.ap.slot_name} est mort dans Hyrule")
            self.state["pending_outgoing_death"] = False
            self.state_store.save()

        if (self.ap.death_link_enabled and self.state["pending_deathlinks"]
                and not dead and self._safe_now()
                and time.monotonic() >= self._deathlink_retry_after):
            event = self.state["pending_deathlinks"][0]
            killed = await asyncio.to_thread(self.game.kill_player)
            if killed:
                self.state["pending_deathlinks"].pop(0)
                self._last_dead = True  # received deaths must never echo
                text = queued_text(event["cause"])
                if text:
                    self.state["message_queue"].append({
                        "text": text, "kind": "DeathLink", "nodes": []})
                    self.state["message_queue"] = self.state["message_queue"][-100:]
                self.state_store.save()
                self.log(f"DeathLink applique de {event['source']}: {event['cause']}")
            else:
                self._deathlink_retry_after = time.monotonic() + 10.0
                self.log("DeathLink non applique: fonction de mort BOTW pas encore "
                         "instrumentee; mort gardee en attente")

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
                self._journal_note("{0}Connexion Archipelago perdue{/} : "
                                   "le jeu continue, les checks partiront "
                                   "à la reconnexion.")
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
                self.log("Archipelago reconnecte; checks hors ligne repris")
                self._journal_note(f"{{1}}Reconnecté{{/}} à Archipelago "
                                   f"{offline_duration(self._offline_since)}")
                self._offline_since = None
                self._reconnect_delay = 1.0
        except FatalClientError:
            raise
        except Exception as exc:
            self.log(f"Archipelago hors ligne: {exc}; nouvel essai dans "
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
                self.log(f"indicateur HUD indisponible : {exc}")
            return
        if done and before is None:
            self.log("indicateur HUD : " + ("connecté" if online else "hors ligne"))

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
            self.log("objet Archipelago (seed, slot, objectif) vérifié dans l'inventaire")

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
                position += 1               # waits for its item's presentation
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
        # Not _safe_now(): safe_for_delivery() is stateful (it compares the
        # game tick with its previous call); a second caller in the same loop
        # made every delivery read "game paused" (25/09). in_world() is the
        # stateless presentation guard.
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
            self.log("journal AP : page refusée par le canal natif, ignorée")
            self._journal_pages.pop(0)
        else:
            self._journal_retry_after = time.monotonic() + 1.0

    def _received_announcement(self, index: int) -> str:
        """Presentation session hook: an item received from another player is
        first announced in the journal ("Alice a trouvé ton Grappin"), then
        shown by its vanilla window if its delivery has one (GetDemo: hearts,
        stamina, rupees), else by the usual AP window."""
        item = self.ap.received_items.get(index)
        if item is None:
            return 'present'
        if self.tips is None:
            return 'pending'
        if index not in self.state.setdefault("journal_announced", []):
            if index not in self._journal_queued:
                line = self._received_line(index, item)
                if line is None:
                    return 'pending'      # the server's line may still come
                self._journal_queued.add(index)
                self._journal_note(line, tag=index)
            return 'pending'
        shown = self._journal_times.get(index)
        if shown is not None and time.monotonic() - shown < JOURNAL_LEAD_SECONDS:
            return 'pending'
        return 'skip' if self._vanilla_window(index) else 'present'

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

    def _vanilla_window(self, index: int) -> bool:
        """Its native delivery shows the game's own presentation: the get
        window (GetDemo), or the rune terminal's download screen."""
        item = self.ap.received_items[index]
        name = self.ap.item_name(item)
        try:
            steps = self.deliveries.backend.catalog.steps(
                name, self._received_before(index, name))
        except (AttributeError, KeyError, ValueError):
            return False
        return any(m.get("kind") in ("get_demo_actor", "champion_actor", "rune_download")
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
                self.log('Journal AP (cadre des conseils) inactif avec ce pack.')
            else:
                self._journal_note(line[len('/ap-tip'):].strip() or 'Test du journal AP')
            return True
        if parts and parts[0] == '/ap-evt':
            self._event_trace_command(parts[1:])
            return True
        if parts and parts[0] == '/ap-coupure':
            # Test of the connection status: a real close, the usual
            # reconnection, its first attempt `seconds` later.
            try:
                seconds = float(parts[1]) if len(parts) > 1 else 10.0
            except ValueError:
                seconds = -1.0
            if not 1.0 <= seconds <= 300.0:
                self.log('Usage : /ap-coupure [secondes, 1 à 300]')
            elif not self.ap.connected:
                self.log('Archipelago déjà déconnecté.')
            else:
                self._reconnect_delay = seconds
                asyncio.get_running_loop().create_task(self.ap.close())
                self.log(f'Coupure Archipelago simulée ; reconnexion dans {seconds:.0f} s.')
            return True
        if not parts or parts[0] != '/ap-replay':
            return False
        if len(parts) != 2:
            self.log('Usage : /ap-replay <identifiant affiche dans le blocage>')
        elif not self.native_presentations or self.presentations is None:
            self.log('Reprise indisponible : attendre la connexion au jeu et le blocage.')
        elif self._presentation_recovery_request is not None:
            self.log('Une demande de reprise attend deja son traitement.')
        else:
            self._presentation_recovery_request = (self.presentations, parts[1])
            self.log('Demande de reprise recue ; attendre sa confirmation avant de fermer Cemu.')
        return True

    def _event_trace_command(self, args):
        """Console /ap-evt [n | reset]: the last requests the game's event
        manager saw (ours and its own), with their real flags (the runtime
        trace patch_event_request.asm, tools/cemu/event_request_trace.py)."""
        import os
        from tools.cemu import event_request_trace as trace
        cave = getattr(self.game, 'cave', None)
        if cave is None:
            self.log('Trace indisponible : attendre la connexion au jeu.')
            return
        try:
            log = Path(os.environ.get('BOTW_CEMU_LOG', '')).read_text(
                encoding='utf-8', errors='replace')
            address = trace.locate(log)
            if args and args[0] == 'reset':
                trace.reset(self.game.process, cave.base, address)
                self.log('trace des requêtes vidée')
                return
            count = int(args[0]) if args else 8
            data = trace.read_trace(self.game.process, cave.base, address)
        except Exception as exc:  # noqa: BLE001 - console diagnostic
            self.log(f'trace des requêtes illisible : {exc}')
            return
        entered = [e for e in data['events'] if e['site'] == 'request_enter']
        outcome = {}
        for e in data['events']:
            if e['site'] != 'request_enter':
                outcome[e['sequence']] = e['site']
        self.log(f"{len(entered)} requête(s) tracée(s), {data['dropped']} perdue(s)")
        for e in entered[-count:]:
            if not e.get('descriptor_hex'):
                self.log(f"#{e['sequence']} sans descripteur")
                continue
            fields = trace.descriptor_fields(bytes.fromhex(e['descriptor_hex']))
            after = outcome.get(e['sequence'] + 1, '?')
            self.log(f"#{e['sequence']} {fields['flow']}<{fields['entry']}> "
                     f"type={fields['type'] or '(vide)'} drapeaux={fields['flags']:#x} "
                     f"-> {after.replace('request_', '')}")

    def _flush_replay_summary(self):
        """Once the items a reloaded save lost are given back, one AP window
        names them (in the presentation session's FIFO)."""
        if not self.state:
            return
        batch = self.state.get("replay_batch") or []
        queue = self.state["apply_queue"]
        high = int(self.state.get("delivered_high", 0))
        if not batch or (queue and int(queue[0]) < high):
            return
        number = int(self.state.get("summary_count", 0)) + 1
        self.state["summary_count"] = number
        self.state.setdefault("summary_queue", []).append({
            "key": f"summary/{number}", "title": "Objets rendus",
            "lines": replay_summary_lines(batch)})
        self.state["replay_batch"] = []
        self.state_store.save()
        self.log(f"objets rendus après chargement : {len(batch)}")

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
                        self.log(f'Reprise refusee : {exc}')
                    else:
                        self.log('Reprise enregistree : fermer Cemu puis relancer la partie. '
                                 'Seule l\'annonce sera rejouee ; aucun objet n\'est donne par cette commande.')
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
            raise FatalClientError(f'file de presentation arretee: {exc}') from exc
        if changed:
            try:
                self.state_store.save()
            except Exception as exc:
                raise FatalClientError(f'projection presentation non enregistree: {exc}') from exc
        head = session.blocked_head() if status in ('uncertain', 'refused') else None
        notice = ((status, head['id'], head.get('attempts'),
                   head.get('replay_after_incarnation')) if head else None)
        if notice is not None and notice != getattr(self, '_presentation_notice', None):
            if head and 'replay_after_incarnation' in head:
                self.log(f'Presentation {status} ({head["id"]}) : reprise autorisee, '
                         'en attente d\'un nouveau Cemu et du jeu pret.')
            elif head:
                self.log(f'Presentation {status} ({head["id"]}, tentative {head.get("attempts", "?")}) : file bloquee. '
                         f'Pour autoriser le rejeu de l\'annonce apres redemarrage : /ap-replay {head["id"]}')
        self._presentation_status = status
        self._presentation_notice = notice
        evidence_error = getattr(session.backend, 'evidence_error', None)
        if isinstance(evidence_error, str) and evidence_error != getattr(self, '_evidence_error', None):
            self.log(f'Diagnostic de presentation non conserve : {evidence_error}')
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
                    raise GameNotReady("resolveur de pointeurs devenu indisponible")
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
                if self.native_presentations and session_bound:
                    await self._native_presentation_tick()
                if session_bound:
                    await self._journal_tick()
                self._hud_tick()
                if self.native_delivery:
                    if session_bound:
                        await self._apply_one_received_native()
                        self._log_delivery_wait()
                        await self._status_item_tick()
                elif not self.native_presentations:
                    await self._deathlink_tick()
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
                        self.log(f"Archipelago indisponible: {exc}; nouvel essai dans {ap_delay:.0f}s")
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
                        self.log(f"BOTW indisponible: {exc}; nouvel essai dans {game_delay:.0f}s")
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
                    self.log(f"boucle BOTW interrompue: {exc}")
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
