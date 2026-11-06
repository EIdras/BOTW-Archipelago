"""The player's launcher (tools/launcher.py), with scripted answers."""
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import time
import unittest
from unittest import mock

from tests.test_play_pack import slot_file
from tools import cemu_install, launcher
from tools.play_mods import Mods


class Answers:
    """A console whose answers are given in advance."""

    def __init__(self, answers=(), files=(), secrets=()):
        self.answers, self.files, self.secrets = list(answers), list(files), list(secrets)
        self.said = []

    def say(self, text=""):
        self.said.append(text)

    def ask(self, prompt, default=""):
        return (self.answers.pop(0) if self.answers else "") or default

    def secret(self, prompt):
        return self.secrets.pop(0) if self.secrets else ""

    def choose_file(self, title, kinds):
        return self.files.pop(0) if self.files else None

    def text(self):
        return "\n".join(self.said)


class Folder(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.seeds = self.root / "play-seeds"
        # The player's Cemu runs no mod (tools/play_mods.py).
        # Never a release here: its sweep would take the real packs for orphans.
        for patcher in (mock.patch.object(launcher, "RELEASE", False),
                        mock.patch.object(launcher.play_seed, "PLAY_SEEDS", self.seeds),
                        mock.patch.object(launcher.cemu_profile, "PROFILE", self.root / "profile"),
                        mock.patch("tools.play_mods.prepare", side_effect=lambda say=None: Mods([], {}))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def seed(self, name, slot="Zelda", archive="AP_x.zip", sessions=()):
        folder = self.seeds / name
        folder.mkdir(parents=True)
        (folder / "analysis.json").write_text(json.dumps({
            "botw_slot": 1, "archive": str(folder / archive), "audit": {"slots": {"1": slot}}}))
        for session in sessions:
            (folder / "sessions" / session).mkdir(parents=True)
        return folder


class ProfileTests(Folder):
    def test_an_existing_profile_asks_nothing(self):
        (self.root / "profile").mkdir()
        (self.root / "profile/isolation.json").write_text("{}")
        ui = Answers()
        launcher.ensure_profile(ui)
        self.assertEqual(ui.said, [])

    def test_the_first_launch_makes_the_profile_from_cemu(self):
        exe = self.root / "Cemu.exe"
        install = mock.Mock(game=Path("game"), update=Path("update"), dlc=Path("dlc"))
        ui = Answers(files=[exe])
        with mock.patch.object(cemu_install, "detect", return_value=install) as detect, \
                mock.patch.object(launcher.cemu_profile, "create") as create:
            launcher.ensure_profile(ui)
        detect.assert_called_once_with(exe)
        create.assert_called_once_with(exe, install)
        self.assertIn("about 5 GB", ui.text())

    def test_a_refused_installation_says_why(self):
        ui = Answers(answers=["n"], files=[self.root / "Cemu.exe"])
        with mock.patch.object(cemu_install, "detect",
                               side_effect=cemu_install.CemuInstallError("DLC not installed")), \
                mock.patch.object(launcher.cemu_profile, "create") as create:
            with self.assertRaises(launcher.Cancelled):
                launcher.ensure_profile(ui)
        self.assertIn("DLC not installed", ui.text())
        create.assert_not_called()


class SeedTests(Folder):
    def test_prepared_seeds_the_last_played_first(self):
        self.seed("111", sessions=["20260901T100000Z"])
        self.seed("222", slot="Ami", sessions=["20260920T100000Z"])
        self.seed("333")
        (self.seeds / "generate").mkdir()
        self.assertEqual([(seed.seed, seed.slot) for seed in launcher.prepared_seeds()],
                         [("222", "Ami"), ("111", "Zelda"), ("333", "Zelda")])

    def test_a_prepared_seed_is_played_as_it_is(self):
        self.seed("111", sessions=["20260901T100000Z"])
        ui = Answers(answers=["1"])
        with mock.patch("tools.play_pack.selected_pack"), mock.patch("tools.play_pack.outdated", return_value=[]), \
                mock.patch.object(launcher.play_seed, "refresh") as refresh:
            self.assertEqual(launcher.choose_seed(ui, None), "111")
        refresh.assert_not_called()
        self.assertIn("last played 2026-09-01", ui.text())

    def test_a_pack_built_by_another_version_is_built_again(self):
        self.seed("111")
        for stale in ({"return_value": ["botw_client/items.py"]}, {"side_effect": RuntimeError("no pack")}):
            with self.subTest(stale), mock.patch("tools.play_pack.selected_pack", **stale), \
                    mock.patch("tools.play_pack.outdated", **stale), \
                    mock.patch.object(launcher.play_seed, "refresh") as refresh:
                ui = Answers(answers=["1"])
                self.assertEqual(launcher.choose_seed(ui, None), "111")
            refresh.assert_called_once_with(self.seeds / "111", [], 0x50000000)
            self.assertIn("Building the game pack of seed 111 again", ui.text())

    def test_the_list_names_each_seeds_version_and_those_not_playable(self):
        from botw_client.locations import WORLD_SCHEMA
        for name, schema, version in (("111", WORLD_SCHEMA, "0.3.1"), ("222", WORLD_SCHEMA - 1, "0.2.5"),
                                      ("333", WORLD_SCHEMA - 1, None)):
            folder = self.seed(name)
            report = json.loads((folder / "analysis.json").read_text())
            report["audit"].update(world_schema=schema, world_version=version)
            (folder / "analysis.json").write_text(json.dumps(report))
        ui = Answers(answers=["1"])
        with mock.patch("tools.play_pack.selected_pack"), mock.patch("tools.play_pack.outdated", return_value=[]):
            launcher.choose_seed(ui, None)
        self.assertIn("111 (Zelda, world 0.3.1)\n", ui.text())
        self.assertIn("222 (Zelda, world 0.2.5): not playable with this version", ui.text())
        self.assertIn("333 (Zelda): not playable with this version", ui.text())

    def test_a_seed_of_a_newer_world_is_played_with_a_warning(self):
        folder = self.seed("111")
        report = json.loads((folder / "analysis.json").read_text())
        report["audit"]["world_version"] = "99.0.0"
        (folder / "analysis.json").write_text(json.dumps(report))
        ui = Answers()
        launcher.warn_newer(ui, "111")
        self.assertIn("world 99.0.0, newer than this version", ui.text())

    def test_another_seed_is_chosen_then_prepared(self):
        self.seed("111")
        path = slot_file(self.root, name="Zelda")
        ui = Answers(answers=["2"], files=[path])
        with mock.patch.object(launcher.play_seed, "prepare") as prepare:
            self.assertEqual(launcher.choose_seed(ui, None), "test-seed")
        prepare.assert_called_once_with(path.resolve(), slot_name=None, layers=[], mem2_end=0x50000000)

    def test_a_dropped_file_already_prepared_is_not_built_again(self):
        path = slot_file(self.root, name="Zelda")
        folder = self.seed("test-seed", archive=path.name)
        (folder / path.name).write_bytes(path.read_bytes())
        with mock.patch("tools.play_pack.selected_pack"), mock.patch("tools.play_pack.outdated", return_value=[]), \
                mock.patch.object(launcher.play_seed, "prepare") as prepare:
            self.assertEqual(launcher.choose_seed(Answers(), str(path)), "test-seed")
        prepare.assert_not_called()

    def test_a_zip_with_several_players_asks_which(self):
        import zipfile
        archive = self.root / "AP_test-seed.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            for slot, name in ((1, "Alice"), (2, "Bob")):
                path = slot_file(self.root, slot=slot, name=name)
                zipped.writestr(path.name, path.read_bytes())
        ui = Answers(answers=["2"])
        with mock.patch.object(launcher.play_seed, "prepare") as prepare:
            launcher.prepare_file(ui, archive)
        prepare.assert_called_once_with(archive.resolve(), slot_name="Bob", layers=[], mem2_end=0x50000000)

    def test_another_file_is_refused(self):
        other = self.root / "notes.json"
        other.write_text('{"x": 1}')
        with self.assertRaisesRegex(ValueError, "not a Breath of the Wild slot file"):
            launcher.prepare_file(Answers(), other)


class Packs(Folder):
    """The packs and their copies in the profile, in the temporary folder too."""

    def setUp(self):
        super().setUp()
        self.packs = self.root / "packs-from-source"
        self.copies = self.root / "profile/portable/graphicPacks"
        for patcher in (mock.patch.object(launcher.play_seed, "DATA", self.root),
                        mock.patch.object(launcher.play_seed, "PACKS", self.packs),
                        mock.patch.object(launcher.cemu_profile, "PORTABLE", self.root / "profile/portable"),
                        mock.patch.object(launcher.cemu_profile, "cemu_running", return_value=False)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def packed(self, name, pack, pointer=None):
        """A prepared seed selecting `pack` (1 MB), installed in the profile."""
        folder = self.seed(name)
        for path in (self.packs / pack, self.copies / f"AP_Ledger_{pack}"):
            path.mkdir(parents=True, exist_ok=True)
            (path / "rules.txt").write_bytes(bytes(2**19))
        pointer = pointer or {"schema": 2, "pack": f"packs-from-source/{pack}"}
        (folder / "play-pack.json").write_text(json.dumps(pointer))
        return folder


class DeleteTests(Packs):
    def test_the_list_deletes_a_seed_with_its_pack_then_lists_the_others(self):
        folder = self.packed("111", "aaa")
        (folder / "AP_x.zip").write_bytes(b"zip")
        os.chmod(folder / "AP_x.zip", stat.S_IREAD)       # copied from a downloaded file
        (folder / "AP_x.apsave").write_bytes(b"save")
        self.packed("222", "bbb")
        ui = Answers(answers=["4", "1", "y", "1"])
        with mock.patch("tools.play_pack.selected_pack"), mock.patch("tools.play_pack.outdated", return_value=[]):
            self.assertEqual(launcher.choose_seed(ui, None), "222")
        self.assertEqual([path.name for path in self.seeds.iterdir()], ["222"])
        self.assertEqual([path.name for path in self.packs.iterdir()], ["bbb"])
        self.assertEqual([path.name for path in self.copies.iterdir()], ["AP_Ledger_bbb"])
        self.assertIn("  3. delete a seed", ui.text())
        self.assertIn("1 MB, with the progress of the game you host on this computer (.apsave)", ui.text())
        self.assertIn("Seed 111 deleted.", ui.text())

    def test_a_pack_another_seed_selects_stays(self):
        self.packed("111", "aaa")
        self.packed("222", "aaa")
        launcher.delete_seed(Answers(answers=["1", "y"]), launcher.prepared_seeds())
        self.assertEqual([path.name for path in self.seeds.iterdir()], ["222"])
        self.assertTrue((self.packs / "aaa").is_dir() and (self.copies / "AP_Ledger_aaa").is_dir())

    def test_a_seed_without_a_valid_selection_still_goes(self):
        for pointer in (None, "not json", {"schema": 2, "pack": "packs-from-source/gone"}, {"schema": 2}):
            with self.subTest(pointer):
                folder = self.seed("111")
                if pointer is not None:
                    (folder / "play-pack.json").write_text(pointer if isinstance(pointer, str)
                                                           else json.dumps(pointer))
                launcher.delete_seed(Answers(answers=["1", "y"]), launcher.prepared_seeds())
                self.assertFalse(folder.exists())

    def test_nothing_outside_the_packs_folder_goes(self):
        (self.root / "elsewhere/aaa").mkdir(parents=True)
        for pointer in ({"schema": 2, "pack": "elsewhere/aaa"}, {"schema": 3, "pack": "packs-from-source/aaa"},
                        {"schema": 2, "pack": "packs-from-source/aaa/.."}):
            with self.subTest(pointer):
                folder = self.packed("111", "aaa", pointer)
                launcher.delete_seed(Answers(answers=["1", "y"]), launcher.prepared_seeds())
                self.assertFalse(folder.exists())
                self.assertTrue((self.root / "elsewhere/aaa").is_dir() and (self.packs / "aaa").is_dir())

    def test_the_selection_of_an_older_checkout_is_followed(self):
        # Schema 1 is relative to the project, whose .build was the data folder.
        pointer = {"schema": 1, "pack": f"{self.root.name}/packs-from-source/aaa"}
        folder = self.packed("111", "aaa", pointer)
        with mock.patch.object(launcher.play_seed, "ROOT", self.root.parent):
            launcher.delete_seed(Answers(answers=["1", "y"]), launcher.prepared_seeds())
        self.assertFalse(folder.exists() or (self.packs / "aaa").exists()
                         or (self.copies / "AP_Ledger_aaa").exists())

    def test_nothing_goes_unless_the_player_confirms(self):
        folder = self.packed("111", "aaa")
        for answer in ("", "n"):
            ui = Answers(answers=["1", answer])
            launcher.delete_seed(ui, launcher.prepared_seeds())
            self.assertTrue(folder.is_dir() and (self.packs / "aaa").is_dir()
                            and (self.copies / "AP_Ledger_aaa").is_dir())
        self.assertIn("Your Breath of the Wild saves stay in the launcher's Cemu profile.", ui.text())
        self.assertNotIn(".apsave", ui.text())

    def test_not_while_cemu_runs(self):
        folder = self.packed("111", "aaa")
        ui = Answers(answers=["1", "y"])
        with mock.patch.object(launcher.cemu_profile, "cemu_running", return_value=True):
            launcher.delete_seed(ui, launcher.prepared_seeds())
        self.assertTrue(folder.is_dir() and (self.packs / "aaa").is_dir())
        self.assertTrue(ui.text().endswith("Close Cemu before deleting a seed."))

    @unittest.skipUnless(os.name == "nt", "a file open on Windows cannot be deleted")
    def test_a_file_in_use_leaves_the_seed_listed_to_delete_again(self):
        folder = self.packed("111", "aaa")
        log = folder / "sessions/20261030T100000Z/client.log"
        log.parent.mkdir(parents=True)
        log.write_text("log")
        ui = Answers(answers=["1", "y", "1", "y"])
        with log.open():
            launcher.delete_seed(ui, launcher.prepared_seeds())
        self.assertIn("Seed 111 is not entirely deleted", ui.text())
        self.assertEqual([seed.seed for seed in launcher.prepared_seeds()], ["111"])
        self.assertFalse((self.packs / "aaa").exists())
        launcher.delete_seed(ui, launcher.prepared_seeds())
        self.assertFalse(folder.exists())
        self.assertIn("Seed 111 deleted.", ui.text())

    @unittest.skipUnless(os.name == "nt", "directory junctions")
    def test_a_link_goes_never_what_it_leads_to(self):
        import _winapi
        outside = self.root / "outside"
        (outside / "seed").mkdir(parents=True)
        (outside / "precious.bin").write_bytes(bytes(2**22))
        folder = self.packed("111", "aaa")
        _winapi.CreateJunction(str(outside), str(folder / "sessions"))
        shutil.rmtree(self.copies / "AP_Ledger_aaa")
        _winapi.CreateJunction(str(outside), str(self.copies / "AP_Ledger_aaa"))
        self.seed("elsewhere", slot="Ami").rename(outside / "seed/222")
        _winapi.CreateJunction(str(outside / "seed/222"), str(self.seeds / "222"))
        ui = Answers(answers=["1", "y", "1", "y"])
        launcher.delete_seed(ui, launcher.prepared_seeds())
        self.assertIn("1 MB", ui.text())        # the pack alone: no link is followed (4 MB more)
        launcher.delete_seed(ui, launcher.prepared_seeds())
        self.assertEqual(list(self.seeds.iterdir()), [])
        self.assertFalse((self.packs / "aaa").exists() or (self.copies / "AP_Ledger_aaa").exists())
        self.assertEqual((outside / "precious.bin").stat().st_size, 2**22)
        self.assertTrue((outside / "seed/222/analysis.json").is_file())


class SweepTests(Packs):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(launcher, "RELEASE", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def orphan(self, name, old=True):
        """A pack (1 MB) no seed selects."""
        pack = self.packs / name
        pack.mkdir(parents=True)
        (pack / "rules.txt").write_bytes(bytes(2**20))
        if old:
            self.age(pack)
        return pack

    def age(self, path):
        then = time.time() - 2 * launcher.play_seed.ORPHAN_AGE
        os.utime(path, (then, then))

    def test_a_release_removes_the_old_packs_no_seed_selects(self):
        self.packed("111", "a" * 16)
        self.packed("222", "b" * 16, {"schema": 1, "pack": f"{self.root.name}/packs-from-source/{'b' * 16}"})
        for name in ("a" * 16, "b" * 16):
            self.age(self.packs / name)
        gone = self.orphan("c" * 16)
        for name, old in (("d" * 16, False), ("not a pack", True), ("e" * 15, True), ("F" * 16, True)):
            self.orphan(name, old)
        (self.packs / ("0" * 16)).write_text("a file")
        ui = Answers()
        with mock.patch.object(launcher.play_seed, "ROOT", self.root.parent):
            launcher.sweep(ui)
        self.assertFalse(gone.exists())
        self.assertEqual(sorted(path.name for path in self.packs.iterdir()),
                         sorted(["a" * 16, "b" * 16, "d" * 16, "not a pack", "e" * 15, "F" * 16, "0" * 16]))
        self.assertEqual(ui.text(), "Deleted 1 game pack no seed uses any more (1 MB).")

    def test_the_seed_step_sweeps_first(self):
        pack = self.orphan("c" * 16)
        with self.assertRaises(ValueError):
            launcher.choose_seed(Answers(), str(self.root / "nothing.apbotw"))
        self.assertFalse(pack.exists())

    def test_an_unreadable_selection_removes_nothing(self):
        (self.seed("111") / "play-pack.json").write_text("not json")
        pack = self.orphan("c" * 16)
        launcher.sweep(Answers())
        self.assertTrue(pack.is_dir())

    def test_a_source_checkout_removes_nothing_and_says_nothing(self):
        pack = self.orphan("c" * 16)
        ui = Answers()
        with mock.patch.object(launcher, "RELEASE", False):
            launcher.sweep(ui)
        self.assertTrue(pack.is_dir())
        pack.rename(self.packs / ("d" * 16))
        self.packed("111", "d" * 16)
        launcher.sweep(ui)
        self.assertEqual(ui.said, [])

    @unittest.skipUnless(os.name == "nt", "directory junctions")
    def test_a_link_stays_with_what_it_leads_to(self):
        import _winapi
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "precious.bin").write_bytes(b"kept")
        self.packs.mkdir()
        _winapi.CreateJunction(str(outside), str(self.packs / ("c" * 16)))
        with mock.patch.object(launcher.play_seed, "ORPHAN_AGE", -1):
            launcher.sweep(Answers())
        self.assertEqual((self.packs / ("c" * 16) / "precious.bin").read_bytes(), b"kept")

    @unittest.skipUnless(os.name == "nt", "a file open on Windows cannot be deleted")
    def test_a_pack_a_file_in_use_keeps_goes_another_time(self):
        busy, free = self.orphan("c" * 16), self.orphan("d" * 16)
        ui = Answers()
        with (busy / "rules.txt").open("rb"):
            launcher.sweep(ui)
        self.assertTrue((busy / "rules.txt").is_file())
        self.assertFalse(free.exists())
        self.assertEqual(ui.text(), "Deleted 1 game pack no seed uses any more (1 MB).")


class RoomTests(Folder):
    def test_the_room_is_remembered_and_the_password_asked(self):
        self.seed("111", archive="AP_111_P1_Zelda.apbotw.json")
        ui = Answers(answers=["", "archipelago.gg:38281"], secrets=["secret"])
        self.assertEqual(launcher.choose_room(ui, "111"), ("archipelago.gg:38281", "secret"))
        self.assertIn("Type the room's address", ui.text())     # nothing typed: asked again
        self.assertEqual(launcher.choose_room(Answers(), "111"), ("archipelago.gg:38281", None))

    def test_the_address_of_the_room_comes_from_its_slot_file(self):
        folder = self.seed("111", archive="AP_111_P1_Zelda.apbotw")
        path = slot_file(folder, name="Zelda", container=True, server="archipelago.gg:50212")
        path.rename(folder / "AP_111_P1_Zelda.apbotw")
        ui = Answers(answers=[""])
        self.assertEqual(launcher.choose_room(ui, "111"), ("archipelago.gg:50212", None))

    def test_a_seeds_zip_can_be_hosted_here(self):
        self.seed("111", archive="AP_111.zip")
        with mock.patch.object(launcher.play_seed, "archipelago_here", return_value=True):
            self.assertEqual(launcher.choose_room(Answers(answers=["local"]), "111"), (None, None))
            self.assertEqual(launcher.choose_room(Answers(), "111"), (None, None))

    def test_without_the_archipelago_server_a_room_is_needed(self):
        self.seed("111", archive="AP_111.zip")
        ui = Answers(answers=["archipelago.gg:1"])
        with mock.patch.object(launcher.play_seed, "archipelago_here", return_value=False):
            self.assertEqual(launcher.choose_room(ui, "111"), ("archipelago.gg:1", None))


class MainTests(Folder):
    def test_the_session_starts_with_what_was_chosen(self):
        with mock.patch.object(launcher, "ensure_profile"), \
                mock.patch.object(launcher, "choose_seed", return_value="111") as seed, \
                mock.patch.object(launcher, "choose_room", return_value=("archipelago.gg:1", "pw")), \
                mock.patch("tools.play_session.run") as run:
            self.assertEqual(launcher.main(["seed.apbotw.json"], Answers()), 0)
        seed.assert_called_once_with(mock.ANY, "seed.apbotw.json")
        run.assert_called_once_with("111", connect="archipelago.gg:1", password="pw")

    def test_an_error_before_the_session_is_said_plainly(self):
        ui = Answers()
        with mock.patch.object(launcher, "ensure_profile",
                               side_effect=cemu_install.CemuInstallError("update v192")), \
                mock.patch("tools.play_session.run") as run:
            self.assertEqual(launcher.main([], ui), 1)
        self.assertIn("Error: update v192", ui.text())
        run.assert_not_called()



class TestAidTests(unittest.TestCase):
    def test_a_source_checkout_takes_the_aids_of_play_cmd(self):
        self.assertEqual(launcher.test_aids(["seed.zip"]), (["seed.zip"], {}))
        rest, aids = launcher.test_aids(["seed.zip", "--cheats", "--speed", "3"])
        self.assertEqual(rest, ["seed.zip"])
        self.assertEqual(aids, {"speed": 3.0, "aids": ["Invincible", "Stamina", "Unbreakable"], "damage": 10})

    def test_a_release_refuses_them(self):
        with mock.patch.dict("sys.modules", {"tools.play_aids": None}):
            with self.assertRaisesRegex(ValueError, "not part of a release"):
                launcher.test_aids(["--cheats"])


if __name__ == "__main__":
    unittest.main()
