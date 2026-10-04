import json
from pathlib import Path
import shutil
import tempfile
import unittest

from botw_patch.resources import digest
from tools.build_resource_base_from_source import INPUT_HASHES, ROOT, build
from tests.full_build import full_build


CONTENT = (Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content")
EXPECTED = {
    "Pack/Bootup.pack": "894f6156606fa296b8fa1fb186cc9ae9eadbe40a6b47ae7fbf23102bc93fcc5a",
    "Pack/TitleBG.pack": "ea5983e73e6fee3271d1cacaec42754fa0fdc2306426bc599f730b19e9f848e0",
    "System/Resource/ResourceSizeTable.product.srsizetable":
        "268b7e0f2fe9fa630fd49c5ed1654b9d43584af74280c8214ed70d2d2eb68f68",
}
OWNED_EXPECTED = {
    **EXPECTED,
    "Pack/Bootup.pack": "cdecc57265924d8d767586763cc1ed38fb6ae91cdbb85c3cae7c4e84b3f0e801",
    "Pack/TitleBG.pack": "c9d91c51a32b63753e6d80c627598057072d81f4214c6dde301af403aa3812e9",
    "System/Resource/ResourceSizeTable.product.srsizetable":
        "41ff0eb51b617d13df298e4b961341f9f4b3f07c02a00b2a9241494016224aa8",
    "UI/StockItem/Item_AP.sbitemico":
        "09c6057c14ecd01abb42df9d2975034c931bc93b95188599e866a6f211f24cd3",
}


class ResourceBaseSourceTests(unittest.TestCase):
    @full_build
    @unittest.skipUnless(all((CONTENT / name).is_file() for name in INPUT_HASHES),
                         "requires verified Wii U v208 update")
    def test_clean_build_is_exact_reproducible_and_immutable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            content = root / "content"
            for name in INPUT_HASHES:
                path = content / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(CONTENT / name, path)
            # Pinned digests: equal to them, a build is reproducible (no second build).
            a = build(content, root / "a")
            self.assertEqual(a.name, "9fa8c98c1e172c8d")
            self.assertEqual(json.loads((a / "manifest.json").read_text())["files"], EXPECTED)
            for name, expected in EXPECTED.items():
                self.assertEqual(digest((a / "content" / name).read_bytes()), expected)
            (a / "content/Pack/Bootup.pack").write_bytes(b"altered")
            with self.assertRaisesRegex(ValueError, "immutable resource base modified"):
                build(content, root / "a")

    def test_wrong_dump_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "content/Pack").mkdir(parents=True)
            (root / "content/Pack/Bootup.pack").write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError, "unexpected Wii U update resource"):
                build(root / "content", root / "out")
            self.assertFalse((root / "out").exists())

    @full_build
    @unittest.skipUnless(all((CONTENT / name).is_file() for name in INPUT_HASHES),
                         "requires verified Wii U v208 update")
    def test_presentation_chain_matches_verified_resource_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            target = build(CONTENT, Path(temp) / "out", stage="owned_marker")
            manifest = json.loads((target / "manifest.json").read_text())
            self.assertEqual(manifest["files"], OWNED_EXPECTED)
            self.assertEqual(len(manifest["changes"]), 10)

    def test_optional_historical_oracle(self):
        historical = ROOT / ".build/ledger-validation/9fa8c98c1e172c8d/content"
        if not historical.is_dir():
            self.skipTest("optional historical comparison absent")
        for name, expected in EXPECTED.items():
            self.assertEqual(digest((historical / name).read_bytes()), expected)


if __name__ == "__main__":
    unittest.main()
