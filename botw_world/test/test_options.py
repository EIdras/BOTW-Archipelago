from BaseClasses import ItemClassification

from . import BotwTestBase
from ..catalog import FILLER, WEAPONS

# The filler of the default options: 152 locations, 112 declared items, 14 maps.
FILLER_SLOTS = 26


class TestWithoutShops(BotwTestBase):
    def test_no_shop_or_stall_location_by_default(self) -> None:
        names = {location.name for location in self.multiworld.get_locations(self.player)}
        self.assertFalse(names & self.world.location_name_groups["Beedle Shops"])
        self.assertFalse(names & self.world.location_name_groups["Stalls"])


class TestWithShops(BotwTestBase):
    options = {"beedle_shop_items": 2, "stall_items": 28}

    def test_every_shop_and_stall_location_exists_and_has_a_price(self) -> None:
        names = {location.name for location in self.multiworld.get_locations(self.player)}
        shops = self.world.location_name_groups["Beedle Shops"] | self.world.location_name_groups["Stalls"]
        self.assertEqual(len(shops), 60)
        self.assertLessEqual(shops, names)
        self.assertEqual(len(self.world.shop_prices), 60)
        self.assertTrue(all(20 <= price <= 200 and price % 5 == 0 for price in self.world.shop_prices.values()))


class TestOneItemPerShop(BotwTestBase):
    options = {"beedle_shop_items": 1}

    def test_half_of_beedles_shop_locations(self) -> None:
        self.assertEqual(len(self.world.shop_prices), 16)


class TestSomeStallItems(BotwTestBase):
    options = {"stall_items": 9}

    def test_the_stall_items_are_spread_two_at_most_on_a_stall(self) -> None:
        stalls = self.world.location_name_groups["Stalls"]
        names = {location.name for location in self.multiworld.get_locations(self.player)} & stalls
        self.assertEqual(len(names), 9)
        self.assertEqual(len(self.world.shop_prices), 9)
        per_stall = {}
        for name in names:
            stall = name.rsplit(" Item ", 1)[0]
            per_stall[stall] = per_stall.get(stall, 0) + 1
        self.assertLessEqual(max(per_stall.values()), 2)


class TestDeathLink(BotwTestBase):
    options = {"death_link": True}

    def test_slot_data_carries_death_link(self) -> None:
        self.assertIs(self.world.fill_slot_data()["death_link"], True)


class TestDeathLinkOffByDefault(BotwTestBase):
    def test_slot_data_carries_death_link(self) -> None:
        self.assertIs(self.world.fill_slot_data()["death_link"], False)


class TestNoTrapsByDefault(BotwTestBase):
    def test_the_pool_has_no_trap(self) -> None:
        self.assertEqual([item.name for item in self.multiworld.itempool if item.trap], [])


class TestEveryFillerATrap(BotwTestBase):
    options = {"trap_percentage": 100}

    def test_the_filler_becomes_traps_of_the_default_weights(self) -> None:
        pool = [item.name for item in self.multiworld.itempool]
        self.assertFalse(set(pool) & {name for _, items in FILLER.values() for name in items})
        traps = [item for item in self.multiworld.itempool if item.trap]
        self.assertEqual(len(traps), FILLER_SLOTS)
        # Drawn at random, of equal weights: every kind may not come up in 26
        # draws, but nearly always four of them.
        names = {item.name for item in traps}
        self.assertLessEqual(names, {"Weapon Shatter", "Blood Moon", "Rupoor", "Hearts Down", "Strip Down",
                                     "Cucco Swarm", "Downpour", "Yiga Ambush", "Paranoia"})
        self.assertGreaterEqual(len(names), 4)
        self.assertEqual(len(pool), 152)


class TestFiller(BotwTestBase):
    def test_the_filler_is_drawn_from_every_family(self) -> None:
        fillers = {name: family for family, (_, items) in FILLER.items() for name in items}
        drawn = [item for item in self.multiworld.itempool if item.name in fillers]
        self.assertEqual(len(drawn), FILLER_SLOTS)
        # Filler, but for the amiibo's weapons: useful.
        treasures = set(WEAPONS["treasure"][2])
        self.assertTrue(all(item.classification == (ItemClassification.useful if item.name in treasures
                                                    else ItemClassification.filler) for item in drawn))
        # 2000 draws: every family and every weapon group, near their weights.
        names = [self.world.get_filler_item_name() for _ in range(2000)]
        for family, (weight, _items) in FILLER.items():
            share = sum(fillers[name] == family for name in names) / len(names)
            self.assertAlmostEqual(share, weight / 100, delta=0.04, msg=family)
        groups = sum(weight for weight, _level, _weapons in WEAPONS.values())
        for group, (weight, _level, weapons) in WEAPONS.items():
            share = sum(name in weapons for name in names) / len(names)
            self.assertAlmostEqual(share, FILLER["weapons"][0] / 100 * weight / groups, delta=0.02, msg=group)


class TestOneTrapOnly(BotwTestBase):
    options = {"trap_percentage": 50, "trap_weights": {"Rupoor": 3, "Blood Moon": 0}}

    def test_only_the_weighted_trap_comes_up(self) -> None:
        names = [item.name for item in self.multiworld.itempool if item.trap]
        self.assertEqual(set(names), {"Rupoor"})
        self.assertEqual(len(names), round(FILLER_SLOTS * 50 / 100))
        fillers = {name for _, items in FILLER.values() for name in items}
        self.assertEqual(len([item for item in self.multiworld.itempool if item.name in fillers]),
                         FILLER_SLOTS - len(names))


class TestDivineBeastGoal(BotwTestBase):
    options = {"goal": "divine_beasts"}


class TestShrineGoal(BotwTestBase):
    options = {"goal": "shrines", "goal_shrines": 120}
