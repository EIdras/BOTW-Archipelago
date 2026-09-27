import unittest
from unittest.mock import Mock, patch
from tools.cemu import autonomous_eventflow as event


class RetryTests(unittest.TestCase):
    def test_explicit_refusals_then_acceptance_stop_retries(self):
        attempt = Mock(side_effect=[{"native_return": 0}, {"native_return": 0}, {"native_return": 1}])
        with patch.object(event.time, "sleep"):
            result = event.retry_until_accepted(attempt, lambda: True, Mock())
        self.assertEqual(result["native_return"], 1)
        self.assertEqual(attempt.call_count, 3)

    def test_unknown_outcome_never_retried(self):
        attempt = Mock(return_value={"status": "timeout"})
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            event.retry_until_accepted(attempt, lambda: True, Mock())
        attempt.assert_called_once()

    def test_busy_does_not_call_game(self):
        attempt = Mock()
        with patch.object(event.time, "monotonic", side_effect=[0, 0, 100]), patch.object(event.time, "sleep"):
            with self.assertRaises(RuntimeError):
                event.retry_until_accepted(attempt, lambda: False, Mock())
        attempt.assert_not_called()
