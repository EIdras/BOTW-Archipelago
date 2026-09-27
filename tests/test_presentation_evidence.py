import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from botw_client.presentation_evidence import PresentationEvidence


class EvidenceTests(unittest.TestCase):
    def test_each_attempt_preserves_before_and_after_in_separate_file(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = PresentationEvidence(directory, object(), SimpleNamespace(base=1), 'unused')
            with patch('tools.cemu.request_reject_trace.snapshot', side_effect=[
                    {'sequence': 0}, {'sequence': 1}, {'sequence': 1}, {'sequence': 2}]):
                for generation in (1, 2):
                    evidence.capture('before', {'request_id': 'location/42'})
                    evidence.capture('after', {'generation': generation, 'status': 'refused'})
            reports = [json.loads(p.read_text()) for p in Path(directory).glob('*.json')]
            self.assertEqual(len(reports), 2)
            self.assertEqual({r['samples'][1]['submission']['generation'] for r in reports}, {1, 2})
            for report in reports:
                before, after = report['samples']
                self.assertEqual(after['request_trace']['sequence'], before['request_trace']['sequence'] + 1)

    def test_unreadable_trace_is_explicit_not_reported_as_a_native_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = PresentationEvidence(directory, object(), SimpleNamespace(base=1), 'unused')
            with patch('tools.cemu.request_reject_trace.snapshot', side_effect=RuntimeError('unstable')):
                evidence.capture('before', {'request_id': 'location/42'})
            sample = json.loads(evidence.path.read_text())['samples'][0]
            self.assertIn('unstable', sample['trace_error'])
            self.assertNotIn('request_trace', sample)
