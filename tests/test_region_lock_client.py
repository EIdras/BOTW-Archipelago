"""The regions Link may enter with region_lock, read from the game's flags."""
import random
import unittest

from botw_client import region_lock as lock
from botw_client.items import load_item_map
from tools import build_poptracker as poptracker

CATALOG = poptracker.catalog()
MAPS = lock.map_flags(load_item_map())


def slot(**options):
    return {"region_lock": 1, "region_borders": [list(pair) for pair in CATALOG.OPEN_BORDERS], **options}


def flags(regions=(), paraglider=True, unreadable=()):
    values = {lock.PARAGLIDER: paraglider, **{MAPS[region]: True for region in regions}}
    return lambda flag, kind: None if flag in unreadable else values.get(flag, False)


class ReachedTests(unittest.TestCase):
    def test_each_map_names_a_region_of_the_borders(self):
        self.assertEqual(set(MAPS), {name for pair in CATALOG.OPEN_BORDERS for name in pair} - {lock.PLATEAU})

    def test_nothing_is_closed_without_region_lock(self):
        self.assertIsNone(lock.reached({}, flags(), MAPS))

    def test_the_plateau_alone_before_the_paraglider(self):
        self.assertEqual(lock.reached(slot(), flags(["Dueling Peaks"], paraglider=False), MAPS), {lock.PLATEAU})

    def test_a_region_opens_from_a_reached_neighbour(self):
        reached = lock.reached(slot(), flags(["Dueling Peaks", "Akkala"]), MAPS)
        self.assertIn("Dueling Peaks", reached)
        # Akkala borders neither the Plateau nor Dueling Peaks.
        self.assertNotIn("Akkala", reached)

    def test_a_travel_point_opens_a_region_with_its_map_alone(self):
        self.assertIn("Akkala", lock.reached(slot(map_travel_points=1), flags(["Akkala"]), MAPS))

    def test_hyrule_castle_with_central(self):
        self.assertIn("Hyrule Castle", lock.reached(slot(), flags(["Central"]), MAPS))
        self.assertNotIn("Hyrule Castle", lock.reached(slot(), flags(), MAPS))

    def test_an_unreadable_flag_closes_nothing(self):
        self.assertIsNone(lock.reached(slot(), flags(unreadable=[lock.PARAGLIDER]), MAPS))
        self.assertIsNone(lock.reached(slot(), flags(unreadable=[MAPS["Lake"]]), MAPS))

    def test_the_world_reaches_the_same_regions(self):
        # The world's graph (botw_world/catalog.py NEIGHBOURS): from the Plateau
        # with the Paraglider, a neighbour whose map is held; with travel, any.
        rng = random.Random(0)
        for _ in range(300):
            held = {region for region in MAPS if rng.random() < 0.4}
            travel = rng.random() < 0.5
            expected, todo = {lock.PLATEAU}, [lock.PLATEAU]
            while todo:
                here = todo.pop()
                others = set(MAPS) if travel and here == lock.PLATEAU else CATALOG.NEIGHBOURS[here]
                for there in sorted(others & held - expected):
                    expected.add(there)
                    todo.append(there)
            expected |= {inner for inner, outer in CATALOG.INNER_REGIONS.items() if outer in expected}
            with self.subTest(held=sorted(held), travel=travel):
                self.assertEqual(lock.reached(slot(map_travel_points=int(travel)), flags(held), MAPS), expected)


if __name__ == "__main__":
    unittest.main()
