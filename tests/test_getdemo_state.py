import unittest
from tools.cemu.getdemo_state import snapshot, close_trace, close_trace_address, MGR_PTR, SCR_PTR


class UiOracleTests(unittest.TestCase):
    def test_close_trace_is_located_and_validated_before_reading_caller(self):
        log = "Applying patch group 'BOTW_AP_UICloseTrace_V208' (Codecave: 01806000-01806050)"
        self.assertEqual(close_trace_address(log), 0x01806000)
        self.assertIsNone(close_trace_address("other group"))
        class Memory:
            def read(self, address, size):
                return bytes.fromhex("4150554900000001000000020234be44")
        self.assertEqual(close_trace(Memory(), 0, 0x01806000),
                         {"close_count": 2, "last_close_return_address": 0x0234be44})
        class Wrong:
            def read(self, address, size):
                return bytes(size)
        with self.assertRaisesRegex(ValueError, "signature mismatch"):
            close_trace(Wrong(), 0, 0x01806000)

    def test_reads_correct_manager_and_screen_without_write_api(self):
        memory = {}
        def put(address, value):
            memory[address] = value.to_bytes(4, "big")
        put(MGR_PTR, 0x11000000)
        put(0x11000020, 0x12000000)
        put(0x11000028, 64)
        memory[0x12000000] = b"Item_Fruit_A\0".ljust(64, b"\0")
        put(SCR_PTR, 0x13000000)
        put(0x13000018, 0x14000000)
        put(0x1400002C, 0x15000000)
        memory[0x1300060F] = b"\x01"
        class ReadOnly:
            def read(self, address, size):
                return memory[address][:size]
        result = snapshot(ReadOnly(), 0)
        self.assertEqual(result["name"], "Item_Fruit_A")
        self.assertTrue(result["screen_active"])
        memory[0x1300060F] = b"\xff"
        self.assertFalse(snapshot(ReadOnly(), 0)["screen_active"])

    def test_uninitialized_manager_is_not_reported_as_open(self):
        class Empty:
            def read(self, address, size):
                return bytes(size)
        self.assertFalse(snapshot(Empty(), 0)["screen_active"])

    def test_partial_reads_fail_instead_of_inventing_state(self):
        class Partial:
            def read(self, address, size):
                return b""
        with self.assertRaisesRegex(RuntimeError, "short UI read"):
            snapshot(Partial(), 0)
