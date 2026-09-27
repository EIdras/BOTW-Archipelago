"""Check a Cemu patch file the way Cemu's assembler will read it, before Cemu.

Cemu refused the first message pack with "Label apMessageText is already
defined" (a data label and a hook label of the same name); the project's PPC
model had silently kept the second. This lint reads every patch group of a
.asm file and reports, per group:
  * labels defined twice;
  * labels used (branch targets, @ha/@l halves, .int words, `addr = b label`)
    but defined nowhere in the group.
It does not assemble instructions; it only checks the names Cemu resolves.

    python -m tools.patch_lint <pack or .asm> ...
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

LABEL = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):$")
NAME = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)(?:@ha|@h|@l)?\b")
BRANCHES = {"b", "bl", "ba", "bla", "beq", "bne", "blt", "bgt", "ble", "bge", "bdnz", "bdz",
            "beq+", "bne+", "beq-", "bne-", "bso", "bns"}
# Words that may appear where a label could: registers, directives, symbols
# defined by Cemu's patch syntax.
RESERVED = {"codecave"}


def groups(text: str) -> list[tuple[str, list[tuple[int, str]]]]:
    out, current = [], None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = (line[1:-1], [])
            out.append(current)
        elif current is not None:
            current[1].append((number, line))
    return out


def used_names(line: str) -> list[str]:
    """Label names this line refers to (empty for plain instructions on registers)."""
    if "=" in line:
        left, right = (part.strip() for part in line.split("=", 1))
        if left in ("moduleMatches", ".origin") or left.startswith("."):
            return []
        line = right                                  # "0xADDR = b label"
    parts = line.replace(",", " ").split()
    if not parts:
        return []
    op, args = parts[0], parts[1:]
    names = []
    if op == ".int":
        names = [a for a in args if not re.fullmatch(r"-?(0x[0-9A-Fa-f]+|\d+)", a)]
    elif op in BRANCHES:
        names = [a for a in args[-1:] if not a.startswith(("0x", "cr")) and not a.isdigit()]
    for arg in args:
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)@(ha|h|l)", arg)
        if match:
            names.append(match.group(1))
    return [n for n in names if n not in RESERVED and not re.fullmatch(r"r\d+|cr\d", n)]


def lint(text: str) -> list[str]:
    problems = []
    for group, lines in groups(text):
        defined: dict[str, int] = {}
        for number, line in lines:
            match = LABEL.match(line)
            if match:
                name = match.group(1)
                if name in defined:
                    problems.append(f"[{group}] ligne {number} : étiquette {name} déjà "
                                    f"définie ligne {defined[name]}")
                defined.setdefault(name, number)
        for number, line in lines:
            if LABEL.match(line):
                continue
            for name in used_names(line):
                if name not in defined:
                    problems.append(f"[{group}] ligne {number} : étiquette {name} non définie")
    return problems


def files(target: Path) -> list[Path]:
    return sorted(target.glob("*.asm")) if target.is_dir() else [target]


def main(argv: list[str]) -> int:
    status = 0
    for arg in argv:
        for path in files(Path(arg)):
            problems = lint(path.read_text(encoding="utf-8"))
            print(f"{path.name}: {'OK' if not problems else f'{len(problems)} problème(s)'}")
            for problem in problems[:20]:
                print("  " + problem)
            status |= bool(problems)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
