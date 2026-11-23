"""The player's guides (botw_world/docs), as the Help page of either window
lists and reads them.

They are written for GitHub: here their navigation line is dropped (the list
beside replaces it) and GitHub's alerts become a bold word.
"""
from __future__ import annotations

from pathlib import Path
import re

from botw_client.paths import ROOT

GUIDES = ROOT / "botw_world" / "docs"
# The guides as their own navigation line names them, in its order; a guide
# not listed comes after, under its first heading.
NAMES = {"setup_en.md": "Setup", "ingame_en.md": "In the game", "en_Breath of the Wild.md": "Options",
         "hosting_en.md": "Hosting", "poptracker_en.md": "Trackers", "mods_en.md": "Mods",
         "troubleshooting_en.md": "Troubleshooting", "setup_fr.md": "Installation (français)",
         "names_fr.md": "Noms en français"}
ORDER = tuple(NAMES)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
ALERT = re.compile(r"^>[ \t]*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*$", re.MULTILINE)
NAVIGATION_ITEM = re.compile(r"\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\.md\)")
WEB = ("http", "https", "mailto")


def guides(folder: Path = GUIDES) -> list[Path]:
    found = sorted(folder.glob("*.md")) if folder.is_dir() else []
    return sorted(found, key=lambda path: ORDER.index(path.name) if path.name in ORDER else len(ORDER))


def title(guide: Path) -> str:
    """A guide's name in the list: its first heading when it has no short one."""
    if guide.name in NAMES:
        return NAMES[guide.name]
    for line in guide.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return guide.stem


def anchor(heading: str) -> str:
    """The anchor GitHub gives a heading: `#the-sealed-sanctum`."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def navigation(paragraph: str) -> bool:
    """The guides' navigation line, which the list beside replaces."""
    items = [item.strip() for item in paragraph.replace("\n", " ").split("·")]
    return len(items) > 2 and all(NAVIGATION_ITEM.fullmatch(item) for item in items if item)


def text(guide: Path) -> str:
    """A guide's text without its navigation line, GitHub's alerts as a bold word."""
    content = guide.read_text(encoding="utf-8")
    content = "\n\n".join(paragraph for paragraph in content.split("\n\n") if not navigation(paragraph))
    return ALERT.sub(lambda match: f"> **{match[1].title()}**", content)
