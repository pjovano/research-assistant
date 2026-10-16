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

FONT = "helv"
FONT_SIZE = 10.0
LEFT = 72.0
FIRST_BASELINE = 100.0
LINE_PITCH = 30.0
BAND_ABOVE = 12.0
BAND_BELOW = 4.0
PAGE_WIDTH = 612.0
PAGE_HEIGHT = 792.0
NARROW_WORD_GAP = -115
LETTER_SPACING = -100
TIGHT_WORDS = ["views.", "So", "then", "consider", "very", "carefully"]
KERNED_WORD = ("Of", "fice")
LETTER_SPACED_WORD = "LETTERS"
TRACKED_WORD = ("Mr. ", "Locke", " wrote")
EN_DASH = "\\226"
RANGES = [("105", "159, "), ("139", "150, "), ("57", "83")]
ADDRESS_PARTS = ["www", ".", "math", ".", "ias", ".", "edu"]
SPACED_SHORT_WORDS = [("truth ", "of"), (" holism ", "in"), (" any ", "to"), (" the", "")]


class TightLinesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_font(fontname=FONT)
            self._append_stream(document, page, self._text_objects())
            document.save(self._path)
        return self._path

    @staticmethod
    def _text_objects() -> bytes:
        shown = [_shown(TIGHT_WORDS, NARROW_WORD_GAP), _shown(list(KERNED_WORD), NARROW_WORD_GAP),
                 _shown(list(LETTER_SPACED_WORD), LETTER_SPACING), _tracked_in_prose(), _ranges(),
                 _shown(ADDRESS_PARTS, NARROW_WORD_GAP), _short_words_spaced()]
        objects = [f"BT /{FONT} {FONT_SIZE} Tf {LEFT} {baseline_of(row)} Td {line} ET"
                   for row, line in enumerate(shown)]
        return "\n".join(objects).encode("latin-1")

    @staticmethod
    def _append_stream(document, page, stream: bytes) -> None:
        xref = document.get_new_xref()
        document.update_object(xref, "<<>>")
        document.update_stream(xref, stream)
        references = " ".join(f"{content} 0 R" for content in [*page.get_contents(), xref])
        document.xref_set_key(page.xref, "Contents", f"[{references}]")


def _shown(pieces: list[str], displacement: int) -> str:
    return "[" + f" {displacement} ".join(f"({piece})" for piece in pieces) + "] TJ"


def _tracked_in_prose() -> str:
    before, tracked, after = TRACKED_WORD
    return f"[({before}) " + f" {LETTER_SPACING} ".join(f"({letter})" for letter in tracked) + f" ({after})] TJ"


def _ranges() -> str:
    pieces = [piece for first, last in RANGES for piece in (first, EN_DASH, last)]
    return _shown(pieces, NARROW_WORD_GAP)


def _short_words_spaced() -> str:
    pieces = [f"({prose}) " + f" {LETTER_SPACING} ".join(f"({letter})" for letter in spaced)
              for prose, spaced in SPACED_SHORT_WORDS]
    return "[" + " ".join(pieces) + "] TJ"


def baseline_of(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


class _UnhyphenatedJoins:
    @staticmethod
    def keeps_hyphen(_text: str, _line: str) -> bool:
        return True


class TestWordSpacesATightLineSetsAsNarrowGapsWithoutBlanks(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.layer = TextLayer(TightLinesPdf(Path(directory.name) / "tight.pdf").write())
        self.addCleanup(self.layer.close)

    def line_html(self, row: int) -> str:
        baseline_from_top = PAGE_HEIGHT - baseline_of(row)
        band = Box(0.0, baseline_from_top - BAND_ABOVE, PAGE_WIDTH, baseline_from_top + BAND_BELOW)
        return BlockHtml(_UnhyphenatedJoins()).of(rows_of(self.layer.chars_in(1, band)))

    def test_equal_gaps_narrower_than_a_word_gap_recurring_along_a_line_open_its_words(self) -> None:
        self.assertEqual(" ".join(TIGHT_WORDS), self.line_html(0))

    def test_one_gap_of_that_width_alone_on_its_line_stays_inside_the_word(self) -> None:
        self.assertEqual("".join(KERNED_WORD), self.line_html(1))

    def test_letters_spaced_evenly_along_a_line_stay_one_word(self) -> None:
        self.assertEqual(LETTER_SPACED_WORD, self.line_html(2))

    def test_a_letter_spaced_word_among_spaced_words_stays_one_word(self) -> None:
        self.assertEqual("".join(TRACKED_WORD), self.line_html(3))

    def test_gaps_beside_the_dashes_of_ranges_open_no_word(self) -> None:
        self.assertEqual("105–159, 139–150, 57–83", self.line_html(4))

    def test_gaps_on_both_sides_of_a_lone_mark_open_no_word(self) -> None:
        self.assertEqual("".join(ADDRESS_PARTS), self.line_html(5))

    def test_short_letter_spaced_words_among_spaced_words_stay_whole(self) -> None:
        self.assertEqual("truth of holism in any to the", self.line_html(6))


if __name__ == "__main__":
    unittest.main()
