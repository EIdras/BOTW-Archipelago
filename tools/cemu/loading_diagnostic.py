"""Read-only loading observations; deliberately makes no readiness decision."""
import json
import threading
import time
from tools.cemu import autonomous_eventflow, menu_diagnostic


def gameplay_state(catalog):
    rows = catalog["screens"]
    hud = rows[42]
    loading_closed = all(rows[i]["pointer"] and rows[i]["activity"] == 255
                         and rows[i]["state_94"] == 0x01000000 for i in (78, 84))
    loading_closed = loading_closed and not rows[85]["pointer"] and rows[85]["activity"] == 255
    ready = (menu_diagnostic.menu_state(catalog, "map")["idle"] and loading_closed
             and not rows[74]["pointer"] and rows[74]["activity"] == 255
             and bool(hud["pointer"]) and hud["activity"] == 0 and hud["state_94"] == 0x200)
    return dict(ready=bool(ready), loading_observed=rows[78]["activity"] == 1,
                dialogue_observed=bool(rows[74]["pointer"]) and rows[74]["activity"] == 1,
                screens=[rows[i] for i in (42, 44, 46, 47, 68, 74, 78, 84, 85)])


def wait_for_gameplay(read, path, timeout=120, activity="loading"):
    """Require an observed loading screen before releasing this diagnostic request."""
    start = time.monotonic()
    if activity not in ("loading", "dialogue"):
        raise ValueError("unknown activity")
    seen_key = activity + "_seen"
    evidence = dict(status="waiting", activity=activity, native_calls_issued=False, transitions=[])
    evidence[seen_key] = False
    previous, stable = None, 0
    def flush():
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    try:
        while time.monotonic() - start < timeout:
            catalog = read()
            state = gameplay_state(catalog)
            evidence[seen_key] |= state[activity + "_observed"]
            stable = stable + 1 if evidence[seen_key] and state["ready"] else 0
            if catalog != previous:
                evidence["transitions"].append(dict(seconds=time.monotonic() - start, state=state, catalog=catalog))
                previous = catalog
                flush()
            if stable >= 3:
                evidence.update(status="released", seconds=time.monotonic() - start)
                return evidence
            time.sleep(0.1)
        raise RuntimeError(f"Activite {activity} puis retour gameplay non observes en{timeout}s : aucune demande envoyee")
    except BaseException as exc:
        evidence.update(status="failed", error=str(exc))
        raise
    finally:
        flush()


def snapshot(process, cave):
    result = {}
    def word(address):
        data = process.read(address, 4)
        if data is None or len(data) != 4:
            raise RuntimeError("short loading diagnostic read")
        return int.from_bytes(data, "big")
    def event_state():
        state = autonomous_eventflow.inspect(process, cave.base)
        if state["manager_available"]:
            state.update({f"field_{offset:x}": word(cave.base + state["manager"] + offset)
                          for offset in (0x174b4, 0x175d0)})
        return state
    # Independent components preserve evidence if a manager disappears mid-load.
    for name, read in (
        ("screens", lambda: menu_diagnostic.screens(process, cave.base)),
        ("event", event_state),
        ("call_count", lambda: word(cave.call_n)),
        ("pending_call", lambda: word(cave.pf_req)),
        ("substitution", cave.sub_state),
    ):
        try:
            result[name] = read()
        except Exception as exc:
            result[name] = {"read_error": str(exc)}
    return result


def capture(read, prompt, path, label, interval=0.05, limit=12000, instructions=None,
            confirmation="Teleportation effectuee et Link de nouveau jouable ? oui/non : ",
            confirmation_key="teleport_completed_user_report", context=None):
    evidence = dict(status="recording", label=label, native_calls_issued=False,
                    interval_seconds=interval, samples=0, read_error_samples=0, transitions=[], truncated=False,
                    limitation="Polling can miss transitions; gameplay boundaries are user observations.")
    if context is not None:
        evidence["context_user_report"] = context
    stop = threading.Event()
    started = time.monotonic()
    def flush():
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    def sample():
        try:
            state = read()
        except Exception as exc:
            state = {"read_error": str(exc)}
        evidence["samples"] += 1
        if "read_error" in state or any(isinstance(v, dict) and "read_error" in v for v in state.values()):
            evidence["read_error_samples"] += 1
        if not evidence["transitions"] or evidence["transitions"][-1]["state"] != state:
            if len(evidence["transitions"]) < limit:
                evidence["transitions"].append(dict(seconds=time.monotonic() - started, state=state))
            else:
                evidence["truncated"] = True
    sample()
    flush()
    def monitor():
        last_flush = started
        try:
            while not stop.wait(interval):
                sample()
                if time.monotonic() - last_flush >= 1:
                    flush()
                    last_flush = time.monotonic()
        except Exception as exc:
            evidence["monitor_error"] = str(exc)
    worker = threading.Thread(target=monitor, daemon=True)
    worker.start()
    completed = False
    try:
        steps = instructions or [("gameplay_after", f"Capture {label} active. Revenir dans Cemu, ouvrir la carte et se teleporter vers un point deja accessible. "
               "Attendre la fin du chargement et Link jouable, sans ramasser d'objet. Revenir ici puis Entree : ")]
        for stage, instruction in steps:
            prompt(instruction)
            evidence.setdefault("user_markers", []).append(dict(stage=stage, seconds=time.monotonic() - started))
        completed = True
    finally:
        stop.set()
        worker.join()
        sample()
        evidence["status"] = ("collected" if not evidence.get("monitor_error") and not evidence["truncated"]
                              and not evidence["read_error_samples"] else "needs_review") if completed else "interrupted"
        evidence["seconds"] = time.monotonic() - started
        flush()
    evidence[confirmation_key] = prompt(confirmation).strip().lower() == "oui"
    flush()
    if not evidence[confirmation_key]:
        raise RuntimeError("Retour au jeu non confirme : aucune presentation demandee")
    return evidence


def exercise(process, cave, prompt, report):
    for label in ("aller", "retour"):
        prompt(f"Avant capture {label} : rester avec Link jouable, tous menus fermes. Entree : ")
        capture(lambda: snapshot(process, cave), prompt,
                report.with_name(f"presentation-loading-{label}.json"), label)
