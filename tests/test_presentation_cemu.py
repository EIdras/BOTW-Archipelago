import os
import unittest
from unittest.mock import Mock

from botw_client.presentation_cemu import CemuPresentationBackend, process_incarnation
from botw_client.presentation import PresentationQueue
from tools.cemu.owned_presentation import finished


class AdapterTests(unittest.TestCase):
    def test_proven_refusal_retries_same_process_but_never_acceptance(self):
        self.make()
        self.cave = self.backend.cave
        self.cave.sub_state.return_value = (0, 0, 0, 0, 0)
        def refuse(*args, **kwargs):
            self.state.update(phase='refused', generation=1, native_return=0,
                              action=0, aborted_generation=0)
            self.join.update(generation=1, executor=0, terminal_generation=0,
                             manager_generation=0, retired_generation=0, ack_generation=0)
            return dict(status='refused', generation=1, owner_after=dict(self.state))
        self.native.request.side_effect = refuse
        for value in (0., .11, .22):
            self.now=value
            status=self.queue.tick(self.backend)
        self.assertEqual(status, 'queued')
        self.assertEqual(self.queue.snapshot()['entries'][0]['last_refusal_ticket']['generation'], 1)
        self.now=1
        self.assertEqual(self.queue.tick(self.backend), 'waiting_ready')
        self.assertEqual(self.native.request.call_count, 1)
        def accept(*args, **kwargs):
            self.state.update(phase='accepted', generation=2, native_return=1)
            return dict(status='accepted', generation=2)
        self.native.request.side_effect=accept
        for value in (3., 3.11, 3.22):
            self.now=value
            status=self.queue.tick(self.backend)
        self.assertEqual(status,'accepted')
        for _ in range(10): self.assertEqual(self.queue.tick(self.backend),'accepted')
        self.assertEqual(self.native.request.call_count,2)

    def test_refusal_proof_rejects_every_missing_or_nonzero_field(self):
        from botw_client.presentation_cemu import refusal_has_no_action
        state=dict(version=2,phase='refused',generation=1,native_return=0,
                   action=0,bound_generation=0,completed_generation=0,left_generation=0,
                   aborted_generation=0,busy=0,fault=0)
        join=dict(generation=1,executor=0,terminal_generation=0,manager_generation=0,
                  retired_generation=0,ack_generation=0)
        self.assertTrue(refusal_has_no_action(state,join,(0,0,0,0,0),1))
        for original in (state,join):
            for key in original:
                altered=dict(original)
                del altered[key]
                self.assertFalse(refusal_has_no_action(
                    altered if original is state else state,
                    altered if original is join else join,(0,0,0,0,0),1), key)
                if original[key] == 0:
                    altered[key]=1
                    self.assertFalse(refusal_has_no_action(
                        altered if original is state else state,
                        altered if original is join else join,(0,0,0,0,0),1),key)
        for text in ((1,0,0,0,0),(0,0,1,0,0),(0,0,0,0,1)):
            self.assertFalse(refusal_has_no_action(state,join,text,1))

    def test_diagnostic_failure_does_not_repeat_or_hide_native_acceptance(self):
        self.make()
        self.backend.evidence = Mock()
        self.backend.evidence.capture.side_effect = OSError('disk unavailable')
        self.send()
        self.assertEqual(self.native.request.call_count, 1)
        self.assertEqual(self.backend.evidence.capture.call_count, 2)
        self.assertIn('disk unavailable', self.backend.evidence_error)
        self.assertEqual(self.queue.snapshot()['entries'][0]['status'], 'accepted')

    def test_recovery_identity_is_read_only_and_available_after_uncertainty(self):
        self.make()
        self.backend.stopped = True
        self.assertEqual(self.backend.recovery_incarnation(), 'pid:creation-time')
        self.native.request.assert_not_called()
        self.identity.return_value = 'same-pid:different-creation-time'
        with self.assertRaises(RuntimeError): self.backend.recovery_incarnation()

    def test_native_submission_checkpoints_are_retained_for_refusal_diagnostics(self):
        self.make()
        def refuse(*args, **kwargs):
            args[6]({'status':'dispatching','owner_before':{'phase':'idle'}})
            self.state.update(generation=1,phase='refused')
            return {'status':'refused','generation':1,'native_return':0}
        self.native.request.side_effect=refuse
        for value in (0.,.11,.22):
            self.now=value
            result=self.queue.tick(self.backend)
        self.assertEqual(result,'refused')
        self.assertEqual(self.backend.last_submission['native_return'],0)
        self.assertEqual(self.backend.last_submission['owner_before']['phase'],'idle')
        self.assertEqual(self.queue.tick(self.backend),'refused')
        self.assertEqual(self.native.request.call_count,1)

    def test_resource_gate_deferral_keeps_queue_without_advancing_generation(self):
        self.make()
        def defer(*args, **kwargs):
            self.state.update(phase='idle')
            return {'status':'deferred','generation':0,'native_return':2}
        self.native.request.side_effect=defer
        for value in (0., .11, .22):
            self.now=value
            result=self.queue.tick(self.backend)
        self.assertEqual(result, 'queued')
        entry=self.queue.snapshot()['entries'][0]
        self.assertEqual((entry['status'],entry['attempts']),('queued',0))
        self.assertEqual((self.backend.generation,self.backend.active),(0,None))
        self.assertFalse(self.backend.stopped)
        self.assertEqual(self.native.request.call_count,1)
        # Three fresh stable samples are required before another preflight.
        self.assertEqual(self.queue.tick(self.backend),'waiting_ready')

    def test_unproven_deferred_result_is_uncertain_and_stops_backend(self):
        self.make()
        self.native.request.side_effect=lambda *a,**k: {
            'status':'deferred','generation':1,'native_return':2}
        for value in (0., .11, .22):
            self.now=value
            result=self.queue.tick(self.backend)
        self.assertEqual(result,'uncertain')
        self.assertTrue(self.backend.stopped)
        self.assertEqual(self.native.request.call_count,1)
    def make(self):
        self.now = 0.
        self.state = dict(version=2, phase='idle', generation=0, fault=0, busy=0,
                          bound_generation=0, completed_generation=0, left_generation=0)
        self.join = {}
        self.native = Mock()
        self.native.inspect.return_value = dict(version=2, state=self.state, address=100, join_address=200)
        self.native.read.side_effect = lambda *a: dict(self.state)
        self.native.read_join.side_effect = lambda *a: dict(self.join)
        self.native.finished.side_effect = finished
        self.identity = Mock(return_value='pid:creation-time')
        self.guard = Mock(return_value=True)
        self.backend = CemuPresentationBackend(Mock(writable=True), Mock(base=1234),
            native=self.native, guard=self.guard, identity=self.identity, clock=lambda: self.now)
        def submit(*args, **kwargs):
            self.assertTrue(args[5]())
            self.state.update(generation=self.state['generation']+1, phase='accepted')
            return dict(status='accepted', generation=self.state['generation'])
        self.native.request.side_effect = submit
        self.queue = PresentationQueue('slot', lambda s: None)
        self.queue.enqueue('1', 'A', 'B')
        self.queue.enqueue('2', 'C', 'D')

    def send(self):
        for value in (0., .11):
            self.now = value
            self.assertEqual(self.queue.tick(self.backend), 'waiting_ready')
        self.now = .22
        self.assertEqual(self.queue.tick(self.backend), 'accepted')

    def test_fifo_requires_native_join_then_new_stable_guard(self):
        self.make()
        self.send()
        self.assertEqual(self.queue.tick(self.backend), 'accepted')
        self.state.update(phase='finished', bound_generation=1, completed_generation=1, left_generation=1)
        self.assertEqual(self.queue.tick(self.backend), 'accepted')  # phase alone is no ACK
        self.join.update(executor=42, **{k:1 for k in ('generation','terminal_generation',
            'manager_generation','retired_generation','ack_generation')})
        self.assertEqual(self.queue.tick(self.backend), 'completed')
        self.assertEqual(self.queue.tick(self.backend), 'waiting_ready')
        self.now = .33
        self.assertEqual(self.queue.tick(self.backend), 'waiting_ready')
        self.now = .44
        self.assertEqual(self.queue.tick(self.backend), 'accepted')
        self.assertEqual(self.native.request.call_count, 2)

    def test_restart_reset_fault_and_timeout_quarantine(self):
        for failure in ('incarnation', 'generation', 'fault', 'timeout'):
            with self.subTest(failure=failure):
                self.make()
                self.send()
                if failure == 'incarnation': self.identity.return_value = 'same-pid:new-creation'
                elif failure == 'generation': self.state['generation'] = 0
                elif failure == 'fault': self.state['fault'] = 1
                else: self.now = 121
                self.assertEqual(self.queue.tick(self.backend), 'uncertain')
                self.assertEqual(self.queue.tick(self.backend), 'uncertain')
                self.assertEqual(self.native.request.call_count, 1)

    def test_guard_resets_stability_and_fast_ticks_do_not_count(self):
        self.make()
        for _ in range(5): self.assertFalse(self.backend.ready())
        self.now = .11
        self.assertFalse(self.backend.ready())
        self.guard.return_value = False
        self.assertFalse(self.backend.ready())
        self.guard.return_value = True
        self.now = .22
        self.assertFalse(self.backend.ready())
        self.native.request.assert_not_called()

    def test_live_stability_gate_is_sampled_but_not_repeated_by_final_guard(self):
        self.make()
        live = Mock(return_value=True)
        self.backend.stability_guard = live
        self.send()
        self.assertEqual(live.call_count, 3)
        self.assertEqual(self.guard.call_count, 5)

    def test_unknown_submit_stops_backend_without_retry(self):
        self.make()
        self.native.request.side_effect = TimeoutError('unknown')
        for value in (0., .11, .22):
            self.now = value
            result = self.queue.tick(self.backend)
        self.assertEqual(result, 'uncertain')
        self.assertTrue(self.backend.stopped)

    def test_windows_creation_time_and_closed_handle(self):
        from tools.cemu.winmem import Process
        process = Process(os.getpid())
        with process:
            first = process_incarnation(process)
            self.assertEqual(first, process_incarnation(process))
            self.assertTrue(first.startswith(str(os.getpid()) + ':'))
        with self.assertRaises(RuntimeError): process_incarnation(process)
