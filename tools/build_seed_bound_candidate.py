"""Derive an isolated native candidate bound to one generated AP seed/slot.

The source build is immutable. Only APBindSession's literal token, its catalog
metadata, and resource-size accounting may differ in the candidate. This tool
does not install the candidate or run Cemu.

The source must already carry the seed-independent chain stages:
- rune selection sync (tools/build_rune_selection_sync.py): without it the
  first rune a seed delivers is absent from the HUD, the wheel and L until a
  reload;
- tower Sheikah Sensor neutralisation (tools/build_plateau_sensor_candidate.py):
  without it any tower can grant the vanilla sensor;
- world heart withholding (tools/build_world_heart_withhold.py): without it
  the Divine Beast heart containers, which are AP checks, also give their
  vanilla heart;
- Master Sword pedestal (tools/build_master_sword_candidate.py): without it the
  pedestal, an AP check, also gives the vanilla sword;
- Ballad upgrade guard (tools/build_ballad_condition_candidate.py): without it
  the end of a Champions' Ballad upgrades a champion power the player has not
  received from AP yet;
- champion power restore (tools/build_hero_soul_restore_withhold.py): without
  it the engine puts the champion power back in the pouch at every load of a
  save where the Divine Beast is freed, which is the normal AP state, so the
  ClearRemains recipe only holds until the next load.
The default source is c6f33f2902bd3da5 + the five stages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path if Path(p).resolve() != ROOT / "tools"]

import oead  # noqa: E402

from botw_client.session import session_token  # noqa: E402
from botw_patch.delivery_flow import retarget_session_binding  # noqa: E402
from botw_patch.resources import ResourceBuilder, digest, unpack  # noqa: E402

SOURCE = ROOT / ".build" / "ballad-upgrade-delivery-candidates" / "a3e856f29c984bf9"
OUTPUT = ROOT / ".build" / "seed-bound-candidates"
FLOW_MEMBER = "EventFlow/Demo007_1.bfevfl"
TITLE = "Pack/TitleBG.pack"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"


def verified_files(source: Path, manifest: dict) -> dict[str, bytes]:
    files = {}
    for prefix, field in (("content/", "files"), ("", "native_files")):
        for name, sha in manifest[field].items():
            path = (source / prefix / name).resolve()
            if not path.is_relative_to(source.resolve()):
                raise ValueError("source path escaped the build")
            raw = path.read_bytes()
            if digest(raw) != sha:
                raise ValueError(f"source hash mismatch: {prefix}{name}")
            files[prefix + name] = raw
    for name, key in (("delivery_catalog.json", "native_delivery_catalog_sha256"),
                      ("rules.txt", "rules_sha256")):
        raw = (source / name).read_bytes()
        if digest(raw) != manifest[key]:
            raise ValueError(f"source hash mismatch: {name}")
        files[name] = raw
    return files


def read_identity(report_path: Path, slot: int) -> tuple[dict, dict]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    # Two-slot seeds, and solo play seeds (tools/play_seed.py).
    if report.get("status") != "passed" or report.get("scope") not in (
            "generated_two_slot_ap_server", "generated_solo_ap_server"):
        raise ValueError("generated AP server report has not passed")
    identity = report["delivery"]["sessions"][str(slot)]
    values = (identity["seed"], identity["team"], identity["slot"],
              identity["data_package_checksum"])
    if (identity["slot"] != slot or identity["seed"] != report["audit"]["seed"]
            or identity["token"] != session_token(values)):
        raise ValueError("session identity/token mismatch")
    archive = Path(report["archive"])
    if digest(archive.read_bytes()) != report["archive_sha256"]:
        raise ValueError("generated AP archive changed")
    with zipfile.ZipFile(archive) as zip_file:
        matches = [json.loads(zip_file.read(name)) for name in zip_file.namelist()
                   if name.endswith(".apbotw.json")]
    manifest = next((item for item in matches if item["slot"] == slot), None)
    if (manifest is None or manifest["seed"] != identity["seed"]
            or manifest["slot_name"] != report["audit"]["slots"][str(slot)]):
        raise ValueError("slot manifest is absent or inconsistent")
    return identity, {"archive_sha256": report["archive_sha256"],
                      "slot_manifest_sha256": manifest["content_sha256"],
                      "slot_name": manifest["slot_name"]}


def verify_member_scope(before: bytes, after: bytes) -> None:
    old = oead.Sarc(unpack(before))
    new = oead.Sarc(unpack(after))
    old_names = {file.name for file in old.get_files()}
    new_names = {file.name for file in new.get_files()}
    if old_names != new_names:
        raise ValueError("TitleBG member list changed")
    changed = {name for name in old_names if
               bytes(old.get_file(name).data) != bytes(new.get_file(name).data)}
    if changed != {FLOW_MEMBER}:
        raise ValueError(f"unexpected TitleBG members changed: {changed}")


def build(report_path: Path, slot: int, source: Path = SOURCE,
          output: Path = OUTPUT) -> Path:
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if (not manifest.get("native_session_binding")
            or not manifest.get("native_delivery_entries")
            or not manifest.get("replaces_base_injection")
            or not manifest.get("reward_replacements")):
        raise ValueError("source is not a complete verified native candidate")
    if not manifest.get("rune_selection_sync"):
        raise ValueError("source lacks the rune selection sync stage "
                         "(tools/build_rune_selection_sync.py --source ...)")
    if not manifest.get("plateau_sensor_source"):
        raise ValueError("source lacks the tower sensor stage "
                         "(tools/build_plateau_sensor_candidate.py --source ...)")
    if not manifest.get("world_heart_withhold"):
        raise ValueError("source lacks the world heart withholding stage "
                         "(tools/build_world_heart_withhold.py --source ...)")
    if not manifest.get("master_sword_source"):
        raise ValueError("source lacks the Master Sword stage "
                         "(tools/build_master_sword_candidate.py --source ...)")
    if not manifest.get("ballad_condition_source"):
        raise ValueError("source lacks the Ballad upgrade guard stage "
                         "(tools/build_ballad_condition_candidate.py --source ...)")
    if not manifest.get("hero_soul_restore_withhold"):
        raise ValueError("source lacks the champion power restore stage "
                         "(tools/build_hero_soul_restore_withhold.py --source ...)")
    if not manifest.get("ballad_upgrade_delivery"):
        raise ValueError("source lacks the Ballad upgrade delivery stage "
                         "(tools/build_ballad_upgrade_delivery.py --source ...)")
    files = verified_files(source, manifest)
    catalog = json.loads(files["delivery_catalog.json"])
    old_token = manifest["native_session_binding_token"]
    if catalog["binding"]["seed_token"] != old_token:
        raise ValueError("source flow/catalog binding mismatch")
    identity, world = read_identity(report_path, slot)
    token = identity["token"]
    if token == old_token:
        raise ValueError("generated token equals the placeholder token; no retarget needed")

    builder = ResourceBuilder(source / "content")
    builder.patch_archive(TITLE, {FLOW_MEMBER: lambda raw:
                          retarget_session_binding(raw, old_token, token)})
    changed_content = builder.finish()
    if set(changed_content) != {TITLE, TABLE}:
        raise ValueError("resource builder changed unexpected files")
    verify_member_scope(files["content/" + TITLE], changed_content[TITLE])
    files.update({"content/" + name: raw for name, raw in changed_content.items()})
    catalog["binding"]["seed_token"] = token
    files["delivery_catalog.json"] = (
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    hashes = {name: digest(raw) for name, raw in sorted(files.items())}
    build_id = hashlib.sha256(json.dumps(hashes, sort_keys=True,
                                        separators=(",", ":")).encode()).hexdigest()[:16]
    target = (output / build_id).resolve()
    if not target.is_relative_to(output.resolve()):
        raise ValueError("candidate path escaped output root")
    for name, raw in files.items():
        path = (target / name).resolve()
        if not path.is_relative_to(target):
            raise ValueError("candidate file path escaped output root")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"immutable candidate changed: {name}")
        path.write_bytes(raw)

    output_manifest = dict(manifest)
    output_manifest.update({
        "status": "requires_in_game_validation",
        "source_build": source.name,
        "native_session_binding_token": token,
        "native_delivery_catalog_sha256": hashes["delivery_catalog.json"],
        "files": {name[8:]: sha for name, sha in hashes.items()
                  if name.startswith("content/")},
        "native_files": {name: hashes[name] for name in manifest["native_files"]},
        "seed_binding": {**identity, **world,
                         "source_report": str(report_path.resolve()),
                         "source_token": old_token},
        "changes": [*manifest.get("changes", []), *builder.changes],
        "production_native_enabled": False,
    })
    manifest_path = target / "manifest.json"
    encoded = (json.dumps(output_manifest, ensure_ascii=False, indent=2) + "\n").encode()
    if manifest_path.exists() and manifest_path.read_bytes() != encoded:
        raise ValueError("immutable candidate manifest changed")
    manifest_path.write_bytes(encoded)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--slot", type=int, required=True)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(build(args.report, args.slot, args.source, args.output))


if __name__ == "__main__":
    main()
