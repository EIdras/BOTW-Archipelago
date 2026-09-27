"""The Legend of Zelda: Breath of the Wild (Wii U, Cemu) for Archipelago."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from BaseClasses import CollectionState, Item, ItemClassification, Location, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from worlds.generic.Rules import set_rule

from .catalog import GAME, GOAL_LOCATION, ITEMS, LOCATIONS, categories, requirements
from .options import OPTION_GROUPS, BotwOptions


class BotwItem(Item):
    game = GAME


class BotwLocation(Location):
    game = GAME


class BotwWeb(WebWorld):
    theme = "grassFlowers"
    tutorials = [
        Tutorial("Multiworld Setup Guide",
                 "Build the game pack of a seed and play Breath of the Wild in Cemu with Archipelago.",
                 "English", "setup_en.md", "setup/en", ["Simon"]),
        Tutorial("Guide de configuration multiworld",
                 "Construire le pack d'une seed et jouer à Breath of the Wild dans Cemu avec Archipelago.",
                 "Français", "setup_fr.md", "setup/fr", ["Simon"]),
    ]
    option_groups = OPTION_GROUPS


class BotwWorld(World):
    """Breath of the Wild, on Wii U (EUR v208) in Cemu. Shrines, towers, Great Fairies, Divine
    Beasts, the rune terminals, the Master Sword and optionally Beedle's shops and the village
    stalls send their rewards to the multiworld; the paraglider, the runes, the champions'
    abilities, armor, hearts and stamina arrive from it, presented by the game's own windows."""
    game = GAME
    web = BotwWeb()
    options_dataclass = BotwOptions
    options: BotwOptions
    topology_present = True
    required_client_version = (0, 6, 7)
    item_name_to_id = {row["name"]: row["id"] for row in ITEMS}
    location_name_to_id = {row["name"]: row["id"] for row in LOCATIONS if row["name"] != GOAL_LOCATION}
    item_name_groups = {"Runes": {"Magnesis", "Remote Bomb", "Stasis", "Cryonis"}}
    location_name_groups = {
        "Shrines": {r["name"] for r in LOCATIONS if "Shrine" in categories(r)},
        "Divine Beasts": {r["name"] for r in LOCATIONS if "Divine Beast" in categories(r)},
        "Divine Beast Hearts": {r["name"] for r in LOCATIONS
                                if "Divine Beast Heart" in categories(r)},
        "Beedle Shops": {r["name"] for r in LOCATIONS if "Shop" in categories(r)},
        "Stalls": {r["name"] for r in LOCATIONS if "Stall" in categories(r)},
    }
    # Shop prices drawn by the seed, in rupees: SHOP_PRICE_STEPS * 5.
    SHOP_PRICE_STEPS = (4, 40)
    shop_prices: dict[int, int]

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        regions = {name: Region(name, self.player, self.multiworld)
                   for name in sorted({r["region"] for r in LOCATIONS})}
        self.multiworld.regions.extend([menu, *regions.values()])
        menu.connect(regions["Great Plateau"])
        for name, region in regions.items():
            if name != "Great Plateau":
                regions["Great Plateau"].connect(
                    region, rule=lambda state: state.has("Paraglider", self.player))
        self.shop_prices = {}
        for row in LOCATIONS:
            shop = categories(row) & {"Shop", "Stall"}
            if shop:
                slots = (self.options.beedle_shop_items if "Shop" in shop
                         else self.options.stall_shop_items).value
                if row["slot"] > slots:
                    continue
                self.shop_prices[row["id"]] = self.random.randint(*self.SHOP_PRICE_STEPS) * 5
            region = regions[row["region"]]
            loc = BotwLocation(self.player, row["name"],
                               None if row["name"] == GOAL_LOCATION else row["id"], region)
            region.locations.append(loc)
            needed = requirements(row)
            set_rule(loc, lambda state, needed=needed: state.has_all(needed, self.player))
            if categories(row) & {"Shrine", "Divine Beast"}:
                # Events counted by the shrine and Divine Beast goals.
                prefix = "Cleared" if "Shrine" in categories(row) else "Freed"
                event = BotwLocation(self.player, f"{prefix} - {row['name']}", None, region)
                event.place_locked_item(BotwItem(event.name, ItemClassification.progression, None, self.player))
                set_rule(event, lambda state, loc=loc: loc.can_reach(state))
                region.locations.append(event)
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)
        goal = self.multiworld.get_location(GOAL_LOCATION, self.player)
        goal.place_locked_item(BotwItem("Victory", ItemClassification.progression, None, self.player))

    def set_rules(self) -> None:
        sword = self.multiworld.get_location("Master Sword Pedestal", self.player)
        set_rule(sword, lambda state: state.has("Paraglider", self.player)
                 and state.has("Heart Container", self.player, 10))
        goal = self.multiworld.get_location(GOAL_LOCATION, self.player)
        base = goal.access_rule

        def can_finish(state: CollectionState) -> bool:
            if not base(state):
                return False
            if self.options.goal_type.value == 1:
                return sum(state.has(f"Freed - {n}", self.player) for n in
                           self.location_name_groups["Divine Beasts"]) >= self.options.divine_beasts_required.value
            if self.options.goal_type.value == 2:
                return sum(state.has(f"Cleared - {n}", self.player) for n in
                           self.location_name_groups["Shrines"]) >= self.options.shrines_required.value
            return True
        set_rule(goal, can_finish)

    def create_item(self, name: str) -> BotwItem:
        row = next(r for r in ITEMS if r["name"] == name)
        classification = (ItemClassification.progression if row.get("progression") else
                          ItemClassification.useful if row.get("useful") else
                          ItemClassification.trap if row.get("trap") else ItemClassification.filler)
        return BotwItem(name, classification, row["id"], self.player)

    def get_filler_item_name(self) -> str:
        return "Rupee Bundle"

    def create_items(self) -> None:
        # Traps without an automatic, accepted game operation are not generated.
        pool = [self.create_item(row["name"]) for row in ITEMS if not row.get("trap")
                for _ in range(int(row.get("count", 1)))]
        # Main.py applies start_inventory_from_pool centrally after create_items.
        capacity = len(self.multiworld.get_unfilled_locations(self.player))
        if len(pool) > capacity:
            raise ValueError("BOTW item pool exceeds available locations")
        pool.extend(self.create_item(self.get_filler_item_name()) for _ in range(capacity - len(pool)))
        self.multiworld.itempool.extend(pool)

    def fill_slot_data(self) -> dict[str, Any]:
        return {"client_schema": 3, "world_schema": 4, "death_link": False,
                **self.options.as_dict("goal_type", "shrines_required", "divine_beasts_required",
                                       "beedle_shop_items", "stall_shop_items")}

    def generate_output(self, output_directory: str) -> None:
        """The slot manifest the game pack is built from: placements and shop prices."""
        placements = []
        for row in LOCATIONS:
            if categories(row) & {"Shop", "Stall"} and row["id"] not in self.shop_prices:
                continue
            loc = self.multiworld.get_location(row["name"], self.player)
            if loc.address is not None and loc.item and loc.item.code is not None:
                placements.append({"location_id": loc.address, "location_name": loc.name,
                                   "item_id": loc.item.code, "item_name": loc.item.name,
                                   "recipient": loc.item.player, "recipient_game": loc.item.game,
                                   "recipient_name": self.multiworld.player_name[loc.item.player],
                                   "flags": int(loc.item.classification)})
        manifest = {"schema": 1, "game": GAME, "seed": self.multiworld.seed_name,
                    "slot": self.player, "slot_name": self.multiworld.player_name[self.player],
                    "slot_data": self.fill_slot_data(), "placements": placements,
                    "shops": [{"location_id": location_id, "price": price}
                              for location_id, price in sorted(self.shop_prices.items())]}
        payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        manifest["content_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
        filename = self.multiworld.get_out_file_name_base(self.player) + ".apbotw.json"
        Path(output_directory, filename).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                                    encoding="utf-8")
