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


if __name__ == "__main__":
    unittest.main()
