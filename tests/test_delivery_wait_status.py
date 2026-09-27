import unittest
from types import SimpleNamespace

from botw_client.runtime import BotwClientRuntime


class DeliveryWaitStatusTests(unittest.TestCase):
    def test_native_readiness_overrides_game_ready_diagnostic(self):
        messages=[]
        runtime=SimpleNamespace(state={'apply_queue':[1],'display_queue':[],
            'location_display_queue':[]},_next_delivery_wait_log=0,
            _presentation_status='waiting_ready',game=SimpleNamespace(delivery_block_reason='ready'),
            presentations=SimpleNamespace(backend=SimpleNamespace(
                wait_reason='conditions IHM non reunies',last_submission=None)),log=messages.append)
        BotwClientRuntime._log_delivery_wait(runtime)
        self.assertTrue(messages[0].endswith('conditions IHM non reunies'))

    def test_deferred_request_explains_automatic_wait(self):
        messages = []
        runtime = SimpleNamespace(
            state={'apply_queue': [5], 'display_queue': [], 'location_display_queue': []},
            _next_delivery_wait_log=0, _presentation_status='waiting_ready',
            presentations=SimpleNamespace(backend=SimpleNamespace(
                last_submission={'status': 'deferred'})),
            game=SimpleNamespace(delivery_block_reason='ready'), log=messages.append)
        BotwClientRuntime._log_delivery_wait(runtime)
        self.assertIn('automatic retry', messages[0])
        self.assertIn('announcement not submitted', messages[0])
        self.assertNotIn('/ap-replay', messages[0])

    def test_authorized_recovery_does_not_request_another_command(self):
        messages = []
        runtime = SimpleNamespace(
            state={'apply_queue': [5], 'display_queue': [], 'location_display_queue': []},
            _next_delivery_wait_log=0, _presentation_status='refused',
            presentations=SimpleNamespace(blocked_head=lambda: {
                'replay_after_incarnation': 'old-process'}),
            game=SimpleNamespace(delivery_block_reason='ready'), log=messages.append)
        BotwClientRuntime._log_delivery_wait(runtime)
        self.assertIn('replay already authorized', messages[0])
        self.assertNotIn('follow the /ap-replay', messages[0])

    def test_blocked_presentation_takes_precedence_over_ready_game(self):
        for status in ('refused', 'uncertain', None):
            with self.subTest(status=status):
                messages = []
                runtime = SimpleNamespace(
                    state={'apply_queue': [5], 'display_queue': [5],
                           'location_display_queue': [42]},
                    _next_delivery_wait_log=0, _presentation_status=status,
                    game=SimpleNamespace(delivery_block_reason='ready'),
                    log=messages.append)
                BotwClientRuntime._log_delivery_wait(runtime)
                self.assertEqual(len(messages), 1)
                if status:
                    self.assertIn('blocked (' + status + ')', messages[0])
                    self.assertNotIn(': ready', messages[0])
                else:
                    self.assertTrue(messages[0].endswith(': ready'))
