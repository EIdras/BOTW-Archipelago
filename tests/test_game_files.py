"""The game's files as Cemu shows them (botw_patch/game_files.py)."""
from pathlib import Path
import tempfile
import unittest

from botw_patch.game_files import GameFiles, dlc_reader


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


if __name__ == "__main__":
    unittest.main()
