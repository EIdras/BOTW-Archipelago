"""The Legend of Zelda: Breath of the Wild (Wii U, Cemu) for Archipelago."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, ClassVar

from BaseClasses import Item, ItemClassification, Location, LocationProgressType, MultiWorld, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from worlds.generic.Rules import forbid_item
from Options import OptionError
from rule_builder.rules import And, CanReachRegion, Has, HasAll, HasAny, HasFromList, Or, Rule, True_

from .catalog import (BOSSES, CHESTS, EXTRA_FILLER, FILLER, GAME, GENTLE_REGIONS, GOAL_LOCATION, INNER_REGIONS, ITEMS, KOROKS, LOCATIONS, MAPS,
                      NEIGHBOURS,
                      OFFERINGS, OPEN_BORDERS, ORBS_PER_TRADE, QUESTS, SIDE_QUEST_ITEMS, TRAPS, TRAVEL_SHRINES, TRAVEL_TERMINALS, WEAPON_LEVELS, WORLD_VERSION, categories,
                      map_keys, requirements)
from .options import ELEMENTAL_TRAPS, OPTION_GROUPS, PRESETS, BotwOptions, ChestSanity, EarlyMap, SpiritOrbs, TowerMaps, WeaponOrder
from .tracker import TRACKER_WORLD, BotwSettings
from .slot_file import BotwSlotFile


# The most heart containers a location asks for: the Master Sword's.
HEARTS_NEEDED = max(count for row in LOCATIONS for names, count in requirements(row) if names == ("Heart Container",))


class BotwItem(Item):
    game = GAME


class BotwLocation(Location):
    game = GAME


class BotwWeb(WebWorld):
    theme = "grassFlowers"
    tutorials = [
        Tutorial("Multiworld Setup Guide",
                 "Install the BOTW Archipelago release and play Breath of the Wild in Cemu in a multiworld.",
                 "English", "setup_en.md", "setup/en", ["EIdras"]),
        Tutorial("Guide de configuration multiworld",
                 "Installer la release BOTW Archipelago et jouer à Breath of the Wild dans Cemu en multiworld.",
                 "Français", "setup_fr.md", "setup/fr", ["EIdras"]),
    ]
    option_groups = OPTION_GROUPS
    options_presets = PRESETS


class BotwWorld(World):
    """Breath of the Wild, on Wii U (v208: EUR, USA or JPN) in Cemu. Shrines, towers, Great Fairies, Divine
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
    location_name_to_id = {**{row["name"]: row["id"] for row in LOCATIONS if row["name"] != GOAL_LOCATION},
                           **{row["name"]: row["id"] for row in CHESTS},
                           **{row["name"]: row["id"] for row in KOROKS},
                           **{row["name"]: row["id"] for row in QUESTS},
                           **{row["name"]: row["id"] for row in OFFERINGS},
                           **{row["name"]: row["id"] for row in BOSSES}}
    item_name_groups = {"Runes": {"Magnesis", "Progressive Remote Bomb", "Progressive Stasis", "Cryonis"},
                        "Weapons": set(WEAPON_LEVELS), "Maps": set(MAPS.values())}
    # Universal Tracker shows as "glitched" (out of logic, but possible) what this
    # item, which only it gives itself, would reach: a region without its map.
    glitches_item_name = "Region Without Its Map"
    # Universal Tracker's map tab (botw_world/tracker.py), and where its pack is (host.yaml).
    tracker_world = TRACKER_WORLD
    settings: ClassVar[BotwSettings]
    settings_key = "botw_options"
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
        "Rune Upgrades": {r["name"] for r in LOCATIONS if "Rune Upgrade" in categories(r)},
        "Champions' Ballad": {r["name"] for r in LOCATIONS if "Champions' Ballad" in categories(r)},
        "Chests": {r["name"] for r in CHESTS},
        **{f"{kind} Chests": {r["name"] for r in CHESTS if r.get("dungeon") in
                              {loc["name"] for loc in LOCATIONS if kind in categories(loc)}}
           for kind in ("Shrine", "Divine Beast")},
        **{f"Chests: {region}": {r["name"] for r in CHESTS if r["region"] == region}
           for region in sorted({r["region"] for r in CHESTS})},
        **{f"{kind} Chests": {r["name"] for r in CHESTS if r["kind"] == kind}
           for kind in sorted({r["kind"] for r in CHESTS})},
        "Koroks": {r["name"] for r in KOROKS},
        **{f"Koroks: {region}": {r["name"] for r in KOROKS if r["region"] == region}
           for region in sorted({r["region"] for r in KOROKS})},
        "Quests": {r["name"] for r in QUESTS},
        **{f"{kind} Quests": {r["name"] for r in QUESTS if r["kind"] == kind} for kind in ("Side", "Shrine")},
        **{f"Quests: {region}": {r["name"] for r in QUESTS if r["region"] == region}
           for region in sorted({r["region"] for r in QUESTS})},
        "Goddess Statue Offerings": {r["name"] for r in OFFERINGS},
        "Bosses": {r["name"] for r in BOSSES},
        **{f"Bosses: {region}": {r["name"] for r in BOSSES if r["region"] == region}
           for region in sorted({r["region"] for r in BOSSES})},
    }
    # Shop prices drawn by the seed, in rupees: SHOP_PRICE_STEPS * 5.
    SHOP_PRICE_STEPS = (4, 40)
    shop_prices: dict[int, int]
    # Universal Tracker regenerates the world from the slot data alone
    # (interpret_slot_data, generate_early).
    ut_can_gen_without_yaml = True
    # The options that shape the world, given back by the slot data.
    SLOT_OPTIONS = ("goal", "goal_shrines", "sanctum_divine_beasts", "sanctum_shrines",
                    "sanctum_master_sword", "sanctum_runes", "beedle_shop_items", "stall_items", "tower_maps",
                    "towers_need_maps", "region_lock", "map_travel_points", "bike_anywhere",
                    "cutscene_skip", "spirit_orbs", "statue_offerings", "chest_sanity", "shrine_chest_items", "korok_sanity", "korok_count",
                    "side_quest_sanity", "shrine_quest_sanity", "boss_sanity", "progressive_horse")
    # The region each map opens: {item: region}.
    MAP_REGIONS = {item: region for region, item in MAPS.items()}
    # Whether Universal Tracker regenerates the world from the slot data (generate_early). It never
    # fills: what only shapes the fill (korok_local_filler, the progression options) is left out of the
    # slot data, so the world places no local filler and checks no room for it (create_items).
    regenerated = False
    # The stall locations of the slot data, when Universal Tracker regenerates.
    passed_stalls: set[int] | None = None
    # korok_sanity's Koroks given back by the slot data, when Universal Tracker regenerates.
    passed_koroks: set[int] | None = None
    # korok_sanity: the Korok rows that are locations (create_regions).
    koroks: list[dict]
    # side_quest_sanity, shrine_quest_sanity: the quest rows that are locations (create_regions).
    quests: list[dict]
    # spirit_orbs on statue_checks: the offerings that are locations (create_regions).
    offerings: list[dict]
    # boss_sanity: the boss rows that are locations (create_regions).
    bosses: list[dict]

    @staticmethod
    def interpret_slot_data(slot_data: dict[str, Any]) -> dict[str, Any]:
        """Universal Tracker: the slot data, given back to generate_early."""
        return slot_data

    def generate_early(self) -> None:
        if self.options.region_lock and self.options.tower_maps != TowerMaps.option_region_keys:
            raise OptionError(f"{self.player_name}: region_lock needs tower_maps on region_keys")
        if self.options.towers_need_maps and self.options.tower_maps != TowerMaps.option_region_keys:
            raise OptionError(f"{self.player_name}: towers_need_maps needs tower_maps on region_keys")
        if self.options.chest_progression and not self.options.chest_sanity:
            raise OptionError(f"{self.player_name}: chest_progression needs chest_sanity")
        if self.options.korok_progression and not self.options.korok_sanity:
            raise OptionError(f"{self.player_name}: korok_progression needs korok_sanity")
        if self.options.quest_progression and not (self.options.side_quest_sanity
                                                   or self.options.shrine_quest_sanity):
            raise OptionError(f"{self.player_name}: quest_progression needs side_quest_sanity "
                              "or shrine_quest_sanity")
        if self.options.boss_progression and not self.options.boss_sanity:
            raise OptionError(f"{self.player_name}: boss_progression needs boss_sanity")
        if self.options.shrine_chest_items and self.options.chest_sanity != ChestSanity.option_ap_items:
            raise OptionError(f"{self.player_name}: shrine_chest_items needs chest_sanity on ap_items")
        if self.options.map_travel_points and self.options.tower_maps == TowerMaps.option_vanilla:
            raise OptionError(f"{self.player_name}: map_travel_points needs the maps as items (tower_maps)")
        passed = getattr(self.multiworld, "re_gen_passthrough", {}).get(self.game)
        if not passed:
            return
        self.regenerated = True
        for name in self.SLOT_OPTIONS:
            if name in passed:
                getattr(self.options, name).value = passed[name]
        # A seed generated before the maps has none.
        if "tower_maps" not in passed:
            self.options.tower_maps.value = TowerMaps.option_vanilla
        # A seed generated before world 0.2.0 does not name its stalls: they are
        # drawn again, and may differ from the seed's.
        if "stall_locations" in passed:
            self.passed_stalls = set(passed["stall_locations"])
        if "korok_locations" in passed:
            self.passed_koroks = set(passed["korok_locations"])

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        regions = {name: Region(name, self.player, self.multiworld)
                   for name in sorted({r["region"] for r in LOCATIONS})}
        self.multiworld.regions.extend([menu, *regions.values()])
        menu.connect(regions["Great Plateau"])
        if self.options.region_lock:
            self.connect_neighbours(regions)
        else:
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
        if self.options.chest_sanity:
            # Excluded, but with chest_progression those whose opening the map says.
            for row in CHESTS:
                loc = BotwLocation(self.player, row["name"], row["id"], regions[row["region"]])
                if not self.options.chest_progression or row["no_progression"]:
                    loc.progress_type = LocationProgressType.EXCLUDED
                regions[row["region"]].locations.append(loc)
                self.set_rule(loc, self.location_rule(row))
        # korok_sanity: korok_count Koroks drawn by the seed, excluded, but with
        # korok_progression those whose puzzle the world's items solve.
        self.koroks = self.chosen_koroks()
        for row in self.koroks:
            loc = BotwLocation(self.player, row["name"], row["id"], regions[row["region"]])
            if not self.options.korok_progression or row["no_progression"]:
                loc.progress_type = LocationProgressType.EXCLUDED
            regions[row["region"]].locations.append(loc)
            self.set_rule(loc, self.location_rule(row))
        # side_quest_sanity, shrine_quest_sanity: the quests, excluded, but with
        # quest_progression all but those of no_progression (rupees, weapons, long, stamina).
        self.quests = [row for row in QUESTS if (self.options.side_quest_sanity if row["kind"] == "Side"
                                                 else self.options.shrine_quest_sanity)]
        for row in self.quests:
            loc = BotwLocation(self.player, row["name"], row["id"], regions[row["region"]])
            if not self.options.quest_progression or row["no_progression"]:
                loc.progress_type = LocationProgressType.EXCLUDED
            regions[row["region"]].locations.append(loc)
            self.set_rule(loc, self.location_rule(row))
        # spirit_orbs on statue_checks: the statues' trades. Offering k takes 4k orbs, and a
        # shrine cleared, which the Temple of Time's statue asks for (Demo034_0_0).
        self.offerings = OFFERINGS[:self.options.statue_offerings.value] \
            if self.options.spirit_orbs == SpiritOrbs.option_statue_checks else []
        cleared = tuple(sorted(f"Cleared - {name}" for name in self.location_name_groups["Shrines"]))
        for row in self.offerings:
            loc = BotwLocation(self.player, row["name"], row["id"], regions[row["region"]])
            regions[row["region"]].locations.append(loc)
            self.set_rule(loc, self.rule(((("Spirit Orb",), ORBS_PER_TRADE * row["number"]), (cleared, 1))))
        # boss_sanity: every boss, excluded, but with boss_progression.
        self.bosses = BOSSES if self.options.boss_sanity else []
        for row in self.bosses:
            loc = BotwLocation(self.player, row["name"], row["id"], regions[row["region"]])
            if not self.options.boss_progression:
                loc.progress_type = LocationProgressType.EXCLUDED
            regions[row["region"]].locations.append(loc)
            self.set_rule(loc, self.location_rule(row))
        goal = self.multiworld.get_location(GOAL_LOCATION, self.player)
        goal.place_locked_item(BotwItem("Victory", ItemClassification.progression, None, self.player))

    def chosen_koroks(self) -> list[dict]:
        """korok_sanity's Koroks: korok_count of them drawn by the seed, or those
        its slot data gives back to Universal Tracker."""
        if not self.options.korok_sanity:
            return []
        if self.passed_koroks is not None:
            return [row for row in KOROKS if row["id"] in self.passed_koroks]
        return sorted(self.random.sample(KOROKS, self.options.korok_count.value), key=lambda row: row["number"])

    def connect_neighbours(self, regions: dict[str, Region]) -> None:
        """region_lock: a region entered from each of its neighbours with its map,
        or Universal Tracker's stand-in for a missing map, and from the Great Plateau
        with the Paraglider too; a region inside another's area, from that one. With
        map_travel_points, a region's travel point is warped to from anywhere: in the
        logic, from the Great Plateau."""
        travel = bool(self.options.map_travel_points)
        for name in sorted(NEIGHBOURS):
            others = set(MAPS) if travel and name == "Great Plateau" else NEIGHBOURS[name]
            for other in sorted(others - {"Great Plateau"}):
                key = Or(Has(MAPS[other]), Has(self.glitches_item_name))
                self.create_entrance(regions[name], regions[other],
                                     And(Has("Paraglider"), key) if name == "Great Plateau" else key)
        for inner, outer in INNER_REGIONS.items():
            self.create_entrance(regions[outer], regions[inner])

    def location_rule(self, row) -> Rule:
        """A location's rule: its requirements, and with tower_maps on region_keys,
        its maps (map_keys; a tower's with towers_need_maps), or Universal Tracker's
        stand-in for a missing map. With region_lock, its region's entrances hold its
        map, and a quest through another region needs to reach that region."""
        rule = self.rule(self.needs(row))
        maps = map_keys(row, bool(self.options.towers_need_maps)) \
            if self.options.tower_maps == TowerMaps.option_region_keys else ()
        parts = [] if isinstance(rule, True_) else [rule]
        if self.options.region_lock:
            parts += [CanReachRegion(self.MAP_REGIONS[name]) for name in maps if name != MAPS.get(row["region"])]
        elif maps:
            parts.append(Or(Has(maps[0]) if len(maps) == 1 else HasAll(*maps), Has(self.glitches_item_name)))
        return And(*parts) if len(parts) > 1 else parts[0] if parts else rule

    def needs(self, row) -> tuple:
        """A location's requirements(); with spirit_orbs on vanilla_statues, its
        heart containers are the Spirit Orbs the statues trade for them."""
        groups = requirements(row)
        if self.options.spirit_orbs != SpiritOrbs.option_vanilla_statues:
            return groups
        return tuple((("Spirit Orb",), count * ORBS_PER_TRADE) if names == ("Heart Container",) else (names, count)
                     for names, count in groups)

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
        parts = [self.rule(self.needs(next(r for r in LOCATIONS if r["name"] == GOAL_LOCATION)))]
        if needed:
            parts.append(HasAll(*needed))
        if options.sanctum_divine_beasts.value:
            parts.append(HasFromList(*beasts, count=options.sanctum_divine_beasts.value))
        if options.sanctum_shrines.value:
            parts.append(HasFromList(*shrines, count=options.sanctum_shrines.value))
        self.set_rule(ganon, And(*parts) if len(parts) > 1 else parts[0])
        if options.weapon_order != WeaponOrder.option_anywhere:
            # The strongest weapon is never among the first: no location of this world's Great Plateau
            # takes this world's Master Sword, which the fill and the moves after it respect. Another
            # player's plateau may: ruling it out too fails a fill with several of them now and then.
            for location in self.get_region("Great Plateau").locations:
                forbid_item(location, "Master Sword", player)
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
        # A rule names the Master Sword only when the sanctum or a side quest (My
        # Hero) asks for it, a map when the maps are region keys. A side quest
        # counts excluded too: every location must be reachable.
        needed = (name == "Master Sword" and self.options.sanctum_master_sword
                  or name in SIDE_QUEST_ITEMS and self.options.side_quest_sanity
                  or name in MAPS.values() and self.options.tower_maps == TowerMaps.option_region_keys)
        if name == "Spirit Orb" and self.options.spirit_orbs != SpiritOrbs.option_containers:
            # Many, and only their number counts.
            return BotwItem(name, ItemClassification.progression_skip_balancing, row["id"], self.player)
        classification = (ItemClassification.progression if row.get("progression") or needed else
                          ItemClassification.useful if row.get("useful") else
                          ItemClassification.trap if row.get("trap") else ItemClassification.filler)
        return BotwItem(name, classification, row["id"], self.player)

    def get_filler_item_name(self) -> str:
        """Arrows, elixirs, weapons, gems or rupees, drawn by FILLER's weights; with extra_filler,
        materials and food too, by EXTRA_FILLER's."""
        families = list((EXTRA_FILLER if self.options.extra_filler else FILLER).values())
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
        """The maps of the pool: all 14 (tower_maps on items or region_keys) or
        none. With early_map, one of them is placed among the locations
        reachable from the start, the Great Plateau's (local_early_items)."""
        if self.options.tower_maps == TowerMaps.option_vanilla:
            return []
        choice = self.options.early_map
        if choice != EarlyMap.option_none:
            regions = GENTLE_REGIONS if choice == EarlyMap.option_gentle else sorted(MAPS)
            if self.options.region_lock and not self.options.map_travel_points:
                # Only the map of a region bordering the Plateau opens one from the start.
                regions = [region for region in regions if region in NEIGHBOURS["Great Plateau"]]
            self.multiworld.local_early_items[self.player][MAPS[self.random.choice(regions)]] = 1
        return list(MAPS.values())

    def create_items(self) -> None:
        # korok_local_filler: that share of the Koroks hold filler of this world.
        local = [] if self.regenerated else self.random.sample(
            self.koroks, len(self.koroks) * self.options.korok_local_filler.value // 100)
        for row in local:
            self.get_location(row["name"]).place_locked_item(self.create_item(self.get_filler_item_name()))
        counts = {row["name"]: int(row.get("count", 1)) for row in ITEMS
                  if not row.get("trap") and not row.get("bonus") and row["name"] not in MAPS.values()}
        # progressive_horse: four Progressive Horses, the last two Epona and the Master Cycle Zero.
        for name in (("Epona", "Master Cycle Zero") if self.options.progressive_horse else ("Progressive Horse",)):
            del counts[name]
        if self.options.spirit_orbs == SpiritOrbs.option_vanilla_statues:
            # The statues give the hearts and the stamina, for the orbs in their place.
            counts["Spirit Orb"] += ORBS_PER_TRADE * (counts.pop("Heart Container") + counts.pop("Stamina Vessel"))
        elif self.options.spirit_orbs == SpiritOrbs.option_statue_checks:
            # Four orbs per offering, which gives nothing more: none is left over.
            counts["Spirit Orb"] = ORBS_PER_TRADE * len(self.offerings)
        pool = [self.create_item(name) for name, count in counts.items() for _ in range(count)]
        pool += [self.create_item(name) for name in self.maps()]
        # Main.py applies start_inventory_from_pool centrally after create_items.
        capacity = len(self.multiworld.get_unfilled_locations(self.player))
        # The locations that hold neither progression nor useful items: a Korok, a chest, a quest.
        excluded = sum(1 for loc in self.multiworld.get_unfilled_locations(self.player)
                       if loc.progress_type == LocationProgressType.EXCLUDED)
        if self.options.spirit_orbs == SpiritOrbs.option_statue_checks and not self.regenerated:
            # Every orb is progression, which no excluded location holds.
            short = max(len(pool) - capacity,
                        sum(1 for item in pool if item.advancement or item.useful) - (capacity - excluded))
            if short > 0:
                raise OptionError(f"{self.player_name}: statue_offerings at {len(self.offerings)} needs {short} "
                                  "more locations that may hold progression: lower it, or turn on "
                                  "korok_progression, chest_progression, quest_progression or boss_progression")
        if len(pool) > capacity:
            if self.options.spirit_orbs == SpiritOrbs.option_vanilla_statues:
                raise OptionError(f"{self.player_name}: spirit_orbs on vanilla_statues needs "
                                  f"{len(pool) - capacity} more locations: turn on chest_sanity, or korok_sanity "
                                  "with a lower korok_local_filler")
            raise ValueError("BOTW item pool exceeds available locations")
        if self.options.spirit_orbs == SpiritOrbs.option_vanilla_statues:
            # The logic counts the orbs of the Master Sword's hearts; the others are filler, which a
            # Korok or a chest that holds nothing needed may hold too.
            for item in [item for item in pool if item.name == "Spirit Orb"][ORBS_PER_TRADE * HEARTS_NEEDED:]:
                item.classification = ItemClassification.filler
        # Traps as many as without the chests, the Koroks, the quests and the bosses, which would bring
        # hundreds more.
        extra = (len(CHESTS) if self.options.chest_sanity else 0) + len(self.koroks) - len(local) \
            + len(self.quests) + len(self.bosses)
        filler = capacity - len(pool)
        pool.extend(self.create_item(name) for name in self.trap_names(max(0, filler - extra)))
        drawn = [self.create_item(self.get_filler_item_name()) for _ in range(capacity - len(pool))]
        # bonus_items: that share of the filler becomes bonus items, in the place of drawn filler that
        # is not useful (traps keep their count), and no more than the locations left that may hold a
        # useful item.
        plain = [item for item in drawn if not (item.advancement or item.useful)]
        # The player's exclude_locations hold none either: Archipelago marks them after create_items.
        chosen = sum(1 for loc in self.multiworld.get_unfilled_locations(self.player)
                     if loc.progress_type != LocationProgressType.EXCLUDED
                     and loc.name in self.options.exclude_locations.value)
        room = capacity - excluded - chosen - sum(1 for item in pool + drawn if item.advancement or item.useful)
        bonus = [row["name"] for row in ITEMS if row.get("bonus")]
        count = min(len(bonus), filler * self.options.bonus_items.value // 100, len(plain), room)
        if count > 0:
            drawn = [item for item in drawn if item.advancement or item.useful] + plain[count:] \
                + [self.create_item(name) for name in self.random.sample(bonus, count)]
        pool.extend(drawn)
        self.multiworld.itempool.extend(pool)

    @classmethod
    def stage_finalize_multiworld(cls, multiworld: MultiWorld) -> None:
        """Once the fill and the progression balancing are done: chest_progression's
        buried chests (bury_late), then weapon_order, as Dark Souls III smooths its
        weapons: the spheres of the whole multiworld, then each world's weapons
        dealt again over their own locations. No rule names a weapon, so the
        spheres do not change."""
        burying = [world for world in multiworld.get_game_worlds(cls.game) if world.options.chest_progression]
        if burying:
            spheres = cls.spheres(multiworld)
            for world in burying:
                world.bury_late(spheres)
        worlds = [world for world in multiworld.get_game_worlds(cls.game)
                  if world.options.weapon_order != WeaponOrder.option_anywhere]
        if not worlds:
            return
        spheres = cls.spheres(multiworld)       # again: bury_late brings items earlier
        for world in worlds:
            world.order_weapons(spheres)

    @staticmethod
    def spheres(multiworld: MultiWorld) -> list[list[Location]]:
        """The multiworld's spheres, each sorted."""
        out = []
        for sphere in multiworld.get_spheres():
            if not sphere:
                break           # what follows is unreachable: left as the fill put it
            out.append(sorted(sphere))
        return out

    def bury_late(self, spheres: list[list[Location]]) -> None:
        """chest_progression: a buried chest is found by chance, so nothing the
        first half of this world's game asks for is in one: the first half of the
        spheres up to the last that holds one of its locations (in a multiworld,
        another game may go on longer). Such a chest of this world
        trades its progression item for the item of one of this world's locations
        reached in its sphere or before and holding no progression: the item is
        found no later, and an item that is not progression opens nothing, so
        every location stays reachable. A chest with no such partner, or that the
        player made a priority location, keeps its item."""
        buried = {row["name"] for row in CHESTS if row["kind"] == "Buried"}
        state = self.multiworld.state
        partners: list[Location] = []
        last = max(index for index, sphere in enumerate(spheres)
                   if any(location.player == self.player for location in sphere))
        for sphere in spheres[:(last + 1) // 2]:
            mine = [location for location in sphere if location.player == self.player
                    and not location.locked and location.address is not None]
            partners += [location for location in mine
                         if location.name not in buried and not location.item.advancement]
            for chest in mine:
                if chest.name not in buried or not chest.item.advancement                         or chest.progress_type == LocationProgressType.PRIORITY:
                    continue
                fits = [location for location in partners
                        if location.can_fill(state, chest.item, check_access=False)
                        and chest.can_fill(state, location.item, check_access=False)]
                if fits:
                    partner = self.random.choice(fits)
                    partners.remove(partner)
                    item = chest.item
                    self.multiworld.push_item(chest, partner.item, collect=False)
                    self.multiworld.push_item(partner, item, collect=False)

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
        # The excluded locations (chest_sanity's chests, korok_sanity's Koroks, the quests and the bosses,
        # but those the *_progression options open) take no useful weapon:
        # their weapons are ordered among them, the others' among the others.
        for excluded in (False, True):
            self._order_weapons_in([location for location in locations
                                    if (location.progress_type == LocationProgressType.EXCLUDED) == excluded])

    def _order_weapons_in(self, locations: list[Location]) -> None:
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
        # 11: the Downpour, Yiga Ambush and Paranoia traps, which one of 10 cannot play.
        # 12: map_travel_points, the travel points a map opens, which one of 11 cannot open.
        # 13: chest_sanity, the chests as locations, which one of 12 neither sees opened nor, with
        #     ap_items, empties: only the seeds with chest_sanity ask for it.
        # 14: korok_sanity, the Koroks as locations, which one of 13 does not see found.
        # 15: side_quest_sanity or shrine_quest_sanity, the quests as locations, which one of 14
        #     does not see finished.
        # 16: spirit_orbs on statue_checks, the statues' offerings as locations, which one of 15
        #     does not see made.
        # 17: boss_sanity, the field bosses as locations, which one of 16 does not see defeated.
        # 18: progressive_horse, the Progressive Horse, which one of 17 cannot give.
        # 19: bonus_items; 20: extra_filler; 21: the elemental traps, which one of 20 cannot play.
        # World schema 7: the Koroks among the locations; 8: then the quests; 9: then the offerings;
        # 10: then the bosses.
        # stall_locations: the stalls drawn by the seed, for Universal Tracker.
        # korok_locations: with korok_sanity, the Koroks drawn by the seed, for Universal Tracker.
        # region_borders: with region_lock, the borders the seed's logic crosses.
        # travel_shrines: with map_travel_points, the shrine each map opens and its terminal's flag.
        elemental = self.options.trap_percentage.value and any(
            self.options.trap_weights.value.get(name, 0) for name in ELEMENTAL_TRAPS)
        client = 21 if elemental else 20 if self.options.extra_filler else 19 if self.options.bonus_items \
            else 18 if self.options.progressive_horse \
            else 17 if self.bosses else 16 if self.offerings \
            else 15 if self.quests else 14 if self.options.korok_sanity else 13 if self.options.chest_sanity \
            else 12
        return {"client_schema": client, "world_schema": 10,
                "world_version": WORLD_VERSION,
                "death_link": bool(self.options.death_link.value),
                **self.options.as_dict(*self.SLOT_OPTIONS),
                "stall_locations": sorted(location_id for location_id in self.shop_prices
                                          if location_id in self.STALL_IDS),
                **({"region_borders": [list(pair) for pair in OPEN_BORDERS]} if self.options.region_lock else {}),
                **({"travel_shrines": self.travel_shrines()} if self.options.map_travel_points else {}),
                **({"korok_locations": [row["id"] for row in self.koroks]} if self.options.korok_sanity else {})}

    @staticmethod
    def travel_shrines() -> dict[str, list[str]]:
        """{map: [shrine, terminal]}: the shrine whose travel point each map opens,
        by its GameData name (DungeonNNN), and the flag its terminal sets."""
        flags = {row["name"]: row["gamedata_flag"] for row in LOCATIONS}
        return {MAPS[region]: [flags[shrine].removeprefix("Clear_"), TRAVEL_TERMINALS[shrine]]
                for region, shrine in sorted(TRAVEL_SHRINES.items())}

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
        for row in [*LOCATIONS, *(CHESTS if self.options.chest_sanity else ())]:
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
