"""Archipelago shops: catalogue, texts, plan, flow and stock edits, client side."""
from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
import struct
import unittest
import zlib

from botw_client import gamedata_table
from botw_client.locations import LocationTarget, LocationTracker, load_targets
from botw_client.shop_catalog import (BY_ID, FIRST_LOCATION_ID, KEPT, LOCATIONS,
                                      MERCHANTS, SLOTS_PER_MERCHANT, catalogue_row,
                                      same_merchant, world_row)

ROOT = Path(__file__).resolve().parents[1]
UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
HAS_GAME = (UPDATE / "Pack/TitleBG.pack").is_file()

NEEDS_TABLE = unittest.skipUnless(gamedata_table.available(), "the GameData flag table is read from the game")


class CatalogueTests(unittest.TestCase):
    def test_ids_follow_the_schema_2_locations_without_gaps(self):
        self.assertEqual([l.id for l in LOCATIONS],
                         list(range(FIRST_LOCATION_ID, FIRST_LOCATION_ID + 32)))
        self.assertEqual(len({l.actor for l in LOCATIONS}), 32)
        self.assertEqual(len({l.flag_hash for l in LOCATIONS}), 32)
        self.assertEqual(BY_ID[154].name, "Dueling Peaks Stable - Beedle Item 1")
        self.assertEqual(BY_ID[185].name, "Kara Kara Bazaar - Beedle Item 2")
        self.assertEqual(same_merchant(155), [154, 155])

    def test_actor_names_fit_the_names_they_replace(self):
        # the stock sheet must not grow: an AP actor name is never longer
        for merchant in MERCHANTS:
            self.assertGreaterEqual(len(merchant.stock) - KEPT, SLOTS_PER_MERCHANT)
        self.assertTrue(all(len(l.actor) == 11 for l in LOCATIONS))

    def test_data_files_carry_exactly_the_catalogue(self):
        with (ROOT / "data/locations_master.csv").open(encoding="utf-8", newline="") as f:
            rows = [r for r in csv.DictReader(f) if r["category"] == "Shop"]
        self.assertEqual(rows, [catalogue_row(l) for l in LOCATIONS])
        world = json.loads((ROOT / "botw_world/data/locations.json").read_text(encoding="utf-8"))
        self.assertEqual([r for r in world if r["category"] == "Shop"],
                         [world_row(l) for l in LOCATIONS])

    @NEEDS_TABLE
    def test_shop_targets_are_optional_s32_custom_flags(self):
        shops = [t for t in load_targets(world_schema=3) if t.optional]
        self.assertEqual([t.name for t in shops], [l.name for l in LOCATIONS])
        self.assertTrue(all(t.kind == "s32" for t in shops))
        self.assertTrue(all(t.hash_u32 == zlib.crc32(t.flag.encode()) for t in shops))
        self.assertEqual(len(load_targets(world_schema=2)), 153)


class Memory:
    def __init__(self, base, size):
        self.base, self.data = base, bytearray(size)

    def read(self, address, size):
        offset = address - self.base
        return bytes(self.data[offset:offset + size])


class TrackerTests(unittest.TestCase):
    def test_a_shop_flag_is_read_as_s32_and_absent_ones_are_skipped(self):
        class Live:
            base = 1000
            index = {"bool": {1: 0}, "s32": {2: 0x40}}

        memory = Memory(1000, 0x80)
        targets = [LocationTarget("Shrine", "F", 1),
                   LocationTarget("Shop A", "APShop_154", 2, "s32", optional=True),
                   LocationTarget("Shop B", "APShop_155", 3, "s32", optional=True)]
        tracker = LocationTracker(memory, {}, targets, live=Live())
        self.assertEqual(tracker.unavailable, ["Shop B"])
        self.assertEqual(tracker.poll(), [])
        struct.pack_into(">i", memory.data, 0x40 + 0x14, 1)
        self.assertEqual(tracker.poll(), ["Shop A"])
        memory.data[7] = 1
        self.assertEqual(tracker.poll(), ["Shrine"])

    def test_a_missing_vanilla_flag_still_refuses(self):
        class Live:
            base = 0
            index = {"bool": {}, "s32": {}}

        with self.assertRaisesRegex(RuntimeError, "F"):
            LocationTracker(Memory(0, 8), {}, [LocationTarget("Shrine", "F", 1)], live=Live())


class ShopWatchTests(unittest.TestCase):
    def watch(self, screen, text, torn=False):
        from botw_client import shop_state

        class Live:
            base = 0
            tp = 0

            def __init__(self):
                self.p = self
                self.reads = 0

            def get(self, hash_u32, kind):
                return screen if hash_u32 == shop_state.crc(shop_state.SCREEN) else None

            def read(self, address, size):
                self.reads += 1
                raw = text.encode().ljust(size, b"\0")
                return raw[2:] + b"\0\0" if torn and self.reads % 2 else raw

        watch = shop_state.ShopWatch.__new__(shop_state.ShopWatch)
        watch.live, watch.text_address = Live(), 0x100
        return watch

    def test_an_open_list_on_an_ap_item_names_its_merchant(self):
        self.assertEqual(self.watch(1, "AP_Shop_157").seen(), [156, 157])

    def test_a_closed_list_a_vanilla_item_or_a_torn_read_name_nothing(self):
        self.assertEqual(self.watch(0, "AP_Shop_157").seen(), [])
        self.assertEqual(self.watch(1, "Obj_ArrowNormal_A_01").seen(), [])
        self.assertEqual(self.watch(1, "AP_Shop_157", torn=True).seen(), [])

    def test_the_string_object_is_found_by_its_hash(self):
        from botw_client.shop_state import SELECTED, crc, locate_string_flags
        memory = {0x10 + 0x04 + 12 * 3: struct.pack(">III", 1, 1, 0x20000000),
                  0x20000000: struct.pack(">I", 0x30000000)}
        obj = bytearray(0x200)
        struct.pack_into(">I", obj, 0x138, crc(SELECTED))

        def read(address, size):
            if address == 0x30000000:
                return bytes(obj[:size])
            return memory.get(address)

        found = locate_string_flags(read, 0x10, {crc(SELECTED): SELECTED})
        self.assertEqual(found[SELECTED]["object"], 0x30000000)
        self.assertEqual(found[SELECTED]["hash_offset"], 0x138)


class HintTests(unittest.TestCase):
    def test_seeing_a_shop_hints_its_unchecked_seed_locations_once(self):
        from botw_client.runtime import BotwClientRuntime
        sent = []

        class Ap:
            seed_locations = {154, 155, 1}
            checked_locations = {155}

            async def send_hints(self, ids):
                sent.append(ids)

        class Game:
            def poll_shop(self):
                return [154, 155]

        class Store:
            def save(self):
                pass

        runtime = BotwClientRuntime.__new__(BotwClientRuntime)
        runtime.ap, runtime.game, runtime.state_store = Ap(), Game(), Store()
        runtime.state, runtime.log = {}, lambda *_: None
        asyncio.run(runtime._poll_shops())
        asyncio.run(runtime._poll_shops())
        self.assertEqual(sent, [[154]])
        self.assertEqual(runtime.state["shop_hints"], [154])


class SeedLocationTests(unittest.TestCase):
    def test_the_seed_is_known_only_when_the_server_lists_missing_locations(self):
        from botw_client.protocol import ArchipelagoClient
        client = ArchipelagoClient("localhost:1", "Player", None, log=lambda *_: None)

        async def send(_packet):
            pass

        client.send = send
        base = {"cmd": "Connected", "team": 0, "slot": 1, "players": [],
                "checked_locations": [3]}
        asyncio.run(client._packet(base))
        self.assertEqual(client.seed_locations, set())
        asyncio.run(client._packet({**base, "missing_locations": [154, 7]}))
        self.assertEqual(client.seed_locations, {3, 7, 154})


class PlanTests(unittest.TestCase):
    def manifest(self, **shop):
        return {"slot": 1, "placements": [
            {"location_id": 154, "item_name": "Hookshot", "recipient": 2,
             "recipient_name": "Alice", "recipient_game": "A Link to the Past", "flags": 1},
            {"location_id": 3, "item_name": "Paraglider", "recipient": 1,
             "recipient_name": "Player", "recipient_game": "Breath of the Wild", "flags": 1}],
            "shops": [{"location_id": 154, "price": 120, **shop}]}

    def test_the_plan_reads_the_shop_placements(self):
        from botw_patch.shops import plan_from_manifest
        (placement,) = plan_from_manifest(self.manifest())
        self.assertEqual((placement.location.id, placement.price, placement.item,
                          placement.own), (154, 120, "Hookshot", False))
        self.assertEqual(plan_from_manifest({"slot": 1, "placements": []}), [])

    def test_a_bad_price_or_an_empty_location_is_refused(self):
        from botw_patch.shops import plan_from_manifest
        with self.assertRaises(ValueError):
            plan_from_manifest(self.manifest(price=0))
        manifest = self.manifest()
        manifest["shops"].append({"location_id": 155, "price": 10})
        with self.assertRaises(ValueError):
            plan_from_manifest(manifest)

    def test_texts_fit_and_speak_to_the_right_player(self):
        from botw_patch.shops import (DESCRIPTION_LINES, DESCRIPTION_WIDTH, NAME_LIMIT,
                                      TRAP, ShopPlacement, texts)
        long = ShopPlacement(BY_ID[154], 10, "An extremely long item name " * 4,
                             "SomeoneWithALongName", "A Game With A Very Long Title " * 3,
                             1, False)
        name, description = texts(long)
        self.assertLessEqual(len(name), NAME_LIMIT)
        lines = description.split("\n")
        self.assertLessEqual(len(lines), DESCRIPTION_LINES)
        self.assertTrue(all(len(line) <= DESCRIPTION_WIDTH for line in lines))
        own = ShopPlacement(BY_ID[155], 10, "Heart Container", "Player", "BotW", 1, True)
        self.assertIn("for you", texts(own)[1])
        self.assertIn("Needed to progress", texts(own)[1])
        trap = ShopPlacement(BY_ID[155], 10, "Ice Trap", "Bob", "OoT", TRAP | 1, False)
        self.assertNotIn("progress", texts(trap)[1])


@unittest.skipUnless(HAS_GAME, "Wii U update missing")
class GameFileTests(unittest.TestCase):
    def sheet(self, merchant):
        import oead
        from botw_patch.resources import unpack
        archive = oead.Sarc(unpack((UPDATE / f"Actor/Pack/{merchant.actor}.sbactorpack")
                                   .read_bytes()))
        return bytes(archive.get_file(f"Actor/ShopData/{merchant.actor}.bshop").data)

    def test_every_sheet_is_the_catalogued_one_and_gets_ap_items_first(self):
        import oead
        from botw_patch.shop_items import arrange_stock
        from botw_patch.shops import stock_entries
        for merchant in MERCHANTS:
            raw = self.sheet(merchant)
            locations = [l for l in LOCATIONS if l.merchant == merchant]
            out, detail = arrange_stock(raw, "Normal", merchant.stock,
                                        stock_entries(merchant, locations))
            self.assertLessEqual(len(out), len(raw))
            self.assertEqual(detail["after"][:4],
                             [l.actor for l in locations] + list(merchant.stock[:KEPT]))
            params = oead.aamp.ParameterIO.from_binary(out).objects["Normal"].params
            arrows = detail["after"].index(merchant.stock[0]) + 1
            before = oead.aamp.ParameterIO.from_binary(raw).objects["Normal"].params
            self.assertEqual(int(params[f"ItemNum{arrows:03d}"].v), int(before["ItemNum001"].v))
            self.assertEqual(int(params[f"ItemAdjustPrice{arrows:03d}"].v),
                             int(before["ItemAdjustPrice001"].v))
            self.assertEqual([bool(params[f"ItemLookGetFlg{i:03d}"].v)
                              for i in range(1, len(locations) + 1)], [True] * len(locations))
            self.assertEqual([int(params[f"ItemSort{i:03d}"].v)
                              for i in range(1, len(merchant.stock) + 1)],
                             list(range(len(merchant.stock))))

    def test_the_purchase_record_sets_the_flag_then_deletes(self):
        import oead
        from botw_patch.events import graph_snapshot, read_flow
        from botw_patch.resources import unpack
        from botw_patch.shop_items import add_purchase_record
        pack = oead.Sarc(unpack((UPDATE / "Event/Npc_TripMaster_00.sbeventpack").read_bytes()))
        raw = bytes(pack.get_file("EventFlow/Npc_TripMaster_00.bfevfl").data)
        records = [(l.actor, l.flag, l.shown_flag) for l in LOCATIONS[:3]]
        out, detail = add_purchase_record(raw, "Event18", records)
        events = graph_snapshot(read_flow(out))["events"]
        node, seen = events["Event18"]["nxt"], []
        while node != "Event150":
            switch = events[node]
            self.assertEqual(switch["actor_query"], "HasPorchItem")
            record = events[switch["cases"][1]]
            self.assertEqual(record["actor_action"], "Demo_SetGameDataInt")
            self.assertEqual(record["params"]["Value"], 1)
            hide = events[record["nxt"]]
            self.assertEqual(hide["actor_action"], "Demo_FlagOFF")
            delete = events[hide["nxt"]]
            self.assertEqual(delete["actor_action"], "Demo_DeletePorchItemInEquip")
            self.assertEqual(delete["nxt"], switch["cases"][0])
            seen.append((switch["params"]["PorchItemName"], record["params"]["GameDataIntName"],
                         hide["params"]["FlagName"]))
            node = switch["cases"][0]
        self.assertEqual(seen, records)
        self.assertEqual(detail["then"], "Event150")

    def test_an_ap_actor_carries_its_own_price_for_3d_stalls(self):
        import oead
        from botw_patch.resources import unpack
        from botw_patch.shop_items import clone_actor_pack
        title = oead.Sarc(unpack((UPDATE / "Pack/TitleBG.pack").read_bytes()))
        amber = bytes(title.get_file("Actor/Pack/Item_Ore_F.sbactorpack").data)
        pack, detail = clone_actor_pack(amber, "Item_Ore_F", "AP_Shop_154", "AP_Item_00",
                                        "AP_Item_00", 55)
        archive = oead.Sarc(unpack(pack))
        names = {f.name for f in archive.get_files()}
        self.assertIn("Actor/GeneralParamList/AP_Shop_154.bgparamlist", names)
        self.assertNotIn("Actor/GeneralParamList/Item_Ore_F.bgparamlist", names)
        params = oead.aamp.ParameterIO.from_binary(bytes(archive.get_file(
            "Actor/GeneralParamList/AP_Shop_154.bgparamlist").data))
        self.assertEqual(params.objects["Item"].params["BuyingPrice"].v, 55)
        link = oead.aamp.ParameterIO.from_binary(bytes(archive.get_file(
            "Actor/ActorLink/AP_Shop_154.bxml").data)).objects["LinkTarget"].params
        self.assertEqual(str(link["GParamUser"].v), "AP_Shop_154")
        self.assertEqual(str(link["ModelUser"].v), "AP_Shop_154")

    def test_texts_go_into_every_language(self):
        import oead
        from botw_patch.resources import unpack
        from botw_patch.shop_items import MSBT, add_item_texts, read_labels
        from botw_patch.shops import LANGUAGES, ShopPlacement, items
        placement = ShopPlacement(BY_ID[154], 10, "Hookshot", "Alice", "ALttP", 1, False)
        for language in LANGUAGES:
            outer = oead.Sarc(unpack((UPDATE / f"Pack/Bootup_{language}.pack").read_bytes()))
            messages = bytes(outer.get_file(f"Message/Msg_{language}.product.ssarc").data)
            archive = oead.Sarc(unpack(messages))
            out, _ = add_item_texts(bytes(archive.get_file(MSBT).data),
                                    items([placement]))
            self.assertTrue(read_labels(out)["AP_Shop_154_Name"].endswith("Hookshot\x00"))


if __name__ == "__main__":
    unittest.main()
