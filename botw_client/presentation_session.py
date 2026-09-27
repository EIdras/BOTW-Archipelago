"""Companion projection of the durable presentation journal, separate from grants."""
import hashlib
import json
from types import SimpleNamespace

from .presentation_store import PresentationStore
from .presentation_cemu import CemuPresentationBackend
from .message_text import clip_units


def clipped(text, units):
    # Never split a UTF-16 surrogate pair. Native capacities include the NUL.
    return clip_units(text, units)


def snapshot_ap(ap):
    """Freeze source data on the event-loop thread before the mailbox worker."""
    received, scouts = dict(ap.received_items), dict(ap.scouted_locations)
    def key(item):
        return item.item, item.location, item.player, getattr(item, 'flags', 0)
    items = list(received.values()) + list(scouts.values())
    names = {key(item): ap.item_name(item) for item in items}
    senders = {key(item): ap.sender(item) for item in items}
    locations = {item.location: ap.location_name(item.location) for item in items}
    return SimpleNamespace(slot=ap.slot, received_items=received, scouted_locations=scouts,
        item_name=lambda item:names[key(item)], sender=lambda item:senders[key(item)],
        location_name=lambda location:locations.get(location))


class NativePresentationSession:
    def __init__(self, state_path, identity, game, *, backend=None):
        if not identity or not identity[0] or identity[0] == 'unknown-seed':
            raise ValueError('A known AP session is required for persistent presentation')
        namespace = json.dumps(identity, ensure_ascii=False)
        digest = hashlib.sha256(namespace.encode()).hexdigest()
        path = state_path.parent / (state_path.name + '.presentations') / (digest + '.json')
        self.store = PresentationStore(path, namespace)
        try:
            if backend is not None:
                self.backend = backend
            else:
                from tools.cemu.presentation_ready import flag_reader, ready
                flags = flag_reader(game.process, game.cave)
                live_gate = getattr(game, "safe_for_delivery", None)
                allow_hudless = callable(live_gate)
                guard = lambda: ready(
                    game.process, game.cave, flags, allow_hudless=allow_hudless)
                options = {"guard": guard}
                import os
                evidence_path = os.environ.get('BOTW_PRESENTATION_EVIDENCE')
                cemu_log = os.environ.get('BOTW_CEMU_LOG')
                if evidence_path and cemu_log:
                    from .presentation_evidence import PresentationEvidence
                    options['evidence'] = PresentationEvidence(
                        evidence_path, game.process, game.cave, cemu_log)
                if allow_hudless:
                    options["stability_guard"] = live_gate
                self.backend = CemuPresentationBackend(
                    game.process, game.cave, **options)
        except BaseException:
            self.store.close()
            raise

    def close(self):
        self.store.close()

    def request_replay(self, request_id):
        self.store.queue.authorize_replay(request_id, self.backend.recovery_incarnation())

    def blocked_head(self):
        head = next((e for e in self.store.queue.snapshot()['entries']
                     if e['status'] != 'completed'), None)
        return head if head and head['status'] in ('uncertain', 'refused') else None

    @staticmethod
    def received_key(ap, index):
        item = ap.received_items[index]
        info = ap.scouted_locations.get(item.location)
        if (item.player == ap.slot and info is not None and info.player == ap.slot
                and info.item == item.item):
            return f'location/{item.location}'
        return f'received/{index}'

    def advance(self, state, ap, game, *, allow_submit=True, sources_ready=True,
                announce=None):
        """announce(index), when the AP journal is on (botw_client/ap_journal.py):
        every received item not yet presented is first announced there (the
        server's line), then 'pending' (line not shown yet: nothing from here
        on is enqueued, order kept), 'skip' (its delivery has the game's own
        get window: no AP window) or 'present' (AP window as usual). Locations
        whose item goes to another player get no AP window: the journal shows
        the server's "sent" line."""
        queue = self.store.queue
        head = self.blocked_head()
        if head and 'replay_after_incarnation' in head and allow_submit and sources_ready:
            incarnation = self.backend.recovery_incarnation()
            if (incarnation != head['replay_after_incarnation'] and self.backend.ready()):
                queue.replay_after_restart(incarnation)
        entries = {e['id']: e for e in queue.snapshot()['entries']}

        def enqueue(key, title, lines):
            # Freeze payload at first enqueue; reconnect may change nicknames.
            if key not in entries:
                entries[key] = queue.enqueue(key, clipped(title, 25),
                    clipped('\n'.join(clipped(line, 40) for line in lines[:4]), 255))

        def location_payload(location_id):
            info = ap.scouted_locations.get(location_id)
            if info is None:
                return
            recipient, recipient_game = ap.sender(info)
            enqueue(f'location/{location_id}', ap.item_name(info) or f'Item #{info.item}',
                    [f'For {recipient}', f'({recipient_game})', ap.location_name(location_id) or str(location_id)])

        def received_payload(index, item, key):
            name = ap.item_name(item)
            if not name:
                return
            sender, sender_game = ap.sender(item)
            delivery = game.item_map.get(name, {}).get('delivery', {})
            extra = delivery.get('text') if delivery.get('kind') == 'manual_prompt' else None
            lines = [f'From {sender}', f'({sender_game})']
            if extra:
                lines.extend(extra[i:i+40] for i in range(0, len(extra), 40))
            enqueue(key, name, lines)

        # AP summaries (items a reloaded save lost, given back silently).
        for summary in (state.get('summary_queue', []) if sources_ready else []):
            enqueue(summary['key'], summary['title'], summary['lines'])
        skipped, skipped_locations = [], []
        if announce is None:
            # Preserve the old priority, but enqueue both sources into one FIFO.
            for location_id in (state['location_display_queue'] if sources_ready else []):
                location_payload(int(location_id))
            for value in (state['display_queue'] if sources_ready else []):
                index = int(value)
                item = ap.received_items.get(index)
                if item is None:
                    continue
                key = self.received_key(ap, index)
                if key.startswith('location/'):
                    # Old shown is only a suppression history, not a native ACK.
                    if item.location in state['location_shown'] and key not in entries:
                        continue
                    location_payload(item.location)
                else:
                    received_payload(index, item, key)
        else:
            for location_id in (state['location_display_queue'] if sources_ready else []):
                info = ap.scouted_locations.get(int(location_id))
                # Items for this slot are presented as received items.
                if (info is not None and info.player != ap.slot
                        and f'location/{location_id}' not in entries):
                    skipped_locations.append(location_id)
            for value in (state['display_queue'] if sources_ready else []):
                index = int(value)
                item = ap.received_items.get(index)
                if item is None:
                    continue
                key = self.received_key(ap, index)
                if key in entries:
                    continue                  # already in the journal: as before
                decision = announce(index)
                if decision == 'pending':
                    break
                if decision == 'skip':
                    skipped.append((value, key))
                elif key.startswith('location/'):
                    location_payload(item.location)
                else:
                    received_payload(index, item, key)

        head = next((e for e in queue.snapshot()['entries'] if e['status'] != 'completed'), None)
        status = ('waiting_ready' if head and head['status'] == 'queued' and not allow_submit
                  else queue.tick(self.backend))
        completed = {e['id'] for e in queue.snapshot()['entries'] if e['status'] == 'completed'}
        changed = False

        def mark(value, pending, shown, confirmed, native):
            nonlocal changed
            if value in state[pending]:
                state[pending].remove(value)
                changed = True
            for field in ([shown, confirmed] if native else [shown]):
                if value not in state[field]:
                    state[field].append(value)
                    state[field].sort()
                    changed = True

        for value, key in skipped:
            # Announced by the journal; its vanilla window follows.
            mark(value, 'display_queue', 'shown', 'presentation_completed', True)
            if key.startswith('location/'):
                mark(int(key.split('/')[1]), 'location_display_queue', 'location_shown',
                     'location_presentation_completed', True)
        for location_id in skipped_locations:
            mark(location_id, 'location_display_queue', 'location_shown',
                 'location_presentation_completed', True)
        for key in completed:
            kind, raw = key.split('/')
            if kind == 'summary':
                pending = [s for s in state.get('summary_queue', []) if s['key'] != key]
                if pending != state.get('summary_queue', []):
                    state['summary_queue'] = pending
                    changed = True
            elif kind == 'location':
                mark(int(raw), 'location_display_queue', 'location_shown', 'location_presentation_completed', True)
            elif kind == 'received':
                mark(int(raw), 'display_queue', 'shown', 'presentation_completed', True)
        for value in (list(state['display_queue']) if sources_ready else []):
            index = int(value)
            if index not in ap.received_items:
                continue
            key = self.received_key(ap, index)
            if key in completed:
                mark(value, 'display_queue', 'shown', 'presentation_completed', True)
            elif key.startswith('location/') and key not in entries:
                if int(key.split('/')[1]) in state['location_shown']:
                    mark(value, 'display_queue', 'shown', 'presentation_completed', False)
        return status, changed
