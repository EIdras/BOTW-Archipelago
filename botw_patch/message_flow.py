"""Offline resource stage for AP dialogue; no grants or runtime activation.

The carrier is the one used by the historical saydialog experiment. Arbitrary
AP text and request ownership still require a dedicated native adapter.
"""
import copy

import oead
from evfl.common import StringHolder
from evfl.container import Container
from evfl.entry_point import EntryPoint
from evfl.event import ActionEvent, Event
from evfl.util import Index, make_rindex

from .events import graph_snapshot, read_flow, write_flow
from .resources import unpack

FLOW = 'Demo007_1'
ENTRY = 'APMessageStandalone'
EVENT = 'APMessage_Dialog'
ACTION = 'Demo_OpenDungeonMessage'
CARRIER = 'DemoMsg/Demo008_2:talk00'
MARKER = 'DemoMsg/AP_Message:Text'


def add_message_entry(raw, *, owned=False):
    flow = read_flow(raw)
    chart = flow.flowchart
    before = graph_snapshot(flow)
    if chart.name != FLOW:
        raise ValueError('AP messages require the resident Demo007_1 flow')
    if any(p.name == ENTRY for p in chart.entry_points) or any(
            event.name == EVENT for event in chart.events):
        raise ValueError('AP message entry/event already exists')
    actors = [a for a in chart.actors if str(a.identifier) == 'EventSystemActor']
    if len(actors) != 1:
        raise ValueError('Expected one unqualified EventSystemActor')
    actor = actors[0]
    if actor.argument_name or actor.argument_entry_point.v is not None:
        raise ValueError('EventSystemActor must not depend on another entry')
    actions = [a for a in actor.actions if str(a) == ACTION]
    if len(actions) > 1:
        raise ValueError('Ambiguous message action binding')
    if not actions:
        actor.actions.append(StringHolder(ACTION))
    action = actions[0] if actions else actor.actions[-1]
    event = Event()
    event.name = EVENT
    event.data = ActionEvent()
    event.data.actor = make_rindex(actor)
    event.data.actor_action = make_rindex(action)
    event.data.params = Container()
    message_id = MARKER if owned else CARRIER
    event.data.params.data = {'IsWaitFinish': True, 'MessageId': message_id}
    event.data.nxt = Index()
    chart.events.append(event)
    entry = EntryPoint(ENTRY)
    entry.main_event = make_rindex(event)
    chart.entry_points.append(entry)
    result = write_flow(flow)
    after = graph_snapshot(read_flow(result))
    # Compare the complete graph, including all existing actor bindings.
    expected = copy.deepcopy(before)
    if not actions:
        next(a for a in expected['actors'] if a[0] == 'EventSystemActor')[3].append(ACTION)
    expected['events'][EVENT] = dict(type='ActionEvent', nxt=None,
        actor='EventSystemActor', actor_action=ACTION,
        params={'IsWaitFinish': True, 'MessageId': message_id})
    expected['entry_points'].append((ENTRY, EVENT))
    if after != expected:
        raise ValueError('AP message stage changed unrelated graph semantics')
    return result, ['isolated waiting dialogue entry; no grant, flags, forced close or campfire continuation']


def add_message_info(raw):
    info = oead.byml.from_binary(unpack(raw))
    key = f'{FLOW}<{ENTRY}>'
    if key in info:
        raise ValueError('AP message EventInfo already exists')
    donor = info[f'{FLOW}<{FLOW}>']
    fields = ('demo_event', 'is_timeline', 'mode', 'slink_user', 'special_actor_name')
    if any(field not in donor for field in fields) or bool(donor['is_timeline']):
        raise ValueError('Incompatible message EventInfo donor')
    info[key] = oead.byml.Hash({field: copy.deepcopy(donor[field]) for field in fields})
    return bytes(oead.yaz0.compress(oead.byml.to_binary(info, big_endian=True))), [
        'register standalone message without campfire camera or transforms']
