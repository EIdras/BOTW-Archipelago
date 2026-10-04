"""The Legend of Zelda: Breath of the Wild (Wii U, Cemu) for Archipelago."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from BaseClasses import CollectionState, Item, ItemClassification, Location, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from Options import OptionError
from worlds.generic.Rules import set_rule

from .catalog import GAME, GOAL_LOCATION, ITEMS, LOCATIONS, TRAPS, WORLD_VERSION, categories, requirements
from .options import OPTION_GROUPS, PRESETS, BotwOptions
from .slot_file import BotwSlotFile


class BotwItem(Item):
    game = GAME


class BotwLocation(Location):
    game = GAME


class BotwWeb(WebWorld):
    theme = "grassFlowers"
    tutorials = [
        Tutorial("Multiworld Setup Guide",
                 "Install the BOTW Archipelago release and play Breath of the Wild in Cemu in a multiworld.",
                 "English", "setup_en.md", "setup/en", ["Simon"]),
        Tutorial("Guide de configuration multiworld",
                 "Installer la release BOTW Archipelago et jouer à Breath of the Wild dans Cemu en multiworld.",
                 "Français", "setup_fr.md", "setup/fr", ["Simon"]),
    ]
    option_groups = OPTION_GROUPS
    options_presets = PRESETS


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
        # Stall Items of the 28 stall locations, at random: a stall has 2 of
        # them, so it ends up with none, one or two.
        stalls = set(self.random.sample(sorted(r["id"] for r in LOCATIONS if "Stall" in categories(r)),
                                        self.options.stall_items.value))
        for row in LOCATIONS:
            shop = categories(row) & {"Shop", "Stall"}
            if shop:
                if ("Shop" in shop and row["slot"] > self.options.beedle_shop_items.value
                        or "Stall" in shop and row["id"] not in stalls):
                    continue
                self.shop_prices[row["id"]] = self.random.randint(*self.SHOP_PRICE_STEPS) * 5
            region = regions[row["region"]]
            loc = BotwLocation(self.player, row["name"],
                               None if row["name"] == GOAL_LOCATION else row["id"], region)
            region.locations.append(loc)
            set_rule(loc, self.rule(requirements(row)))
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

    def rule(self, groups):
        """An access rule from requirements(): every group met by one of its items."""
        player = self.player
        return lambda state: all(any(state.has(name, player, count) for name in names)
                                 for names, count in groups)

    def set_rules(self) -> None:
        player, options = self.player, self.options
        beasts = sorted(f"Freed - {name}" for name in self.location_name_groups["Divine Beasts"])
        shrines = sorted(f"Cleared - {name}" for name in self.location_name_groups["Shrines"])
        # Ganon's sanctum, sealed in game until these are met (botw_patch/ganon_gate.py).
        ganon = self.multiworld.get_location(GOAL_LOCATION, player)
        base = ganon.access_rule
        needed = (["Master Sword"] if options.sanctum_master_sword else []) + (
            sorted(self.item_name_groups["Runes"]) if options.sanctum_runes else [])

        def sanctum(state: CollectionState) -> bool:
            return (base(state) and state.has_all(needed, player)
                    and state.has_from_list(beasts, player, options.sanctum_divine_beasts.value)
                    and state.has_from_list(shrines, player, options.sanctum_shrines.value))
        set_rule(ganon, sanctum)
        # What finishes the game.
        if options.goal == options.goal.option_divine_beasts:
            done = lambda state: state.has_all(beasts, player)
        elif options.goal == options.goal.option_shrines:
            done = lambda state: state.has_from_list(shrines, player, options.goal_shrines.value)
        else:
            done = lambda state: state.has("Victory", player)
        self.multiworld.completion_condition[player] = done

    def create_item(self, name: str) -> BotwItem:
        row = next(r for r in ITEMS if r["name"] == name)
        # A rule names the Master Sword only when the sanctum asks for it.
        needed = name == "Master Sword" and self.options.sanctum_master_sword
        classification = (ItemClassification.progression if row.get("progression") or needed else
                          ItemClassification.useful if row.get("useful") else
                          ItemClassification.trap if row.get("trap") else ItemClassification.filler)
        return BotwItem(name, classification, row["id"], self.player)

    def get_filler_item_name(self) -> str:
        return "Rupee Bundle"

    def trap_names(self, filler: int) -> list[str]:
        """The traps that take the place of a share of the `filler` slots: Trap
        Percentage of them, each drawn by the weights of Trap Weights."""
        count = round(filler * self.options.trap_percentage.value / 100)
        weights = {name: self.options.trap_weights.value.get(name, 0) for name in TRAPS}
        names = [name for name, weight in weights.items() if weight > 0]
        if not count:
            return []
        if not names:
            raise OptionError(f"{self.player_name}: trap_percentage is above 0 "
                              "but every trap of trap_weights has a weight of 0")
        return self.random.choices(names, weights=[weights[name] for name in names], k=count)

    def create_items(self) -> None:
        pool = [self.create_item(row["name"]) for row in ITEMS if not row.get("trap")
                for _ in range(int(row.get("count", 1)))]
        # Main.py applies start_inventory_from_pool centrally after create_items.
        capacity = len(self.multiworld.get_unfilled_locations(self.player))
        if len(pool) > capacity:
            raise ValueError("BOTW item pool exceeds available locations")
        pool.extend(self.create_item(name) for name in self.trap_names(capacity - len(pool)))
        pool.extend(self.create_item(self.get_filler_item_name()) for _ in range(capacity - len(pool)))
        self.multiworld.itempool.extend(pool)

    def fill_slot_data(self) -> dict[str, Any]:
        # client_schema 4: the Gerudo Set, an item a client of schema 3 cannot deliver.
        # 5: the goal and the sanctum's requirements, which a client of schema 4 cannot read.
        return {"client_schema": 5, "world_schema": 4, "world_version": WORLD_VERSION,
                "death_link": bool(self.options.death_link.value),
                **self.options.as_dict("goal", "goal_shrines", "sanctum_divine_beasts", "sanctum_shrines",
                                       "sanctum_master_sword", "sanctum_runes",
                                       "beedle_shop_items", "stall_items")}

    @classmethod
    def data_package_checksum(cls) -> str:
        """The client's checksum of this game's DataPackage, as botw_client/session.py
        computes it from what the server sends (item ids, location ids)."""
        payload = {"game": GAME, "items": {code: name for name, code in cls.item_name_to_id.items()},
                   "locations": dict(cls.location_name_to_id)}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def generate_output(self, output_directory: str) -> None:
        """The slot file the game pack is built from (slot_file.py): placements and shop prices."""
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
                    # With the seed, the slot and the team (always 0), what binds the game
                    # pack to this slot: the file alone is enough to build it.
                    "data_package_checksum": self.data_package_checksum(),
                    "slot_data": self.fill_slot_data(), "placements": placements,
                    "shops": [{"location_id": location_id, "price": price}
                              for location_id, price in sorted(self.shop_prices.items())]}
        payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        manifest["content_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
        path = Path(output_directory, self.multiworld.get_out_file_name_base(self.player)
                    + BotwSlotFile.patch_file_ending)
        BotwSlotFile(manifest, str(path), self.player, self.multiworld.player_name[self.player]).write()
