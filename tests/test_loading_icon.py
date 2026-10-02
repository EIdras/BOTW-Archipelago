"""The Archipelago icon of the loading screen: layout resources."""
from pathlib import Path
import struct
import unittest

import numpy as np
import oead

from botw_patch import hud_layout as hud
from botw_patch import loading_icon as li
from tests.test_hud_layout import CONTENT, ICON, common


class SilhouetteTests(unittest.TestCase):
    def test_black_with_the_lighter_details_cut_out(self):
        # A dark disc with a lighter ring: the disc stays, the ring goes.
        size = 64
        y, x = np.mgrid[:size, :size]
        radius = np.hypot(x - 32, y - 32)
        rgba = np.zeros((size, size, 4), dtype=np.uint8)
        rgba[..., :3] = np.where((radius > 12) & (radius < 15), 220, 60)[..., None]
        rgba[..., 3] = np.where(radius < 28, 255, 0)
        out = np.frombuffer(li.silhouette(size, size, rgba.tobytes()),
                            dtype=np.uint8).reshape(size, size, 4)
        self.assertEqual(int(out[..., :3].max()), 0)                # black only
        self.assertEqual(int(out[32, 32, 3]), 255)                  # the dark centre stays
        self.assertEqual(int(out[32, 32 + 13, 3]), 0)               # the lighter ring is cut
        self.assertEqual(int(out[32, 32 + 22, 3]), 255)             # the dark rim stays
        self.assertEqual(int(out[0, 0, 3]), 0)                      # transparent stays so

    def test_the_texture_is_reproducible(self):
        raw = ICON.read_bytes()
        first = li.texture(raw)
        self.assertEqual(li.texture(raw), first)
        width, height, rgba = hud.read_flim(first)
        self.assertEqual((width, height), (li.TEXTURE_SIZE, li.TEXTURE_SIZE))
        alpha = np.frombuffer(rgba, dtype=np.uint8)[3::4]
        self.assertTrue(0.2 < (alpha > 128).mean() < 0.8)


@unittest.skipUnless((CONTENT / "Pack/Bootup.pack").is_file(), "requires the Wii U update")
class LoadingScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = common()
        cls.patched, cls.detail = li.patch_archive(cls.raw, ICON.read_bytes())
        cls.archive = oead.Sarc(cls.patched)

    def sections(self, name):
        return hud.read_layout(bytes(self.archive.get_file(name).data))[1]

    def test_the_part_follows_the_icons_under_their_node(self):
        sections = self.sections(li.SCREEN)
        names = [hud.pane_name(d) if m in (b"pan1", b"prt1", b"pic1") else m.decode()
                 for m, d in sections]
        at = names.index(li.PART_PANE)
        self.assertEqual(names[at - 1], "Pa_Ancient_00")
        self.assertEqual(names[at + 1], "N_Pos_00")
        data = sections[at][1]
        model = sections[names.index("Pa_DLC_00")][1]
        self.assertEqual(data[0], model[0])                          # visible, alpha inherited
        self.assertEqual(struct.unpack_from(">ff", data, 0x24), li.POSITION)
        self.assertEqual(struct.unpack_from(">ff", data, 0x44), (li.SIZE, li.SIZE))
        self.assertEqual(data[0x58:].split(b"\0")[0].decode(), li.PART_LAYOUT)
        # Everything else of the screen is unchanged.
        vanilla = hud.read_layout(bytes(oead.Sarc(self.raw).get_file(li.SCREEN).data))[1]
        self.assertEqual(sections[:at] + sections[at + 1:], vanilla)

    def test_the_part_layout_is_one_picture_of_the_silhouette(self):
        sections = self.sections(f"blyt/{li.PART_LAYOUT}.bflyt")
        pictures = [d for m, d in sections if m == b"pic1"]
        self.assertEqual([hud.pane_name(d) for d in pictures], [li.PICTURE])
        self.assertEqual(pictures[0][0] & 1, 1)
        txl = dict(sections)[b"txl1"]
        self.assertIn(li.TEXTURE.encode(), txl)
        self.assertIsNotNone(self.archive.get_file(f"timg/{li.TEXTURE}"))

    def test_it_is_added_once(self):
        with self.assertRaises(ValueError):
            li.patch_archive(self.patched, ICON.read_bytes())


if __name__ == "__main__":
    unittest.main()
