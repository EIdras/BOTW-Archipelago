"""Regression coverage for cross-game item identity and received-item ordering."""
import unittest
from botw_client.protocol import ArchipelagoClient, LocationInfo, NetworkItem


class MultiworldProtocolTests(unittest.IsolatedAsyncioTestCase):
    def client(self):
        c = ArchipelagoClient("localhost:38281", "Tester", log=lambda _: None)
        c.slot = 1
        c.slot_info = {1: {"game": c.game}, 2: {"game": "Other Game"}}
        c.players = {1: "Tester", 2: "Friend"}
        c.commands = []
        async def send(*commands):
            c.commands.extend(commands)
        c.send = send
        return c

    async def test_ids_are_scoped_by_recipient_game_for_scouts(self):
        c = self.client()
        await c._packet({"cmd": "DataPackage", "data": {"games": {
            c.game: {"item_name_to_id": {"Magnesis": 5}, "location_name_to_id": {}},
            "Other Game": {"item_name_to_id": {"Hookshot": 5}, "location_name_to_id": {"Chest": 7}}
        }}})
        self.assertEqual(c.item_name(LocationInfo(5, 100, 2, 1)), "Hookshot")
        # For ReceivedItems, player is the sender, not the item's game.
        self.assertEqual(c.item_name(NetworkItem(5, 7, 2, 1)), "Magnesis")
        self.assertEqual(c.render_node({"type": "item_id", "text": "5", "player": 2}), "Hookshot")
        self.assertEqual(c.render_node({"type": "location_id", "text": "7", "player": 2}), "Chest")

    async def test_empty_initial_inventory_is_ready_at_data_package_barrier(self):
        c = self.client()
        c.connected = True
        self.assertFalse(c.items_synchronized)
        await c._packet({"cmd": "DataPackage", "data": {"games": {
            c.game: {"item_name_to_id": {}, "location_name_to_id": {}}}}})
        self.assertTrue(c.items_synchronized)
        self.assertEqual(c.received_items, {})
        await c._packet({"cmd": "ReceivedItems", "index": 0,
                         "items": [[1, 1, 2, 0]]})
        self.assertEqual(len(c.received_items), 1)

    async def test_initial_gap_stays_unsynchronized_at_data_package_barrier(self):
        c = self.client()
        c.connected = True
        await c._packet({"cmd": "ReceivedItems", "index": 2,
                         "items": [[1, 1, 2, 0]]})
        await c._packet({"cmd": "DataPackage", "data": {"games": {
            c.game: {"item_name_to_id": {}, "location_name_to_id": {}}}}})
        self.assertFalse(c.items_synchronized)
        self.assertEqual(c.commands[-1], {"cmd": "Sync"})

    async def test_gap_requests_sync_and_does_not_publish_partial_inventory(self):
        c = self.client()
        await c._packet({"cmd": "ReceivedItems", "index": 0, "items": [[1, 1, 1, 0]]})
        await c._packet({"cmd": "ReceivedItems", "index": 3, "items": [[2, 2, 1, 0]]})
        self.assertFalse(c.items_synchronized)
        self.assertNotIn(3, c.received_items)
        self.assertEqual(c.commands[-1], {"cmd": "Sync"})

    async def test_duplicate_packet_is_idempotent_and_conflicting_overlap_resyncs(self):
        c = self.client()
        await c._packet({"cmd": "ReceivedItems", "index": 0, "items": [[1, 1, 1, 0], [2, 2, 1, 0]]})
        await c._packet({"cmd": "ReceivedItems", "index": 1, "items": [[2, 2, 1, 0]]})
        self.assertTrue(c.items_synchronized)
        self.assertEqual(len(c.received_items), 2)
        await c._packet({"cmd": "ReceivedItems", "index": 1, "items": [[3, 2, 1, 0]]})
        self.assertFalse(c.items_synchronized)
        self.assertEqual(c.received_items[1].item, 2)

    async def test_index_zero_replaces_inventory_after_rollback(self):
        c = self.client()
        await c._packet({"cmd": "ReceivedItems", "index": 0, "items": [[1, 1, 1, 0], [2, 2, 1, 0]]})
        await c._packet({"cmd": "ReceivedItems", "index": 0, "items": [[3, 3, 1, 0]]})
        self.assertTrue(c.items_synchronized)
        self.assertEqual(c.received_items, {0: NetworkItem(3, 3, 1, 0)})
