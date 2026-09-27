"""Small, preconditioned edits of vanilla event graphs using Nintendo's actions.

Keep event names, entry points and graph links intact. A removed grant becomes
a one-frame wait, not a dangling reference or a post-hoc inventory rollback.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import evfl
from evfl.common import StringHolder, Argument, ActorIdentifier
from evfl.container import Container
from evfl.entry_point import EntryPoint
from evfl.event import ActionEvent, Event, SubFlowEvent
from evfl.util import Index, make_rindex

RUNE_FLAGS = frozenset({
    "IsGet_Obj_Magnetglove", "IsGet_Obj_RemoteBomb",
    "IsGet_Obj_StopTimer", "IsGet_Obj_IceMaker",
})


def read_flow(data: bytes) -> evfl.EventFlow:
    result = evfl.EventFlow()
    result.read(data)
    if result.flowchart is None:
        raise ValueError("expected a flowchart, not a timeline")
    return result


def write_flow(flow: evfl.EventFlow) -> bytes:
    expected = graph_snapshot(flow)
    stream = io.BytesIO()
    if not flow.write(stream):
        raise ValueError("EventFlow writer failed")
    result = stream.getvalue()
    reread = read_flow(result)
    if graph_snapshot(reread) != expected:
        raise ValueError("event graph changed during serialization")
    return result


def graph_snapshot(flow: evfl.EventFlow) -> dict:
    """Comparable graph semantics, independent of binary offsets and padding."""
    def value(v):
        if isinstance(v, (Argument, ActorIdentifier)):
            return (type(v).__name__, str(v))
        if isinstance(v, dict):
            return {k: value(x) for k, x in v.items()}
        if isinstance(v, list):
            return [value(x) for x in v]
        return v

    def ref(index):
        return index.v.name if index.v else None

    chart = flow.flowchart
    events = {}
    for event in chart.events:
        data = event.data
        node = {"type": type(data).__name__}
        for field in ("nxt", "join"):
            if hasattr(data, field):
                node[field] = ref(getattr(data, field))
        if hasattr(data, "forks"):
            node["forks"] = [ref(i) for i in data.forks]
        if hasattr(data, "cases"):
            node["cases"] = {k: ref(i) for k, i in data.cases.items()}
        if hasattr(data, "actor"):
            node["actor"] = str(data.actor.v.identifier)
        for field in ("actor_action", "actor_query"):
            if hasattr(data, field):
                node[field] = str(getattr(data, field).v)
        for field in ("res_flowchart_name", "entry_point_name"):
            if hasattr(data, field):
                node[field] = getattr(data, field)
        if hasattr(data, "params"):
            node["params"] = value(data.params.data) if data.params else {}
        events[event.name] = node
    return {"name": chart.name, "events": events,
            "entry_points": [(p.name, ref(p.main_event)) for p in chart.entry_points],
            "actors": [(str(a.identifier), a.argument_name, ref(a.argument_entry_point),
                        [str(x) for x in a.actions], [str(x) for x in a.queries],
                        value(a.params.data) if a.params else {}, a.concurrent_clips)
                       for a in chart.actors]}


def action_instead(flow, event, actor_name: str, action_name: str, params: dict):
    """Replace a linear event by one vanilla action of an actor of the flow.

    The actor must already be declared by the flow (no sub-name); the action is
    added to its list when missing. The successor is kept.
    """
    old = event.data
    if not isinstance(old, (ActionEvent, SubFlowEvent)):
        raise ValueError(f"cannot replace branching event {event.name}")
    actor = next((a for a in flow.flowchart.actors
                  if a.identifier.name == actor_name and not a.identifier.sub_name), None)
    if actor is None:
        raise ValueError(f"actor {actor_name} not declared by {flow.flowchart.name}")
    action = next((a for a in actor.actions if str(a) == action_name), None)
    if action is None:
        action = StringHolder(action_name)
        actor.actions.append(action)
    new = ActionEvent()
    new.actor = make_rindex(actor)
    new.actor_action = make_rindex(action)
    new.nxt = old.nxt
    new.params = Container()
    new.params.data = dict(params)
    event.data = new


def add_action_entry(flow, entry_name: str, actor_name: str, action_name: str,
                     params: dict) -> None:
    """Append an entry point running one vanilla action of a declared actor.

    Nothing existing changes: a new event and a new entry point are added.
    """
    chart = flow.flowchart
    if entry_name in {entry.name for entry in chart.entry_points}:
        raise ValueError(f"entry already present: {entry_name}")
    if entry_name in {event.name for event in chart.events}:
        raise ValueError(f"event name already present: {entry_name}")
    actor = next((a for a in chart.actors
                  if a.identifier.name == actor_name and not a.identifier.sub_name), None)
    if actor is None:
        raise ValueError(f"actor {actor_name} not declared by {chart.name}")
    action = next((a for a in actor.actions if str(a) == action_name), None)
    if action is None:
        action = StringHolder(action_name)
        actor.actions.append(action)
    event = Event()
    event.name = entry_name
    event.data = ActionEvent()
    event.data.actor = make_rindex(actor)
    event.data.actor_action = make_rindex(action)
    event.data.params = Container()
    event.data.params.data = dict(params)
    event.data.nxt = Index()
    chart.events.append(event)
    entry = EntryPoint(entry_name)
    entry.main_event = make_rindex(event)
    chart.entry_points.append(entry)


def add_action_after(flow, event_name: str, new_name: str, actor_name: str,
                     action_name: str, params: dict) -> None:
    """Insert one vanilla action right after a linear event (it inherits its successor).

    Used to restore a vanilla framing around an action we kept, without
    touching any existing event but the single edge that now points at the
    inserted one. The actor must already be declared by the flow.
    """
    chart = flow.flowchart
    events = {event.name: event for event in chart.events}
    if new_name in events:
        raise ValueError(f"event name already present: {new_name}")
    before = events[event_name]
    if not isinstance(before.data, (ActionEvent, SubFlowEvent)):
        raise ValueError(f"cannot insert after branching event {event_name}")
    actor = next((a for a in chart.actors
                  if a.identifier.name == actor_name and not a.identifier.sub_name), None)
    if actor is None:
        raise ValueError(f"actor {actor_name} not declared by {chart.name}")
    action = next((a for a in actor.actions if str(a) == action_name), None)
    if action is None:
        action = StringHolder(action_name)
        actor.actions.append(action)
    event = Event()
    event.name = new_name
    event.data = ActionEvent()
    event.data.actor = make_rindex(actor)
    event.data.actor_action = make_rindex(action)
    event.data.params = Container()
    event.data.params.data = dict(params)
    event.data.nxt = before.data.nxt
    before.data.nxt = make_rindex(event)
    chart.events.append(event)


def add_subflow_after(flow, event_name: str, new_name: str, flowchart: str,
                      entry: str, params: dict) -> None:
    """Insert a SubFlowEvent right after a linear event (it inherits its successor)."""
    chart = flow.flowchart
    events = {event.name: event for event in chart.events}
    if new_name in events:
        raise ValueError(f"event name already present: {new_name}")
    before = events[event_name]
    if not isinstance(before.data, (ActionEvent, SubFlowEvent)):
        raise ValueError(f"cannot insert after branching event {event_name}")
    event = Event()
    event.name = new_name
    event.data = SubFlowEvent()
    event.data.res_flowchart_name = flowchart
    event.data.entry_point_name = entry
    event.data.params = Container()
    event.data.params.data = dict(params)
    event.data.nxt = before.data.nxt
    before.data.nxt = make_rindex(event)
    chart.events.append(event)


def add_entry_to_event(flow, entry_name: str, event_name: str) -> None:
    """Append an entry point starting at an existing event (nothing else changes)."""
    chart = flow.flowchart
    if entry_name in {entry.name for entry in chart.entry_points}:
        raise ValueError(f"entry already present: {entry_name}")
    event = next(e for e in chart.events if e.name == event_name)
    entry = EntryPoint(entry_name)
    entry.main_event = make_rindex(event)
    chart.entry_points.append(entry)


def guard_with_query(flow, event_name: str, switch_name: str, actor_name: str,
                     query_name: str, params: dict, otherwise: str | None) -> None:
    """Run ``event_name`` only when a vanilla query answers 1.

    A SwitchEvent is inserted in front of the event and every reference to the
    event (successors, cases, forks, joins, entry points) is moved to it. Case 1
    leads to the event; case 0 to a one-frame wait whose successor is
    ``otherwise`` (None ends the entry).
    """
    from evfl.event import SwitchEvent
    chart = flow.flowchart
    events = {event.name: event for event in chart.events}
    if switch_name in events or switch_name + "_Skip" in events:
        raise ValueError(f"event name already present: {switch_name}")
    target = events[event_name]
    actor = next((a for a in chart.actors
                  if a.identifier.name == actor_name and not a.identifier.sub_name), None)
    if actor is None:
        raise ValueError(f"actor {actor_name} not declared by {chart.name}")
    query = next((q for q in actor.queries if str(q) == query_name), None)
    if query is None:
        query = StringHolder(query_name)
        actor.queries.append(query)
    wait = next((a for a in actor.actions if str(a) == "Demo_WaitFrame"), None)
    if wait is None:
        wait = StringHolder("Demo_WaitFrame")
        actor.actions.append(wait)
    skip = Event()
    skip.name = switch_name + "_Skip"
    skip.data = ActionEvent()
    skip.data.actor = make_rindex(actor)
    skip.data.actor_action = make_rindex(wait)
    skip.data.params = Container()
    skip.data.params.data = {"Frame": 1, "IsWaitFinish": True}
    skip.data.nxt = make_rindex(events[otherwise]) if otherwise else Index()
    switch = Event()
    switch.name = switch_name
    switch.data = SwitchEvent()
    switch.data.actor = make_rindex(actor)
    switch.data.actor_query = make_rindex(query)
    switch.data.params = Container()
    switch.data.params.data = dict(params)
    switch.data.cases = {1: make_rindex(target), 0: make_rindex(skip)}

    def moved(index):
        return make_rindex(switch) if index.v is target else index

    for event in chart.events:
        data = event.data
        for field in ("nxt", "join"):
            if hasattr(data, field) and getattr(data, field).v is target:
                setattr(data, field, moved(getattr(data, field)))
        if hasattr(data, "forks"):
            data.forks = [moved(index) for index in data.forks]
        if hasattr(data, "cases"):
            data.cases = {key: moved(index) for key, index in data.cases.items()}
    for entry in chart.entry_points:
        if entry.main_event.v is target:
            entry.main_event = make_rindex(switch)
    chart.events.extend([switch, skip])


@dataclass(frozen=True)
class SubFlowStep:
    """A chain element of branch_with_query calling another flow's entry."""
    flowchart: str
    entry: str


def branch_with_query(flow, event_name: str, switch_name: str, actor_name: str,
                      query_name: str, params: dict, chain: list[tuple[str, str, dict]],
                      rejoin: str) -> None:
    """Choose between an event and a new linear chain with a vanilla query.

    A SwitchEvent is inserted in front of ``event_name`` and every reference to
    the event is moved to it. Case 0 leads to the event, unchanged; case 1 to
    ``chain``, a list of (name, action, params) actions of ``actor_name`` run
    in order (an action may be a SubFlowStep: a call to another flow's entry),
    the last one continuing at ``rejoin``.
    """
    from evfl.event import SwitchEvent
    chart = flow.flowchart
    events = {event.name: event for event in chart.events}
    if not chain:
        raise ValueError("empty branch")
    for name in (switch_name, *(name for name, _action, _params in chain)):
        if name in events:
            raise ValueError(f"event name already present: {name}")
    target = events[event_name]
    actor = next((a for a in chart.actors
                  if a.identifier.name == actor_name and not a.identifier.sub_name), None)
    if actor is None:
        raise ValueError(f"actor {actor_name} not declared by {chart.name}")

    def holder(collection, name):
        found = next((value for value in collection if str(value) == name), None)
        if found is None:
            found = StringHolder(name)
            collection.append(found)
        return found

    query = holder(actor.queries, query_name)
    added = []
    nxt = events[rejoin]
    for name, action_name, action_params in reversed(chain):
        event = Event()
        event.name = name
        if isinstance(action_name, SubFlowStep):
            event.data = SubFlowEvent()
            event.data.res_flowchart_name = action_name.flowchart
            event.data.entry_point_name = action_name.entry
        else:
            event.data = ActionEvent()
            event.data.actor = make_rindex(actor)
            event.data.actor_action = make_rindex(holder(actor.actions, action_name))
        event.data.params = Container()
        event.data.params.data = dict(action_params)
        event.data.nxt = make_rindex(nxt)
        added.append(event)
        nxt = event
    switch = Event()
    switch.name = switch_name
    switch.data = SwitchEvent()
    switch.data.actor = make_rindex(actor)
    switch.data.actor_query = make_rindex(query)
    switch.data.params = Container()
    switch.data.params.data = dict(params)
    switch.data.cases = {1: make_rindex(nxt), 0: make_rindex(target)}

    def moved(index):
        return make_rindex(switch) if index.v is target else index

    for event in chart.events:
        data = event.data
        for field in ("nxt", "join"):
            if hasattr(data, field) and getattr(data, field).v is target:
                setattr(data, field, moved(getattr(data, field)))
        if hasattr(data, "forks"):
            data.forks = [moved(index) for index in data.forks]
        if hasattr(data, "cases"):
            data.cases = {key: moved(index) for key, index in data.cases.items()}
    for entry in chart.entry_points:
        if entry.main_event.v is target:
            entry.main_event = make_rindex(switch)
    chart.events.extend([switch, *reversed(added)])


def wait_instead(flow, event, frames: int = 1):
    action_instead(flow, event, "EventSystemActor", "Demo_WaitFrame",
                   {"Frame": frames, "IsWaitFinish": True})


def suppress_terminal_rewards(data: bytes) -> tuple[bytes, list[str]]:
    flow = read_flow(data)
    if flow.flowchart.name != "Demo003_0":
        raise ValueError("wrong terminal flow")
    changed = []
    flags = set()
    for event in flow.flowchart.events:
        action = event.data
        if not isinstance(action, ActionEvent):
            continue
        name = str(action.actor_action.v)
        params = action.params.data if action.params else {}
        flag = params.get("FlagName")
        if name == "Demo_FlagON" and flag in RUNE_FLAGS:
            flags.add(flag)
            wait_instead(flow, event)
            changed.append(event.name)
        elif name not in {"Demo_OpenItemDownloadDemo", "Demo_WaitCloseItemDownloadDemo"}:
            continue
        else:
            wait_instead(flow, event)
            changed.append(event.name)
    if flags != RUNE_FLAGS:
        raise ValueError(f"terminal grants do not match supported layout: {flags}")
    return write_flow(flow), changed


def suppress_reward(data: bytes, actor_name: str, expected_count: int = 1) -> tuple[bytes, list[str]]:
    flow = read_flow(data)
    changed = []
    for event in flow.flowchart.events:
        action = event.data
        if (isinstance(action, SubFlowEvent)
                and action.res_flowchart_name == "GetDemo"
                and action.entry_point_name == "GetItemByName"
                and action.params
                and action.params.data.get("CheckTargetActorName") == actor_name):
            wait_instead(flow, event)
            changed.append(event.name)
    if len(changed) != expected_count:
        raise ValueError(f"{flow.flowchart.name}: {len(changed)} grants, expected {expected_count}")
    return write_flow(flow), changed


def suppress_champion_rewards(data: bytes) -> tuple[bytes, list[str]]:
    changes = []
    for race in ("Rito", "Goron", "Gerudo", "Zora"):
        data, changed = suppress_reward(data, f"Obj_HeroSoul_{race}")
        changes.extend(changed)
    return data, changes
