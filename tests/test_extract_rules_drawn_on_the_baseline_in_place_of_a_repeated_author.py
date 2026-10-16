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
LINE_PITCH = 12.0
FIRST_BASELINE = 100.0
MARGIN = 43.0
RUN_ON_INDENT = 36.0
RULE_LENGTH = 29.0
RULE_WIDTH = 0.2
UNDERLINE_DROP_SHARE = 0.2
PAGE_WIDTH, PAGE_HEIGHT = 440.0, 660.0
WHOLE_PAGE = Box(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT)
DASH_RUN = "——"
AUTHOR_ENTRY = ('Abel, J. (1963). "Categories with multiplication". In: C. R. Acad. Sci.,',
                "Paris 256, pp. 1887-1890.")
REPEATED_ENTRY = ('(1964). "Elementary algebra in categories with multiplication". In:',
                  "C. R. Acad. Sci., Paris 258, pp. 771-774.")
NEXT_AUTHOR_ENTRY = ('Baker, G. (1929). "On the axioms of elementary geometry". In: Monatsh.',
                     "Math. 36, pp. 269-284.")


class RuledRepeatedAuthorPdf:
    def __init__(self, path: Path, rule_drop: float) -> None:
        self._path = path
        self._rule_drop = rule_drop
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
        rule_y = self._baseline + self._rule_drop
        page.draw_line((MARGIN, rule_y), (MARGIN + RULE_LENGTH, rule_y), width=RULE_WIDTH)
        for line in lines:
            self._line(page, MARGIN + RUN_ON_INDENT, line)

    def _line(self, page, left: float, text: str) -> None:
        page.insert_text((left, self._baseline), text, fontsize=FONT_SIZE, fontname=FONT)
        self._baseline += LINE_PITCH


class _UnhyphenatedJoins:
    @staticmethod
    def keeps_hyphen(_text: str, _line: str) -> bool:
        return True


class TestRulesDrawnOnTheBaselineInPlaceOfARepeatedAuthor(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def entry_htmls(self, rule_drop: float) -> list[str]:
        layer = TextLayer(RuledRepeatedAuthorPdf(self._directory / "entries.pdf", rule_drop).write())
        self.addCleanup(layer.close)
        entries = HangingIndentList(layer).boxed_entries(1, [WHOLE_PAGE])
        html = BlockHtml(_UnhyphenatedJoins())
        return [html.of(rows_of(layer.chars_in(1, entry.bbox))) for entry in entries]

    def test_a_rule_on_the_baseline_opens_the_repeated_authors_entry_with_a_dash_run(self) -> None:
        self.assertEqual(f"{DASH_RUN} {' '.join(REPEATED_ENTRY)}", self.entry_htmls(0.0)[1])

    def test_each_entry_beside_the_ruled_one_stays_whole(self) -> None:
        htmls = self.entry_htmls(0.0)
        self.assertEqual([" ".join(AUTHOR_ENTRY), " ".join(NEXT_AUTHOR_ENTRY)], [htmls[0], htmls[2]])

    def test_a_rule_below_the_baseline_leaves_the_entry_running_on_from_the_one_above(self) -> None:
        htmls = self.entry_htmls(UNDERLINE_DROP_SHARE * FONT_SIZE)
        self.assertEqual(" ".join(AUTHOR_ENTRY + REPEATED_ENTRY), htmls[0])


if __name__ == "__main__":
    unittest.main()
