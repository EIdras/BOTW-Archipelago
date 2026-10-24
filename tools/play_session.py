"""A play session: Cemu, the client and an AP server, together.

    python tools/play_session.py [--seed <seed folder name>] [--connect <address> [--password <p>] | --host]
                                 [test aids of source checkouts: --speed <x> --invincible --stamina
                                  --unbreakable --damage <x> --cheats]

  * the pack bound to the seed's BOTW slot (tools/play_seed.py), enabled in
    the isolated Cemu profile (tools/cemu_profile.py) with copies of the
    graphic packs the player's own Cemu runs, but those it cannot run with
    (tools/player_packs.py);
  * a Cemu account of its own, so that a new game never overwrites the saves
    copied from the Cemu installation, which are checked unchanged at the end;
  * the AP server:
      - with --connect, the room the seed is hosted in, archipelago.gg for
        instance (--connect archipelago.gg:38281);
      - otherwise the official AP server, in process, on port 38281, saving
        its state next to the seed's zip (.apsave): progress carries over
        between sessions. It listens on this computer only, or with --host on
        every network interface, for the other players of a multiworld;
  * the client runtime (native deliveries, presentations, AP journal), whose
    state also lives in the seed folder, until Cemu closes.
Lines typed in the console go to the AP server as chat or commands (/hint,
/status...; sent as !hint, !status... to a remote room), or to the client
(/ap-... commands).

Each launch writes play-seeds/<seed>/sessions/<stamp>/ in the data folder
(botw_client/paths.py): the client
log, Cemu's log, and session.json (checks sent, items received, cursor, save
hashes).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import faulthandler
import functools
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
os.environ["SKIP_REQUIREMENTS_UPDATE"] = "1"
sys.path[:] = [str(ROOT)] + [p for p in sys.path
                            if Path(p).resolve() != ROOT / 'tools']

from botw_client.paths import BUILD, DATA  # noqa: E402

# The Archipelago runtime of a source checkout, for the local server.
sys.path.insert(0, str(BUILD / "ap-runtime"))

from tools import cemu_profile as profile  # noqa: E402

PLAY_SEEDS = DATA / "play-seeds"
PORT = 38281
GAME = "Breath of the Wild"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(folder: Path) -> dict[str, str]:
    if not folder.is_dir():
        return {}
    return {path.relative_to(folder).as_posix(): sha(path)
            for path in sorted(folder.rglob("*")) if path.is_file()}


def find_seed(name: str | None, pack_path: Path | None = None) -> tuple[Path, dict, Path]:
    seeds = sorted(path for path in PLAY_SEEDS.iterdir()
                   if (path / "analysis.json").is_file()) if PLAY_SEEDS.is_dir() else []
    if name:
        seeds = [path for path in seeds if path.name == name]
    if len(seeds) != 1:
        raise RuntimeError("name the play seed (--seed): "
                           + ", ".join(path.name for path in seeds) or "none")
    folder = seeds[0]
    report = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    archive = Path(report["archive"])
    if sha(archive) != report["archive_sha256"]:
        raise RuntimeError("the seed archive changed")
    if pack_path is not None:
        from tools.build_pack_from_source import verify_pack
        from tools.play_pack import seed_binding
        pack_path = pack_path.resolve()
        verify_pack(pack_path, seed_binding(folder))
        return folder, report, pack_path
    from tools.play_pack import outdated, selected_pack
    try:
        stale = outdated(selected_pack(folder))
    except (OSError, ValueError, RuntimeError, KeyError):
        stale = ["(no pack)"]
    if stale:
        # As the player's launcher does: a pack built from older sources would
        # play without the change being tested (Vilia's price, 04/10).
        from tools.play_seed import refresh
        print(f"Pack out of date ({', '.join(stale[:3])}{'...' if len(stale) > 3 else ''}): "
              "building it again (about a minute)...", flush=True)
        refresh(folder)
    return folder, report, selected_pack(folder)


def enabled_packs(portable: Path) -> list[str]:
    import xml.etree.ElementTree as ET
    root = ET.parse(portable / "settings.xml").getroot()
    packs = root.find("GraphicPack")
    return [] if packs is None else [entry.get("filename") for entry in packs]


class Stream:
    """Console output, copied into the session folder (tracebacks included)."""

    def __init__(self, console, path: Path):
        self.console = console
        self.file = path.open("a", encoding="utf-8", errors="replace")

    def write(self, text: str) -> int:
        self.file.write(text)
        self.file.flush()
        return self.console.write(text)

    def flush(self) -> None:
        self.file.flush()
        self.console.flush()

    def fileno(self) -> int:
        return self.console.fileno()


class Tee:
    def __init__(self, path: Path):
        self.file = path.open("a", encoding="utf-8")
        self.lock = threading.Lock()

    def __call__(self, line) -> None:
        text = f"{datetime.now().strftime('%H:%M:%S')} {line}"
        with self.lock:
            self.file.write(text + "\n")
            self.file.flush()
        print(text, flush=True)


def slot_name(report: dict) -> str:
    """The name of the seed's BOTW slot, the one the client connects as."""
    return report["audit"]["slots"][str(report.get("botw_slot", 1))]


async def console(runtime, context, log, slot_name: str) -> None:
    """Typed lines: /command for the AP server, anything else as AP chat.
    Without a local server (context None), a command goes to the room as the
    players type them in chat: /hint x as !hint x."""
    lines: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    reader_stopped = threading.Event()

    def reader():
        while not reader_stopped.is_set():
            try:
                line = input()
            except (EOFError, KeyboardInterrupt, OSError):
                return
            if reader_stopped.is_set():
                return
            try:
                loop.call_soon_threadsafe(lines.put_nowait, line)
            except RuntimeError:
                # The loop can close between the stop check and scheduling.
                if loop.is_closed():
                    return
                raise

    threading.Thread(target=reader, name="console", daemon=True).start()
    server = (f"/send {slot_name} <item>, /hint {slot_name} <item>, /players, /status"
              if context is not None else "/hint <item>, /players, /status (sent to the room as !hint...)")
    log(f"Console: {server}; "
        "/ap-tip <text> (in-game journal); /ap-disconnect [s] (simulated AP outage); "
        "/ap-evt [n|reset] (event requests seen by the game); "
        "/ap-deathlink [cause] (test: a DeathLink received, sent to nobody); "
        "any other text goes to the AP chat.")
    try:
        while not runtime.stop_event.is_set():
            line = (await lines.get()).strip()
            if not line:
                continue
            try:
                if runtime.handle_local_command(line):
                    continue
                if line.startswith("/") and context is not None:
                    context.commandprocessor(line)
                elif line.startswith("/") and not runtime.ap.connected:
                    log("command not sent: Archipelago is offline")
                elif line.startswith("/"):
                    await runtime.ap.say("!" + line[1:])
                elif runtime.ap.connected:
                    await runtime.ap.say(line)
                else:
                    log("message not sent: Archipelago is offline")
            except Exception as exc:  # noqa: BLE001 - a typo must not stop the session
                log(f"command refused: {exc!r}")
    finally:
        reader_stopped.set()


async def play(folder: Path, report: dict, pack: Path, session: Path,
               process: subprocess.Popen, log: Tee, *, journal: bool,
               connect: str | None = None, password: str | None = None,
               host: bool = False) -> dict:
    """The client until Cemu closes, on the room at `connect`, or on a local
    server hosting the seed (on every interface with `host`)."""
    from botw_client.runtime import BotwClientRuntime
    from botw_client.tip_channel import TipChannel

    def on_loop_error(_loop, context_data):
        log("asyncio error: " + context_data.get("message", ""))
        error = context_data.get("exception")
        if error is not None:
            traceback.print_exception(type(error), error, error.__traceback__)

    async def client(address: str, context) -> dict:
        asyncio.get_running_loop().set_exception_handler(on_loop_error)
        name = slot_name(report)
        runtime = BotwClientRuntime(
            address, name, password, state_path=folder / "client-state.json",
            log=log, game_name=GAME, native_presentations=True, native_delivery=True,
            tip_factory=TipChannel if journal else None,
            game_process_alive=lambda: process.poll() is None,
            delivery_catalog_path=pack / "delivery_catalog.json",
            game_language=profile.console_language())

        async def watch_cemu():
            while process.poll() is None:
                await asyncio.sleep(1.0)
            log("Cemu closed: client stopping.")
            runtime.stop()

        watcher = asyncio.create_task(watch_cemu())
        chat = asyncio.create_task(console(runtime, context, log, name))
        try:
            await runtime.run()
        finally:
            for task in (watcher, chat):
                task.cancel()
            await asyncio.gather(watcher, chat, return_exceptions=True)
        return {
            "checked_locations": sorted(runtime.ap.checked_locations),
            "checked_names": sorted(runtime.ap.location_name(i) or str(i)
                                    for i in runtime.ap.checked_locations)
            if hasattr(runtime.ap, "location_name") else None,
            "received_items": [runtime.ap.item_name(runtime.ap.received_items[index])
                               for index in sorted(runtime.ap.received_items)],
            "native_session_bound": runtime._native_session_bound,
        }

    if connect is not None:
        log(f"Archipelago room: {connect}, slot {slot_name(report)}")
        return {"server": connect, **await client(connect, None)}

    import websockets
    from MultiServer import Context, server
    import worlds
    for package in worlds.network_data_package["games"].values():
        package.setdefault("item_name_groups", {})
        package.setdefault("location_name_groups", {})
    context = Context("127.0.0.1", PORT, "", "", 0, 0, False)
    context.load(report["archive"])
    context.init_save(True)          # .apsave next to the archive copy
    summary = {"server": f"local, port {PORT}" + (", every interface" if host else ""),
               "server_save": context.save_filename}
    interface = "0.0.0.0" if host else "127.0.0.1"
    try:
        async with websockets.serve(functools.partial(server, ctx=context), interface, PORT):
            log(f"local AP server ready on {interface}:{PORT}"
                + (": the other players connect to this computer's address, port "
                   f"{PORT}" if host else ""))
            summary.update(await client(f"ws://127.0.0.1:{PORT}", context))
    finally:
        # Reporting and server shutdown must never prevent the final AP save.
        # MultiServer catches write errors internally and returns False.
        if not context._save():
            raise OSError("the Archipelago server's final save failed")
    return summary


def main(argv: list[str] | None = None) -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", help="the seed, a folder of play-seeds in the data folder")
    parser.add_argument("--pack", type=Path, help="a pack built from the sources, to use explicitly")
    parser.add_argument("--prepare-only", action="store_true")
    try:
        # A test aid of source checkouts: a release does not ship it (tools/build_release.py).
        from tools.play_speed import speed_argument
    except ImportError:
        parser.set_defaults(speed=1.0)
    else:
        parser.add_argument("--speed", type=speed_argument, default=1.0,
                            help="run/sprint/climb speed multiplier (0.1 to 10, default 1), for tests")
    try:
        # Test aids of source checkouts too (tools/play_aids.py).
        from tools.play_aids import damage_argument
    except ImportError:
        parser.set_defaults(invincible=False, stamina=False, unbreakable=False, damage=1, cheats=False)
    else:
        aids = parser.add_argument_group("test aids")
        aids.add_argument("--invincible", action="store_true", help="Link's hearts never drop")
        aids.add_argument("--stamina", action="store_true", help="endless stamina")
        aids.add_argument("--unbreakable", action="store_true", help="weapons, bows and shields never break")
        aids.add_argument("--damage", type=damage_argument, default=1,
                          help="weapons and bows hit this many times harder (2 to 100); "
                               "enemies wielding them too")
        aids.add_argument("--cheats", action="store_true",
                          help="all of them: --invincible --stamina --unbreakable --damage 10")
    server = parser.add_mutually_exclusive_group()
    server.add_argument("--connect", metavar="ADDRESS",
                        help="join the room hosting the seed (archipelago.gg:38281...) "
                             "instead of a local server")
    server.add_argument("--host", action="store_true",
                        help=f"the local server listens on every network interface (port {PORT}), "
                             "for the other players of the seed")
    parser.add_argument("--password", help="the room's password, with --connect")
    arguments = parser.parse_args(argv)
    if arguments.password and not arguments.connect:
        parser.error("--password goes with --connect")
    cheats = arguments.cheats
    aids = [key for key, chosen in (("Invincible", arguments.invincible), ("Stamina", arguments.stamina),
                                    ("Unbreakable", arguments.unbreakable)) if chosen or cheats]
    damage = arguments.damage if arguments.damage > 1 or not cheats else 10
    run(arguments.seed, pack=arguments.pack, prepare_only=arguments.prepare_only, speed=arguments.speed,
        connect=arguments.connect, password=arguments.password, host=arguments.host,
        aids=aids, damage=damage)


def run(seed: str | None, *, pack: Path | None = None, prepare_only: bool = False, speed: float = 1.0,
        connect: str | None = None, password: str | None = None, host: bool = False,
        aids: list[str] = (), damage: int = 1) -> None:
    """A session of the prepared seed `seed`, until Cemu closes."""
    folder, report, pack = find_seed(seed, pack)
    from tools.play_seed import hostable
    if not connect and not hostable(report):
        raise SystemExit("This seed was prepared from its slot file only: a local server needs "
                         "the seed's zip, and Archipelago. Join the room hosting it: --connect <address>.")
    pack_manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    # The AP journal lives in the game's tip frame; every pack carries it.
    journal = pack_manifest.get("ap_journal") == "tip_channel"
    if speed != 1:
        from tools.play_speed import variant
        pack = variant(pack, speed, DATA / 'play-speed-packs')
    source_saves = profile.SAVES / f"{profile.SOURCE_ACCOUNT:08x}"
    source_saves_before = tree_hashes(source_saves)
    account = profile.ensure_play_account()
    portable = profile.prepare_play(pack)
    # The graphic packs of the player's own Cemu (tools/player_packs.py), copied
    # into the profile, but those the seed pack cannot run with.
    from tools import player_packs
    try:
        mods = player_packs.enabled(profile.source_user_data(), profile.region().title)
    except (OSError, KeyError, ValueError) as exc:
        mods = []
        print(f"Your Cemu's graphic packs could not be read: {exc}", flush=True)
    ours = player_packs.seed_pack(pack)
    kept, left = player_packs.carried(mods, ours)
    mirrored = player_packs.mirror(kept, portable / "graphicPacks")
    player_packs.enable(portable, mirrored)
    aid_packs = []
    if aids or damage > 1:
        from tools import play_aids
        aid_packs = play_aids.install(
            portable / "graphicPacks", list(aids), damage, profile.update() / "content",
            pack / "content/System/Resource/ResourceSizeTable.product.srsizetable")
        play_aids.enable(portable, aid_packs)
    packs = enabled_packs(portable)
    if packs != [f"graphicPacks/{profile.PACK_PREFIX}{pack.name}/rules.txt",
                 *(entry["entry"] for entry in mirrored), *(entry["entry"] for entry in aid_packs)]:
        raise RuntimeError(f"the play profile loads something else: {packs}")
    game = profile.game()
    print(f"Play profile ready: seed {folder.name}, pack {pack.name}, account "
          f"{account['account']}. Link's speed: x{speed:g}; graphic packs enabled: {len(packs)}.",
          flush=True)
    if aid_packs:
        print("Test aids: " + ", ".join(entry["name"] for entry in aid_packs) + ".", flush=True)
    print("\n".join(player_packs.report(mods, ours, left)), flush=True)
    if journal:
        print("AP journal in the tip frame; try it: /ap-tip <text>.", flush=True)
    else:
        print("No AP journal in the tip frame with this pack.", flush=True)
    if prepare_only:
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    session = folder / "sessions" / stamp
    session.mkdir(parents=True)
    play_saves = profile.SAVES / f"{profile.PLAY_ACCOUNT:08x}"
    result = {"schema": 1, "started_utc": stamp, "seed": folder.name, "pack": pack.name,
              "locomotion_speed_multiplier": speed,
              "test_aids": [{k: v for k, v in entry.items() if k != "files"} for entry in aid_packs],
              "native_tip_channel": journal,
              "account": account, "graphic_packs": packs,
              "player_packs": [{"entry": mod.entry, "priority": mod.priority,
                                "carried": mod.entry not in left} for mod in mods],
              "play_saves_before": tree_hashes(play_saves), "status": "running"}
    # A hard crash of this console must land in the report: faulthandler
    # catches native faults, the hooks catch Python errors, and stderr is
    # copied into the session folder.
    sys.stderr = Stream(sys.stderr, session / "stderr.log")
    faulthandler.enable(sys.stderr)
    threading.excepthook = lambda args: traceback.print_exception(
        args.exc_type, args.exc_value, args.exc_traceback)
    sys.excepthook = traceback.print_exception
    (session / "session.json").write_text(json.dumps(result, indent=2) + "\n",
                                          encoding="utf-8")
    log = Tee(session / "client.log")
    print("Archipelago session: Cemu starts on the play account. Play normally and "
          "save whenever you like; close Cemu to end the session. "
          "Do not close this window before Cemu.", flush=True)
    process = subprocess.Popen([str(profile.PROFILE / "Cemu.exe"), "-m", str(portable / "mlc01"),
                                "-g", str(game)], cwd=profile.PROFILE)
    os.environ["BOTW_CEMU_PID"] = str(process.pid)
    os.environ["BOTW_CEMU_LOG"] = str(portable / "log.txt")
    os.environ["BOTW_PRESENTATION_EVIDENCE"] = str(session / "presentation-evidence")
    result["pid"] = process.pid
    try:
        result.update(asyncio.run(play(folder, report, pack, session, process, log,
                                      journal=journal, connect=connect,
                                      password=password, host=host)))
        result["status"] = "finished"
    except KeyboardInterrupt:
        result["status"] = "interrupted"
    except Exception as exc:  # noqa: BLE001 - reported, then re-raised
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        log(f"Client stopped on an error: {result['error']}. Commands are no longer active.")
        traceback.print_exc()
        raise
    finally:
        if process.poll() is None:
            print("Close Cemu to end the session.", flush=True)
            process.wait()
        result["play_saves_after"] = tree_hashes(play_saves)
        result["source_saves_unchanged"] = tree_hashes(source_saves) == source_saves_before
        cemu_log = portable / "log.txt"
        if cemu_log.exists():
            (session / "cemu.log").write_bytes(cemu_log.read_bytes())
        result["finished_utc"] = datetime.now(timezone.utc).isoformat()
        (session / "session.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Session saved: {session}", flush=True)
        if not result["source_saves_unchanged"]:
            print("WARNING: the saves copied from the Cemu installation have changed.", flush=True)


if __name__ == "__main__":
    main()
