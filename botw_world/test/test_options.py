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


class TestDivineBeastGoal(BotwTestBase):
    options = {"goal_type": "divine_beasts", "divine_beasts_required": 4}


class TestShrineGoal(BotwTestBase):
    options = {"goal_type": "shrines", "shrines_required": 120}
