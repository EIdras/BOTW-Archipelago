import asyncio
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from botw_client.presentation_session import NativePresentationSession
from botw_client.runtime import BotwClientRuntime, StateStore, FatalClientError
from botw_client.game import BotwGame


class SessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'state.json'
        self.game = Mock()
        self.game.item_map = {'Apple':{'delivery':{'kind':'actors'}}}
        self.ap = SimpleNamespace(slot=1, received_items={0:SimpleNamespace(item=10, player=2, location=55)},
            connected=True, items_synchronized=True,
            scouted_locations={}, item_name=lambda item:'Apple', sender=lambda item:('Player','BOTW'),
            location_name=lambda loc:'Oman Au Shrine')
        self.backend = Mock()
        self.backend.ready.return_value = True
        self.backend.submit.return_value = dict(status='accepted', session='native', generation=1)
        self.backend.poll.return_value = dict(status='pending', session='native', generation=1)
        self.state_store = StateStore(self.path)
        self.state = self.state_store.select('seed',0,1,'package')
        self.state['display_queue'] = [0]
        self.session = NativePresentationSession(self.path, ('seed',0,1,'package'), self.game, backend=self.backend)
        self.addCleanup(self.session.close)

    def advance(self, **kwargs):
        return self.session.advance(self.state, self.ap, self.game, **kwargs)

    def finish(self):
        self.backend.poll.return_value = dict(status='finished', session='native', generation=1)

    def test_acceptance_keeps_pending_and_only_native_finish_projects_shown(self):
        self.assertEqual(self.advance(), ('accepted', False))
        self.assertEqual(self.state['display_queue'], [0])
        self.assertEqual(self.state['shown'], [])
        self.assertEqual(self.advance(), ('accepted', False))
        self.finish()
        self.assertEqual(self.advance(), ('completed', True))
        self.assertEqual(self.state['display_queue'], [])
        self.assertEqual(self.state['shown'], [0])
        self.assertEqual(self.state['presentation_completed'], [0])
        self.game.show_received.assert_not_called()

    def test_default_backend_allows_hudless_only_with_live_game_gate(self):
        game = Mock(process=Mock(), cave=Mock())
        game.safe_for_delivery.return_value = True
        backend = Mock()
        flags = Mock()
        with patch("botw_client.presentation_session.CemuPresentationBackend",
                   return_value=backend) as factory, \
             patch("tools.cemu.presentation_ready.flag_reader",
                   return_value=flags), \
             patch("tools.cemu.presentation_ready.ready",
                   return_value=True) as ready:
            session = NativePresentationSession(
                self.path, ('other-seed', 0, 1, 'package'), game)
            self.addCleanup(session.close)
            kwargs = factory.call_args.kwargs
            self.assertTrue(kwargs["guard"]())
            self.assertTrue(kwargs["stability_guard"]())
        ready.assert_called_once_with(
            game.process, game.cave, flags, allow_hudless=True)
        game.safe_for_delivery.assert_called_once_with()

    def test_local_scout_and_received_share_one_native_request(self):
        self.ap.received_items[0].player = 1
        self.ap.scouted_locations[55] = SimpleNamespace(item=10, player=1)
        self.state['location_display_queue'] = [55]
        self.advance()
        self.assertEqual(self.backend.submit.call_args.args[0], 'location/55')
        self.finish()
        self.advance()
        self.assertEqual(self.state['location_presentation_completed'], [55])
        self.assertEqual(self.state['presentation_completed'], [0])
        self.assertEqual(self.state['location_display_queue'], [])
        self.assertEqual(self.backend.submit.call_count, 1)

    def test_historical_shown_is_not_migrated_to_native_confirmation(self):
        self.ap.received_items[0].player = 1
        self.ap.scouted_locations[55] = SimpleNamespace(item=10, player=1)
        self.state['location_shown'] = [55]
        self.advance()
        self.assertEqual(self.state['shown'], [0])
        self.assertEqual(self.state['presentation_completed'], [])
        self.assertEqual(self.state['location_presentation_completed'], [])
        self.backend.submit.assert_not_called()

    def test_restart_rebuilds_projection_after_client_state_save_failure(self):
        original = deepcopy(self.state)
        self.advance()
        self.finish()
        self.advance()  # Durable completed journal, client projection not saved.
        self.session.close()
        self.session = NativePresentationSession(self.path, ('seed',0,1,'package'), self.game, backend=self.backend)
        self.addCleanup(self.session.close)
        self.state = original
        self.advance()
        self.assertEqual(self.state['presentation_completed'], [0])
        self.assertEqual(self.backend.submit.call_count, 1)

    def test_restart_quarantines_pending_and_blocks_following_sources(self):
        self.advance()
        self.session.close()
        self.session = NativePresentationSession(self.path, ('seed',0,1,'package'), self.game, backend=self.backend)
        self.addCleanup(self.session.close)
        self.state['location_display_queue'] = [99]
        self.ap.scouted_locations[99] = SimpleNamespace(item=11, player=2)
        self.assertEqual(self.advance(), ('uncertain', False))
        self.assertEqual(self.state['shown'], [])
        self.assertEqual(self.backend.submit.call_count, 1)
        self.backend.poll.assert_not_called()

    def reopen(self, incarnation='old-cemu'):
        self.session.close()
        self.backend.recovery_incarnation.return_value = incarnation
        self.session = NativePresentationSession(
            self.path, ('seed',0,1,'package'), self.game, backend=self.backend)
        self.addCleanup(self.session.close)

    def test_cut_before_submission_resumes_without_recovery(self):
        self.advance(allow_submit=False)
        self.reopen('new-cemu')
        self.assertEqual(self.advance(), ('accepted', False))
        self.assertEqual(self.backend.submit.call_count, 1)

    def test_cut_during_window_requires_command_restart_and_readiness(self):
        self.advance()
        self.reopen()
        self.session.request_replay('received/0')
        original = deepcopy(self.state)
        self.reopen()  # A companion reconnect alone must never enable replay.
        self.assertEqual(self.advance(), ('uncertain', False))
        self.reopen('new-cemu')
        self.assertEqual(self.advance(allow_submit=False), ('uncertain', False))
        self.assertEqual(self.advance(sources_ready=False), ('uncertain', False))
        self.backend.ready.return_value = False
        self.assertEqual(self.advance(), ('uncertain', False))
        self.assertEqual(self.backend.submit.call_count, 1)
        self.assertEqual(self.state, original)
        self.backend.ready.return_value = True
        self.backend.submit.return_value = dict(status='accepted', session='fresh', generation=1)
        self.assertEqual(self.advance(), ('accepted', False))
        self.assertEqual(self.state['presentation_completed'], [])
        self.backend.poll.return_value = dict(status='finished', session='fresh', generation=1)
        self.assertEqual(self.advance(), ('completed', True))
        self.assertEqual(self.state['presentation_completed'], [0])
        self.assertEqual(self.state['applied'], [])
        self.game.apply_item_step.assert_not_called()

    def test_native_finish_without_durable_ack_still_needs_explicit_recovery(self):
        self.advance()
        self.finish()  # Native finish happened, but client never polled/journaled it.
        self.reopen('new-cemu')
        self.assertEqual(self.advance(), ('uncertain', False))
        self.backend.poll.assert_not_called()
        self.assertEqual(self.state['presentation_completed'], [])

    def test_recovery_does_not_skip_following_fifo_entries(self):
        self.advance()
        self.reopen()
        self.session.request_replay('received/0')
        self.ap.received_items[1] = SimpleNamespace(item=11, player=2, location=56)
        self.state['display_queue'].append(1)
        self.reopen('new-cemu')
        self.backend.submit.return_value = dict(status='accepted', session='fresh', generation=1)
        self.advance()
        self.assertEqual(self.backend.submit.call_args.args[0], 'received/0')
        self.assertEqual(self.advance(), ('uncertain', False))  # Old-session proof rejected.
        self.assertEqual(self.state['presentation_completed'], [])
        self.assertEqual(self.session.store.queue.snapshot()['entries'][1]['status'], 'queued')

    async def test_console_recovery_is_committed_by_worker_not_console(self):
        self.advance()
        self.reopen()
        log = Mock()
        runtime = BotwClientRuntime('localhost:1', 'test', state_path=self.path,
            game_factory=lambda:self.game, native_presentations=True, log=log)
        runtime.state, runtime.ap, runtime.presentations = self.state, self.ap, self.session
        runtime._ap_session_ready = True
        before = self.session.store.queue.snapshot()
        self.assertTrue(runtime.handle_local_command('/ap-replay received/0'))
        self.assertEqual(self.session.store.queue.snapshot(), before)
        await runtime._native_presentation_tick()
        self.assertEqual(self.session.blocked_head()['replay_after_incarnation'], 'old-cemu')
        self.assertTrue(any('Replay recorded' in c.args[0] for c in log.call_args_list))
        self.assertEqual(self.backend.submit.call_count, 1)

    async def test_wrong_console_id_cannot_unblock_or_stop_runtime(self):
        self.advance()
        self.reopen()
        log = Mock()
        runtime = BotwClientRuntime('localhost:1', 'test', state_path=self.path,
            game_factory=lambda:self.game, native_presentations=True, log=log)
        runtime.state, runtime.ap, runtime.presentations = self.state, self.ap, self.session
        runtime._ap_session_ready = True
        runtime.handle_local_command('/ap-replay received/999')
        await runtime._native_presentation_tick()
        self.assertNotIn('replay_after_incarnation', self.session.blocked_head())
        self.assertTrue(any('Replay refused' in c.args[0] for c in log.call_args_list))

    def test_reconnect_keeps_payload_and_pending_poll_ignores_submission_delay(self):
        self.advance()
        self.ap.sender = lambda item:('New nickname','Other game')
        self.finish()
        self.assertEqual(self.advance(allow_submit=False), ('completed', True))
        self.assertEqual(self.backend.submit.call_count, 1)

    async def test_runtime_projection_and_close_preserve_native_control(self):
        runtime = BotwClientRuntime('localhost:1', 'test', state_path=self.path,
            game_factory=lambda:self.game, native_presentations=True)
        runtime.state, runtime.ap, runtime.presentations = self.state, self.ap, self.session
        runtime._ap_session_ready = True
        runtime.state_store = self.state_store
        await runtime._native_presentation_tick()
        self.assertEqual(self.state['shown'], [])
        self.finish()
        await runtime._native_presentation_tick()
        self.assertEqual(StateStore(self.path).select('seed',0,1,'package')['presentation_completed'], [0])
        with self.assertRaises(RuntimeError): await runtime._show_one_received()
        game = BotwGame()
        game.native_presentation_mode = True
        game.process, game.cave = Mock(), Mock()
        cave = game.cave
        game.close()
        cave.sub_disarm.assert_not_called()

    async def test_cancel_waits_for_pending_worker_before_resources_can_close(self):
        runtime = BotwClientRuntime('localhost:1', 'test', state_path=self.path,
            game_factory=lambda:self.game, native_presentations=True)
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def advance(*a, **kw):
            started.set()
            if not release.wait(5): raise TimeoutError('test worker not released')
            return 'accepted', False
        runtime.presentations = Mock(advance=advance)
        task = asyncio.create_task(runtime._native_presentation_tick())
        self.assertTrue(await asyncio.to_thread(started.wait, 2))
        task.cancel()
        await asyncio.sleep(.02)
        self.assertFalse(task.done())
        release.set()
        with self.assertRaises(asyncio.CancelledError): await task

    async def test_projection_save_error_is_fatal_and_does_not_resubmit(self):
        runtime = BotwClientRuntime('localhost:1', 'test', state_path=self.path,
            game_factory=lambda:self.game, native_presentations=True)
        runtime.state, runtime.ap, runtime.presentations = self.state, self.ap, self.session
        runtime._ap_session_ready = True
        await runtime._native_presentation_tick()
        self.finish()
        with patch.object(runtime.state_store, 'save', side_effect=OSError('disk full')):
            with self.assertRaises(FatalClientError): await runtime._native_presentation_tick()
        self.assertEqual(self.backend.submit.call_count, 1)

    async def test_native_active_loop_never_calls_legacy_display_or_grant_paths(self):
        runtime = BotwClientRuntime('localhost:1', 'test', state_path=self.path,
            game_factory=lambda:self.game, native_presentations=True)
        runtime.state = self.state
        runtime._poll_locations = AsyncMock()
        runtime._reconnect_tick = AsyncMock()
        runtime._discover_received = Mock()
        runtime._collect_messages = Mock()
        forbidden = ('_deathlink_tick', '_show_one_location_reward', '_show_one_received',
                     '_apply_one_received', '_show_one_message')
        for name in forbidden:
            setattr(runtime, name, AsyncMock())
        async def tick(): runtime.stop()
        runtime._native_presentation_tick = AsyncMock(side_effect=tick)
        await runtime._active_loop()
        runtime._native_presentation_tick.assert_awaited_once()
        for name in forbidden:
            getattr(runtime, name).assert_not_awaited()
        self.game.cave.sub_disarm.assert_not_called()
