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
pack's patches must not write too (FPS++ takes our per-frame hook,
0x031FA97C).
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FOLDER = "graphicPacks"
DEFAULT_PRIORITY = 100          # GraphicPack2::m_fs_priority
LEGACY_VERSION = 2              # GP_LEGACY_VERSION: packs up to it are not loaded
MODULE = 0x6267BFD0             # moduleMatches of the v208 executable, in every version
PATCH_LINE = re.compile(r"^\s*(0x[0-9a-fA-F]+)\s*=", re.MULTILINE)


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


def uncommented(line: str) -> str:
    """`line` without its comment: from a # or ; outside quotes (IniParser)."""
    quoted = False
    for i, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char in "#;" and not quoted:
            return line[:i]
    return line


def definition(rules: Path) -> dict[str, str] | None:
    """The options of the [Definition] section, names in lower case, or None
    when Cemu would not load the pack (no such first section, no or an
    outdated version)."""
    section, options = None, {}
    for raw in rules.read_text(encoding="utf-8", errors="replace").splitlines():
        line = uncommented(raw).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            if section is not None:
                break
            section = line[1:-1].strip()
            if section.lower() != "definition":
                return None
            continue
        if section is None or "=" not in line:
            continue
        key, value = line.split("=", 1)
        options.setdefault(key.strip().lower(), value.strip().strip('"'))
    try:
        if int(options.get("version", "")) <= LEGACY_VERSION:
            return None
    except ValueError:
        return None
    return options


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


def patched_addresses(folder: Path, module: int = MODULE) -> frozenset[int]:
    """The addresses the patch_*.asm of `folder` write, in their sections for
    `module` (moduleMatches)."""
    found = set()
    for path in sorted(folder.glob("patch_*.asm")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for section in re.split(r"^\s*\[[^\]\n]*\]\s*$", text, flags=re.MULTILINE)[1:]:
            matches = re.search(r"^\s*moduleMatches\s*=\s*([^\n;#]+)", section, re.MULTILINE)
            if not matches:
                continue
            modules = {int(value.strip(), 16) for value in matches.group(1).split(",") if value.strip()}
            if module not in modules:
                continue
            body = "\n".join(uncommented(line) for line in section.splitlines())
            found |= {int(value, 16) for value in PATCH_LINE.findall(body)}
    return frozenset(found)


def enabled(user_data: Path, title: str) -> list[PlayerPack]:
    """The graphic packs Cemu runs for `title` (the game's eight-digit low title
    id, 101c9400), in the order it activates them."""
    root = user_data / FOLDER
    title_id = int("00050000" + title, 16)
    entries = settings_entries(user_data / "settings.xml")
    packs = []
    for folder in pack_folders(root):
        options = definition(folder / "rules.txt")
        if options is None:
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
        if disabled:
            continue
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
            code=(folder / "code").is_dir(), patched=patched_addresses(folder)))
    return packs


def report(packs: list[PlayerPack], ours: dict | None = None) -> list[str]:
    """What the player's packs are, and what they share with a seed pack
    (`ours`: its files, relative to the pack, and the addresses its patches
    write), as lines to show."""
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
        if ours is None:
            continue
        replaced = {f"content/{name}" for name in pack.content} | {f"aoc/{name}" for name in pack.aoc}
        shared = sorted(replaced & set(ours["files"]))
        if shared:
            lines.append(f"      replaces {len(shared)} file(s) the Archipelago pack changes: "
                         + ", ".join(shared[:6]) + (" ..." if len(shared) > 6 else ""))
        taken = sorted(pack.patched & ours["patched"])
        if taken:
            lines.append("      patches the same code as the Archipelago pack: "
                         + ", ".join(f"0x{address:08X}" for address in taken[:6])
                         + (" ..." if len(taken) > 6 else ""))
        if pack.code:
            lines.append("      replaces the game's executable files (code/)")
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
    print("\n".join(report(enabled(user_data, cemu_profile.region().title),
                           seed_pack(arguments.pack) if arguments.pack else None)))
