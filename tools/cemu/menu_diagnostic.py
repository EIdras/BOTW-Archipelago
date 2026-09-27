"""Snapshot the known screen-manager table without guessing a busy predicate."""
import json
import time
from tools.cemu.getdemo_state import SCR_PTR


def inventory_state(catalog):
    selected = [catalog["screens"][i] for i in (46, 47, 68)]
    idle = all(s["activity"] == 255 for s in selected)
    idle = idle and selected[1]["pointer"] == 0
    idle = idle and all(s["pointer"] and s["state_94"] == 0x01000000 for s in (selected[0], selected[2]))
    return {"idle": bool(idle), "screens": selected}


def menu_state(catalog, kind):
    selected = [catalog["screens"][i] for i in (44, 46, 47, 68)]
    idle = all(s["activity"] == 255 for s in selected) and selected[2]["pointer"] == 0
    idle = idle and all(s["pointer"] and s["state_94"] in (0x01000000, 0x01fc0000)
                        for s in (selected[0], selected[1], selected[3]))
    expected = selected[0]["activity"] == 1 if kind == "map" else (
        selected[1]["activity"] == 1 and selected[3]["activity"] == 1 and bool(selected[2]["pointer"]))
    return dict(idle=bool(idle), expected_menu_open=bool(expected), screens=selected)


def wait_for_inventory(process, base, path, timeout=90, menu_kind=None):
    """Diagnostic queue: require the inventory busy initially, then await idle."""
    start = time.monotonic()
    evidence = {"status": "waiting", "menu_kind": menu_kind or "inventory", "transitions": [], "native_call_issued_by_waiter": False}
    previous, stable = None, 0
    try:
        while time.monotonic() - start < timeout:
            catalog = screens(process, base)
            state = menu_state(catalog, menu_kind) if menu_kind else inventory_state(catalog)
            if previous is None and menu_kind and not state["expected_menu_open"]:
                raise RuntimeError("Menu attendu non observe : aucun appel envoye")
            if previous is None and state["idle"]:
                raise RuntimeError("Inventaire deja ferme : le report de demande ne peut pas etre teste")
            if state != previous:
                evidence["transitions"].append({"seconds": time.monotonic() - start, **state})
                path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
                previous = state
            stable = stable + 1 if state["idle"] else 0
            if stable >= 3:
                evidence.update(status="released", seconds=time.monotonic() - start)
                return evidence
            time.sleep(0.1)
        raise RuntimeError("Inventaire non libere en90 secondes : aucune demande native envoyee")
    except BaseException as exc:
        evidence.update(status="failed", error=str(exc))
        raise
    finally:
        path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


def screens(process, base):
    def read(address, size):
        if not 0x01000000 <= address < 0x60000000:
            raise ValueError("invalid screen pointer")
        data = process.read(base + address, size)
        if data is None or len(data) != size:
            raise RuntimeError("short screen catalog read")
        return data
    def word(address):
        return int.from_bytes(read(address, 4), "big")
    manager = word(SCR_PTR)
    count = word(manager + 0x14)
    if count != 99:
        raise ValueError("unexpected screen table size")
    table = word(manager + 0x18)
    activity = read(manager + 0x604, count)
    result = []
    for index in range(count):
        pointer = word(table + index * 4)
        result.append(dict(index=index, pointer=pointer, activity=activity[index],
                           state_94=word(pointer + 0x94) if pointer else None))
    return dict(manager=manager, screens=result)


def exercise(process, base, prompt, path, other_menus=False):
    result = {"status": "running", "method": "read_only_manual_menu_stages", "stages": []}
    try:
        steps = [
            ("gameplay", "Fermer tous les menus et rester avec Link jouable. Entree ici : "),
            ("inventory", "Ouvrir l'inventaire, le LAISSER OUVERT, puis revenir ici et Entree : "),
            ("gameplay_after", "Fermer l'inventaire, attendre Link jouable, puis revenir ici et Entree : ")]
        if other_menus:
            steps = [steps[0],
                ("map", "Ouvrir la CARTE, sans lancer de teleportation. La laisser ouverte puis revenir ici et Entree : "),
                ("after_map", "Fermer la carte, attendre Link jouable, puis revenir ici et Entree : "),
                ("system", "Ouvrir le menu SYSTEME/OPTIONS (sans sauvegarder ni charger). Le laisser ouvert puis revenir ici et Entree : "),
                ("after_system", "Fermer tous les menus, attendre Link jouable, puis revenir ici et Entree : ")]
        for stage, instruction in steps:
            prompt(instruction)
            result["stages"].append(dict(stage=stage, **screens(process, base)))
            path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        result["status"] = "collected"
    except BaseException as exc:
        result.update(status="failed", error=str(exc))
        raise
    finally:
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
