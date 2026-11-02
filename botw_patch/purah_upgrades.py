"""Purah's rune upgrades, three locations: she no longer upgrades the runes.

At Hateno's Ancient Tech Lab, once the Slate's camera is restored, Purah
powers up a rune for three ancient materials (Npc_AncientDoctor, entry
SelectPowerUp): screws for the Sheikah Sensor, shafts for Remote Bomb, cores
for Stasis. Her flow checks the materials only, never that the rune is owned,
and the upgrade is the rune's IsGet_Obj_*Lv2 flag (set by Demo032_0). In AP the
"+" is the second copy of the rune's item, which the multiworld alone gives;
Purah's three upgrades become locations.

Each upgrade calls PowerUpDemo with the flag it sets first (FlagName, a
Hateno_*Lv2_Choice flag, volatile, which Demo032_0 reads to pick the rune,
then clears). This stage changes, in each copy of her flow:
  * the three calls: FlagName is the location's own saved flag (FLAGS), so the
    materials are still taken (Event524) and the upgrade still counted (Event522);
  * PowerUpDemo's Demo_CallDemo Demo032_0 (Event525): a one-frame wait, no rune
    is upgraded;
  * the nine checks of the Lv2 flags, which decide that she has upgraded all
    (Event225-227, Event363-365) and what she explains (Event451-453): the
    location flags, so a "+" received early takes no upgrade away from her.
Her choice (EventFlowMsg/Npc_AncientDoctor:talk31) hides each rune already
upgraded by a condition on its Lv2 flag; generate_texts points it at the
location flag in every language: the flags have the names' lengths, so the
tag keeps its bytes' count.
Her flow has three identical copies, in three event packs; each is changed.
"""
from __future__ import annotations

from pathlib import Path
import tempfile

import oead

from botw_client import regions
from botw_patch.events import graph_snapshot, read_flow, wait_instead, write_flow
from botw_patch.resources import ResourceBuilder, unpack, vanilla_digest

PACKS = {
    "Event/Npc_AncientDoctor.sbeventpack": "bdb45dae11c63ce848d6a9ec94412bd19d4dd8aebcb29cf7134e8eff0dbba5b6",
    "Event/Hateno_SheikPad_PowerUp.sbeventpack": "d0500cbc5aaf6c4298d7e6c8ef29a3498a1ba6e356e43971d25c1941f97a774b",
    "Event/CarryingBlueFireEXMini.sbeventpack": "6630ba6f19eb644d310336c83ece64375dcf0048a10b5cfc9a40379c182bc791",
}
FLOW = "EventFlow/Npc_AncientDoctor.bfevfl"
FLOW_SHA = "8da3db3b304fb10b641d2100ec16210a03279f5462d572097c1404964ce21487"
# rune: (its Lv2 flag, the location's flag, the volatile choice flag, the call).
FLAGS = {
    "Sheikah Sensor": ("IsGet_Obj_SheikSensorLv2", "APPurahUp_SheikSensorLv2",
                       "Hateno_SheikSensorLv2_Choice", "Event537"),
    "Remote Bomb": ("IsGet_Obj_RemoteBombLv2", "APPurahUp_RemoteBombLv2",
                    "Hateno_RemoteBombLv2_Choice", "Event536"),
    "Stasis": ("IsGet_Obj_StopTimerLv2", "APPurahUp_StopTimerLv2",
               "Hateno_StopTimerLv2_Choice", "Event534"),
}
LOCATION_FLAGS = tuple(flag for _lv2, flag, _choice, _call in FLAGS.values())
UPGRADE = "Event525"
CHECKS = ("Event225", "Event226", "Event227", "Event363", "Event364", "Event365",
          "Event451", "Event452", "Event453")
GAMEDATA = "GameData/gamedata.ssarc"
SAVEFORMAT = "GameData/savedataformat.ssarc"
MSBT = "EventFlowMsg/Npc_AncientDoctor.msbt"
SOURCE_FILES = ("botw_patch/purah_upgrades.py",)


def transform(raw: bytes) -> tuple[bytes, list[str]]:
    if vanilla_digest(raw) != FLOW_SHA:
        raise ValueError("Purah's flow changed")
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    nodes = before["events"]
    events = {event.name: event for event in flow.flowchart.events}
    location = {lv2: flag for lv2, flag, _choice, _call in FLAGS.values()}
    for _rune, (_lv2, flag, choice, call) in FLAGS.items():
        node = nodes[call]
        if (node.get("entry_point_name") != "PowerUpDemo" or node.get("res_flowchart_name")
                or node["params"].get("FlagName") != choice):
            raise ValueError(f"Purah's upgrade call changed: {call}")
        events[call].data.params.data["FlagName"] = flag
    readers = {name for name, node in nodes.items()
               if node.get("params", {}).get("FlagName") in location}
    if readers != set(CHECKS) or any(nodes[name].get("actor_query") != "CheckFlag" for name in CHECKS):
        raise ValueError(f"Purah's checks of the upgrades changed: {sorted(readers)}")
    for name in CHECKS:
        events[name].data.params.data["FlagName"] = location[nodes[name]["params"]["FlagName"]]
    upgrade = nodes[UPGRADE]
    if (upgrade.get("actor_action") != "Demo_CallDemo"
            or upgrade["params"].get("DemoName") != "Demo032_0"):
        raise ValueError("Purah's upgrade cutscene changed")
    calls = [name for name, node in nodes.items() if node.get("actor_action") == "Demo_CallDemo"
             and node["params"].get("DemoName") == "Demo032_0"]
    if calls != [UPGRADE]:
        raise ValueError(f"Purah's flow calls Demo032_0 elsewhere: {calls}")
    wait_instead(flow, events[UPGRADE])

    after = graph_snapshot(flow)
    changed = {name for name in nodes if nodes[name] != after["events"][name]}
    expected = {call for *_rest, call in FLAGS.values()} | set(CHECKS) | {UPGRADE}
    if (changed != expected or set(after["events"]) != set(nodes)
            or after["entry_points"] != before["entry_points"]
            or after["events"][UPGRADE]["nxt"] != upgrade["nxt"]):
        raise ValueError(f"Purah's flow changed beyond her upgrades: {sorted(changed ^ expected)}")
    return write_flow(flow), [f"{FLOW}: Purah's upgrades are locations ({', '.join(LOCATION_FLAGS)})"]


def add_flags(raw: bytes) -> tuple[bytes, list[str]]:
    """The three location flags, saved bools."""
    from tools.build_game_data_mod import modify_gamedata_flags
    return (modify_gamedata_flags(raw, LOCATION_FLAGS, is_save=True, kind="bool"),
            [f"register saved bool {flag}" for flag in LOCATION_FLAGS])


def add_save_format(raw: bytes) -> tuple[bytes, list[str]]:
    from tools.build_game_data_mod import modify_saveformat
    return modify_saveformat(raw, LOCATION_FLAGS), ["save Purah's upgrade locations"]


def retarget_choice(msbt: bytes) -> bytes:
    """talk31's conditions on the Lv2 flags, on the location flags instead: each
    name, UTF-16 big-endian after its length in bytes, exactly once."""
    for lv2, flag, _choice, _call in FLAGS.values():
        if len(flag) != len(lv2):
            raise ValueError(f"{flag}: not the length of {lv2}")
        old, new = (len(name.encode("utf-16-be")).to_bytes(2, "big") + name.encode("utf-16-be")
                    for name in (lv2, flag))
        if msbt.count(old) != 1:
            raise ValueError(f"Purah's choice names {lv2} {msbt.count(old)} times")
        msbt = msbt.replace(old, new)
    return msbt


def generate_texts(files: dict[str, bytes], content) -> tuple[dict[str, bytes], list[dict]]:
    """Purah's choice, retargeted in every language of the overlay being built
    (after the stages that already changed the message archives). content: the
    update folder, or the game's files (botw_patch/game_files.py)."""
    from botw_patch.ap_quest import INPUT_HASHES
    from botw_patch.game_files import GameFiles
    game = GameFiles.of(content)
    table = "System/Resource/ResourceSizeTable.product.srsizetable"
    hashes, languages = regions.inputs(INPUT_HASHES, game.content), regions.of_content(game.content).languages
    inputs = {}
    for language in languages:
        name = f"Pack/Bootup_{language}.pack"
        inputs[name] = files[name] if name in files else game.checked(name, hashes[name])
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        stage = Path(temp)
        for name, raw in {**inputs, table: files[table]}.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        builder = ResourceBuilder(stage)
        for language in languages:
            def messages(raw, language=language):
                archive = oead.Sarc(unpack(raw))
                writer = oead.SarcWriter.from_sarc(archive)
                writer.files[MSBT] = retarget_choice(bytes(archive.get_file(MSBT).data))
                packed = bytes(writer.write()[1])
                return ((bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else packed),
                        [f"{language}: Purah's choice follows her upgrade locations"])

            builder.patch_archive(f"Pack/Bootup_{language}.pack",
                                  {f"Message/Msg_{language}.product.ssarc": messages})
        out = builder.finish()
        changes = builder.changes
    files = dict(files)
    files.update(out)
    return files, changes
