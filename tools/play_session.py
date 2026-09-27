"""A play session: Cemu, a local AP server and the client, together.

    python tools/play_session.py [--seed <seed folder name>] [--speed <x>]

  * the pack bound to a solo play seed (tools/play_seed.py), the only graphic
    pack enabled in the isolated Cemu profile (tools/cemu_profile.py);
  * a Cemu account of its own, so that a new game never overwrites the saves
    copied from the Cemu installation, which are checked unchanged at the end;
  * the official AP server, in process, on 127.0.0.1:38281, saving its state
    next to the seed archive (.apsave): progress carries over between sessions;
  * the client runtime (native deliveries, presentations, AP journal), whose
    state also lives in the seed folder, until Cemu closes.
Lines typed in the console go to the AP server as chat or commands (/hint,
/status...), or to the client (/ap-... commands).

Each launch writes .build/play-seeds/<seed>/sessions/<stamp>/ : the client
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
sys.path.insert(0, str(ROOT / ".build/ap-runtime"))

from tools import cemu_profile as profile  # noqa: E402

PLAY_SEEDS = ROOT / ".build/play-seeds"
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
        from tools.build_pack_from_source import load_seed, verify_pack
        binding = load_seed(folder / "analysis.json", 1)
        pack_path = pack_path.resolve()
        verify_pack(pack_path, binding)
        return folder, report, pack_path
    from tools.play_pack import selected_pack
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


async def console(runtime, context, log, slot_name: str) -> None:
    """Typed lines: /command for the AP server, anything else as AP chat."""
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
    log(f"Console: /send {slot_name} <item>, /hint {slot_name} <item>, /players, /status; "
        "/ap-tip <text> (in-game journal); /ap-disconnect [s] (simulated AP outage); "
        "/ap-evt [n|reset] (event requests seen by the game); "
        "any other text goes to the AP chat.")
    try:
        while not runtime.stop_event.is_set():
            line = (await lines.get()).strip()
            if not line:
                continue
            try:
                if runtime.handle_local_command(line):
                    continue
                if line.startswith("/"):
                    context.commandprocessor(line)
                elif runtime.ap.connected:
                    await runtime.ap.say(line)
                else:
                    log("message not sent: Archipelago is offline")
            except Exception as exc:  # noqa: BLE001 - a typo must not stop the session
                log(f"command refused: {exc!r}")
    finally:
        reader_stopped.set()


async def play(folder: Path, report: dict, pack: Path, session: Path,
               process: subprocess.Popen, log: Tee, *, journal: bool) -> dict:
    import websockets
    from MultiServer import Context, server
    from botw_client.runtime import BotwClientRuntime

    import worlds
    for package in worlds.network_data_package["games"].values():
        package.setdefault("item_name_groups", {})
        package.setdefault("location_name_groups", {})
    context = Context("127.0.0.1", PORT, "", "", 0, 0, False)
    context.load(report["archive"])
    context.init_save(True)          # .apsave next to the archive copy
    summary = {"server_save": context.save_filename}
    try:
        async with websockets.serve(functools.partial(server, ctx=context),
                                    "127.0.0.1", PORT):
            log(f"local AP server ready on 127.0.0.1:{PORT}")

            def on_loop_error(_loop, context_data):
                log("asyncio error: " + context_data.get("message", ""))
                error = context_data.get("exception")
                if error is not None:
                    traceback.print_exception(type(error), error, error.__traceback__)

            asyncio.get_running_loop().set_exception_handler(on_loop_error)
            from botw_client.tip_channel import TipChannel
            slot_name = report["audit"]["slots"]["1"]
            runtime = BotwClientRuntime(
                f"ws://127.0.0.1:{PORT}", slot_name, state_path=folder / "client-state.json",
                log=log, game_name=GAME, native_presentations=True, native_delivery=True,
                tip_factory=TipChannel if journal else None,
                game_process_alive=lambda: process.poll() is None,
                delivery_catalog_path=pack / "delivery_catalog.json")

            async def watch_cemu():
                while process.poll() is None:
                    await asyncio.sleep(1.0)
                log("Cemu closed: client stopping.")
                runtime.stop()

            watcher = asyncio.create_task(watch_cemu())
            chat = asyncio.create_task(console(runtime, context, log, slot_name))
            try:
                await runtime.run()
            finally:
                for task in (watcher, chat):
                    task.cancel()
                await asyncio.gather(watcher, chat, return_exceptions=True)
                summary.update({
                    "checked_locations": sorted(runtime.ap.checked_locations),
                    "checked_names": sorted(runtime.ap.location_name(i) or str(i)
                                            for i in runtime.ap.checked_locations)
                    if hasattr(runtime.ap, "location_name") else None,
                    "received_items": [runtime.ap.item_name(runtime.ap.received_items[index])
                                       for index in sorted(runtime.ap.received_items)],
                    "native_session_bound": runtime._native_session_bound,
                })
    finally:
        # Reporting and server shutdown must never prevent the final AP save.
        # MultiServer catches write errors internally and returns False.
        if not context._save():
            raise OSError("the Archipelago server's final save failed")
    return summary


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", help="folder of .build/play-seeds")
    parser.add_argument("--pack", type=Path, help="a pack built from the sources, to use explicitly")
    parser.add_argument("--prepare-only", action="store_true")
    from tools.play_speed import speed_argument, variant
    parser.add_argument("--speed", type=speed_argument, default=1.0,
                        help="run/sprint/climb speed multiplier (0.1 to 10, default 1)")
    arguments = parser.parse_args()

    folder, report, pack = find_seed(arguments.seed, arguments.pack)
    pack_manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    # The AP journal lives in the game's tip frame; every pack carries it.
    journal = pack_manifest.get("ap_journal") == "tip_channel"
    pack = variant(pack, arguments.speed, ROOT / '.build/play-speed-packs')
    source_saves = profile.SAVES / f"{profile.SOURCE_ACCOUNT:08x}"
    source_saves_before = tree_hashes(source_saves)
    account = profile.ensure_play_account()
    portable = profile.prepare_play(pack)
    packs = enabled_packs(portable)
    if packs != [f"graphicPacks/{profile.PACK_PREFIX}{pack.name}/rules.txt"]:
        raise RuntimeError(f"the play profile loads something else: {packs}")
    print(f"Play profile ready: seed {folder.name}, pack {pack.name}, account "
          f"{account['account']}. Link's speed: x{arguments.speed:g}; one graphic pack enabled.",
          flush=True)
    if journal:
        print("AP journal in the tip frame; try it: /ap-tip <text>.", flush=True)
    else:
        print("No AP journal in the tip frame with this pack.", flush=True)
    if arguments.prepare_only:
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    session = folder / "sessions" / stamp
    session.mkdir(parents=True)
    play_saves = profile.SAVES / f"{profile.PLAY_ACCOUNT:08x}"
    result = {"schema": 1, "started_utc": stamp, "seed": folder.name, "pack": pack.name,
              "locomotion_speed_multiplier": arguments.speed,
              "native_tip_channel": journal,
              "account": account, "graphic_packs": packs,
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
    game = Path(json.loads((ROOT / "botw_client.json").read_text(encoding="utf-8"))["game"])
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
                                      journal=journal)))
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
