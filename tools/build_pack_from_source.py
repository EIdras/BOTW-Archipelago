"""Build an isolated seed-bound Cemu pack from explicit dumps and project sources."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import platform
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path if Path(p).resolve() != ROOT / "tools"]

from botw_client.paths import DATA
from botw_client.session import session_token
from tools import build_native_from_source as native
from tools import build_resources_from_source as resources
from tools.build_resources_from_source import digest, encode

RULES = (
    '[Definition]\ntitleIds = 00050000101C9500\nname = Archipelago Native Integration\n'
    'path = "The Legend of Zelda: Breath of the Wild/Archipelago/Native Integration"\n'
    'description = The game pack of one Archipelago seed\n'
    'version = 7\nfsPriority = 2000\n'
).encode("utf-8")
# Packs built before the description changed stay valid.
EARLIER_RULES = RULES.replace(b"The game pack of one Archipelago seed",
                              b"Native delivery and source reward replacement validation")
RUNTIME = {"patch_apInject.asm", "patch_event_request.asm"}
DIAGNOSTICS = {"patch_ui_close_trace.asm", "patch_ui_lifecycle.asm", "patch_request_reject_trace.asm"}


SCOPES = {"generated_solo_ap_server", "generated_two_slot_ap_server", "generated_ap_seed"}


def seed_slot(report_path: Path) -> int:
    """The BOTW slot a prepared seed is played as (solo seeds: 1)."""
    return int(json.loads(report_path.read_bytes()).get("botw_slot", 1))


SLOT_FILE = ".apbotw"               # an Archipelago player container (botw_world/slot_file.py)
SLOT_MEMBER = "slot.json"
EARLIER_SLOT_FILE = ".apbotw.json"  # the plain manifest of seeds generated before it


def _contained(raw: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(raw)) as container:
        return json.loads(container.read(SLOT_MEMBER))


def slot_manifests(archive: Path) -> list[dict]:
    """The BOTW slot manifests of a seed: those of the slot files in its zip, or
    of the slot file itself."""
    name = archive.name.lower()
    if name.endswith(".json"):
        return [json.loads(archive.read_bytes())]
    if name.endswith(SLOT_FILE):
        return [_contained(archive.read_bytes())]
    with zipfile.ZipFile(archive) as zipped:
        return [json.loads(zipped.read(member)) if member.endswith(EARLIER_SLOT_FILE)
                else _contained(zipped.read(member))
                for member in zipped.namelist() if member.endswith((SLOT_FILE, EARLIER_SLOT_FILE))]


def slot_server(archive: Path) -> str | None:
    """The room a slot file was downloaded from: archipelago.gg writes its
    address into the container it serves."""
    if not archive.name.lower().endswith(SLOT_FILE):
        return None
    try:
        with zipfile.ZipFile(archive) as container:
            server = json.loads(container.read("archipelago.json")).get("server")
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None
    return server or None


def load_seed(report_path: Path, slot: int, archive: Path | None = None) -> dict:
    """Verify an audited AP identity against its archive and hashed slot manifest."""
    return _verified_seed(report_path, slot, archive)[0]


def slot_manifest(report_path: Path, slot: int, archive: Path | None = None) -> dict:
    """The verified slot manifest (placements, shops) of an audited AP identity."""
    return _verified_seed(report_path, slot, archive)[1]


def _verified_seed(report_path: Path, slot: int, archive: Path | None = None) -> tuple[dict, dict]:
    if type(slot) is not int or slot < 1:
        raise ValueError("invalid AP slot")
    report_raw = report_path.read_bytes()
    report = json.loads(report_raw)
    if report.get("status") != "passed" or report.get("scope") not in SCOPES:
        raise ValueError("AP identity report has not passed")
    identity = report["delivery"]["sessions"][str(slot)]
    values = tuple(identity[k] for k in ("seed", "team", "slot", "data_package_checksum"))
    if (type(identity["team"]) is not int or type(identity["slot"]) is not int
            or type(identity["token"]) is not int or identity["slot"] != slot
            or identity["seed"] != report["audit"]["seed"]
            or identity["token"] != session_token(values)):
        raise ValueError("AP session identity/token mismatch")
    archive = archive if archive is not None else Path(report["archive"])
    if digest(archive.read_bytes()) != report["archive_sha256"]:
        raise ValueError("AP archive checksum mismatch")
    matches = [m for m in slot_manifests(archive) if m.get("slot") == slot]
    if len(matches) != 1:
        raise ValueError("AP slot manifest absent or ambiguous")
    manifest = dict(matches[0])
    claimed = manifest.pop("content_sha256", None)
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    if digest(payload) != claimed:
        raise ValueError("AP slot manifest checksum mismatch")
    if (manifest.get("game") != "Breath of the Wild"
            or manifest.get("seed") != identity["seed"]
            or manifest.get("slot_name") != report["audit"]["slots"][str(slot)]
            or manifest.get("slot_data", {}).get("world_schema") not in (2, 3, 4)
            or manifest.get("slot_data", {}).get("client_schema") not in (3, 4, 5, 6, 7)
            or manifest.get("data_package_checksum", identity["data_package_checksum"])
            != identity["data_package_checksum"]):
        raise ValueError("AP slot manifest identity/schema mismatch")
    return ({**{key: identity[key] for key in
                ("seed", "team", "slot", "data_package_checksum", "token")},
             "archive_sha256": report["archive_sha256"],
             "slot_manifest_sha256": claimed, "slot_name": manifest["slot_name"],
             "report_sha256": digest(report_raw)}, manifest)


def verify_pack(pack: Path, binding: dict | None = None) -> dict:
    """Check a complete generated pack before installation or selection."""
    pack = pack.resolve()
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    identity = dict(manifest)
    build_id = identity.pop("build_id", None)
    if (manifest.get("component") != "seed_bound_play_pack"
            or build_id != digest(encode(identity))[:16]
            or pack.name not in {build_id, "AP_Ledger_" + str(build_id)}):
        raise ValueError("pack manifest identity mismatch")
    if binding is not None and manifest["seed_binding"] != binding:
        raise ValueError("pack does not match the selected AP seed identity")
    expected_native = RUNTIME | (DIAGNOSTICS if manifest["diagnostics_enabled"] else set())
    if set(manifest["native_files"]) != expected_native:
        raise ValueError("pack native file set mismatch")
    hashes = {resources.pack_path(n): sha for n, sha in manifest["files"].items()}
    hashes.update(manifest["native_files"])
    hashes.update({"rules.txt": manifest["rules_sha256"],
                   "delivery_catalog.json": manifest["native_delivery_catalog_sha256"]})
    existing = {p.relative_to(pack).as_posix() for p in pack.rglob("*") if p.is_file()}
    if existing != {*hashes, "manifest.json"}:
        raise ValueError("pack has missing or unexpected files")
    for name, sha in hashes.items():
        path = (pack / name).resolve()
        if not path.is_relative_to(pack) or digest(path.read_bytes()) != sha:
            raise ValueError(f"pack file changed: {name}")
    catalog = json.loads((pack / "delivery_catalog.json").read_text(encoding="utf-8"))
    if catalog["binding"]["seed_token"] != manifest["seed_binding"]["token"]:
        raise ValueError("pack catalog binding mismatch")
    if (pack / "rules.txt").read_bytes() not in (RULES, EARLIER_RULES):
        raise ValueError("pack rules mismatch")
    return manifest


def build(content: Path, rpx: Path, report: Path, slot: int, output: Path, *,
          archive: Path | None = None, diagnostics: bool = True,
          resource_gate: bool = False, event_gate: bool = False) -> Path:
    binding, slot_data = _verified_seed(report, slot, archive)
    from botw_patch.shops import plan_from_manifest
    shops = plan_from_manifest(slot_data)
    if digest(rpx.read_bytes()) != native.RPX_SHA256:
        raise ValueError("incompatible RPX: provide the verified Wii U EUR v208 dump")
    # A file the antivirus still holds may outlive the build here: the system's
    # temporary folder takes it, rather than failing the pack.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        work = Path(temp)
        native_dir = native.build(rpx, work / "native", resource_gate=resource_gate, event_gate=event_gate)
        resource_dir = resources.build(content, work / "resources", binding_token=binding["token"],
                                       shops=shops, status=slot_data)
        nm = json.loads((native_dir / "manifest.json").read_text(encoding="utf-8"))
        rm = json.loads((resource_dir / "manifest.json").read_text(encoding="utf-8"))
        files = {resources.pack_path(name): (resource_dir / resources.pack_path(name)).read_bytes()
                 for name in rm["files"]}
        for name in nm["files"]:
            if name.startswith("runtime/") or diagnostics:
                files[Path(name).name] = (native_dir / name).read_bytes()
        files["delivery_catalog.json"] = (resource_dir / "delivery_catalog.json").read_bytes()
    files["rules.txt"] = RULES
    sources = {**nm["source_hashes"], **rm["source_hashes"]}
    for name in ("tools/build_pack_from_source.py", "botw_client/session.py"):
        sources[name] = digest((ROOT / name).read_bytes())
    manifest = {
        "schema": 1, "component": "seed_bound_play_pack", "status": "requires_in_game_validation",
        "platform": "wiiu", "revision": "EUR v208", "installed": False,
        "production_native_enabled": False, "seed_binding": binding,
        "input_hashes": {**rm["input_hashes"], "U-King.rpx": nm["rpx_sha256"]},
        "source_hashes": sources,
        "dependencies": {**rm["dependencies"], "python": platform.python_version()},
        "files": rm["files"],
        "native_files": {name: digest(raw) for name, raw in sorted(files.items()) if name.endswith(".asm")},
        "runtime_files": sorted(RUNTIME),
        "diagnostics_enabled": diagnostics,
        "presentation_resource_gate_enabled": resource_gate,
        "presentation_event_gate_enabled": event_gate,
        "diagnostic_files": sorted(DIAGNOSTICS) if diagnostics else [],
        "gameplay_aids": False, "minimum_allocations": rm["minimum_allocations"],
        "rules_sha256": digest(RULES),
        "native_delivery_catalog_sha256": digest(files["delivery_catalog.json"]),
        "native_delivery_entries": True,
        "native_delivery_entry_count": sum(len(steps) for item in
            json.loads(files["delivery_catalog.json"])["items"].values()
            for steps in item["variants"].values()),
        "native_session_binding": True, "native_session_binding_token": binding["token"],
        "replaces_base_injection": True,
        # The AP journal in the game's tip frame, in every pack.
        "ap_journal": "tip_channel" if nm["options"].get("tip_channel") else None,
        "limits": ["embedded_legacy_instrumentation_retained"],
    }
    if shops:       # only then, so that seeds without shops keep their pack identity
        manifest["shops"] = rm["shops"]
    manifest["status_item"] = rm["status_item"]
    build_id = digest(encode(manifest))[:16]
    manifest["build_id"] = build_id
    files["manifest.json"] = encode(manifest)
    target = output.resolve() / build_id
    if target.exists():
        verify_pack(target, binding)
        if any((target / name).read_bytes() != raw for name, raw in files.items()):
            raise ValueError("immutable pack differs from reconstruction")
        return target
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    verify_pack(target, binding)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--rpx", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--slot", type=int, required=True)
    parser.add_argument("--archive", type=Path, help="explicit relocated copy of the audited AP archive")
    parser.add_argument("--without-diagnostics", action="store_true")
    parser.add_argument("--resource-gate", action="store_true",
                        help="experimental native preflight: defer before submission when resource is unavailable")
    parser.add_argument("--event-gate", action="store_true", help="defer before submission while native event admission is blocked (requires --resource-gate)")
    parser.add_argument("--output", type=Path, default=DATA / "packs-from-source")
    args = parser.parse_args()
    print(build(args.content, args.rpx, args.report, args.slot, args.output,
                archive=args.archive, diagnostics=not args.without_diagnostics,
                resource_gate=args.resource_gate, event_gate=args.event_gate))
