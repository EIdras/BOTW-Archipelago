import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from botw_client.presentation_store import PresentationStore


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'queue.json'

    def test_exclusive_in_process_and_child_then_reopen(self):
        with PresentationStore(self.path, 'slot') as store:
            store.queue.enqueue('1', 'Titre', 'Texte')
            with self.assertRaises(OSError):
                PresentationStore(self.path, 'slot')
            script = ('from botw_client.presentation_store import PresentationStore\n'
                      'import sys\ntry:\n PresentationStore(sys.argv[1], "slot")\n'
                      'except OSError:\n sys.exit(23)\n')
            child = subprocess.run([sys.executable, '-c', script, str(self.path)], capture_output=True, timeout=10)
            self.assertEqual(child.returncode, 23, child.stderr)
        with PresentationStore(self.path, 'slot') as store:
            self.assertEqual(store.queue.snapshot()['entries'][0]['status'], 'queued')

    def test_recovery_quarantines_accepted(self):
        backend = Mock()
        backend.ready.return_value = True
        backend.submit.return_value = dict(status='accepted', session='cemu', generation=1)
        with PresentationStore(self.path, 'slot') as store:
            store.queue.enqueue('1', 'A', 'B')
            self.assertEqual(store.queue.tick(backend), 'accepted')
        with PresentationStore(self.path, 'slot') as store:
            self.assertEqual(store.queue.tick(backend), 'uncertain')
            self.assertEqual(json.loads(self.path.read_text())['entries'][0]['status'], 'uncertain')
        self.assertEqual(backend.submit.call_count, 1)

    def test_completed_identity_survives_reopening_without_replay(self):
        backend = Mock()
        backend.submit.return_value = dict(status='accepted', session='cemu', generation=1)
        backend.poll.return_value = dict(status='finished', session='cemu', generation=1)
        with PresentationStore(self.path, 'slot') as store:
            store.queue.enqueue('1', 'A', 'B')
            self.assertEqual(store.queue.tick(backend), 'accepted')
            self.assertEqual(store.queue.tick(backend), 'completed')
        with PresentationStore(self.path, 'slot') as store:
            self.assertEqual(store.queue.enqueue('1', 'A', 'B')['status'], 'completed')
            self.assertEqual(store.queue.tick(backend), 'idle')
        self.assertEqual(backend.submit.call_count, 1)

    def test_replace_failure_preserves_previous_snapshot_and_stops(self):
        with PresentationStore(self.path, 'slot') as store:
            store.queue.enqueue('1', 'A', 'B')
            previous = self.path.read_bytes()
            backend = Mock()
            with patch('botw_client.presentation_store.os.replace', side_effect=OSError('disk')):
                with self.assertRaises(OSError):
                    store.queue.tick(backend)
            backend.submit.assert_not_called()
            self.assertTrue(store.queue.broken)
            self.assertEqual(self.path.read_bytes(), previous)
            self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_corrupt_or_wrong_namespace_never_resets(self):
        self.path.write_text('{broken')
        with self.assertRaises(ValueError):
            PresentationStore(self.path, 'slot')
        self.assertEqual(self.path.read_text(), '{broken')
        self.path.unlink()
        with PresentationStore(self.path, 'slot'):
            pass
        with self.assertRaises(ValueError):
            PresentationStore(self.path, 'other')
        with PresentationStore(self.path, 'slot'):
            pass

    def test_closed_queue_cannot_dispatch(self):
        with PresentationStore(self.path, 'slot') as store:
            store.queue.enqueue('1', 'A', 'B')
        with self.assertRaises(RuntimeError):
            store.queue.tick(Mock())

    def test_abrupt_writer_exit_releases_lease_and_quarantines_dispatch(self):
        script = '''
import os, sys
from botw_client.presentation_store import PresentationStore
store = PresentationStore(sys.argv[1], 'slot')
store.queue.enqueue('1', 'A', 'B')
class Backend:
    def ready(self): return True
    def submit(self, *args): os._exit(24)
store.queue.tick(Backend())
'''
        child = subprocess.run([sys.executable, '-c', script, str(self.path)], capture_output=True, timeout=10)
        self.assertEqual(child.returncode, 24, child.stderr)
        self.assertEqual(json.loads(self.path.read_text())['entries'][0]['status'], 'dispatching')
        with PresentationStore(self.path, 'slot') as store:
            backend = Mock()
            self.assertEqual(store.queue.tick(backend), 'uncertain')
            backend.submit.assert_not_called()

    def test_failure_after_replace_stops_and_recovery_is_conservative(self):
        import os
        with PresentationStore(self.path, 'slot') as store:
            store.queue.enqueue('1', 'A', 'B')
            backend = Mock()
            calls = 0
            real = os.fsync
            def fail_second(fd):
                nonlocal calls
                calls += 1
                if calls == 2: raise OSError('post-replace flush failed')
                return real(fd)
            with patch('botw_client.presentation_store.os.fsync', side_effect=fail_second):
                with self.assertRaises(OSError): store.queue.tick(backend)
            backend.submit.assert_not_called()
            self.assertTrue(store.queue.broken)
        with PresentationStore(self.path, 'slot') as store:
            self.assertEqual(store.queue.snapshot()['entries'][0]['status'], 'uncertain')
