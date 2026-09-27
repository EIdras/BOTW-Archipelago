import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from botw_client.message_text import MESSAGE_MAX_UNITS, clip_units, queued_text
from botw_client.presentation_session import clipped
from botw_client.protocol import APMessage
from botw_client.runtime import BotwClientRuntime, StateStore


class MessageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'state.json'
        self.game = Mock()
        self.runtime = BotwClientRuntime('unused', 'Player', state_path=self.path,
            game_factory=lambda: self.game, native_presentations=True)
        self.runtime.state = self.runtime.state_store.select('seed', 0, 1)

    def collect(self, text, nodes=()):
        self.runtime.ap.messages.put_nowait(APMessage(text, 'Chat', nodes))
        self.runtime._collect_messages()

    def test_long_message_survives_restart_without_using_game_or_grant_queues(self):
        text = 'An important hint: ' + 'look near the shrine. ' * 15
        self.collect(text.strip())
        restored = StateStore(self.path).select('seed', 0, 1)
        self.assertEqual(restored['message_queue'][0]['text'], text.strip())
        self.assertEqual(restored['apply_queue'], [])
        self.assertEqual(restored['display_queue'], [])
        self.assertEqual(self.game.mock_calls, [])

    def test_binary_commands_and_broken_unicode_are_safe_even_in_metadata(self):
        self.collect('Hello\x0e\0\ud800{size:80}',
                     ({'text': '\ud800', 'extra': ['\x0e']},))
        restored = StateStore(self.path).select('seed', 0, 1)['message_queue'][0]
        self.assertEqual(restored['text'], 'Hello  \ufffd{size:80}')
        self.assertEqual(restored['nodes'][0]['text'], '\ufffd')
        self.assertEqual(restored['nodes'][0]['extra'], [' '])

    def test_queue_retains_latest_hundred_messages_in_order(self):
        for number in range(105):
            self.runtime.ap.messages.put_nowait(APMessage(str(number), 'Chat', ()))
        self.runtime._collect_messages()
        queue = StateStore(self.path).select('seed', 0, 1)['message_queue']
        self.assertEqual([entry['text'] for entry in queue],
                         [str(number) for number in range(5, 105)])

    async def test_legacy_output_is_short_but_failed_display_keeps_full_message(self):
        self.runtime.native_mode = False
        text = 'Detailed message ' * 20
        self.collect(text)
        self.runtime._safe_now = lambda: True
        self.game.show_ap_message.return_value = False
        await self.runtime._show_one_message()
        displayed = self.game.show_ap_message.call_args.args[0]
        self.assertLessEqual(len(displayed.encode('utf-16-be')), 39 * 2)
        self.assertTrue(displayed.endswith('...'))
        self.assertEqual(self.runtime.state['message_queue'][0]['text'], text.strip())
        self.game.show_ap_message.return_value = True
        await self.runtime._show_one_message()
        self.assertEqual(StateStore(self.path).select('seed', 0, 1)['message_queue'], [])

    async def test_native_mode_refuses_historical_display_even_when_called_directly(self):
        self.collect('Pending text')
        self.runtime._safe_now = lambda: True
        await self.runtime._show_one_message()
        self.assertEqual(self.game.mock_calls, [])
        self.assertEqual(self.runtime.state['message_queue'][0]['text'], 'Pending text')

    def test_dialogue_storage_capacity_counts_utf16_and_marks_truncation(self):
        text = queued_text('🙂' * 2048)
        self.assertLessEqual(len(text.encode('utf-16-be')), MESSAGE_MAX_UNITS * 2)
        self.assertTrue(text.endswith('...'))
        self.assertNotIn('\ufffd', text)
        self.assertEqual(queued_text('é' * MESSAGE_MAX_UNITS), 'é' * MESSAGE_MAX_UNITS)

    def test_native_item_text_is_literal_and_preserves_pair_boundaries(self):
        self.assertEqual(clipped('ab🙂c', 3), 'ab')
        self.assertEqual(clipped('ab🙂c', 4), 'ab🙂')
        self.assertEqual(clipped('A\x0eB\ud800\n{0}', 50), 'A B\ufffd\n{0}')
        self.assertEqual(clip_units('texte', 0), '')


if __name__ == '__main__':
    unittest.main()
