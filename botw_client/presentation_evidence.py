"""Read-only native trace collection, isolated from presentation decisions."""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid


class PresentationEvidence:
    def __init__(self, directory, process, cave, log):
        self.directory = Path(directory)
        self.process, self.cave, self.log = process, cave, Path(log)
        self.path = None
        self.data = None

    def capture(self, phase, submission):
        from tools.cemu.request_reject_trace import snapshot

        if phase == 'before':
            self.path = self.directory / (uuid.uuid4().hex + '.json')
            self.data = {'schema': 1, 'scope': 'presentation_request_trace',
                         'samples': []}
        sample = {'phase': phase, 'utc': datetime.now(timezone.utc).isoformat(),
                  'submission': dict(submission)}
        try:
            sample['request_trace'] = snapshot(self.process, self.cave.base, self.log)
            from tools.cemu.autonomous_eventflow import manager_diagnostic
            sample['event_manager'] = manager_diagnostic(self.process, self.cave.base)
        except Exception as exc:
            sample['trace_error'] = f'{type(exc).__name__}: {exc}'
        self.data['samples'].append(sample)
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + '\n',
                             encoding='utf-8')
        temporary.replace(self.path)
