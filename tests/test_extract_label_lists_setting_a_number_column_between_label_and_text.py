from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.layer import TextLayer
from _extract.lists import HangingIndentList

FONT = "helv"
FONT_SIZE = 8.0
LINE_PITCH = 11.0
FIRST_BASELINE = 100.0
LABEL_LEFT = 51.0
NUMBER_LEFT = 75.0
TEXT_LEFT = 90.0
WHOLE_PAGE = Box(0.0, 0.0, 440.0, 650.0)
WRAPPED_ENTRY = ("W", "", ["Collected works in twenty volumes, edited by two editors, published by a press,",
                           "1969."])
NUMBERED_ENTRIES = [("FS", "1", "Early writings"), ("JS", "2", "Jena writings"),
                    ("PdG", "3", "Phenomenology of spirit"), ("NS", "4", "Nuremberg writings"),
                    ("WL I", "5", "Science of logic, first part"), ("WL II", "6", "Science of logic, second part"),
                    ("GPR", "7", "Outlines of the philosophy of right"), ("E I", "8", "Encyclopaedia, first part"),
                    ("GP III", "20", "Lectures on the history of philosophy, third part")]
ENTRIES = [WRAPPED_ENTRY] + [(label, number, [text]) for label, number, text in NUMBERED_ENTRIES]
EXPECTED = [" ".join(part for part in (label, number, *lines) if part) for label, number, lines in ENTRIES]


class NumberColumnLabelListPdf:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._baseline = FIRST_BASELINE

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            for entry in ENTRIES:
                self._entry(page, entry)
            document.save(self._path)
        return self._path

    def _entry(self, page, entry: tuple[str, str, list[str]]) -> None:
        label, number, lines = entry
        self._insert(page, LABEL_LEFT, label)
        text_left = NUMBER_LEFT if number else TEXT_LEFT
        lines = [f"{number} {lines[0]}", *lines[1:]] if number else lines
        for position, line in enumerate(lines):
            self._insert(page, text_left if position == 0 else TEXT_LEFT, line)
            self._baseline += LINE_PITCH

    def _insert(self, page, left: float, text: str) -> None:
        page.insert_text((left, self._baseline), text, fontsize=FONT_SIZE, fontname=FONT)


class TestLabelListsSettingANumberColumnBetweenLabelAndText(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.layer = TextLayer(NumberColumnLabelListPdf(Path(directory.name) / "abbreviations.pdf").write())
        self.addCleanup(self.layer.close)
        self.lists = HangingIndentList(self.layer)

    def test_the_list_is_read_as_a_label_list(self) -> None:
        self.assertTrue(self.lists.sets_a_label_column(1, [WHOLE_PAGE]))

    def test_each_entry_opens_at_its_label_with_its_number_and_wrapped_lines(self) -> None:
        entries = self.lists.boxed_entries(1, [WHOLE_PAGE])
        self.assertEqual(EXPECTED, [" ".join(entry.text.split()) for entry in entries])


if __name__ == "__main__":
    unittest.main()
