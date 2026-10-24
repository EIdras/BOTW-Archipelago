"""The player's launcher (tools/launcher.py), with scripted answers."""
import json
from pathlib import Path
import tempfile
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
        for patcher in (mock.patch.object(launcher.play_seed, "PLAY_SEEDS", self.seeds),
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
