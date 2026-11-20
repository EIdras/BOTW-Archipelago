"""PopTracker told where Link is, through UAT (botw_client/uat.py)."""
import asyncio
import json
import socket
import unittest

from botw_client import uat


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Areas:
    def region_at(self, x, z):
        return "Hebra" if x < 0 else None


class UatTests(unittest.TestCase):
    def test_a_tracker_gets_info_then_the_variables_then_each_change(self):
        async def run():
            import aiohttp
            port = free_port()
            server = uat.UatServer(version="0.4.0", log=lambda text: None, ports=(port,), hosts=("127.0.0.1",))
            self.assertEqual(await server.start(), port)
            await server.set(region="Hebra", x=-1200, z=300)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(f"ws://127.0.0.1:{port}") as socket_:
                        info, = json.loads((await socket_.receive()).data)
                        self.assertEqual((info["cmd"], info["protocol"], info["name"]),
                                         ("Info", 0, "Breath of the Wild Archipelago"))
                        await socket_.send_str(json.dumps([{"cmd": "Sync"}]))
                        synced = json.loads((await socket_.receive()).data)
                        self.assertEqual({var["name"]: var["value"] for var in synced},
                                         {"region": "Hebra", "x": -1200, "z": 300})
                        await server.set(region="Hebra", x=-1150, z=300)     # only what changed
                        self.assertEqual(json.loads((await socket_.receive()).data),
                                         [{"cmd": "Var", "name": "x", "value": -1150}])
                        await socket_.send_str(json.dumps([{"cmd": "Hello"}]))
                        reply, = json.loads((await socket_.receive()).data)
                        self.assertEqual((reply["cmd"], reply["reason"]), ("ErrorReply", "unknown cmd"))
            finally:
                await server.close()
        asyncio.run(run())

    def test_a_busy_port_is_logged_and_the_session_goes_on(self):
        async def run():
            port = free_port()
            first = uat.UatServer(log=lambda text: None, ports=(port,), hosts=("127.0.0.1",))
            said = []
            second = uat.UatServer(log=said.append, ports=(port,), hosts=("127.0.0.1",))
            try:
                self.assertEqual(await first.start(), port)
                self.assertIsNone(await second.start())
                self.assertIn("no port to listen at", said[0])
            finally:
                await first.close()
                await second.close()
        asyncio.run(run())

    def test_whereabouts_only_in_the_main_field(self):
        self.assertEqual(uat.whereabouts(True, (-1200.4, 150.0, 300.6), Areas()),
                         {"region": "Hebra", "x": -1200, "z": 301})
        self.assertEqual(uat.whereabouts(True, (50.0, 0.0, 0.0), Areas())["region"], "")
        self.assertIsNone(uat.whereabouts(False, (-1200.0, 0.0, 0.0), Areas()))
        self.assertIsNone(uat.whereabouts(True, None, Areas()))
        self.assertEqual(uat.whereabouts(True, (-1200.0, 0.0, 300.0), Areas(), 359.6)["heading"], 0)

    def test_the_room_hears_of_a_move_a_turn_or_a_region_seldom(self):
        now = [0.0]
        room = uat.RoomThrottle(lambda: now[0])
        here = {"region": "Hebra", "x": 0, "z": 0, "heading": 350}
        self.assertTrue(room.due(here))
        room.sent(here)
        now[0] = 1.0
        self.assertFalse(room.due(dict(here, x=500)))             # too soon
        now[0] = 3.0
        self.assertFalse(room.due(dict(here, x=30, heading=10)))  # a step, a small turn
        self.assertTrue(room.due(dict(here, heading=15)))         # 25 degrees round north
        self.assertTrue(room.due(dict(here, x=60)))
        self.assertTrue(room.due(dict(here, region="Tabantha")))


if __name__ == "__main__":
    unittest.main()
