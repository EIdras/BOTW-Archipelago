"""BYML written with every container a node of its own (botw_patch/byml_unshared.py)."""
from pathlib import Path
import struct
import unittest

import oead

from botw_patch.byml_unshared import to_binary
from botw_patch.resources import unpack

CONTENT = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"


def container_offsets(raw: bytes) -> list[int]:
    """Every offset at which a hash or an array is referenced, root included."""
    found = []

    def node(at: int) -> None:
        found.append(at)
        kind, count = raw[at], int.from_bytes(raw[at + 1:at + 4], "big")
        if kind == 0xC1:
            for i in range(count):
                entry = at + 4 + 8 * i
                if raw[entry + 3] in (0xC0, 0xC1):
                    node(struct.unpack_from(">I", raw, entry + 4)[0])
        elif kind == 0xC0:
            values = at + 4 + ((count + 3) & ~3)
            for i in range(count):
                if raw[at + 4 + i] in (0xC0, 0xC1):
                    node(struct.unpack_from(">I", raw, values + 4 * i)[0])
    node(struct.unpack_from(">I", raw, 12)[0])
    return found


class WriterTests(unittest.TestCase):
    def test_identical_containers_stay_apart(self):
        def twin():
            return oead.byml.Hash({"A": oead.S32(1), "B": "x"})
        doc = oead.byml.Array([twin(), twin(),
                               oead.byml.Hash({"C": True, "D": oead.F32(1.5), "E": oead.U32(7),
                                               "F": oead.byml.Array([])})])
        raw = to_binary(doc)
        self.assertEqual(oead.byml.from_binary(raw), doc)
        offsets = container_offsets(raw)
        self.assertEqual(len(offsets), len(set(offsets)))
        self.assertEqual(len(offsets), 5)                   # the root, three hashes, one array
        shared = bytes(oead.byml.to_binary(doc, big_endian=True))
        self.assertLess(len(set(container_offsets(shared))), 5)    # oead's: the twins share a node

    @unittest.skipUnless((CONTENT / "Pack/TitleBG.pack").is_file(), "requires the Wii U update")
    def test_the_games_quest_file_comes_back_at_its_size_with_no_node_shared(self):
        title = oead.Sarc(unpack((CONTENT / "Pack/TitleBG.pack").read_bytes()))
        raw = unpack(bytes(title.get_file("Quest/QuestProduct.sbquestpack").data))
        data = oead.byml.from_binary(raw)
        ours = to_binary(data)
        self.assertEqual(len(ours), len(raw))
        self.assertEqual(ours[:16], raw[:16])
        self.assertEqual(oead.byml.from_binary(ours), data)
        offsets = container_offsets(ours)
        self.assertEqual(len(offsets), len(set(offsets)))
        self.assertEqual(sorted(container_offsets(raw)) == sorted(set(container_offsets(raw))), True)


if __name__ == "__main__":
    unittest.main()
