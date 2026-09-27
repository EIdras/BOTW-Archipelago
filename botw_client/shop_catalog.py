"""Archipelago shop locations: the single source of their names, IDs and flags.

Pure data, importable by the client, the resource builder and the tests (the
APWorld and data/locations_master.csv carry the same rows; a test checks
they match this module).

Beedle (Terry, Npc_TripMaster_00..15) sells from a list at the 15 stables and
at Kara Kara Bazaar. Each of his 16 appearances has its own stock sheet
(Actor/ShopData/Npc_TripMaster_k.bshop); places were read from the map units
(nearest LocationTag) and named from LocationMarker.msbt (docs/reference/
shops_plan.md). Up to SLOTS_PER_MERCHANT stock entries of each become AP
locations, shown first in the list; buying one sets its saved s32 flag
APShop_<id> to 1 (the merchant's flow does it, see botw_patch/shops.py), which
the client tracks like any other location flag.
"""
from __future__ import annotations

from dataclasses import dataclass
import zlib

FIRST_LOCATION_ID = 154          # append-only after the 153 schema-2 locations
SLOTS_PER_MERCHANT = 2
CATEGORY = "Shop"
FLAG_KIND = "s32"


@dataclass(frozen=True)
class Merchant:
    index: int
    place: str          # English marker name
    place_fr: str       # French marker name
    region: str         # region of the nearest shrine (logic: any region needs the paraglider)
    # Vanilla `Normal` table, in order (checked against the sheet at build time).
    stock: tuple[str, ...]

    @property
    def actor(self) -> str:
        return f"Npc_TripMaster_{self.index:02d}"


_A, _B1, _B2 = "Obj_ArrowNormal_A_01", "Obj_ArrowBundle_A_01", "Obj_ArrowBundle_A_02"
MERCHANTS = (
    Merchant(0, "Dueling Peaks Stable", "Relais des Géminés", "Dueling Peaks",
             (_A, _B1, "Animal_Insect_H", "Animal_Insect_A", "Item_Enemy_57")),
    Merchant(1, "Foothill Stable", "Relais du pied de la montagne", "Eldin",
             (_A, _B1, "Animal_Insect_B", "Animal_Insect_M")),
    Merchant(2, "Gerudo Canyon Stable", "Relais du canyon Gerudo", "Wasteland",
             (_A, _B2, "Animal_Insect_N", "Animal_Insect_T", "Animal_Insect_M")),
    Merchant(3, "East Akkala Stable", "Relais de l'est d'Akkala", "Akkala",
             (_A, _B2, "Item_Plant_M", "Animal_Insect_AB", "Item_Plant_B")),
    Merchant(4, "Tabantha Bridge Stable", "Relais du pont de Tabanta", "Tabantha",
             (_A, _B2, "Animal_Insect_Q", "Animal_Insect_N", "Animal_Insect_R")),
    Merchant(5, "Serenne Stable", "Relais de Delass", "Ridgeland",
             (_A, _B2, "Animal_Insect_T", "Animal_Insect_E", "Animal_Insect_B")),
    Merchant(6, "South Akkala Stable", "Relais du sud d'Akkala", "Akkala",
             (_A, _B2, "Animal_Insect_S", "Animal_Insect_X", "Animal_Insect_M")),
    Merchant(7, "Rito Stable", "Relais des Piafs", "Tabantha",
             (_A, _B2, "Animal_Insect_E", "Animal_Insect_T", "Animal_Insect_B")),
    Merchant(8, "Riverside Stable", "Relais de la rivière", "Dueling Peaks",
             (_A, _B1, "Animal_Insect_R", "Animal_Insect_I", "Animal_Insect_B")),
    Merchant(9, "Lakeside Stable", "Relais du lac", "Faron",
             (_A, _B1, "Animal_Insect_R", "Animal_Insect_S", "Animal_Insect_B")),
    Merchant(10, "Outskirt Stable", "Relais de l'orée de la plaine", "Central",
             (_A, _B1, "Animal_Insect_A", "Animal_Insect_H", "Animal_Insect_M")),
    Merchant(11, "Woodland Stable", "Relais de la forêt", "Woodland",
             (_A, _B1, "Animal_Insect_C", "Animal_Insect_E", "Animal_Insect_M")),
    Merchant(12, "Wetland Stable", "Relais des marécages", "Lanayru",
             (_A, _B1, "Animal_Insect_A", "Animal_Insect_AB", "Animal_Insect_B")),
    Merchant(13, "Snowfield Stable", "Relais des prairies gelées", "Hebra",
             (_A, _B2, "Animal_Insect_Q", "Animal_Insect_T", "Animal_Insect_B")),
    Merchant(14, "Highland Stable", "Relais des alpages", "Lake",
             (_A, _B2, "Animal_Insect_E", "Animal_Insect_M", "Item_Enemy_57")),
    Merchant(15, "Kara Kara Bazaar", "Bazar Assek", "Gerudo",
             (_A, _B2, "Animal_Insect_Q", "Animal_Insect_C", "Animal_Insect_B")),
)
# Arrows (single and bundle) stay on sale: the AP entries replace insects and
# materials only, so every sheet keeps at least SLOTS_PER_MERCHANT of those.
KEPT = 2


@dataclass(frozen=True)
class ShopLocation:
    merchant: Merchant
    slot: int           # 1..SLOTS_PER_MERCHANT, position in the list

    @property
    def id(self) -> int:
        return FIRST_LOCATION_ID + SLOTS_PER_MERCHANT * self.merchant.index + self.slot - 1

    @property
    def name(self) -> str:
        return f"{self.merchant.place} - Beedle Item {self.slot}"

    @property
    def actor(self) -> str:
        """The item actor created for this location (unique: it names the location)."""
        return f"AP_Shop_{self.id:03d}"

    @property
    def flag(self) -> str:
        return f"APShop_{self.id:03d}"

    @property
    def shown_flag(self) -> str:
        """Saved bool, true until bought: the stock entry carries ItemLookGetFlg,
        which shows an entry only while IsGet_<its actor> is true (10f bis), so
        clearing it takes the bought item out of the list for good."""
        return f"IsGet_{self.actor}"

    @property
    def flag_hash(self) -> int:
        """Signed crc32, as GameData and the CSV store it."""
        value = zlib.crc32(self.flag.encode())
        return value - (1 << 32) if value >= 1 << 31 else value


LOCATIONS = tuple(ShopLocation(m, s) for m in MERCHANTS
                  for s in range(1, SLOTS_PER_MERCHANT + 1))
BY_ID = {location.id: location for location in LOCATIONS}
BY_NAME = {location.name: location for location in LOCATIONS}
BY_ACTOR = {location.actor: location for location in LOCATIONS}


def catalogue_row(location: ShopLocation) -> dict:
    """The row of data/locations_master.csv (all values as the CSV writes them)."""
    return {"name": location.name, "region": location.merchant.region,
            "category": CATEGORY, "requires": "", "gamedata_flag": location.flag,
            "flag_hash": str(location.flag_hash),
            "notes": f"{location.merchant.actor} slot {location.slot}; custom saved s32"}


def world_row(location: ShopLocation) -> dict:
    """The row of botw_world/data/locations.json."""
    row = catalogue_row(location)
    return {**row, "id": location.id, "merchant": location.merchant.index,
            "slot": location.slot}


def same_merchant(location_id: int) -> list[int]:
    """Every shop location ID sold by the merchant of this one."""
    merchant = BY_ID[location_id].merchant
    return [location.id for location in LOCATIONS if location.merchant == merchant]
