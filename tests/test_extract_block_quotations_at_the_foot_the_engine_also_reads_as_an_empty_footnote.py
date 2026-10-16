from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
BODY_SIZE = 10.0
QUOTATION_SIZE = 8.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
MARGIN = 40.0
INDENTED = MARGIN + 25.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
TWIN_INSET = 1.0
BODY_BASELINES = (100.0, 114.0)
QUOTATION_BASELINES = (580.0, 590.0)
BODY_LINES = ("Kant holds that the definition is complete because",
              "the mathematician, as he puts it,")
QUOTATION_LINES = ("thinks everything that suffices to distinguish the thing",
                   "from all others, a thing in his pure reason, whereby")
NUMBERED_NOTE_LINES = ("2. Here the author gives the general principle under which",
                       "the cases already examined all fall, as he says.")
NEXT_PAGE_BODY = "he intends that the thing be distinguished from all others."


@dataclass(frozen=True)
class Foot:
    left: float
    lines: tuple[str, ...] = QUOTATION_LINES


class QuotedFootPdf:
    def __init__(self, path: Path, foot: Foot) -> None:
        self._path = path
        self._foot = foot

    def write(self) -> Path:
        with pymupdf.open() as document:
            first = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for baseline, line in zip(BODY_BASELINES, BODY_LINES):
                first.insert_text((MARGIN, baseline), line, fontsize=BODY_SIZE, fontname=FONT)
            for baseline, line in zip(QUOTATION_BASELINES, self._foot.lines):
                first.insert_text((self._foot.left, baseline), line, fontsize=QUOTATION_SIZE, fontname=FONT)
            second = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            second.insert_text((MARGIN, BODY_BASELINES[0]), NEXT_PAGE_BODY, fontsize=BODY_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


@dataclass(frozen=True)
class Region:
    left: float
    baselines: tuple[float, ...]
    inset: float = 0.0

    def block(self, file_page: int, kind: str, html: str) -> Block:
        box = (self.left, self.baselines[0] - LINE_HALF_HEIGHT,
               RIGHT - self.inset, self.baselines[-1] + LINE_HALF_HEIGHT / 2 - self.inset)
        return Block(file_page, kind, html, box, {}, f"/page/{file_page}/{kind}/{self.baselines[0]}")


def engine_reading(foot: Foot) -> list[PageBlocks]:
    quotation = f"<p>{' '.join(foot.lines)}</p>"
    first = [Region(MARGIN, BODY_BASELINES).block(1, TEXT_KIND, f"<p>{' '.join(BODY_LINES)}</p>"),
             Region(foot.left, QUOTATION_BASELINES).block(1, TEXT_KIND, quotation),
             Region(foot.left, QUOTATION_BASELINES, TWIN_INSET).block(1, FOOTNOTE_KIND, "<p></p>")]
    second = [Region(MARGIN, BODY_BASELINES[:1]).block(2, TEXT_KIND, f"<p>{NEXT_PAGE_BODY}</p>")]
    return [PageBlocks(1, first), PageBlocks(2, second)]


class TestBlockQuotationsAtTheFootTheEngineAlsoReadsAsAnEmptyFootnote(unittest.TestCase):
    def built(self, foot: Foot) -> NoteStructure:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(QuotedFootPdf(Path(directory.name) / "quoted.pdf", foot).write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading(foot)), [], WorkerReadings.none(), keep_everything())
        return NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)

    def test_an_indented_quotation_read_also_as_an_empty_footnote_stays_out_of_the_notes(self) -> None:
        self.assertEqual([], self.built(Foot(INDENTED)).definitions())

    def test_the_indented_quotation_runs_on_to_the_next_page_in_the_body(self) -> None:
        structure = self.built(Foot(INDENTED))
        paragraphs = NoteWriter().render(structure.elements(), []).text.strip().split("\n\n")
        self.assertIn(f"{' '.join(QUOTATION_LINES)} %% file p. 2 %% {NEXT_PAGE_BODY}", paragraphs)

    def test_a_flush_block_read_also_as_an_empty_footnote_keeps_the_notes_judgment(self) -> None:
        definitions = self.built(Foot(MARGIN)).definitions()
        self.assertEqual([" ".join(QUOTATION_LINES)], [definition.text for definition in definitions])

    def test_an_indented_note_opening_on_its_numeral_and_a_stop_keeps_the_notes_judgment(self) -> None:
        definitions = self.built(Foot(INDENTED, NUMBERED_NOTE_LINES)).definitions()
        self.assertEqual([" ".join(NUMBERED_NOTE_LINES)], [definition.text for definition in definitions])


if __name__ == "__main__":
    unittest.main()
