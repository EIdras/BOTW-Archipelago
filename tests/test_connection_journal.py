"""AP connection status in the in-game journal: one line per outage."""
import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from botw_client.runtime import BotwClientRuntime, offline_duration


class DurationTests(unittest.TestCase):
    def test_duration_reads_in_seconds_then_minutes(self):
        self.assertEqual(offline_duration(None), "")
        self.assertEqual(offline_duration(100.0, 100.2), "after 1 s offline")
        self.assertEqual(offline_duration(100.0, 145.0), "after 45 s offline")
        self.assertEqual(offline_duration(100.0, 225.0), "after 2 min 05 s offline")


class OutageTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_loss_line_per_outage_then_one_reconnection_line(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = BotwClientRuntime(
                "localhost:1", "test", state_path=Path(folder) / "state.json",
                game_factory=Mock, log=lambda _: None, tip_factory=Mock())
            runtime.ap.connected = False
            attempts = []

            async def fail():
                attempts.append(1)
                if len(attempts) < 3:
                    raise ConnectionError("refused")
                runtime.ap.connected = True

            async def close():
                pass

            runtime._connect_ap = fail
            runtime.ap.close = close
            runtime._wait_or_stop = lambda _delay: asyncio.sleep(0)
            for _ in range(12):
                await runtime._reconnect_tick()
                await asyncio.sleep(0)
                if runtime.ap.connected and runtime._reconnect_task is None:
                    break
            notes = [markup for markup, _ in runtime._journal_notes]
            self.assertEqual(len(attempts), 3)
            self.assertEqual(len(notes), 2, notes)
            self.assertIn("lost", notes[0])
            self.assertIn("Reconnected", notes[1])
            self.assertIn("offline", notes[1])
            self.assertIsNone(runtime._offline_since)


    async def test_console_outage_closes_and_delays_the_reconnection(self):
        with tempfile.TemporaryDirectory() as folder:
            logs = []
            runtime = BotwClientRuntime(
                "localhost:1", "test", state_path=Path(folder) / "state.json",
                game_factory=Mock, log=logs.append, tip_factory=Mock())
            closed = []

            async def close():
                closed.append(1)
                runtime.ap.connected = False

            runtime.ap.close = close
            runtime.ap.connected = True
            self.assertTrue(runtime.handle_local_command("/ap-disconnect 20"))
            await asyncio.sleep(0)
            self.assertEqual((closed, runtime._reconnect_delay), ([1], 20.0))
            self.assertTrue(runtime.handle_local_command("/ap-disconnect 0"))
            self.assertIn("Usage", logs[-1])

if __name__ == "__main__":
    unittest.main()
