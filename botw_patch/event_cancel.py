"""A cutscene played by an event flow made cancellable the game's own way.

A flow that plays a cutscene through its own actions (camera, animations,
waits, captions), rather than through a .bdemo timeline, is out of the skip
controller's reach. The game makes 28 such flows cancellable with three of its
own nodes: Demo_EventCancelStart opens a segment, Demo_EventCancelEnd closes it,
and the query CheckEventCancel then answers 1 when the segment was cancelled, 0
when it was played. The game puts only presentation in a segment, or tidies up
in case 1.

make_cancellable() wraps a segment of a flow's main path in those nodes. In case
1, the segment's effects are played again in their order, without their
presentation: a cancel must leave the game as the cutscene does. Each action of
the segment is either presentation (dropped) or an effect (played again); an
action in neither list stops the build, so that a new cutscene is looked at
rather than an effect lost.
"""
from __future__ import annotations

from evfl.common import StringHolder
from evfl.container import Container
from evfl.event import ActionEvent, Event, ForkEvent, JoinEvent, SubFlowEvent, SwitchEvent
from evfl.util import Index, make_rindex

SYSTEM = "EventSystemActor"
SOUND = "SceneSoundCtrlTag"
# The game's own parameters, the commonest in its cancellable flows.
START = ("Demo_EventCancelStart", {"IsWaitFinish": True, "ShowLogo": False})
END = ("Demo_EventCancelEnd", {"IsWaitFinish": True, "NoFadeIn": False})
QUERY = "CheckEventCancel"
CLEANUP = ((SYSTEM, "Demo_CloseMessageDialog", {"IsWaitFinish": True}),
           (SOUND, "Demo_KillAllDemoSound", {"IsWaitFinish": True}))

# What a cutscene only shows: camera, animations, waits, captions, rumble, sounds, effects.
PRESENTATION = frozenset({
    "Demo_WaitFrame", "Demo_CameraAnimFlow", "Demo_CameraAnimFlowAbs", "Demo_MovePosFlow",
    "Demo_Msg2CameraKeepState", "Demo_PlayASForDemo", "Demo_PlayASAdapt", "Demo_TrigNullASPlay",
    "Demo_OpenMessageDialog", "Demo_Talk", "Demo_Idling", "Demo_LookAtObject",
    "Demo_RumbleSmall", "Demo_RumbleMiddle", "Demo_RotRumble",
    "Demo_XLinkEventCreate", "Demo_XLinkEventKill", "Demo_XLinkEventFade",
    "Demo_SoundTrigger", "Demo_Ctrl", "Demo_FadeIn", "Demo_FadeOut",
})
# What a cutscene changes, played again by a cancel. Of the warps, the last only.
EFFECTS = frozenset({
    "Demo_FlagON", "Demo_FlagOFF", "Demo_SetGameDataInt",
    "Demo_EventBind", "Demo_BindOff", "Demo_Join", "Demo_PlayerHideOff", "Demo_PlayerShow",
    "Demo_BindSheikPad", "Demo_UnbindSheikPad",
    # The event's lighting: played again, it ends as the cutscene leaves it.
    "Demo_SetPaletteType", "Demo_SetDirectionalLight", "Demo_EventSetDiffuseAttenuate",
})
WARPS = frozenset({"Demo_WarpPlayerToDestination", "Demo_WarpPlayer"})


def segment(first: Event, last: Event) -> list[Event]:
    """The segment's events in the order they run, from `first` to `last` on the
    main path. A fork's branches run in their order, up to its join."""
    def fork_branch(event):
        out = []
        while event is not None:
            if isinstance(event.data, (SwitchEvent, JoinEvent)):
                raise ValueError(f"{event.name}: unexpected in a fork branch")
            if isinstance(event.data, ForkEvent):
                for fork in event.data.forks:
                    out += fork_branch(fork.v)
                event = event.data.join.v
                out.append(event)
                event = event.data.nxt.v
                continue
            out.append(event)
            event = event.data.nxt.v
        return out

    out, event = [], first
    while event is not None:
        if isinstance(event.data, SwitchEvent):
            raise ValueError(f"{event.name}: a choice in a cutscene segment")
        if isinstance(event.data, ForkEvent):
            for fork in event.data.forks:
                out += fork_branch(fork.v)
            event = event.data.join.v
        out.append(event)
        if event is last:
            return out
        event = event.data.nxt.v
    raise ValueError(f"{last.name} is not on the main path after {first.name}")


def action_name(event: Event) -> str | None:
    data = event.data
    return str(data.actor_action.v) if isinstance(data, ActionEvent) else None


def effects(events: list[Event]) -> list[Event]:
    """The events a cancel plays again: effects and sub-flows in their order, the last warp."""
    out, warp = [], None
    for event in events:
        data = event.data
        if isinstance(data, (ForkEvent, JoinEvent)):
            continue
        if isinstance(data, SubFlowEvent):
            out.append(event)
            continue
        name = action_name(event)
        if name in WARPS:
            warp = event
        elif name in EFFECTS:
            out.append(event)
        elif name not in PRESENTATION:
            raise ValueError(f"{event.name}: {name} is neither presentation nor a known effect")
    if warp is not None:
        out.append(warp)
    return out


def _actor(chart, name: str):
    actor = next((a for a in chart.actors
                  if a.identifier.name == name and not a.identifier.sub_name), None)
    if actor is None:
        raise ValueError(f"actor {name} not declared by {chart.name}")
    return actor


def _holder(items, name: str):
    found = next((item for item in items if str(item) == name), None)
    if found is None:
        found = StringHolder(name)
        items.append(found)
    return found


def make_cancellable(flow, after: str, last: str, prefix: str = "ApCancel") -> list[str]:
    """Wrap the main path from the event after `after` to `last` in a cancellable
    segment. The flow then goes on where `last` led. Returns the names of the
    events a cancel plays again, in order."""
    chart = flow.flowchart
    events = {event.name: event for event in chart.events}
    if any(name.startswith(prefix) for name in events):
        raise ValueError(f"{chart.name} already has a cancellable segment")
    before, end_of = events[after], events[last]
    if not isinstance(before.data, (ActionEvent, SubFlowEvent)):
        raise ValueError(f"{after}: a segment starts after a plain action")
    if not isinstance(end_of.data, (ActionEvent, SubFlowEvent, JoinEvent)):
        raise ValueError(f"{last}: a segment ends on a plain action or a join")
    replayed = effects(segment(before.data.nxt.v, end_of))
    resume = end_of.data.nxt.v
    created = []

    def new(data, name=None) -> Event:
        event = Event()
        event.name = name or f"{prefix}{len(created)}"
        event.data = data
        created.append(event)
        return event

    def action(actor_name, name, params) -> Event:
        actor = _actor(chart, actor_name)
        data = ActionEvent()
        data.actor = make_rindex(actor)
        data.actor_action = make_rindex(_holder(actor.actions, name))
        data.params = Container()
        data.params.data = dict(params)
        data.nxt = Index()
        return new(data)

    def copy(source: Event) -> Event:
        old = source.data
        data = type(old)()
        if isinstance(old, SubFlowEvent):
            data.res_flowchart_name = old.res_flowchart_name
            data.entry_point_name = old.entry_point_name
        else:
            data.actor = make_rindex(old.actor.v)
            data.actor_action = make_rindex(old.actor_action.v)
        data.params = Container()
        data.params.data = dict(old.params.data) if old.params else {}
        data.nxt = Index()
        return new(data)

    def link(chain: list[Event]) -> None:
        for a, b in zip(chain, chain[1:]):
            a.data.nxt = make_rindex(b)

    start = action(SYSTEM, *START)
    start.data.nxt = before.data.nxt
    before.data.nxt = make_rindex(start)
    end = action(SYSTEM, *END)
    end_of.data.nxt = make_rindex(end)
    tail = action(SYSTEM, "Demo_WaitFrame", {"IsWaitFinish": True, "Frame": 1})
    tail.data.nxt = make_rindex(resume) if resume is not None else Index()
    cancel = [action(actor, name, params) for actor, name, params in CLEANUP]
    cancel += [copy(event) for event in replayed]
    link(cancel + [tail])
    system = _actor(chart, SYSTEM)
    switch = SwitchEvent()
    switch.actor = make_rindex(system)
    switch.actor_query = make_rindex(_holder(system.queries, QUERY))
    switch.params = Container()
    switch.params.data = {}
    switch.cases = {0: make_rindex(tail), 1: make_rindex(cancel[0])}
    check = new(switch)
    end.data.nxt = make_rindex(check)
    chart.events.extend(created)
    return [event.name for event in replayed]
