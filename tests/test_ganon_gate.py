"""The sanctum's gate (botw_patch/ganon_gate.py), on the game's own flow."""
import math
from pathlib import Path
import unittest

from botw_patch import ganon_gate as gate

UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
AREA_CENTRE, AREA_RADIUS = (-254.0, -1061.0), 25.0      # E-4, Area 264383435


@unittest.skipUnless((UPDATE / gate.PACK).is_file(), "Wii U update absent")
class GateTests(unittest.TestCase):
    def gated(self):
        import oead
        from botw_patch.events import graph_snapshot, read_flow
        from botw_patch.resources import unpack
        raw = bytes(oead.Sarc(unpack((UPDATE / gate.PACK).read_bytes())).get_file(gate.FLOW).data)
        out, _ = gate.transform(raw)
        return graph_snapshot(read_flow(raw)), graph_snapshot(read_flow(out))

    def test_the_fight_waits_behind_the_open_flag(self):
        before, after = self.gated()
        self.assertEqual(dict(after["entry_points"])["BossRoom0"], "APGanonGate")
        check = after["events"]["APGanonGate"]
        self.assertEqual((check["actor_query"], check["params"]), ("CheckFlag", {"FlagName": gate.OPEN}))
        self.assertEqual(check["cases"][1], dict(before["entry_points"])["BossRoom0"])

    def test_closed_it_only_marks_the_refusal_and_sends_link_back(self):
        before, after = self.gated()
        path, node = [], after["events"]["APGanonGate"]["cases"][0]
        while node:
            path.append(after["events"][node])
            node = path[-1].get("nxt")
        self.assertEqual([e["actor_action"] for e in path],
                         ["Demo_FlagON", "Demo_FadeOut", "Demo_WarpPlayerToDestination", "Demo_FadeIn",
                          "Demo_OpenDungeonMessage"])
        self.assertEqual(path[4]["params"]["MessageId"], gate.MESSAGE)
        self.assertEqual(path[0]["params"]["FlagName"], gate.REFUSED)
        warp = path[2]["params"]
        self.assertGreater(math.hypot(warp["DestinationX"] - AREA_CENTRE[0],
                                      warp["DestinationZ"] - AREA_CENTRE[1]), AREA_RADIUS + 5)
        # Nothing of the game's flow changed.
        for name, event in before["events"].items():
            self.assertEqual(after["events"][name], event)

    def test_the_sealed_line_is_added_in_every_language(self):
        import oead
        from botw_patch.resources import unpack
        from botw_patch.shop_items import add_labels, read_labels
        from botw_patch.status_item import LANGUAGES
        self.assertEqual(set(gate.SEALED), set(LANGUAGES))
        for language in LANGUAGES:
            with self.subTest(language=language):
                boot = oead.Sarc(unpack((UPDATE / f"Pack/Bootup_{language}.pack").read_bytes()))
                messages = oead.Sarc(unpack(bytes(boot.get_file(f"Message/Msg_{language}.product.ssarc").data)))
                raw = bytes(messages.get_file(gate.MSBT).data)
                out, _ = add_labels(raw, {gate.LABEL: gate.SEALED[language]}, gate.MODEL_LABEL)
                before, after = read_labels(raw), read_labels(out)
                self.assertEqual(after[gate.LABEL].rstrip(chr(0)), gate.SEALED[language])
                self.assertEqual({k: v for k, v in after.items() if k != gate.LABEL}, before)
                # Three lines at most, as the monks' own.
                self.assertLessEqual(gate.SEALED[language].count(chr(10)), 2)



class _Game:
    """The live flags of the gate, as BotwGame exposes them."""

    def __init__(self, is_open=False, refused=False):
        self.flags = {"open": is_open, "refused": refused}

    def ganon_gate(self):
        return self.flags["open"], self.flags["refused"]

    def open_ganon_gate(self):
        self.flags["open"] = True

    def clear_ganon_refusal(self):
        self.flags["refused"] = False


class ClientGateTests(unittest.IsolatedAsyncioTestCase):
    def runtime(self, game, slot_data, checked=(), received=()):
        import tempfile
        from types import SimpleNamespace
        from botw_client.runtime import BotwClientRuntime
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        runtime = BotwClientRuntime("unused:1", "test", state_path=Path(temporary.name) / "state.json",
                                    game_factory=lambda: game, tip_factory=lambda _game: None,
                                    log=lambda _line: None)
        runtime.game = game
        runtime.state = runtime.state_store.select("seed", 0, 1, "checksum")
        names = dict(enumerate(checked))
        runtime.ap = SimpleNamespace(slot_data=slot_data, checked_locations=set(names),
                                     location_name=names.get,
                                     received_items=dict(enumerate(received)), item_name=str)
        return runtime

    async def test_the_gate_opens_once_the_requirements_are_met(self):
        game = _Game()
        beasts = {"goal_type": 1, "divine_beasts_required": 2}
        runtime = self.runtime(game, beasts, ["Divine Beast Vah Ruta"])
        await runtime._ganon_gate_tick()
        self.assertFalse(game.flags["open"])
        runtime = self.runtime(game, beasts, ["Divine Beast Vah Ruta", "Divine Beast Vah Medoh"])
        await runtime._ganon_gate_tick()
        self.assertTrue(game.flags["open"])

    async def test_a_refusal_says_what_is_missing_in_the_journal(self):
        game = _Game(refused=True)
        runtime = self.runtime(game, {"goal_type": 2, "shrines_required": 40}, ["Oman Au Shrine"])
        await runtime._ganon_gate_tick()
        self.assertFalse(game.flags["refused"])
        self.assertEqual(runtime._journal_notes,
                         [("{0}Sanctum sealed{/}: 1/40 shrines cleared", None)])

    async def test_the_runes_and_the_master_sword_are_counted_when_asked(self):
        game = _Game(refused=True)
        asks = {"goal_type": 0, "ganon_runes": True, "ganon_master_sword": True}
        runtime = self.runtime(game, asks, received=["Magnesis", "Stasis", "Paraglider"])
        await runtime._ganon_gate_tick()
        self.assertFalse(game.flags["open"])
        self.assertEqual(runtime._journal_notes,
                         [("{0}Sanctum sealed{/}: 2/4 runes, 0/1 Master Sword", None)])
        runtime = self.runtime(game, asks, received=["Magnesis", "Stasis", "Remote Bomb", "Cryonis",
                                                     "Master Sword"])
        await runtime._ganon_gate_tick()
        self.assertTrue(game.flags["open"])

    async def test_a_seed_from_before_the_options_asks_for_neither(self):
        game = _Game()
        await self.runtime(game, {"goal_type": 0})._ganon_gate_tick()
        self.assertTrue(game.flags["open"])

    async def test_the_sanctum_options_are_read_from_a_schema_5_seed(self):
        game = _Game(refused=True)
        medium = {"goal": 0, "sanctum_divine_beasts": 2, "sanctum_shrines": 3,
                  "sanctum_master_sword": True, "sanctum_runes": False}
        runtime = self.runtime(game, medium, ["Divine Beast Vah Ruta", "Oman Au Shrine"], ["Master Sword"])
        await runtime._ganon_gate_tick()
        self.assertEqual(runtime._journal_notes, [(
            "{0}Sanctum sealed{/}: 1/2 Divine Beasts freed, 1/3 shrines cleared", None)])

    def test_each_goal_is_reached_by_its_own_rule(self):
        game = _Game()
        beasts = [f"Divine Beast Vah {name}" for name in ("Ruta", "Rudania", "Medoh", "Naboris")]
        goal = self.runtime(game, {"goal": 1}, beasts[:3])
        self.assertFalse(goal._goal_reached())
        self.assertTrue(self.runtime(game, {"goal": 1}, beasts)._goal_reached())
        shrines = {"goal": 2, "goal_shrines": 2}
        self.assertFalse(self.runtime(game, shrines, ["Oman Au Shrine"])._goal_reached())
        self.assertTrue(self.runtime(game, shrines, ["Oman Au Shrine", "Ja Baij Shrine"])._goal_reached())
        # Ganon's goal: his defeat, once the sanctum's requirements are met.
        ganon = self.runtime(game, {"goal": 0, "sanctum_runes": True})
        ganon.state["goal_observed"] = True
        self.assertFalse(ganon._goal_reached())
        ganon = self.runtime(game, {"goal": 0, "sanctum_runes": True},
                             received=["Magnesis", "Remote Bomb", "Stasis", "Cryonis"])
        self.assertFalse(ganon._goal_reached())     # not defeated yet
        ganon.state["goal_observed"] = True
        self.assertTrue(ganon._goal_reached())

    async def test_a_pack_without_the_gate_is_left_alone(self):
        game = _Game()
        game.ganon_gate = lambda: None
        runtime = self.runtime(game, {"goal_type": 0})
        await runtime._ganon_gate_tick()
        self.assertTrue(runtime._gate_unavailable)
        self.assertFalse(game.flags["open"])


if __name__ == "__main__":
    unittest.main()
