"""The GameData rewriter (tools/build_game_data_mod.py), on a small table."""
import unittest

import oead

from tools.build_game_data_mod import definition, modify_gamedata_flags, open_yaz_sarc


def archive(members: dict) -> bytes:
    writer = oead.SarcWriter(endian=oead.Endianness.Big)
    for name, document in members.items():
        writer.files[name] = bytes(oead.byml.to_binary(document, big_endian=True, version=2))
    return bytes(oead.yaz0.compress(bytes(writer.write()[1])))


def member(raw: bytes, name: str) -> bytes:
    sarc = open_yaz_sarc(raw)       # kept while its member is read: the member is a view into it
    return bytes(sarc.get_file(name).data)


def bool_page(*names: str):
    return oead.byml.Hash({"bool_data": oead.byml.Array([definition(name, False, "bool") for name in names])})


class GameDataFlagTests(unittest.TestCase):
    def setUp(self):
        self.raw = archive({"/bool_data_0.bgdata": bool_page("First", "Second"),
                            "/bool_data_1.bgdata": bool_page("Third"),
                            "/s32_data_0.bgdata": oead.byml.Hash({"s32_data": oead.byml.Array([
                                definition("Counter", False)])})})

    def test_a_one_trigger_flag_is_declared_so_and_the_others_are_not(self):
        out = modify_gamedata_flags(self.raw, ("Kept",), is_save=True, kind="bool", one_trigger=True)
        out = modify_gamedata_flags(out, ("Free",), is_save=True, kind="bool")
        entries = {str(e["DataName"]): e for e in oead.byml.from_binary(member(out, "/bool_data_1.bgdata"))["bool_data"]}
        self.assertTrue(entries["Kept"]["IsOneTrigger"])
        self.assertFalse(entries["Free"]["IsOneTrigger"])
        with self.assertRaisesRegex(ValueError, "bool only"):
            modify_gamedata_flags(self.raw, ("Count",), is_save=True, one_trigger=True)

