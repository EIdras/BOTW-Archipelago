"""A guide's markdown shown in a tk Text: what the guides use of it, no more.

Headings (each leaves a mark named by its GitHub anchor), paragraphs, lists,
quotes, fenced code, tables (aligned columns), and inline code, bold, italic
and links. An image is shown when tk can read it (PNG, GIF), named by its
text when it cannot, and left out when the folder does not hold it.
"""
from __future__ import annotations

from pathlib import Path
import re
import tkinter as tk
from tkinter import font as tkfont, ttk
from typing import Callable
from urllib.parse import unquote

from ..core.guides import anchor
from . import theme

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
FENCE = re.compile(r"^\s*(```|~~~)")
RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
SEPARATOR = re.compile(r"^:?-+:?$")
INLINE = re.compile(r"(?P<code>`[^`]+`)"
                    r"|(?P<image>!\[[^\]]*\]\([^)\s]+\))"
                    r"|(?P<link>\[[^\]]+\]\([^)\s]+\))"
                    r"|(?P<bold>\*\*[^*]+?\*\*|__[^_]+?__)"
                    r"|(?P<italic>(?<![\w*])\*[^*\s][^*]*?\*(?!\w)|(?<!\w)_[^_\s][^_]*?_(?!\w))")
LINK = re.compile(r"!?\[([^\]]*)\]\(([^)\s]+)\)")
READABLE = (".png", ".gif")
INDENT = 22         # pixels per list level


def _plain(text: str) -> str:
    """Inline markdown without its marks: for a table's cells, which are aligned."""
    text = LINK.sub(lambda match: match[1], text)
    return re.sub(r"\*\*|__|`", "", text)


class MarkdownView(tk.Frame):
    def __init__(self, parent: tk.Misc, follow: Callable[[str], None]):
        """`follow(url)`: a link clicked, as written in the guide."""
        super().__init__(parent, bg=theme.SURFACE, highlightthickness=1, highlightbackground=theme.BORDER)
        self.follow = follow
        self.text = tk.Text(self, bg=theme.SURFACE, fg=theme.TEXT, relief="flat", wrap="word", padx=theme.px(22), pady=theme.px(16),
                            highlightthickness=0, borderwidth=0, cursor="arrow", font=theme.FONTS["body"],
                            selectbackground=theme.ACCENT, inactiveselectbackground=theme.ACCENT,
                            spacing1=1, spacing3=1)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.images: list[tk.PhotoImage] = []
        self.base = Path(".")
        self._links = 0
        self._styles()

    def _styles(self) -> None:
        family = theme.FAMILY
        body = tkfont.Font(font=theme.FONTS["body"])
        tags = {
            "h1": {"font": (family, 18, "bold"), "spacing1": 6, "spacing3": 10},
            "h2": {"font": (family, 14, "bold"), "spacing1": 16, "spacing3": 6},
            "h3": {"font": (family, 11, "bold"), "spacing1": 12, "spacing3": 4},
            "p": {"spacing3": 10},
            "gap": {"font": (family, 4)},
            "bold": {"font": (family, body.cget("size"), "bold")},
            "italic": {"font": (family, body.cget("size"), "italic")},
            "code": {"font": theme.FONTS["mono"], "background": theme.FIELD},
            "codeblock": {"font": theme.FONTS["mono"], "background": theme.FIELD, "lmargin1": 12, "lmargin2": 12,
                          "rmargin": 12, "spacing1": 0, "spacing3": 0, "wrap": "none"},
            "table": {"font": theme.FONTS["mono"], "wrap": "none", "spacing1": 2, "spacing3": 2},
            "header": {"font": (theme.FONTS["mono"][0], theme.FONTS["mono"][1], "bold")},
            "quote": {"foreground": theme.MUTED, "lmargin1": 14, "lmargin2": 14},
            "link": {"foreground": theme.ACCENT_HOVER, "underline": True},
            "muted": {"foreground": theme.MUTED},
        }
        for name, options in tags.items():
            self.text.tag_configure(name, **options)
        # Later tags win: a heading's font over bold's, a link's colour over a quote's.
        for name in ("bold", "italic", "h3", "h2", "h1", "code", "link"):
            self.text.tag_raise(name)
        self.text.tag_bind("link", "<Enter>", lambda _e: self.text.configure(cursor="hand2"))
        self.text.tag_bind("link", "<Leave>", lambda _e: self.text.configure(cursor="arrow"))

    # ---- showing a guide ----------------------------------------------------

    def show(self, markdown: str, base: Path) -> None:
        """`base`: the guide's folder, which its links and images are relative to."""
        self.base = base
        self.images.clear()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for mark in self.text.mark_names():
            if mark.startswith("#"):
                self.text.mark_unset(mark)
        for tag in self.text.tag_names():
            if tag.startswith("link-"):
                self.text.tag_delete(tag)
        self._blocks(markdown.splitlines())
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)

    def scroll_to(self, heading: str) -> bool:
        mark = f"#{heading}"
        if mark not in self.text.mark_names():
            return False
        self.text.yview(mark)
        return True

    # ---- blocks -------------------------------------------------------------

    def _blocks(self, lines: list[str]) -> None:
        index = 0
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                index += 1
            elif FENCE.match(line):
                end = index + 1
                while end < len(lines) and not FENCE.match(lines[end]):
                    end += 1
                self._insert("\n".join(lines[index + 1:end]) + "\n", ("codeblock",))
                self._insert("\n", ("gap",))
                index = end + 1
            elif heading := HEADING.match(line):
                level = min(len(heading[1]), 3)
                self.text.mark_set(f"#{anchor(_plain(heading[2]))}", "end-1c")
                self.text.mark_gravity(f"#{anchor(_plain(heading[2]))}", "left")
                self._inline(heading[2], (f"h{level}",))
                self._insert("\n", (f"h{level}",))
                index += 1
            elif RULE.match(line):
                self._insert("\n", ("p",))
                index += 1
            elif line.lstrip().startswith("|"):
                end = index
                while end < len(lines) and lines[end].lstrip().startswith("|"):
                    end += 1
                self._table(lines[index:end])
                index = end
            elif line.lstrip().startswith(">"):
                end = index
                while end < len(lines) and lines[end].lstrip().startswith(">"):
                    end += 1
                quoted = [re.sub(r"^\s*>\s?", "", text) for text in lines[index:end]]
                for paragraph in "\n".join(quoted).split("\n\n"):
                    self._inline(self._joined(paragraph.splitlines()), ("quote",))
                    self._insert("\n", ("quote", "p"))
                index = end
            elif ITEM.match(line):
                index = self._list(lines, index)
            else:
                end = index + 1
                while end < len(lines) and lines[end].strip() and not self._starts_block(lines[end]):
                    end += 1
                self._inline(self._joined(lines[index:end]), ())
                self._insert("\n", ("p",))
                index = end

    @staticmethod
    def _starts_block(line: str) -> bool:
        stripped = line.lstrip()
        return bool(HEADING.match(line) or FENCE.match(line) or ITEM.match(line) or RULE.match(line)
                    or stripped.startswith(("|", ">")))

    @staticmethod
    def _joined(lines: list[str]) -> str:
        """A paragraph's lines as one, a line ended by two spaces or a backslash kept apart."""
        out = ""
        for line in lines:
            hard = line.endswith("  ") or line.endswith("\\")
            line = line.rstrip().rstrip("\\").strip()
            out += line + ("\n" if hard else " ")
        return out.strip()

    def _list(self, lines: list[str], index: int) -> int:
        """The items from `index`, nested by their indent; the index after them."""
        base = len(ITEM.match(lines[index])[1])
        indents: list[int] = []
        while index < len(lines):
            item = ITEM.match(lines[index])
            if not item or len(item[1]) < base:
                if lines[index].strip() and not item and lines[index].startswith(" "):
                    index += 1      # a continuation already taken with its item
                    continue
                break
            indent = len(item[1])
            while indents and indents[-1] > indent:
                indents.pop()
            if not indents or indents[-1] < indent:
                indents.append(indent)
            level = len(indents) - 1
            text = [item[3]]
            end = index + 1
            while (end < len(lines) and lines[end].strip() and not ITEM.match(lines[end])
                   and not self._starts_block(lines[end].strip())):
                text.append(lines[end])
                end += 1
            marker = item[2] if item[2][0].isdigit() else "•"
            task = re.match(r"\[([ xX])\]\s+", text[0])
            if task:        # GitHub's task list: a box, ticked or not
                marker, text[0] = "☐" if task[1] == " " else "☑", text[0][task.end():]
            tag = self._list_tag(level)
            self._insert(f"{marker}\t", (tag,))
            self._inline(self._joined(text), (tag,))
            self._insert("\n", (tag,))
            index = end
            while index < len(lines) and not lines[index].strip():
                following = index + 1
                if following < len(lines) and ITEM.match(lines[following]) and \
                        len(ITEM.match(lines[following])[1]) >= base:
                    index = following
                else:
                    break
        self._insert("\n", ("gap",))
        return index

    def _list_tag(self, level: int) -> str:
        name = f"list{level}"
        if name not in self.text.tag_names():
            left = 4 + level * INDENT
            self.text.tag_configure(name, lmargin1=left, lmargin2=left + INDENT, tabs=(left + INDENT,),
                                    spacing3=3)
        return name

    def _table(self, lines: list[str]) -> None:
        rows = [[_plain(cell.strip()) for cell in line.strip().strip("|").split("|")] for line in lines]
        rows = [row for row in rows if not all(SEPARATOR.match(cell) for cell in row if cell)]
        if not rows:
            return
        columns = max(len(row) for row in rows)
        widths = [max(len(row[column]) if column < len(row) else 0 for row in rows) for column in range(columns)]
        for number, row in enumerate(rows):
            cells = [(row[column] if column < len(row) else "").ljust(widths[column]) for column in range(columns)]
            self._insert("  ".join(cells).rstrip() + "\n", ("table", "header") if number == 0 else ("table",))
        self._insert("\n", ("gap",))

    # ---- inline -------------------------------------------------------------

    def _inline(self, text: str, tags: tuple[str, ...]) -> None:
        position = 0
        for match in INLINE.finditer(text):
            self._insert(text[position:match.start()], tags)
            kind, token = match.lastgroup, match[0]
            if kind == "code":
                self._insert(token[1:-1], tags + ("code",))
            elif kind == "bold":
                self._inline(token[2:-2], tags + ("bold",))
            elif kind == "italic":
                self._inline(token[1:-1], tags + ("italic",))
            elif kind == "link":
                label, url = LINK.match(token).groups()
                self._link(label, url, tags)
            elif kind == "image":
                label, url = LINK.match(token).groups()
                self._image(label, url, tags)
            position = match.end()
        self._insert(text[position:], tags)

    def _link(self, label: str, url: str, tags: tuple[str, ...]) -> None:
        self._links += 1
        tag = f"link-{self._links}"
        self.text.tag_bind(tag, "<Button-1>", lambda _e: self.follow(url))
        self._inline(label, tags + ("link", tag))

    def _image(self, label: str, url: str, tags: tuple[str, ...]) -> None:
        path = (self.base / unquote(url.split("#")[0])).resolve()
        if not path.is_file():
            return
        if path.suffix.lower() in READABLE:
            try:
                image = tk.PhotoImage(file=str(path))
            except tk.TclError:
                image = None
            if image is not None:
                shrink = -(-image.width() // 760)
                if shrink > 1:
                    image = image.subsample(shrink)
                self.images.append(image)
                self.text.image_create("end", image=image)
                return
        self._insert(f"[{label}]", tags + ("muted", "italic"))

    def _insert(self, text: str, tags: tuple[str, ...]) -> None:
        if text:
            self.text.insert("end", text, tags)
