"""Native presentation adapter (owner v2) of the presentation queue.

Caller owns the writable process/cave and serializes calls. Never reattach an
adapter to another process or reuse it after an uncertain outcome.
"""
import ctypes
from ctypes import wintypes
import time
import uuid


def refusal_has_no_action(state, join, text, generation):
    """Positive native proof, not a timeout or a missing window."""
    return (state.get('version') == 2 and state.get('phase') == 'refused'
            and generation > 0 and state.get('generation') == generation
            and state.get('native_return') == 0
            and all(state.get(key) == 0 for key in (
                'action', 'bound_generation', 'completed_generation',
                'left_generation', 'aborted_generation', 'busy', 'fault'))
            and join.get('generation') == generation
            and all(join.get(key) == 0 for key in (
                'executor', 'terminal_generation', 'manager_generation',
                'retired_generation', 'ack_generation'))
            and len(text) == 5 and text[0] == text[2] == text[4] == 0)


def process_incarnation(process):
    if not process.h:
        raise RuntimeError('Cemu handle closed')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    times = [wintypes.FILETIME() for _ in range(4)]
    code = wintypes.DWORD()
    if not kernel.GetProcessTimes(process.h, *(ctypes.byref(t) for t in times)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.GetExitCodeProcess(process.h, ctypes.byref(code)):
        raise ctypes.WinError(ctypes.get_last_error())
    if code.value != 259 or times[1].dwHighDateTime or times[1].dwLowDateTime:
        raise RuntimeError('Cemu process exited')
    created = times[0].dwHighDateTime << 32 | times[0].dwLowDateTime
    if not created:
        raise RuntimeError('Cemu creation time unavailable')
    return f'{process.pid}:{created:016x}'


class CemuPresentationBackend:
    def __init__(self, process, cave, *, clock=time.monotonic, timeout=120,
                 native=None, guard=None, stability_guard=None,
                 identity=process_incarnation, evidence=None, explain=None):
        if native is None:
            from tools.cemu import owned_presentation as native
        if not process.writable:
            raise ValueError('Writable Cemu handle required')
        self.process, self.cave, self.native = process, cave, native
        self.clock, self.timeout, self.identity = clock, timeout, identity
        self.incarnation = identity(process)
        self.owner = native.inspect(process, cave.base)
        if self.owner['version'] != 2:
            raise ValueError('Native owner v2 required')
        if guard is None:
            from tools.cemu.presentation_ready import flag_reader, ready
            flags = flag_reader(process, cave)
            guard = lambda: ready(process, cave, flags)
        self.guard = guard
        self.explain = explain
        self.stability_guard = stability_guard or (lambda: True)
        self.session = f'{self.incarnation}:{cave.base:x}:{uuid.uuid4().hex}'
        self.generation = self.owner['state']['generation']
        self.samples = 0
        self.last_sample = None
        self.active = None
        self.last_submission = None
        self.stopped = False
        self.evidence = evidence
        self.evidence_error = None
        self.retry_after = 0.0
        self.wait_reason = 'checking native readiness'

    def _capture_evidence(self, phase):
        if self.evidence is not None:
            try:
                self.evidence.capture(phase, self.last_submission)
            except Exception as exc:
                # A diagnostic failure must not convert a known native result
                # into an uncertainty or cause another submission.
                self.evidence_error = f'{type(exc).__name__}: {exc}'

    def _check(self):
        if self.stopped or self.identity(self.process) != self.incarnation:
            self.stopped = True
            raise RuntimeError('Presentation adapter stopped or Cemu incarnation changed')

    def recovery_incarnation(self):
        """Read-only identity even when an uncertain submission stopped us."""
        if self.identity(self.process) != self.incarnation:
            raise RuntimeError('Cemu incarnation changed during recovery')
        return self.incarnation

    def _state(self):
        self._check()
        state = self.native.read(self.process, self.cave.base, self.owner['address'])
        join = self.native.read_join(self.process, self.cave.base, self.owner['join_address'])
        self._check()
        if state['version'] != 2 or state['generation'] != self.generation or state['fault']:
            self.stopped = True
            raise RuntimeError('Native generation/protocol changed or faulted')
        return state, join

    def ready(self):
        state, join = self._state()
        if self.clock() < self.retry_after:
            self.samples, self.last_sample = 0, None
            self.wait_reason = 'waiting before the next native attempt'
            return False
        available = (not state['busy'] and self.active is None and
                     (state['phase'] in ('idle', 'refused') or self.native.finished(state, join)))
        if not available or not self.guard():
            self.samples, self.last_sample = 0, None
            self.wait_reason = ('native presentation still busy' if not available
                                else 'UI conditions and presentation guards not met')
            return False
        now = self.clock()
        if self.last_sample is None or now - self.last_sample >= 0.1:
            if not self.stability_guard():
                self.samples, self.last_sample = 0, None
                self.wait_reason = 'game not yet stable for the presentation'
                return False
            self.samples += 1
            self.last_sample = now
        self.wait_reason = ('presentation ready' if self.samples >= 3
                            else 'native presentation conditions settling')
        return self.samples >= 3

    def wait_detail(self):
        """Why the presentation guard holds, read when the log asks (it reads the screens)."""
        if self.explain is None or not self.wait_reason.startswith('UI conditions'):
            return None
        try:
            return self.explain()
        except Exception as exc:  # noqa: BLE001 - a diagnostic only
            return f'unreadable: {exc}'

    def submit(self, request_id, title, description):
        try:
            if not self.ready():
                raise RuntimeError('Stable readiness not established')
            expected = self.generation + 1
            self.samples, self.last_sample = 0, None
            def final_guard():
                self._state()
                return self.guard()
            self.last_submission = {'request_id':request_id}
            self._capture_evidence('before')
            def checkpoint(update):
                self.last_submission.update(update)
            # native.request takes the emulator's mutex; the client's turn first
            # (botw_client/invoker_turn.py).
            from .invoker_turn import client_turn
            with client_turn():
                result = self.native.request(self.process, self.cave, self.owner, title,
                                             description, final_guard, checkpoint,
                                             resolution_quota=2)
            self.last_submission.update(result)
            self._capture_evidence('after')
            self._check()
            if result.get('status') == 'deferred' and result.get('generation') == self.generation:
                self.retry_after = self.clock() + 1.0
                return dict(status='deferred')
            if result.get('generation') != expected or result.get('status') not in ('accepted', 'refused'):
                raise RuntimeError('Native submission outcome unknown')
            self.generation = expected
            if result['status'] == 'refused' and isinstance(result.get('owner_after'), dict):
                state, join = self._state()
                text = self.cave.sub_state()
                retryable = refusal_has_no_action(state, join, text, expected)
                self.last_submission['refusal_proof'] = dict(
                    owner=state, join=join, text=list(text), retryable=retryable)
                self._capture_evidence('refusal_classified')
                if retryable:
                    self.retry_after = self.clock() + 2.0
                    return dict(status='retryable_refusal', session=self.session,
                                generation=expected)
            if result['status'] == 'accepted':
                self.active = dict(session=self.session, generation=expected)
                self.deadline = self.clock() + self.timeout
            return dict(status=result['status'], session=self.session, generation=expected)
        except Exception:
            self.stopped = True
            raise

    def poll(self, ticket):
        try:
            if self.active is None or ticket != self.active:
                raise RuntimeError('Foreign native ticket')
            state, join = self._state()
            if self.native.finished(state, join):
                self.active = None
                return dict(ticket, status='finished')
            if state['phase'] not in ('accepted', 'bound', 'action_complete', 'released', 'finished') or self.clock() >= self.deadline:
                raise RuntimeError('Native completion uncertain or timed out')
            return dict(ticket, status='pending')
        except Exception:
            self.stopped = True
            raise
