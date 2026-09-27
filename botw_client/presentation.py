"""Single-writer presentation queue, separate from item delivery and save ledger.

The caller supplies a durable atomic journal commit and a backend implementing
the validated native finish/readiness contract. This module is not wired to
the legacy bool-returning game display API. Recovered in-flight work is always
uncertain: volatile native generations cannot establish cross-session identity.
"""
from copy import deepcopy


class PresentationQueue:
    STATES={'queued','dispatching','accepted','completed','uncertain','refused'}

    def __init__(self, namespace, commit, snapshot=None):
        if not isinstance(namespace,str) or not namespace:
            raise ValueError('Explicit queue namespace required')
        self.commit=commit
        self.broken=False
        self.state=deepcopy(snapshot) if snapshot is not None else dict(version=1,namespace=namespace,entries=[])
        self._validate(namespace)
        recovered=False
        for entry in self.state['entries']:
            if entry['status'] in ('dispatching','accepted'):
                entry.update(status='uncertain',detail='Recovered in-flight request; no automatic replay')
                recovered=True
        if recovered:
            self._save()

    @staticmethod
    def _payload(title,description):
        for text,capacity in ((title,256),(description,512)):
            if not isinstance(text,str) or '\0' in text or len(text.encode('utf-16-be'))+2>capacity:
                raise ValueError('Invalid presentation text')

    def _validate(self,namespace):
        s=self.state
        if s.get('version')!=1 or s.get('namespace')!=namespace or not isinstance(s.get('entries'),list):
            raise ValueError('Queue journal version/namespace mismatch')
        seen=set()
        nonterminal=False
        for e in s['entries']:
            if not isinstance(e,dict) or not isinstance(e.get('id'),str) or not e['id'] or e['id'] in seen:
                raise ValueError('Invalid/duplicate request identity')
            seen.add(e['id'])
            if type(e.get('attempts')) is not int or e['attempts']<0:
                raise ValueError('Invalid attempt count')
            self._payload(e.get('title'),e.get('description'))
            if e.get('status') not in self.STATES:
                raise ValueError('Unknown presentation state')
            if e['status']=='completed' and nonterminal:
                raise ValueError('Completion out of FIFO order')
            if e['status']!='completed':
                if nonterminal and e['status']!='queued':
                    raise ValueError('Multiple in-flight requests')
                nonterminal=True
            if e['status'] in ('accepted','completed') and not self._ticket(e.get('ticket',{})):
                raise ValueError('Missing native request identity')
            if 'replay_after_incarnation' in e:
                if (e['status'] not in ('uncertain','refused')
                        or not isinstance(e['replay_after_incarnation'],str)
                        or not e['replay_after_incarnation']):
                    raise ValueError('Invalid replay authorization')

    @staticmethod
    def _ticket(ticket):
        return (isinstance(ticket,dict) and isinstance(ticket.get('session'),str) and bool(ticket['session'])
                and type(ticket.get('generation')) is int and 0<ticket['generation']<=0xffffffff)

    def snapshot(self):
        return deepcopy(self.state)

    def _save(self):
        try:
            self.commit(self.snapshot())
        except BaseException:
            self.broken=True
            raise

    def enqueue(self,request_id,title,description):
        if self.broken:
            raise RuntimeError('Journal unavailable; queue stopped')
        if not isinstance(request_id,str) or not request_id:
            raise ValueError('Explicit request identity required')
        self._payload(title,description)
        for e in self.state['entries']:
            if e['id']==request_id:
                if (e['title'],e['description'])!=(title,description):
                    raise ValueError('Same identity with different payload')
                return deepcopy(e)
        entry=dict(id=request_id,title=title,description=description,status='queued',attempts=0)
        self.state['entries'].append(entry)
        self._save()
        return deepcopy(entry)

    def tick(self,backend):
        """One bounded operation; backend.ready includes gameplay/UI/protections.

        submit(id,title,description) returns status deferred/accepted/refused/uncertain;
        deferred proves that the native wrapper was not called and generation
        did not advance, so the durable head may safely remain queued;
        accepted also includes session and generation. poll(ticket) returns
        pending/finished/uncertain and the same session/generation. finished must
        mean the joined native proof, never acceptance or UI disappearance alone.
        """
        if self.broken:
            raise RuntimeError('Journal unavailable; queue stopped')
        entry=next((e for e in self.state['entries'] if e['status']!='completed'),None)
        if entry is None:
            return 'idle'
        status=entry['status']
        if status in ('uncertain','refused','dispatching'):
            return status
        if status=='queued':
            if not backend.ready():
                return 'waiting_ready'
            entry.update(status='dispatching',attempts=entry['attempts']+1)
            self._save()  # Must complete durably BEFORE any native submission.
            try:
                result=backend.submit(entry['id'],entry['title'],entry['description'])
                if result.get('status')=='accepted' and self._ticket(result):
                    ticket={k:result[k] for k in ('session','generation')}
                    if any(e is not entry and e.get('ticket')==ticket for e in self.state['entries']):
                        entry.update(status='uncertain',detail='Native identity already used by another request')
                    else:
                        entry.update(status='accepted',ticket=ticket)
                elif result.get('status')=='deferred':
                    entry.update(status='queued',attempts=entry['attempts']-1,
                                 detail='Native presentation resource not ready; no request submitted')
                elif result.get('status')=='retryable_refusal' and self._ticket(result):
                    entry.update(status='queued',
                                 detail='Native refusal without action; automatic retry after readiness',
                                 last_refusal_ticket={k:result[k] for k in ('session','generation')})
                elif result.get('status')=='refused':
                    entry.update(status='refused',detail='Explicit native refusal; no automatic retry')
                else:
                    entry.update(status='uncertain',detail='Submission outcome not established')
            except Exception as exc:
                entry.update(status='uncertain',detail=str(exc))
        elif status=='accepted':
            try:
                result=backend.poll(deepcopy(entry['ticket']))
                matches=all(result.get(k)==v for k,v in entry['ticket'].items())
                if not matches or result.get('status') not in ('pending','finished'):
                    entry.update(status='uncertain',detail='Native completion identity/outcome not established')
                elif result['status']=='finished':
                    entry.update(status='completed')
                else:
                    return 'accepted'
            except Exception as exc:
                entry.update(status='uncertain',detail=str(exc))
        self._save()
        return entry['status']

    def retry_refused(self,request_id):
        """Explicit caller decision, only for a proven refusal; never uncertainty."""
        if self.broken:
            raise RuntimeError('Journal unavailable; queue stopped')
        entry=next((e for e in self.state['entries'] if e['status']!='completed'),None)
        if entry is None or entry['id']!=request_id or entry['status']!='refused':
            raise ValueError('Only the explicitly refused head can be retried')
        if 'replay_after_incarnation' in entry:
            raise ValueError('Authorized recovery requires a fresh Cemu process')
        entry.update(status='queued')
        self._save()

    def authorize_replay(self,request_id,incarnation):
        """Explicit decision to replay an announcement after Cemu restarts.

        This never acknowledges presentation completion or touches delivery.
        The caller provides the identity of the currently attached process.
        """
        if self.broken:
            raise RuntimeError('Journal unavailable; queue stopped')
        entry=next((e for e in self.state['entries'] if e['status']!='completed'),None)
        if entry is None or entry['id']!=request_id or entry['status'] not in ('uncertain','refused'):
            raise ValueError('Only the blocked FIFO head can be authorized for replay')
        if not isinstance(incarnation,str) or not incarnation:
            raise ValueError('Cemu incarnation required')
        # Repeated commands must not postpone an already authorized recovery.
        if 'replay_after_incarnation' not in entry:
            entry['replay_after_incarnation']=incarnation
            self._save()

    def replay_after_restart(self,incarnation):
        """Caller must establish readiness in a fresh Cemu process first."""
        if self.broken:
            raise RuntimeError('Journal unavailable; queue stopped')
        entry=next((e for e in self.state['entries'] if e['status']!='completed'),None)
        if not entry or 'replay_after_incarnation' not in entry:
            return False
        if not isinstance(incarnation,str) or not incarnation:
            raise ValueError('Cemu incarnation required')
        if incarnation==entry['replay_after_incarnation']:
            return False
        entry.setdefault('recovery_history',[]).append({
            'decision':'explicit_announcement_replay',
            'previous_status':entry['status'], 'attempts':entry['attempts'],
            'ticket':deepcopy(entry.get('ticket')), 'detail':entry.get('detail'),
            'after_incarnation':entry.pop('replay_after_incarnation'),
            'resumed_incarnation':incarnation,
        })
        entry.pop('ticket',None)
        entry.pop('detail',None)
        entry['status']='queued'
        self._save()  # A crash here may only recover queued work, never a grant.
        return True
