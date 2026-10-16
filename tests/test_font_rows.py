from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _font_fixtures import FIRST_PAGE_INDEX, PIXEL_SAMPLES, occurrence_in
from _clean.cmap import ToUnicodeCMap
from _clean.fonts import NO_TOUNICODE, FontRecord
from _clean.fontscan import MISSING_FROM_TOUNICODE, FontRows, FontStatusRows
from _clean.pixels import Disagreement
from _clean.textlayer import SuspectOccurrence

TEXT_LAYER_FONT = "Symbol"
BASEFONT = "ABCDEF+Symbol"
MAPPED_CODE = "0005"
MAPPED_CHAR = ""
UNMAPPED_CHAR = ""
OTHER_UNMAPPED_CHAR = ""
READING = "∀"
OCCURRENCE_COUNT = 3


def mapped_record() -> FontRecord:
    cmap = ToUnicodeCMap.from_mappings({MAPPED_CODE: MAPPED_CHAR})
    return FontRecord(1, BASEFONT, frozenset({FIRST_PAGE_INDEX}), {}, cmap, None)


def occurrences_of(char: str) -> list[SuspectOccurrence]:
    return [occurrence_in(TEXT_LAYER_FONT, char)] * OCCURRENCE_COUNT


def disagreement_row(record: FontRecord, char: str) -> dict:
    disagreement = Disagreement(TEXT_LAYER_FONT, char, PIXEL_SAMPLES, 0, READING)
    return FontStatusRows(record, []).disagreement_row(disagreement)


class TestFontRows(unittest.TestCase):
    def _rows(self, record: FontRecord, found_char: str, disagreeing_char: str) -> list[dict]:
        status_rows = FontStatusRows(record, occurrences_of(found_char)).rows()
        return FontRows(status_rows, [disagreement_row(record, disagreeing_char)]).rows()

    def test_a_character_missing_from_the_tounicode_that_the_pixels_disagree_on_is_reported_once(self) -> None:
        rows = self._rows(mapped_record(), UNMAPPED_CHAR, UNMAPPED_CHAR)
        self.assertEqual([(MISSING_FROM_TOUNICODE, "U+F024")], [(row["status"], row["unicode"]) for row in rows])

    def test_the_single_row_keeps_the_text_layer_count(self) -> None:
        row = self._rows(mapped_record(), UNMAPPED_CHAR, UNMAPPED_CHAR)[0]
        self.assertEqual(OCCURRENCE_COUNT, row["count"])

    def test_the_single_row_carries_the_pixel_reading(self) -> None:
        row = self._rows(mapped_record(), UNMAPPED_CHAR, UNMAPPED_CHAR)[0]
        self.assertEqual(READING, row["reading"])

    def test_a_disagreement_on_another_character_keeps_its_own_row(self) -> None:
        rows = self._rows(mapped_record(), UNMAPPED_CHAR, OTHER_UNMAPPED_CHAR)
        self.assertEqual(["U+F024", "U+F025"], [row["unicode"] for row in rows])

    def test_a_status_row_without_a_character_stands_beside_the_disagreement(self) -> None:
        record = FontRecord(1, BASEFONT, frozenset({FIRST_PAGE_INDEX}), {}, None, NO_TOUNICODE)
        rows = self._rows(record, UNMAPPED_CHAR, UNMAPPED_CHAR)
        self.assertEqual([NO_TOUNICODE, MISSING_FROM_TOUNICODE], [row["status"] for row in rows])


if __name__ == "__main__":
    unittest.main()
