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

FILE_PAGE = 1
FONT = "cour"
FONT_SIZE = 9.0
LINE_PITCH = 11.0
FIRST_BASELINE = 100.0
CHAR_WIDTH = pymupdf.get_text_length("x", FONT, FONT_SIZE)
MARGIN = 54.0
WIDEST_NUMBER_CHARS = 3
RUN_ON_CHARS = 4
PAGE_WIDTH, PAGE_HEIGHT = 480.0, 660.0
WHOLE_PAGE = Box(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT)
LEAD_IN = "For textbooks we state the year of publication of the first edition."
ENTRIES = [("K. R. Apt: Logic Programming. In: J. v. Leeuwen (Editor): Handbook",
            "of Theoretical Computer Science, vol. B. Elsevier, Amsterdam 1990."),
           ("C. Baier and J.-P. Katoen: Principles of Model-Checking. MIT Press.",),
           ("J. Barwise: Admissible Sets and Structures. Springer-Verlag, Berlin",
            "1975."),
           ("J. Barwise and S. Feferman (Editors): Model-Theoretic Logics. Berlin",
            "and New York 1985."),
           ("P. Benacerraf and H. Putnam (Editors): Philosophy of Mathematics.",
            "Cambridge University Press, Cambridge 1983."),
           ("B. Bolzano: Wissenschaftslehre, vol. II. J. E. von Seidel, Sulzbach",
            "1837."),
           ("G. Cantor: Gesammelte Abhandlungen mathematischen und philosophischen",
            "Inhalts. Springer-Verlag, Berlin 1932."),
           ("C. C. Chang and H. J. Keisler: Model Theory. North-Holland, Amsterdam",
            "and London 1973."),
           ("A. Church: A Note on the Entscheidungsproblem. The Journal of Symbolic",
            "Logic 1 (1936)."),
           ("N. Cutland: Computability. Cambridge University Press, Cambridge 1980.",),
           ("G. Frege: Begriffsschrift, eine der arithmetischen nachgebildete",
            "Formelsprache des reinen Denkens. Louis Nebert, Halle 1879.")]


class LeadInNumberedListPdf:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._baseline = FIRST_BASELINE

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            self._line(page, MARGIN, LEAD_IN)
            for number, (opening, *run_ons) in enumerate(ENTRIES, start=1):
                self._line(page, self._number_left(number), f"{number}. {opening}")
                for run_on in run_ons:
                    self._line(page, MARGIN + RUN_ON_CHARS * CHAR_WIDTH, run_on)
            document.save(self._path)
        return self._path

    def _line(self, page, left: float, text: str) -> None:
        page.insert_text((left, self._baseline), text, fontsize=FONT_SIZE, fontname=FONT)
        self._baseline += LINE_PITCH

    @staticmethod
    def _number_left(number: int) -> float:
        return MARGIN + (WIDEST_NUMBER_CHARS - len(f"{number}.")) * CHAR_WIDTH


class TestNumberedListsOpeningOnAnUnnumberedLeadInSentence(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(LeadInNumberedListPdf(Path(directory.name) / "references.pdf").write())
        self.addCleanup(layer.close)
        self.entries = [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(FILE_PAGE, WHOLE_PAGE)]

    def test_the_lead_in_sentence_stands_as_an_entry_of_its_own(self) -> None:
        self.assertEqual(LEAD_IN, self.entries[0])

    def test_each_numbered_entry_opens_at_its_right_aligned_number(self) -> None:
        expected = [" ".join((f"{number}. {lines[0]}",) + lines[1:]) for number, lines in enumerate(ENTRIES, start=1)]
        self.assertEqual(expected, self.entries[1:])


if __name__ == "__main__":
    unittest.main()
