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

FONT = "helv"
FONT_SIZE = 10.0
LINE_PITCH = 15.0
FIRST_BASELINE = 100.0
MARGIN = 57.0
RUN_ON_INDENT = 9.0
RULED_INDENT = 27.0
RULE_THICKNESS = 0.5
RULE_RISE = 0.25
HAIRLINE_OVERLAP = 0.02
UNDER_THE_GLYPH_OVERLAP = 0.5 * FONT_SIZE
PAGE_WIDTH, PAGE_HEIGHT = 440.0, 660.0
WHOLE_PAGE = Box(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT)
DASH_RUN = "——"
AUTHOR_ENTRY = ("Beck, Lewis White. Studies in the Philosophy of Kant. Indianapolis:",
                "Bobbs-Merrill Company, 1965.")
REPEATED_ENTRY = (". Essays on Kant and Hume. New Haven and London: Yale University",
                  "Press, 1978.")
NEXT_AUTHOR_ENTRY = ("Caird, Edward. The Critical Philosophy of Immanuel Kant. 2 vols. New",
                     "York: Macmillan and Co., 1889.")


class RuleUpToTheGlyphPdf:
    def __init__(self, path: Path, rule_overlap: float) -> None:
        self._path = path
        self._rule_overlap = rule_overlap
        self._baseline = FIRST_BASELINE

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            self._entry(page, AUTHOR_ENTRY)
            self._ruled_entry(page, REPEATED_ENTRY)
            self._entry(page, NEXT_AUTHOR_ENTRY)
            document.save(self._path)
        return self._path

    def _entry(self, page, lines: tuple[str, str]) -> None:
        opening, run_on = lines
        self._line(page, MARGIN, opening)
        self._line(page, MARGIN + RUN_ON_INDENT, run_on)

    def _ruled_entry(self, page, lines: tuple[str, str]) -> None:
        opening, run_on = lines
        rule_middle = self._baseline - RULE_RISE
        rule_end = MARGIN + RULED_INDENT + self._rule_overlap
        rule = pymupdf.Rect(MARGIN, rule_middle - RULE_THICKNESS / 2, rule_end, rule_middle + RULE_THICKNESS / 2)
        page.draw_rect(rule, color=None, fill=(0, 0, 0))
        self._line(page, MARGIN + RULED_INDENT, opening)
        self._line(page, MARGIN + RUN_ON_INDENT, run_on)

    def _line(self, page, left: float, text: str) -> None:
        page.insert_text((left, self._baseline), text, fontsize=FONT_SIZE, fontname=FONT)
        self._baseline += LINE_PITCH


class _UnhyphenatedJoins:
    @staticmethod
    def keeps_hyphen(_text: str, _line: str) -> bool:
        return True


class TestRulesDrawnUpToTheGlyphAfterThemInPlaceOfARepeatedAuthor(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def entry_htmls(self, rule_overlap: float) -> list[str]:
        layer = TextLayer(RuleUpToTheGlyphPdf(self._directory / "entries.pdf", rule_overlap).write())
        self.addCleanup(layer.close)
        entries = HangingIndentList(layer).boxed_entries(1, [WHOLE_PAGE])
        html = BlockHtml(_UnhyphenatedJoins())
        return [html.of(rows_of(layer.chars_in(1, entry.bbox))) for entry in entries]

    def test_a_rule_reaching_a_hairline_into_the_glyph_after_it_opens_its_own_entry_with_a_dash_run(self) -> None:
        self.assertEqual(f"{DASH_RUN}{' '.join(REPEATED_ENTRY)}", self.entry_htmls(HAIRLINE_OVERLAP)[1])

    def test_each_entry_beside_the_rule_reaching_into_the_glyph_stays_whole(self) -> None:
        htmls = self.entry_htmls(HAIRLINE_OVERLAP)
        self.assertEqual([" ".join(AUTHOR_ENTRY), " ".join(NEXT_AUTHOR_ENTRY)], [htmls[0], htmls[2]])

    def test_a_rule_running_under_the_glyph_after_it_leaves_the_entry_running_on_from_the_one_above(self) -> None:
        htmls = self.entry_htmls(UNDER_THE_GLYPH_OVERLAP)
        self.assertEqual(" ".join(AUTHOR_ENTRY + REPEATED_ENTRY), htmls[0])


if __name__ == "__main__":
    unittest.main()
