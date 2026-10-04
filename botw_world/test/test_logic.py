from . import BotwTestBase
from ..catalog import CLIMATES, ITEMS, LOCATIONS, LOGIC, PLATEAU_RUNES, RUNES, required_items

TERMINALS = ("Magnesis Terminal", "Remote Bombs Terminal", "Stasis Terminal", "Cryonis Terminal")


class TestGreatPlateau(BotwTestBase):
    def test_terminals_need_nothing(self) -> None:
        for terminal in TERMINALS:
            self.assertTrue(self.can_reach_location(terminal), terminal)

    def test_each_plateau_shrine_needs_its_rune(self) -> None:
        for shrine, rune in PLATEAU_RUNES.items():
            self.assertFalse(self.can_reach_location(shrine), shrine)
            self.collect_by_name(rune)
            self.assertTrue(self.can_reach_location(shrine), shrine)

    def test_leaving_the_plateau_needs_the_paraglider(self) -> None:
        self.collect_by_name(list(RUNES))
        self.assertFalse(self.can_reach_region("Hateno"))
        self.collect_by_name("Paraglider")
        self.assertTrue(self.can_reach_region("Hateno"))


class TestShrinesOutsideThePlateau(BotwTestBase):
    def test_a_temperate_shrine_needs_the_paraglider_and_its_runes(self) -> None:
        self.assertEqual(LOGIC["Kam Urog Shrine"]["climate"], "none")
        self.assertAccessDependency(["Kam Urog Shrine"], [["Paraglider", *RUNES]], only_check_listed=True)


class TestEitherWay(BotwTestBase):
    def test_either_rune_opens_a_shrine_with_two_ways(self) -> None:
        self.assertEqual(LOGIC["Maka Rah Shrine"]["runes"], "Magnesis/Stasis")
        self.assertAccessDependency(["Maka Rah Shrine"], [["Magnesis", "Stasis"]], only_check_listed=True)


class TestWhatTheGameBlocks(BotwTestBase):
    def reach_with(self, location: str, *names: str) -> bool:
        self.collect_by_name(["Paraglider", *RUNES, *names])
        return self.can_reach_location(location)

    def test_the_volcanos_heart_needs_the_flamebreaker_armour(self) -> None:
        self.assertEqual(LOGIC["Divine Beast Vah Rudania"]["climate"], "heat")
        self.assertFalse(self.reach_with("Divine Beast Vah Rudania"))
        self.collect_by_name("Flamebreaker Set")
        self.assertTrue(self.can_reach_location("Divine Beast Vah Rudania"))

    def test_the_canyon_around_goron_city_burns_too(self) -> None:
        # The game's climate map: Shora Hah's isle burns, Foothill Stable's slopes do not.
        self.assertFalse(self.reach_with("Shora Hah Shrine"))
        for location in ("Tah Muhl Shrine", "Sah Dahaj Shrine", "Eldin Tower"):
            self.assertTrue(self.can_reach_location(location), location)
        self.collect_by_name("Flamebreaker Set")
        self.assertTrue(self.can_reach_location("Shora Hah Shrine"))

    def test_cold_and_desert_heat_ask_for_no_armour(self) -> None:
        self.assertTrue(self.reach_with("Hebra Tower"))
        self.assertTrue(self.can_reach_location("Jee Noh Shrine"))

    def test_vah_ruta_needs_the_zora_armour_up_the_waterfalls(self) -> None:
        self.assertFalse(self.reach_with("Divine Beast Vah Ruta"))
        self.collect_by_name("Zora Set")
        self.assertTrue(self.can_reach_location("Divine Beast Vah Ruta"))


class TestGerudoTown(BotwTestBase):
    options = {"stall_items": 28}

    def test_the_guards_and_vah_naboris_need_the_gerudo_outfit(self) -> None:
        self.collect_by_name(["Paraglider", *RUNES])
        for location in ("Gerudo Town - Fruit Stall Item 1", "Divine Beast Vah Naboris"):
            self.assertFalse(self.can_reach_location(location), location)
        self.collect_by_name("Gerudo Set")
        for location in ("Gerudo Town - Fruit Stall Item 1", "Divine Beast Vah Naboris"):
            self.assertTrue(self.can_reach_location(location), location)
        self.assertTrue(self.can_reach_location("Kara Kara Bazaar - Fruit Stall Item 1"))     # outside the walls

    def test_a_shrine_quest_given_in_the_town_needs_the_gerudo_outfit(self) -> None:
        self.collect_by_name(["Paraglider", *RUNES])
        self.assertFalse(self.can_reach_location("Misae Suma Shrine"))
        self.collect_by_name("Gerudo Set")
        self.assertTrue(self.can_reach_location("Misae Suma Shrine"))


class TestTarreyTown(BotwTestBase):
    options = {"stall_items": 28}

    def test_its_arrow_stall_comes_through_the_southern_mine(self) -> None:
        self.collect_by_name(["Paraglider", *RUNES])
        self.assertFalse(self.can_reach_location("Tarrey Town - Arrow Stall Item 1"))
        self.collect_by_name("Flamebreaker Set")
        self.assertTrue(self.can_reach_location("Tarrey Town - Arrow Stall Item 1"))


class TestClassification(BotwTestBase):
    def test_progression_items_are_exactly_those_the_logic_names(self) -> None:
        # Archipelago's rule (docs/world api.md): an item a rule names must be
        # progression; and one no rule names is not, or balancing hurries it early.
        named = set().union(*(required_items(row) for row in LOCATIONS))
        progression = {row["name"] for row in ITEMS if row.get("progression")}
        self.assertEqual(progression, {name for name in named if not name.startswith("Freed - ")})

    def test_every_climate_is_armour_of_the_pool(self) -> None:
        names = {row["name"] for row in ITEMS}
        for groups in CLIMATES.values():
            for group in groups:
                self.assertLessEqual(set(group), names)


class TestMasterSword(BotwTestBase):
    def test_the_master_sword_needs_ten_heart_containers(self) -> None:
        self.collect_by_name("Paraglider")
        hearts = self.get_items_by_name("Heart Container")
        self.collect(hearts[:9])
        self.assertFalse(self.can_reach_location("Master Sword Pedestal"))
        self.collect(hearts[9])
        self.assertTrue(self.can_reach_location("Master Sword Pedestal"))


class TestSanctumByDefault(BotwTestBase):
    def test_ganon_waits_for_the_four_runes(self) -> None:
        self.collect_by_name("Paraglider")
        self.assertFalse(self.can_reach_location("Defeat Calamity Ganon"))
        self.collect_by_name(list(RUNES))
        self.assertTrue(self.can_reach_location("Defeat Calamity Ganon"))
        self.assertFalse(self.get_item_by_name("Master Sword").advancement)


class TestSanctumOpen(BotwTestBase):
    options = {"ganon_runes": False}

    def test_ganon_is_there_as_soon_as_link_leaves_the_plateau(self) -> None:
        self.collect_by_name("Paraglider")
        self.assertTrue(self.can_reach_location("Defeat Calamity Ganon"))


class TestSanctumMasterSword(BotwTestBase):
    options = {"ganon_master_sword": True, "ganon_runes": False}

    def test_the_master_sword_becomes_a_key_item(self) -> None:
        self.assertTrue(self.get_item_by_name("Master Sword").advancement)
        self.collect_by_name("Paraglider")
        self.assertFalse(self.can_reach_location("Defeat Calamity Ganon"))
        self.collect_by_name("Master Sword")
        self.assertTrue(self.can_reach_location("Defeat Calamity Ganon"))


class TestPresets(BotwTestBase):
    def test_every_preset_sets_options_of_the_world(self) -> None:
        from ..options import PRESETS, BotwOptions
        for name, preset in PRESETS.items():
            for option, value in preset.items():
                with self.subTest(preset=name, option=option):
                    BotwOptions.type_hints[option].from_any(value)
