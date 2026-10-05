"""The French names table (botw_world/docs/names_fr.md) follows the world."""
import unittest

from tools import build_names_fr as names

HAVE_GAME = all((names.UPDATE / f"Pack/Bootup_{language}.pack").is_file() for language in ("EUen", "EUfr"))


@unittest.skipUnless(HAVE_GAME, "Wii U update absent")
class NamesTests(unittest.TestCase):
    def test_the_table_is_up_to_date(self):
        # A location or item added to the world: run tools/build_names_fr.py.
        self.assertEqual(names.OUTPUT.read_text(encoding="utf-8"), names.build(names.UPDATE))

    def test_the_game_names_differ_from_a_translation(self):
        table = names.OUTPUT.read_text(encoding="utf-8")
        self.assertIn("| Tah Muhl Shrine | Sanctuaire de Ta'Mur |", table)
        self.assertIn("| Kara Kara Bazaar - Beedle Item 1 | Bazar Assek : Beedle, objet 1 |", table)
        self.assertNotIn("\x0e", table)


if __name__ == "__main__":
    unittest.main()
