"""The game's files as Cemu shows them (botw_patch/game_files.py)."""
from pathlib import Path
import tempfile
import unittest

import oead

from botw_patch.game_files import GameFiles, ModConflict, dlc_checked, dlc_reader, guard, own_member
from botw_patch.resources import vanilla_digest


def sarc(members: dict[str, bytes]) -> bytes:
    writer = oead.SarcWriter(oead.Endianness.Big)
    for name, data in members.items():
        writer.files[name] = data
    return bytes(writer.write()[1])


def write(root: Path, files: dict[str, bytes]) -> Path:
    for name, data in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data)
    return root


class GameFilesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.content = write(root / "update/content", {"Pack/Bootup.pack": b"update",
                                                      "Event/B.sbeventpack": b"b", "Event/a.sbeventpack": b"a"})
        self.aoc = write(root / "dlc/content/0010", {"Map/A.smubin": b"dlc"})
        self.low = write(root / "low", {"content/Pack/Bootup.pack": b"low", "content/Event/C.sbeventpack": b"c"})
        self.high = write(root / "high", {"content/Pack/Bootup.pack": b"high",
                                          "aoc/0010/Map/A.smubin": b"pack dlc"})

    def tearDown(self):
        self.temp.cleanup()

    def test_the_game_alone(self):
        game = GameFiles(self.content, self.aoc)
        self.assertEqual((game.read("Pack/Bootup.pack"), game.read_aoc("Map/A.smubin")), (b"update", b"dlc"))
        self.assertIsNone(game.provider("Pack/Bootup.pack"))
        self.assertFalse(game.exists("Pack/Missing.pack"))
        with self.assertRaises(FileNotFoundError):
            game.read("Pack/Missing.pack")
        self.assertIs(GameFiles.of(game), game)
        self.assertEqual(GameFiles.of(self.content).read("Pack/Bootup.pack"), b"update")

    def test_the_winning_pack_gives_each_file(self):
        game = GameFiles(self.content, self.aoc, [self.high, self.low])
        self.assertEqual(game.read("Pack/Bootup.pack"), b"high")
        self.assertEqual(game.provider("Pack/Bootup.pack"), self.high.resolve())
        self.assertEqual(game.read("Event/C.sbeventpack"), b"c")
        self.assertEqual(game.read("Event/a.sbeventpack"), b"a")
        self.assertEqual(game.read_aoc("Map/A.smubin"), b"pack dlc")
        self.assertEqual(game.provider_aoc("Map/A.smubin"), self.high.resolve())
        self.assertEqual(dlc_reader(game)("Map/A.smubin"), b"pack dlc")
        self.assertEqual(dlc_reader(self.aoc)("Map/A.smubin"), b"dlc")

    def test_names_join_the_layers_in_folder_order(self):
        game = GameFiles(self.content, self.aoc, [self.low])
        self.assertEqual(game.names("Event", "*.sbeventpack"),
                         sorted(["Event/a.sbeventpack", "Event/B.sbeventpack", "Event/C.sbeventpack"], key=Path))

    def test_names_cannot_leave_the_game(self):
        game = GameFiles(self.content)
        for name in ("../outside.pack", "/Pack/Bootup.pack", "Pack\\Bootup.pack"):
            with self.assertRaisesRegex(ValueError, "escapes"):
                game.read(name)
        with self.assertRaises(FileNotFoundError):
            game.read_aoc("Map/A.smubin")       # no DLC given

    def test_checked_judges_the_update_not_the_pack(self):
        game = GameFiles(self.content, self.aoc, [self.high])
        own = vanilla_digest(b"update")
        self.assertEqual(game.checked("Pack/Bootup.pack", own), b"high")
        with self.assertRaisesRegex(ValueError, "unexpected update resource: Pack/Bootup.pack"):
            game.checked("Pack/Bootup.pack", vanilla_digest(b"high"))
        self.assertEqual(game.original("Pack/Bootup.pack"), b"update")
        self.assertEqual(game.checked_aoc("Map/A.smubin", vanilla_digest(b"dlc")), b"pack dlc")
        self.assertEqual(dlc_checked(game)("Map/A.smubin", vanilla_digest(b"dlc")), b"pack dlc")
        self.assertEqual(dlc_checked(self.aoc)("Map/A.smubin", vanilla_digest(b"dlc")), b"dlc")
        with self.assertRaisesRegex(ValueError, "unexpected DLC map"):
            dlc_checked(self.aoc)("Map/A.smubin", vanilla_digest(b"other"))


class RewriteGuardTest(unittest.TestCase):
    """A flow a seed pack rebuilds must be the game's own in a mod's archive."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        vanilla = {"EventFlow/A.bfevfl": b"flow a", "EventFlow/B.bfevfl": b"flow b", "Quest/Q.byml": b"q" * 64}
        self.content = write(root / "update/content", {"Pack/TitleBG.pack": sarc(vanilla)})
        modded = {**vanilla, "EventFlow/B.bfevfl": b"flow b, modded", "Quest/Q.byml": b"q" * 8,
                  "Model/New.sbfres": b"model"}
        self.mod = write(root / "SomeMod", {"content/Pack/TitleBG.pack": sarc(modded)})

    def tearDown(self):
        self.temp.cleanup()

    def test_only_while_a_build_reads_the_game(self):
        guard("Pack/TitleBG.pack", "EventFlow/B.bfevfl")
        self.assertIsNone(own_member("Pack/TitleBG.pack", "Quest/Q.byml"))

    def test_a_changed_flow_is_refused_naming_the_pack(self):
        with GameFiles(self.content, packs=[self.mod]).active():
            guard("Pack/TitleBG.pack", "EventFlow/A.bfevfl")        # unchanged by the mod
            guard("Pack/TitleBG.pack", "Quest/Q.byml")              # data: built on, not rebuilt
            guard("Pack/TitleBG.pack", "EventFlow/New.bfevfl")      # one we add
            with self.assertRaisesRegex(ModConflict, "SomeMod changes EventFlow/B.bfevfl in Pack/TitleBG.pack"):
                guard("Pack/TitleBG.pack", "EventFlow/B.bfevfl")
        with GameFiles(self.content).active():                      # no mod: nothing to refuse
            guard("Pack/TitleBG.pack", "EventFlow/B.bfevfl")

    def test_the_games_own_member_sizes_what_a_mod_encodes_smaller(self):
        with GameFiles(self.content, packs=[self.mod]).active():
            self.assertEqual(own_member("Pack/TitleBG.pack", "Quest/Q.byml"), b"q" * 64)
            self.assertIsNone(own_member("Pack/Other.pack", "Quest/Q.byml"))
        with GameFiles(self.content).active():
            self.assertIsNone(own_member("Pack/TitleBG.pack", "Quest/Q.byml"))


if __name__ == "__main__":
    unittest.main()
