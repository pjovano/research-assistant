from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.outline import Heading as OutlineHeading
from _extract.policy import SectionPolicy
from _extract.spans import ScopePoints
from _extract.structure import Paragraph
from _extract.withheld import WithheldNote
from _extract_fixtures import page_assembler

FONT_SIZE = 9.0
LINE_PITCH = 11.0
LEFT_MARGIN = 40.0
HANGING_INDENT = 10.0
NOTES_TITLE, REFERENCES_TITLE = "Notes", "References"
NOTES_BASELINE = 90.0
FIRST_NOTE_BASELINE = 112.0
NOTES = [["1 A first note that runs over", "onto its own line."], ["2 A second note that cites", "a work by Kant."],
         ["3 A third note that cites", "a work by Hegel."], ["4 A closing note thanks", "the colleagues."]]
REFERENCES_BASELINE = 215.0
NOTES_HEADING_BOX = (38.0, 80.0, 90.0, 93.0)
NOTE_BLOCK_BOX = (38.0, 100.0, 300.0, 194.0)
REFERENCES_HEADING_BOX = (38.0, 204.0, 110.0, 218.0)
EXCLUDED_NOTE = NOTES[-1]


class NotesInOneBlockPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((LEFT_MARGIN, NOTES_BASELINE), NOTES_TITLE, fontname="hebo", fontsize=FONT_SIZE)
            for row, (left, text) in enumerate(self._hanging_lines()):
                page.insert_text((left, FIRST_NOTE_BASELINE + row * LINE_PITCH), text, fontname="helv",
                                 fontsize=FONT_SIZE)
            page.insert_text((LEFT_MARGIN, REFERENCES_BASELINE), REFERENCES_TITLE, fontname="hebo",
                             fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path

    @staticmethod
    def _hanging_lines() -> list[tuple[float, str]]:
        return [(LEFT_MARGIN if row == 0 else LEFT_MARGIN + HANGING_INDENT, text)
                for note in NOTES for row, text in enumerate(note)]


class TestSpanCoveringOneEntryOfABlock(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        self._layer = TextLayer(NotesInOneBlockPdf(directory / "notes.pdf").write())
        self.addCleanup(self._layer.close)
        policy = SectionPolicy(ScopePoints(self._layer).spans([(f"1: {EXCLUDED_NOTE[0]}", f"1: {REFERENCES_TITLE}")]))
        self._assembler = page_assembler(self._layer, policy)
        blocks = [Block(1, HEADING_KIND, "", NOTES_HEADING_BOX, {}, "/page/1/SectionHeader/0"),
                  Block(1, TEXT_KIND, "<p>engine text</p>", NOTE_BLOCK_BOX, {}, "/page/1/Text/1"),
                  Block(1, HEADING_KIND, "", REFERENCES_HEADING_BOX, {}, "/page/1/SectionHeader/2")]
        due = [OutlineHeading(1, NOTES_TITLE, 1), OutlineHeading(1, REFERENCES_TITLE, 1)]
        self._elements = self._assembler.assemble(PageBlocks(1, blocks), due, None).elements

    def test_an_entry_list_drops_the_entry_a_span_covers_inside_a_block_it_mostly_keeps(self) -> None:
        texts = [element.text for element in self._elements if isinstance(element, Paragraph)]
        self.assertEqual([" ".join(note) for note in NOTES[:-1]], texts)

    def test_a_notes_entry_a_span_covers_inside_a_kept_block_is_withheld(self) -> None:
        self.assertEqual([WithheldNote(1, "4", True)], self._assembler.withheld_notes())


if __name__ == "__main__":
    unittest.main()
