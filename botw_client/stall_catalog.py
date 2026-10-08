"""Archipelago 3D stall locations: the single source of their names, IDs and flags.

Pure data, importable by the client, the resource builder and the tests (the
APWorld and data/locations_master.csv carry the same rows; a test checks
they match this module, and, with the dumps, that every object and merchant
below is where the map says).

A 3D stall has no stock sheet: each item on sale is an object of the DLC map
unit (aoc/0010/Map/MainField/<cell>/<cell>_Static.smubin) linked to its
merchant by `ForSale`; the merchant's flow runs DisplayShop:Multiple for the
object looked at (docs/reference/shops.md). Up to SLOTS_PER_MERCHANT
objects of a merchant become AP locations: the object turns into the
location's AP actor, created only while IsGet_AP_Shop_<id> is true (so a
bought one never comes back, blood moon included), and the merchant's flow
records the purchase in APShop_<id> as Beedle's does.

Merchants: the 14 stalls selling consumables through DisplayShop:Multiple in
their own flow that have an item on sale in several copies (armour stalls,
mannequins, are another mechanism; stalls whose items are all single are
left whole). Objects: chosen in the game, stall by stall, where the jewel
reads best (lab/tools/cemu/stall_marks.py: the article looked at, and where
Link stood), with the jewel's pose there: lying on its back or standing, and
its yaw, its logo upright for a customer standing where Link stood. Rules
kept: an item sold in several copies, never its last one (the stall keeps
everything it sold), the two at least SPACING apart (the jewels are about
0.6 m wide). Tarrey Town's stall, built by a quest, keeps the automatic
choice (the lowest objects, lying, its top towards the merchant). Places:
nearest LocationTag, named from LocationMarker.msbt. Regions: the tower whose
map shows the merchant, as for every location (tools/map_regions.py).
"""
from __future__ import annotations

from dataclasses import dataclass
import zlib

FIRST_LOCATION_ID = 186          # after the 32 Beedle items (154-185)
SLOTS_PER_MERCHANT = 2
SPACING = 0.6                    # metres, between a stall's two objects
CATEGORY = "Stall"
FLAG_KIND = "s32"


@dataclass(frozen=True)
class StallMerchant:
    index: int
    actor: str          # the merchant NPC
    cell: str           # map unit, aoc/0010/Map/MainField/<cell>/<cell>_Static.smubin
    hash_id: int        # the merchant object's HashId
    place: str          # English marker name
    label: str          # what the stall sells, to tell stalls of one place apart
    region: str
    buy_event: str      # SubFlowEvent DisplayShop:Multiple of the merchant's flow
    yaw: float          # the merchant's Y rotation (radians)
    # (HashId, vanilla actor, pose, yaw, lift) of the objects that become
    # locations, in slot order: the jewel "lying" or "standing" there, turned by
    # yaw (radians), lift metres above the object (below when negative: a
    # standing jewel down on the counter, from a rack's article).
    objects: tuple[tuple[int, str, str, float, float], ...]

    @property
    def map_unit(self) -> str:
        return f"Map/MainField/{self.cell}/{self.cell}_Static.smubin"


MERCHANTS = (
    StallMerchant(0, "Npc_HighMountain021", "B-3", 4095316960, "Rito Village", "General Stall",
                  "Tabantha", "Event79", 1.0801347494125366,
                  ((1287359318, "Item_Material_01", "lying", 2.2861, 0.0),
                   (2529727570, "Item_Material_06", "lying", 1.8793, 0.0))),
    StallMerchant(1, "Npc_oasis045", "B-7", 2770706636, "Gerudo Town", "Fruit Stall",
                  "Wasteland", "Event27", 0.8168146014213562,
                  ((1621577614, "Item_Fruit_C", "lying", 0.7794, 0.0),
                   (2048757940, "Item_Fruit_F", "lying", 0.8325, 0.0))),
    StallMerchant(2, "Npc_oasis002", "B-7", 2768665121, "Gerudo Town", "Arrow Stall",
                  "Wasteland", "Event31", 0.8799998760223389,
                  ((1250568235, "Obj_ArrowBundle_A_01", "lying", 0.7243, 0.0),
                   (3521419955, "Obj_ElectricArrow_A_02", "lying", 0.8701, 0.0))),
    StallMerchant(3, "Npc_SmallOasis010", "B-7", 262592810, "Kara Kara Bazaar", "Fruit Stall",
                  "Wasteland", "Event34", 1.5399999618530273,
                  ((3418843795, "Item_Fruit_F", "lying", 1.9764, 0.0),
                   (769942167, "Item_Fruit_F", "lying", 0.9912, 0.0))),
    StallMerchant(4, "Npc_oasis044", "B-7", 3321817496, "Gerudo Town", "Materials Stall",
                  "Wasteland", "Event29", -0.6200000643730164,
                  ((1256391030, "Item_Material_07", "lying", -0.9542, 0.0),
                   (1497053731, "Item_Material_03", "lying", -1.0515, 0.0))),
    StallMerchant(5, "Npc_kokiri004", "F-2", 2323688611, "Korok Forest", "Mushroom Stall",
                  "Woodland", "Event49", 0.0,
                  ((3793699955, "Item_MushroomGet_D", "lying", 0.4982, 0.0),
                   (525736165, "Item_Mushroom_A", "lying", -0.8959, 0.0))),
    StallMerchant(6, "Npc_kokiri003", "F-2", 7154937, "Korok Forest", "General Stall",
                  "Woodland", "Event68", -1.0199999809265137,
                  ((3559016972, "Item_Material_01", "lying", -1.5017, 0.0),
                   (2136474935, "Item_Material_03", "lying", -0.168, 0.0))),
    StallMerchant(7, "Npc_goron002", "G-2", 3812339821, "Goron City", "General Stall",
                  "Eldin", "Event44", -1.9017302989959717,
                  ((3043415669, "Item_Material_01", "lying", -1.5939, 0.0),
                   (2699587822, "Item_Ore_H", "lying", 0.7496, 0.0))),
    StallMerchant(8, "Npc_Kakariko010", "G-6", 17212261, "Kakariko Village", "Arrow Stall",
                  "Dueling Peaks", "Event175", -1.919862151145935,
                  ((3820325991, "Obj_ArrowNormal_A_01", "standing", 2.8769, -0.433),
                   (2376699312, "Obj_FireArrow_A_03", "standing", -0.3752, -0.093))),
    StallMerchant(9, "Npc_Kakariko014", "G-6", 185877349, "Kakariko Village", "General Stall",
                  "Dueling Peaks", "Event87", 0.3490658402442932,
                  ((3640152823, "Item_PlantGet_M", "lying", -2.4887, 0.0),
                   (3058983883, "Item_Material_06", "lying", -2.6858, 0.0))),
    StallMerchant(10, "Npc_SouthernVillage005", "H-8", 3292211395, "Lurelin Village",
                  "General Stall", "Faron", "Event49", 2.9399991035461426,
                  ((4103452247, "Item_InsectGet_O", "lying", -1.6142, 0.0),
                   (2335650137, "Obj_ArrowBundle_A_01", "lying", 2.4697, 0.0))),
    StallMerchant(11, "Npc_HighMountain010", "I-3", 2045298369, "Tarrey Town", "Arrow Stall",
                  "Akkala", "Event249", 2.2831859588623047,
                  ((781734643, "Obj_ArrowBundle_A_02", "lying", 2.2832, 0.0),
                   (225064014, "Obj_BombArrow_A_03", "lying", 2.2832, 0.0))),
    StallMerchant(12, "Npc_Zora002", "I-4", 2771744683, "Zora's Domain", "General Stall",
                  "Lanayru", "Event103", -0.33999988436698914,
                  ((2425727025, "Item_Ore_H", "lying", 1.2063, 0.0),
                   (2178080993, "Item_Material_03", "lying", -1.8332, 0.0))),
    StallMerchant(13, "Npc_HatenoVillage002", "I-7", 330593372, "Hateno Village",
                  "General Stall", "Hateno", "Event65", -2.880000114440918,
                  ((4020751443, "Item_Material_05", "lying", 3.1235, 0.0),
                   (2366597095, "Obj_ArrowBundle_A_01", "lying", 1.7538, 0.0))),
)


@dataclass(frozen=True)
class StallLocation:
    merchant: StallMerchant
    slot: int           # 1..SLOTS_PER_MERCHANT

    @property
    def id(self) -> int:
        return FIRST_LOCATION_ID + SLOTS_PER_MERCHANT * self.merchant.index + self.slot - 1

    @property
    def name(self) -> str:
        return f"{self.merchant.place} - {self.merchant.label} Item {self.slot}"

    @property
    def object_hash(self) -> int:
        return self.merchant.objects[self.slot - 1][0]

    @property
    def vanilla_actor(self) -> str:
        return self.merchant.objects[self.slot - 1][1]

    @property
    def pose(self) -> str:
        """The jewel lying on its back or standing (botw_patch/stalls.py)."""
        return self.merchant.objects[self.slot - 1][2]

    @property
    def yaw(self) -> float:
        return self.merchant.objects[self.slot - 1][3]

    @property
    def lift(self) -> float:
        return self.merchant.objects[self.slot - 1][4]

    # Same actor and flags scheme as Beedle's items (botw_client/shop_catalog.py).
    @property
    def actor(self) -> str:
        return f"AP_Shop_{self.id:03d}"

    @property
    def flag(self) -> str:
        return f"APShop_{self.id:03d}"

    @property
    def shown_flag(self) -> str:
        """Saved bool, true until bought: the map tag creates the object only
        while it is true (botw_patch/stalls.py)."""
        return f"IsGet_{self.actor}"

    @property
    def flag_hash(self) -> int:
        value = zlib.crc32(self.flag.encode())
        return value - (1 << 32) if value >= 1 << 31 else value


LOCATIONS = tuple(StallLocation(m, s) for m in MERCHANTS
                  for s in range(1, SLOTS_PER_MERCHANT + 1))
BY_ID = {location.id: location for location in LOCATIONS}
BY_NAME = {location.name: location for location in LOCATIONS}


def catalogue_row(location: StallLocation) -> dict:
    """The row of data/locations_master.csv (all values as the CSV writes them)."""
    return {"name": location.name, "region": location.merchant.region,
            "category": CATEGORY, "requires": "", "gamedata_flag": location.flag,
            "flag_hash": str(location.flag_hash),
            "notes": (f"{location.merchant.actor} object {location.object_hash} "
                      f"({location.vanilla_actor}); custom saved s32")}


def world_row(location: StallLocation) -> dict:
    """The row of botw_world/data/locations.json."""
    row = catalogue_row(location)
    return {**row, "id": location.id, "merchant": location.merchant.index,
            "slot": location.slot}
