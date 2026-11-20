"""The shared shrines (botw_patch/shrine_chests.py): built once from the base
game, each shrine chest that is a location holding its item, enabled by the
sessions of the seeds that ask for them."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import oead

from botw_patch import chests, shrine_chests
from botw_patch.resources import ResourceBuilder, unpack
from tests.full_build import full_build


def unit(*objs) -> bytes:
    return bytes(oead.byml.to_binary(oead.byml.Hash({"Objs": oead.byml.Array([
        oead.byml.Hash({"UnitConfigName": actor, "HashId": oead.U32(hash_id),
                        "!Parameters": oead.byml.Hash({"DropActor": drop})})
        for actor, hash_id, drop in objs])}), big_endian=True))


class SharedShrineTests(unittest.TestCase):
    def test_the_listed_chests_are_the_shrines_locations(self):
        listed = shrine_chests.listed()
        self.assertEqual(len(listed), 174)
        first, last = chests.SHRINES_HELD
        self.assertTrue(all(first <= number <= last and flag.startswith("CDungeon_TBox_Dungeon")
                            for flag, number in listed.items()))

    def test_the_key_depends_on_what_the_shrines_hold_not_on_the_seed(self):
        key = shrine_chests.key()
        self.assertEqual(shrine_chests.key(), key)
        with mock.patch.object(shrine_chests, "listed", return_value={"CDungeon_TBox_Dungeon_Stone_1": 1191}):
            self.assertNotEqual(shrine_chests.key(), key)

    def test_only_a_listed_chest_gets_its_item(self):
        raw = unit(("TBox_Dungeon_Stone", 5, "Item_Ore_A"), ("TBox_Dungeon_Iron", 6, "Weapon_Sword_001"))
        new, given = shrine_chests.changed_unit(raw, {"CDungeon_TBox_Dungeon_Stone_5": 1200})
        self.assertEqual(given, ["CDungeon_TBox_Dungeon_Stone_5"])
        drops = [str(o["!Parameters"]["DropActor"]) for o in oead.byml.from_binary(unpack(new))["Objs"]]
        self.assertEqual(drops, [chests.actor(1200), "Weapon_Sword_001"])

    def test_a_session_without_them_enables_nothing(self):
        from tools import play_session
        with tempfile.TemporaryDirectory() as temp:
            pack = Path(temp)
            (pack / "delivery_catalog.json").write_text(json.dumps({"chests": {"held": [[1, 1190]]}}))
            self.assertEqual(play_session.enable_shrines(pack, pack), [])


class InstallTests(unittest.TestCase):
    @full_build
    def test_built_once_then_reused_and_the_old_version_removed(self):
        from tools import cemu_profile
        base = cemu_profile.base_content()
        if base is None:
            self.skipTest("requires the base game as a folder")
        table = ResourceBuilder(cemu_profile.update() / "content").table
        with tempfile.TemporaryDirectory() as temp:
            packs = Path(temp)
            (packs / (shrine_chests.PREFIX + "old")).mkdir()
            folder = shrine_chests.install(base, table, packs)
            self.assertEqual([p.name for p in packs.iterdir()], [folder.name])
            record = json.loads((folder / shrine_chests.RECORD).read_text(encoding="utf-8"))
            built = (folder / "content/Pack/Dungeon000.pack").stat().st_mtime_ns
            self.assertEqual(shrine_chests.install(base, table, packs), folder)
            self.assertEqual((folder / "content/Pack/Dungeon000.pack").stat().st_mtime_ns, built)
            listed, given = shrine_chests.listed(), {}
            for name in record["files"]:
                if not name.endswith(".pack"):
                    continue
                dungeon = Path(name).stem
                ours = oead.Sarc((folder / name).read_bytes())
                theirs = oead.Sarc(unpack((base / f"Pack/{dungeon}.pack").read_bytes()))
                member = chests.shrine_unit(dungeon)
                self.assertEqual({f.name: bytes(f.data) for f in ours.get_files() if f.name != member},
                                 {f.name: bytes(f.data) for f in theirs.get_files() if f.name != member})
                for obj in oead.byml.from_binary(unpack(bytes(ours.get_file(member).data)))["Objs"]:
                    if str(obj["UnitConfigName"]).startswith(chests.DUNGEON_PREFIX):
                        given[chests.shrine_flag(obj)] = str(obj["!Parameters"]["DropActor"])
            self.assertEqual({flag: given[flag] for flag in listed},
                             {flag: chests.actor(number) for flag, number in listed.items()})


if __name__ == "__main__":
    unittest.main()
