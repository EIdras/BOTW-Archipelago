import unittest

from tools.cemu.rpx import RPX

from botw_patch.message_flow import MARKER
from tests.ppc_owner_model import PpcOwnerModel
from tools.build_message_action import source, SITES


class MessageActionTests(unittest.TestCase):
    def model(self):
        m = PpcOwnerModel(source())
        self.header = m.labels['apMessageData']
        self.set(m, 8, 1)
        self.set(m, 12, 7)
        self.set(m, 20, 0x43000000)
        self.set(m, 40, 15)
        m.reg[26] = 0x44000000
        m.put(m.reg[26] + 16, 0x45000000)
        for i, byte in enumerate(MARKER.encode() + b'\0'):
            m.put(0x45000000 + i, byte, 1)
        return m

    def set(self, m, offset, value):
        m.put(self.header + offset, value)

    def get(self, m, offset):
        return m.get(self.header + offset)

    def bind(self, m):
        m.run('apMessageBind')

    def text(self, m):
        m.reg[31] = m.labels['apMessageArcSafe']
        m.reg[26] = m.labels['apMessageLabelSafe']
        m.reg[27] = 0x46000000
        m.run('apMessageText')

    def test_owned_action_injects_once_and_leave_is_not_final_ack(self):
        m = self.model()
        self.bind(m)
        self.assertEqual((self.get(m, 8), self.get(m, 16), self.get(m, 24)), (2, 0x44000000, 7))
        self.text(m)
        self.assertEqual(m.get(0x460001d0), m.labels['apMessageTextBuffer'])
        self.assertEqual(m.get(0x460001d4), 15)
        m.reg[31] = 0x44000000
        m.run('apMessageComplete')
        self.assertEqual(self.get(m, 28), 7)
        m.reg[3] = 0x44000000
        m.run('apMessageLeave')
        self.assertEqual((self.get(m, 8), self.get(m, 32)), (4, 7))
        self.assertEqual(m.get(0x460001d0), m.labels['apMessageTextBuffer'])

    def test_vanilla_marker_prefix_or_suffix_never_claims_or_changes_arguments(self):
        for text in [MARKER + 'x', MARKER[:-1], 'DemoMsg/Demo008_2:talk00']:
            m = self.model()
            for i, b in enumerate(text.encode() + b'\0'):
                m.put(0x45000000 + i, b, 1)
            before = dict(m.reg), m.cr, m.lr
            self.bind(m)
            self.assertEqual((dict(m.reg), m.cr, m.lr), before)
            self.assertEqual(self.get(m, 8), 1)
            self.assertEqual(self.get(m, 16), 0)

    def test_same_text_at_other_safe_string_addresses_cannot_inject(self):
        m = self.model()
        self.bind(m)
        m.reg[31], m.reg[26], m.reg[27] = 0x47000000, 0x48000000, 0x46000000
        m.put(m.reg[31], m.get(m.labels['apMessageArcSafe']))
        m.put(m.reg[26], m.get(m.labels['apMessageLabelSafe']))
        m.run('apMessageText')
        self.assertEqual((m.get(0x460001d0), self.get(m, 56)), (0, 0))

    def test_no_generation_or_executor_cannot_claim(self):
        for offset in (12, 20):
            m = self.model()
            self.set(m, offset, 0)
            self.bind(m)
            self.assertEqual((self.get(m, 8), self.get(m, 16)), (1, 0))
            self.assertEqual(m.reg[4], m.labels['apMessageArcSafe'])

    def test_duplicate_text_or_overflow_faults_without_second_screen_write(self):
        for duplicate in (False, True):
            m = self.model()
            self.bind(m)
            if duplicate:
                self.text(m)
            else:
                self.set(m, 40, 2048)
            m.writes.clear()
            self.text(m)
            self.assertEqual((self.get(m, 8), self.get(m, 52)), (8, 1))
            self.assertFalse(any(0x46000000 <= a < 0x46001000 for a, _, _ in m.writes))

    def test_unrelated_completion_is_ignored_and_early_leave_is_uncertain(self):
        m = self.model()
        self.bind(m)
        m.reg[31] = 0x44001000
        m.run('apMessageComplete')
        self.assertEqual(self.get(m, 8), 2)
        m.reg[3] = 0x44000000
        m.run('apMessageLeave')
        self.assertEqual((self.get(m, 8), self.get(m, 52)), (8, 1))

    def test_failed_atomic_reservation_never_injects(self):
        m = self.model()
        self.bind(m)
        m.fail_reservation = True
        self.text(m)
        self.assertEqual((m.get(0x460001d0), self.get(m, 52)), (0, 1))

    @unittest.skipUnless(RPX.is_file(), "requires the game's U-King.rpx at the project's root")
    def test_anchor_instructions_match_supported_rpx(self):
        from tools.cemu.rpx import Rpx
        rpx = Rpx()
        for site, word, _, _ in SITES:
            self.assertEqual(rpx.read(site, 4), word.to_bytes(4, 'big'))

    def complete(self, m):
        self.bind(m)
        self.text(m)
        m.reg[31] = 0x44000000
        m.run('apMessageComplete')

    def retire(self, m):
        m.reg[30], m.reg[26] = 0x43000000, 1
        m.run('apMessageExecutorTerminal')
        m.run('apMessageExecutorManager')
        m.reg[11] = 0x49000000
        m.put(m.reg[11], 0)
        m.run('apMessageExecutorRetired')

    def leave(self, m):
        m.reg[3] = 0x44000000
        m.run('apMessageLeave')

    def test_action_leave_and_executor_retirement_required_in_either_order(self):
        for retire_first in (True, False):
            m = self.model()
            self.complete(m)
            first, second = (self.retire, self.leave) if retire_first else (self.leave, self.retire)
            first(m)
            self.assertNotEqual(self.get(m, 8), 9)
            self.assertEqual(m.get(m.labels['apMessageJoinData'] + 12), 0)
            second(m)
            self.assertEqual(self.get(m, 8), 9)
            self.assertEqual(m.get(m.labels['apMessageJoinData'] + 12), 7)

    def test_wrong_or_abnormal_executor_never_acknowledges(self):
        for wrong in (True, False):
            m = self.model()
            self.complete(m)
            self.leave(m)
            m.reg[30] = 0x43001000 if wrong else 0x43000000
            m.reg[26] = 2
            m.run('apMessageExecutorTerminal')
            self.assertEqual(m.get(m.labels['apMessageJoinData'] + 12), 0)
            self.assertEqual(self.get(m, 52), 0 if wrong else 1)

    def test_retirement_without_manager_confirmation_cannot_finish(self):
        m = self.model()
        self.complete(m)
        self.leave(m)
        m.reg[30], m.reg[11] = 0x43000000, 0x49000000
        m.run('apMessageExecutorRetired')
        self.assertEqual((self.get(m, 8), self.get(m, 52)), (8, 1))

    def test_leave_after_retirement_never_reads_freed_executor(self):
        m = self.model()
        self.complete(m)
        self.retire(m)
        read = m.get
        def guarded(address, size=4):
            if 0x43000000 <= address < 0x43001000:
                self.fail('read freed executor')
            return read(address, size)
        m.get = guarded
        self.leave(m)
        self.assertEqual(self.get(m, 8), 9)
        # Pointer reuse after acknowledgment must not turn a finished request
        # into a fault when a vanilla action/executor uses the same addresses.
        m.run('apMessageExecutorTerminal')
        self.leave(m)
        self.assertEqual((self.get(m, 8), self.get(m, 52)), (9, 0))

    def test_creation_requires_exact_flow_and_entry_and_preserves_registers(self):
        for entry in ('APMessageStandalone', 'APDisplayStandalone', 'APMessageStandaloneExtra'):
            m = self.model()
            self.set(m, 20, 0)
            m.reg[3], m.reg[30] = 0x43000000, 0x4a000000
            for offset, text, address in [(0x24, 'Demo007_1', 0x4b000000), (0x70, entry, 0x4b000100)]:
                m.put(m.reg[30] + offset, address)
                for i, byte in enumerate(text.encode() + b'\0'):
                    m.put(address + i, byte, 1)
            before = dict(m.reg), m.lr, m.cr
            m.run('apMessageExecutorCreated')
            self.assertEqual((dict(m.reg), m.lr, m.cr), before)
            self.assertEqual(self.get(m, 20), 0x43000000 if entry == 'APMessageStandalone' else 0)
