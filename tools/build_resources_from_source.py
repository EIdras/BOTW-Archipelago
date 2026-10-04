"""Rebuild all play resources from the verified Wii U update and project sources.

The result is a resource component, not an installable pack: it still needs
the matching native component and seed identity. Historical candidates are
comparison oracles only, never build inputs.
"""
from __future__ import annotations

import argparse
from importlib.metadata import version
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path if Path(p).resolve() != ROOT / "tools"]

import oead
import rstb

from botw_patch.build import RECIPES, SOURCE_HASHES
from botw_patch.delivery_flow import (
    BIND_ENTRY, QUIET_FLOW, compile_native_entries, delivery_catalog, patch_delivery_event_info,
    patch_delivery_flow, patch_session_binding)
from botw_patch.resources import digest, unpack
from tools.build_resource_base_from_source import INPUT_HASHES, generate_presentation, patch_stage
from tools.build_game_data_mod import modify_gamedata_flags
from tools import build_plateau_sensor_candidate as sensor
from tools import build_master_sword_candidate as sword
from tools import build_ballad_condition_candidate as ballad
from tools.build_ballad_upgrade_delivery import champion_entries, transform_for as upgrade_delivery
from botw_patch import death_link, ganon_gate, gerudo_outfit, hud_layout, loading_icon, traps
from botw_patch.status_item import INPUT_HASHES as STATUS_INPUTS

TITLE = "Pack/TitleBG.pack"
BOOTUP = "Pack/Bootup.pack"
MEMBER_FLOW = "Demo007_1"
MEMBER = f"EventFlow/{MEMBER_FLOW}.bfevfl"
QUIET_MEMBER = f"EventFlow/{QUIET_FLOW}.bfevfl"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
# Keep the allocation used by the played pack, including the margin retained
# when its locomotion aid was removed. This is an explicit tested floor, not
# a claim that serialized size predicts all runtime parser allocations.
MINIMUM_ALLOCATIONS = {"Pack/TitleBG.pack": 86590304}
REWARD_PACKS = {
    "Event/ClearRemains.sbeventpack": "875b181bf68954442bf82f9087aeb6c23adcb59fd2dec4cff9a7853fa255f43c",
    "Event/Demo003_0.sbeventpack": "16ecca5f88d21a120a87dad5fc8ee9c0ddc7fe58ef66b82027f44144054746bd",
    "Event/Demo033_0.sbeventpack": "a7812b878782907322e9860f5d2f5a01af49e44957b236070492e1cdc8927c7e",
    "Event/FindDungeon.sbeventpack": "7a29348697eb73e8c17c2e2b9152afd9f271d608655658371cc79c2938ef06ab",
    "Event/Npc_DungeonPriest001.sbeventpack": "0d3015c2a8b23b2a1c6668cf4c534632d32bc20eb1af5f0dd15006594553bf75",
}
# The English texts, for the names of what can kill Link (DeathLink); the
# same version as the Archipelago key item's.
DEATH_LINK_MESSAGES = {death_link.MESSAGES: STATUS_INPUTS[death_link.MESSAGES]}
UPDATE_HASHES = {
    **INPUT_HASHES, **REWARD_PACKS, sensor.PACK: sensor.EXPECTED_SOURCE_SHA,
    **DEATH_LINK_MESSAGES,
    **sword.PACKS,
    **gerudo_outfit.PACKS, **gerudo_outfit.text_inputs(),
    **ganon_gate.PACKS,
    **{ballad.pack(name): spec[1] for name, spec in ballad.FLOWS.items()},
}
SOURCE_FILES = (
    "tools/build_resources_from_source.py", "tools/build_resource_base_from_source.py",
    "tools/build_game_data_mod.py", "tools/build_delivery_control.py",
    "tools/build_ui_close_trace.py", "tools/build_ui_lifecycle.py",
    "tools/build_eventflow_alias.py", "tools/build_autonomous_eventflow.py",
    "tools/build_owned_presentation.py", "tools/build_plateau_sensor_candidate.py",
    "tools/build_master_sword_candidate.py", "tools/build_ballad_condition_candidate.py",
    "tools/build_ballad_upgrade_delivery.py", "botw_patch/build.py",
    "botw_patch/resources.py", "botw_patch/events.py", "botw_patch/delivery_flow.py",
    "botw_patch/ledger_experiment.py", "botw_client/delivery_plan.py",
    "botw_client/items.py", "data/item_map.json", "assets/wiiu/Item_AP.sbitemico",
    "botw_patch/hud_layout.py", "tools/bitemico.py", "botw_patch/death_link.py",
    "botw_patch/loading_icon.py", "botw_patch/traps.py", "botw_patch/melee_weapons.py",
    *gerudo_outfit.SOURCE_FILES, *ganon_gate.SOURCE_FILES,
)


def pack_path(name: str) -> str:
    """Where a built resource goes in a pack: DLC files (aoc/0010/...) at the
    root, as Cemu reads a graphic pack's aoc folder; the rest in content/."""
    return name if name.startswith("aoc/") else "content/" + name


def default_aoc(content: Path) -> Path | None:
    """The DLC content next to the update's (title/0005000c/<id>/content/0010)."""
    aoc = content.parents[2] / "0005000c" / content.parents[0].name / "content" / "0010"
    return aoc if aoc.is_dir() else None


def encode(data) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def generate(content: Path, binding_token: int, shops: list | None = None,
             status: dict | None = None, aoc: Path | None = None
             ) -> tuple[dict[str, bytes], dict, list[dict]]:
    """shops: botw_patch.shops.ShopPlacement list of the seed (none: no shop stage).
    status: the slot manifest, for the Archipelago key item (none: no item)."""
    if type(binding_token) is not int or not 0 < binding_token <= 0x7FFFFFFF:
        raise ValueError("binding token must be a positive signed s32")
    # Verify every consumed update archive before constructing any output.
    inputs = {}
    for name, expected in UPDATE_HASHES.items():
        raw = (content / name).read_bytes()
        if digest(raw) != expected:
            raise ValueError(f"unexpected Wii U update resource: {name}")
        inputs[name] = raw
    files, changes = generate_presentation(content, "owned_marker")
    title = oead.Sarc(unpack(inputs[TITLE]))
    def donor(name):
        return bytes(title.get_file(f"EventFlow/{name}.bfevfl").data)
    specs, _unsupported = compile_native_entries()
    catalog = delivery_catalog(binding_token=binding_token)

    donors = (donor("OperationGuide"), donor("Demo002_0"), donor("GetDemo"),
              donor("GetDemo"), donor("Demo017_0"))

    def delivery(raw):
        raw, trap_edits = traps.add_entries(raw, MEMBER_FLOW)
        result, edits = patch_delivery_flow(raw, *donors)
        result, binding_edits = patch_session_binding(result, binding_token)
        return result, trap_edits + edits + binding_edits

    def quiet_delivery(raw):
        # The silent twins, in their own flowchart (see QUIET_FLOW), and the
        # traps: their entries first, which their delivery entries call.
        raw, trap_edits = traps.add_entries(raw)
        result, edits = patch_delivery_flow(raw, *donors, quiet=True)
        return result, trap_edits + edits

    def event_info(raw):
        result, edits = patch_delivery_event_info(raw, specs, extra_entries=(BIND_ENTRY,))
        result, trap_edits = traps.add_event_info(result)
        return result, edits + trap_edits

    files, edits = patch_stage(files, TITLE, {MEMBER: delivery, QUIET_MEMBER: quiet_delivery},
                               extra_archive=(BOOTUP, {
        "Event/EventInfo.product.sbyml": event_info,
        "GameData/gamedata.ssarc": lambda raw: (
            modify_gamedata_flags(raw, ("APDeliveryRejectCounter",), is_save=False),
            ["register volatile APDeliveryRejectCounter"]),
    }))
    changes.extend(edits)

    # Search by member identity, as in the original resource compiler. Reject
    # unexpected copies instead of silently leaving a source reward active.
    found, packs = set(), set()
    for path in sorted((content / "Event").glob("*.sbeventpack")):
        name = path.relative_to(content).as_posix()
        raw = inputs.get(name)
        if raw is None:
            raw = path.read_bytes()
        archive = oead.Sarc(unpack(raw))
        transforms = {}
        for member in archive.get_files():
            flow = Path(member.name).stem
            if flow not in RECIPES or member.name != f"EventFlow/{flow}.bfevfl":
                continue
            if name not in REWARD_PACKS or digest(bytes(member.data)) != SOURCE_HASHES[flow]:
                raise ValueError(f"unexpected source reward copy: {name}/{member.name}")
            transforms[member.name] = RECIPES[flow]
            found.add(flow)
        if transforms:
            files[name] = raw
            files, edits = patch_stage(files, name, transforms)
            changes.extend(edits)
            packs.add(name)
    if found != set(RECIPES) or packs != set(REWARD_PACKS):
        raise ValueError("incomplete source reward coverage")

    stages = [(sensor.PACK, {sensor.FLOW: sensor.transform})]
    stages += [(name, {sword.FLOW: sword.transform}) for name in sword.PACKS]
    # The Gerudo outfit is an item (botw_patch/gerudo_outfit.py): Vilia no longer sells it.
    stages += [(name, {member: gerudo_outfit.transform_for(member) for member in members})
               for name, members in gerudo_outfit.STAGES.items()]
    stages += [(ballad.pack(name), {ballad.member(name): ballad.transform_for(name)})
               for name in ballad.FLOWS]
    # The sanctum stays sealed until the seed's requirements are met (botw_patch/ganon_gate.py).
    stages += [(ganon_gate.PACK, {ganon_gate.FLOW: ganon_gate.transform})]
    for name, transforms in stages:
        files[name] = inputs[name]
        files, edits = patch_stage(files, name, transforms)
        changes.extend(edits)
    champions = champion_entries(catalog)
    files, edits = patch_stage(files, TITLE, {
        MEMBER: upgrade_delivery({item: entry for item, entry in champions.items()
                                  if not item.endswith(" (quiet)")}),
        QUIET_MEMBER: upgrade_delivery({item: entry for item, entry in champions.items()
                                        if item.endswith(" (quiet)")}, host=QUIET_FLOW),
    })
    changes.extend(edits)
    # DeathLink (botw_patch/death_link.py): in every pack, requested only when
    # the seed has DeathLink on.
    files, edits = patch_stage(files, TITLE, {QUIET_MEMBER: death_link.add_entry},
                               extra_archive=(BOOTUP, {death_link.EVENT_INFO: death_link.add_event_info,
                                                       death_link.GAMEDATA: death_link.add_flag}))
    changes.extend(edits)
    files, edits = patch_stage(files, BOOTUP, {ganon_gate.GAMEDATA: ganon_gate.add_flags})
    changes.extend(edits)
    catalog["ganon_gate"] = {"open": ganon_gate.OPEN, "refused": ganon_gate.REFUSED}
    catalog["death_link"] = {"entry": death_link.ENTRY, "flow": death_link.FLOW_NAME,
                             "flag": death_link.FLAG,
                             "attackers": death_link.attacker_names(inputs[death_link.MESSAGES])}
    # The AP connection indicator of the HUD (botw_patch/hud_layout.py) and
    # the AP icon of the loading screen (botw_patch/loading_icon.py).
    icon = (ROOT / "assets/wiiu/Item_AP.sbitemico").read_bytes()

    def indicator(raw):
        out, detail = hud_layout.patch_archive(unpack(raw), icon)
        out, loading = loading_icon.patch_archive(out, icon)
        return (bytes(oead.yaz0.compress(out)) if raw[:4] == b"Yaz0" else out), [detail, loading]

    files, edits = patch_stage(files, BOOTUP, {hud_layout.ARCHIVE: indicator})
    changes.extend(edits)
    if shops:
        from botw_patch import shops as shop_stage
        files, edits = shop_stage.generate(files, content, shops,
                                           aoc=aoc if aoc is not None else default_aoc(content))
        changes.extend(edits)
    if status:
        from botw_patch import status_item
        files, edits = status_item.generate(files, content, status)
        changes.extend(edits)
        catalog["status_item"] = {"entry": status_item.ENTRY, "actor": status_item.ACTOR}
    # Vilia's lines at the price she now asks (botw_patch/gerudo_outfit.py).
    files, edits = gerudo_outfit.generate_texts(files, content)
    changes.extend(edits)
    # The sealed sanctum's line (botw_patch/ganon_gate.py).
    files, edits = ganon_gate.generate_texts(files, content)
    changes.extend(edits)
    table = rstb.ResourceSizeTable(unpack(files[TABLE]), True)
    for name, minimum in MINIMUM_ALLOCATIONS.items():
        table.set_size(name, max(table.get_size(name), minimum))
    stream = io.BytesIO()
    table.write(stream, True)
    files[TABLE] = bytes(oead.yaz0.compress(stream.getvalue()))
    return files, catalog, changes


def build(content: Path, output: Path, *, binding_token: int, shops: list | None = None,
          status: dict | None = None, aoc: Path | None = None) -> Path:
    files, catalog, changes = generate(content.resolve(), binding_token, shops, status, aoc)
    manifest = {
        "schema": 1, "component": "complete_play_resources", "status": "not_installable",
        "platform": "wiiu", "revision": "EUR v208", "installed": False,
        "binding_token": binding_token, "gameplay_aids": False,
        "minimum_allocations": MINIMUM_ALLOCATIONS,
        "input_hashes": UPDATE_HASHES,
        "source_hashes": {name: digest((ROOT / name).read_bytes()) for name in SOURCE_FILES},
        "dependencies": {name: version(name) for name in ("oead", "evfl", "rstb")},
        "files": {name: digest(raw) for name, raw in sorted(files.items())},
        "catalog_sha256": digest(encode(catalog)), "changes": changes,
        "limits": ["matching_native_component_required", "seed_identity_not_verified",
                   "not_validated_in_game"],
    }
    if shops:
        # Only for seeds with shops, so that the others keep their identity.
        from botw_patch import shops as shop_stage
        manifest["shops"] = [{"location_id": p.location.id, "price": p.price} for p in shops]
        manifest["input_hashes"] = {**UPDATE_HASHES, **shop_stage.INPUT_HASHES}
        manifest["source_hashes"].update({name: digest((ROOT / name).read_bytes())
                                          for name in shop_stage.SOURCE_FILES})
        from botw_client.stall_catalog import StallLocation
        if any(isinstance(p.location, StallLocation) for p in shops):
            from botw_patch import stalls
            manifest["input_hashes"].update({**stalls.INPUT_HASHES, **{
                stalls.AOC_PREFIX + name: sha for name, sha in stalls.MAP_HASHES.items()}})
            manifest["source_hashes"].update({name: digest((ROOT / name).read_bytes())
                                              for name in stalls.SOURCE_FILES})
    if status:
        from botw_patch import status_item
        manifest["status_item"] = {"seed": status["seed"], "slot": status["slot"]}
        manifest["input_hashes"] = {**manifest["input_hashes"], **status_item.INPUT_HASHES}
        manifest["source_hashes"].update({name: digest((ROOT / name).read_bytes())
                                          for name in status_item.SOURCE_FILES})
    build_id = digest(encode(manifest))[:16]
    manifest["build_id"] = build_id
    outputs = {pack_path(name): raw for name, raw in files.items()}
    outputs.update({"delivery_catalog.json": encode(catalog), "manifest.json": encode(manifest)})
    target = output.resolve() / build_id
    if target.exists():
        existing = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
        if existing != set(outputs):
            raise ValueError("resource component is incomplete or contains unexpected files")
        for name, raw in outputs.items():
            if (target / name).read_bytes() != raw:
                raise ValueError(f"immutable resource component modified: {name}")
        return target
    for name, raw in outputs.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--binding-token", type=int, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / ".build/resources-from-source")
    args = parser.parse_args()
    print(build(args.content, args.output, binding_token=args.binding_token))
