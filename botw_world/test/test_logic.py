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


class TestClimates(BotwTestBase):
    def reach_with(self, location: str, *names: str) -> bool:
        self.collect_by_name(["Paraglider", *RUNES, *names])
        return self.can_reach_location(location)

    def test_death_mountain_needs_the_flamebreaker_armour(self) -> None:
        self.assertEqual(LOGIC["Tah Muhl Shrine"]["climate"], "heat")
        self.assertFalse(self.reach_with("Tah Muhl Shrine"))
        self.collect_by_name("Flamebreaker Set")
        self.assertTrue(self.can_reach_location("Tah Muhl Shrine"))

    def test_the_desert_needs_the_desert_voe_set(self) -> None:
        self.assertFalse(self.reach_with("Jee Noh Shrine", "Warm Doublet", "Snowquill Set"))
        self.collect_by_name("Desert Voe Set")
        self.assertTrue(self.can_reach_location("Jee Noh Shrine"))

    def test_hebra_needs_the_snowquill_set_and_a_milder_cold_either_armour(self) -> None:
        self.assertFalse(self.reach_with("Hebra Tower", "Warm Doublet"))
        self.assertTrue(self.can_reach_location("Gerudo Tower"))        # cold: the doublet is enough
        self.collect_by_name("Snowquill Set")
        self.assertTrue(self.can_reach_location("Hebra Tower"))

    def test_vah_ruta_needs_the_zora_armour(self) -> None:
        self.assertFalse(self.reach_with("Divine Beast Vah Ruta"))
        self.collect_by_name("Zora Set")
        self.assertTrue(self.can_reach_location("Divine Beast Vah Ruta"))


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
