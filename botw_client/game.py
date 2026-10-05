"""Bridge between the AP loop and the verified Cemu mailbox API."""
from __future__ import annotations

import json
import pathlib
import sys
import time
import textwrap
import zlib

from .items import load_item_map
from .locations import LocationTracker, alternate_targets, known_hashes, load_targets
from .paths import DATA
from .rune_selection import EQUIP_HASH, RuneSelectionSync, SyncOutcome

ROOT = pathlib.Path(__file__).resolve().parent.parent
CEMU_TOOLS = ROOT / "tools" / "cemu"
sys.path.insert(0, str(CEMU_TOOLS))

from gdt_index import build_index  # noqa: E402
from livegdt import LiveGdt  # noqa: E402
from mailbox import be, cemu_pid, open_cave  # noqa: E402
import getdemo  # noqa: E402
import saycenter  # noqa: E402

BLOCK_LEASE_FRAMES = 180
# One second was insufficient in a burst: the next demo could render the
# resource selected by the prior actor. A native manager reset still needs to
# be instrumented; do not clear its internals by hand.
DISPLAY_SETTLE_SECONDS = 2.5
SAFE_STABLE_SECONDS = 3.0
TERMINAL_RUNE_FLAGS = {
    "Magnesis Terminal": "IsGet_Obj_Magnetglove",
    "Remote Bombs Terminal": "IsGet_Obj_RemoteBomb",
    "Stasis Terminal": "IsGet_Obj_StopTimer",
    "Cryonis Terminal": "IsGet_Obj_IceMaker",
}
TOWER_SENSOR_FLAGS = (
    "IsGet_Obj_SheikSensor",
    "IsStart_Obj_SheikSensor",
    "App_SeakSensor_IsEnabled",
)
CUSTOM_FLAGS = {
    "APReceivedCursor": (zlib.crc32(b"APReceivedCursor"), "s32"),
    "APSeedToken": (zlib.crc32(b"APSeedToken"), "s32"),
}
# The sanctum's gate (botw_patch/ganon_gate.py); a pack built before has none.
GANON_FLAGS = {
    "APGanonOpen": (zlib.crc32(b"APGanonOpen"), "bool"),
    "APGanonRefused": (zlib.crc32(b"APGanonRefused"), "bool"),
}


class GameNotReady(RuntimeError):
    pass


class BotwGame:
    def __init__(self, *, index_cache_path=None):
        self.index_cache_path = pathlib.Path(index_cache_path) if index_cache_path is not None else None
        self.process = None
        self.cave = None
        self.live = None
        self.locations = None
        self.shop_watch = None
        self.item_map = load_item_map()
        self.flag_by_name = None
        self._window_was_busy = False
        self._window_free_since = time.monotonic()
        self._center_static = None
        self._safe_signature = None
        self._safe_since = None
        self._last_safe_tick = None
        self.save_ledger_available = False
        self.save_ledger_flags_present = False
        self.delivery_block_reason = "game not connected"
        self.native_presentation_mode = False

    def close(self):
        if self.process and self.cave:
            try:
                self.set_blocking(False)
                if not self.native_presentation_mode:
                    self.cave.sub_disarm()
            except Exception:
                pass
        if self.process:
            self.process.close()
        self.process = self.cave = self.live = self.locations = None
        self._center_static = None
        self._safe_signature = None
        self._safe_since = None
        self._last_safe_tick = None

    def connect(self, progress=print):
        self.close()
        process, cave = open_cave()
        self.process, self.cave = process, cave
        if not cave.pf_ready():
            self.close()
            raise GameNotReady("apPfReq missing from the loaded patch: CLOSE AND REOPEN CEMU")
        ok, passages, tick = cave.resolve_ready()
        if not ok:
            self.close()
            raise GameNotReady(
                f"invalid pointer resolver: {passages} passes, tick={tick}; "
                "CLOSE AND REOPEN CEMU")
        progress(f"pointer resolver: {passages} passes")
        channels = cave.channels()
        if not self.native_presentation_mode:
            for name, (pointer, ready) in channels.items():
                progress(f"  {name:22} {pointer:#010x}  {'ready' if ready else 'NOT READY'}")
        unavailable = ([] if self.native_presentation_mode else
                       [name for name, (_, ready) in channels.items() if not ready])
        if unavailable or not cave.ui_ready():
            self.close()
            raise GameNotReady(
                "channels not ready (load a save): "
                + ", ".join(unavailable or ["IHM"]))

        if self.native_presentation_mode:
            # The live bool table already contains location flags. Avoid the
            # expensive full-process scan of the legacy serialized tables.
            progress("reading the live flags...")
            index = {}
        else:
            progress("building the GameData index (cached for this PID when available)...")
            index = self._load_or_build_index(progress)
        self.live = LiveGdt(process, cave.base)
        count = (self.live.build(kinds=("bool", "s32")) if self.native_presentation_mode
                 else self.live.build())
        progress(f"live GameData: {count} scalar flags indexed")
        if not self.native_presentation_mode:
            self._validate_delivery_flags()
        if not self.native_presentation_mode:
            progress("BOTW save ledger: " +
                     ("available" if self.save_ledger_available
                      else "unavailable (external state fallback)"))
        targets = load_targets()
        self.locations = LocationTracker(
            process, index, targets + alternate_targets(targets), live=self.live)
        if self.locations.live_addresses:
            progress(f"locations: {len(self.locations.addresses)} in the fast range, "
                     f"{len(self.locations.live_addresses)} through the live GameData")
        return self

    def _validate_delivery_flags(self):
        """Refuse to start delivery if a mapped live flag is unavailable."""
        missing = []
        for name, entry in self.item_map.items():
            delivery = entry["delivery"]
            if delivery["kind"] == "flags":
                fields = [(flag, "bool") for flag, _ in delivery["writes"]]
            elif delivery["kind"] == "rune":
                fields = [(delivery["flag"], "bool"),
                          ("PlayerEquipItemType", "s32")]
            elif delivery["kind"] in ("counter", "counter_at_least"):
                fields = [(delivery["flag"], delivery["type"])]
            else:
                fields = []
            for flag, expected_kind in fields:
                hash_u32, actual_kind = self._hash(flag)
                if (actual_kind != expected_kind
                        or hash_u32 not in self.live.index[expected_kind]):
                    missing.append(f"{name}: {flag}/{expected_kind}")
        self.save_ledger_flags_present = all(
            hash_u32 in self.live.index[kind]
            for hash_u32, kind in CUSTOM_FLAGS.values())
        # An isolated persistence test read back live writes, but
        # reloading restored zero instead of the saved cursor/token. Presence
        # alone cannot certify a save backend; direct LiveGdt writes are not a
        # validated persistent write path. Keep the legacy external fallback.
        self.save_ledger_available = False
        if missing:
            raise GameNotReady(
                f"{len(missing)} GameData actions unavailable; client not armed: "
                + ", ".join(missing[:5]))

    def _load_or_build_index(self, progress):
        cache_path = self.index_cache_path or DATA / "index-cache.json"
        legacy_cache = CEMU_TOOLS / ".index_cache.json"
        pid = cemu_pid()
        for candidate in ((cache_path,) if self.index_cache_path is not None else (cache_path, legacy_cache)):
            if not candidate.exists():
                continue
            try:
                cache = json.loads(candidate.read_text(encoding="utf-8"))
                index = {int(key): value for key, value in cache["index"].items()}
                if cache.get("pid") == pid and index:
                    h, address = next(iter(index.items()))
                    if be(self.process.read(address, 4)) == h:
                        progress(f"cached index: {len(index)} flags")
                        return index
            except (OSError, KeyError, ValueError, TypeError):
                pass
        started = time.monotonic()
        index = build_index(self.process, known_hashes())
        progress(f"index built in {time.monotonic() - started:.0f}s: {len(index)} flags")
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({
                "pid": pid, "index": {str(k): v for k, v in index.items()}
            }), encoding="utf-8")
        except OSError as exc:
            progress(f"cache not written: {exc}")
        return index

    def healthy(self) -> bool:
        if not self.cave:
            return False
        ok, _, _ = self.cave.resolve_ready()
        return ok and self.cave.pf_ready()

    def set_blocking(self, enabled: bool):
        if not self.cave:
            return
        value = BLOCK_LEASE_FRAMES if enabled else 0
        if not self.process.write(self.cave.block_grants, value.to_bytes(4, "big")):
            raise RuntimeError("apBlockGrants write refused")

    def poll_locations(self) -> list[str]:
        if not self.locations:
            return []
        return self.locations.poll()

    def poll_shop(self) -> list[int]:
        """Shop location IDs of the Beedle whose buy list is open (for hints)."""
        if self.live is None or self.shop_watch is False:
            return []
        if self.shop_watch is None:
            from .shop_state import ShopWatch
            try:
                self.shop_watch = ShopWatch(self.live)
            except RuntimeError:
                self.shop_watch = False     # not found: no shop hints this session
                return []
        return self.shop_watch.seen()

    def suppress_terminal_rune(self, location_name: str):
        """Undo only the vanilla rune associated with one AP terminal."""
        flag = TERMINAL_RUNE_FLAGS.get(location_name)
        if flag:
            self._write_flag(flag, False, "bool")

    def ganon_gate(self) -> tuple[bool, bool] | None:
        """(open, refused) of the sanctum's gate; None if the pack has no gate."""
        if any(hash_u32 not in self.live.index[kind] for hash_u32, kind in GANON_FLAGS.values()):
            return None
        return (bool(self._read_flag("APGanonOpen", "bool")),
                bool(self._read_flag("APGanonRefused", "bool")))

    def open_ganon_gate(self):
        self._write_flag("APGanonOpen", True, "bool")

    def close_master_sword_pedestal(self) -> bool:
        """The pedestal's sword taken as a dropped weapon: its pull marked done
        (Get_MasterSword_Finish, as the pull sets it), so that the pedestal no
        longer offers to pull a sword it no longer holds. True if it was open."""
        if self._read_flag("Get_MasterSword_Finish", "bool"):
            return False
        self._write_flag("Get_MasterSword_Finish", True, "bool")
        return True

    def clear_ganon_refusal(self):
        self._write_flag("APGanonRefused", False, "bool")

    def suppress_tower_sensor(self):
        """Restore the measured pre-sensor state after Plateau Tower."""
        for flag in TOWER_SENSOR_FLAGS:
            self._write_flag(flag, False, "bool")

    def _hash(self, name: str) -> tuple[int, str]:
        if name in CUSTOM_FLAGS:
            return CUSTOM_FLAGS[name]
        if name in GANON_FLAGS:
            return GANON_FLAGS[name]
        if self.flag_by_name is None:
            from .gamedata_table import load
            data = load()
            self.flag_by_name = {
                flag_name: (int(key) & 0xFFFFFFFF, kind)
                for key, (kind, flag_name) in data.items()
            }
        if name in self.flag_by_name:
            return self.flag_by_name[name]
        raise KeyError(f"unknown GameData flag: {name}")

    def _read_flag(self, name: str, expected_kind: str | None = None):
        hash_u32, kind = self._hash(name)
        if expected_kind and kind != expected_kind:
            raise RuntimeError(f"{name}: type {kind}, expected {expected_kind}")
        if kind not in ("bool", "s32", "f32"):
            raise RuntimeError(f"{name}: type {kind} not supported")
        value = self.live.get(hash_u32, kind)
        if value is None:
            raise RuntimeError(f"{name}: live GameData object not found")
        return value

    def _write_flag(self, name: str, value, expected_kind: str | None = None):
        hash_u32, kind = self._hash(name)
        if expected_kind and kind != expected_kind:
            raise RuntimeError(f"{name}: type {kind}, expected {expected_kind}")
        if kind not in ("bool", "s32", "f32"):
            raise RuntimeError(f"{name}: type {kind} not supported")
        if not self.live.set(hash_u32, value, kind):
            raise RuntimeError(f"{name}: live GameData object not found")
        actual = self._read_flag(name, kind)
        if kind == "f32":
            if abs(actual - float(value)) > 0.01:
                raise RuntimeError(f"{name}: read back {actual}, expected {value}")
        elif actual != value:
            raise RuntimeError(f"{name}: read back {actual}, expected {value}")

    def _increment_flag(self, name: str, kind: str, delta, maximum):
        current = self._read_flag(name, kind)
        target = min(current + delta, maximum)
        self._write_flag(name, target, kind)
        # A same-frame read only proves that the live object accepted the
        # write. Give the game time to run its own update before confirming.
        time.sleep(0.25)
        actual = self._read_flag(name, kind)
        if kind == "f32":
            valid = abs(actual - float(target)) <= 0.01
        else:
            valid = actual == target
        if not valid:
            raise RuntimeError(f"{name}: write overwritten ({actual}, expected {target})")

    def _give_and_wait(self, actor: str, quantity: int = 1, timeout: float = 5.0):
        before = self.cave.read()["give_done"]
        if not self.cave.give(actor, quantity):
            raise RuntimeError(f"itemGet request refused: {actor}")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.cave.read()
            if state["give_done"] != before:
                return
            time.sleep(0.02)
        self.process.write(self.cave.give_req, bytes(4))
        raise RuntimeError(f"itemGet without an answer for {actor}; request cancelled")

    def item_action_count(self, name: str) -> int:
        entry = self.item_map.get(name)
        if not entry:
            raise RuntimeError(f"AP item missing from the item map: {name}")
        delivery = entry["delivery"]
        kind = delivery["kind"]
        if kind in ("actors", "flags"):
            return len(delivery["actors"] if kind == "actors" else delivery["writes"])
        return 1

    def apply_item_step(self, name: str, step: int,
                        received_before: int = 0) -> str | None:
        entry = self.item_map.get(name)
        if not entry:
            raise RuntimeError(f"AP item missing from the item map: {name}")
        delivery = entry["delivery"]
        kind = delivery["kind"]
        count = self.item_action_count(name)
        if not 0 <= step < count:
            raise IndexError(f"{name}: invalid step {step}/{count}")
        if kind == "actors":
            self._give_and_wait(delivery["actors"][step])
        elif kind == "progressive_actors":
            actors = delivery["actors"]
            actor = actors[min(received_before, len(actors) - 1)]
            self._give_and_wait(actor)
        elif kind == "flags":
            flag, value = delivery["writes"][step]
            self._write_flag(flag, value, "bool")
        elif kind == "rune":
            self._write_flag(delivery["flag"], True, "bool")
            self._write_flag(
                "PlayerEquipItemType", delivery["equip_type"], "s32")
        elif kind == "counter":
            self._increment_flag(delivery["flag"], delivery["type"],
                                 delivery["delta"], delivery["maximum"])
        elif kind == "counter_at_least":
            hash_u32, actual_kind = self._hash(delivery["flag"])
            if actual_kind != delivery["type"]:
                raise RuntimeError(
                    f"{delivery['flag']}: type {actual_kind}, expected {delivery['type']}")
            current = self.live.get(hash_u32, actual_kind)
            if current is None:
                raise RuntimeError(
                    f"{delivery['flag']}: live GameData object not found")
            self._write_flag(delivery["flag"], max(current, delivery["value"]),
                             delivery["type"])
        elif kind == "manual_prompt":
            return delivery["text"]
        else:
            raise RuntimeError(f"action not implemented: {kind}")
        return None

    def apply_item(self, name: str, received_before: int = 0) -> str | None:
        """Apply every sub-action; runtime persists progress between steps."""
        extra = None
        for step in range(self.item_action_count(name)):
            extra = self.apply_item_step(name, step, received_before) or extra
        return extra

    def frame_tick(self) -> int:
        """The cave's per-frame counter: game frames, not wall time."""
        return be(self.process.read(self.cave.tick, 4))

    def pause_menu_ready(self) -> tuple[bool, str]:
        """Can the pause menu be built at once (botw_client/pause_menu.py)."""
        from .pause_menu import pause_menu_ready
        return pause_menu_ready(lambda guest, size: self.process.read(self.cave.base + guest, size))

    def get_window_free(self) -> bool:
        _, screen, activity = getdemo.state(self.process, self.cave, verbose=False)
        return not screen or activity == 0xFF

    def safe_for_delivery(self) -> bool:
        """Conservative gate shared by item, DeathLink and display queues."""
        if not self.cave or not self.cave.ui_ready() or not self.get_window_free():
            self._safe_signature = self._safe_since = None
            self.delivery_block_reason = "UI or get window busy"
            return False
        try:
            health = int(self._read_flag("CurrentHart", "s32"))
            save_prohibited = bool(self._read_flag("SaveProhibition", "bool"))
        except RuntimeError:
            self._safe_signature = self._safe_since = None
            self.delivery_block_reason = "safety flags unreadable"
            return False
        tick = be(self.process.read(self.cave.tick, 4))
        if health <= 0 or save_prohibited or tick == self._last_safe_tick:
            self._safe_signature = self._safe_since = None
            self._last_safe_tick = tick
            self.delivery_block_reason = (
                "Link dead" if health <= 0 else
                "saving/loading forbidden" if save_prohibited else
                "game paused or in the background")
            return False
        self._last_safe_tick = tick
        signature = (
            be(self.process.read(self.cave.pmdm_this, 4)),
            be(self.process.read(self.cave.scr_table, 4)),
        )
        now = time.monotonic()
        if not all(signature) or signature != self._safe_signature:
            self._safe_signature = signature
            self._safe_since = now
            self.delivery_block_reason = "UI pointers settling"
            return False
        elapsed = now - self._safe_since if self._safe_since is not None else 0.0
        if elapsed < SAFE_STABLE_SECONDS:
            self.delivery_block_reason = (
                f"stable for {elapsed:.1f}/{SAFE_STABLE_SECONDS:.0f}s")
            return False
        self.delivery_block_reason = "ready"
        return True

    def bind_ap_session(self, token: int):
        if not self.save_ledger_available:
            return
        current = int(self._read_flag("APSeedToken", "s32"))
        if current not in (0, token):
            raise RuntimeError(
                f"this save belongs to AP token {current}; expected {token}")
        if current == 0:
            self._write_flag("APSeedToken", token, "s32")

    def sync_rune_selection(self, expected: int | None = None) -> SyncOutcome:
        """Align the live rune selection object with PlayerEquipItemType.

        See botw_client/rune_selection.py. Never raises for a missing or
        stale patch: the committed save is already correct, so the outcome
        only reports whether the running game shows it.
        """
        if not self.process or not self.cave or not self.live:
            return SyncOutcome("unavailable", detail="game not connected")
        if not self.cave.sel_ready():
            return SyncOutcome(
                "unavailable", detail="patch without rune selection (restart Cemu?)")

        def read_equip():
            value = self.live.get(EQUIP_HASH, "s32")
            if value is None:
                raise RuntimeError("PlayerEquipItemType not found")
            return int(value)

        sync = RuneSelectionSync(
            lambda address: getdemo.rd(self.process, self.cave, address),
            read_equip, self.cave.request_rune_selection)
        try:
            return sync.reconcile(expected)
        except Exception as exc:  # noqa: BLE001 - runs after a commit, must not raise
            return SyncOutcome("unavailable", expected,
                               detail=f"{type(exc).__name__}: {exc}")

    def delivery_position(self) -> tuple[int, int]:
        if not self.save_ledger_available:
            raise RuntimeError("BOTW ledger unavailable")
        cursor = int(self._read_flag("APReceivedCursor", "s32"))
        return cursor >> 8, cursor & 0xFF

    def set_delivery_position(self, index: int, step: int = 0):
        if not self.save_ledger_available:
            raise RuntimeError("BOTW ledger unavailable")
        if index < 0 or not 0 <= step <= 0xFF:
            raise ValueError(f"invalid AP cursor: {index}/{step}")
        self._write_flag("APReceivedCursor", (index << 8) | step, "s32")

    def display_ready(self) -> bool:
        if not self.cave or not self.cave.ui_ready():
            return False
        if not self.get_window_free():
            self._window_was_busy = True
            self._window_free_since = None
            return False
        if self._window_was_busy and self._window_free_since is None:
            self._window_free_since = time.monotonic()
            self._window_was_busy = False
            return False
        return (self._window_free_since is not None and
                time.monotonic() - self._window_free_since >= DISPLAY_SETTLE_SECONDS)

    def _show_item(self, name: str, title: str, lines: list[str]) -> bool:
        if self.native_presentation_mode:
            raise RuntimeError('Legacy display disabled while native owner controls presentation')
        if not self.display_ready():
            return False
        entry = self.item_map.get(name)
        actor = entry["display_actor"] if entry else "Item_AP"
        description = "\n".join(lines[:4])
        manager = getdemo.rd(self.process, self.cave, getdemo.MGR_PTR)
        if not manager:
            return False

        self.cave.show_item_text(title, description)
        try:
            name_guest = self.cave.write_text(actor, "ascii")
            obj_guest = self.cave.guest(self.cave.text_buf + getdemo.OBJ_OFF)
            self.process.write(
                self.cave.text_buf + getdemo.OBJ_OFF,
                name_guest.to_bytes(4, "big") + getdemo.STR_VT.to_bytes(4, "big")
                + (0x40).to_bytes(4, "big"))
            before = be(self.process.read(self.cave.call_n, 4))
            self.cave.call_pf(getdemo.OPEN_FN, manager, obj_guest)
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                if be(self.process.read(self.cave.call_n, 4)) > before:
                    break
                time.sleep(0.01)
            else:
                return False

            # This buffer is the direct postcondition of OPEN_FN. Read it
            # immediately, as the verified getdemo.py does: once the screen is
            # active the manager may already reuse or clear the string.
            capacity = getdemo.rd(self.process, self.cave, manager + 0x28)
            buf = getdemo.rd(self.process, self.cave, manager + 0x20)
            seen = self.cave.cstr(buf, min(capacity, 64)) if buf else None
            if seen != actor:
                return False

            # OPEN_FN returns before the UI has necessarily resolved its
            # title/description and icon resources. Keep substitutions armed
            # until screen 0x0b is actually active; disarming immediately was
            # observed to mix vanilla text and the preceding actor in bursts.
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline and self.get_window_free():
                time.sleep(0.01)
            if self.get_window_free():
                return False
            resolve_deadline = time.monotonic() + 0.5
            while time.monotonic() < resolve_deadline:
                title_req, _, desc_req, _, _ = self.cave.sub_state()
                if not title_req and not desc_req:
                    break
                time.sleep(0.01)

            return True
        finally:
            # A failure at any point must not corrupt the next genuine chest.
            self.process.write(self.cave.pf_req, bytes(4))
            self.cave.sub_disarm()

    def show_received(self, name: str, sender: str, game: str,
                      extra: str | None = None) -> bool:
        lines = [f"From {sender}"[:40], f"({game})"[:40]]
        if extra:
            lines.extend(extra[i:i + 40] for i in range(0, len(extra), 40))
        return self._show_item(name, name[:25], lines)

    def show_location_reward(self, name: str, recipient: str,
                             game: str, location: str) -> bool:
        lines = [f"For {recipient}"[:40], f"({game})"[:40], location[:40]]
        return self._show_item(name, name[:25], lines)

    def show_ap_message(self, text: str) -> bool:
        """Show one short AP line in the verified, non-blocking center channel."""
        if not self.safe_for_delivery():
            return False
        text = " ".join(text.split())
        if not text:
            return True
        # The carrier has exactly this many measured UTF-16 units available.
        text = textwrap.shorten(text, width=len(saycenter.DEFAULT_MSG),
                                placeholder="...")
        base = self.cave.base
        version_guest = self.cave.guest(self.cave.tick - 4)
        cave_range = (version_guest, version_guest + 8192)
        if self._center_static is None:
            self._center_static = saycenter.locate(
                self.process, base, self.cave, saycenter.DEFAULT_MSG,
                saycenter.DEFAULT_INDEX, cave_range, verbose=False)
        if self._center_static is None:
            return False
        address = base + self._center_static
        size = max(saycenter.WINDOW, len(saycenter.DEFAULT_MSG) * 2 + 32)
        saved = self.process.read(address, size)
        if not saved:
            return False
        self.process.write(address, text.encode("utf-16-be") + b"\x00\x00")
        try:
            return bool(saycenter.trigger(
                self.process, self.cave, saycenter.DEFAULT_INDEX, timeout=3.0))
        finally:
            self.process.write(address, saved)

    def is_dead(self) -> bool:
        """Link is dead: CurrentHart is 0 from the death until the reload.

        Measured on natural deaths and lethal damage: CurrentHart reaches 0 at
        the frame the game requests its death cutscene (Demo006_0) and stays
        there through the Game Over screen (about 9 s). A rescue (Mipha's
        Grace) never goes through 0, and every load, after a death or from the
        menu, goes through 99999, never 0. Writing 0 does not kill: the
        DeathLink entry of the pack does (botw_patch/death_link.py).
        """
        return self._read_flag("CurrentHart", "s32") <= 0
