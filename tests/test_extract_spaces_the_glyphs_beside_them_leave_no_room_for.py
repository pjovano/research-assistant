from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.layer import LayerChar, OverlappedSpaces, TextLayer
from _extract.layerhtml import BlockHtml
from _extract.layerlines import rows_of

FONT = "helv"
FONT_SIZE = 12.0
LEFT = 72.0
FIRST_BASELINE = 100.0
LINE_PITCH = 30.0
BAND_ABOVE = 12.0
BAND_BELOW = 4.0
PAGE_WIDTH = 612.0
PAGE_HEIGHT = 792.0
SPACE_WIDTH = 278
E_WIDTH = 667
TIGHT_SPACE_KERN = 150
KERNED_BACK_SPACE_KERN = 248
MARK_KERN_BACK = 600
MARK_KERN_FORWARD = -322
UNDER_THE_NEXT_GLYPH = f"[(som ) {SPACE_WIDTH} (ething whole)] TJ"
INSIDE_THE_WORD_BEFORE = rf"[(E) {E_WIDTH} (\264 ) (ditions whole)] TJ"
SHRUNK_WORD_SPACE = f"[(tight ) {TIGHT_SPACE_KERN} (words)] TJ"
MARK_SET_BACK_INSIDE_THE_WORD = f"[(Ro) {MARK_KERN_BACK} (!) {MARK_KERN_FORWARD} (zsa whole)] TJ"
KERNED_BACK_WORD_SPACE = f"[(itself. ) {KERNED_BACK_SPACE_KERN} (There)] TJ"
SHOWN_LINES = (UNDER_THE_NEXT_GLYPH, INSIDE_THE_WORD_BEFORE, SHRUNK_WORD_SPACE, MARK_SET_BACK_INSIDE_THE_WORD,
               KERNED_BACK_WORD_SPACE)


class SpacedLinesPdf:
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
        objects = [f"BT /{FONT} {FONT_SIZE} Tf {LEFT} {baseline_of(row)} Td {shown} ET"
                   for row, shown in enumerate(SHOWN_LINES)]
        return "\n".join(objects).encode("latin-1")

    @staticmethod
    def _append_stream(document, page, stream: bytes) -> None:
        xref = document.get_new_xref()
        document.update_object(xref, "<<>>")
        document.update_stream(xref, stream)
        references = " ".join(f"{content} 0 R" for content in [*page.get_contents(), xref])
        document.xref_set_key(page.xref, "Contents", f"[{references}]")


def baseline_of(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


class _UnhyphenatedJoins:
    @staticmethod
    def keeps_hyphen(_text: str, _line: str) -> bool:
        return True


class TestSpacesTheGlyphsBesideThemLeaveNoRoomFor(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.layer = TextLayer(SpacedLinesPdf(Path(directory.name) / "spaces.pdf").write())
        self.addCleanup(self.layer.close)

    def line_text(self, row: int) -> str:
        return "".join(char.char for char in self.line_chars(row)).strip()

    def line_html(self, row: int) -> str:
        return BlockHtml(_UnhyphenatedJoins()).of(rows_of(self.line_chars(row)))

    def line_chars(self, row: int) -> list:
        baseline_from_top = PAGE_HEIGHT - baseline_of(row)
        band = Box(0.0, baseline_from_top - BAND_ABOVE, PAGE_WIDTH, baseline_from_top + BAND_BELOW)
        return self.layer.chars_in(1, band)

    def test_a_space_the_glyph_after_it_starts_under_is_not_a_word_break(self) -> None:
        self.assertEqual("something whole", self.line_text(0))

    def test_a_space_inside_the_reach_of_the_accented_letter_before_it_is_not_a_word_break(self) -> None:
        self.assertEqual("Éditions whole", self.line_text(1))

    def test_a_word_space_shrunk_by_a_kern_is_kept(self) -> None:
        self.assertEqual("tight words", self.line_text(2))

    def test_a_word_space_the_next_glyph_is_kerned_back_into_is_kept(self) -> None:
        self.assertEqual("itself. There", self.line_text(4))

    def test_no_word_gap_opens_after_a_mark_set_back_inside_the_word_before(self) -> None:
        self.assertEqual("Ro!zsa whole", self.line_html(3))


class TestSpaceAfterAFormatCharacter(unittest.TestCase):
    def test_a_space_after_a_zero_width_format_character_drawn_over_it_is_a_word_break(self) -> None:
        placed = (("–", 363.85, 368.72), ("\u200b", 368.72, 371.43), (" ", 368.76, 371.47), ("w", 371.07, 378.29))
        chars = [LayerChar(char, ((left + right) / 2, 5.0), False, FONT_SIZE, bbox=(left, 0.0, right, 10.0))
                 for char, left, right in placed]
        self.assertEqual("–\u200b w", "".join(char.char for char in OverlappedSpaces().dropped(chars)))


if __name__ == "__main__":
    unittest.main()
