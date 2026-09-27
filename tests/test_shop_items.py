"""botw_patch.shop_items: shop item texts, purchase cleanup and the AP model checks.

The game-file tests read the BOTW EUR update installed in Cemu, and the base
game next to the RPX named in botw_client.json; they are skipped without them.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from botw_patch.shop_items import (DELETE_ACTION, ApShopItem, add_item_texts,
                                   add_purchase_cleanup, read_labels, wrap_description)

UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
LANG_PACK = "Pack/Bootup_EUfr.pack"
MSG_ARCHIVE = "Message/Msg_EUfr.product.ssarc"
MSBT = "ActorType/Item.msbt"
HAVE_UPDATE = (UPDATE / LANG_PACK).is_file()
MODEL_SOURCE = ROOT / "assets/models/ap_item/wiiu"


def vanilla(pack: str, member: str) -> bytes:
    import oead
    from botw_patch.resources import unpack
    archive = oead.Sarc(unpack((UPDATE / pack).read_bytes()))
    return bytes(archive.get_file(member).data)


def amber_file(part: str) -> bytes | None:
    """Amber's model file (Item_Ore_F): in TitleBG.pack, else in the base game."""
    import oead
    from botw_patch.resources import unpack
    title = oead.Sarc(unpack((UPDATE / "Pack/TitleBG.pack").read_bytes()))
    member = title.get_file(f"Model/Item_Ore_F{part}.sbfres")
    if member is not None:
        return bytes(member.data)
    try:
        game = Path(json.loads((ROOT / "botw_client.json").read_text(encoding="utf-8"))["game"])
    except (OSError, ValueError, KeyError):
        return None
    for root in (UPDATE, game.parent.parent / "content"):
        path = root / f"Model/Item_Ore_F{part}.sbfres"
        if path.is_file():
            return path.read_bytes()
    return None


class IndexGroupTests(unittest.TestCase):
    def test_single_entry_reference_is_the_highest_set_bit(self):
        from botw_patch.shop_items import single_entry_reference
        # measured on TitleBG.pack models
        self.assertEqual(single_entry_reference("Item_Ore_F"), 78)
        self.assertEqual(single_entry_reference("Skeleton"), 62)
        self.assertEqual(single_entry_reference("Link"), 30)
        self.assertEqual(single_entry_reference("Weapon_Arrow_005"), 125)
        self.assertEqual(single_entry_reference("AP_Item_00"), 77)


class DescriptionTests(unittest.TestCase):
    def test_lines_are_broken_like_vanilla_descriptions(self):
        text = wrap_description("mot " * 30)
        self.assertTrue(all(len(line) <= 44 for line in text.split("\n")))
        self.assertGreater(text.count("\n"), 0)

    def test_a_description_longer_than_four_lines_is_refused(self):
        with self.assertRaises(ValueError):
            wrap_description("mot " * 60)


@unittest.skipUnless(HAVE_UPDATE, "update content absent")
class TextTests(unittest.TestCase):
    def test_names_and_descriptions_are_added(self):
        import oead
        from botw_patch.resources import unpack
        messages = oead.Sarc(unpack(vanilla(LANG_PACK, MSG_ARCHIVE)))
        raw = bytes(messages.get_file(MSBT).data)
        items = [ApShopItem("AP_A", 10, "Un", "Ligne 1\nLigne 2"),
                 ApShopItem("AP_B", 20, "Deux", "Texte")]
        out, detail = add_item_texts(raw, items)
        labels = read_labels(out)
        self.assertEqual(detail["entries"], 603)
        self.assertEqual(labels["AP_A_Desc"], "Ligne 1\nLigne 2\x00")
        self.assertTrue(labels["AP_B_Name"].endswith("Deux\x00"))


@unittest.skipUnless(HAVE_UPDATE, "update content absent")
class CleanupTests(unittest.TestCase):
    def terry_flow(self) -> bytes:
        return vanilla("Event/Npc_TripMaster_00.sbeventpack", "EventFlow/Npc_TripMaster_00.bfevfl")

    def test_the_deletes_sit_between_the_buy_list_and_its_successor(self):
        from botw_patch.events import graph_snapshot, read_flow
        out, detail = add_purchase_cleanup(self.terry_flow(), "Event18", ["AP_A", "AP_B"])
        events = graph_snapshot(read_flow(out))["events"]
        self.assertEqual(events["Event18"]["nxt"], "APShopDelete00")
        self.assertEqual(events["APShopDelete00"]["nxt"], "APShopDelete01")
        self.assertEqual(events["APShopDelete01"]["nxt"], "Event150")
        self.assertEqual(events["APShopDelete01"]["actor_action"], DELETE_ACTION)
        self.assertEqual(events["APShopDelete01"]["params"],
                         {"IsWaitFinish": True, "DeleteNum": -1, "PorchItemName": "AP_B"})
        self.assertEqual(detail["then"], "Event150")

    def test_the_parameters_are_the_ballad_ones(self):
        # 9q measured this action with these parameters at the end of the Ballad.
        from botw_patch.events import graph_snapshot, read_flow
        ballad = graph_snapshot(read_flow(vanilla("Event/Demo622_2.sbeventpack",
                                                  "EventFlow/Demo622_2.bfevfl")))
        self.assertEqual(ballad["events"]["Event456"]["actor_action"], DELETE_ACTION)
        self.assertEqual(set(ballad["events"]["Event456"]["params"]),
                         {"IsWaitFinish", "DeleteNum", "PorchItemName"})

    def test_only_a_followed_subflow_can_carry_the_cleanup(self):
        with self.assertRaises(ValueError):
            add_purchase_cleanup(self.terry_flow(), "Event150", ["AP_A"])


@unittest.skipUnless(HAVE_UPDATE and (MODEL_SOURCE / "AP_Item.sbfres").is_file(),
                     "model files absent")
class ModelTests(unittest.TestCase):
    def amber(self):
        from botw_patch.shop_items import MODEL_PARTS
        parts = {p: amber_file(p) for p in MODEL_PARTS}
        if None in parts.values():
            self.skipTest("amber's model files absent (base game content)")
        return parts

    def reference(self):
        from botw_patch.shop_items import bfres_summary
        return {p: bfres_summary(raw) for p, raw in self.amber().items()}

    def test_the_shipped_amber_fingerprint_matches_the_game(self):
        # botw_patch.shops keeps only what it needs of amber's files.
        from botw_patch.resources import digest, unpack
        from botw_patch.shops import MODEL_REFERENCE
        for part, raw in self.amber().items():
            self.assertEqual(MODEL_REFERENCE[part]["sha256"], digest(raw))
            self.assertEqual(MODEL_REFERENCE[part]["unpacked_size"], len(unpack(raw)))
            self.assertEqual(MODEL_REFERENCE[part]["summary"], self.reference()[part])

    def test_amber_passes_and_rests_on_its_origin(self):
        from botw_patch.shop_items import check_model, model_bounds
        amber = self.amber()
        self.assertIn("bounds", check_model(amber, self.reference()))
        bounds = model_bounds(amber[""])
        self.assertGreater(bounds["min"][1], -0.01)
        self.assertLess(max(bounds["size"]), 1.0)

    def test_renaming_amber_and_back_gives_amber_byte_for_byte(self):
        from botw_patch.resources import unpack
        from botw_patch.shop_items import MODEL_PARTS, rename_model
        amber = self.amber()
        there, detail = rename_model(amber, "Item_Ore_F", "AP_Item_00")
        back, _ = rename_model(there, "AP_Item_00", "Item_Ore_F")
        self.assertTrue(all(unpack(back[p]) == unpack(amber[p]) for p in MODEL_PARTS))
        self.assertEqual(detail["occurrences"], {"model": 6, ".Tex1": 6, ".Tex2": 6})

    def test_every_name_is_found_after_renaming(self):
        from botw_patch.resources import unpack
        from botw_patch.shop_items import MODEL_PARTS, index_group, index_lookup, rename_model
        renamed, _ = rename_model(self.amber(), "Item_Ore_F", "AP_Item_00")
        for part in MODEL_PARTS:
            data = unpack(renamed[part])
            for slot in (0, 1):
                rows = index_group(data, slot)
                for row in rows[1:]:
                    self.assertEqual(index_lookup(rows, row[3]), row[3])
                    self.assertTrue(row[3].startswith("AP_Item_00"))

    def test_a_renaming_that_changes_length_is_refused(self):
        from botw_patch.shop_items import rename_model
        with self.assertRaises(ValueError):
            rename_model(self.amber(), "Item_Ore_F", "AP_Item")

    def test_a_wrong_model_is_refused(self):
        from botw_patch.shop_items import check_model
        amber = self.amber()
        swapped = dict(amber, **{".Tex1": amber[""]})   # a model file where textures belong
        with self.assertRaises(ValueError):
            check_model(swapped, self.reference())

    def test_the_actor_gets_its_own_model_list(self):
        import oead
        from botw_patch.resources import unpack
        from botw_patch.shop_items import clone_actor_pack
        title = oead.Sarc(unpack((UPDATE / "Pack/TitleBG.pack").read_bytes()))
        model = bytes(title.get_file("Actor/Pack/Item_Ore_F.sbactorpack").data)
        out, _ = clone_actor_pack(model, "Item_Ore_F", "AP_X", "AP_Item")
        pack = oead.Sarc(unpack(out))
        link = oead.aamp.ParameterIO.from_binary(bytes(pack.get_file("Actor/ActorLink/AP_X.bxml").data))
        self.assertEqual(str(link.objects["LinkTarget"].params["ModelUser"].v), "AP_X")
        models = oead.aamp.ParameterIO.from_binary(
            bytes(pack.get_file("Actor/ModelList/AP_X.bmodellist").data))
        data = models.lists["ModelData"].lists["ModelData_0"]
        self.assertEqual(str(data.objects["Base"].params["Folder"].v), "AP_Item")
        self.assertEqual(str(data.lists["Unit"].objects["Unit_0"].params["UnitName"].v), "Item_Ore_F")
        self.assertIsNone(pack.get_file("Actor/ModelList/Item_Ore_F.bmodellist"))


if __name__ == "__main__":
    unittest.main()
