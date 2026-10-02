"""The GameData flag table read from the player's game (botw_client/gamedata_table.py)."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zlib

import oead

from botw_client import gamedata_table as gt


def signed(name):
    value = zlib.crc32(name.encode())
    return value - (1 << 32) if value >= 1 << 31 else value


def bgdata(kind, names):
    entries = oead.byml.Array([oead.byml.Hash({
        "DataName": name, "HashValue": oead.S32(signed(name))}) for name in names])
    return bytes(oead.byml.to_binary(oead.byml.Hash({kind: entries}), big_endian=True))


def bootup():
    gamedata = oead.SarcWriter(oead.Endianness.Big)
    gamedata.files["/bool_data_0.bgdata"] = bgdata("bool_data", ["IsGet_Obj_Test", "Open_Door"])
    gamedata.files["/s32_data_0.bgdata"] = bgdata("s32_data", ["CurrentRupee"])
    gamedata.files["/bool_array_data_0.bgdata"] = bgdata("bool_array_data", ["Flags"])
    outer = oead.SarcWriter(oead.Endianness.Big)
    outer.files[gt.GAMEDATA] = bytes(oead.yaz0.compress(gamedata.write()[1]))
    return bytes(outer.write()[1])


class TableTests(unittest.TestCase):
    def test_every_flag_of_every_type_with_its_hash(self):
        table = gt.extract(bootup())
        self.assertEqual(table, {str(signed(n)): [k, n] for k, n in sorted(
            [("bool", "IsGet_Obj_Test"), ("bool", "Open_Door"), ("s32", "CurrentRupee"),
             ("bool_array", "Flags")], key=lambda kn: signed(kn[1]))})
        self.assertEqual(list(table), sorted(table, key=int))

    def test_built_once_then_read(self):
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp) / "content"
            (content / "Pack").mkdir(parents=True)
            (content / gt.BOOTUP).write_bytes(bootup())
            table = Path(temp) / "gamedata.json"
            gt.build(content, table)
            self.assertEqual(gt.load(table)[str(signed("CurrentRupee"))], ["s32", "CurrentRupee"])

    def test_without_table_nor_game_the_error_says_what_to_do(self):
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.object(gt, "DEFAULT_CONTENT", Path(temp) / "none"):
            with self.assertRaisesRegex(gt.GameDataTableMissing, "play_seed"):
                gt.load(Path(temp) / "gamedata.json")


@unittest.skipUnless((gt.DEFAULT_CONTENT / gt.BOOTUP).is_file(), "Wii U update dump absent")
class GameTableTests(unittest.TestCase):
    def test_the_update_holds_the_45011_flags(self):
        table = gt.extract((gt.DEFAULT_CONTENT / gt.BOOTUP).read_bytes())
        self.assertEqual(len(table), 45011)
        self.assertEqual(table[str(signed("IsGet_Obj_DLC_HeroSoul_Zora"))],
                         ["bool", "IsGet_Obj_DLC_HeroSoul_Zora"])


if __name__ == "__main__":
    unittest.main()
