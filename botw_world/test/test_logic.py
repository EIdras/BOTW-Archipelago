from . import BotwTestBase
from ..catalog import PLATEAU_RUNES, RUNES

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
    def test_a_shrine_needs_the_paraglider_and_every_rune(self) -> None:
        self.assertAccessDependency(["Tah Muhl Shrine"], [["Paraglider", *RUNES]], only_check_listed=True)


class TestMasterSword(BotwTestBase):
    def test_the_master_sword_needs_ten_heart_containers(self) -> None:
        self.collect_by_name("Paraglider")
        hearts = self.get_items_by_name("Heart Container")
        self.collect(hearts[:9])
        self.assertFalse(self.can_reach_location("Master Sword Pedestal"))
        self.collect(hearts[9])
        self.assertTrue(self.can_reach_location("Master Sword Pedestal"))
