import struct
import unittest
from tools.cemu.event_request_trace import read_trace, assess
from tools.build_event_request_trace import trace_source, MAGIC, CAPACITY, STRIDE


class Memory:
    def __init__(self, data):
        self.data = data

    def read(self, address, size):
        offset = address - 0x1800000
        return self.data[offset:offset + size]


class EventRequestTests(unittest.TestCase):
    def trace(self, descriptor=True):
        record = bytearray(512)
        struct.pack_into(">8I", record, 0, 1, 1, 0x02ddf80c, 0x40000000, 0x12000000, 0x40000000, 0, 0)
        struct.pack_into(">I", record, 32 + 0x34, 0x12000040 if descriptor else 0)
        record[128:138] = b"Demo007_1\0"
        record[204:214] = b"Demo007_1\0"
        return Memory(struct.pack(">8I", MAGIC, 1, 128, 512, 1, 0, 0, 0) + record)

    def test_stack_descriptor_is_copied_not_dereferenced_later(self):
        result = read_trace(self.trace(), 0, 0x1800000)
        self.assertEqual(result["events"][0]["descriptor_name_candidate"], "Demo007_1")
        self.assertEqual(result["events"][0]["descriptor_entry_candidate"], "Demo007_1")

    def test_null_descriptor_is_allowed(self):
        result = read_trace(self.trace(False), 0, 0x1800000)
        self.assertIsNone(result["events"][0]["descriptor_hex"])

    def test_truncated_read_fails(self):
        memory = self.trace()
        memory.data = memory.data[:-1]
        with self.assertRaisesRegex(RuntimeError, "short"):
            read_trace(memory, 0, 0x1800000)

    def test_each_exit_captures_manager_once_and_never_copies_dead_request(self):
        source = trace_source()
        for index in (2, 3):
            body = source.split(f"apEvent{index}:")[1].split(f"apEvent{index}Full:")[0]
            self.assertEqual(body.count("stw r0, 376(r10)"), 1)
            self.assertNotIn("lwz r12, 0x34(r4)", body)
        self.assertNotIn("bl ", source)

    def test_buffer_allocation_matches_capacity(self):
        words = trace_source().split("apEventData:\n")[1].split("; request_enter")[0].splitlines()
        self.assertEqual(len(words), 8 + CAPACITY * STRIDE // 4)

    def test_visual_success_cannot_hide_overflow_or_missing_target(self):
        result = assess(dict(status="collected", dropped=116, events=[]))
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(len(result["reasons"]), 2)

    def test_observed_target_is_distinct_from_event_completion(self):
        result = assess(dict(status="collected", dropped=0, events=[
            dict(sequence=201, descriptor_name_candidate="Demo007_1")]))
        self.assertEqual(result["status"], "collected")
        self.assertEqual(result["target_sequences"], [201])


if __name__ == "__main__":
    unittest.main()
