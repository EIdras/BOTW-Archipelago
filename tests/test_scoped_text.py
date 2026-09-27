"""Exercise the emitted gate against hostile labels and changed RPX contexts."""
from pathlib import Path
import re
import unittest
from unittest.mock import Mock
from tools.build_scoped_text import SCOPES, guard, scoped_source, verify_rpx
from tools.cemu.rpx import RPX, Rpx
from tools.cemu.mailbox import Cave


def execute_gate(source, stack):
    """Small interpreter for the read-only gate's instruction subset.

    Unsupported operations fail the test, particularly any write or game call.
    """
    registers = {1: 0}
    equal = False
    for line in source.splitlines():
        line = line.strip()
        if line.startswith(";"):
            continue
        op, *args = re.split(r"[ ,]+", line)
        if op == "addi":
            dst, src, value = args
            registers[int(dst[1:])] = registers[int(src[1:])] + int(value, 0)
        elif op in {"lwz", "lbz"}:
            dst, address = args
            offset, src = re.fullmatch(r"(0x[0-9a-f]+)\(r(\d+)\)", address).groups()
            pos = registers[int(src)] + int(offset, 0)
            size = 4 if op == "lwz" else 1
            registers[int(dst[1:])] = int.from_bytes(stack[pos:pos+size], "big")
        elif op == "cmpw":
            equal = registers[int(args[0][1:])] == registers[int(args[1][1:])]
        elif op == "cmpwi":
            equal = registers[int(args[0][1:])] == int(args[1], 0)
        elif op == "bne":
            if not equal:
                return False
        else:
            raise AssertionError(f"unexpected instruction: {line}")
    return True


class ScopedTextTests(unittest.TestCase):
    def test_cleanup_cannot_hide_unconsumed_text(self):
        from tools.cemu.scoped_text import assess_text
        evidence = dict(samples=[dict(substitution=(0, 0, 0, 0, 0))], before_cleanup=[
            dict(substitution=(0, 2, 0, 2, 0)), dict(substitution=(0, 4, 0, 4, 0))])
        self.assertEqual(assess_text(evidence)["status"], "collected")
        evidence["before_cleanup"][1]["substitution"] = (1, 3, 2, 2, 0)
        self.assertEqual(assess_text(evidence)["status"], "needs_review")
        evidence["before_cleanup"][1]["substitution"] = (0, 3, 0, 2, 0)
        self.assertEqual(assess_text(evidence)["status"], "needs_review")

    def test_utf16_units_and_invalid_pair_never_partially_arms(self):
        memory = Mock()
        cave = Cave(memory, 0x1000, 0)
        cave.show_item_text("A\U0001f600", "B\U0001f600")
        memory.write.assert_any_call(cave.sub_len, (3).to_bytes(4, "big"))
        memory.write.assert_any_call(cave.sub_desc_len, (3).to_bytes(4, "big"))
        for description, n in (("X" * 256, 2), ("\ud800", 2), ("bad\0text", 2),
                               ("valid", -1), ("valid", 1 << 32)):
            memory.reset_mock()
            with self.assertRaises((ValueError, UnicodeError)):
                cave.show_item_text("valid", description, n)
            memory.write.assert_not_called()

    def test_exact_label_only_and_no_pointer_chasing(self):
        for _, offset, storage, label, end, _ in SCOPES:
            code = guard(offset, storage, label, end)
            stack = bytearray(0x288)
            stack[offset:offset+4] = storage.to_bytes(4, "big")
            stack[storage:storage+len(label)] = label
            self.assertTrue(execute_gate(code, stack))
            # Includes a changed suffix and non-NUL terminator (prefix attack).
            for index, original in enumerate(label):
                for value in range(256):
                    if value == original:
                        continue
                    stack[storage+index] = value
                    self.assertFalse(execute_gate(code, stack))
                stack[storage+index] = original
            for ptr in (0, 1, storage+1, 0xFFFFFFFF):
                stack[offset:offset+4] = ptr.to_bytes(4, "big")
                self.assertFalse(execute_gate(code, stack))

    @unittest.skipUnless(RPX.is_file(), "requires the game's U-King.rpx at the project's root")
    def test_rpx_context_and_fail_closed_on_change(self):
        rpx = Rpx()
        evidence = verify_rpx(rpx)
        self.assertIn("030835b8", evidence)
        class Changed:
            def read(self, address, count):
                raw = rpx.read(address, count)
                return bytes(count) if address == 0x03083850 else raw
        with self.assertRaisesRegex(ValueError, "03083850|0x3083850"):
            verify_rpx(Changed())

    def test_legacy_is_immutable_and_each_gate_precedes_consumption(self):
        root = Path(__file__).resolve().parents[1]
        raw = (root / "native/cemu/legacy/patch_apInject.asm").read_bytes()
        candidate = scoped_source(raw).decode()
        for _, offset, storage, label, end, request in SCOPES:
            self.assertIn(guard(offset, storage, label, end) +
                          f"    lwz   r12, {request}@l(r11)", candidate)
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            scoped_source(raw + b"\n")


if __name__ == "__main__":
    unittest.main()
