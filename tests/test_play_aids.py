"""The test aids of play sessions (tools/play_aids.py): never in a release."""
import argparse
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import play_aids
from tools.play_session import enabled_packs

UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
TABLE = UPDATE / "System/Resource/ResourceSizeTable.product.srsizetable"


class ArgumentTests(unittest.TestCase):
    def run_main(self, *argv):
        from tools import play_session
        with mock.patch.object(play_session, "run") as run:
            play_session.main(list(argv))
        return run.call_args.kwargs

    def test_cheats_turn_every_aid_on(self):
        kwargs = self.run_main("--cheats")
        self.assertEqual(kwargs["aids"], ["Invincible", "Stamina", "Unbreakable"])
        self.assertEqual(kwargs["damage"], 10)

    def test_aids_are_off_unless_asked(self):
        kwargs = self.run_main()
        self.assertEqual((kwargs["aids"], kwargs["damage"]), ([], 1))
        self.assertEqual(self.run_main("--stamina", "--damage", "4")["aids"], ["Stamina"])

    def test_the_damage_factor_is_bounded(self):
        for wrong in ("1", "101", "x", "2.5"):
            with self.assertRaises(argparse.ArgumentTypeError):
                play_aids.damage_argument(wrong)
        self.assertEqual(play_aids.damage_argument("10"), 10)


class PackTests(unittest.TestCase):
    def test_patch_aids_are_packs_of_their_own_enabled_after_the_seed(self):
        with tempfile.TemporaryDirectory() as folder:
            portable = Path(folder)
            (portable / "settings.xml").write_text(
                '<?xml version="1.0"?><content><GraphicPack>'
                '<Entry filename="graphicPacks/AP_Ledger_796aa895aad1ffff/rules.txt"/>'
                "</GraphicPack></content>", encoding="utf-8")
            entries = play_aids.install(portable / "graphicPacks", ["Invincible", "Unbreakable"], 1,
                                        UPDATE, TABLE)
            play_aids.enable(portable, entries)
            self.assertEqual(enabled_packs(portable), [
                "graphicPacks/AP_Ledger_796aa895aad1ffff/rules.txt",
                "graphicPacks/AP_Aid_Invincible/rules.txt", "graphicPacks/AP_Aid_Unbreakable/rules.txt"])
            patch = (portable / "graphicPacks/AP_Aid_Invincible/patch_aid.asm").read_text(encoding="utf-8")
            self.assertIn("moduleMatches = 0x6267BFD0", patch)
            self.assertIn("0x02D452A4 = nop", patch)

    @unittest.skipUnless(TABLE.is_file(), "Wii U update absent")
    def test_a_weapon_changes_its_power_only_and_fits_its_size(self):
        import oead
        import rstb
        from botw_patch.resources import unpack
        sizes = rstb.ResourceSizeTable(unpack(TABLE.read_bytes()), True)
        # The Traveler's Bow: its power, 5, shares its bytes with two other parameters.
        raw = (UPDATE / "Actor/Pack/Weapon_Bow_001.sbactorpack").read_bytes()
        data, before, after = play_aids.stronger_weapon(raw, 10, sizes.get_size("Actor/Pack/Weapon_Bow_001.bactorpack"))
        self.assertEqual((before, after), (5, 50))

        def parameters(pack, power=None):
            sarc = oead.Sarc(oead.yaz0.decompress(pack))
            member = next(f for f in sarc.get_files() if f.name.endswith(".bgparamlist"))
            return play_aids._values(oead.aamp.ParameterIO.from_binary(bytes(member.data)), power)
        self.assertEqual(parameters(data), parameters(raw, 50))
        with self.assertRaises(ValueError):
            play_aids.stronger_weapon(raw, 10, 100)


if __name__ == "__main__":
    unittest.main()
