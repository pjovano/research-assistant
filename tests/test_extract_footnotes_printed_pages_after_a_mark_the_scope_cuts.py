from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, excluding, keep_everything
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.policy import SectionPolicy
from _extract.readings import WorkerReadings
from _extract.spans import PagePlace
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
AUTHOR_BASELINE = 80.0
BODY_BASELINE = 140.0
NOTE_BASELINE = 600.0
SCOPE_RESUME = 110.0
AUTHOR_LINE = "A. Author"
MARK = "1"
FIRST_BODY = "The paper opens on its first claim."
SECOND_BODY = "The paper closes on its last claim."
NOTE = "R. Writer, Journal of Tests 7, 424 (2010)."


class AuthorMarkedPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            first = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            first.insert_text((LEFT, AUTHOR_BASELINE), AUTHOR_LINE, fontsize=BODY_SIZE, fontname=FONT)
            mark_left = LEFT + pymupdf.get_text_length(AUTHOR_LINE, FONT, BODY_SIZE)
            first.insert_text((mark_left, AUTHOR_BASELINE - MARK_RISE), MARK, fontsize=MARK_SIZE, fontname=FONT)
            first.insert_text((LEFT, BODY_BASELINE), FIRST_BODY, fontsize=BODY_SIZE, fontname=FONT)
            second = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            second.insert_text((LEFT, BODY_BASELINE), SECOND_BODY, fontsize=BODY_SIZE, fontname=FONT)
            second.insert_text((LEFT, NOTE_BASELINE), f"{MARK} {NOTE}", fontsize=NOTE_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


@dataclass(frozen=True)
class PrintedLine:
    file_page: int
    baseline: float

    def block(self, kind: str, html: str) -> Block:
        box = (LEFT, self.baseline - LINE_HALF_HEIGHT, RIGHT, self.baseline + LINE_HALF_HEIGHT / 2)
        return Block(self.file_page, kind, html, box, {}, f"/page/{self.file_page}/{kind}/{self.baseline}")


def engine_reading() -> list[PageBlocks]:
    first = [PrintedLine(1, AUTHOR_BASELINE).block(TEXT_KIND, f"<p>{AUTHOR_LINE}<sup>{MARK}</sup></p>"),
             PrintedLine(1, BODY_BASELINE).block(TEXT_KIND, f"<p>{FIRST_BODY}</p>")]
    second = [PrintedLine(2, BODY_BASELINE).block(TEXT_KIND, f"<p>{SECOND_BODY}</p>"),
              PrintedLine(2, NOTE_BASELINE).block(FOOTNOTE_KIND, f"<p>{MARK} {NOTE}</p>")]
    return [PageBlocks(1, first), PageBlocks(2, second)]


class TestFootnotesPrintedPagesAfterAMarkTheScopeCuts(unittest.TestCase):
    def built(self, policy: SectionPolicy) -> NoteStructure:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(AuthorMarkedPdf(Path(directory.name) / "marked.pdf").write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading()), [], WorkerReadings.none(), policy)
        return NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)

    def test_a_later_pages_note_printing_the_numeral_of_a_cut_mark_keeps_its_text(self) -> None:
        structure = self.built(excluding(PagePlace(1), PagePlace(1, SCOPE_RESUME)))
        self.assertEqual([f"{MARK}. {NOTE}"], [definition.text for definition in structure.definitions()])

    def test_a_later_pages_note_printing_the_numeral_of_a_kept_mark_answers_it(self) -> None:
        structure = self.built(keep_everything())
        self.assertEqual([NOTE], [definition.text for definition in structure.definitions()])


if __name__ == "__main__":
    unittest.main()
