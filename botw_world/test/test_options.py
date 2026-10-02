from . import BotwTestBase


class TestWithoutShops(BotwTestBase):
    def test_no_shop_or_stall_location_by_default(self) -> None:
        names = {location.name for location in self.multiworld.get_locations(self.player)}
        self.assertFalse(names & self.world.location_name_groups["Beedle Shops"])
        self.assertFalse(names & self.world.location_name_groups["Stalls"])


class TestWithShops(BotwTestBase):
    options = {"beedle_shop_items": 2, "stall_shop_items": 2}

    def test_every_shop_and_stall_location_exists_and_has_a_price(self) -> None:
        names = {location.name for location in self.multiworld.get_locations(self.player)}
        shops = self.world.location_name_groups["Beedle Shops"] | self.world.location_name_groups["Stalls"]
        self.assertEqual(len(shops), 60)
        self.assertLessEqual(shops, names)
        self.assertEqual(len(self.world.shop_prices), 60)
        self.assertTrue(all(20 <= price <= 200 and price % 5 == 0 for price in self.world.shop_prices.values()))


class TestOneItemPerShop(BotwTestBase):
    options = {"beedle_shop_items": 1, "stall_shop_items": 1}

    def test_half_of_the_shop_locations(self) -> None:
        self.assertEqual(len(self.world.shop_prices), 30)


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
        self.assertEqual(pool.count("Rupee Bundle"), 0)
        traps = [item for item in self.multiworld.itempool if item.trap]
        self.assertEqual(len(traps), 41)
        self.assertEqual({item.name for item in traps}, {
            "Weapon Shatter", "Blood Moon", "Rupoor", "Hearts Down", "Strip Down",
            "Cucco Swarm"})
        self.assertEqual(len(pool), 152)


class TestOneTrapOnly(BotwTestBase):
    options = {"trap_percentage": 50, "trap_weights": {"Rupoor": 3, "Blood Moon": 0}}

    def test_only_the_weighted_trap_comes_up(self) -> None:
        names = [item.name for item in self.multiworld.itempool if item.trap]
        self.assertEqual(set(names), {"Rupoor"})
        self.assertEqual(len(names), round(41 * 50 / 100))
        self.assertEqual([item.name for item in self.multiworld.itempool].count("Rupee Bundle"),
                         41 - len(names))


class TestDivineBeastGoal(BotwTestBase):
    options = {"goal_type": "divine_beasts", "divine_beasts_required": 4}


class TestShrineGoal(BotwTestBase):
    options = {"goal_type": "shrines", "shrines_required": 120}
