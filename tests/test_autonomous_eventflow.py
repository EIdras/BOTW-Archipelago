import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from tools.cemu import autonomous_eventflow as event
from tools.cemu.rpx import RPX


class AutonomousTests(unittest.TestCase):
    @unittest.skipUnless(RPX.is_file(), "requires the game's U-King.rpx at the project's root")
    def test_manager_pointer_matches_rpx_signed_address(self):
        from tools.cemu.rpx import Rpx
        raw = Rpx().read(event.HELPER + 0x24, 8)
        high = int.from_bytes(raw[2:4], "big") << 16
        low = int.from_bytes(raw[6:8], "big", signed=True)
        self.assertEqual(event.MANAGER_PTR, high + low)

    @patch.object(event, "inspect", return_value={"manager": 30, "manager_available": False})
    @patch.object(event, "snapshot", return_value={"screen": 0, "name": "", "manager": 1})
    def test_unavailable_manager_is_reported_before_any_write(self, *_):
        process, cave = self.setup_request()
        records = []
        with self.assertRaises(RuntimeError):
            event.request(process, cave, 1, lambda value: records.append(dict(value)))
        self.assertEqual(records[-1]["status"], "not_ready")
        self.assertEqual(records[-1]["before"]["manager"], 30)
        process.write.assert_not_called()

    def setup_request(self, acknowledge=True):
        memory = {1: 0, 2: 0, 3: 12, 4: 1}
        process = Mock()
        process.read.side_effect = lambda address, size: memory[address].to_bytes(size, "big")
        cave = SimpleNamespace(base=0, pf_req=1, opn_req=2, call_n=3, call_ret=4,
            text_buf=0x1800000, pf_ready=lambda: True, ui_ready=lambda: True,
            sub_state=lambda: (0, 0, 0, 0, 0), guest=lambda p: p)
        def invoke(*args):
            if acknowledge:
                memory[3] += 1
        cave.call_pf = Mock(side_effect=invoke)
        cave.show_item_text = Mock()
        cave.sub_disarm = Mock()
        return process, cave

    @patch("tools.cemu.scoped_text.verify_gates", return_value=[{"verified": True}])
    @patch.object(event, "inspect", return_value={"manager": 0x40000000, "manager_available": True})
    @patch.object(event, "snapshot", return_value={"screen": 0, "name": "", "manager": 1})
    def test_text_is_armed_before_launch_and_disarmed_on_refusal(self, *_):
        process, cave = self.setup_request()
        def reject(*args):
            cave.show_item_text.assert_called_once_with("Test Archipelago 2", "Message numero 2.\nAffichage par EventFlow.")
            process.read.side_effect = lambda address, size: ({1: 0, 2: 0, 3: 13, 4: 0}[address]).to_bytes(size, "big")
        cave.call_pf.side_effect = reject
        result = event.request(process, cave, 2, Mock(), custom_text=True)
        self.assertEqual(result["native_return"], 0)
        cave.sub_disarm.assert_called_once()

    @patch("tools.cemu.scoped_text.verify_gates", side_effect=ValueError("gate absent"))
    @patch.object(event, "inspect", return_value={"manager_available": True})
    @patch.object(event, "snapshot", return_value={"screen": 0, "name": "", "manager": 1})
    def test_legacy_text_refused_without_any_write(self, *_):
        process, cave = self.setup_request()
        with self.assertRaisesRegex(ValueError, "gate absent"):
            event.request(process, cave, 1, Mock(), custom_text=True)
        process.write.assert_not_called()
        cave.show_item_text.assert_not_called()
        cave.call_pf.assert_not_called()

    @patch.object(event, "inspect", return_value={"manager": 0x40000000, "manager_available": True})
    @patch.object(event, "snapshot", return_value={"screen": 0, "name": "", "manager": 1})
    def test_only_launch_wrapper_called(self, *_):
        process, cave = self.setup_request()
        checkpoint = Mock()
        result = event.request(process, cave, 1, checkpoint)
        cave.call_pf.assert_called_once_with(event.HELPER, 0, 0x18000c0, 0x18000c8, 1, 0)
        self.assertEqual(result["native_return"], 1)
        self.assertEqual(checkpoint.call_count, 3)
        process.write.assert_any_call(cave.pf_req, bytes(4))

    @patch.object(event, "inspect", return_value={"manager": 0x40000000, "manager_available": True})
    @patch.object(event, "snapshot", return_value={"screen": 0, "name": "", "manager": 1})
    def test_dynamic_delivery_entry_uses_bounded_native_strings(self, *_):
        process, cave = self.setup_request()
        result = event.request(process, cave, 7, Mock(),
                               flow="Demo007_1", entry="APD_12345678_00")
        self.assertEqual((result["flow"], result["entry"]),
                         ("Demo007_1", "APD_12345678_00"))
        process.write.assert_any_call(cave.text_buf, b"Demo007_1\0")
        process.write.assert_any_call(cave.text_buf + 0x40,
                                      b"APD_12345678_00\0")

    def test_dynamic_entry_validation_happens_before_process_access(self):
        process, cave = self.setup_request()
        with self.assertRaisesRegex(ValueError, "native buffer"):
            event.request(process, cave, 1, Mock(), entry="x" * 64)
        process.read.assert_not_called()

    @patch.object(event, "inspect", return_value={"manager": 0x40000000, "manager_available": True})
    @patch.object(event, "snapshot", return_value={"screen": 1, "name": "", "manager": 1})
    def test_busy_window_causes_no_writes(self, *_):
        process, cave = self.setup_request()
        with self.assertRaises(RuntimeError):
            event.request(process, cave, 1, Mock())
        process.write.assert_not_called()

    @patch.object(event, "inspect", return_value={"manager": 0x40000000, "manager_available": True})
    @patch.object(event, "snapshot", return_value={"screen": 0, "name": "", "manager": 1})
    def test_timeout_cancels_pending_call(self, *_):
        process, cave = self.setup_request(False)
        with patch.object(event.time, "monotonic", side_effect=[0, 4]):
            with self.assertRaises(RuntimeError):
                event.request(process, cave, 1, Mock())
        process.write.assert_any_call(cave.pf_req, bytes(4))
