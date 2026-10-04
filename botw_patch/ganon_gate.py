"""The Ganon gate: the sanctum of Hyrule Castle stays sealed until the seed's
requirements are met.

The final fight has one start in the game's map (E-4): entering the cylinder
Area 264383435 (centre -254, 297, -1061, radius 25), behind the sanctum's
doors, signals the EventTag of HyruleCastle<BossRoom0>, the whole fight (the
curse Ganons of the Divine Beasts still held, then Calamity Ganon, Demo142_0).
The Area signals again on each entry.

This stage puts a check before that entry's first event:
  * APGanonOpen set (the client sets it, saved, once the requirements are
    met): the fight as in the game;
  * otherwise: APGanonRefused on (volatile: the client names in the AP journal
    what is still missing), a fade, Link back before the doors (measured in
    game on 04/10, 36 m from the Area's edge) facing away, the fade back, and
    the shrines' blue text (Demo_OpenDungeonMessage, as a shrine's monk
    speaks) saying that a seal still guards the sanctum.
Nothing of the fight runs nor any of its flags is set.

The text is a label added to DemoMsg/Demo033_0 in every language
(generate_texts), shaped as its talk07, the monks' own short line.
"""
from __future__ import annotations

from evfl.common import StringHolder
from evfl.container import Container
from evfl.event import ActionEvent, Event, SwitchEvent
from evfl.util import Index, make_rindex

from pathlib import Path
import tempfile

import oead

from botw_patch.events import graph_snapshot, read_flow, write_flow
from botw_patch.resources import ResourceBuilder, digest, unpack

PACK = "Event/HyruleCastle.sbeventpack"
PACKS = {PACK: "18a747e4ec97bceb0e6c39e36282c84ebb7fd48c9a218c54c7671ef73eb42db2"}
FLOW = "EventFlow/HyruleCastle.bfevfl"
FLOW_SHA = "46b73af59502134e25567cb074b2b53b482b916c9a6d817408aac9838081e91c"
ENTRY = "BossRoom0"
FIRST = "Event205"
GAMEDATA = "GameData/gamedata.ssarc"
OPEN = "APGanonOpen"
REFUSED = "APGanonRefused"
# Before the sanctum's doors, outside the Area; Y a little above the floor.
OUTSIDE = (-254.0, 300.0, -1000.0)
FACING = 0.0                    # degrees: away from the doors (the fight's own warp faces -180)
SOURCE_FILES = ("botw_patch/ganon_gate.py",)
MSBT = "DemoMsg/Demo033_0.msbt"
MODEL_LABEL = "talk07"
LABEL = "APGanonSealed"
MESSAGE = f"DemoMsg/Demo033_0:{LABEL}"
SEALED = {
    "EUde": "Ein Siegel schützt dieses\nHeiligtum noch. Kehre zurück, wenn\ndeine Aufgabe erfüllt ist.",
    "EUen": "A seal still guards this sanctum.\nReturn once your quest is complete.",
    "EUes": "Un sello protege aún este santuario.\nVuelve cuando hayas cumplido\ntu misión.",
    "EUfr": "Un sceau protège encore ce sanctuaire.\nReviens lorsque ta quête sera\naccomplie.",
    "EUit": "Un sigillo protegge ancora questo\nsantuario. Torna quando avrai\ncompiuto la tua missione.",
    "EUnl": "Een zegel beschermt dit heiligdom nog.\nKeer terug wanneer je taak\nvoltooid is.",
    "EUru": "Святилище всё ещё запечатано.\nВозвращайся, когда завершишь\nсвоё задание.",
}


def transform(raw: bytes) -> tuple[bytes, list[str]]:
    if digest(raw) != FLOW_SHA:
        raise ValueError("HyruleCastle flow changed")
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    chart = flow.flowchart
    entry = next(e for e in chart.entry_points if e.name == ENTRY)
    first = entry.main_event.v
    if first.name != FIRST:
        raise ValueError(f"{ENTRY} starts with {first.name}, not {FIRST}")
    system = next(a for a in chart.actors if str(a.identifier) == "EventSystemActor")
    fader = next(a for a in chart.actors if str(a.identifier) == "Fader")

    def holder(collection, name):
        found = next((value for value in collection if str(value) == name), None)
        if found is None:
            if name != "Demo_OpenDungeonMessage":
                raise ValueError(f"the flow's actor lacks {name}")
            found = StringHolder(name)
            collection.append(found)
        return found

    def action(name, actor, command, params, nxt=None):
        event = Event()
        event.name = name
        event.data = ActionEvent()
        event.data.actor = make_rindex(actor)
        event.data.actor_action = make_rindex(holder(actor.actions, command))
        event.data.params = Container()
        event.data.params.data = params
        event.data.nxt = make_rindex(nxt) if nxt is not None else Index()
        chart.events.append(event)
        return event

    sealed = action("APGanonGate_Sealed", system, "Demo_OpenDungeonMessage",
                    {"IsWaitFinish": True, "MessageId": MESSAGE})
    fade_in = action("APGanonGate_FadeIn", fader, "Demo_FadeIn",
                     {"Color": 1, "DispMode": "Auto", "Frame": 0, "IsWaitFinish": True}, sealed)
    x, y, z = OUTSIDE
    warp = action("APGanonGate_Warp", system, "Demo_WarpPlayerToDestination",
                  {"IsWaitFinish": True, "DestinationX": x, "DestinationY": y, "DestinationZ": z,
                   "DirectionY": FACING}, fade_in)
    fade_out = action("APGanonGate_FadeOut", fader, "Demo_FadeOut",
                      {"Color": 1, "DispMode": "NoLogo", "Frame": 0, "IsWaitFinish": True}, warp)
    refused = action("APGanonGate_Refused", system, "Demo_FlagON",
                     {"IsWaitFinish": True, "FlagName": REFUSED}, fade_out)
    gate = Event()
    gate.name = "APGanonGate"
    gate.data = SwitchEvent()
    gate.data.actor = make_rindex(system)
    gate.data.actor_query = make_rindex(holder(system.queries, "CheckFlag"))
    gate.data.params = Container()
    gate.data.params.data = {"FlagName": OPEN}
    gate.data.cases = {0: make_rindex(refused), 1: make_rindex(first)}
    chart.events.append(gate)
    if len({e.name for e in chart.events}) != len(chart.events):
        raise ValueError("gate event names already present")
    entry.main_event = make_rindex(gate)
    out = write_flow(flow)
    after = graph_snapshot(read_flow(out))
    if any(after["events"].get(name) != node for name, node in before["events"].items()):
        raise ValueError("existing event changed")
    expected = [(name, "APGanonGate" if name == ENTRY else event)
                for name, event in before["entry_points"]]
    if after["entry_points"] != expected:
        raise ValueError("entry points changed beyond the gate")
    return out, [f"HyruleCastle<{ENTRY}>: {OPEN} checked first; closed, {REFUSED} on and Link "
                 f"back to {OUTSIDE}"]


def add_flags(raw: bytes) -> tuple[bytes, list[str]]:
    """APGanonOpen (saved bool) and APGanonRefused (volatile bool)."""
    from tools.build_game_data_mod import modify_gamedata_flags
    raw = modify_gamedata_flags(raw, (OPEN,), is_save=True, kind="bool")
    raw = modify_gamedata_flags(raw, (REFUSED,), is_save=False, kind="bool")
    return raw, [f"register saved bool {OPEN}", f"register volatile bool {REFUSED}"]


def generate_texts(files: dict[str, bytes], content: Path) -> tuple[dict[str, bytes], list[dict]]:
    """The sealed sanctum's line, added to DemoMsg/Demo033_0 in every language
    of the overlay being built (after the stages that already changed the
    message archives)."""
    from botw_patch.shop_items import add_labels
    from botw_patch.status_item import INPUT_HASHES, LANGUAGES
    table = "System/Resource/ResourceSizeTable.product.srsizetable"
    inputs = {}
    for language in LANGUAGES:
        name = f"Pack/Bootup_{language}.pack"
        if name in files:           # already changed by an earlier stage
            inputs[name] = files[name]
            continue
        raw = (content / name).read_bytes()
        if digest(raw) != INPUT_HASHES[name]:
            raise ValueError(f"unexpected update resource: {name}")
        inputs[name] = raw
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        stage = Path(temp)
        for name, raw in {**inputs, table: files[table]}.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        builder = ResourceBuilder(stage)
        for language in LANGUAGES:
            def messages(raw, language=language):
                archive = oead.Sarc(unpack(raw))
                writer = oead.SarcWriter.from_sarc(archive)
                writer.files[MSBT], detail = add_labels(bytes(archive.get_file(MSBT).data),
                                                        {LABEL: SEALED[language]}, MODEL_LABEL)
                packed = bytes(writer.write()[1])
                return (bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else packed), detail

            builder.patch_archive(f"Pack/Bootup_{language}.pack",
                                  {f"Message/Msg_{language}.product.ssarc": messages})
        out = builder.finish()
        changes = builder.changes
    files = dict(files)
    files.update(out)
    return files, changes
