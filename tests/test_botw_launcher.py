"""The launcher without its window (botw_launcher/): settings, versions and the
handoff, seeds, rooms, storage, updates, and the jobs' protocol."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from botw_client import compatibility, paths
from botw_client.locations import WORLD_SCHEMA
from botw_client.version import VERSION, parse
from botw_launcher import handoff, jobs, logs, settings, versions
from botw_launcher.core import output, profile, rooms, seeds, storage, updates, worlds
from tests.test_play_pack import slot_file
from tools import cemu_profile, play_seed
from tools.play_mods import Mods

ROOT = Path(__file__).resolve().parents[1]


def zip_release(folder: Path, archive: Path) -> Path:
    """A release's zip as versions up to 0.3.x published them: release.json first and
    uncompressed, read from the zip's first bytes (core/updates.py read_statement)."""
    marker = folder / paths.RELEASE_MARKER
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        if marker.is_file():
            zipped.write(marker, f"{folder.name}/{paths.RELEASE_MARKER}", zipfile.ZIP_STORED)
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path != marker:
                zipped.write(path, Path(folder.name, path.relative_to(folder)).as_posix())
    return archive


class Data(unittest.TestCase):
    """A data folder of its own, with no mod in the player's Cemu and no Cemu running."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.data = Path(temp.name).resolve() / "data"
        self.data.mkdir()
        self.seeds = self.data / "play-seeds"
        self.patch(play_seed, "PLAY_SEEDS", self.seeds)
        self.patch(play_seed, "PACKS", self.data / "packs-from-source")
        self.patch(cemu_profile, "PROFILE", self.data / "cemu-validation")
        self.patch(cemu_profile, "PORTABLE", self.data / "cemu-validation/portable")
        self.cemu_running = self.patch(cemu_profile, "cemu_running", mock.Mock(return_value=False))
        self.patch_name("tools.play_mods.prepare", mock.Mock(side_effect=lambda say=None: Mods([], {})))

    def patch(self, target, name, value):
        patcher = mock.patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def patch_name(self, name, value):
        patcher = mock.patch(name, value)
        patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def seed(self, name, slot="Zelda", archive="AP_x.zip", sessions=(), **audit):
        folder = self.seeds / name
        folder.mkdir(parents=True)
        (folder / "analysis.json").write_text(json.dumps({
            "botw_slot": 1, "archive": str(folder / archive), "audit": {"slots": {"1": slot}, **audit}}))
        for session in sessions:
            (folder / "sessions" / session).mkdir(parents=True)
        return folder


class SettingsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "launcher/settings.json"

    def test_what_is_saved_is_read_back(self):
        chosen = settings.Settings(log_level="DEBUG", check_updates=False, last_seed="123")
        settings.save(chosen, self.path)
        self.assertEqual(settings.load(self.path), chosen)

    def test_a_missing_or_broken_file_gives_the_defaults(self):
        self.assertEqual(settings.load(self.path), settings.Settings())
        self.path.parent.mkdir()
        self.path.write_text("not json")
        self.assertEqual(settings.load(self.path), settings.Settings())

    def test_a_value_of_another_type_or_an_unknown_level_is_ignored(self):
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({"check_updates": "yes", "log_level": "LOUD", "last_seed": "9"}))
        loaded = settings.load(self.path)
        self.assertEqual((loaded.check_updates, loaded.log_level, loaded.last_seed), (True, "INFO", "9"))

    def test_the_keys_of_another_version_survive_a_save(self):
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({"theme_of_a_later_version": "dark", "last_seed": "1"}))
        loaded = settings.load(self.path)
        loaded.last_seed = "2"
        settings.save(loaded, self.path)
        self.assertEqual(json.loads(self.path.read_text())["theme_of_a_later_version"], "dark")
        self.assertEqual(json.loads(self.path.read_text())["last_seed"], "2")


class VersionsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def install(self, version, complete=True, launcher=True, console=False):
        folder = self.folder / version
        (folder / "botw_launcher").mkdir(parents=True)
        (folder / "tools").mkdir()
        if launcher:
            (folder / (versions.CONSOLE_ENTRY if console else versions.ENTRY)).write_text("")
        if complete:
            (folder / versions.COMPLETE).write_text(json.dumps({"version": version}))
        return folder

    def test_the_installed_versions_the_newest_first(self):
        for version in ("0.4.0", "0.10.0", "0.9.1"):
            self.install(version)
        self.assertEqual([one.version for one in versions.installed(self.folder)], ["0.10.0", "0.9.1", "0.4.0"])

    def test_an_unfinished_installation_or_one_without_a_launcher_is_not_a_version(self):
        self.install("0.4.0")
        unfinished = self.install("0.5.0", complete=False)
        self.install("0.6.0", launcher=False)
        self.assertEqual([one.version for one in versions.installed(self.folder)], ["0.4.0"])
        self.assertEqual(versions.unfinished(self.folder), [unfinished])

    def test_the_newest_is_named_only_above_the_version_asked(self):
        self.install("0.4.0")
        self.assertEqual(versions.newest("0.3.9", self.folder).version, "0.4.0")
        self.assertIsNone(versions.newest("0.4.0", self.folder))
        self.assertIsNone(versions.newest("0.3.0", self.folder / "nothing"))

    def test_a_version_is_removed_but_the_one_running(self):
        folder = self.install("0.4.0")
        versions.remove(versions.find("0.4.0", self.folder))
        self.assertFalse(folder.exists())
        with self.assertRaisesRegex(ValueError, "the one running"):
            versions.remove(versions.Installed(VERSION, versions.ROOT))

    def test_a_version_is_started_isolated_by_its_own_entry(self):
        command = versions.command(self.folder / "0.4.0", ["--seed", "1"])
        self.assertEqual(command[1:], ["-I", "-X", "utf8", str(self.folder / "0.4.0" / versions.ENTRY),
                                       "--seed", "1"])

    def test_a_version_older_than_this_launcher_opens_its_console_one_never_by_handoff(self):
        folder = self.install("0.2.6", console=True)
        found = versions.find("0.2.6", self.folder)
        self.assertTrue(found.console)
        self.assertIsNone(versions.newest("0.1.0", self.folder))
        # It asks which seed to play: only a file to add is passed on.
        self.assertEqual(versions.command(folder, ["--seed", "1"])[1:], ["-I", str(folder / versions.CONSOLE_ENTRY)])
        self.assertEqual(versions.command(folder, ["AP_1.zip"])[-1], "AP_1.zip")
        with mock.patch.object(versions.subprocess, "Popen") as popen:
            versions.start(folder, [], data=self.folder / "data")
        environment = popen.call_args.kwargs["env"]
        self.assertEqual(environment[paths.DATA_VARIABLE], str(self.folder / "data"))
        self.assertEqual(environment[versions.PINNED_VARIABLE], "1")


class HandoffTests(unittest.TestCase):
    def release(self, is_release=True):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        if is_release:
            (root / paths.RELEASE_MARKER).write_text("{}")
        patcher = mock.patch.object(handoff, "ROOT", root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def take_over(self, process=None, newest=versions.Installed("9.0.0", Path("nine")), pinned=False):
        """What the handoff returns, and the mock that stands for starting a version."""
        with mock.patch.object(versions, "newest", return_value=newest), \
                mock.patch.object(versions, "start", return_value=process) as self.start, \
                mock.patch.dict(os.environ):
            os.environ.pop(versions.PINNED_VARIABLE, None)
            if pinned:
                os.environ[versions.PINNED_VARIABLE] = "1"
            return handoff.take_over(["--seed", "1"]), self.start

    def test_a_newer_version_takes_over_with_the_arguments(self):
        self.release()
        # Still running after the grace period: it started.
        process = mock.Mock(wait=mock.Mock(side_effect=subprocess.TimeoutExpired("launcher", 6)))
        with self.assertRaises(SystemExit) as stopped:
            self.take_over(process)
        self.assertEqual(stopped.exception.code, 0)
        self.start.assert_called_once_with(Path("nine"), ["--seed", "1"])

    def test_a_version_that_fails_to_start_is_given_up_and_said(self):
        self.release()
        notice, _start = self.take_over(mock.Mock(wait=mock.Mock(return_value=1)))
        self.assertIn("Version 9.0.0 is installed but failed to start", notice)

    def test_nothing_newer_installed_is_this_version_running(self):
        self.release()
        self.assertEqual(self.take_over(newest=None)[0], None)

    def test_a_pinned_launcher_and_a_source_checkout_never_hand_over(self):
        self.release()
        notice, start = self.take_over(pinned=True)
        self.assertIsNone(notice)
        start.assert_not_called()
        self.release(is_release=False)
        notice, start = self.take_over()
        self.assertIsNone(notice)
        start.assert_not_called()


class SeedTests(Data):
    def test_prepared_seeds_the_last_used_first(self):
        self.seed("111", sessions=["20260901T100000.000000Z"])
        self.seed("222", slot="Ami", sessions=["20260920T100000.000000Z"])
        (self.seeds / "generate").mkdir()
        self.assertEqual([(seed.name, seed.slot) for seed in seeds.prepared()], [("222", "Ami"), ("111", "Zelda")])
        self.seed("333")        # just prepared, never played: the one the player is about to play
        self.assertEqual(seeds.prepared()[0].name, "333")
        self.assertIsNone(seeds.prepared()[0].last_played)

    def test_a_seed_of_another_schema_is_not_playable_and_says_its_world(self):
        self.seed("111", world_schema=WORLD_SCHEMA, world_version=VERSION)
        self.seed("222", world_schema=WORLD_SCHEMA - 1, world_version="0.1.0")
        found = {seed.name: (seed.playable, seed.world_schema, seed.world_version) for seed in seeds.prepared()}
        self.assertEqual(found, {"111": (True, WORLD_SCHEMA, VERSION), "222": (False, WORLD_SCHEMA - 1, "0.1.0")})

    def test_a_file_that_is_not_a_seed_is_refused_in_a_sentence(self):
        other = self.data / "notes.zip"
        with zipfile.ZipFile(other, "w") as zipped:
            zipped.writestr("readme.txt", "nothing")
        with self.assertRaisesRegex(ValueError, "Not a Breath of the Wild slot file or seed: notes.zip"):
            seeds.inspect(other)

    def test_a_slot_file_says_its_seed_its_player_and_whether_it_is_playable(self):
        ours = seeds.inspect(slot_file(self.data, name="Zelda", container=True, slot_data={
            "world_schema": WORLD_SCHEMA, "client_schema": compatibility.CLIENT_SCHEMAS[-1], "world_version": VERSION}))
        self.assertEqual((ours.seed, ours.players, ours.unplayable), ("test-seed", ("Zelda",), ""))
        older = seeds.inspect(slot_file(self.data, name="Link", container=True, slot_data={
            "world_schema": WORLD_SCHEMA - 1, "client_schema": 3, "world_version": "0.1.0"}))
        self.assertEqual(older.world_version, "0.1.0")
        self.assertIn("cannot play", older.unplayable)

    def test_a_file_already_prepared_only_has_its_pack_checked(self):
        file = seeds.inspect(slot_file(self.data, container=True, slot_data={
            "world_schema": WORLD_SCHEMA, "client_schema": compatibility.CLIENT_SCHEMAS[-1]}))
        folder = self.seed(file.seed, archive=file.path.name)
        (folder / file.path.name).write_bytes(file.path.read_bytes())
        with mock.patch("tools.play_mods.fresh_pack") as fresh, mock.patch.object(play_seed, "prepare") as prepare:
            self.assertEqual(seeds.prepare(file, "Player"), file.seed)
        fresh.assert_called_once()
        prepare.assert_not_called()

    def test_a_new_file_is_built_for_the_player_chosen(self):
        file = seeds.SeedFile(self.data / "AP_1.zip", "1", ("Zelda", "Link"), VERSION, WORLD_SCHEMA, "")
        said = []
        with mock.patch.object(play_seed, "prepare") as prepare:
            seeds.prepare(file, "Link", said.append)
        self.assertEqual(prepare.call_args.kwargs["slot_name"], "Link")
        self.assertIn("for Link", said[0])

    def test_deleting_a_seed_says_what_goes_then_removes_it(self):
        folder = self.seed("111")
        (folder / "AP_x.apsave").write_bytes(b"x" * 100)
        going = seeds.deletion("111")
        self.assertEqual((going.paths, going.with_pack, going.with_hosted_progress), ((folder,), False, True))
        self.assertGreater(going.size, 100)
        seeds.delete("111")
        self.assertFalse(folder.exists())

    def test_no_seed_is_deleted_while_cemu_runs(self):
        folder = self.seed("111")
        self.cemu_running.return_value = True
        with self.assertRaisesRegex(RuntimeError, "Close Cemu"):
            seeds.delete("111")
        self.assertTrue(folder.exists())


class RoomTests(Data):
    def prepared(self, **keys):
        self.seed("111", **keys)
        return seeds.read("111")

    def test_the_room_is_remembered_never_a_password(self):
        seed = self.prepared()
        rooms.remember(seed, rooms.Room(address="archipelago.gg:12345"))
        self.assertEqual(rooms.remembered(seed), rooms.Room(address="archipelago.gg:12345"))
        self.assertEqual(json.loads((seed.folder / rooms.FILE).read_text()),
                         {"room": "archipelago.gg:12345", "open": False})

    def test_a_seed_hosted_here_is_remembered_so_while_it_can_be(self):
        seed = self.prepared(hostable=True)
        rooms.remember(seed, rooms.Room(hosted_here=True, open_to_network=True))
        with mock.patch.object(play_seed, "archipelago_here", return_value=True):
            self.assertEqual(rooms.remembered(seed), rooms.Room(hosted_here=True, open_to_network=True))
        with mock.patch.object(play_seed, "archipelago_here", return_value=False):
            self.assertFalse(rooms.remembered(seed).hosted_here)
            self.assertFalse(rooms.can_host(seed))

    def test_the_first_room_is_the_one_its_slot_file_was_downloaded_from(self):
        file = slot_file(self.data, container=True, server="archipelago.gg:54321")
        folder = self.seed("111", archive=file.name)
        (folder / file.name).write_bytes(file.read_bytes())
        self.assertEqual(rooms.remembered(seeds.read("111")).address, "archipelago.gg:54321")

    def test_an_address_is_taken_as_the_rooms_page_shows_it(self):
        self.assertEqual(rooms.normalized("  archipelago.gg:12345 "), "archipelago.gg:12345")
        self.assertEqual(rooms.normalized("wss://example.org:1"), "wss://example.org:1")
        for refused in ("", "   ", "http://archipelago.gg:1"):
            with self.subTest(refused), self.assertRaisesRegex(ValueError, "archipelago.gg:12345"):
                rooms.normalized(refused)


class StorageTests(Data):
    def release(self):
        """A release whose default data folder is self.data."""
        root = self.data.parent / "release"
        root.mkdir()
        (root / paths.RELEASE_MARKER).write_text("{}")
        self.patch(storage, "ROOT", root)
        self.patch(storage, "DATA", self.data)
        self.patch(paths, "default_data_folder", lambda *_: self.data)
        self.patch(os, "environ", {key: value for key, value in os.environ.items() if key != paths.DATA_VARIABLE})

    def test_the_room_taken_is_counted_by_what_it_is_for(self):
        (self.seed("111") / "AP_x.zip").write_bytes(b"s" * 300)
        (self.data / "packs-from-source/p1").mkdir(parents=True)
        (self.data / "packs-from-source/p1/file").write_bytes(b"p" * 500)
        (self.data / "gamedata.json").write_bytes(b"o" * 70)
        sizes = {usage.label: usage.size for usage in storage.usage(self.data)}
        self.assertEqual((sizes["Game packs"], sizes["Other files"], sizes["Game profile"]), (500, 70, 0))
        self.assertGreater(sizes["Seeds"], 300)

    def test_a_source_checkout_keeps_its_data_where_it_is(self):
        self.assertIn("source code", storage.relocation_refusal())

    def test_the_folder_picked_is_used_when_empty_else_a_folder_inside_it(self):
        self.assertEqual(storage.destination(self.data.parent / "new"), self.data.parent / "new")
        self.assertEqual(storage.destination(self.data.parent), self.data.parent / paths.RELEASE_FOLDER)

    def test_a_move_is_refused_into_the_data_itself_a_full_folder_or_while_cemu_runs(self):
        self.release()
        (self.data / "play-seeds").mkdir()
        full = self.data.parent / "full"
        full.mkdir()
        (full / "file").write_text("x")
        self.assertIn("outside", storage.relocation_refusal(self.data / "inside"))
        self.assertIn("not empty", storage.relocation_refusal(full))
        self.cemu_running.return_value = True
        self.assertIn("Close Cemu", storage.relocation_refusal(self.data.parent / "new"))

    def test_the_data_moves_whole_and_every_version_finds_it_again(self):
        self.release()
        folder = self.seed("111")
        (folder / "AP_x.zip").write_bytes(b"seed")
        target = self.data.parent / "elsewhere"
        steps = []
        storage.relocate(target, say=lambda _text: None, progress=lambda *step: steps.append(step))
        self.assertEqual((target / "play-seeds/111/AP_x.zip").read_bytes(), b"seed")
        self.assertEqual(paths.chosen_data_folder(self.data), target)
        # The seed's archive is named by its full path: it follows.
        report = json.loads((target / "play-seeds/111/analysis.json").read_text())
        self.assertEqual(Path(report["archive"]), target / "play-seeds/111/AP_x.zip")
        self.assertEqual([entry.name for entry in self.data.iterdir()], [paths.LOCATION_FILE])
        self.assertNotIn(storage.PREVIOUS, json.loads((self.data / paths.LOCATION_FILE).read_text()))
        self.assertEqual(steps[-1][:2], (2, 2))

    def test_what_a_move_could_not_remove_goes_at_a_later_start(self):
        self.release()
        self.seed("111")
        target = self.data.parent / "elsewhere"
        with mock.patch.object(play_seed, "remove", side_effect=PermissionError("in use")):
            storage.relocate(target, say=lambda _text: None)
        self.assertTrue((self.data / "play-seeds").exists())
        self.assertEqual(paths.chosen_data_folder(self.data), target)
        self.assertTrue(storage.finish_relocation())
        self.assertEqual([entry.name for entry in self.data.iterdir()], [paths.LOCATION_FILE])

    def test_a_copy_that_fails_changes_nothing(self):
        self.release()
        self.seed("111")
        with mock.patch.object(storage.shutil, "copytree", side_effect=OSError("disk full")), \
                self.assertRaises(OSError):
            storage.relocate(self.data.parent / "elsewhere", say=lambda _text: None)
        self.assertIsNone(paths.chosen_data_folder(self.data))
        self.assertTrue((self.data / "play-seeds/111").is_dir())


def github_release(version, *, prerelease=False, draft=False, asset=None, digest=""):
    name = updates.asset_name(version) if asset is None else asset
    return {"tag_name": f"v{version}", "name": f"BOTW Archipelago {version}", "body": "notes",
            "html_url": f"https://example.org/{version}", "prerelease": prerelease, "draft": draft,
            "assets": [{"name": name, "browser_download_url": f"https://example.org/{name}", "size": 4,
                        "digest": digest},
                       {"name": "botw.apworld", "browser_download_url": "https://example.org/w", "size": 1}]}


def apworld_release(version, *, prerelease=False):
    return {"tag_name": f"v{version}", "name": f"BOTW Archipelago {version}", "body": "notes",
            "html_url": f"https://example.org/{version}", "prerelease": prerelease, "draft": False,
            "assets": [{"name": "botw.apworld", "browser_download_url": f"https://example.org/{version}/w",
                        "size": 1}]}


class UpdateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def found(self, *entries):
        return updates.releases(lambda _url: json.dumps(list(entries)).encode())

    def test_the_releases_this_system_can_install_the_newest_first(self):
        found = self.found(github_release("0.4.0"), github_release("0.10.0"), github_release("0.9.0", draft=True),
                           github_release("0.8.0", asset="BOTW-Archipelago-0.8.0-Other.zip"),
                           {"tag_name": "tracker-icons", "assets": []})
        self.assertEqual([release.version for release in found], ["0.10.0", "0.4.0"])

    def test_an_update_is_a_newer_apworld_a_pre_release_only_when_asked(self):
        found = self.found(github_release("0.3.3"), apworld_release("0.4.0"), apworld_release("0.5.0", prerelease=True))
        self.assertEqual(updates.newer(found, than="0.3.0").version, "0.4.0")
        self.assertEqual(updates.newer(found, prereleases=True, than="0.3.0").version, "0.5.0")
        self.assertIsNone(updates.newer(found, than="0.4.0"))
        self.assertIsNone(updates.newer(self.found(github_release("0.3.3")), than="0.3.0"))   # a zip is no update
        self.assertEqual(updates.named(found, "0.4.0").asset_name, "botw.apworld")
        self.assertIsNone(updates.named(found, "0.1.0"))

    def test_a_release_of_the_zips_time_is_its_zip_even_with_a_world_beside(self):
        old, new = self.found(github_release("0.3.3"), apworld_release("0.4.0"))[::-1]
        self.assertEqual((old.kind, old.asset_name), ("zip", updates.asset_name("0.3.3")))
        self.assertEqual((new.kind, new.asset_name), ("apworld", "botw.apworld"))
        # A seed is played with a zip beside, or a newer apworld in place of this one; never an older apworld.
        found = self.found(github_release("0.3.3"), apworld_release("0.4.0"), apworld_release("0.5.0"))
        self.assertEqual([one.version for one in updates.usable(found, than="0.4.0")], ["0.5.0", "0.3.3"])

    def test_an_answer_that_is_not_the_release_list_is_an_error_to_show(self):
        with self.assertRaisesRegex(OSError, "could not be read"):
            updates.releases(lambda _url: b"<html>rate limited</html>")

    def release_zip(self, version="9.0.0", launcher=True, extra=()):
        archive = self.folder / updates.asset_name(version)
        with zipfile.ZipFile(archive, "w") as zipped:
            root = f"BOTW-Archipelago-{version}"
            zipped.writestr(f"{root}/{paths.RELEASE_MARKER}", json.dumps({"version": version}))
            if launcher:
                zipped.writestr(f"{root}/{versions.ENTRY}", "")
            for name in extra:
                zipped.writestr(name, "x")
        return archive

    def test_a_release_is_installed_next_to_the_others(self):
        installed = updates.install(self.release_zip(), folder=self.folder / "versions")
        self.assertEqual(installed, versions.Installed("9.0.0", self.folder / "versions/9.0.0"))
        self.assertEqual([one.version for one in versions.installed(self.folder / "versions")], ["9.0.0"])
        self.assertFalse((self.folder / updates.asset_name("9.0.0")).exists())    # the download is not kept

    def test_a_release_from_before_this_launcher_is_installed_with_its_console_one(self):
        archive = self.release_zip("0.2.6", launcher=False, extra=["BOTW-Archipelago-0.2.6/tools/launcher.py"])
        self.assertTrue(updates.install(archive, folder=self.folder / "versions").console)

    def test_a_release_without_a_launcher_or_with_unsafe_paths_is_refused_and_leaves_nothing(self):
        for archive, message in ((self.release_zip("0.2.0", launcher=False), "no launcher"),
                                 (self.release_zip("9.1.0", extra=["../outside.txt"]), "unsafe path"),
                                 (self.folder / "missing.zip", "could not be installed")):
            with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                updates.install(archive, folder=self.folder / "versions")
        self.assertEqual(list((self.folder / "versions").iterdir()), [])
        self.assertFalse((self.folder / "outside.txt").exists())

    def download(self, content, digest=""):
        release = updates.Release("9.0.0", "", "", "", False, "r.zip", "https://example.org/r.zip",
                                  len(b"data"), digest)
        with mock.patch.object(updates, "_open", return_value=io.BytesIO(content)):
            return updates.download(release, folder=self.folder)

    def apworld(self, version: str) -> Path:
        from tools.package_native import client_payload, package
        payload = client_payload({paths.RELEASE_MARKER: json.dumps(
            {"version": version, compatibility.KEY: compatibility.statement()}).encode()})
        return package(self.folder / "built" / f"{version}.apworld", payload)

    def test_what_an_apworld_plays_is_read_from_its_first_bytes(self):
        data = self.apworld("0.5.0").read_bytes()
        reads = []

        def fetch_range(_url, start, length):
            reads.append(length)
            return data[start:start + length]
        self.assertEqual(updates.read_statement("https://x/botw.apworld", fetch_range), compatibility.statement())
        self.assertEqual(reads, [updates.HEAD])

    def install_apworld(self, built: Path, version: str) -> Path:
        custom = self.folder / "custom_worlds"
        custom.mkdir(exist_ok=True)
        target = custom / "botw.apworld"
        target.write_bytes(b"the version running")
        content = built.read_bytes()
        release = updates.Release(version, "", "", "", False, "botw.apworld", "https://x/botw.apworld",
                                  len(content), hashlib.sha256(content).hexdigest(), kind="apworld")
        with mock.patch.object(updates, "_open", return_value=io.BytesIO(content)):
            updates.install_apworld(release, target, folder=self.folder / "downloads")
        return target

    def test_an_update_replaces_the_apworld_archipelago_loads_and_keeps_the_old_one(self):
        built = self.apworld("0.5.0")
        target = self.install_apworld(built, "0.5.0")
        self.assertEqual(target.read_bytes(), built.read_bytes())
        self.assertEqual([entry.name for entry in target.parent.iterdir()], ["botw.apworld"])  # nothing else to load
        self.assertEqual([entry.name for entry in (self.folder / "downloads").iterdir()],
                         [f"botw-{VERSION}.apworld.previous"])

    def test_an_apworld_of_another_version_or_without_its_window_replaces_nothing(self):
        from tools.package_native import package
        for built, message in ((self.apworld("0.5.1"), "not the botw.apworld of version 0.5.0"),
                               (package(self.folder / "bare.apworld"), "cannot be read")):
            with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                self.install_apworld(built, "0.5.0")
            self.assertEqual((self.folder / "custom_worlds/botw.apworld").read_bytes(), b"the version running")
            self.assertEqual([entry.name for entry in (self.folder / "custom_worlds").iterdir()], ["botw.apworld"])

    def test_only_a_window_opened_from_an_apworld_updates_it(self):
        world = self.folder / "botw.apworld"
        world.write_bytes(b"x")
        self.assertEqual(updates.installed_apworld({updates.APWORLD_VARIABLE: str(world)}), world)
        self.assertIsNone(updates.installed_apworld({updates.APWORLD_VARIABLE: str(self.folder)}))
        self.assertIsNone(updates.installed_apworld({}))

    def test_a_download_is_checked_against_what_github_published(self):
        good = hashlib.sha256(b"data").hexdigest()
        self.assertEqual(self.download(b"data", good).read_bytes(), b"data")
        for content, digest, message in ((b"da", good, "incomplete"), (b"dat4", good, "not the one GitHub published")):
            with self.subTest(message), self.assertRaisesRegex(OSError, message):
                (self.folder / "r.zip").unlink(missing_ok=True)
                self.download(content, digest)
            self.assertEqual(list(self.folder.glob("r.*")), [])


class WorldTests(unittest.TestCase):
    def test_the_check_before_a_session_plays_exactly_what_this_version_states(self):
        said = compatibility.statement()
        self.assertEqual(said["world_schemas"], [WORLD_SCHEMA])
        for world in (WORLD_SCHEMA - 1, WORLD_SCHEMA, WORLD_SCHEMA + 1, None):
            for client in (2, *compatibility.CLIENT_SCHEMAS, compatibility.CLIENT_SCHEMAS[-1] + 1):
                with self.subTest(world=world, client=client):
                    try:
                        play_seed.check_compatible({"world_schema": world, "client_schema": client})
                        checked = True
                    except ValueError:
                        checked = False
                    self.assertEqual(checked, compatibility.plays(said, world, client))

    def test_the_releases_before_the_statement_play_by_the_frozen_table(self):
        candidates = ("0.0.9", "0.1.0", "0.2.6", "0.3.0", "0.3.3", "0.4.0", "0.5.0")
        self.assertEqual([worlds.legacy(version) for version in candidates],
                         [None, {"world_schemas": [4]}, {"world_schemas": [4]}, {"world_schemas": [5]},
                          {"world_schemas": [5]}, None, None])
        self.assertLess(max(worlds.LEGACY), WORLD_SCHEMA)
        self.assertEqual(worlds.statement("0.3.3", {"world_schemas": [9]}), {"world_schemas": [9]})
        self.assertTrue(worlds.newer(WORLD_SCHEMA + 1))
        self.assertTrue(worlds.newer(WORLD_SCHEMA, compatibility.CLIENT_SCHEMAS[-1] + 1))
        self.assertFalse(worlds.newer(WORLD_SCHEMA, compatibility.CLIENT_SCHEMAS[-1]))
        self.assertFalse(worlds.newer(WORLD_SCHEMA - 1))

    def test_the_newest_version_that_plays_a_seed_is_offered_then_the_one_that_made_it(self):
        known = {version: worlds.statement(version, None) for version in ("0.1.0", "0.1.1", "0.2.6", "0.3.0")}
        known.update({"0.4.0": None,        # a release whose zip could not be read
                      "0.5.0": {"world_schemas": [6, 7], "client_schemas": [13, 14]},
                      "0.5.1": {"world_schemas": [7], "client_schemas": [14]}})
        self.assertEqual(worlds.choices(4, None, "0.1.1", known), ["0.2.6", "0.1.1"])
        self.assertEqual(worlds.choices(4, 3, "0.2.6", known), ["0.2.6"])
        self.assertEqual(worlds.choices(7, 14, "0.5.0", known), ["0.5.1", "0.5.0"])
        self.assertEqual(worlds.choices(6, 13, "0.4.0", known), ["0.5.0"])
        self.assertEqual(worlds.choices(6, 12, "0.4.0", known), [])     # a client schema 0.5.0 dropped
        self.assertEqual(worlds.choices(3, None, "0.0.9", known), [])
        self.assertEqual(worlds.choices(4, None, "0.1.1", {}), [])      # the releases not read yet


class StatementTests(unittest.TestCase):
    """What a release plays, read from the first bytes of its zip."""

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, True)

    def release(self, version="0.5.0", statement=True, packages=0) -> Path:
        release = self.folder / f"BOTW-Archipelago-{version}"
        (release / "python").mkdir(parents=True)
        (release / "python/python.exe").write_bytes(b"x" * 1000)
        (release / "BOTW Archipelago.cmd").write_text("x")
        marker = {"version": version, "packages": {f"package-{n}": "1.0" for n in range(packages)}}
        if statement:
            marker[compatibility.KEY] = compatibility.statement()
        (release / paths.RELEASE_MARKER).write_text(json.dumps(marker))
        return zip_release(release, self.folder / f"{release.name}.zip")

    @staticmethod
    def ranges(archive: Path, calls: list | None = None):
        def fetch_range(_url, start, length):
            if calls is not None:
                calls.append((start, length))
            return archive.read_bytes()[start:start + length]
        return fetch_range

    def test_a_release_zip_starts_with_its_statement_uncompressed(self):
        archive = self.release()
        with zipfile.ZipFile(archive) as zipped:
            first = zipped.infolist()[0]
            self.assertEqual((first.filename, first.compress_type),
                             (f"BOTW-Archipelago-0.5.0/{paths.RELEASE_MARKER}", zipfile.ZIP_STORED))
            self.assertEqual(sum(info.filename.endswith(paths.RELEASE_MARKER) for info in zipped.infolist()), 1)
        calls = []
        self.assertEqual(updates.read_statement("url", self.ranges(archive, calls)), compatibility.statement())
        self.assertEqual(calls, [(0, updates.HEAD)])

    def test_a_long_release_json_is_read_in_a_second_part(self):
        calls = []
        archive = self.release(packages=400)
        self.assertEqual(updates.read_statement("url", self.ranges(archive, calls)), compatibility.statement())
        self.assertEqual(len(calls), 2)

    def test_a_release_from_before_the_statement_states_nothing(self):
        archive = self.folder / "old.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
            zipped.writestr("BOTW-Archipelago-0.3.3/assets/model.bin", "x")
            zipped.writestr(f"BOTW-Archipelago-0.3.3/{paths.RELEASE_MARKER}", json.dumps({"version": "0.3.3"}))
        self.assertIsNone(updates.read_statement("url", self.ranges(archive)))
        self.assertIsNone(updates.read_statement("url", self.ranges(self.release(statement=False))))
        with self.assertRaisesRegex(OSError, "not a zip"):
            updates.read_statement("url", lambda *_: b"<html>")

    def test_the_statements_are_read_once_for_the_releases_since_the_table(self):
        archive = self.release()
        found = [updates.Release(version, "", "", "", False, f"{version}.zip", f"https://x/{version}", 10, "")
                 for version in ("0.5.0", "0.4.0", "0.3.3")]
        calls = []
        cache = self.folder / "releases.json"

        def fetch_range(url, start, length):
            if url.endswith("0.4.0"):
                raise OSError("offline")
            return self.ranges(archive, calls)(url, start, length)
        stated = updates.with_statements(found, fetch_range, cache)
        self.assertEqual(updates.with_statements(found[1:2], lambda *_: 1 / 0, cache)[0].plays, None)
        self.assertEqual([release.plays for release in stated], [compatibility.statement(), None, None])
        self.assertEqual(calls, [(0, updates.HEAD)])        # 0.3.3 is the table's, 0.4.0 failed
        self.assertEqual(updates.with_statements(found, fetch_range, cache)[0].plays, compatibility.statement())
        self.assertEqual(len(calls), 1)                     # kept from the first read

    def test_an_installed_version_says_what_it_plays(self):
        folder = self.folder / "0.5.0"
        folder.mkdir()
        self.assertIsNone(versions.Installed("0.5.0", folder).plays)
        (folder / paths.RELEASE_MARKER).write_text(json.dumps({"version": "0.5.0", "plays": {"world_schemas": [7]}}))
        self.assertEqual(versions.Installed("0.5.0", folder).plays, {"world_schemas": [7]})


class OutputTests(unittest.TestCase):
    def test_a_build_step_is_a_progress(self):
        self.assertEqual(output.interpret("  [3/14] GameData"),
                         {"event": "progress", "step": 3, "steps": 14, "label": "GameData"})

    def test_the_lines_of_a_session_are_its_steps(self):
        for line, expected in (
                ("Archipelago session: Cemu starts on the play account. Play normally", output.CEMU),
                ("21:02:11 connected to AP_123, slot Zelda (1)", output.ROOM),
                ("21:09:00 Archipelago offline: timed out; retrying in 5s", output.OFFLINE),
                ("21:09:05 Archipelago unavailable: refused; retrying in 5s", output.OFFLINE),
                ("21:09:10 Archipelago reconnected; offline checks resumed", output.ROOM),
                ("21:03:00 BOTW save bound to the AP session", output.GAME),
                ("22:00:00 Cemu closed: client stopping.", output.CLOSING)):
            with self.subTest(line):
                self.assertEqual(output.interpret(line), {"event": "stage", "stage": expected})
        self.assertEqual(output.interpret("21:05:00 check detected: Oman Au Shrine"),
                         {"event": "count", "what": "check"})
        self.assertEqual(output.interpret("21:05:01 item applied #4: Paraglider"), {"event": "count", "what": "item"})
        self.assertEqual(output.interpret("21:05:03 deliveries waiting (3): event settling 1.2s"),
                         {"event": "waiting", "count": 3})
        self.assertIsNone(output.interpret("21:05:02 the room says: not connected to anything"))

    def test_the_tools_still_print_those_lines(self):
        # The wording is the tools': a change there must come here too.
        printed = {"tools/play_session.py": ("Archipelago session: Cemu starts", "Cemu closed: client stopping."),
                   "tools/play_seed.py": ('print(f"  [{step}/{steps}] {name}"',),
                   "botw_client/protocol.py": ('f"connected to {self.seed_name}, slot ',),
                   "botw_client/runtime.py": ("BOTW save bound to the AP session", "Archipelago reconnected",
                                              'f"Archipelago offline: ', 'f"Archipelago unavailable: ',
                                              'f"check detected: ', 'f"item applied #',
                                              'f"deliveries waiting ({queues}): "')}
        for name, wordings in printed.items():
            source = (ROOT / name).read_text(encoding="utf-8")
            for wording in wordings:
                with self.subTest(wording):
                    self.assertIn(wording, source)


class JobTests(unittest.TestCase):
    def run_job(self, function, arguments="{}"):
        """A job's exit code, the lines it printed and the events it sent."""
        out = io.StringIO()
        streams = sys.stdout, sys.stderr
        try:
            with mock.patch.dict(jobs.JOBS, {"test": function}), mock.patch.object(sys, "__stdout__", out), \
                    mock.patch.object(sys, "__stderr__", out), mock.patch.object(sys, "stdin", io.StringIO(arguments)):
                code = jobs.main(["test"])
        finally:
            sys.stdout, sys.stderr = streams
        lines = out.getvalue().splitlines()
        events = [json.loads(line[1:]) for line in lines if line.startswith(jobs.MARK)]
        return code, [line for line in lines if not line.startswith(jobs.MARK)], events

    def test_a_job_reports_its_lines_its_steps_and_its_result(self):
        def build(seed):
            print("Building...")
            print("  [1/2] Text")
            return {"seed": seed}
        code, lines, events = self.run_job(build, '{"seed": "123"}\n')
        self.assertEqual((code, lines), (0, ["Building...", "  [1/2] Text"]))
        self.assertEqual(events, [{"event": "progress", "step": 1, "steps": 2, "label": "Text"},
                                  {"event": "done", "result": {"seed": "123"}}])

    def test_a_job_that_fails_says_why_and_logs_where(self):
        def build():
            raise ValueError("no Breath of the Wild player in this seed")
        code, lines, events = self.run_job(build)
        self.assertEqual((code, events),
                         (1, [{"event": "failed", "error": "no Breath of the Wild player in this seed"}]))
        self.assertIn("Traceback (most recent call last):", lines)

    def test_a_tool_that_exits_with_a_sentence_fails_with_it(self):
        def session():
            raise SystemExit("This seed was prepared from its slot file only")
        self.assertEqual(self.run_job(session)[2], [{"event": "failed",
                                                     "error": "This seed was prepared from its slot file only"}])

    def test_an_unknown_job_is_refused(self):
        with mock.patch.object(sys, "stderr", io.StringIO()) as said:
            self.assertEqual(jobs.main(["nothing"]), 2)
        self.assertIn("unknown job", said.getvalue())

    def test_a_session_is_started_with_what_the_player_chose(self):
        with mock.patch("tools.play_session.main") as session, mock.patch.object(seeds, "refresh"), \
                mock.patch.object(seeds, "newer_world", return_value=None), \
                mock.patch("tools.build_poptracker.PACK_FOLDER", Path("nowhere")), \
                mock.patch.object(jobs, "emit"):
            jobs.play("123", room="archipelago.gg:1", password="secret", session_arguments=["--speed", "3"])
            jobs.play("123", open_to_network=True)
        self.assertEqual([call.args[0] for call in session.call_args_list],
                         [["--seed", "123", "--speed", "3", "--connect", "archipelago.gg:1", "--password", "secret"],
                          ["--seed", "123", "--host"]])


class LogTests(Data):
    def test_a_diagnostic_holds_the_logs_and_the_last_session_not_the_seed(self):
        folder = self.seed("111", sessions=["20260901T100000.000000Z", "20260902T100000.000000Z"])
        (folder / "AP_x.zip").write_bytes(b"the seed itself")
        (folder / "sessions/20260902T100000.000000Z/client.log").write_text("21:00:00 connected")
        log_folder = self.data / "logs"
        log_folder.mkdir()
        (log_folder / logs.FILE).write_text("launcher started")
        archive = logs.export_diagnostic(self.data / "diagnostic.zip", folder, log_folder)
        with zipfile.ZipFile(archive) as zipped:
            names = set(zipped.namelist())
        self.assertLessEqual({"environment.txt", "logs/launcher.log", "seed/111/analysis.json",
                              "seed/111/20260902T100000.000000Z/client.log"}, names)
        self.assertFalse([name for name in names if name.endswith(".zip") or "20260901" in name])


class ProfileTests(Data):
    def test_the_profile_is_made_from_what_cemu_holds(self):
        self.assertFalse(profile.exists())
        install = mock.Mock(game=Path("game"), update=Path("update"), dlc=Path("dlc"))
        with mock.patch.object(profile.cemu_install, "detect", return_value=install), \
                mock.patch.object(cemu_profile, "create") as create:
            found = profile.detect(Path("Cemu.exe"))
            profile.create(Path("Cemu.exe"))
        self.assertEqual((found.game, found.update, found.dlc), (Path("game"), Path("update"), Path("dlc")))
        create.assert_called_once_with(Path("Cemu.exe"), install)

    def test_an_existing_profile_says_where_it_comes_from(self):
        (self.data / "cemu-validation").mkdir()
        (self.data / "cemu-validation/isolation.json").write_text(json.dumps({"source_cemu": "C:/Cemu/Cemu.exe"}))
        self.assertTrue(profile.exists())
        self.assertEqual(profile.summary().source_cemu, "C:/Cemu/Cemu.exe")


if __name__ == "__main__":
    unittest.main()
