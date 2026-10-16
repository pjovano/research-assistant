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
FONT_SIZE = 10.0
LINE_PITCH = 13.5
ENTRY_SPACING = 9.0
FIRST_BASELINE = 110.0
LABEL_LEFT = 104.0
TEXT_LEFT = 166.0
WHOLE_PAGE = Box(0.0, 0.0, 595.0, 842.0)
ENTRIES = [("[GS86]", ["S. Graf and J. Sifakis. A logic for the specification and proof of",
                       "regular controllable processes. Acta Informatica, 23, 1986."]),
           ("[Gun85]", ["C. Gunter. Profinite solutions for recursive domain equations.",
                        "Technical Report, Carnegie-Mellon University, 1985."]),
           ("[Har79]", ["D. Harel. First Order Dynamic Logic, volume 68 of Lecture Notes",
                        "in Computer Science. Springer-Verlag, Berlin, 1979."]),
           ("[HM85]", ["M. Hennessy and R. Milner. Algebraic laws for nondeterminism",
                       "and concurrency. JACM, 32, 1985."]),
           ("[Hoa69]", ["C. A. R. Hoare. An axiomatic basis for computer programming.",
                        "Communications of the ACM, 12, 1969."]),
           ("[Joh82]", ["P. T. Johnstone. Stone Spaces, volume 3 of Cambridge Studies in",
                        "Advanced Mathematics. Cambridge University Press, 1982."])]
EXPECTED = [" ".join([label, *lines]) for label, lines in ENTRIES]


class LabelColumnBibliographyPdf:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._baseline = FIRST_BASELINE

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            for label, lines in ENTRIES:
                self._entry(page, label, lines)
            document.save(self._path)
        return self._path

    def _entry(self, page, label: str, lines: list[str]) -> None:
        page.insert_text((LABEL_LEFT, self._baseline), label, fontsize=FONT_SIZE, fontname=FONT)
        for position, line in enumerate(lines):
            origin = (TEXT_LEFT, self._baseline + position * LINE_PITCH)
            page.insert_text(origin, line, fontsize=FONT_SIZE, fontname=FONT)
        self._baseline += LINE_PITCH * len(lines) + ENTRY_SPACING


class TestEntryListsSettingEachLabelInAColumnOfItsOwn(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.layer = TextLayer(LabelColumnBibliographyPdf(Path(directory.name) / "bibliography.pdf").write())
        self.addCleanup(self.layer.close)
        self.entries = HangingIndentList(self.layer).boxed_entries(1, [WHOLE_PAGE])

    def test_each_entry_opens_at_the_label_set_beside_its_first_line(self) -> None:
        self.assertEqual(EXPECTED, [" ".join(entry.text.split()) for entry in self.entries])


if __name__ == "__main__":
    unittest.main()
