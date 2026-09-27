"""Remove three standalone diagnostic probes in a new, uninstalled candidate.

Never rewrites the source pack or the play profile. This is not the final
runtime reduction: the baseline injection still contains historical probes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_seed_bound_candidate import verified_files

REMOVED = {
    "patch_ui_close_trace.asm": "BOTW_AP_UICloseTrace_V208",
    "patch_ui_lifecycle.asm": "BOTW_AP_UILifecycle_V208",
    "patch_request_reject_trace.asm": "BOTW_AP_RequestReject_V208",
}


def strip_probes(files):
    """Fail closed on foreign groups, shared symbols or overlapping hooks."""
    texts = {name: raw.decode("utf-8") for name, raw in files.items()
             if name.endswith(".asm")}
    if not REMOVED.keys() <= texts.keys():
        raise ValueError("expected diagnostic files missing")
    retained = {n: s for n, s in texts.items() if n not in REMOVED}
    def sites(text):
        return {int(a, 16) for a in re.findall(r"^\s*(0x[0-9a-fA-F]+)\s*=", text, re.M)}
    removed_sites = set()
    for name, group in REMOVED.items():
        text = texts[name]
        if re.findall(r"^\[([^\]]+)\]", text, re.M) != [group]:
            raise ValueError(f"unexpected patch group: {name}")
        symbols = re.findall(r"^\s*([A-Za-z_]\w*)\s*(?::|=)", text, re.M)
        symbols = [s for s in symbols if s != "moduleMatches"]
        for other, source in retained.items():
            if sites(text) & sites(source):
                raise ValueError(f"overlapping hook: {name}/{other}")
            if any(re.search(r"\b" + re.escape(s) + r"\b", source) for s in symbols):
                raise ValueError(f"retained patch references diagnostic: {other}")
        removed_sites.update(sites(text))
    return {n: raw for n, raw in files.items() if n not in REMOVED}, sorted(removed_sites)


def build(source, output):
    source, output = source.resolve(), output.resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    original = verified_files(source, manifest)
    files, sites = strip_probes(original)
    hashes = {n: hashlib.sha256(raw).hexdigest() for n, raw in sorted(files.items())}
    identity = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:16]
    target = output / identity
    # Preserve historical feature metadata as provenance only.
    for key in ("close_call_trace", "lifecycle_trace", "lifecycle_sites",
                "lifecycle_version", "lifecycle_reserve", "request_reject_trace"):
        manifest.pop(key, None)
    manifest["native_files"] = {n: hashes[n] for n in manifest["native_files"] if n not in REMOVED}
    manifest["status"] = "requires_in_game_validation"
    manifest["runtime_cleanup"] = {
        "parent_path": str(source), "parent_build": source.name,
        "removed_files": list(REMOVED), "restored_vanilla_sites": [hex(a) for a in sites],
        "retained_files_byte_identical": True, "installed": False,
        "scope": "standalone probes only; injection still instrumented",
    }
    files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    for name, raw in files.items():
        path = (target / name).resolve()
        if not path.is_relative_to(target):
            raise ValueError("output path escapes candidate")
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"immutable candidate changed: {name}")
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".build/runtime-cleanup")
    args = parser.parse_args()
    print(build(args.source, args.output))
