"""region_lock's return out of a closed region (botw_client/region_return.py): the plateau's
return aimed at the last safe ground outside, put back at once, and Link's life kept."""
from __future__ import annotations

import struct
import unittest
import zlib

from botw_client import region_border as rb, region_return as rr
from botw_client.cucco_swarm import PLAYER_INFO
from botw_client.region_border import Areas
from botw_client.travel_points import PARAGLIDER

from tests.test_region_border import Clock, Memory

INFO, PLAYER = 0x20000000, 0x30000000
Z = 2000.0      # in the plateau's box from x = -1600 to -350


class Grid:
    """A tower grid of 2 m rows, the West area left of x = `split`, the East one right of it."""
    rows, divisor = 4000, 2

    def __init__(self, split=0):
        self.split = split

    def row(self, index):
        return [(0, self.split + 5000), (1, 5000 - self.split)]


class Game:
    def __init__(self, split=0, life=12, paraglider=1):
        self.memory, self.clock = Memory(), Clock()
        self.flags = {PARAGLIDER: paraglider, rr.LIFE_FLAG: life}
        self.memory.put(PLAYER_INFO, INFO.to_bytes(4, "big"))
        self.memory.put(INFO + 0x30, PLAYER.to_bytes(4, "big"))
        self.memory.put(rr.PLATEAU_BOX, rr.VANILLA)
        self.set_life(life)
        self.back = rr.RegionReturn(self.memory.read, self.memory.write, self.get, self.set_flag,
                                    Areas(Grid(split), {0: "West", 1: "East"}), clock=self.clock)

    def get(self, flag, kind):
        return self.flags.get(flag)

    refused = 0

    def set_flag(self, flag, value):
        if self.refused:
            self.refused -= 1
            return False
        self.memory.writes.append((flag, value))
        self.flags[flag] = value
        return True

    def set_life(self, life):
        self.memory.put(PLAYER + rr.LIFE, struct.pack(">i", life))
        self.flags[rr.LIFE_FLAG] = life

    def life(self):
        return struct.unpack(">i", self.memory.read(PLAYER + rr.LIFE, 4))[0]

    def stand(self, x, closed=frozenset({"East"}), z=Z, playing=True):
        """Link on his safe ground at (x, 0, z), a tick later."""
        self.memory.put(PLAYER + rr.SAFE_GROUND, struct.pack(">3f", x, 0.0, z))
        self.clock.now += 0.1
        return self.back.tick((x, 0.0, z), closed, playing=playing)

    def walk(self, start, end, closed=frozenset({"East"})):
        x, state = start, None
        while x <= end:
            state = self.stand(x, closed)
            x += 0.5
        return state

    def held(self, x=0.5):
        """The engine holds the target, Link not put down yet."""
        self.memory.put(PLAYER + rr.SAFE_GROUND, self.memory.read(rr.PLATEAU_RETURN, 12))
        self.clock.now += 0.1
        return self.back.tick((x, 0.0, Z), frozenset({"East"}))

    def destination(self):
        return struct.unpack(">3f", self.memory.read(rr.PLATEAU_RETURN, 12))


class Send(unittest.TestCase):
    def test_entering_aims_the_return_beyond_the_message(self):
        game = Game()
        state = game.walk(-40, 0.5)
        self.assertEqual("aimed", state["phase"])
        target = game.destination()
        self.assertAlmostEqual(-rr.CLEAR, target[0])    # East begins at x = 0
        self.assertGreater(rr.CLEAR, rb.WARN)
        self.assertEqual(0, game.flags[PARAGLIDER])
        self.assertEqual(rr.VANILLA[:4], game.memory.read(rr.PLATEAU_BOX, 4))   # Link outside the box
        self.assertTrue(game.back.busy)

    def test_in_the_plateaus_box_it_is_emptied(self):
        game = Game(split=-1000)
        game.walk(-1040, -999.5)
        self.assertEqual(rr.EMPTY_BOX, game.memory.read(rr.PLATEAU_BOX, 4))

    def test_without_a_ground_clear_of_the_message_the_clearest(self):
        game = Game()
        game.walk(-8, 0.5)
        self.assertAlmostEqual(-8.0, game.destination()[0])

    def test_held_target_puts_the_flag_back_first(self):
        game = Game()
        game.walk(-40, 0.5)
        game.memory.writes.clear()
        state = game.held()
        self.assertEqual("landing", state["phase"])
        self.assertEqual([(PARAGLIDER, 1), (rr.PLATEAU_BOX, rr.VANILLA)], game.memory.writes)
        state = game.stand(game.back.target[0])
        self.assertEqual(("cooldown", "returned"), (state["phase"], state["result"]))

    def test_put_down_without_a_hit_the_advance_is_taken_back(self):
        game = Game(life=3)
        game.walk(-40, 0.5)
        game.stand(game.back.target[0])
        self.assertEqual(7, game.life())
        game.clock.now += rr.COOLDOWN
        self.assertEqual("idle", game.stand(game.back.target[0])["phase"])
        self.assertEqual(3, game.life())

    def test_the_message_is_let_go_through_the_return(self):
        game = Game()
        game.walk(-40, 0.5)
        self.assertTrue(game.back.hush)
        game.stand(game.back.target[0])
        self.assertTrue(game.back.hush)
        game.clock.now += rr.COOLDOWN
        game.stand(game.back.target[0])
        self.assertFalse(game.back.hush)

    def test_the_returns_damage_is_given_back(self):
        game = Game(life=12)
        game.walk(-40, 0.5)
        game.stand(game.back.target[0])
        game.set_life(8)
        state = game.stand(game.back.target[0])
        self.assertEqual(("cooldown", "returned"), (state["phase"], state["result"]))
        self.assertEqual(12, game.life())

    def test_a_return_that_would_kill_is_paid_in_advance(self):
        game = Game(life=3)
        game.walk(-40, 0.5)
        self.assertEqual(7, game.life())
        game.stand(game.back.target[0])
        game.set_life(3)
        game.stand(game.back.target[0])
        self.assertEqual(3, game.life())

    def test_after_the_cooldown_a_second_return(self):
        game = Game()
        game.walk(-40, 0.5)
        target = game.destination()[0]
        game.stand(target)
        game.set_life(8)
        game.stand(target)
        game.flags[rr.LIFE_FLAG] = game.life()       # CurrentHart follows the actor's life
        game.clock.now += rr.COOLDOWN
        self.assertEqual("idle", game.stand(target)["phase"])
        self.assertEqual("aimed", game.walk(target, 0.5)["phase"])

    def test_without_the_hold_the_flag_is_back_soon(self):
        game = Game()
        game.walk(-40, 0.5)
        game.clock.now += rr.FLAG_SECONDS
        state = game.stand(0.5)
        self.assertEqual(("aimed", 1), (state["phase"], game.flags[PARAGLIDER]))
        self.assertEqual(rr.VANILLA, game.memory.read(rr.PLATEAU_BOX, len(rr.VANILLA)))

    def test_a_flag_refused_back_is_written_again_and_the_box_waits_for_it(self):
        game = Game()
        game.walk(-40, 0.5)
        game.refused = 2                            # both tries of that tick
        game.clock.now += rr.RETURN_SECONDS
        state = game.stand(0.5)
        self.assertEqual(("no return", 0), (state["result"], game.flags[PARAGLIDER]))
        self.assertNotEqual(rr.VANILLA, game.memory.read(rr.PLATEAU_BOX, len(rr.VANILLA)))
        game.stand(0.5)
        self.assertEqual(1, game.flags[PARAGLIDER])
        self.assertEqual(rr.VANILLA, game.memory.read(rr.PLATEAU_BOX, len(rr.VANILLA)))

    def test_a_hit_before_the_hold_is_not_the_return_s(self):
        game = Game(life=3)
        game.walk(-40, 0.5)
        game.set_life(5)                            # an enemy, 7 -> 5
        game.stand(0.5)
        game.stand(game.back.target[0])
        self.assertEqual(("cooldown", 5), (game.back.phase, game.life()))
        game.set_life(1)                            # the return's 4
        state = game.stand(game.back.target[0])
        self.assertEqual("returned", state["result"])
        self.assertEqual(3, game.life())

    def test_no_hold_puts_everything_back(self):
        game = Game(life=3)
        game.walk(-40, 0.5)
        game.clock.now += rr.RETURN_SECONDS
        state = game.stand(0.5)
        self.assertEqual("no return", state["result"])
        self.assertEqual(1, game.flags[PARAGLIDER])
        self.assertEqual(rr.VANILLA, game.memory.read(rr.PLATEAU_BOX, len(rr.VANILLA)))
        self.assertEqual(3, game.life())


class Guards(unittest.TestCase):
    def test_without_paraglider_nothing_is_written(self):
        game = Game(paraglider=0)
        state = game.walk(-40, 10)
        self.assertEqual("idle", state["phase"])
        self.assertEqual([], game.memory.writes)

    def test_a_life_other_than_current_hart_waits(self):
        game = Game()
        game.flags[rr.LIFE_FLAG] = 11
        state = game.walk(-40, 0.5)
        self.assertEqual("idle", state["phase"])
        self.assertEqual([], game.memory.writes)

    def test_in_the_air_nothing_happens(self):
        game = Game()
        game.walk(-40, -1)
        game.memory.put(PLAYER + rr.SAFE_GROUND, struct.pack(">3f", 1.0, 0.0, Z))
        state = game.back.tick((1.0, 10.0, Z), frozenset({"East"}))
        self.assertEqual("idle", state["phase"])

    def test_no_ground_outside_the_clifftop_only_after_a_while(self):
        game = Game()
        start = game.clock.now
        while game.clock.now - start < rr.FALLBACK_SECONDS - 0.05:
            state = game.stand(3)
            self.assertEqual("waiting: no safe ground known outside", state["result"])
        self.assertEqual([], game.memory.writes)
        game.clock.now += 0.05
        state = game.stand(3)
        self.assertEqual(("aimed", True, "East"), (state["phase"], state["fallback"], state["region"]))
        self.assertEqual(rr.CLIFFTOP, game.destination())
        self.assertEqual(rr.CLIFFTOP, tuple(struct.unpack(">3f", rr.VANILLA[16:])))

    def test_off_the_ground_the_clifftop_waits_again(self):
        game = Game()
        for _ in range(int(rr.FALLBACK_SECONDS * 10) - 2):
            game.stand(3)
        game.clock.now += 0.1
        game.back.tick((3.0, 10.0, Z), frozenset({"East"}))     # a jump
        state = game.stand(3)
        self.assertEqual("waiting: no safe ground known outside", state["result"])

    def test_no_clifftop_when_it_is_closed_itself(self):
        game = Game(split=-2000)                                # the plateau in East
        for _ in range(int(rr.FALLBACK_SECONDS * 20)):
            state = game.stand(3)
        self.assertEqual(("idle", "waiting: no safe ground known outside"), (state["phase"], state["result"]))
        self.assertEqual([], game.memory.writes)

    def test_a_dead_link_is_not_sent(self):
        game = Game()
        game.walk(-40, -1)
        game.set_life(0)
        state = game.stand(0.5)
        self.assertEqual(("idle", "waiting: Link dead"), (state["phase"], state["result"]))
        self.assertEqual([], game.memory.writes)

    def test_out_of_play_nothing_is_sent_and_the_grounds_stay(self):
        game = Game()
        kept = game.walk(-40, -1)["kept"]
        game.stand(-0.5, playing=False)
        state = game.stand(0.5, playing=False)
        self.assertEqual(("idle", kept + 1), (state["phase"], state["kept"]))
        self.assertEqual([], game.memory.writes)
        game.stand(-30, playing=False)
        self.assertEqual((1, {"out of play or dead": 1}), game.back.state["missed"])
        self.assertEqual("aimed", game.stand(0.5)["phase"])

    def test_a_life_changed_since_is_not_written_back(self):
        for life in (0, 12):                                    # a death, a respawn
            game = Game(life=3)
            game.walk(-40, 0.5)
            game.set_life(life)
            game.clock.now += rr.RETURN_SECONDS
            self.assertEqual("no return", game.stand(0.5, playing=False)["result"])
            self.assertEqual(life, game.life())

    def test_a_jump_forgets_the_grounds(self):
        game = Game()
        game.walk(-40, -1)
        state = game.stand(100)
        self.assertEqual(0, state["kept"])

    def test_entering_with_a_safe_ground_left_outside_is_told(self):
        game = Game()
        game.walk(-40, -1)
        for x in (2.0, 4.0, 6.0):
            game.clock.now += 0.1
            state = game.back.tick((x, 0.0, Z), frozenset({"East"}))
        self.assertEqual("idle", state["phase"])
        state = game.stand(-30)
        self.assertEqual((1, {"safe ground outside": 3}), state["missed"])
        self.assertIn("safe ground in West", rr.report(state))

    def test_an_open_region_is_walked_into(self):
        game = Game()
        state = game.walk(-40, 10, closed=frozenset())
        self.assertEqual("idle", state["phase"])
        self.assertEqual([], game.memory.writes)


class Repair(unittest.TestCase):
    def test_a_return_left_aimed_is_put_back(self):
        game = Game()
        game.memory.put(rr.PLATEAU_BOX, rr.EMPTY_BOX)
        game.memory.put(rr.PLATEAU_RETURN, struct.pack(">3f", 1, 2, 3))
        self.assertTrue(game.stand(-40)["plateau"])
        self.assertEqual(rr.VANILLA, game.memory.read(rr.PLATEAU_BOX, len(rr.VANILLA)))

    def test_another_content_is_left_alone(self):
        game = Game()
        game.memory.put(rr.PLATEAU_BOX + 4, b"\0\0\0\0")
        state = game.walk(-40, 0.5)
        self.assertEqual((False, "idle"), (state["plateau"], state["phase"]))
        self.assertEqual([], game.memory.writes)

    def test_the_vanilla_bytes_are_the_measured_ones(self):
        values = struct.unpack(">7f", rr.VANILLA)
        self.assertEqual((-1600.0, -350.0, 1400.0, 2400.0), values[:4])
        self.assertLess(max(abs(a - b) for a, b in zip(values[4:], (-1021.73, 253.32, 1792.6))), 0.01)


class Sign(unittest.TestCase):
    def border(self, back):
        from tests.test_region_border import game
        memory, reads = game((-40.0, 0.0, Z)), []
        sign = rb.RegionBorder(memory.read, memory.write, lambda index, passes: True,
                               Areas(Grid(), {0: "West", 1: "East"}),
                               lambda: reads.append(1) or frozenset({"East"}), back=back, clock=back.clock)
        return sign, reads

    def test_the_closed_regions_are_not_read_while_a_return_runs(self):
        back = Busy()
        sign, reads = self.border(back)
        sign.tick()
        back.busy = True
        back.clock.now += 5
        state = sign.tick()
        self.assertEqual(1, len(reads))
        self.assertEqual({"East"}, back.closed)
        self.assertEqual("ticked", state["back"])
        sign.release()
        self.assertTrue(back.released)

    def test_the_message_is_let_go_while_the_return_hushes_it(self):
        from tests.test_region_border import game
        memory, holds, back = game((-5.0, 0.0, Z)), [], Busy()
        sign = rb.RegionBorder(memory.read, memory.write, lambda index, passes: holds.append(passes) or True,
                               Areas(Grid(), {0: "West", 1: "East"}), lambda: frozenset({"East"}),
                               back=back, clock=back.clock)
        self.assertTrue(sign.tick()["message"])
        back.hush = True
        self.assertFalse(sign.tick()["message"])
        self.assertEqual([rb.MARGIN, 0], holds)

    def sign(self, x, playing, closures=None):
        from tests.test_region_border import game
        memory, holds, back = game((x, 0.0, Z)), [], Busy()
        sign = rb.RegionBorder(memory.read, memory.write, lambda index, passes: holds.append(passes) or True,
                               Areas(Grid(), {0: "West", 1: "East"}), lambda: frozenset({"East"}),
                               back=back, playing=playing, closures=closures, clock=back.clock)
        return sign, memory, holds, back

    def test_back_in_play_the_message_waits_a_while(self):
        play = [False]
        sign, _memory, _holds, back = self.sign(-5.0, lambda: play[0])
        self.assertFalse(sign.tick()["message"])               # a dialogue
        play[0] = True
        back.clock.now += rb.PLAY_SECONDS + 0.01
        start = back.clock.now
        while back.clock.now - start < rb.SETTLE - 0.05:
            self.assertFalse(sign.tick()["message"])
            back.clock.now += 0.1
        back.clock.now += 0.1
        self.assertTrue(sign.tick()["message"])

    def test_after_a_return_the_message_waits_a_while(self):
        sign, _memory, _holds, back = self.sign(-5.0, None)
        self.assertTrue(sign.tick()["message"])
        back.hush = True
        self.assertFalse(sign.tick()["message"])
        back.hush = False
        self.assertFalse(sign.tick()["message"])
        back.clock.now += rb.SETTLE + 0.01
        self.assertTrue(sign.tick()["message"])

    def test_closed_by_the_game_the_message_waits_longer_each_time(self):
        count = [7]                                             # the cave's, from an earlier load
        sign, _memory, holds, back = self.sign(-5.0, None, lambda: count[0])

        def tick(seconds=0.1):
            back.clock.now += seconds
            return sign.tick()

        self.assertTrue(tick()["message"])
        self.assertEqual(0, tick()["closures"])
        for wait in (rb.BACKOFF, rb.BACKOFF * 2, rb.BACKOFF * 4):
            count[0] += 1                                       # the hold stopped: closed by the game
            state = tick()
            self.assertFalse(state["message"])
            self.assertAlmostEqual(wait, state["backoff"])
            self.assertFalse(tick(wait - 0.2)["message"])
            self.assertTrue(tick(0.2)["message"])
        self.assertEqual(3, sign.closures)
        for _ in range(int(rb.STEADY / 2) + 1):
            tick(2.0)                                           # held without a closure
        count[0] += 1
        self.assertAlmostEqual(rb.BACKOFF, tick()["backoff"])
        tick(rb.BACKOFF + 0.1)
        count[0] = 0                                            # Cemu started again: a new cave
        self.assertTrue(tick()["message"])
        self.assertEqual(4, sign.closures)

    def test_a_pack_without_the_count_holds_as_before(self):
        sign, _memory, _holds, _back = self.sign(-5.0, None, lambda: None)
        self.assertTrue(sign.tick()["message"])

    def test_out_of_play_the_message_is_let_go_and_no_return(self):
        calls, play = [], [True]
        sign, _memory, holds, back = self.sign(-5.0, lambda: calls.append(1) or play[0])
        self.assertTrue(sign.tick()["message"])
        play[0] = False
        back.clock.now += rb.PLAY_SECONDS + 0.01
        state = sign.tick()
        self.assertEqual((False, True, False), (state["message"], state["near"], state["playing"]))
        self.assertFalse(back.playing)
        self.assertEqual([rb.MARGIN, 0], holds)
        sign.tick()                                             # within PLAY_SECONDS: not read again
        self.assertEqual(2, len(calls))

    def test_playing_is_read_only_near_and_unreadable_is_out_of_play(self):
        calls = []
        sign, _memory, _holds, _back = self.sign(-rb.WARN - rb.LEAVE - 1.0, lambda: calls.append(1) or True)
        self.assertFalse(sign.tick()["playing"])
        self.assertEqual([], calls)
        sign, _memory, _holds, _back = self.sign(-5.0, lambda: 1 / 0)
        self.assertFalse(sign.tick()["message"])

    def test_the_message_is_let_go_a_little_farther_than_it_shows(self):
        from tests.test_region_border import PLAYER as LINK
        sign, memory, holds, back = self.sign(-rb.WARN, None)
        self.assertTrue(sign.tick()["message"])
        memory.put(LINK + 0x204, struct.pack(">f", -rb.WARN - rb.LEAVE + 0.1))
        self.assertTrue(sign.tick()["message"])
        memory.put(LINK + 0x204, struct.pack(">f", -rb.WARN - rb.LEAVE - 0.1))
        self.assertFalse(sign.tick()["message"])
        memory.put(LINK + 0x204, struct.pack(">f", -rb.WARN - 0.1))
        self.assertFalse(sign.tick()["message"])
        self.assertEqual([rb.MARGIN, rb.MARGIN, 0], holds)


class Busy:
    def __init__(self):
        self.clock, self.busy, self.released, self.closed = Clock(), False, False, None

    hush = False

    def tick(self, position, closed, field=True, playing=True):
        self.playing = playing
        self.closed = closed
        return "ticked"

    def release(self):
        self.released = True


class Runtime(unittest.TestCase):
    def runtime(self, memory):
        from types import SimpleNamespace
        from botw_client.runtime import BotwClientRuntime
        runtime = BotwClientRuntime.__new__(BotwClientRuntime)
        runtime._border_areas = Areas(Grid(), {0: "West", 1: "East"})
        runtime._border_zone = runtime._border_return = None
        runtime._border_missed = runtime._border_closures = 0
        runtime._journal_notes, runtime.tip_factory = [], object()
        runtime.lines = []
        runtime.log = runtime.lines.append
        live = SimpleNamespace(index={"bool": {HASH: OBJECT}}, sets=[], get=lambda h, kind: None)
        live.set = lambda h, value: live.sets.append((h, value)) or True
        process = SimpleNamespace(read=memory.read, write=memory.write)
        runtime.game = SimpleNamespace(item_map={}, process=process, live=live,
                                       cave=SimpleNamespace(base=0, hold_center=lambda index, passes: True))
        return runtime, live

    def test_the_flag_is_written_only_on_its_own_object(self):
        memory = Memory()
        runtime, live = self.runtime(memory)
        back = runtime._make_border({"region_lock": 1}).back
        self.assertFalse(back.set_flag(PARAGLIDER, 0))
        memory.put(OBJECT + 8, HASH.to_bytes(4, "big"))
        self.assertTrue(back.set_flag(PARAGLIDER, 0))
        self.assertEqual([(HASH, 0)], live.sets)

    def test_the_log_tells_each_return(self):
        runtime, _ = self.runtime(Memory())
        for back in ({"phase": "idle"}, {"phase": "aimed", "target": (1.0, 2.0, 3.0)}, {"phase": "landing"},
                     {"phase": "cooldown", "result": "returned"}, {"phase": "cooldown", "result": "returned"}):
            runtime._log_border({"nearest": None, "back": back})
        self.assertEqual(["region lock: Link sent back to (1.0, 2.0, 3.0)", "region lock: returned"],
                         runtime.lines)
        runtime._log_border({"nearest": None, "back": {"phase": "idle", "missed": (1, {"cooldown": 4})}})
        self.assertEqual("region lock: in a closed region without a return: cooldown 0.4 s", runtime.lines[-1])
        self.assertIn("2 safe grounds kept", rr.report(dict(phase="idle", kept=2, target=None, result=None,
                                                             plateau=True)))

    def test_each_return_tells_why_in_the_journal_once_queued(self):
        runtime, _ = self.runtime(Memory())
        for _ in range(2):
            for back in ({"phase": "aimed", "target": (1.0, 2.0, 3.0), "region": "East"},
                         {"phase": "cooldown", "result": "returned", "region": "East"}):
                runtime._log_border({"nearest": None, "back": back})
        self.assertEqual([("{0}East is locked{/}: find the {1}East Map{/} to enter it", None)],
                         runtime._journal_notes)
        runtime._log_border({"nearest": None, "back": {"phase": "aimed", "target": rr.CLIFFTOP,
                                                       "region": "East", "fallback": True}})
        self.assertIn("no safe ground known outside, Link sent to the Great Plateau's clifftop",
                      runtime.lines[-1])

    def test_the_journals_line_names_what_opens_the_region(self):
        from botw_client.ap_journal import region_locked_line
        self.assertIn("find the {1}Central Map{/}", region_locked_line("Central", False))
        self.assertIn("open another region next to it", region_locked_line("Central", True))
        self.assertIn("opens with Central", region_locked_line("Hyrule Castle", False, "Central"))

    def test_nothing_is_closed_before_the_paraglider_but_during_a_return(self):
        runtime, live = self.runtime(Memory())
        border = runtime._make_border({"region_lock": 1})
        live.get = lambda h, kind: False
        self.assertIsNone(border.closed_source())        # the game keeps Link on the Plateau
        border.back.lowered = True                       # a return holds the flag low a moment
        self.assertEqual({"West", "East"}, set(border.closed_source()))
        border.back.lowered = False
        live.get = lambda h, kind: True
        self.assertEqual({"West", "East"}, set(border.closed_source()))

    def test_playing_asks_the_delivery_backend_and_life(self):
        from types import SimpleNamespace
        runtime, live = self.runtime(Memory())
        seen = []
        runtime.deliveries = SimpleNamespace(backend=SimpleNamespace(playing=lambda: seen.append(1) or True))
        playing = runtime._make_border({"region_lock": 1}).playing
        live.get = lambda h, kind: 12
        self.assertTrue(playing())
        live.get = lambda h, kind: 0
        self.assertFalse(playing())
        self.assertEqual(1, len(seen))

    def test_a_message_closed_by_the_game_is_logged(self):
        runtime, _ = self.runtime(Memory())
        runtime._log_border({"nearest": None, "closures": 1, "backoff": 2.97, "back": {}})
        runtime._log_border({"nearest": None, "closures": 1, "backoff": 2.87, "back": {}})
        self.assertEqual(["region border: the game closed the held message (1 so far): asked again in 3 s"],
                         runtime.lines)

    def test_a_menu_near_a_border_logs_nothing(self):
        runtime, _ = self.runtime(Memory())
        runtime._log_border({"nearest": ("East", 3.0), "near": True, "message": True, "back": {}})
        runtime._log_border({"nearest": ("East", 3.0), "near": True, "message": False, "back": {}})
        self.assertEqual(["region border: East closed, 3 m away: message"], runtime.lines)


HASH, OBJECT = zlib.crc32(PARAGLIDER.encode()) & 0xFFFFFFFF, 0x24000000


if __name__ == "__main__":
    unittest.main()
