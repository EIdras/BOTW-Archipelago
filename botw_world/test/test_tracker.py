"""Universal Tracker: the rules say what is missing, and the world comes back
the same from its slot data (interpret_slot_data, generate_early)."""
import random
import unittest

from BaseClasses import CollectionState
from test.general import gen_steps, setup_multiworld
from worlds.AutoWorld import call_all

from .. import BotwWorld
from ..catalog import GOAL_LOCATION, LOCATIONS, categories, map_keys, requirements

# Options other than the defaults: a shrine goal, every sanctum requirement,
# Beedle's shops and stalls.
OPTIONS = {"goal": "shrines", "goal_shrines": 30, "sanctum_divine_beasts": 3, "sanctum_shrines": 20,
           "sanctum_master_sword": True, "sanctum_runes": True, "beedle_shop_items": 2,
           "stall_items": 11}


def generate(options=None, passthrough=None, seed=1):
    """A solo world through pre_fill, as Universal Tracker regenerates one when
    `passthrough` (what interpret_slot_data returned) is given."""
    multiworld = setup_multiworld(BotwWorld, (), seed, options or {})
    if passthrough is not None:
        multiworld.re_gen_passthrough = {BotwWorld.game: passthrough}
    for step in gen_steps:
        call_all(multiworld, step)
    return multiworld


def states(multiworld, count, seed=0):
    """Random states over the progression items and the events."""
    pick = random.Random(seed)
    items = [item for item in multiworld.itempool if item.advancement]
    items += [loc.item for loc in multiworld.get_locations() if loc.address is None and loc.item]
    items += multiworld.precollected_items[1]
    world = multiworld.worlds[1]
    items.append(world.create_item(world.glitches_item_name))       # Universal Tracker's only
    for _ in range(count):
        state = CollectionState(multiworld)
        share = pick.random()
        for item in items:
            if pick.random() < share:
                state.collect(item, True)
        yield state


def plain(row, state, player, keys=True):
    """The rule as requirements() says it: every group met by one of its names;
    with the maps as region keys (keys), every map of map_keys(), or the stand-in
    Universal Tracker gives itself."""
    maps = map_keys(row) if keys else ()
    return (all(any(state.has(name, player, count) for name in names) for names, count in requirements(row))
            and (all(state.has(name, player) for name in maps) or state.has("Region Without Its Map", player)))


class TestRulesAreTheLogic(unittest.TestCase):
    def test_every_location_and_event_asks_what_its_requirements_say(self):
        for options in ({}, OPTIONS, {**OPTIONS, "tower_maps": "items"}):
            multiworld = generate(options)
            keys = options.get("tower_maps", "region_keys") == "region_keys"
            rows = {row["name"]: row for row in LOCATIONS}
            spots = []
            for loc in multiworld.get_locations():
                name = loc.name.split(" - ", 1)[1] if loc.address is None and " - " in loc.name else loc.name
                if name != GOAL_LOCATION:
                    spots.append((loc, rows[name]))
            for state in states(multiworld, 150):
                for loc, row in spots:
                    self.assertEqual(loc.access_rule(state), plain(row, state, 1, keys), loc.name)

    def test_the_sanctum_and_the_goal_ask_what_the_options_say(self):
        multiworld = generate(OPTIONS)
        ganon = multiworld.get_location(GOAL_LOCATION, 1)
        goal_row = next(row for row in LOCATIONS if row["name"] == GOAL_LOCATION)
        beasts = [f"Freed - {r['name']}" for r in LOCATIONS if "Divine Beast" in categories(r)]
        shrines = [f"Cleared - {r['name']}" for r in LOCATIONS if "Shrine" in categories(r)]
        for state in states(multiworld, 300):
            sanctum = (plain(goal_row, state, 1)
                       and state.has_all(["Master Sword", "Magnesis", "Remote Bomb", "Stasis", "Cryonis"], 1)
                       and state.has_from_list(beasts, 1, 3) and state.has_from_list(shrines, 1, 20))
            self.assertEqual(ganon.access_rule(state), sanctum)
            self.assertEqual(multiworld.completion_condition[1](state), state.has_from_list(shrines, 1, 30))

    def test_explain_names_what_is_missing(self):
        multiworld = generate()
        rule = multiworld.get_location("Oman Au Shrine", 1).access_rule
        state = CollectionState(multiworld)
        self.assertIn("Missing Magnesis", rule.explain_str(state))
        self.assertTrue(rule.explain_json(state))


class TestRegeneration(unittest.TestCase):
    def test_the_slot_data_gives_back_the_same_world(self):
        original = generate(OPTIONS, seed=7)
        slot_data = original.worlds[1].fill_slot_data()
        self.assertEqual(len(slot_data["stall_locations"]), 11)
        passthrough = BotwWorld.interpret_slot_data(slot_data)
        self.assertTrue(passthrough)
        again = generate(passthrough=passthrough, seed=99)       # default options, another seed
        names = lambda mw: sorted(loc.name for loc in mw.get_locations())
        self.assertEqual(names(again), names(original))
        self.assertEqual(again.worlds[1].fill_slot_data(), slot_data)
        ganon = (original.get_location(GOAL_LOCATION, 1), again.get_location(GOAL_LOCATION, 1))
        for state in states(original, 200):
            twin = CollectionState(again)
            for item, count in state.prog_items[1].items():
                twin.prog_items[1][item] = count
            self.assertEqual(ganon[1].access_rule(twin), ganon[0].access_rule(state))
            self.assertEqual(again.completion_condition[1](twin), original.completion_condition[1](state))

    def test_a_normal_generation_is_not_changed_by_the_tracker(self):
        self.assertIsNone(generate(OPTIONS).worlds[1].passed_stalls)
