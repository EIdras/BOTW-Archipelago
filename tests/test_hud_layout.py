"""The AP connection indicator of the HUD: layout resources."""
from pathlib import Path
import struct
import unittest

import oead

from botw_patch import hud_layout as hud
from botw_patch.resources import unpack

CONTENT = Path(r"C:\Users\Simon\AppData\Roaming\Cemu\mlc01\usr\title\0005000e\101c9500\content")
ICON = Path(__file__).resolve().parents[1] / "assets/wiiu/Item_AP.sbitemico"


def common():
    boot = oead.Sarc(unpack((CONTENT / "Pack/Bootup.pack").read_bytes()))
    return unpack(bytes(boot.get_file(hud.ARCHIVE).data))


@unittest.skipUnless((CONTENT / "Pack/Bootup.pack").is_file(), "requires the Wii U update")
class HudLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = common()
        cls.archive = oead.Sarc(cls.raw)

    def file(self, name):
        return bytes(self.archive.get_file(name).data)

    def test_every_vanilla_layout_round_trips(self):
        count = 0
        for f in self.archive.get_files():
            if f.name.startswith("blyt/"):
                raw = bytes(f.data)
                self.assertEqual(hud.write_layout(*hud.read_layout(raw)), raw, f.name)
                count += 1
        self.assertEqual(count, 330)

    def test_vanilla_srgb_textures_round_trip(self):
        for f in self.archive.get_files():
            if f.name.endswith("^l.bflim"):
                raw = bytes(f.data)
                width, height, rgba = hud.read_flim(raw)
                swizzle = raw[len(raw) - 0x14 + 15] >> 5
                again = hud.write_flim(width, height, rgba, swizzle)
                self.assertEqual(hud.read_flim(again), (width, height, rgba), f.name)
                self.assertEqual(len(again), len(raw), f.name)
                # Header bytes 0x12-0x13 are 0 on small textures (the key,
                # 16 KB, like ours) and grow with the size on big ones.
                self.assertEqual(again[-0x28:-0x16] + again[-0x14:],
                                 raw[-0x28:-0x16] + raw[-0x14:], f.name)
                if len(raw) <= 0x8000:
                    self.assertEqual(again[-0x28:], raw[-0x28:], f.name)

    def test_part_layout_has_two_logos_offline_shown(self):
        _header, sections = hud.read_layout(hud.part_layout(self.file(hud.TEMPLATE)))
        kinds = [m for m, _ in sections]
        self.assertEqual(kinds, [b"lyt1", b"txl1", b"mat1", b"pan1", b"pas1", b"pic1",
                                 b"pic1", b"pae1", b"grp1"])
        body = dict(sections)
        self.assertIn(hud.PART_LAYOUT.encode() + b"\0", body[b"lyt1"])
        txl = body[b"txl1"]
        self.assertEqual(struct.unpack_from(">H", txl, 0)[0], 2)
        self.assertIn(b"Nt_APOffline_00^l.bflim\0", txl)
        self.assertIn(b"Nt_APOnline_00^l.bflim\0", txl)
        mat = body[b"mat1"]
        count, first, second = struct.unpack_from(">HxxII", mat, 0)
        self.assertEqual((count, first, second), (2, 0x14, 0x14 + 0x48))
        for offset, (name, texture) in zip((first, second), ((hud.OFFLINE, 0), (hud.ONLINE, 1))):
            entry = mat[offset - 8:offset - 8 + 0x48]
            self.assertEqual(entry[:0x1c].split(b"\0")[0].decode(), name)
            self.assertEqual(struct.unpack_from(">H", entry, 0x28)[0], texture)
            self.assertEqual(entry[0x20:0x24], b"\xff\xff\xff\xff")
        pictures = [data for m, data in sections if m == b"pic1"]
        self.assertEqual([(hud.pane_name(p), p[0] & 1, struct.unpack_from(">H", p, 0x5c)[0])
                          for p in pictures], [(hud.OFFLINE, 1, 0), (hud.ONLINE, 0, 1)])
        self.assertEqual(len(mat) % 4, 0)
        self.assertEqual(len(txl) % 4, 0)

    def test_the_part_goes_last_under_the_whole_hud_node(self):
        screen = self.file(hud.SCREEN)
        new, _ = hud.add_part(screen)
        _h, before = hud.read_layout(screen)
        _h, after = hud.read_layout(new)
        self.assertEqual(len(after), len(before) + 1)
        index = next(i for i, (m, d) in enumerate(after)
                     if m == b"prt1" and hud.pane_name(d) == hud.PART_PANE)
        self.assertEqual(hud.pane_name(after[index - 1][1]), hud.PARENT_LAST)
        self.assertEqual(after[index + 1][0], b"pae1")
        part = after[index][1]
        self.assertEqual(struct.unpack_from(">ff", part, 0x24), hud.POSITION)
        self.assertEqual(struct.unpack_from(">ff", part, 0x44), (hud.SIZE, hud.SIZE))
        self.assertEqual(part[0x58:].split(b"\0")[0].decode(), hud.PART_LAYOUT)
        self.assertEqual(after[:index] + after[index + 1:], before)
        with self.assertRaises(ValueError):
            hud.add_part(new)

    def test_textures_are_the_logo_in_colour_and_in_grey(self):
        made = hud.textures(ICON.read_bytes())
        on = hud.read_flim(made[f"timg/{hud.TEXTURES[hud.ONLINE]}"])
        off = hud.read_flim(made[f"timg/{hud.TEXTURES[hud.OFFLINE]}"])
        self.assertEqual(on[:2], (64, 64))
        pixels = [on[2][i:i + 4] for i in range(0, len(on[2]), 4)]
        self.assertEqual(pixels[0][3], 0)                        # transparent corner
        self.assertTrue(any(p[0] != p[2] for p in pixels if p[3]))  # coloured
        grey = [off[2][i:i + 4] for i in range(0, len(off[2]), 4)]
        self.assertTrue(all(p[0] == p[1] == p[2] for p in grey))
        self.assertEqual([p[3] for p in grey], [p[3] for p in pixels])

    def test_archive_gains_the_part_and_its_three_files(self):
        out, detail = hud.patch_archive(self.raw, ICON.read_bytes())
        archive = oead.Sarc(out)
        for name in detail["added"]:
            self.assertIsNotNone(archive.get_file(name), name)
        self.assertEqual(len(list(archive.get_files())), len(list(self.archive.get_files())) + 3)


if __name__ == "__main__":
    unittest.main()
