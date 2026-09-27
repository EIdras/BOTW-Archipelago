"""Generate an AP seed with the official runtime (.build/ap-runtime).

    python tools/generate_native.py [Archipelago Generate.py options]

The runtime's copy of the world is refreshed first (tools/prepare_ap_runtime.py),
the player files are those of players/ and the archive goes to
.build/native-seeds/, unless the options say otherwise.
"""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.prepare_ap_runtime import RUNTIME, sync_world  # noqa: E402

if __name__ == "__main__":
    if not (RUNTIME / "Generate.py").is_file():
        raise SystemExit("Run tools/prepare_ap_runtime.py first")
    sync_world()
    os.environ["SKIP_REQUIREMENTS_UPDATE"] = "1"
    sys.path.insert(0, str(RUNTIME))
    if "--player_files_path" not in sys.argv:
        sys.argv.extend(["--player_files_path", str(ROOT / "players")])
    if "--outputpath" not in sys.argv:
        sys.argv.extend(["--outputpath", str(ROOT / ".build/native-seeds")])
    from Generate import main
    from Main import main as generate
    args, seed = main()
    generate(args, seed)
