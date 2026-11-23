"""A seed added from its room's link (botw_launcher/core/room_link.py), and the
hints the window keeps (botw_launcher/tk/pages/hints.py): without a window."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from botw_launcher.core import output, room_link
from tests.tk_support import require_tkinter

# A room's page as archipelago.gg renders it (WebHostLib/templates/macros.html list_patches_room).
PAGE = """<html><body><table id="patches-table"><thead><tr><th>Id</th><th>Name</th><th>Game</th>
<th>Download Link</th><th>Tracker Page</th></tr></thead><tbody>
<tr>
  <td>1</td>
  <td data-tooltip="Connect via Game Client"><a href="archipelago://Link:None@archipelago.gg:38281?game=Breath of the Wild&room=AbCdEfGhIjKlMnOpQrStUv">Link</a></td>
  <td>Breath of the Wild</td>
  <td><a href="/dl_patch/AbCdEfGhIjKlMnOpQrStUv/41" download>Download Patch File...</a></td>
  <td><a href="/tracker/x/0/1">Tracker</a></td>
</tr>
<tr>
  <td>2</td>
  <td data-tooltip="Connect via Game Client"><a href="archipelago://Mireille &amp; co:None@archipelago.gg:38281?game=A Link to the Past&room=AbCdEfGhIjKlMnOpQrStUv">Mireille &amp; co</a></td>
  <td>A Link to the Past</td>
  <td><a href="/dl_patch/AbCdEfGhIjKlMnOpQrStUv/42" download>Download Patch File...</a></td>
  <td><a href="/tracker/x/0/2">Tracker</a></td>
</tr>
<tr>
  <td>3</td>
  <td><a href="archipelago://Zelda:None@archipelago.gg:38281?game=Breath of the Wild&room=x">Zelda</a></td>
  <td>Breath of the Wild</td>
  <td><a href="/dl_patch/AbCdEfGhIjKlMnOpQrStUv/43" download>Download Patch File...</a></td>
  <td></td>
</tr>
<tr><td>4</td><td><a href="archipelago://Bob:None@archipelago.gg:38281?game=Clique">Bob</a></td>
  <td>Clique</td><td>No file to download for this game.</td><td></td></tr>
</tbody></table></body></html>"""
URL = "https://archipelago.gg/room/AbCdEfGhIjKlMnOpQrStUv"


class RoomLinkTests(unittest.TestCase):
    def test_the_link_of_a_rooms_page_is_taken_as_pasted(self):
        for link in (URL, URL + "/", "archipelago.gg/room/AbCdEfGhIjKlMnOpQrStUv", f"  {URL}  "):
            self.assertEqual(room_link.page_url(link), URL)
        for wrong in ("archipelago.gg:38281", "https://archipelago.gg/seed/AbCdEfGhIjKl",
                      "ftp://archipelago.gg/room/AbCdEfGhIjKl", "https:///room/AbCdEfGhIjKl", ""):
            with self.assertRaises(ValueError):
                room_link.page_url(wrong)

    def test_the_players_with_a_slot_file_are_read_from_the_page(self):
        found = room_link.slots(PAGE, URL)
        self.assertEqual([(slot.number, slot.player, slot.game) for slot in found],
                         [(1, "Link", "Breath of the Wild"), (2, "Mireille & co", "A Link to the Past"),
                          (3, "Zelda", "Breath of the Wild")])
        self.assertEqual(found[0].address, "archipelago.gg:38281")
        self.assertEqual(found[0].download, "https://archipelago.gg/dl_patch/AbCdEfGhIjKlMnOpQrStUv/41")
        self.assertEqual([slot.player for slot in room_link.ours(found)], ["Link", "Zelda"])

    def test_a_page_without_this_game_or_without_files_is_refused_with_why(self):
        def page(text):
            return lambda _url, _limit: text.encode()
        with self.assertRaisesRegex(ValueError, "No slot file"):
            room_link.room_slots(URL, page("<html>Not found</html>"))
        other = PAGE.replace("Breath of the Wild", "Hollow Knight")
        with self.assertRaisesRegex(ValueError, "No Breath of the Wild player"):
            room_link.room_slots(URL, page(other))

        def unreachable(_url, _limit):
            raise OSError("HTTP Error 404")
        with self.assertRaisesRegex(ValueError, "did not open"):
            room_link.room_slots(URL, unreachable)

    def test_the_slot_file_is_saved_under_a_safe_name(self):
        slot = room_link.room_slots(URL, lambda _url, _limit: PAGE.encode())[0]
        asked = []

        def fetch(url, limit):
            asked.append((url, limit))
            return b"slot file"
        with tempfile.TemporaryDirectory() as folder:
            path = room_link.download(slot, Path(folder) / "downloads", fetch)
            self.assertEqual(path.name, "P1_Link_AbCdEfGhIjKlMnOpQrStUv.apbotw")
            self.assertEqual(path.read_bytes(), b"slot file")
            self.assertEqual(asked, [(slot.download, room_link.FILE_LIMIT)])
            odd = room_link.Slot(2, "../a:b*?", room_link.GAME, "", "https://h/dl_patch/R00m/7")
            self.assertEqual(room_link.download(odd, Path(folder), fetch).name, "P2_.._a_b___R00m.apbotw")

    def test_a_fetch_bigger_than_its_limit_is_refused(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.side_effect = lambda size: b"x" * size
        with mock.patch("urllib.request.urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "more than expected"):
                room_link.fetch(URL, 10)


class SessionOutputTests(unittest.TestCase):
    def test_a_lines_time_is_taken_off(self):
        self.assertEqual(output.untimed("12:34:56 Player sent Hookshot"), "Player sent Hookshot")
        self.assertEqual(output.untimed("Player sent Hookshot"), "Player sent Hookshot")

    def test_the_play_job_gives_the_client_an_observer_for_its_session_only(self):
        from botw_launcher import jobs
        from tools import play_session
        seen = []

        def main(_arguments):
            play_session.OBSERVER({"event": "hints", "hints": []})
        with mock.patch.object(play_session, "main", main), \
                mock.patch.object(jobs, "emit", lambda event, **fields: seen.append((event, fields))), \
                mock.patch("botw_launcher.core.seeds.refresh"), mock.patch("tools.build_poptracker.ensure_pack"), \
                mock.patch("botw_launcher.core.seeds.newer_world", return_value=None), \
                mock.patch("botw_launcher.logs.last_session", return_value=None), \
                mock.patch("botw_launcher.core.seeds.folder_of", return_value=Path(".")):
            jobs.JOBS["play"](seed="s")
        self.assertIn(("hints", {"hints": []}), seen)
        self.assertIsNone(play_session.OBSERVER)


class HintsFileTests(unittest.TestCase):
    def test_the_last_hints_are_kept_in_the_seeds_folder(self):
        require_tkinter()
        from botw_launcher.tk.pages import hints
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(hints.load(Path(folder)), [])
            kept = [{"item": "Paraglider", "found": False}]
            hints.save(Path(folder), kept)
            self.assertEqual(hints.load(Path(folder)), kept)
            (Path(folder) / hints.FILE).write_text(json.dumps({"not": "a list"}), encoding="utf-8")
            self.assertEqual(hints.load(Path(folder)), [])

    def test_names_are_offered_from_the_world(self):
        require_tkinter()
        from botw_launcher.tk.pages import hints
        items, locations = hints.names()
        self.assertIn("Paraglider", items)
        self.assertIn("Defeat Calamity Ganon", locations)
        self.assertEqual(items, sorted(set(items)))


if __name__ == "__main__":
    unittest.main()
