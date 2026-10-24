"""Breath of the Wild Archipelago: the one command a player runs.

    "BOTW Archipelago.cmd" [<slot file .apbotw | seed zip>]

1. The first time, asks where Cemu.exe is, finds the game in that installation
   and makes the isolated Cemu profile (tools/cemu_install.py,
   tools/cemu_profile.py).
2. Picks the seed: the file given (or dropped on the launcher), else one
   already prepared, or a new file chosen in a window. A new seed's game pack
   is built (tools/play_seed.py), and a prepared seed's again when another
   version of the project built it.
3. Asks the address of the room (the one written in a slot file downloaded
   from the room's page, then the one remembered for the seed) and its password; a
   seed prepared from its zip can also be hosted on this computer, where the
   Archipelago runtime is (tools/prepare_ap_runtime.py).
4. Plays (tools/play_session.py) until Cemu closes.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path if Path(p).resolve() != ROOT / "tools"]

from tools import cemu_install, cemu_profile, play_seed  # noqa: E402

ROOM_FILE = "launcher.json"
LOCAL = "local"
SEED_FILES = [("Breath of the Wild slot file or seed", "*.apbotw *.apbotw.json *.zip")]


class Cancelled(Exception):
    pass


class Console:
    """The launcher's questions, in the console; files in a window when there is one."""

    def say(self, text: str = "") -> None:
        print(text, flush=True)

    def ask(self, prompt: str, default: str = "") -> str:
        try:
            answer = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
        except EOFError:
            raise Cancelled from None
        return answer or default

    def secret(self, prompt: str) -> str:
        import getpass
        try:
            return getpass.getpass(f"{prompt}: ").strip()
        except EOFError:
            raise Cancelled from None

    def choose_file(self, title: str, kinds: list[tuple[str, str]]) -> Path | None:
        try:
            import tkinter
            from tkinter import filedialog
            window = tkinter.Tk()
            window.withdraw()
            window.attributes("-topmost", True)
            try:
                chosen = filedialog.askopenfilename(title=title, filetypes=kinds + [("All files", "*.*")])
            finally:
                window.destroy()
        except Exception:       # noqa: BLE001 - no window here: the path is typed
            chosen = self.ask(f"{title} (path)").strip('"')
        return Path(chosen) if chosen else None


def yes(ui, prompt: str, default: bool = True) -> bool:
    answer = ui.ask(f"{prompt} ({'Y/n' if default else 'y/N'})").lower()
    return default if not answer else answer.startswith("y")


def ensure_profile(ui) -> None:
    """The isolated Cemu profile, made from the player's Cemu the first time."""
    if (cemu_profile.PROFILE / "isolation.json").is_file():
        return
    ui.say("First launch: the game runs in a Cemu profile of its own, copied once from your Cemu.")
    while True:
        executable = ui.choose_file("Where is Cemu.exe?", [("Cemu", "Cemu.exe")])
        if executable is None:
            raise Cancelled
        try:
            install = cemu_install.detect(executable)
            break
        except cemu_install.CemuInstallError as exc:
            ui.say(str(exc))
            if not yes(ui, "Choose Cemu.exe again?", default=False):
                raise Cancelled from None
    ui.say(f"Breath of the Wild: {install.game}\nUpdate v{cemu_install.UPDATE_VERSION}: {install.update}\n"
           f"DLC: {install.dlc}")
    ui.say(f"The profile copies Cemu, the update, the DLC and your saves (about 5 GB) into "
           f"{cemu_profile.PROFILE}. Your Cemu is never modified.")
    if not yes(ui, "Make the profile?"):
        raise Cancelled
    cemu_profile.create(executable, install)


@dataclass
class Prepared:
    seed: str
    slot: str
    last_played: str        # the last session's folder name, "" if never played


def prepared_seeds() -> list[Prepared]:
    """The prepared seeds, the last played first."""
    seeds = []
    folders = sorted(play_seed.PLAY_SEEDS.iterdir()) if play_seed.PLAY_SEEDS.is_dir() else []
    for folder in folders:
        try:
            report = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
            slot = report["audit"]["slots"][str(report.get("botw_slot", 1))]
        except (OSError, ValueError, KeyError):
            continue
        sessions = sorted(path.name for path in (folder / "sessions").glob("*")) \
            if (folder / "sessions").is_dir() else []
        seeds.append(Prepared(folder.name, slot, sessions[-1] if sessions else ""))
    return sorted(seeds, key=lambda seed: seed.last_played, reverse=True)


def fresh(ui, seed: str) -> str:
    """The prepared seed, its pack built again when it is missing, was built
    by another version of the project, or over other mods than the player's
    (tools/play_mods.py)."""
    from tools import play_mods
    play_mods.fresh_pack(play_seed.PLAY_SEEDS / seed, play_mods.prepare(ui.say), ui.say)
    warn_newer(ui, seed)
    return seed


def warn_newer(ui, seed: str) -> None:
    from botw_client.version import VERSION
    try:
        report = json.loads((play_seed.PLAY_SEEDS / seed / "analysis.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    made = play_seed.newer_world(report.get("audit", {}))
    if made:
        ui.say(f"This seed was generated with the Breath of the Wild world {made}, newer than this version "
               f"({VERSION}): if something is missing, update BOTW Archipelago.")


def prepare_file(ui, path: Path) -> str:
    """Prepare the seed of a slot file or zip, unless it already is; its name."""
    from tools.build_pack_from_source import slot_manifests
    path = path.resolve()
    try:
        names = [manifest["slot_name"] for manifest in slot_manifests(path)
                 if manifest.get("game") == play_seed.GAME]
        seed = slot_manifests(path)[0]["seed"]
    except (OSError, ValueError, KeyError, IndexError) as exc:
        raise ValueError(f"not a Breath of the Wild slot file or seed: {path}") from exc
    if not names:
        raise ValueError(f"no Breath of the Wild player in this seed: {path}")
    slot = names[0]
    if len(names) > 1:
        for number, name in enumerate(names, 1):
            ui.say(f"  {number}. {name}")
        slot = names[pick(ui, "Which player are you?", len(names)) - 1]
    folder = play_seed.PLAY_SEEDS / seed
    if (folder / "analysis.json").is_file() and (folder / path.name).is_file()             and play_seed.sha(folder / path.name) == play_seed.sha(path):
        return fresh(ui, seed)
    # Built over the player's own mods (tools/play_mods.py).
    from botw_patch.game_files import ModConflict
    from tools import play_mods
    mods = play_mods.prepare(ui.say)
    ui.say(f"Building the game pack of seed {seed} for {slot} (about a minute)...")
    try:
        play_seed.prepare(path, slot_name=slot if len(names) > 1 else None, layers=mods.layers,
                          mem2_end=mods.mem2_end)
    except ModConflict as conflict:
        play_mods.leave_out(mods, conflict, ui.say)
        play_mods.fresh_pack(folder, mods, ui.say)
    warn_newer(ui, seed)
    return seed


def pick(ui, prompt: str, count: int, default: int = 1) -> int:
    while True:
        answer = ui.ask(prompt, str(default))
        if answer.isdigit() and 1 <= int(answer) <= count:
            return int(answer)
        ui.say(f"Type a number from 1 to {count}.")


def choose_seed(ui, argument: str | None) -> str:
    if argument:
        return prepare_file(ui, Path(argument.strip('"')))
    seeds = prepared_seeds()
    if seeds:
        ui.say("Seeds:")
        for number, seed in enumerate(seeds, 1):
            day = seed.last_played[:8]
            played = f", last played {day[:4]}-{day[4:6]}-{day[6:]}" if day else ""
            ui.say(f"  {number}. {seed.seed} ({seed.slot}{played})")
        ui.say(f"  {len(seeds) + 1}. another seed: your slot file (.apbotw) or the seed's zip")
        choice = pick(ui, "Seed", len(seeds) + 1)
        if choice <= len(seeds):
            return fresh(ui, seeds[choice - 1].seed)
    path = ui.choose_file("Your slot file (.apbotw) or the seed's zip", SEED_FILES)
    if path is None:
        raise Cancelled
    return prepare_file(ui, path)


def choose_room(ui, seed: str) -> tuple[str | None, str | None]:
    """The room's address and password, or (None, None) to host the seed here."""
    from botw_client.protocol import server_url
    folder = play_seed.PLAY_SEEDS / seed
    report = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    hostable = play_seed.hostable(report) and play_seed.archipelago_here()
    try:
        remembered = json.loads((folder / ROOM_FILE).read_text(encoding="utf-8")).get("room", "")
    except (OSError, ValueError):
        from tools.build_pack_from_source import slot_server
        remembered = slot_server(Path(report["archive"])) or ""
    prompt = "Room address (archipelago.gg:<port>)"
    if hostable:
        prompt += f", or {LOCAL!r} to host the seed on this computer"
    while True:
        room = ui.ask(prompt, remembered)
        if hostable and room.lower() == LOCAL:
            address = None
            break
        try:
            if room:
                server_url(room)
                address = room
                break
        except ValueError:
            pass
        ui.say("Type the room's address, as its page shows it: archipelago.gg:12345")
    (folder / ROOM_FILE).write_text(json.dumps({"room": room}) + "\n", encoding="utf-8")
    if address is None:
        return None, None
    return address, ui.secret("Room password (Enter if none)") or None


def test_aids(argv: list[str]) -> tuple[list[str], dict]:
    """The test aids of a source checkout, as Play.cmd takes them (--speed, --cheats,
    --invincible, --stamina, --unbreakable, --damage); the other arguments. A release
    ships none of their modules (tools/build_release.py): there, they are refused."""
    names = ("--speed", "--damage", "--cheats", "--invincible", "--stamina", "--unbreakable")
    if not any(arg.split("=")[0] in names for arg in argv):
        return argv, {}
    try:
        from tools.play_aids import damage_argument
        from tools.play_speed import speed_argument
    except ImportError:
        raise ValueError("test aids are not part of a release: play from a source checkout") from None
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--speed", type=speed_argument, default=1.0)
    parser.add_argument("--damage", type=damage_argument, default=1)
    for flag in ("--cheats", "--invincible", "--stamina", "--unbreakable"):
        parser.add_argument(flag, action="store_true")
    known, rest = parser.parse_known_args(argv)
    aids = [key for key, chosen in (("Invincible", known.invincible), ("Stamina", known.stamina),
                                    ("Unbreakable", known.unbreakable)) if chosen or known.cheats]
    damage = known.damage if known.damage > 1 or not known.cheats else 10
    return rest, {"speed": known.speed, "aids": aids, "damage": damage}


def main(argv: list[str], ui=None) -> int:
    ui = ui or Console()
    ui.say("Breath of the Wild Archipelago")
    try:
        argv, aids = test_aids(argv)
        ensure_profile(ui)
        seed = choose_seed(ui, argv[0] if argv else None)
        address, password = choose_room(ui, seed)
    except Cancelled:
        ui.say("Cancelled.")
        return 1
    except (cemu_install.CemuInstallError, ValueError, OSError, RuntimeError) as exc:
        ui.say(f"Error: {exc}")
        return 1
    from tools import build_poptracker, play_session
    build_poptracker.ensure_installed(ui.say)
    play_session.run(seed, connect=address, password=password, **aids)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
