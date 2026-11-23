"""The tk window (botw_launcher/tk): it loads in a Python of its own, the
guides read as on GitHub, and the log reaches its page once."""
from __future__ import annotations

from pathlib import Path
import logging
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.tk_support import hidden_root, require_tkinter  # noqa: E402

require_tkinter()

from botw_launcher.core import guides  # noqa: E402
from botw_launcher.tk import events, theme  # noqa: E402
from botw_launcher.tk.context import Records  # noqa: E402
from botw_launcher.tk.markdown_view import LINK, MarkdownView  # noqa: E402


class ImportTests(unittest.TestCase):
    def test_the_window_and_its_jobs_load_in_a_python_of_their_own(self):
        code = "import botw_launcher.tk.app, botw_launcher.tk.child, botw_launcher.jobs"
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class GuideTests(unittest.TestCase):
    def setUp(self):
        self.root = hidden_root()
        theme.apply(self.root)
        self.followed: list[str] = []
        self.view = MarkdownView(self.root, self.followed.append)

    def tearDown(self):
        self.root.destroy()

    def show(self, text: str) -> str:
        self.view.show(text, ROOT)
        return self.view.text.get("1.0", "end")

    def test_marks_are_gone_and_headings_are_anchors(self):
        shown = self.show("# The guide\n\nSome **bold**, `code`, *italic* and a [link](other.md#a-heading).\n\n"
                          "## Shops and stalls!\n")
        self.assertNotIn("**", shown)
        self.assertNotIn("`", shown)
        self.assertIn("a link.", shown)
        self.assertTrue(self.view.scroll_to("shops-and-stalls"))
        self.assertTrue(self.view.scroll_to("the-guide"))

    def test_a_link_clicked_gives_its_url(self):
        self.show("See [the hosting page](hosting_en.md#a-room).")
        link = next(tag for tag in self.view.text.tag_names() if tag.startswith("link-"))
        start = self.view.text.tag_ranges(link)[0]
        self.view.pack()
        self.root.deiconify()
        self.root.update()
        x, y, *_ = self.view.text.bbox(start)
        # The pointer first: a tag's binding follows the character under it.
        self.view.text.event_generate("<Motion>", x=x + 1, y=y + 1)
        self.view.text.event_generate("<Button-1>", x=x + 1, y=y + 1)
        self.assertEqual(self.followed, ["hosting_en.md#a-room"])

    def test_lists_tables_and_task_boxes(self):
        shown = self.show("- [ ] To do\n- [x] Done\n  - nested\n\n| Name | Count |\n|---|---:|\n"
                          "| **Shrines** | 120 |\n")
        self.assertIn("☐\tTo do", shown)
        self.assertIn("☑\tDone", shown)
        self.assertIn("•\tnested", shown)
        self.assertIn("Name     Count", shown)
        self.assertIn("Shrines  120", shown)
        self.assertNotIn("---", shown)

    def test_every_guide_link_to_a_heading_finds_it(self):
        anchors = {}
        for guide in guides.guides():
            self.view.show(guides.text(guide), guide.parent)
            anchors[guide.resolve()] = {mark[1:] for mark in self.view.text.mark_names() if mark.startswith("#")}
        for guide in guides.guides():
            for _label, url in LINK.findall(guides.text(guide)):
                path, _, heading = url.partition("#")
                if heading and "://" not in url:
                    target = (guide.parent / unquote(path)).resolve() if path else guide.resolve()
                    self.assertIn(heading, anchors.get(target, set()), f"{guide.name}: {url}")

    def test_a_missing_image_is_left_out(self):
        self.assertEqual(self.show("Before ![A picture](nowhere/picture.jpg) after.").strip(), "Before  after.")

    def test_the_navigation_line_and_alerts(self):
        with tempfile.TemporaryDirectory() as folder:
            guide = Path(folder) / "guide.md"
            guide.write_bytes("# Guide\n\n**Setup** · [In the game](ingame_en.md) · [Options](o.md)\n\n"
                              "> [!TIP]\n> Read this.\n".encode())
            text = guides.text(guide)
        self.assertNotIn("In the game", text)
        self.assertIn("> **Tip**", text)


class EventsTests(unittest.TestCase):
    def test_a_background_failure_reaches_the_window(self):
        failures = []

        def fail():
            raise OSError("no network")
        root = hidden_root()
        try:
            events.background(fail, failed=failures.append)
            for _ in range(200):
                events.pump(root)
                root.update()
                if failures:
                    break
                time.sleep(0.01)
        finally:
            for pending in root.tk.call("after", "info"):
                root.after_cancel(pending)
            root.destroy()
        self.assertEqual([str(error) for error in failures], ["no network"])


class RecordsTests(unittest.TestCase):
    def test_a_line_logged_before_the_page_is_shown_once(self):
        records = Records()
        shown: list[str] = []
        records.added.connect(lambda _level, line: shown.append(line))
        records.handle(logging.LogRecord("botw_launcher", logging.INFO, __file__, 1, "started", (), None))
        shown.extend(line for _level, line in records.kept)     # a page filled now, before the window's loop runs
        root = hidden_root()
        try:
            events.pump(root)
        finally:
            root.destroy()
        self.assertEqual(len([line for line in shown if line.endswith("started")]), 1)


if __name__ == "__main__":
    unittest.main()


class OpenerTests(unittest.TestCase):
    """Off Windows, folders and pages open with xdg-open, without the library
    path of Archipelago's AppImage, which would break the system's programs."""

    def test_a_folder_or_a_page_opens_without_the_appimage_s_libraries(self):
        from unittest import mock
        from botw_launcher.tk import widgets
        with mock.patch.object(widgets.sys, "platform", "linux"), \
                mock.patch.dict(widgets.os.environ, {"LD_LIBRARY_PATH": "/tmp/.mount_AP/lib"}), \
                mock.patch.object(widgets.subprocess, "Popen") as popen, \
                mock.patch.object(widgets.webbrowser, "open") as browser:
            widgets.open_folder(Path("/home/player/data"))
            widgets.open_link("https://archipelago.gg")
        self.assertEqual([call.args[0] for call in popen.call_args_list],
                         [["xdg-open", str(Path("/home/player/data"))], ["xdg-open", "https://archipelago.gg"]])
        for call in popen.call_args_list:
            self.assertNotIn("LD_LIBRARY_PATH", call.kwargs["env"])
        browser.assert_not_called()

    def test_without_xdg_open_a_page_still_opens_and_a_folder_is_logged(self):
        from unittest import mock
        from botw_launcher.tk import widgets
        with mock.patch.object(widgets.sys, "platform", "linux"), \
                mock.patch.object(widgets.subprocess, "Popen", side_effect=FileNotFoundError("xdg-open")), \
                mock.patch.object(widgets.webbrowser, "open") as browser, \
                self.assertLogs(widgets.logger, logging.WARNING):
            widgets.open_folder(Path("/home/player/data"))
            widgets.open_link("https://archipelago.gg")
        browser.assert_called_once_with("https://archipelago.gg")
