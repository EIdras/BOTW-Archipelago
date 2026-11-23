"""The launcher's window (botw_launcher/tk), driven without showing it."""
import json
import logging
from pathlib import Path
import time
import unittest
from unittest import mock

from tests.tk_support import hidden_root, require_tkinter

require_tkinter()

import tkinter as tk  # noqa: E402

from botw_client.locations import WORLD_SCHEMA
from botw_client.version import VERSION
from botw_launcher import settings
from botw_launcher.core import output, room_link, rooms, updates, worlds
from botw_launcher.options import Options
from botw_launcher.tk import dialogs, events, theme
from botw_launcher.tk.app import MainWindow
from botw_launcher.tk.child import run as child_run
from botw_launcher.tk.context import Context, Records, Releases
from botw_launcher.tk.pages import help as help_page, play as play_page, storage as storage_page
from botw_launcher.tk.pages.logs import CHOICES
from tests.test_botw_launcher import Data


def text_of(widget) -> str:
    return widget.cget("text")


def shown(widget) -> bool:
    return bool(widget.winfo_manager())


class Window(Data):
    def setUp(self):
        super().setUp()
        self.patch(settings, "PATH", self.data / "launcher/settings.json")
        self.patch(storage_page, "DATA", self.data)
        self.patch(MainWindow, "_tidy", staticmethod(lambda: (0, 0)))
        self.checks = self.patch(Releases, "check", mock.Mock())     # no network in a test
        self.notices = []

    def open(self, *arguments, profile=True) -> MainWindow:
        if profile:
            (self.data / "cemu-validation").mkdir(exist_ok=True)
            (self.data / "cemu-validation/isolation.json").write_text("{}")
        self._drop_calls()      # what an earlier window left queued is not for this one
        self.root = hidden_root()
        self.addCleanup(self._close, self.root)
        theme.apply(self.root)
        self.records = Records()
        context = Context(Options.parse(list(arguments)), self.records, child_run, self.root.destroy)
        context.settings.check_updates = False      # no network in a test
        context.notice.connect(lambda text, actions: self.notices.append((text, actions)))
        window = MainWindow(self.root, context)
        events.pump(self.root)
        self.root.update()
        return window

    def _close(self, root: tk.Tk) -> None:
        for pending in root.tk.call("after", "info"):
            root.after_cancel(pending)
        root.destroy()
        self._drop_calls()

    @staticmethod
    def _drop_calls() -> None:
        while not events._calls.empty():
            events._calls.get_nowait()

    def wait_until(self, condition, timeout: float = 30) -> bool:
        end = time.monotonic() + timeout
        while not condition() and time.monotonic() < end:
            self.root.update()
            time.sleep(0.02)
        return bool(condition())


class OptionsTests(unittest.TestCase):
    def test_the_command_line_names_a_file_a_seed_and_what_goes_to_the_session(self):
        options = Options.parse(['"C:/seeds/AP_1.zip"', "--seed", "123", "--speed", "3", "--cheats"])
        self.assertEqual((options.file, options.seed, options.session_arguments),
                         (Path("C:/seeds/AP_1.zip"), "123", ("--speed", "3", "--cheats")))
        self.assertEqual(Options.parse([]), Options())


class PlayPageTests(Window):
    def test_the_first_launch_asks_for_cemu_then_shows_the_seeds(self):
        window = self.open(profile=False)
        play = window.play_page
        self.assertIs(play.view, play.setup)
        (self.data / "cemu-validation").mkdir()
        (self.data / "cemu-validation/isolation.json").write_text("{}")
        play.setup.created.emit()
        self.assertIs(play.view, play.seeds)
        self.assertTrue(shown(play.seeds.empty))       # no seed yet: it says how to add one

    def test_the_seeds_are_listed_and_the_one_named_is_selected(self):
        self.seed("111", sessions=["20260901T100000.000000Z"])
        self.seed("222", slot="Ami")
        view = self.open("--seed", "111").play_page.seeds
        self.assertEqual((len(view.rows), view.selected.name, text_of(view.name)), (2, "111", "Zelda"))
        view.select("222")
        self.assertEqual(view.selected.name, "222")
        view.refresh()
        self.assertEqual(view.selected.name, "222")     # the choice survives a refresh

    def test_a_room_is_needed_to_play_and_is_remembered(self):
        self.seed("111")
        self.patch_name("tools.play_seed.archipelago_here", mock.Mock(return_value=False))
        window = self.open()
        self.patch(window.context.jobs, "start", mock.Mock())
        view = window.play_page.seeds
        self.assertFalse(shown(view.host))       # nothing to host a seed with here
        asked = []
        view.play_requested.connect(lambda seed, room, password: asked.append((seed.name, room, password)))
        view.play()
        self.assertEqual(asked, [])
        self.assertIn("archipelago.gg:12345", text_of(view.problem))
        view.address.insert(0, "archipelago.gg:38281")
        view.password.insert(0, "secret")
        view.play()
        self.assertEqual(asked, [("111", rooms.Room(address="archipelago.gg:38281"), "secret")])
        self.assertEqual(json.loads((self.seeds / "111" / rooms.FILE).read_text())["room"], "archipelago.gg:38281")

    def test_a_seed_that_can_be_hosted_and_never_joined_a_room_is_hosted_here(self):
        self.seed("111", hostable=True)
        with mock.patch("tools.play_seed.archipelago_here", return_value=True):
            view = self.open().play_page.seeds
            self.assertEqual(view.mode.get(), "host")
            self.assertIn("disabled", view.address.state())

    def test_a_seed_this_version_cannot_play_is_offered_the_newest_version_of_its_world_and_its_own(self):
        older = max(schema for schema in worlds.LEGACY if schema < WORLD_SCHEMA)    # the newest released before
        first = worlds.LEGACY[older]
        newest = f"{first}9"         # a later release of the same world
        self.seed("111", world_schema=older, world_version=first)
        known = {version: worlds.statement(version, None) for version in (first, newest)}
        with mock.patch.object(Releases, "known", return_value=known):
            window = self.open()
        view = window.play_page.seeds
        self.assertEqual((view.play_button.text, view.other_button.text),
                         (f"Play with version {newest}", f"Use version {first}"))
        self.assertTrue(view.play_button.enabled)
        self.assertIn(VERSION, text_of(view.warning))
        with mock.patch.object(window.context.releases, "open_with") as open_with:
            view.play()
            view.play_with_other()
        self.assertEqual(open_with.call_args_list, [mock.call(newest, ("--seed", "111")),
                                                    mock.call(first, ("--seed", "111"))])

    def test_a_seed_a_newer_apworld_plays_is_offered_the_update(self):
        from botw_client import compatibility
        self.seed("111", world_schema=WORLD_SCHEMA + 1, world_version="9.0.0")
        window = self.open()
        releases = window.context.releases
        releases.found = [updates.Release("9.0.0", "", "", "", False, "botw.apworld", "https://x/w", 1, "",
                                          {**compatibility.statement(), "world_schemas": [WORLD_SCHEMA + 1]},
                                          kind="apworld")]
        view = window.play_page.seeds
        view.select("111")
        self.assertEqual(view.play_button.text, "Update to version 9.0.0")
        self.assertIn("replaces this one in Archipelago", text_of(view.warning))
        with mock.patch.object(releases, "update") as update:
            view.play()
        update.assert_called_once_with(releases.found[0])

    def test_an_older_seed_of_the_apworlds_time_is_to_be_generated_again(self):
        self.seed("111", world_schema=WORLD_SCHEMA - 1, world_version="0.4.0")
        window = self.open()
        window.context.releases.found = [updates.Release("0.3.3", "", "", "", False, "z.zip", "https://x/z", 1, "",
                                                         {"world_schemas": [1]})]
        view = window.play_page.seeds
        view.select("111")
        self.assertEqual(view.play_button.text, "Not playable")
        self.assertIn("one version of the world at a time", text_of(view.warning))

    def test_a_seed_no_known_release_plays_says_what_to_do(self):
        from botw_client.compatibility import CLIENT_SCHEMAS
        from botw_launcher.core import seeds
        self.seed("111", world_schema=WORLD_SCHEMA, client_schema=CLIENT_SCHEMAS[-1] + 1, world_version="9.0.0")
        self.seed("222", world_schema=WORLD_SCHEMA - 1, world_version="0.3.3")
        view = self.open().play_page.seeds
        newer, older = seeds.read("111"), seeds.read("222")
        self.assertFalse(newer.playable or older.playable)
        view.offered = []
        self.assertIn("Looking for the version", view._unplayable(older))
        self.checks.assert_called()      # the releases are read to find it
        view.context.releases.found = [mock.Mock()]
        for known, seed, expected in (({}, newer, "update BOTW Archipelago"),
                                      ({"0.4.1": None}, older, "could not be read"),
                                      ({}, older, "generate it again")):
            with self.subTest(expected), mock.patch.object(Releases, "known", return_value=known):
                self.assertIn(expected, view._unplayable(seed))

    def test_playing_starts_the_session_job_and_shows_its_steps(self):
        self.seed("111")
        window = self.open("--speed", "3")
        play = window.play_page
        with mock.patch.object(window.context.jobs, "start") as start:
            play.play(play.seeds.selected, rooms.Room(address="archipelago.gg:1"), "secret")
        name, arguments, _title = start.call_args.args
        self.assertEqual((name, arguments), ("play", {
            "seed": "111", "room": "archipelago.gg:1", "password": "secret", "open_to_network": False,
            "session_arguments": ["--speed", "3"]}))
        self.assertIs(play.view, play.session)
        window.context.jobs.name = "play"
        for stage in (output.PACK, output.CEMU, output.ROOM, output.GAME):
            play.session._event({"event": "stage", "stage": stage})
        play.session._event({"event": "count", "what": "check"})
        self.assertEqual(play.session.steps.states[output.GAME], "done")
        self.assertIn("1 checks found", text_of(play.session.counters))
        # A room lost and found again while playing is not a save to wait for.
        play.session._event({"event": "stage", "stage": output.ROOM})
        self.assertIn("Playing", text_of(play.session.state))
        play.session._event({"event": "stage", "stage": output.CLOSING})
        self.assertNotIn("active", play.session.steps.states.values())
        play.session._finished("play", False, "the room refused the slot")
        self.assertIn("the room refused the slot", text_of(play.session.state))

    def test_the_session_says_how_many_items_wait_until_the_client_stops_saying_it(self):
        self.seed("111")
        window = self.open()
        session = window.play_page.session
        window.context.jobs.name = "play"
        self.patch(play_page, "WAITING_SILENCE", 50)
        session._event({"event": "waiting", "count": 3})
        self.assertIn("3 waiting", text_of(session.counters))
        self.wait_until(lambda: "waiting" not in text_of(session.counters), 3)
        self.assertNotIn("waiting", text_of(session.counters))

    def test_the_keyboard_walks_the_seeds_and_opens_the_pages(self):
        self.seed("111")
        self.seed("222", slot="Ami")
        window = self.open("--seed", "111")
        seeds_view = window.play_page.seeds
        first = list(seeds_view.rows)[0]
        seeds_view.select(first)
        seeds_view.step(1)
        self.assertNotEqual(seeds_view.selected.name, first)
        seeds_view.step(1)              # the last stays selected
        seeds_view.step(-5)
        self.assertEqual(seeds_view.selected.name, first)
        window.shortcuts["<Control-Key-4>"]()
        self.assertTrue(window.nav["Logs"][1].current)
        window.shortcuts["<Up>"]()          # not on the seeds: nothing
        self.assertEqual(seeds_view.selected.name, first)

    def test_a_session_ended_is_played_again_with_the_same_seed_and_room(self):
        self.seed("111")
        window = self.open()
        play = window.play_page
        with mock.patch.object(window.context.jobs, "start") as start:
            play.play(play.seeds.selected, rooms.Room(address="archipelago.gg:1"), "secret")
            play.session._finished("play", True, {"session": ""})
            self.assertTrue(shown(play.session.again_button))
            play.session.again.emit()
        first, second = start.call_args_list
        self.assertEqual(first.args[:2], second.args[:2])
        self.assertEqual(second.args[1]["password"], "secret")

    def test_a_session_that_fails_marks_the_step_it_failed_at_only(self):
        self.seed("111")
        window = self.open()
        session = window.play_page.session
        window.context.jobs.name = "play"
        session._event({"event": "stage", "stage": output.PACK})
        session._finished("play", False, "no pack")
        self.assertEqual(list(session.steps.states.values()), ["failed", "pending", "pending", "pending"])

    def test_a_job_runs_in_its_own_process_and_its_failure_is_a_sentence(self):
        window = self.open()
        outcome = []
        window.context.jobs.start("prepare-seed", {"path": str(self.data / "nothing.zip"), "slot": "Zelda"},
                                  "Preparing", lambda succeeded, payload: outcome.append((succeeded, payload)))
        self.assertTrue(window.context.jobs.busy)
        self.root.update()
        self.assertTrue(shown(window.activity))
        with self.assertLogs("botw_launcher.tk.job_runner", "ERROR"):
            self.assertTrue(self.wait_until(lambda: outcome))
        self.assertEqual(outcome, [(False, "Not a Breath of the Wild slot file or seed: nothing.zip")])
        self.assertFalse(window.context.jobs.busy)
        self.assertFalse(shown(window.activity))


class OtherPagesTests(Window):
    def test_every_page_opens(self):
        self.seed("111")
        window = self.open()
        for name, (_button, page) in window.nav.items():
            window.show(name)
            self.root.update()
            self.assertTrue(page.current, name)
            self.assertEqual([other for other, (_b, p) in window.nav.items() if p.current], [name])

    def test_help_reads_the_guides_and_follows_their_links(self):
        window = self.open()
        window.show("Help")
        page = window.help_page
        self.assertEqual(page.current_guide.name, help_page.guides.ORDER[0])
        self.assertGreaterEqual(len(page.entries), 7)
        page.follow("ingame_en.md#the-archipelago-journal")
        self.assertEqual(page.current_guide.name, "ingame_en.md")
        with mock.patch.object(help_page.webbrowser, "open") as browser:
            page.follow("https://archipelago.gg")
        browser.assert_called_once_with("https://archipelago.gg")
        page.back()
        self.assertEqual(page.current_guide.name, help_page.guides.ORDER[0])

    def test_the_room_taken_is_measured_once_then_after_a_change_only(self):
        self.seed("111")
        window = self.open()
        page = window.nav["Storage"][1]
        with mock.patch.object(storage_page, "background") as run:
            window.show("Storage")
            window.show("Play")
            window.show("Storage")
            self.assertEqual(run.call_count, 1)
            window.context.seeds_changed.emit()
            window.show("Play")
            window.show("Storage")
            self.assertEqual(run.call_count, 2)
        # The version running is listed, installed or not.
        texts = [text_of(child) for child in page.versions.winfo_children() if isinstance(child, tk.Label)]
        self.assertIn(f"Version {VERSION}  (running", " | ".join(texts))

    def test_the_logs_show_what_the_player_chose_to_see(self):
        window = self.open()
        logs_page = window.nav["Logs"][1]
        window.show("Logs")
        logger = logging.getLogger("botw_launcher.test")
        logger.addHandler(self.records)
        self.addCleanup(logger.removeHandler, self.records)
        logger.setLevel(logging.DEBUG)
        logger.info("a main step")
        logger.debug("a detail")
        self.wait_until(lambda: "a main step" in logs_page.view.text.get("1.0", "end"), 5)
        self.assertIn("a main step", logs_page.view.text.get("1.0", "end"))
        self.assertNotIn("a detail", logs_page.view.text.get("1.0", "end"))
        logs_page.level.set(next(text for text, level in CHOICES if level == "DEBUG"))
        logs_page._level_changed()
        self.assertIn("a detail", logs_page.view.text.get("1.0", "end"))
        window.context.save_settings()
        self.assertEqual(settings.load().log_level, "DEBUG")       # and the choice is kept

    def test_an_update_is_announced_once_unless_skipped(self):
        window = self.open()
        release = updates.Release("99.0.0", "", "", "", False, "r.zip", "https://example.org/r.zip", 1, "")
        with mock.patch.object(window.context.releases, "newer", return_value=release):
            window._announce()
            self.assertEqual([text for text, _actions in self.notices], ["Version 99.0.0 is out."])
            skip = dict(self.notices[0][1])["Not this one"]
            skip()
            window._announce()
        self.assertEqual(len(self.notices), 1)
        self.assertEqual(settings.load().skipped_version, "99.0.0")

    def test_a_window_opened_from_an_apworld_installs_the_update(self):
        window = self.open()
        release = updates.Release("99.0.0", "", "", "", False, "botw.apworld", "https://x/w", 1, "", kind="apworld")
        with mock.patch.object(window.context.releases, "newer", return_value=release),                 mock.patch.object(updates, "installed_apworld", return_value=Path("C:/AP/custom_worlds/botw.apworld")):
            window._announce()
            install = dict(self.notices[0][1])["Install"]
            with mock.patch.object(window.context.jobs, "start") as start:
                install()
        name, arguments, _title, done = start.call_args.args
        self.assertEqual((name, arguments["release"]["version"]), ("install-apworld", "99.0.0"))
        done(True, {})
        self.assertIn("open it again", self.notices[-1][0])


class RoomAndHintsTests(Window):
    """A seed from its room's link, the session's coloured log, the Hints page."""

    def test_a_seed_is_added_from_its_rooms_link_choosing_the_player(self):
        self.seed("111")
        window = self.open()
        view = window.play_page.seeds
        found = [room_link.Slot(1, "Link", room_link.GAME, "archipelago.gg:1", "https://h/dl_patch/R/1"),
                 room_link.Slot(3, "Zelda", room_link.GAME, "archipelago.gg:1", "https://h/dl_patch/R/3")]
        downloaded = self.data / "downloads" / "P3_Zelda_R.apbotw"
        self.patch(dialogs, "ask_text", lambda *_a, **_k: "https://archipelago.gg/room/RRRRRRRRRR")
        self.patch(dialogs, "choose", lambda _parent, _title, _text, choices, **_k: choices[1])
        self.patch(room_link, "room_slots", lambda link: found)
        asked = []
        self.patch(room_link, "download", lambda slot, folder: asked.append(slot) or downloaded)
        added = []
        self.patch(view, "add_file", added.append)
        view.add_from_room()
        self.assertFalse(view.link_button.enabled)      # while the room's page opens
        self.assertTrue(self.wait_until(lambda: added, 10))
        self.assertEqual((asked, added), ([found[1]], [downloaded]))
        self.assertTrue(view.link_button.enabled)

    def test_a_room_that_fails_says_why_and_adds_nothing(self):
        self.seed("111")
        window = self.open()
        view = window.play_page.seeds
        self.patch(dialogs, "ask_text", lambda *_a, **_k: "https://archipelago.gg/room/RRRRRRRRRR")

        def refused(_link):
            raise ValueError("No Breath of the Wild player in this room.")
        self.patch(room_link, "room_slots", refused)
        told = []
        self.patch(dialogs, "tell", lambda _parent, _title, text, role="": told.append(text))
        self.patch(view, "add_file", lambda path: self.fail("nothing to add"))
        view.add_from_room()
        self.assertTrue(self.wait_until(lambda: told, 10))
        self.assertEqual(told, ["No Breath of the Wild player in this room."])
        self.assertTrue(view.link_button.enabled)

    def test_the_rooms_messages_are_coloured_once_and_the_log_is_searched(self):
        self.seed("111")
        window = self.open()
        session = window.play_page.session
        window.context.jobs.name = "play"
        parts = [["Zelda", "me", 0], [" sent ", "text", 0], ["Hookshot", "item_id", 1], [" to ", "text", 0],
                 ["Alice", "player", 0]]
        session._event({"event": "message", "kind": "ItemSend", "parts": parts})
        session._line("12:00:00 Zelda sent Hookshot to Alice")     # the client's own line: shown already
        session._line("12:00:01 check detected: Oman Au Shrine")
        text = session.log.text
        self.assertEqual(text.get("1.0", "end-1c"),
                         "Zelda sent Hookshot to Alice\n12:00:01 check detected: Oman Au Shrine\n")
        hookshot = text.search("Hookshot", "1.0")
        self.assertIn(theme.ITEMS["progression"], text.tag_names(hookshot))
        self.assertIn(theme.PARTS["me"], text.tag_names("1.0"))
        session.search.insert(0, "SHRINE")
        session._search()
        self.assertEqual(text_of(session.found), "1 found")
        session._line("12:00:02 check detected: Ja Baij Shrine")     # found as it comes
        self.assertEqual(len(text.tag_ranges("found")), 4)
        session.search.delete(0, "end")
        session._search()
        self.assertEqual((text.tag_ranges("found"), text_of(session.found)), ((), ""))

    def hints_window(self):
        self.seed("111")
        window = self.open("--seed", "111")
        window.context.jobs.name = "play"
        window.play_page.session.begin(window.play_page.seeds.selected, rooms.Room(address="archipelago.gg:1"))
        return window, window.nav["Hints"][1]

    HINTS = [
        {"receiving": "Zelda", "finding": "Alice", "item": "Paraglider", "location": "Cave", "entrance": "",
         "found": False, "flags": 1, "status": 30, "mine": True, "in_my_world": False},
        {"receiving": "Zelda", "finding": "Zelda", "item": "Bow", "location": "Shrine", "entrance": "",
         "found": True, "flags": 2, "status": 40, "mine": True, "in_my_world": True},
        {"receiving": "Alice", "finding": "Zelda", "item": "Hookshot", "location": "Chest", "entrance": "",
         "found": False, "flags": 4, "status": 0, "mine": False, "in_my_world": True},
    ]

    def test_the_rooms_hints_are_listed_filtered_and_kept_for_later(self):
        window, page = self.hints_window()
        window.play_page.session._event({"event": "hints", "hints": self.HINTS})
        rows = [page.table.item(row) for row in page.table.get_children()]
        self.assertEqual([row["values"][0] for row in rows], ["Paraglider", "Hookshot", "Bow"])
        self.assertEqual([row["tags"][0] for row in rows], ["progression", "trap", "found"])
        self.assertEqual(rows[0]["values"][-1], "Priority")
        self.assertIn("3 hints, 2 still to find (in the room now)", text_of(page.state))
        page.shown_kind.set("Your items")
        page.hide_found.set(True)
        page.refresh()
        self.assertEqual([page.table.item(row)["values"][0] for row in page.table.get_children()], ["Paraglider"])
        # Kept in the seed's folder: read again when no session runs.
        window.context.jobs.name = None
        page._finished()
        page.hints, page.seed_name = [], ""
        page.shown()
        self.assertEqual(len(page.hints), 3)
        self.assertIn("when you last played", text_of(page.state))

    def test_a_hint_is_asked_through_the_session_as_the_room_takes_it(self):
        window, page = self.hints_window()
        session = window.play_page.session
        sent = []
        self.patch(window.context.jobs, "send", sent.append)
        self.patch(type(window.context.jobs), "busy", property(lambda _jobs: True))
        page.shown()
        self.assertFalse(page.ask_button.enabled)      # Cemu has not started: no command yet
        window.context.jobs.event.emit({"event": "stage", "stage": output.CEMU})
        self.assertTrue(page.ask_button.enabled)
        page.name.set("Paraglider")
        page.ask()
        page.kind.set("location")
        page.name.set("Oman Au Shrine")
        page.ask()
        session.room = rooms.Room(hosted_here=True)
        page.kind.set("item")
        page.name.set("Bow")
        page.ask()
        self.assertEqual(sent, ["/hint Paraglider", "/hint_location Oman Au Shrine", "/hint Zelda Bow"])

    def test_names_are_suggested_as_they_are_typed(self):
        _window, page = self.hints_window()
        page.name.set("paragl")
        page._typed()
        self.assertEqual(list(page.name.cget("values")), ["Paraglider"])
        page.kind.set("location")
        page.name.set("calamity ganon")
        page._typed()
        self.assertIn("Defeat Calamity Ganon", page.name.cget("values"))


class DialogTests(Window):
    def answer(self, act, **question) -> bool:
        """The question asked, never shown; `act(dialog)` answers it."""
        self.open()
        self.patch(dialogs.Dialog, "_place", lambda dialog, owner: None)

        def press():
            dialog = next(child for child in self.root.winfo_children() if isinstance(child, dialogs.Dialog))
            try:
                act(dialog)
            finally:
                if dialog.winfo_exists():
                    dialog.answer("not answered")
        self.root.after(50, press)
        return dialogs.ask(self.root, "A question", "Some text.", **question)

    def test_enter_gives_the_highlighted_answer_and_escape_the_cautious_one(self):
        self.assertIs(self.answer(lambda dialog: dialog.enter(dialog)), True)
        self.assertIs(self.answer(lambda dialog: dialog.escape()), False)
        # A dangerous answer is never the default.
        self.assertIs(self.answer(lambda dialog: dialog.enter(dialog), danger=True), False)
        # Enter on an answer with the focus gives that one (its own binding).
        self.assertIs(self.answer(lambda dialog: dialog.buttons[False].invoke()), False)

    def test_a_line_or_a_choice_is_answered_in_the_dialog(self):
        self.open()
        self.patch(dialogs.Dialog, "_place", lambda dialog, owner: None)

        def answer(act):
            def press():
                dialog = next(child for child in self.root.winfo_children() if isinstance(child, dialogs.Dialog))
                act(dialog)
            self.root.after(50, press)

        def typed(dialog):
            dialog.field.insert(0, "  https://archipelago.gg/room/x  ")
            dialog.enter(dialog.field)
        answer(typed)
        self.assertEqual(dialogs.ask_text(self.root, "Link", "Paste it."), "https://archipelago.gg/room/x")
        answer(lambda dialog: dialog.escape())
        self.assertIsNone(dialogs.ask_text(self.root, "Link", "Paste it."))
        answer(lambda dialog: (dialog.field.set("Zelda"), dialog.enter(dialog.field)))
        self.assertEqual(dialogs.choose(self.root, "Who?", "Pick.", ["Link", "Zelda"]), "Zelda")


if __name__ == "__main__":
    unittest.main()
