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


def plain(row, state, player, keys=True, towers=False):
    """The rule as requirements() says it: every group met by one of its names;
    with the maps as region keys (keys), every map of map_keys() (a tower's with
    towers), or the stand-in Universal Tracker gives itself."""
    maps = map_keys(row, towers) if keys else ()
    return (all(any(state.has(name, player, count) for name in names) for names, count in requirements(row))
            and (all(state.has(name, player) for name in maps) or state.has("Region Without Its Map", player)))


class TestRulesAreTheLogic(unittest.TestCase):
    def test_every_location_and_event_asks_what_its_requirements_say(self):
        for options in ({}, OPTIONS, {**OPTIONS, "tower_maps": "items"}, {"towers_need_maps": True}):
            multiworld = generate(options)
            keys = options.get("tower_maps", "region_keys") == "region_keys"
            towers = options.get("towers_need_maps", False)
            rows = {row["name"]: row for row in LOCATIONS}
            spots = []
            for loc in multiworld.get_locations():
                name = loc.name.split(" - ", 1)[1] if loc.address is None and " - " in loc.name else loc.name
                if name != GOAL_LOCATION:
                    spots.append((loc, rows[name]))
            for state in states(multiworld, 150):
                for loc, row in spots:
                    self.assertEqual(loc.access_rule(state), plain(row, state, 1, keys, towers), loc.name)

    def test_the_sanctum_and_the_goal_ask_what_the_options_say(self):
        multiworld = generate(OPTIONS)
        ganon = multiworld.get_location(GOAL_LOCATION, 1)
        goal_row = next(row for row in LOCATIONS if row["name"] == GOAL_LOCATION)
        beasts = [f"Freed - {r['name']}" for r in LOCATIONS if "Divine Beast" in categories(r)]
        shrines = [f"Cleared - {r['name']}" for r in LOCATIONS if "Shrine" in categories(r)]
        for state in states(multiworld, 300):
            sanctum = (plain(goal_row, state, 1)
                       and state.has_all(["Master Sword", "Magnesis", "Progressive Remote Bomb", "Progressive Stasis", "Cryonis"], 1)
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


class MapTabTests(unittest.TestCase):
    """Universal Tracker's map tab (botw_world/tracker.py): the player's PopTracker pack, Link's
    mark from the room's data storage, the items beside the map."""

    def test_the_map_tab_reads_the_players_pack(self):
        from .. import tracker
        config = BotwWorld.tracker_world
        self.assertEqual(config["external_pack_key"], "ut_pack_path")
        self.assertEqual((config["map_page_maps"], config["map_page_locations"]),
                         ("maps/maps.json", "locations/locations.json"))
        self.assertEqual(BotwWorld.settings_key, "botw_options")
        self.assertIn("ut_pack_path", tracker.BotwSettings.__annotations__)
        self.assertFalse(tracker.TrackerPackPath.required)
        # The key the client writes (botw_client/uat.py ROOM_KEY), for a slot of a team.
        self.assertEqual(config["location_setting_key"].format(team=0, player=3), "botw_link_0_3")
        for layout in config["map_page_item_layouts_left"]:
            self.assertFalse(set(layout["items"]) - set(BotwWorld.item_name_to_id), layout["name"])

    def test_link_is_placed_by_the_packs_grid(self):
        import json
        import os
        import tempfile
        import zipfile
        from .. import tracker
        grid = {"origin_x": -6000.0, "origin_z": -5000.0, "scale": 0.2, "left": 162, "top": 180,
                "cell": 20.0, "rows": 84, "cols": 104}
        with tempfile.TemporaryDirectory() as folder:
            pack = os.path.join(folder, "poptracker", tracker.PACK)
            os.makedirs(os.path.dirname(pack))
            with zipfile.ZipFile(pack, "w") as archive:
                archive.writestr("maps/link_grid.json", json.dumps(grid))
            self.assertEqual(tracker.link_coords(0, {"x": -1000, "z": 1500, "region": "Great Plateau"}, pack),
                             (838, 1120, tracker.LINK_ICON))
            self.assertIsNone(tracker.link_coords(0, "", pack))              # nothing written yet
            self.assertIsNone(tracker.link_coords(0, {"x": -5900, "z": 0}, pack))   # off the map shown
            self.assertEqual(tracker.built_pack({"BOTW_AP_DATA": folder}), pack)
            self.assertEqual(tracker.built_pack({"BOTW_AP_DATA": os.path.join(folder, "none")}), "")
        self.assertIsNone(tracker.link_coords(0, {"x": 0, "z": 0}, os.path.join(folder, "gone.zip")))
        # A pack with the arrows: his mark faces where he does.
        with tempfile.TemporaryDirectory() as folder:
            pack = os.path.join(folder, tracker.PACK)
            with zipfile.ZipFile(pack, "w") as archive:
                archive.writestr("maps/link_grid.json", json.dumps(dict(grid, arrows=tracker.ARROWS)))
            here = {"x": -1000, "z": 1500, "region": "Great Plateau"}
            self.assertEqual(tracker.link_coords(0, dict(here, heading=95), pack), (838, 1120, "images/link/04.png"))
            self.assertEqual(tracker.link_coords(0, dict(here, heading=350), pack)[2], "images/link/00.png")
            self.assertEqual(tracker.link_coords(0, here, pack)[2], tracker.LINK_ICON)
