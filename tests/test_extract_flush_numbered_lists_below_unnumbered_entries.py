from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.elements import Paragraph
from _extract.layer import TextLayer
from _extract.policy import SectionOpening

NOTES_TITLE = "Notes"
NOTES_LEVEL = 1
SUBLEVEL = 2
FILE_PAGE = 1
FONT = "cour"
HEADING_FONT = "hebo"
FONT_SIZE = 9.0
HEADING_SIZE = 10.0
LEFT = 51.0
RIGHT = 440.0
LINE_PITCH = 11.0
BLOCK_GAP = 6.0
FIRST_BASELINE = 80.0
SUBHEADING = "Kant"
ABBREVIATIONS = (("C = Correspondence, trans. and ed. by A. Zweig (Cambridge, UK:",
                  "1999)/Briefwechsel, Akademieausgabe Vol. 12 (Berlin, 1969)."),
                 ("CPR = Critique of Pure Reason, trans. and ed. P. Guyer and A. W.",
                  "Wood (Cambridge University Press, 1999)."))
NOTES = (("12 Although the term absolute idealism does not recur frequently,",
          "it is found more than once."),
         ("13 On this, see the seminal Forster (1989) and Franks (2005).",))
CARRIED = (("note carried over from the page before runs on and ends",
            "on a second line of its own."),)


class NotesPage:
    def __init__(self, directory: Path, heading: str | None, unnumbered: tuple) -> None:
        self._path = directory / "notes.pdf"
        self._heading = heading
        self._paragraphs = unnumbered + NOTES
        self._blocks: list[Block] = []

    def write(self) -> Path:
        baseline = FIRST_BASELINE
        with pymupdf.open() as document:
            page = document.new_page()
            if self._heading is not None:
                page.insert_text((LEFT, baseline), self._heading, fontsize=HEADING_SIZE, fontname=HEADING_FONT)
                self._blocks.append(self._block(HEADING_KIND, self._heading, baseline, 1))
                baseline += LINE_PITCH + BLOCK_GAP
            for lines in self._paragraphs:
                for row, line in enumerate(lines):
                    page.insert_text((LEFT, baseline + row * LINE_PITCH), line, fontsize=FONT_SIZE, fontname=FONT)
                self._blocks.append(self._block(TEXT_KIND, " ".join(lines), baseline, len(lines)))
                baseline += len(lines) * LINE_PITCH + BLOCK_GAP
            document.save(self._path)
        return self._path

    @property
    def blocks(self) -> PageBlocks:
        return PageBlocks(FILE_PAGE, self._blocks)

    def _block(self, kind: str, text: str, baseline: float, rows: int) -> Block:
        box = (LEFT - 2.0, baseline - LINE_PITCH, RIGHT, baseline + (rows - 1) * LINE_PITCH + 3.0)
        return Block(FILE_PAGE, kind, f"<p>{text}</p>", box, {}, f"/page/{FILE_PAGE}/{len(self._blocks)}")


class TestFlushNumberedListsBelowUnnumberedEntries(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _paragraphs(self, heading: str | None, unnumbered: tuple) -> list[Paragraph]:
        printed = NotesPage(self._directory, heading, unnumbered)
        layer = TextLayer(printed.write())
        self.addCleanup(layer.close)
        policy = keep_everything()
        policy.opens(SectionOpening(NOTES_LEVEL, NOTES_TITLE))
        elements = page_assembler(layer, policy).assemble(printed.blocks, [], SUBLEVEL).elements
        return [element for element in elements if isinstance(element, Paragraph)]

    def test_unnumbered_entries_below_a_heading_above_the_first_number_each_keep_a_paragraph(self) -> None:
        texts = [paragraph.text for paragraph in self._paragraphs(SUBHEADING, ABBREVIATIONS)]
        self.assertEqual([" ".join(lines) for lines in ABBREVIATIONS + NOTES], texts)

    def test_unnumbered_lines_opening_the_page_above_the_first_number_resume_the_carried_note(self) -> None:
        first = self._paragraphs(None, CARRIED)[0]
        self.assertEqual((" ".join(CARRIED[0]), True), (first.text, first.resumes_mid_sentence))


if __name__ == "__main__":
    unittest.main()
