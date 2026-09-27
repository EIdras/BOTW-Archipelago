"""Prepare a runtime from unmodified official AP sources, only loading BOTW.

    python tools/prepare_ap_runtime.py --source <Archipelago 0.6.7 checkout>

This copies the actual AP core, the generic world and its tests, excluding
unrelated games and their optional dependencies, into .build/ap-runtime, with
this project's world as worlds/botw. No AP source is patched or replaced with
mocks. Generation, the local server and the world's tests run on it;
sync_world() refreshes its copy of the world before each of them.
"""
from pathlib import Path
import argparse
import shutil

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / ".build/ap-runtime"
WORLD = ROOT / "botw_world"


def sync_world(runtime: Path = RUNTIME) -> Path:
    """Replace the runtime's copy of the world by the current sources."""
    target = runtime / "worlds/botw"
    if not (runtime / "worlds/AutoWorld.py").is_file():
        raise FileNotFoundError(f"AP runtime absent: run tools/prepare_ap_runtime.py ({runtime})")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(WORLD, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


def prepare(source: Path, destination: Path) -> Path:
    if not (source / "worlds/AutoWorld.py").is_file():
        raise ValueError("not an Archipelago source checkout")
    destination.mkdir(parents=True, exist_ok=True)
    for path in source.glob("*.py"):
        shutil.copy2(path, destination / path.name)
    for name in ("worlds",):
        (destination / name).mkdir(exist_ok=True)
        for path in (source / name).glob("*.py"):
            shutil.copy2(path, destination / name / path.name)
    for name in ("worlds/generic", "rule_builder", "data", "test"):
        if (source / name).exists():
            shutil.copytree(source / name, destination / name, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__"))
    sync_world(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=ROOT / ".build/validation/Archipelago")
    parser.add_argument("--output", type=Path, default=RUNTIME)
    args = parser.parse_args()
    print(prepare(args.source, args.output))
