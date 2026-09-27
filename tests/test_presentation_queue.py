import unittest
from unittest.mock import Mock
from botw_client.presentation import PresentationQueue


class QueueTests(unittest.TestCase):
    def test_proven_refusal_stays_queued_across_restart_then_fifo_continues(self):
        q,j,b=self.make()
        b.submit.return_value=dict(status='retryable_refusal',session='old',generation=1)
        self.assertEqual(q.tick(b),'queued')
        recovered=PresentationQueue('seed/slot',lambda _: None,q.snapshot())
        self.assertEqual(recovered.snapshot()['entries'][0]['status'],'queued')
        b.submit.return_value=dict(status='accepted',session='new',generation=1)
        b.poll.return_value=dict(status='finished',session='new',generation=1)
        self.assertEqual(recovered.tick(b),'accepted')
        self.assertEqual(recovered.tick(b),'completed')
        b.submit.return_value=dict(status='accepted',session='new',generation=2)
        self.assertEqual(recovered.tick(b),'accepted')
        self.assertEqual(b.submit.call_args.args[0],'received/1')

    def make(self):
        journal=[]
        q=PresentationQueue('seed/slot',journal.append)
        q.enqueue('received/0','One','First')
        q.enqueue('received/1','Two','Second')
        backend=Mock()
        backend.ready.return_value=True
        backend.submit.return_value=dict(status='accepted',session='process-instance',generation=1)
        backend.poll.return_value=dict(status='finished',session='process-instance',generation=1)
        return q,journal,backend

    def test_fifo_waits_for_matching_finish_and_journals_before_dispatch(self):
        q,j,b=self.make()
        def submit(*args):
            self.assertEqual(j[-1]['entries'][0]['status'],'dispatching')
            return dict(status='accepted',session='process-instance',generation=1)
        b.submit.side_effect=submit
        self.assertEqual(q.tick(b),'accepted')
        b.poll.return_value=dict(status='pending',session='process-instance',generation=1)
        self.assertEqual(q.tick(b),'accepted')
        self.assertEqual(b.submit.call_count,1)
        b.poll.return_value=dict(status='finished',session='process-instance',generation=1)
        self.assertEqual(q.tick(b),'completed')
        b.ready.return_value=False
        self.assertEqual(q.tick(b),'waiting_ready')
        self.assertEqual(b.submit.call_count,1)

    def test_duplicate_identity_is_idempotent_but_payload_conflict_fails(self):
        q,j,b=self.make()
        q.enqueue('received/0','One','First')
        self.assertEqual(len(j),2)
        with self.assertRaises(ValueError):
            q.enqueue('received/0','Changed','First')
        q.tick(b)
        q.tick(b)
        self.assertEqual(q.enqueue('received/0','One','First')['status'],'completed')

    def test_unknown_or_exception_blocks_every_following_request(self):
        for exception in (False,True):
            q,j,b=self.make()
            if exception:
                b.submit.side_effect=TimeoutError('ack lost')
            else:
                b.submit.return_value=dict(status='uncertain')
            self.assertEqual(q.tick(b),'uncertain')
            self.assertEqual(q.tick(b),'uncertain')
            self.assertEqual(b.submit.call_count,1)
            with self.assertRaises(ValueError):
                q.retry_refused('received/0')

    def test_other_session_or_generation_cannot_acknowledge(self):
        for key,value in (('session','restarted-process'),('generation',2)):
            q,j,b=self.make()
            q.tick(b)
            b.poll.return_value=dict(status='finished',session='process-instance',generation=1,**{})
            b.poll.return_value[key]=value
            self.assertEqual(q.tick(b),'uncertain')

    def test_recovery_quarantines_inflight_but_preserves_queued_and_completed(self):
        q,j,b=self.make()
        q.tick(b)
        restored=PresentationQueue('seed/slot',j.append,q.snapshot())
        self.assertEqual(restored.tick(b),'uncertain')
        self.assertEqual(restored.snapshot()['entries'][1]['status'],'queued')
        q.tick(b)
        restored=PresentationQueue('seed/slot',j.append,q.snapshot())
        self.assertEqual(restored.snapshot()['entries'][0]['status'],'completed')
        with self.assertRaises(ValueError):
            PresentationQueue('different-seed',j.append,q.snapshot())

    def test_journal_failure_before_dispatch_never_calls_backend(self):
        q,j,b=self.make()
        q.commit=Mock(side_effect=OSError('disk unavailable'))
        with self.assertRaises(OSError):
            q.tick(b)
        b.submit.assert_not_called()
        with self.assertRaises(RuntimeError):
            q.tick(b)

    def test_failed_commit_after_acceptance_stops_and_recovers_as_uncertain(self):
        q,j,b=self.make()
        def commit(snapshot):
            if snapshot['entries'][0]['status']=='accepted':
                raise OSError('disk unavailable')
            j.append(snapshot)
        q.commit=commit
        with self.assertRaises(OSError):
            q.tick(b)
        self.assertEqual(b.submit.call_count,1)
        restored=PresentationQueue('seed/slot',lambda _:None,j[-1])
        self.assertEqual(restored.tick(b),'uncertain')

    def test_refusal_requires_explicit_retry(self):
        q,j,b=self.make()
        b.submit.return_value=dict(status='refused')
        self.assertEqual(q.tick(b),'refused')
        self.assertEqual(q.tick(b),'refused')
        q.retry_refused('received/0')
        self.assertEqual(q.tick(b),'refused')
        self.assertEqual(b.submit.call_count,2)

    def test_native_ticket_cannot_be_reused_for_second_request(self):
        q,j,b=self.make()
        q.tick(b)
        q.tick(b)
        self.assertEqual(q.tick(b),'uncertain')
        self.assertEqual(q.tick(b),'uncertain')
        self.assertEqual(b.submit.call_count,2)

    def test_explicit_replay_requires_restart_and_retains_audit_history(self):
        q,j,b=self.make()
        q.tick(b)
        q=PresentationQueue('seed/slot',j.append,q.snapshot())
        q.authorize_replay('received/0','old-process')
        q=PresentationQueue('seed/slot',j.append,q.snapshot())
        self.assertFalse(q.replay_after_restart('old-process'))
        self.assertEqual(q.tick(b),'uncertain')
        self.assertTrue(q.replay_after_restart('new-process'))
        e=q.snapshot()['entries'][0]
        self.assertEqual((e['status'],e['attempts']),('queued',1))
        self.assertNotIn('ticket',e)
        self.assertEqual(e['recovery_history'][0]['ticket'],
                         dict(session='process-instance',generation=1))
        # Replay authorizes no completion; a fresh joined ACK is still needed.
        b.submit.return_value=dict(status='accepted',session='new-session',generation=1)
        self.assertEqual(q.tick(b),'accepted')
        self.assertEqual(q.snapshot()['entries'][0]['attempts'],2)
        self.assertEqual(q.snapshot()['entries'][1]['status'],'queued')

    def test_no_replay_without_authorization_or_for_another_head(self):
        q,j,b=self.make()
        with self.assertRaises(ValueError): q.authorize_replay('received/0','process')
        q.tick(b)
        q=PresentationQueue('seed/slot',j.append,q.snapshot())
        self.assertFalse(q.replay_after_restart('new-process'))
        with self.assertRaises(ValueError): q.authorize_replay('received/1','process')
        with self.assertRaises(ValueError): q.authorize_replay('received/0','')
        self.assertEqual(q.tick(b),'uncertain')

    def test_dispatching_without_ticket_can_be_explicitly_recovered(self):
        q,j,b=self.make()
        snapshot=q.snapshot()
        snapshot['entries'][0].update(status='dispatching',attempts=1)
        q=PresentationQueue('seed/slot',j.append,snapshot)
        q.authorize_replay('received/0','process-at-decision')
        self.assertTrue(q.replay_after_restart('fresh-process'))
        self.assertEqual(q.snapshot()['entries'][0]['status'],'queued')
        b.submit.assert_not_called()

    def test_recovery_commit_failure_stops_queue_before_any_submission(self):
        for stage in ('authorization','requeue'):
            with self.subTest(stage=stage):
                q,j,b=self.make()
                q.tick(b)
                q=PresentationQueue('seed/slot',j.append,q.snapshot())
                if stage=='requeue': q.authorize_replay('received/0','old')
                q.commit=Mock(side_effect=OSError('disk full'))
                with self.assertRaises(OSError):
                    if stage=='authorization': q.authorize_replay('received/0','old')
                    else: q.replay_after_restart('new')
                with self.assertRaises(RuntimeError): q.tick(b)
                self.assertEqual(b.submit.call_count,1)

    def test_duplicate_authorization_keeps_original_restart_barrier(self):
        q,j,b=self.make()
        b.submit.return_value=dict(status='refused')
        q.tick(b)
        q.authorize_replay('received/0','old')
        q.authorize_replay('received/0','new')
        self.assertEqual(q.snapshot()['entries'][0]['replay_after_incarnation'],'old')
        with self.assertRaises(ValueError): q.retry_refused('received/0')


if __name__=='__main__':
    unittest.main()
