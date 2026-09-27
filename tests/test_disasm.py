import unittest

from tools.cemu.disasm import disasm


class DialoguePredicateDisassemblyTests(unittest.TestCase):
    def test_dialogue_equality_predicate_has_correct_registers_and_mask(self):
        # Actual Wii U v208 words at 035fdbb0, 035fdbb8, 035fdbc4.
        self.assertEqual(disasm(0x680B0003, 0), 'xori r11, r0, 0x3')
        self.assertEqual(disasm(0x7D6C0034, 0), 'cntlzw r12, r11')
        self.assertEqual(disasm(0x5583D97E, 0), 'rlwinm r3, r12, 27, 5, 31')

    def test_record_form_and_action_failure_mask_are_explicit(self):
        self.assertEqual(disasm(0x7D6C0035, 0), 'cntlzw. r12, r11')
        self.assertEqual(disasm(0x5583D97F, 0), 'rlwinm. r3, r12, 27, 5, 31')
        self.assertEqual(disasm(0x540C063C, 0), 'rlwinm r12, r0, 0, 24, 30')
