from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.layerlines import rows_of
from _extract.lists import HangingIndentList

FONT = "cour"
FONT_SIZE = 9.0
ADVANCE = pymupdf.get_text_length("x", FONT, FONT_SIZE)
LINE_PITCH = 11.0
FIRST_BASELINE = 100.0
MARGIN = 63.0
FIRST_LINE_INDENT_CHARS = 2
RULE_CHARS = 5
RULE_THICKNESS = 0.48
RULE_RISE_SHARE = 0.35
UNDERLINE_DROP = 1.5
WHOLE_PAGE = Box(0.0, 0.0, 480.0, 660.0)
DASH_RUN = "——"
FIRST_ENTRY = ("[1] A. Author, The first title of a list, Journal of Works,",
               "vol. 1 (1990), pp. 1-20.")
PATH_RULED_ENTRY = ("[2]", ", The second title, set just after a rule drawn as",
                    "a path, Journal of Works, vol. 2 (1991), pp. 21-40.")
IMAGE_RULED_ENTRY = ("[3]", ", The third title, set just past a rule painted as",
                     "an image, Journal of Works, vol. 3 (1992), pp. 41-60.")
UNDERLINED_ENTRY = ("[4] B. Writer, The fourth title, whose first word is ruled,",
                    "Journal of Works, vol. 4 (1993), pp. 61-80.")


class RepeatedAuthorListPdf:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._baseline = FIRST_BASELINE

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            self._entry(page, FIRST_ENTRY)
            self._ruled_entry(page, PATH_RULED_ENTRY, self._draw_path)
            self._ruled_entry(page, IMAGE_RULED_ENTRY, self._paint_image)
            self._underlined_entry(page, UNDERLINED_ENTRY)
            document.save(self._path)
        return self._path

    def _entry(self, page, lines: tuple[str, str]) -> None:
        opening, run_on = lines
        self._line(page, self._opening_left(), opening)
        self._line(page, MARGIN, run_on)

    def _ruled_entry(self, page, entry: tuple[str, str, str], rule) -> None:
        number, opening, run_on = entry
        number_left = self._opening_left()
        rule_left = number_left + (len(number) + 1) * ADVANCE
        rule_right = rule_left + RULE_CHARS * ADVANCE
        self._text(page, number_left, number)
        rule(page, pymupdf.Rect(rule_left, self._rule_top(), rule_right, self._rule_top() + RULE_THICKNESS))
        self._line(page, rule_right, opening)
        self._line(page, MARGIN, run_on)

    def _underlined_entry(self, page, lines: tuple[str, str]) -> None:
        opening, _run_on = lines
        underlined_left = self._opening_left() + opening.index("B.") * ADVANCE
        top = self._baseline + UNDERLINE_DROP
        self._draw_path(page, pymupdf.Rect(underlined_left, top, underlined_left + RULE_CHARS * ADVANCE,
                                           top + RULE_THICKNESS))
        self._entry(page, lines)

    def _line(self, page, left: float, text: str) -> None:
        self._text(page, left, text)
        self._baseline += LINE_PITCH

    def _text(self, page, left: float, text: str) -> None:
        page.insert_text((left, self._baseline), text, fontsize=FONT_SIZE, fontname=FONT)

    def _rule_top(self) -> float:
        return self._baseline - RULE_RISE_SHARE * FONT_SIZE - RULE_THICKNESS / 2

    @staticmethod
    def _opening_left() -> float:
        return MARGIN + FIRST_LINE_INDENT_CHARS * ADVANCE

    @staticmethod
    def _draw_path(page, rect: pymupdf.Rect) -> None:
        page.draw_rect(rect, color=None, fill=(0, 0, 0))

    @staticmethod
    def _paint_image(page, rect: pymupdf.Rect) -> None:
        pixel = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 1, 1), False)
        pixel.clear_with(0)
        page.insert_image(rect, pixmap=pixel, keep_proportion=False)


class _UnhyphenatedJoins:
    @staticmethod
    def keeps_hyphen(_text: str, _line: str) -> bool:
        return True


class TestRulesDrawnInPlaceOfARepeatedAuthor(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.layer = TextLayer(RepeatedAuthorListPdf(Path(directory.name) / "entries.pdf").write())
        self.addCleanup(self.layer.close)
        self.entries = HangingIndentList(self.layer).boxed_entries(1, [WHOLE_PAGE])

    def entry_texts(self) -> list[str]:
        return [" ".join(entry.text.split()) for entry in self.entries]

    def entry_html(self, position: int) -> str:
        return BlockHtml(_UnhyphenatedJoins()).of(rows_of(self.layer.chars_in(1, self.entries[position].bbox)))

    def test_an_entry_opening_with_a_rule_is_one_entry_with_its_number(self) -> None:
        self.assertEqual(["[1]", "[2]", "[3]", "[4]"], [text.split()[0] for text in self.entry_texts()])

    def test_a_rule_drawn_as_a_path_reads_as_a_dash_run_in_the_entry(self) -> None:
        self.assertEqual(f"[2] {DASH_RUN}{PATH_RULED_ENTRY[1]} {PATH_RULED_ENTRY[2]}", self.entry_texts()[1])

    def test_a_rule_painted_as_an_image_reads_as_a_dash_run_in_the_entry(self) -> None:
        self.assertEqual(f"[3] {DASH_RUN}{IMAGE_RULED_ENTRY[1]} {IMAGE_RULED_ENTRY[2]}", self.entry_texts()[2])

    def test_the_entry_built_from_the_characters_carries_the_dash_run(self) -> None:
        self.assertTrue(self.entry_html(1).startswith(f"[2] {DASH_RUN}, The second title"))

    def test_a_rule_drawn_under_a_word_does_not_read_as_a_dash(self) -> None:
        self.assertEqual(" ".join(UNDERLINED_ENTRY), self.entry_texts()[3])


if __name__ == "__main__":
    unittest.main()
