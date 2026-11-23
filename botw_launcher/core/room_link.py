"""A seed added from its room's link, as the room's page shows it in the
browser: https://archipelago.gg/room/<id>.

That page lists each player with their game, the room's address (in the
archipelago:// link on their name) and their slot file ("Download Patch File",
/dl_patch/...). Opening it also wakes a room that was asleep. The API's
room_status is not used: for this game its download points at /slot_file/,
which only serves the files of the games Archipelago knows.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Callable
import urllib.parse
import urllib.request

from tools.play_seed import GAME

from . import updates

PAGE_LIMIT = 4 << 20        # bytes: a room's page is far smaller
FILE_LIMIT = 64 << 20       # a slot file holds a manifest, a few hundred kB
TIMEOUT = 30
_ROOM_PATH = re.compile(r"^/room/([A-Za-z0-9_-]{8,40})/?$")
_ADDRESS = re.compile(r"^archipelago://[^@]*@([^/?#]+)")
_UNSAFE = re.compile(r"[^A-Za-z0-9 _.()-]")

Fetch = Callable[[str, int], bytes]


@dataclass(frozen=True)
class Slot:
    number: int
    player: str
    game: str
    address: str        # the room's, archipelago.gg:12345 ("" when the page has none)
    download: str       # the slot file's URL


def page_url(link: str) -> str:
    """The room page of a link the player pasted; ValueError when it is not one."""
    text = link.strip()
    if "://" not in text:
        text = "https://" + text
    parts = urllib.parse.urlsplit(text)
    room = _ROOM_PATH.match(parts.path)
    if parts.scheme not in ("http", "https") or not parts.hostname or room is None:
        raise ValueError("Not a room's link. Paste it as your browser shows the room's page: "
                         "https://archipelago.gg/room/...")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, f"/room/{room[1]}", "", ""))


def fetch(url: str, limit: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "BOTW-Archipelago-launcher"})
    with urllib.request.urlopen(request, timeout=TIMEOUT, context=updates._context()) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{url} sent more than expected: not a room's page or slot file.")
    return data


class _Rows(HTMLParser):
    """The table's rows: each cell's text and links."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[tuple[str, list[str]]]] = []
        self._cell: list | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.rows.append([])
            self._cell = None
        elif tag == "td" and self.rows:
            self._cell = ["", []]
            self.rows[-1].append(self._cell)
        elif tag == "a" and self._cell is not None:
            self._cell[1].append(dict(attrs).get("href") or "")

    def handle_endtag(self, tag):
        if tag in ("td", "tr"):
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell[0] += data


def slots(page: str, url: str) -> list[Slot]:
    """Every player of the room's page that has a slot file to download."""
    reader = _Rows()
    reader.feed(page)
    found = []
    for row in reader.rows:
        if len(row) < 4 or not row[0][0].strip().isdigit():
            continue
        links = [href for _text, hrefs in row for href in hrefs]
        download = next((href for href in links if "/dl_patch/" in href), None)
        if download is None:
            continue
        address = next((match[1] for href in links if (match := _ADDRESS.match(href))), "")
        found.append(Slot(int(row[0][0].strip()), row[1][0].strip(), row[2][0].strip(),
                          "" if address.endswith(":None") else address, urllib.parse.urljoin(url, download)))
    return found


def ours(found: list[Slot]) -> list[Slot]:
    return [slot for slot in found if slot.game == GAME]


def room_slots(link: str, fetch: Fetch = fetch) -> list[Slot]:
    """The Breath of the Wild players of the room at `link`; ValueError with
    what the player can do when there is none."""
    url = page_url(link)
    try:
        page = fetch(url, PAGE_LIMIT).decode("utf-8", "replace")
    except OSError as exc:
        raise ValueError(f"The room's page did not open: {exc}. Check the link, and that the room "
                         "still exists (a room is removed after a long time unused).") from exc
    found = slots(page, url)
    if not found:
        raise ValueError("No slot file on this page: is it the room's page? Its link starts with "
                         "https://archipelago.gg/room/")
    botw = ours(found)
    if not botw:
        raise ValueError(f"No {GAME} player in this room.")
    return botw


def download(slot: Slot, folder: Path, fetch: Fetch = fetch) -> Path:
    """The slot file of `slot`, saved in `folder` under the name the room's page gives it."""
    data = fetch(slot.download, FILE_LIMIT)
    room = slot.download.rstrip("/").split("/")[-2]
    name = _UNSAFE.sub("_", f"P{slot.number}_{slot.player}_{room}")[:120] + ".apbotw"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    partial = path.with_suffix(".partial")
    partial.write_bytes(data)
    partial.replace(path)
    return path
