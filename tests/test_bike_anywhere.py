"""The Master Cycle Zero anywhere outdoors (botw_patch/bike_anywhere.py): the climate
patch group of the native build, the horse-only walls tagged in the resources."""
from __future__ import annotations

from pathlib import Path
import struct
import unittest
import zlib

import oead
import rstb

from botw_patch import bike_anywhere as bike
from botw_patch.resources import unpack
from tools.build_native_from_source import generate
from tools.patch_lint import lint

ROOT = Path(__file__).resolve().parents[1]
UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
HAS_UPDATE = (UPDATE / "Actor/Pack/AirWallHorse.sbactorpack").is_file()
HAS_RPX = (ROOT / "U-King.rpx").is_file()


class NativeTests(unittest.TestCase):
    def test_the_group_comes_only_with_the_option(self):
        self.assertNotIn(bike.GROUP, generate()["runtime/patch_apInject.asm"].decode())
        injection = generate(bike_anywhere=True)["runtime/patch_apInject.asm"].decode()
        self.assertEqual(injection.count(bike.GROUP), 1)
        self.assertTrue(injection.endswith(bike.NATIVE))
        self.assertEqual(lint(injection), [])

    def test_the_tag_hash_is_its_name(self):
        self.assertEqual(zlib.crc32(bike.TAG.encode()), bike.TAG_HASH)

    @unittest.skipUnless(HAS_RPX, "the game's executable is read")
    def test_the_patched_instruction_is_the_climate_lookup(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools/cemu"))
        from rpx import Rpx
        word, = struct.unpack(">I", Rpx(ROOT / "U-King.rpx").read(bike.CLIMATE_CALL, 4))
        self.assertEqual(word >> 26, 18)                                  # bl
        offset = word & 0x3FFFFFC
        self.assertEqual(bike.CLIMATE_CALL + offset - (0x4000000 if offset & 0x2000000 else 0), 0x036728C0)


@unittest.skipUnless(HAS_UPDATE, "the game's files are read")
class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.sizes = rstb.ResourceSizeTable(
            unpack((UPDATE / bike.TABLE).read_bytes()), True)

    def test_only_the_walls_actor_link_changes_and_fits(self):
        for wall in bike.WALLS:
            with self.subTest(wall=wall):
                raw = (UPDATE / f"Actor/Pack/{wall}.sbactorpack").read_bytes()
                self.assertFalse(bike.lets_through(raw, wall))
                new = bike.wall_pack(raw, wall, self.sizes)
                self.assertTrue(bike.lets_through(new, wall))
                before, after = oead.Sarc(unpack(raw)), oead.Sarc(unpack(new))
                changed = {f.name for f in before.get_files()
                           if bytes(f.data) != bytes(after.get_file(f.name).data)}
                self.assertEqual(changed, {f"Actor/ActorLink/{wall}.bxml"})
                with self.assertRaises(ValueError):
                    bike.wall_pack(new, wall, self.sizes)

    def test_actor_info_tags_the_walls_only(self):
        raw = (UPDATE / bike.ACTOR_INFO).read_bytes()
        before = oead.byml.from_binary(unpack(raw))
        after = oead.byml.from_binary(unpack(bike.tag_actor_info(raw)))
        changed = [str(a["name"]) for a, b in zip(before["Actors"], after["Actors"])
                   if oead.byml.to_text(a) != oead.byml.to_text(b)]
        self.assertEqual(sorted(changed), sorted(bike.WALLS))
        for actor in after["Actors"]:
            if str(actor["name"]) in bike.WALLS:
                self.assertEqual(int(actor["tags"][f"tag{bike.TAG_HASH:08x}"]), bike.TAG_HASH)

    def test_the_stage_runs_only_for_a_slot_that_asks(self):
        self.assertFalse(bike.enabled(None))
        self.assertFalse(bike.enabled({"slot_data": {"bike_anywhere": 0}}))
        self.assertTrue(bike.enabled({"slot_data": {"bike_anywhere": 1}}))
        files = {bike.ACTOR_INFO: (UPDATE / bike.ACTOR_INFO).read_bytes(),
                 bike.TABLE: (UPDATE / bike.TABLE).read_bytes()}
        out, changes = bike.generate(files, UPDATE)
        self.assertEqual(set(out) - set(files), {f"Actor/Pack/{wall}.sbactorpack" for wall in bike.WALLS})
        self.assertEqual(out[bike.TABLE], files[bike.TABLE])
        self.assertEqual(len(changes), 1 + len(bike.WALLS))


if __name__ == "__main__":
    unittest.main()
