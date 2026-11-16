"""The GameData and save format rewriters (tools/build_game_data_mod.py), on small tables."""
import unittest

import oead

from tools.build_game_data_mod import definition, modify_gamedata_flags, modify_saveformat, open_yaz_sarc, signed_crc


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


def save_entry(name: str):
    return oead.byml.Hash({"DataName": name, "HashValue": oead.S32(signed_crc(name))})


def save_page(number: int, names):
    header = oead.byml.Hash({"IsCommon": False, "IsCommonAtSameAccount": False, "IsSaveSecureCode": True,
                             "file_name": f"page_{number}.sav"})
    return oead.byml.Hash({"file_list": oead.byml.Array([header, oead.byml.Array([save_entry(n) for n in names])])})


def save_names(raw: bytes, number: int) -> list[str]:
    document = oead.byml.from_binary(member(raw, f"/saveformat_{number}.bgsvdata"))
    return [str(entry["DataName"]) for entry in document["file_list"][1]]


class GameDataFlagTests(unittest.TestCase):
    def setUp(self):
        self.raw = archive({"/bool_data_0.bgdata": bool_page("First", "Second"),
                            "/bool_data_1.bgdata": bool_page("Third"),
                            "/s32_data_0.bgdata": oead.byml.Hash({"s32_data": oead.byml.Array([
                                definition("Counter", False)])})})

    def test_new_flags_end_the_last_page_and_nothing_else_changes(self):
        out = modify_gamedata_flags(self.raw, ("Third", "NewA", "NewB"), is_save=True, kind="bool")
        for untouched in ("/bool_data_0.bgdata", "/s32_data_0.bgdata"):
            self.assertEqual(member(out, untouched), member(self.raw, untouched))
        entries = oead.byml.from_binary(member(out, "/bool_data_1.bgdata"))["bool_data"]
        self.assertEqual([str(entry["DataName"]) for entry in entries], ["Third", "NewA", "NewB"])
        self.assertEqual(int(entries[1]["HashValue"]), signed_crc("NewA"))
        self.assertTrue(entries[1]["IsSave"])
        self.assertFalse(entries[0]["IsSave"])

    def test_known_flags_leave_the_table_as_it_is(self):
        out = modify_gamedata_flags(self.raw, ("First", "Third"), is_save=True, kind="bool")
        self.assertEqual(member(out, "/bool_data_1.bgdata"), member(self.raw, "/bool_data_1.bgdata"))

    def test_a_name_whose_hash_another_flag_has_is_refused(self):
        taken = definition("Other", False, "bool")
        taken["HashValue"] = oead.S32(signed_crc("NewA"))
        raw = archive({"/bool_data_0.bgdata": oead.byml.Hash({"bool_data": oead.byml.Array([taken])})})
        with self.assertRaisesRegex(RuntimeError, "NewA and Other"):
            modify_gamedata_flags(raw, ("NewA",), is_save=True, kind="bool")


class SaveFormatTests(unittest.TestCase):
    def test_entries_are_sorted_by_hash_over_the_pages_whose_headers_stay(self):
        # A first page already full, and one more entry on the last: a new flag moves entries between pages.
        names = sorted((f"Flag_{number}" for number in range(8193)), key=signed_crc)
        pages = {0: names[1:], 5: names[:1]}
        raw = archive({f"/saveformat_{number}.bgsvdata": save_page(number, pages.get(number, ()))
                       for number in range(6)})
        out = modify_saveformat(raw, ("NewFlag", names[7]))
        expected = sorted([*names, "NewFlag"], key=signed_crc)
        self.assertEqual(save_names(out, 0), expected[:8192])
        self.assertEqual(save_names(out, 1), expected[8192:])
        self.assertEqual([save_names(out, number) for number in range(2, 6)], [[]] * 4)
        for number in range(6):
            header = oead.byml.from_binary(member(out, f"/saveformat_{number}.bgsvdata"))["file_list"][0]
            self.assertEqual(str(header["file_name"]), f"page_{number}.sav")
        # Chained, as the build does: the same table as both flags at once.
        self.assertEqual(modify_saveformat(modify_saveformat(raw, ("NewFlag",)), (names[7],)), out)


if __name__ == "__main__":
    unittest.main()
