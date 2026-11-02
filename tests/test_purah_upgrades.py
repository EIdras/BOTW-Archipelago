"""Purah's rune upgrades are locations (botw_patch/purah_upgrades.py), on the game's own flow and texts."""
from pathlib import Path
import unittest

from botw_patch import purah_upgrades as pu

UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
HAVE_UPDATE = all((UPDATE / name).is_file() for name in pu.PACKS)


def member(pack: str, name: str) -> bytes:
    import oead
    from botw_patch.resources import unpack
    archive = oead.Sarc(unpack((UPDATE / pack).read_bytes()))
    return bytes(archive.get_file(name).data)


def graph(raw: bytes) -> dict:
    from botw_patch.events import graph_snapshot, read_flow
    return graph_snapshot(read_flow(raw))["events"]


@unittest.skipUnless(HAVE_UPDATE, "Wii U update absent")
class PurahUpgradeTests(unittest.TestCase):
    def test_every_copy_of_her_flow_is_the_same_and_changed(self):
        from botw_patch.resources import vanilla_digest
        for pack in pu.PACKS:
            self.assertEqual(vanilla_digest(member(pack, pu.FLOW)), pu.FLOW_SHA)

    def test_an_upgrade_takes_the_materials_and_sets_its_location_only(self):
        before = graph(member("Event/Npc_AncientDoctor.sbeventpack", pu.FLOW))
        after = graph(pu.transform(member("Event/Npc_AncientDoctor.sbeventpack", pu.FLOW))[0])
        for _rune, (lv2, flag, choice, call) in pu.FLAGS.items():
            self.assertEqual(before[call]["params"]["FlagName"], choice)
            self.assertEqual(after[call]["params"]["FlagName"], flag)
            self.assertEqual(after[call]["params"]["Value"], -3)
        # PowerUpDemo: the flag given, the materials taken, no cutscene, the count.
        self.assertEqual(after["Event523"]["params"]["FlagName"], ("Argument", "FlagName"))
        self.assertEqual(after["Event524"]["actor_action"], "Demo_IncreasePorchItem")
        self.assertEqual((after[pu.UPGRADE]["actor_action"], after[pu.UPGRADE]["nxt"]),
                         ("Demo_WaitFrame", "Event522"))
        flags = {node.get("params", {}).get("FlagName") for node in after.values()}
        self.assertFalse({lv2 for lv2, *_rest in pu.FLAGS.values()} & flags)

    def test_her_choice_hides_the_upgrades_she_gave_in_every_language(self):
        import oead
        from botw_patch.resources import unpack
        from botw_patch.shop_items import read_labels
        titles = {"101c9500": "EUde EUen EUes EUfr EUit EUnl EUru", "101c9400": "USen USes USfr",
                  "101c9300": "JPja"}
        for title, languages in titles.items():
            for language in languages.split():
                path = UPDATE.parents[1] / title / f"content/Pack/Bootup_{language}.pack"
                if not path.is_file():
                    continue
                pack = oead.Sarc(unpack(path.read_bytes()))
                archive = oead.Sarc(unpack(bytes(pack.get_file(f"Message/Msg_{language}.product.ssarc").data)))
                old = bytes(archive.get_file(pu.MSBT).data)
                new = pu.retarget_choice(old)
                self.assertEqual(len(new), len(old), language)
                labels = read_labels(new)
                for lv2, flag, _choice, _call in pu.FLAGS.values():
                    self.assertIn(flag, labels["talk31"], language)
                    self.assertNotIn(lv2, labels["talk31"], language)
                self.assertEqual({k: v for k, v in labels.items() if k != "talk31"},
                                 {k: v for k, v in read_labels(old).items() if k != "talk31"})


if __name__ == "__main__":
    unittest.main()
