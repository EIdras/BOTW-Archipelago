"""The Breath of the Wild graphic packs the player's own Cemu runs.

    python tools/player_packs.py [--user-data <Cemu user folder>] [--pack <seed pack>]

Mods reach Cemu as graphic packs, whatever installed them (UKMM and BCML
deploy one, others are unzipped by hand). This reads them as Cemu does
(GraphicPack2::LoadAll and LoadGraphicPack, CemuConfig): every folder of
graphicPacks/ holding a rules.txt, in the order Cemu walks them (depth first,
in the order the file system lists them: the order Cemu activates them,
which settles equal priorities and hands out the code caves); enabled when
settings.xml lists it without disabled="true", or lists it not at all and
its [Definition] says default = true; for the profile's version of the game
(titleIds). Nothing is copied or changed.

For each one: its fsPriority (the highest wins a file both replace), the
presets chosen, the files of content/ and aoc/ it replaces, and the
addresses its patches (patch_*.asm) write for our executable, which a seed
pack's patches must not write too: of two patches of one instruction,
only one runs.

The play profile then runs them too: carried() picks those a seed pack can
run with, mirror() copies them into the profile's graphicPacks/AP_Player/,
under the path they have in the player's Cemu (so Cemu walks them in the
same order, after our AP_ packs), and enable() turns them on there with
their presets. The seed pack is built on top of the copies holding game
files (layers(); tools/play_mods.py), with a priority above theirs, so that
the file both change is the seed pack's, made from the mod's.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.cemu import guest  # noqa: E402

FOLDER = "graphicPacks"
DEFAULT_PRIORITY = 100          # GraphicPack2::m_fs_priority
LEGACY_VERSION = 2              # GP_LEGACY_VERSION: packs up to it are not loaded
MODULE = 0x6267BFD0             # moduleMatches of the v208 executable, in every version
PATCH_LINE = re.compile(r"^\s*(0x[0-9a-fA-F]+)\s*=", re.MULTILINE)
MIRROR = "AP_Player"            # the profile's copies, under its graphicPacks/
MIRROR_STATE = "mirror.json"    # in MIRROR: the source of each copy, and its fingerprint


@dataclass(frozen=True)
class PlayerPack:
    folder: Path
    entry: str                  # the pack's name in settings.xml: graphicPacks/<path>/rules.txt
    name: str
    virtual_path: str           # where Cemu's graphic pack window shows it
    priority: int
    default: bool
    presets: tuple[tuple[str, str], ...]        # (category, preset) chosen in settings.xml
    content: tuple[str, ...]    # files it replaces, relative to content/
    aoc: tuple[str, ...]        # relative to aoc/
    patches: tuple[str, ...]    # patch_*.asm, or patches.txt
    code: bool                  # it replaces files of code/
    patched: frozenset[int]     # addresses its patches write in our executable
    ram: tuple[tuple[int, int], ...] = ()   # its [RAM] mappings (start, end): Extended Memory's
    enabled: bool = True        # Cemu runs it (installed() lists the others too)
    order: int = 0              # its place in the order Cemu loads the packs

    @property
    def path(self) -> str:
        """Its folder, relative to graphicPacks/."""
        return self.entry[len(FOLDER) + 1:-len("/rules.txt")]


def uncommented(line: str) -> str:
    """`line` without its comment: from a # or ; outside quotes (IniParser)."""
    quoted = False
    for i, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char in "#;" and not quoted:
            return line[:i]
    return line


def sections(rules: Path) -> list[tuple[str, dict[str, str]]]:
    """The sections of a rules.txt in order: (name, options), option names in
    lower case, the first of each name kept (IniParser.FindOption)."""
    found: list[tuple[str, dict[str, str]]] = []
    for raw in rules.read_text(encoding="utf-8", errors="replace").splitlines():
        line = uncommented(raw).strip()
        if not line:
            continue
        if line.startswith("["):
            end = line.find("]")
            found.append(((line[1:end] if end > 0 else line[1:]).strip(), {}))
            continue
        if not found or "=" not in line:
            continue
        key, value = line.split("=", 1)
        found[-1][1].setdefault(key.strip().lower(), value.strip().strip('"'))
    return found


def definition(rules: Path) -> dict[str, str] | None:
    """The options of the [Definition] section, names in lower case, or None
    when Cemu would not load the pack (no such first section, no or an
    outdated version)."""
    found = sections(rules)
    if not found or found[0][0].lower() != "definition":
        return None
    options = found[0][1]
    try:
        if int(options.get("version", "")) <= LEGACY_VERSION:
            return None
    except ValueError:
        return None
    return options


def ram_mappings(rules: Path) -> tuple[tuple[int, int], ...] | None:
    """The memory ranges a pack's [RAM] sections map (mapping0..31: start-end),
    as GraphicPack2 reads them; None when Cemu refuses the pack for them
    (before version 6, a bad syntax, an end not after the start, not aligned
    to 0x1000)."""
    options = definition(rules)
    if options is None:
        return None
    mappings = []
    for name, values in sections(rules):
        if name.lower() != "ram":
            continue
        for index in range(32):
            value = values.get(f"mapping{index}")
            if value is None:
                continue
            if int(options["version"]) <= 5:
                return None
            found = re.fullmatch(r"(0[xX][0-9a-fA-F]+|\d+)\s*-\s*(0[xX][0-9a-fA-F]+|\d+)", value.strip())
            if not found:
                return None
            start, end = int(found[1], 0), int(found[2], 0)
            if end <= start or start & 0xFFF or end & 0xFFF:
                return None
            mappings.append((start, end))
    return tuple(mappings)


def mem2_end(packs: list[PlayerPack]) -> int:
    """Where the game's main memory ends with `packs` running (in the order
    Cemu activates them): a mapping from MEM2's start moves its end, the last
    one wins, and one past the overlay area is refused (memory_mapForCurrentTitle)."""
    end = guest.MEM2_END
    for pack in packs:
        for start, stop in pack.ram:
            if start == guest.MEM2_START and stop <= guest.MEM2_MAX_END:
                end = stop
    return end


def memory_pack(packs: list[PlayerPack]) -> PlayerPack | None:
    """An installed pack, not enabled, that gives the game more main memory
    (Extended Memory, of Cemu's community packs), the one named so first."""
    found = [pack for pack in packs if not pack.enabled
             and mem2_end([pack]) > guest.MEM2_END and not pack.code]
    found.sort(key=lambda pack: (pack.name.lower() != "extended memory", pack.order))
    return found[0] if found else None


def settings_entries(settings: Path) -> dict[str, tuple[bool, tuple[tuple[str, str], ...]]]:
    """settings.xml's graphic packs: name -> (disabled, presets)."""
    try:
        packs = ET.parse(settings).getroot().find("GraphicPack")
    except (OSError, ET.ParseError):
        return {}
    entries = {}
    for entry in packs if packs is not None else ():
        name = (entry.get("filename") or "").replace("\\", "/")
        if not name:
            continue
        presets = tuple((preset.findtext("category") or "", preset.findtext("preset") or "")
                        for preset in entry.findall("Preset"))
        entries[name] = (entry.get("disabled", "").lower() in ("true", "1"), presets)
    return entries


def pack_folders(root: Path) -> list[Path]:
    """The folders holding a rules.txt under `root`, in the order Cemu loads them."""
    found = []

    def walk(folder: Path):
        try:
            children = list(os.scandir(folder))
        except OSError:
            return
        for child in children:
            if not child.is_dir():
                continue
            path = Path(child.path)
            if (path / "rules.txt").is_file():
                found.append(path)
            elif not child.is_symlink():
                walk(path)
    walk(root)
    return found


def files(folder: Path) -> tuple[str, ...]:
    """The files under `folder`, relative to it, as Cemu redirects them (the
    folder itself may be a link: UKMM deploys content/ as one)."""
    if not folder.is_dir():
        return ()
    out = []
    for top, _dirs, names in os.walk(folder):
        out += [(Path(top) / name).relative_to(folder).as_posix() for name in names]
    return tuple(sorted(out))


def addresses(text: str, module: int = MODULE) -> set[int]:
    """The addresses a patch file writes, in its sections for `module` (moduleMatches)."""
    found = set()
    for section in re.split(r"^\s*\[[^\]\n]*\]\s*$", text, flags=re.MULTILINE)[1:]:
        matches = re.search(r"^\s*moduleMatches\s*=\s*([^\n;#]+)", section, re.MULTILINE)
        if not matches:
            continue
        modules = {int(value.strip(), 16) for value in matches.group(1).split(",") if value.strip()}
        if module not in modules:
            continue
        body = "\n".join(uncommented(line) for line in section.splitlines())
        found |= {int(value, 16) for value in PATCH_LINE.findall(body)}
    return found


def patched_addresses(folder: Path, module: int = MODULE) -> frozenset[int]:
    """The addresses the patch_*.asm of `folder` write for `module`."""
    found = set()
    for path in sorted(folder.glob("patch_*.asm")):
        found |= addresses(path.read_text(encoding="utf-8", errors="replace"), module)
    return frozenset(found)


def our_addresses() -> frozenset[int]:
    """Every address a seed pack's patches may write (all options: the tower
    maps add hooks), from the project's native sources."""
    from tools import build_native_from_source as native
    found = set()
    for text in native.generate(resource_gate=True, event_gate=True, tower_maps=True).values():
        found |= addresses(text if isinstance(text, str) else text.decode("utf-8"))
    return frozenset(found)


def enabled(user_data: Path, title: str) -> list[PlayerPack]:
    """The graphic packs Cemu runs for `title` (the game's eight-digit low title
    id, 101c9400), in the order it activates them."""
    return [pack for pack in installed(user_data, title) if pack.enabled]


def installed(user_data: Path, title: str) -> list[PlayerPack]:
    """Every graphic pack Cemu loads for `title`, enabled or not, in the order
    it walks them."""
    root = user_data / FOLDER
    title_id = int("00050000" + title, 16)
    entries = settings_entries(user_data / "settings.xml")
    packs = []
    for order, folder in enumerate(pack_folders(root)):
        options = definition(folder / "rules.txt")
        ram = ram_mappings(folder / "rules.txt")
        if options is None or ram is None:
            continue
        try:
            titles = {int(value.strip(), 16) for value in options.get("titleids", "").split(",") if value.strip()}
        except ValueError:
            continue
        if title_id not in titles:
            continue
        entry = f"{FOLDER}/{folder.relative_to(root).as_posix()}/rules.txt"
        default = options.get("default", "").lower() in ("true", "1")
        disabled, presets = entries.get(entry, (not default, ()))
        try:
            priority = int(options.get("fspriority", DEFAULT_PRIORITY))
        except ValueError:
            priority = DEFAULT_PRIORITY
        patches = tuple(sorted(path.name for path in folder.glob("patch_*.asm"))) or \
            (("patches.txt",) if (folder / "patches.txt").is_file() else ())
        packs.append(PlayerPack(
            folder=folder, entry=entry, name=options.get("name", folder.name),
            virtual_path=options.get("path", ""), priority=priority, default=default, presets=presets,
            content=files(folder / "content"), aoc=files(folder / "aoc"), patches=patches,
            code=(folder / "code").is_dir(), patched=patched_addresses(folder), ram=ram,
            enabled=not disabled, order=order))
    return packs


def shared_files(pack: PlayerPack, ours: dict) -> list[str]:
    replaced = {f"content/{name}" for name in pack.content} | {f"aoc/{name}" for name in pack.aoc}
    return sorted(replaced & set(ours["files"]))


def carried(packs: list[PlayerPack], patched: frozenset[int]) -> tuple[list[PlayerPack], dict[str, str]]:
    """The packs the play profile runs next to a seed pack whose patches may
    write `patched` (our_addresses()), and why each other one is left out (by
    entry). Game files shared with the seed pack are no reason: the seed pack
    is built on top of them (layers())."""
    keep, left = [], {}
    for pack in packs:
        if pack.code:
            left[pack.entry] = "it replaces the game's executable"
        elif pack.patched & patched:
            left[pack.entry] = "it patches code the Archipelago pack needs"
        else:
            keep.append(pack)
    return keep, left


def fingerprint(folder: Path) -> str:
    """Every file of a pack (through links, as Cemu reads it): name, size, time."""
    rows = []
    for top, _dirs, names in os.walk(folder, followlinks=True):
        for name in names:
            path = Path(top) / name
            stat = path.stat()
            rows.append((path.relative_to(folder).as_posix(), stat.st_size, stat.st_mtime_ns))
    return hashlib.sha256(json.dumps(sorted(rows)).encode()).hexdigest()


def mirror(packs: list[PlayerPack], graphic_packs: Path) -> list[dict]:
    """Copy `packs` into `graphic_packs`/MIRROR (a copy whose source has not
    changed is kept), remove the copies of other packs; the entries to enable."""
    root = graphic_packs / MIRROR
    state_path = root / MIRROR_STATE
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    wanted = {pack.path: pack for pack in packs}
    for path in list(state):
        if path not in wanted:
            shutil.rmtree(root / path, ignore_errors=True)
            del state[path]
    for folder in pack_folders(root):           # copies the state does not know
        path = folder.relative_to(root).as_posix()
        if path not in wanted or path not in state:
            shutil.rmtree(folder, ignore_errors=True)
            state.pop(path, None)
    entries = []
    for path, pack in wanted.items():
        target = root / path
        source = {"from": str(pack.folder), "fingerprint": fingerprint(pack.folder)}
        if state.get(path) != source or not (target / "rules.txt").is_file():
            shutil.rmtree(target, ignore_errors=True)
            state.pop(path, None)
            shutil.copytree(pack.folder, target)        # links are followed: their files are copied
            state[path] = source
        entries.append({"entry": f"{FOLDER}/{MIRROR}/{path}/rules.txt", "source": pack.entry,
                        "name": pack.virtual_path or pack.name, "priority": pack.priority,
                        "presets": [list(preset) for preset in pack.presets],
                        "fingerprint": source["fingerprint"], "game_files": bool(pack.content or pack.aoc)})
    root.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return entries


def layers(entries: list[dict], graphic_packs: Path) -> list[dict]:
    """The copies (mirror()) a seed pack is built over: those with game files,
    as Cemu lets them win a file, the highest fsPriority first, then the first
    loaded (the order of `entries`). folder: the copy; pack, priority and
    fingerprint: what the seed pack's identity records."""
    ordered = sorted((entry for entry in entries if entry["game_files"]),
                     key=lambda entry: (-entry["priority"], entries.index(entry)))
    return [{"folder": graphic_packs.parent / entry["entry"][:-len("/rules.txt")],
             "pack": entry["entry"][len(FOLDER) + 1:-len("/rules.txt")],
             "priority": entry["priority"], "fingerprint": entry["fingerprint"]} for entry in ordered]


def layer(folder: Path) -> dict:
    """A graphic pack folder as a layer (layers()), named after the folder: for builds by hand."""
    options = definition(folder / "rules.txt") or {}
    return {"folder": folder, "pack": folder.name, "fingerprint": fingerprint(folder),
            "priority": int(options.get("fspriority", DEFAULT_PRIORITY))}


def enable(portable: Path, entries: list[dict]) -> None:
    """Turn the copies on in the profile's settings.xml, with the player's presets."""
    settings = ET.parse(portable / "settings.xml")
    packs = settings.getroot().find("GraphicPack")
    for entry in entries:
        element = ET.SubElement(packs, "Entry", filename=entry["entry"])
        for category, preset in entry["presets"]:
            node = ET.SubElement(element, "Preset")
            ET.SubElement(node, "category").text = category
            ET.SubElement(node, "preset").text = preset
    settings.write(portable / "settings.xml", encoding="utf-8", xml_declaration=True)


def report(packs: list[PlayerPack], ours: dict | None = None, left: dict[str, str] | None = None) -> list[str]:
    """What the player's packs are, what they share with a seed pack (`ours`:
    its files, relative to the pack, and the addresses its patches write),
    and why some are not carried (`left`, from carried()), as lines to show."""
    if not packs:
        return ["Your Cemu runs no graphic pack for Breath of the Wild."]
    lines = [f"Your Cemu runs {len(packs)} graphic pack(s) for Breath of the Wild:"]
    for pack in packs:
        parts = [f"priority {pack.priority}"]
        if pack.content or pack.aoc:
            parts.append(f"{len(pack.content) + len(pack.aoc)} game files")
        if pack.patches:
            parts.append("code patches")
        if pack.presets:
            parts.append(", ".join(f"{category or 'preset'}: {preset}" for category, preset in pack.presets))
        lines.append(f"  - {pack.virtual_path or pack.name} ({'; '.join(parts)})")
        if ours is not None:
            shared = shared_files(pack, ours)
            if shared:
                lines.append(f"      the Archipelago pack is built on its version of {len(shared)} file(s): "
                             + ", ".join(shared[:6]) + (" ..." if len(shared) > 6 else ""))
            taken = sorted(pack.patched & ours["patched"])
            if taken:
                lines.append("      patches the same code as the Archipelago pack: "
                             + ", ".join(f"0x{address:08X}" for address in taken[:6])
                             + (" ..." if len(taken) > 6 else ""))
        if left is not None and pack.entry in left:
            lines.append(f"      not in the Archipelago game: {left[pack.entry]}")
    if left is not None:
        lines.append(f"The Archipelago game runs {len(packs) - len(left)} of them.")
    return lines


def seed_pack(pack: Path) -> dict:
    """What a seed pack shares with others: its game files and patched addresses."""
    return {"files": {path.relative_to(pack).as_posix() for path in pack.rglob("*")
                      if path.is_file() and path.relative_to(pack).parts[0] in ("content", "aoc")},
            "patched": patched_addresses(pack)}


if __name__ == "__main__":
    import argparse
    from tools import cemu_profile
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-data", type=Path,
                        help="Cemu's user folder (default: the one the play profile was copied from)")
    parser.add_argument("--pack", type=Path, help="a seed pack, to show what it shares with them")
    arguments = parser.parse_args()
    user_data = arguments.user_data or cemu_profile.source_user_data()
    print(f"Cemu user folder: {user_data}")
    found = enabled(user_data, cemu_profile.region().title)
    ours = seed_pack(arguments.pack) if arguments.pack else None
    print("\n".join(report(found, ours, carried(found, our_addresses())[1])))
