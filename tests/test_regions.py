"""The versions of the game (botw_client/regions.py): which one an update is, the
European hashes of another's resources, its language archives in the build."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from botw_client import regions
from tests.full_build import full_build

ROOT = Path(__file__).resolve().parents[1]
MLC = Path(os.environ.get("APPDATA", "")) / "Cemu/mlc01/usr/title"
REPORT = ROOT / ".build/play-seeds/08278964164390492688/analysis.json"


def update(root: Path, *languages: str) -> Path:
    (root / "Pack").mkdir(parents=True)
    for language in languages:
        (root / f"Pack/Bootup_{language}.pack").write_bytes(b"")
    return root


class RegionTests(unittest.TestCase):
    def test_an_update_is_known_by_its_main_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertIs(regions.of_content(update(Path(temp) / "eu", "EUen", "EUfr")), regions.EUR)
            self.assertIs(regions.of_content(update(Path(temp) / "us", "USen", "USfr")), regions.USA)
            self.assertIs(regions.of_content(update(Path(temp) / "jp", "JPja")), regions.JPN)
            with self.assertRaisesRegex(ValueError, "not the update of a supported version"):
                regions.of_content(update(Path(temp) / "other", "KRko"))

    def test_a_text_is_its_languages_else_its_european_counterparts(self):
        texts = {"EUen": "en", "EUfr": "fr", "JPja": "ja"}
        self.assertEqual([regions.localized(texts, l) for l in ("USen", "USfr", "JPja", "EUen")],
                         ["en", "fr", "ja", "en"])
        with self.assertRaises(KeyError):
            regions.localized({"EUen": "en"}, "JPja")

    def test_a_japanese_build_reads_its_one_language_archive_for_any_european_one(self):
        table = json.loads(regions.HASHES.read_text(encoding="utf-8"))["JPN"]["languages"]
        with tempfile.TemporaryDirectory() as temp:
            content = update(Path(temp), "JPja")
            self.assertEqual(regions.inputs({"Pack/Bootup.pack": "a", "Pack/Bootup_EUen.pack": "b"}, content),
                             {"Pack/Bootup.pack": "a", "Pack/Bootup_JPja.pack": table["Pack/Bootup_JPja.pack"]})
            self.assertEqual(regions.inputs({"Pack/Bootup.pack": "a"}, content), {"Pack/Bootup.pack": "a"})

    def test_the_title_ids(self):
        self.assertEqual(regions.USA.title_id(), "00050000101C9400")
        self.assertEqual(regions.EUR.title_id("0005000e"), "0005000E101C9500")
        self.assertIs(regions.by_title("00050000101C9400"), regions.USA)
        self.assertIs(regions.by_title("101c9300"), regions.JPN)
        self.assertIsNone(regions.by_title("101c9200"))

    def test_an_american_language_takes_the_european_texts(self):
        self.assertEqual([regions.european(l) for l in regions.USA.languages], ["EUen", "EUes", "EUfr"])
        self.assertEqual(regions.USA.main, "USen")
        self.assertEqual(regions.JPN.main, "JPja")

    def test_a_european_build_reads_what_it_pins(self):
        hashes = {"Pack/Bootup.pack": "a", "Pack/Bootup_EUen.pack": "b", "Pack/Bootup_EUde.pack": "c"}
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(regions.inputs(hashes, update(Path(temp), "EUen")), hashes)

    def test_an_american_build_reads_its_own_language_archives(self):
        hashes = {"Pack/Bootup.pack": "a", "Pack/Bootup_EUen.pack": "b", "Pack/Bootup_EUde.pack": "c",
                  "Pack/Bootup_EUfr.pack": "d"}
        table = json.loads(regions.HASHES.read_text(encoding="utf-8"))["USA"]["languages"]
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(regions.inputs(hashes, update(Path(temp), "USen")),
                             {"Pack/Bootup.pack": "a", "Pack/Bootup_USen.pack": table["Pack/Bootup_USen.pack"],
                              "Pack/Bootup_USfr.pack": table["Pack/Bootup_USfr.pack"]})

    def test_the_table_maps_to_european_hashes_only(self):
        table = json.loads(regions.HASHES.read_text(encoding="utf-8"))
        europe = set().union(*(entry["equivalents"].values() for entry in table.values()))
        theirs = set().union(*(entry["equivalents"] for entry in table.values()))
        self.assertFalse(europe & theirs)
        self.assertEqual(set(table["USA"]["languages"]), {f"Pack/Bootup_{l}.pack" for l in regions.USA.languages})

    def test_other_bytes_keep_their_own_hash(self):
        self.assertEqual(regions.vanilla_digest(b"x"), hashlib.sha256(b"x").hexdigest())

    @unittest.skipUnless((MLC / "0005000e/101c9400/content/Pack/Bootup.pack").is_file()
                         and (MLC / "0005000e/101c9500/content/Pack/Bootup.pack").is_file(),
                         "requires the European and American updates in Cemu")
    def test_an_american_file_is_named_by_its_european_hash(self):
        for name in ("Pack/Bootup.pack", "Actor/ActorInfo.product.sbyml"):
            with self.subTest(name):
                eu = (MLC / "0005000e/101c9500/content" / name).read_bytes()
                us = (MLC / "0005000e/101c9400/content" / name).read_bytes()
                self.assertNotEqual(eu, us)
                self.assertEqual(regions.vanilla_digest(us), hashlib.sha256(eu).hexdigest())


def _resources(data: bytes, prefix: str, out: dict) -> None:
    """{path: hash} of a file's resources once Yaz0 is undone and archives opened."""
    import oead
    if data[:4] == b"Yaz0":
        data = bytes(oead.yaz0.decompress(data))
    if data[:4] == b"SARC":
        for member in oead.Sarc(data).get_files():
            _resources(bytes(member.data), f"{prefix}//{member.name}", out)
        return
    out[prefix] = hashlib.sha256(data).hexdigest()


def _installed(region: regions.Region) -> bool:
    return (MLC / "0005000e" / region.title / "content/Pack/Bootup.pack").is_file()


OTHERS = [region for region in regions.REGIONS if region is not regions.EUR and _installed(region)]


class OtherVersionPackTests(unittest.TestCase):
    """Against the versions installed in Cemu: the American and Japanese packs."""

    @full_build
    @unittest.skipUnless(_installed(regions.EUR) and OTHERS and REPORT.is_file(),
                         "requires the European update, another version's and an audited play seed in Cemu")
    def test_another_versions_pack_is_the_european_one_in_its_languages(self):
        from tools.build_pack_from_source import build, rules, verify_pack
        with tempfile.TemporaryDirectory() as temp:
            def built(region):
                update = MLC / "0005000e" / region.title
                return build(update / "content", update / "code/U-King.rpx", REPORT, 1, Path(temp) / region.key)

            def contents(pack):
                found = {}
                for path in pack.rglob("*"):
                    name = path.relative_to(pack).as_posix()
                    if path.is_file() and name not in ("manifest.json", "rules.txt", "delivery_catalog.json"):
                        _resources(path.read_bytes(), name, found)
                table = "content/System/Resource/ResourceSizeTable.product.srsizetable"
                return {n: h for n, h in found.items() if n != table
                        and not any(f"_{l}." in n for r in regions.REGIONS for l in r.languages)}

            europe = built(regions.EUR)
            ours, eu_catalog = contents(europe), json.loads((europe / "delivery_catalog.json").read_text("utf-8"))
            for region in OTHERS:
                with self.subTest(region.key):
                    pack = built(region)
                    self.assertEqual(verify_pack(pack)["revision"], f"{region.key} v208")
                    self.assertEqual((pack / "rules.txt").read_bytes(), rules(region))
                    self.assertIn(f"titleIds = {region.title_id()}".encode(), rules(region))
                    self.assertEqual(contents(pack), ours)
                    catalog = json.loads((pack / "delivery_catalog.json").read_text(encoding="utf-8"))
                    self.assertEqual(set(catalog["horses"]["GameRomHorseEpona"]), set(region.languages))
                    if region.main.endswith("en"):
                        self.assertEqual(catalog["death_link"], eu_catalog["death_link"])
                    else:       # no English texts: no killer named in the English sentences
                        self.assertEqual(catalog["death_link"]["attackers"], {})

    @full_build
    @unittest.skipUnless(OTHERS, "requires another version's update and DLC in Cemu")
    def test_another_versions_stalls_and_tower_maps(self):
        from botw_patch import tower_maps
        from botw_patch.shops import plan_from_manifest
        from tools.build_resources_from_source import default_aoc, generate
        from tests.test_tower_maps import save_flags
        ids = [202, 208]        # Kakariko (G-6) and Tarrey Town (I-3): towers' units too
        manifest = {"slot": 1, "seed": "1", "slot_name": "Player", "slot_data": {"tower_maps": 2},
                    "shops": [{"location_id": i, "price": 100} for i in ids],
                    "placements": [{"location_id": i, "item_name": f"Item {i}",
                                    "recipient_name": "Player", "recipient_game": "Breath of the Wild",
                                    "flags": 1, "recipient": 1} for i in ids]}
        for region in OTHERS:
            with self.subTest(region.key):
                update = MLC / "0005000e" / region.title / "content"
                files, _catalog, _changes = generate(update, 417391497, shops=plan_from_manifest(manifest),
                                                     status=manifest, aoc=default_aoc(update))
                for number, (_region, cell, tags) in tower_maps.TOWERS.items():
                    flags = save_flags(files["aoc/0010/" + tower_maps.unit(cell)])
                    self.assertEqual({flags[h] for h in tags}, {f"APTower_{number}"})
                self.assertIn("IsGet_AP_Shop_202",
                              save_flags(files["aoc/0010/" + tower_maps.unit("G-6")]).values())
                self.assertEqual(sorted(n for n in files if n.startswith("Pack/Bootup_")),
                                 [f"Pack/Bootup_{l}.pack" for l in region.languages])

if __name__ == "__main__":
    unittest.main()
