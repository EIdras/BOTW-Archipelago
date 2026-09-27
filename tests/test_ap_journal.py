"""The AP journal: the server's lines, laid out as tips, one tip at a time."""
from __future__ import annotations

import asyncio
import time
import unittest

from botw_client import tip_protocol as tp
from botw_client.ap_journal import journal_line
from botw_client.protocol import NetworkItem
from botw_client.tip_channel import COLOR, RESET, pages

ME, ALICE, BOB = 1, 2, 3
NAMES = {0: "Server", ME: "Simon", ALICE: "Alice", BOB: "Bob"}
ITEMS = {5: "Rupee Bundle", 6: "Paraglider", 7: "Hookshot"}
PLACES = {77: "Temple", 12: "Oman Au Shrine", 30: "Forest"}


def visible(page: str) -> str:
    out, i = [], 0
    while i < len(page):
        if page.startswith(COLOR, i):
            i += len(COLOR) + 1
            continue
        out.append(page[i])
        i += 1
    return "".join(out)


def render(node):
    kind, text = node.get("type"), node.get("text", "")
    if kind == "player_id":
        return NAMES[int(text)]
    if kind == "item_id":
        return ITEMS[int(text)]
    if kind == "location_id":
        return PLACES[int(text)]
    return text


def item_send(sender, receiving, item=7, location=77):
    """A PrintJSON ItemSend as the AP server sends it."""
    if sender == receiving:
        nodes = [{"type": "player_id", "text": str(sender)}, {"text": " found their "},
                 {"type": "item_id", "text": str(item)}, {"text": " ("},
                 {"type": "location_id", "text": str(location)}, {"text": ")"}]
    else:
        nodes = [{"type": "player_id", "text": str(sender)}, {"text": " sent "},
                 {"type": "item_id", "text": str(item)}, {"text": " to "},
                 {"type": "player_id", "text": str(receiving)}, {"text": " ("},
                 {"type": "location_id", "text": str(location)}, {"text": ")"}]
    return {"kind": "ItemSend", "text": "".join(render(n) for n in nodes), "nodes": nodes,
            "receiving": receiving, "sender": sender, "slot": None,
            "received_at": time.time()}


def chat(slot, text):
    return {"kind": "Chat", "text": text, "nodes": [{"text": text}], "receiving": None,
            "sender": None, "slot": slot, "received_at": time.time()}


def line(e, **options):
    return journal_line(e, ME, render, **options)


class PagesTests(unittest.TestCase):
    def test_lines_follow_the_games_tips(self):
        text = ("Tu as trouve Grappin pour Alice (A Link to the Past). Bob t'envoie : "
                "Coeur. Indice : l'Epee est chez Carol.")
        out = pages(text)
        self.assertEqual(len(out), 2)
        for page in out:
            rows = visible(page).split("\n")
            self.assertLessEqual(len(rows), tp.LINES)
            self.assertTrue(all(len(row) <= tp.LINE_WIDTH for row in rows))
        self.assertEqual(" ".join(" ".join(visible(p).split("\n")) for p in out), text)

    def test_colours_survive_the_line_breaks(self):
        (page,) = pages("{2}Alice{/} t'envoie : {1}Grappin de la tres longue foret perdue{/}")
        self.assertTrue(page.startswith(COLOR + "\u0002Alice" + RESET))
        self.assertIn(COLOR + "\u0001", page)
        self.assertTrue(page.endswith(RESET))
        self.assertEqual(visible(page).replace("\n", " "),
                         "Alice t'envoie : Grappin de la tres longue foret perdue")

    def test_text_braces_are_not_codes_and_long_words_break(self):
        (page,) = pages("{x} " + "A" * 40)
        self.assertNotIn(COLOR, page)
        rows = visible(page).split("\n")
        self.assertEqual(rows, ["{x} " + "A" * 30, "A" * 10])


class JournalTests(unittest.TestCase):
    def test_the_servers_sent_line_coloured(self):
        self.assertEqual(line(item_send(ME, ALICE)),
                         "{2}Simon{/} sent {1}Hookshot{/} to {2}Alice{/} (Temple)")

    def test_received_items_wait_for_their_presentation(self):
        self.assertIsNone(line(item_send(ALICE, ME)))
        self.assertIsNone(line(item_send(ME, ME)))

    def test_other_players_traffic_only_when_asked(self):
        self.assertIsNone(line(item_send(ALICE, BOB)))
        self.assertEqual(line(item_send(ALICE, BOB), everyone=True),
                         "{2}Alice{/} sent {1}Hookshot{/} to {2}Bob{/} (Temple)")

    def test_hints_about_this_slot(self):
        hint = dict(item_send(ALICE, ME), kind="Hint")
        self.assertIsNotNone(line(hint))
        self.assertIsNone(line(dict(item_send(ALICE, BOB), kind="Hint")))

    def test_chat_is_optional_and_received_text_has_no_codes(self):
        self.assertEqual(line(chat(ALICE, "Alice: salut {2}")), "Alice: salut (2)")
        self.assertIsNone(line(chat(ALICE, "Alice: salut"), chat=False))
        self.assertIsNone(line({"kind": "Join", "text": "Bob joined", "nodes": []}))


class FakeTips:
    def __init__(self, results):
        self.results, self.submitted, self.state = list(results), [], "idle"
        self.world = True

    def in_world(self):
        return self.world

    def poll(self):
        return self.state if self.state != "active" else None

    def submit(self, page):
        result = self.results.pop(0)
        if result == "accepted":
            self.submitted.append(page)
            self.state = "active"
        return result


def runtime(tips):
    from botw_client.runtime import BotwClientRuntime

    class Ap:
        slot, slot_name, players = ME, "Simon", NAMES
        location_names_by_game = {"A Link to the Past": PLACES, "Breath of the Wild": PLACES}
        received_items = {0: NetworkItem(5, 77, ALICE, 1), 1: NetworkItem(6, 12, ME, 1),
                          2: NetworkItem(5, -1, 0, 0)}

        def render_node(self, node):
            return render(node)

        def item_name(self, item):
            return ITEMS[item.item]

        def sender(self, item):
            return NAMES[item.player], ("Breath of the Wild" if item.player == ME
                                        else "A Link to the Past")

    class Store:
        def save(self):
            pass

    r = BotwClientRuntime.__new__(BotwClientRuntime)
    r.tips, r.tip_factory = tips, object()
    r.ap, r.state_store, r.log = Ap(), Store(), lambda *_: None
    r.state = {"message_queue": []}
    r.journal_chat, r.journal_everyone = True, False
    r._journal_notes, r._journal_pages = [], []
    r._journal_current, r._journal_retry_after = None, 0.0
    r._journal_started = time.time() - 1
    r._journal_queued, r._journal_times, r._journal_waiting = set(), {}, {}
    def unsafe():
        raise AssertionError("the journal must not call the stateful delivery guard")
    r._safe_now = unsafe
    return r


class RuntimeTickTests(unittest.TestCase):
    def test_one_tip_at_a_time_notes_first_and_stale_entries_skipped(self):
        tips = FakeTips(["accepted", "accepted"])
        r = runtime(tips)
        old = item_send(ME, BOB)
        old["received_at"] = r._journal_started - 10
        r.state["message_queue"] = [old, item_send(ME, ALICE)]
        r._journal_note("Connecté")
        asyncio.run(r._journal_tick())
        self.assertEqual([visible(p) for p in tips.submitted], ["Connecté"])
        asyncio.run(r._journal_tick())            # ours still on screen
        self.assertEqual(len(tips.submitted), 1)
        tips.state = "closed"
        asyncio.run(r._journal_tick())
        self.assertEqual(visible(tips.submitted[1]).replace("\n", " "),
                         "Simon sent Hookshot to Alice (Temple)")
        self.assertEqual(r.state["message_queue"], [])

    def test_a_received_items_line_stays_queued_for_its_item(self):
        tips = FakeTips(["accepted"])
        r = runtime(tips)
        received = item_send(ALICE, ME)
        r.state["message_queue"] = [received, chat(BOB, "Bob: hi")]
        asyncio.run(r._journal_tick())
        self.assertEqual([visible(p) for p in tips.submitted], ["Bob: hi"])
        self.assertEqual(r.state["message_queue"], [received])

    def test_nothing_is_sent_until_link_is_in_the_world(self):
        tips = FakeTips(["accepted"])
        r = runtime(tips)
        r._journal_note("Connecté")
        tips.world = False                        # title screen, loading
        asyncio.run(r._journal_tick())
        self.assertEqual(tips.submitted, [])
        tips.world, r._journal_retry_after = True, 0.0
        asyncio.run(r._journal_tick())
        self.assertEqual([visible(p) for p in tips.submitted], ["Connecté"])

    def test_busy_retries_later_and_a_dropped_tip_is_shown_again(self):
        tips = FakeTips(["busy", "accepted", "accepted"])
        r = runtime(tips)
        r._journal_note("Bonjour")
        asyncio.run(r._journal_tick())
        self.assertEqual(tips.submitted, [])
        r._journal_retry_after = 0.0
        asyncio.run(r._journal_tick())
        tips.state = "dropped"
        asyncio.run(r._journal_tick())
        self.assertEqual([visible(p) for p in tips.submitted], ["Bonjour", "Bonjour"])


class ReceivedAnnouncementTests(unittest.TestCase):
    """A received item: the server's line, then its window."""

    def runtime(self, kind="get_demo_actor"):
        r = runtime(FakeTips(["accepted"] * 5))

        class Catalog:
            def steps(self, name, before):
                return [{"mutations": [{"kind": kind}]}]

        r.deliveries = type("D", (), {"backend": type("B", (), {"catalog": Catalog()})()})()
        r._received_before = lambda index, name: 0
        return r

    def announce_and_show(self, r, index):
        while r._received_announcement(index) == "pending" and not r._journal_notes:
            r._journal_waiting[index] -= 10       # server line not coming
        r.tips.state = "closed"                   # the previous tip has closed
        asyncio.run(r._journal_tick())
        r._journal_times[index] -= 10
        return visible(r.tips.submitted[-1]).replace("\n", " ")

    def test_the_servers_line_first_then_the_vanilla_window_alone(self):
        r = self.runtime()
        r.state["message_queue"] = [item_send(ALICE, ME, item=5, location=77)]
        self.assertEqual(r._received_announcement(0), "pending")
        self.assertEqual(r.state["message_queue"], [])            # taken for its item
        asyncio.run(r._journal_tick())
        self.assertEqual(visible(r.tips.submitted[0]).replace("\n", " "),
                         "Alice sent Rupee Bundle to Simon (Temple)")
        self.assertEqual(r.state["journal_announced"], [0])
        self.assertEqual(r._received_announcement(0), "pending")  # reading time
        r._journal_times[0] -= 10
        self.assertEqual(r._received_announcement(0), "skip")

    def test_without_a_server_line_the_same_sentence_after_a_wait(self):
        r = self.runtime()
        self.assertEqual(r._received_announcement(1), "pending")
        self.assertEqual(r._journal_notes, [])                    # still waiting
        self.assertEqual(self.announce_and_show(r, 1),
                         "Simon found their Paraglider (Oman Au Shrine)")
        self.assertEqual(self.announce_and_show(r, 2),
                         "Rupee Bundle sent to Simon by the server")

    def test_a_silent_delivery_keeps_its_ap_window(self):
        r = self.runtime("grant_actor")
        r.state["journal_announced"] = [0]                        # earlier session
        self.assertEqual(r._received_announcement(0), "present")

    def session(self, r):
        from botw_client.presentation_session import NativePresentationSession
        enqueued = []

        class Queue:
            def snapshot(self):
                return {"entries": [{"id": k, "status": "queued"} for k in enqueued]}

            def enqueue(self, key, title, description):
                enqueued.append(key)
                return {"id": key}

            def tick(self, backend):
                return "idle"

        s = NativePresentationSession.__new__(NativePresentationSession)
        s.store = type("S", (), {"queue": Queue()})()
        s.blocked_head = lambda: None
        s.backend = None
        return s, enqueued

    def test_the_session_holds_items_behind_a_pending_line_in_order(self):
        r = self.runtime()
        s, enqueued = self.session(r)
        ap = r.ap
        ap.received_items[3] = NetworkItem(5, 78, BOB, 1)
        ap.scouted_locations = {}
        state = {"display_queue": [0, 3], "location_display_queue": [], "shown": [],
                 "presentation_completed": [], "location_shown": [],
                 "location_presentation_completed": []}
        game = type("G", (), {"item_map": {}})()
        decisions = {0: "pending", 3: "present"}
        s.advance(state, ap, game, announce=decisions.get)
        self.assertEqual(enqueued, [])                            # 3 waits behind 0
        decisions[0] = "skip"
        s.advance(state, ap, game, announce=decisions.get)
        self.assertEqual(enqueued, ["received/3"])
        self.assertEqual((state["display_queue"], state["presentation_completed"]), ([3], [0]))

    def test_a_location_sent_to_another_player_has_no_ap_window(self):
        from botw_client.protocol import LocationInfo
        r = self.runtime()
        s, enqueued = self.session(r)
        ap = r.ap
        ap.scouted_locations = {30: LocationInfo(7, 30, ALICE, 1), 12: LocationInfo(6, 12, ME, 1)}
        state = {"display_queue": [1], "location_display_queue": [30, 12], "shown": [],
                 "presentation_completed": [], "location_shown": [],
                 "location_presentation_completed": []}
        game = type("G", (), {"item_map": {}})()
        s.advance(state, ap, game, announce=lambda index: "skip")
        self.assertEqual(enqueued, [])
        self.assertEqual(state["location_display_queue"], [])
        self.assertEqual(sorted(state["location_presentation_completed"]), [12, 30])
        self.assertEqual(state["presentation_completed"], [1])


if __name__ == "__main__":
    unittest.main()
