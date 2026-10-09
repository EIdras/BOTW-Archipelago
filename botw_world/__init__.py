"""The Legend of Zelda: Breath of the Wild (Wii U, Cemu) for Archipelago."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from BaseClasses import Item, ItemClassification, Location, MultiWorld, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from Options import OptionError
from rule_builder.rules import And, Has, HasAll, HasAny, HasFromList, Or, Rule, True_

from .catalog import (FILLER, GAME, GENTLE_REGIONS, GOAL_LOCATION, ITEMS, LOCATIONS, MAPS, TRAPS, WEAPON_LEVELS,
                      WORLD_VERSION, categories, map_keys, requirements)
from .options import OPTION_GROUPS, PRESETS, BotwOptions, StartingMap, TowerMaps, WeaponOrder
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
    item_name_groups = {"Runes": {"Magnesis", "Remote Bomb", "Stasis", "Cryonis"},
                        "Weapons": set(WEAPON_LEVELS), "Maps": set(MAPS.values())}
    # Universal Tracker shows as "glitched" (out of logic, but possible) what this
    # item, which only it gives itself, would reach: a region without its map.
    glitches_item_name = "Region Without Its Map"
    # weapon_order loosely_smoothed: how far, in levels, a weapon may move.
    WEAPON_LEVEL_SPREAD = 1.5
    STALL_IDS = frozenset(r["id"] for r in LOCATIONS if "Stall" in categories(r))
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
    # Universal Tracker regenerates the world from the slot data alone
    # (interpret_slot_data, generate_early).
    ut_can_gen_without_yaml = True
    # The options that shape the world, given back by the slot data.
    SLOT_OPTIONS = ("goal", "goal_shrines", "sanctum_divine_beasts", "sanctum_shrines",
                    "sanctum_master_sword", "sanctum_runes", "beedle_shop_items", "stall_items", "tower_maps")
    # The stall locations of the slot data, when Universal Tracker regenerates.
    passed_stalls: set[int] | None = None

    @staticmethod
    def interpret_slot_data(slot_data: dict[str, Any]) -> dict[str, Any]:
        """Universal Tracker: the slot data, given back to generate_early."""
        return slot_data

    def generate_early(self) -> None:
        passed = getattr(self.multiworld, "re_gen_passthrough", {}).get(self.game)
        if not passed:
            return
        for name in self.SLOT_OPTIONS:
            if name in passed:
                getattr(self.options, name).value = passed[name]
        # A seed of world 0.1 has no maps; the starting map comes back as an item received.
        if "tower_maps" not in passed:
            self.options.tower_maps.value = TowerMaps.option_vanilla
        self.options.starting_map.value = StartingMap.option_none
        # A seed generated before world 0.2.0 does not name its stalls: they are
        # drawn again, and may differ from the seed's.
        if "stall_locations" in passed:
            self.passed_stalls = set(passed["stall_locations"])

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        regions = {name: Region(name, self.player, self.multiworld)
                   for name in sorted({r["region"] for r in LOCATIONS})}
        self.multiworld.regions.extend([menu, *regions.values()])
        menu.connect(regions["Great Plateau"])
        for name, region in regions.items():
            if name != "Great Plateau":
                self.create_entrance(regions["Great Plateau"], region, Has("Paraglider"))
        self.shop_prices = {}
        # Stall Items of the 28 stall locations, at random: a stall has 2 of
        # them, so it ends up with none, one or two.
        stalls = self.passed_stalls if self.passed_stalls is not None else set(self.random.sample(
            sorted(r["id"] for r in LOCATIONS if "Stall" in categories(r)), self.options.stall_items.value))
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
            self.set_rule(loc, self.location_rule(row))
            if categories(row) & {"Shrine", "Divine Beast"}:
                # Events counted by the shrine and Divine Beast goals: in the
                # location's region, with its rule.
                prefix = "Cleared" if "Shrine" in categories(row) else "Freed"
                event = BotwLocation(self.player, f"{prefix} - {row['name']}", None, region)
                event.place_locked_item(BotwItem(event.name, ItemClassification.progression, None, self.player))
                self.set_rule(event, self.location_rule(row))
                region.locations.append(event)
        goal = self.multiworld.get_location(GOAL_LOCATION, self.player)
        goal.place_locked_item(BotwItem("Victory", ItemClassification.progression, None, self.player))

    def location_rule(self, row) -> Rule:
        """A location's rule: its requirements, and with tower_maps on region_keys,
        its maps (map_keys), or Universal Tracker's stand-in for a missing map."""
        rule = self.rule(requirements(row))
        maps = map_keys(row) if self.options.tower_maps == TowerMaps.option_region_keys else ()
        if not maps:
            return rule
        keys = Or(Has(maps[0]) if len(maps) == 1 else HasAll(*maps), Has(self.glitches_item_name))
        return keys if isinstance(rule, True_) else And(rule, keys)

    @staticmethod
    def rule(groups) -> Rule:
        """An access rule from requirements(): every group met by one of its
        names, that one name `count` times. Built from Archipelago's rule
        builder, which can say what is missing (Universal Tracker's /explain)."""
        parts = [Has(names[0], count) if len(names) == 1 else
                 HasAny(*names) if count == 1 else
                 Or(*(Has(name, count) for name in names))
                 for names, count in groups]
        return And(*parts) if len(parts) > 1 else parts[0] if parts else True_()

    def set_rules(self) -> None:
        player, options = self.player, self.options
        beasts = sorted(f"Freed - {name}" for name in self.location_name_groups["Divine Beasts"])
        shrines = sorted(f"Cleared - {name}" for name in self.location_name_groups["Shrines"])
        # Ganon's sanctum, sealed in game until these are met (botw_patch/ganon_gate.py).
        ganon = self.multiworld.get_location(GOAL_LOCATION, player)
        needed = (["Master Sword"] if options.sanctum_master_sword else []) + (
            sorted(self.item_name_groups["Runes"]) if options.sanctum_runes else [])
        parts = [self.rule(requirements(next(r for r in LOCATIONS if r["name"] == GOAL_LOCATION)))]
        if needed:
            parts.append(HasAll(*needed))
        if options.sanctum_divine_beasts.value:
            parts.append(HasFromList(*beasts, count=options.sanctum_divine_beasts.value))
        if options.sanctum_shrines.value:
            parts.append(HasFromList(*shrines, count=options.sanctum_shrines.value))
        self.set_rule(ganon, And(*parts) if len(parts) > 1 else parts[0])
        # What finishes the game.
        if options.goal == options.goal.option_divine_beasts:
            done = HasAll(*beasts)
        elif options.goal == options.goal.option_shrines:
            done = HasFromList(*shrines, count=options.goal_shrines.value)
        else:
            done = Has("Victory")
        self.set_completion_rule(done)

    def create_item(self, name: str) -> BotwItem:
        if name == self.glitches_item_name:
            return BotwItem(name, ItemClassification.progression, None, self.player)
        row = next(r for r in ITEMS if r["name"] == name)
        # A rule names the Master Sword only when the sanctum asks for it, a map
        # when the maps are region keys.
        needed = (name == "Master Sword" and self.options.sanctum_master_sword
                  or name in MAPS.values() and self.options.tower_maps == TowerMaps.option_region_keys)
        classification = (ItemClassification.progression if row.get("progression") or needed else
                          ItemClassification.useful if row.get("useful") else
                          ItemClassification.trap if row.get("trap") else ItemClassification.filler)
        return BotwItem(name, classification, row["id"], self.player)

    def get_filler_item_name(self) -> str:
        """Arrows, elixirs, weapons, gems or rupees, drawn by FILLER's weights."""
        families = list(FILLER.values())
        _weight, items = self.random.choices(families, weights=[w for w, _ in families])[0]
        return self.random.choices(list(items), weights=list(items.values()))[0]

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

    def maps(self) -> list[str]:
        """The maps of the pool, all 14 (tower_maps on items or region_keys) or
        none, but the one starting_map gives Link at the start."""
        if self.options.tower_maps == TowerMaps.option_vanilla:
            return []
        maps = list(MAPS.values())
        choice = self.options.starting_map
        if choice != StartingMap.option_none:
            regions = GENTLE_REGIONS if choice == StartingMap.option_gentle else sorted(MAPS)
            start = MAPS[self.random.choice(regions)]
            self.multiworld.push_precollected(self.create_item(start))
            maps.remove(start)
        return maps

    def create_items(self) -> None:
        pool = [self.create_item(row["name"]) for row in ITEMS if not row.get("trap")
                and row["name"] not in MAPS.values() for _ in range(int(row.get("count", 1)))]
        pool += [self.create_item(name) for name in self.maps()]
        # Main.py applies start_inventory_from_pool centrally after create_items.
        capacity = len(self.multiworld.get_unfilled_locations(self.player))
        if len(pool) > capacity:
            raise ValueError("BOTW item pool exceeds available locations")
        pool.extend(self.create_item(name) for name in self.trap_names(capacity - len(pool)))
        pool.extend(self.create_item(self.get_filler_item_name()) for _ in range(capacity - len(pool)))
        self.multiworld.itempool.extend(pool)

    @classmethod
    def stage_finalize_multiworld(cls, multiworld: MultiWorld) -> None:
        """weapon_order, once the fill and the progression balancing are done, as
        Dark Souls III smooths its weapons: the spheres of the whole multiworld,
        computed once, then each world's weapons dealt again over their own
        locations. No rule names a weapon, so the spheres do not change."""
        worlds = [world for world in multiworld.get_game_worlds(cls.game)
                  if world.options.weapon_order != WeaponOrder.option_anywhere]
        if not worlds:
            return
        spheres = []
        for sphere in multiworld.get_spheres():
            if not sphere:
                break           # what follows is unreachable: left as the fill put it
            spheres.append(sorted(sphere))
        for world in worlds:
            world.order_weapons(spheres)

    def order_weapons(self, spheres: list[list[Location]]) -> None:
        """The locations holding this world's weapons, in any world, by sphere (at
        random within one), receive these weapons again by level: the weaker in
        the first. Loosely smoothed, each level moves by up to WEAPON_LEVEL_SPREAD.
        The jokes (level 0) and the plando's locked placements do not move. A
        location's own rules still decide what it takes; should they leave a weapon
        without a place, the fill's placement stays."""
        locations = []
        for sphere in spheres:
            mine = [location for location in sphere if not location.locked
                    and location.item.player == self.player and WEAPON_LEVELS.get(location.item.name)]
            self.random.shuffle(mine)
            locations += mine
        weapons = [location.item for location in locations]
        self.random.shuffle(weapons)
        spread = (self.WEAPON_LEVEL_SPREAD
                  if self.options.weapon_order == WeaponOrder.option_loosely_smoothed else 0)
        order = sorted(((WEAPON_LEVELS[item.name] + self.random.uniform(-spread, spread), index)
                        for index, item in enumerate(weapons)))
        free, placements = list(locations), []
        for _key, index in order:
            item = weapons[index]
            spot = next((location for location in free
                         if location.can_fill(self.multiworld.state, item, check_access=False)), None)
            if spot is None:
                logging.warning(f"{self.player_name}: weapon_order left as the fill made it "
                                f"(no location takes {item.name})")
                return
            free.remove(spot)
            placements.append((spot, item))
        for location, item in placements:
            self.multiworld.push_item(location, item, collect=False)

    def fill_slot_data(self) -> dict[str, Any]:
        # client_schema 4: the Gerudo Set, an item a client of schema 3 cannot deliver.
        # 5: the goal and the sanctum's requirements, which a client of schema 4 cannot read.
        # 6: arrows, elixirs, gems and rupees as filler, which a client of schema 5 cannot deliver.
        # 7: weapons as filler, which a client of schema 6 cannot deliver.
        # 8: the Master Cycle Zero, the Travel Medallion and the Korok Mask, which one of 7 cannot.
        # 9: Epona, registered at the stables, and the Master Cycle Zero selected only when no
        #    rune is, which one of 8 cannot.
        # 10: the tower maps, as items, which one of 9 cannot deliver nor tell from the towers.
        # stall_locations: the stalls drawn by the seed, for Universal Tracker.
        return {"client_schema": 10, "world_schema": 4, "world_version": WORLD_VERSION,
                "death_link": bool(self.options.death_link.value),
                **self.options.as_dict(*self.SLOT_OPTIONS),
                "stall_locations": sorted(location_id for location_id in self.shop_prices
                                          if location_id in self.STALL_IDS)}

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
