import unittest

from botw_client.backend import (
    BackendContractError,
    DeliveryCheckpoint,
    DeliveryCommand,
    DeliveryCoordinator,
    DeliveryResult,
    DeliveryStatus,
)


class FakeBackend:
    def __init__(self, checkpoint, result=None, error=None,
                 checkpoint_after=None):
        self.current = checkpoint
        self.result = result
        self.error = error
        self.checkpoint_after = checkpoint_after
        self.calls = 0

    def checkpoint(self):
        if self.calls and self.checkpoint_after is not None:
            return self.checkpoint_after
        return self.current

    def deliver(self, _command):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result

    def checked_locations(self):
        return set()


class DeliveryCoordinatorTests(unittest.TestCase):
    command = DeliveryCommand("seed-a", 2, 7, "Ancient Core")
    ready = DeliveryCheckpoint("seed-a", 2, command.cursor)

    def test_exact_commit_is_accepted(self):
        backend = FakeBackend(
            self.ready,
            DeliveryResult(DeliveryStatus.APPLIED, self.command.next_cursor))
        result = DeliveryCoordinator(backend).deliver(self.command)
        self.assertEqual(result, DeliveryResult(
            DeliveryStatus.APPLIED, self.command.next_cursor))
        self.assertEqual(backend.calls, 1)

    def test_lost_ack_is_reconciled_from_committed_cursor(self):
        backend = FakeBackend(
            self.ready, error=TimeoutError("ack perdu"),
            checkpoint_after=DeliveryCheckpoint(
                "seed-a", 2, self.command.next_cursor))
        result = DeliveryCoordinator(backend).deliver(self.command)
        self.assertEqual(result.status, DeliveryStatus.APPLIED)
        self.assertEqual(result.cursor, self.command.next_cursor)
        self.assertIn("reading it back", result.detail)
        self.assertEqual(backend.calls, 1)

    def test_interruption_with_unchanged_cursor_is_quarantined(self):
        backend = FakeBackend(
            self.ready, error=TimeoutError("pendant mutation"),
            checkpoint_after=self.ready)
        coordinator = DeliveryCoordinator(backend)
        result = coordinator.deliver(self.command)
        self.assertEqual(result.status, DeliveryStatus.UNCERTAIN)
        self.assertEqual(result.cursor, self.command.cursor)
        self.assertIn("mutation possible", result.detail)
        self.assertEqual(backend.calls, 1)

    def test_native_uncertain_is_reconciled_without_retry(self):
        backend = FakeBackend(
            self.ready,
            DeliveryResult(DeliveryStatus.UNCERTAIN,
                           self.command.cursor, "owner gone"),
            checkpoint_after=self.ready)
        result = DeliveryCoordinator(backend).deliver(self.command)
        self.assertEqual(result.status, DeliveryStatus.UNCERTAIN)
        self.assertIn("owner gone", result.detail)
        self.assertEqual(backend.calls, 1)

    def test_wrong_session_and_gap_never_call_backend(self):
        wrong = FakeBackend(DeliveryCheckpoint(
            "seed-b", 2, self.command.cursor))
        result = DeliveryCoordinator(wrong).deliver(self.command)
        self.assertEqual(result.status, DeliveryStatus.SESSION_MISMATCH)
        self.assertEqual(wrong.calls, 0)

        gap = FakeBackend(DeliveryCheckpoint(
            "seed-a", 2, self.command.cursor - 1))
        result = DeliveryCoordinator(gap).deliver(self.command)
        self.assertEqual(result.status, DeliveryStatus.OUT_OF_ORDER)
        self.assertEqual(result.cursor, self.command.cursor - 1)
        self.assertEqual(gap.calls, 0)

    def test_committed_item_is_not_called_twice(self):
        backend = FakeBackend(DeliveryCheckpoint(
            "seed-a", 2, self.command.next_cursor))
        result = DeliveryCoordinator(backend).deliver(self.command)
        self.assertEqual(result.status, DeliveryStatus.ALREADY_APPLIED)
        self.assertEqual(backend.calls, 0)

    def test_deferred_and_full_require_unchanged_cursor(self):
        for status in (DeliveryStatus.DEFERRED,
                       DeliveryStatus.INVENTORY_FULL):
            with self.subTest(status=status):
                backend = FakeBackend(
                    self.ready, DeliveryResult(status, self.command.cursor))
                self.assertEqual(
                    DeliveryCoordinator(backend).deliver(self.command).status,
                    status)

        backend = FakeBackend(
            self.ready, DeliveryResult(
                DeliveryStatus.INVENTORY_FULL, self.command.next_cursor))
        with self.assertRaisesRegex(BackendContractError, "cursor advanced"):
            DeliveryCoordinator(backend).deliver(self.command)

    def test_success_requires_exact_next_cursor(self):
        backend = FakeBackend(
            self.ready, DeliveryResult(
                DeliveryStatus.APPLIED, self.command.cursor))
        with self.assertRaisesRegex(
                BackendContractError, f"expected {self.command.next_cursor}"):
            DeliveryCoordinator(backend).deliver(self.command)

    def test_impossible_reconciliation_cursor_is_rejected(self):
        backend = FakeBackend(
            self.ready, error=TimeoutError(),
            checkpoint_after=DeliveryCheckpoint(
                "seed-a", 2, self.command.next_cursor + 1))
        with self.assertRaisesRegex(
                BackendContractError,
                f"expected {self.command.cursor} or {self.command.next_cursor}"):
            DeliveryCoordinator(backend).deliver(self.command)

    def test_substep_commit_uses_packed_cursor(self):
        command = DeliveryCommand("seed-a", 2, 7, "Snowquill Set", 1, 3)
        backend = FakeBackend(
            DeliveryCheckpoint("seed-a", 2, command.cursor),
            DeliveryResult(DeliveryStatus.APPLIED, command.next_cursor))
        result = DeliveryCoordinator(backend).deliver(command)
        self.assertEqual(result.cursor, (7 << 8) | 2)


if __name__ == "__main__":
    unittest.main()
