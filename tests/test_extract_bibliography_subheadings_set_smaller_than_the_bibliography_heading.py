from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.policy import SectionOpening
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
FILE_PAGE = 1
PAGE_WIDTH, PAGE_HEIGHT = 400.0, 600.0
LEFT = 40.0
RIGHT = 360.0
RUN_ON_INDENT = 18.0
LINE_PITCH = 12.0
BODY_SIZE = 9.0
BIBLIOGRAPHY_SIZE = 16.0
LARGE_SUBHEADING_SIZE = 20.0
SMALL_SUBHEADING_SIZE = 8.0
BIBLIOGRAPHY_BASELINE = 60.0
SUBHEADING_BASELINE = 100.0
FIRST_ENTRY_BASELINE = 130.0
BIBLIOGRAPHY_TITLE = "Bibliography"
SUBHEADING_TITLE = "SECONDARY LITERATURE"
ENTRIES = (("Abel, Anna (1971). A First Study of the Subject. Frankfurt am Main: Verlag",
            "der Gesellschaft"),
           ("Baker, Bernd (1984). A Second Study of the Subject. Berlin and New York:",
            "De Gruyter"),
           ("Carter, Clara (2004). A Third Study of the Subject. Oxford: Blackwell",))


@dataclass(frozen=True)
class SubdividedBibliography:
    subheading_size: float

    def write(self, path: Path) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_text((LEFT, BIBLIOGRAPHY_BASELINE), BIBLIOGRAPHY_TITLE, fontsize=BIBLIOGRAPHY_SIZE,
                             fontname=FONT)
            page.insert_text((LEFT, SUBHEADING_BASELINE), SUBHEADING_TITLE, fontsize=self.subheading_size,
                             fontname=FONT)
            for row, (indent, line) in enumerate(_entry_lines()):
                page.insert_text((LEFT + indent, _entry_baseline(row)), line, fontsize=BODY_SIZE, fontname=FONT)
            document.save(path)
        return path


def _entry_lines() -> list[tuple[float, str]]:
    return [(RUN_ON_INDENT if row else 0.0, line) for entry in ENTRIES for row, line in enumerate(entry)]


def _entry_baseline(row: int) -> float:
    return FIRST_ENTRY_BASELINE + row * LINE_PITCH


def _block(kind: str, text: str, top: float, bottom: float) -> Block:
    return Block(FILE_PAGE, kind, f"<p>{text}</p>", (LEFT - 2.0, top, RIGHT + 2.0, bottom), {},
                 f"/page/{FILE_PAGE}/{kind}/{top}")


def engine_reading() -> DocumentBlocks:
    rows = len(_entry_lines())
    entries_text = " ".join(line for _indent, line in _entry_lines())
    return DocumentBlocks([PageBlocks(FILE_PAGE, [
        _block(HEADING_KIND, BIBLIOGRAPHY_TITLE, BIBLIOGRAPHY_BASELINE - BIBLIOGRAPHY_SIZE, BIBLIOGRAPHY_BASELINE + 4),
        _block(HEADING_KIND, SUBHEADING_TITLE, SUBHEADING_BASELINE - LARGE_SUBHEADING_SIZE, SUBHEADING_BASELINE + 3),
        _block(TEXT_KIND, entries_text, FIRST_ENTRY_BASELINE - BODY_SIZE, _entry_baseline(rows - 1) + 3)])])


class TestBibliographySubheadingsSetSmallerThanTheBibliographyHeading(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _paragraphs(self, subheading_size: float) -> list[str]:
        layer = TextLayer(SubdividedBibliography(subheading_size).write(self._directory / "bibliography.pdf"))
        self.addCleanup(layer.close)
        inputs = StructureInputs(engine_reading(), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        return NoteWriter().render(structure.elements(), structure.definitions()).text.strip().split("\n\n")

    def test_a_subheading_in_smaller_type_keeps_the_bibliography_an_entry_list(self) -> None:
        paragraphs = self._paragraphs(SMALL_SUBHEADING_SIZE)
        self.assertEqual([" ".join(entry) for entry in ENTRIES], paragraphs[-len(ENTRIES):])

    def test_a_heading_in_larger_type_ends_the_entry_list(self) -> None:
        paragraphs = self._paragraphs(LARGE_SUBHEADING_SIZE)
        self.assertEqual(" ".join(line for _indent, line in _entry_lines()), paragraphs[-1])


class TestSectionOpeningsBelowAnEntryListsHeading(unittest.TestCase):
    def test_an_opening_whose_type_size_is_unread_does_not_sit_under_the_list(self) -> None:
        bibliography = SectionOpening(1, BIBLIOGRAPHY_TITLE, (BIBLIOGRAPHY_SIZE, False, False))
        self.assertFalse(SectionOpening(1, SUBHEADING_TITLE).sits_under(bibliography))


if __name__ == "__main__":
    unittest.main()
