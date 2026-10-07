"""Items a reloaded save lost: given back silently, named in one AP summary."""
from __future__ import annotations

import asyncio
import unittest

from botw_client.backend import DeliveryResult, DeliveryStatus
from botw_client.protocol import NetworkItem
from botw_client.runtime import replay_summary_lines


class LayoutTests(unittest.TestCase):
    def test_counts_order_and_overflow(self):
        self.assertEqual(replay_summary_lines(["Zora Set", "Korok Seed", "Korok Seed"]),
                         ["Zora Set, Korok Seed x2"])
        many = [f"Item number {n}" for n in range(20)]
        lines = replay_summary_lines(many)
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(len(line) <= 40 for line in lines))
        self.assertRegex(lines[-1], r"and \d+ more$")
        shown = sum(line.count("Item") for line in lines)
        self.assertEqual(int(lines[-1].rsplit("and ", 1)[1].split()[0]), 20 - shown)


class Backend:
    """Commits whatever it is asked, records the commands."""

    def __init__(self, runtime, catalog):
        self.runtime, self.catalog, self.commands = runtime, catalog, []

    def checkpoint(self):
        return type("C", (), {"cursor": self.runtime.cursor, "seed": "s", "slot": 1})()


class Catalog:
    def steps(self, name, before):
        quiet = None if name == "Heart Container" else "APD_Q"
        return [{"entry": "APD", "quiet_entry": quiet, "mutations": []}]


def runtime():
    from botw_client.runtime import BotwClientRuntime

    class Ap:
        items_synchronized = True
        received_items = {0: NetworkItem(1, -1, 2, 0), 1: NetworkItem(2, -1, 2, 0),
                          2: NetworkItem(3, -1, 2, 0)}

        def item_name(self, item):
            return {1: "Zora Set", 2: "Heart Container", 3: "Korok Seed"}[item.item]

    class Store:
        def save(self):
            pass

    r = BotwClientRuntime.__new__(BotwClientRuntime)
    r.ap, r.state_store, r.log = Ap(), Store(), lambda *_: None
    r.native_delivery, r.native_presentations = True, True
    r._native_delivery_retry_after = 0.0
    r._session_identity = ("s", 0, 1, "p")
    r._received_before = lambda index, name: 0
    r._message_blocks_items = lambda: False
    r._discover_received = lambda: None
    r.cursor = 0
    backend = Backend(r, Catalog())

    class Deliveries:
        def deliver(self, command):
            backend.commands.append(command)
            r.cursor = (command.index + 1) << 8
            return DeliveryResult(DeliveryStatus.APPLIED, r.cursor, "")

    r.deliveries = Deliveries()
    r.deliveries.backend = backend
    r.state = {"apply_queue": [0, 1, 2], "presentation_completed": [0, 1, 2],
               "delivered_high": 2}
    return r, backend


class ReplayTests(unittest.TestCase):
    def test_items_below_the_highest_delivery_come_back_silently_then_one_summary(self):
        r, backend = runtime()
        for _ in range(3):
            asyncio.run(r._apply_one_received_native())
            r.state["apply_queue"].pop(0)
            r._flush_replay_summary()
            if r.state.get("summary_queue"):
                break
        self.assertEqual([c.quiet for c in backend.commands], [True, True])
        # Hearts have no silent delivery: their own window, not in the summary.
        self.assertEqual(r.state["summary_queue"], [{
            "key": "summary/1", "title": "Items restored", "lines": ["Zora Set"]}])
        asyncio.run(r._apply_one_received_native())      # index 2: new, not given back
        self.assertFalse(backend.commands[-1].quiet)

    def test_a_new_reload_supersedes_a_summary_not_yet_shown(self):
        # Seen in play: a reload's window still waiting, then another reload;
        # the first was shown, then the items it named came back again.
        r, _backend = runtime()
        asked = []

        class Session:
            def withdraw(self, key):
                asked.append(key)
                return key != "summary/2"           # summary/2: already submitted

        r.presentations = Session()
        r.state.update(summary_queue=[
            {"key": "summary/1", "title": "Items restored", "lines": ["Zora Set"]},
            {"key": "summary/2", "title": "Items restored", "lines": ["Korok Seed"]},
            {"key": "summary/3", "title": "Items received", "lines": ["Korok Seed"]}],
            replay_batch=[])
        r._flush_replay_summary()
        self.assertEqual(asked, ["summary/1", "summary/2"])
        self.assertEqual([s["key"] for s in r.state["summary_queue"]], ["summary/2", "summary/3"])
        # Nothing given back: a waiting window stays.
        r.state["apply_queue"] = [5]
        asked.clear()
        r._flush_replay_summary()
        self.assertEqual(asked, [])

    def test_the_session_presents_the_summary_and_forgets_it_once_shown(self):
        from botw_client.presentation_session import NativePresentationSession
        enqueued, done = [], set()

        class Queue:
            def snapshot(self):
                return {"entries": [{"id": k, "status": "completed" if k in done else "queued"}
                                    for k in enqueued]}

            def enqueue(self, key, title, description):
                enqueued.append(key)
                return {"id": key}

            def tick(self, backend):
                return "idle"

        s = NativePresentationSession.__new__(NativePresentationSession)
        s.store = type("S", (), {"queue": Queue()})()
        s.blocked_head, s.backend = (lambda: None), None
        state = {"summary_queue": [{"key": "summary/1", "title": "Items restored",
                                    "lines": ["Zora Set"]}],
                 "display_queue": [], "location_display_queue": [], "shown": [],
                 "presentation_completed": [], "location_shown": [],
                 "location_presentation_completed": []}
        ap = type("A", (), {"received_items": {}, "scouted_locations": {}, "slot": 1})()
        game = type("G", (), {"item_map": {}})()
        s.advance(state, ap, game)
        self.assertEqual(enqueued, ["summary/1"])
        done.add("summary/1")
        s.advance(state, ap, game)
        self.assertEqual(state["summary_queue"], [])


class BulkTests(unittest.TestCase):
    """A release or a collect: its items come quietly, named in one AP window;
    a trap still strikes, a rune keeps its screen."""

    def test_the_protocol_times_live_items_and_records_the_notices(self):
        from botw_client.protocol import ArchipelagoClient
        ap = ArchipelagoClient("localhost:1", "test", log=lambda *_: None)
        ap.slot, ap.items_synchronized = 2, True
        item = [1, 5, 3, 0]
        asyncio.run(ap._packet({"cmd": "ReceivedItems", "index": 0, "items": [item]}))
        self.assertEqual(ap.received_at, {})              # a connection's items: not live
        asyncio.run(ap._packet({"cmd": "ReceivedItems", "index": 1, "items": [item, item]}))
        self.assertEqual(sorted(ap.received_at), [1, 2])
        for kind, slot in (("Release", 3), ("Collect", 4), ("Collect", 2), ("Goal", 2)):
            asyncio.run(ap._packet({"cmd": "PrintJSON", "type": kind, "slot": slot,
                                    "data": [{"text": kind}]}))
        self.assertEqual([world for _at, world in ap.bulk_notices], [3, None])

    def bulk_runtime(self):
        r, backend = runtime()
        names = {1: "Zora Set", 2: "Heart Container", 3: "Korok Seed", 4: "Rupoor", 5: "Stasis"}
        r.ap.item_name = lambda item: names[item.item]
        r.ap.slot = 1
        # 0: sent by world 2 with its release, 1: by world 3 at the same time,
        # 2: by world 2 a minute before; 3, 4: a trap and a rune of the release.
        r.ap.received_items = {0: NetworkItem(1, 10, 2, 0), 1: NetworkItem(3, 11, 3, 0),
                               2: NetworkItem(3, 12, 2, 0), 3: NetworkItem(4, 13, 2, 0),
                               4: NetworkItem(5, 14, 2, 0)}
        r.ap.received_at = {0: 100.0, 1: 100.0, 2: 40.0, 3: 100.0, 4: 100.0}
        r.ap.bulk_notices = [(101.0, 2)]
        r.game = type("G", (), {"item_map": {
            "Rupoor": {"delivery": {"kind": "trap"}}, "Stasis": {"delivery": {"kind": "rune"}}}})()
        r.state.update(apply_queue=[0, 1, 2, 3, 4], presentation_completed=[0, 1, 2, 3, 4],
                       delivered_high=0, message_queue=[])
        return r, backend

    def test_a_release_marks_the_items_of_its_world_that_came_with_it(self):
        r, _backend = self.bulk_runtime()
        r._mark_bulk()
        # The trap and the rune are marked, but keep their presentation.
        self.assertEqual(r.state["bulk"], [0, 3, 4])
        self.assertEqual([i for i in range(5) if r._bulk(i)], [0])

    def test_a_collect_marks_every_item_that_came_with_it(self):
        r, _backend = self.bulk_runtime()
        r.ap.bulk_notices = [(99.0, None)]
        r._mark_bulk()
        self.assertEqual([i for i in range(5) if r._bulk(i)], [0, 1])

    def test_released_items_come_quietly_then_one_summary(self):
        r, backend = self.bulk_runtime()
        r.ap.bulk_notices = [(99.0, None)]
        r._mark_bulk()
        r.state["apply_queue"] = [0, 1, 3]
        for _ in range(2):
            asyncio.run(r._apply_one_received_native())
            r.state["apply_queue"].pop(0)
        r._flush_replay_summary()
        self.assertEqual([c.quiet for c in backend.commands], [True, True])
        self.assertEqual(r.state["summary_queue"], [{
            "key": "summary/1", "title": "Items received", "lines": ["Zora Set, Korok Seed"]}])
        self.assertEqual(r.state.get("replay_batch", []), [])

    def test_the_journal_says_once_that_released_items_are_coming(self):
        r, _backend = self.bulk_runtime()
        notes = []
        r._journal_note = lambda markup, tag=None: notes.append(markup)
        r.ap.bulk_notices = [(99.0, None)]
        r._mark_bulk()
        r.state["apply_queue"] = [0, 1, 3]
        for _ in range(2):
            asyncio.run(r._apply_one_received_native())
            r.state["apply_queue"].pop(0)
        self.assertEqual(notes, ["{1}2 items{/} of a release on their way, listed once all are given"])

    def test_a_trap_between_released_items_does_not_split_the_summary(self):
        r, backend = self.bulk_runtime()
        items = r.ap.received_items
        items[1], items[3] = items[3], items[1]      # the trap at 1, between two items
        r.ap.received_at[2] = 100.0
        r.ap.bulk_notices = [(99.0, None)]
        r._mark_bulk()
        r.state["apply_queue"] = [0, 1, 2]
        for _ in range(3):
            asyncio.run(r._apply_one_received_native())
            r.state["apply_queue"].pop(0)
            r._flush_replay_summary()
        self.assertEqual([c.quiet for c in backend.commands], [True, False, True])
        self.assertEqual(r.state["summary_queue"], [{
            "key": "summary/1", "title": "Items received", "lines": ["Zora Set, Korok Seed"]}])

    def test_an_item_without_a_window_of_its_own_is_named_too(self):
        r, backend = self.bulk_runtime()
        r.ap.bulk_notices = [(99.0, None)]
        r._mark_bulk()
        r.deliveries.backend.catalog = type("C", (), {
            "data": {"flow": "Demo007_1"},
            "steps": lambda self, name, before: [{"entry": "APD", "flow": "OperationGuide",
                                                  "mutations": []}]})()
        r.state["apply_queue"] = [0, 1]
        for _ in range(2):
            asyncio.run(r._apply_one_received_native())
            r.state["apply_queue"].pop(0)
        r._flush_replay_summary()
        self.assertEqual(r.state["summary_queue"][0]["lines"], ["Zora Set, Korok Seed"])

    def test_a_released_item_has_no_line_nor_window(self):
        r, _backend = self.bulk_runtime()
        r._mark_bulk()
        line = {"kind": "ItemSend", "receiving": 1, "sender": 2,
                "nodes": [{"type": "item_id", "text": "1"}, {"type": "location_id", "text": "10"}]}
        other = dict(line, sender=3, nodes=[{"type": "item_id", "text": "3"},
                                            {"type": "location_id", "text": "11"}])
        r.state["message_queue"] = [line, other]
        self.assertEqual(r._received_announcement(0), "skip")
        self.assertEqual(r.state["message_queue"], [other])
        self.assertTrue(r._bulk_line(line))
        self.assertFalse(r._bulk_line(other))


if __name__ == "__main__":
    unittest.main()
