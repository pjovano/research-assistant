from __future__ import annotations

import re
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

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
NOTE_SIZE = 8.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
MARGIN = 40.0
INDENTED = MARGIN + 20.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
BODY_BASELINES = (100.0, 114.0, 128.0)
QUOTATION_BASELINES = (440.0, 450.0)
NOTE_BASELINE = 480.0
AMONG_THE_NOTES = (500.0, 510.0)
FIRST_BODY = ("Plato returns to convention in his last dialogue.",)
FIRST_MARK = "1"
FINISHED_NOTE = "The Laws were left unrevised at his death."
UNFINISHED_NOTE = "The Laws were left unrevised at his death, and the"
SECOND_BODY = ("In the Laws, Plato castigates those who claim that the",
               "gods and the just are matters of mere convention, and he",
               "states their view in their own words")
SECOND_MARK = "2"
QUOTATION_LINES = ("that the gods are creations of artifice, not by nature but",
                   "by certain conventions, and different in different places.")
SECOND_NOTE = "The passage closes the tenth book of the Laws."
DEFINITION_RE = re.compile(r"^\[\^(\d+)\]: (.*)$", re.MULTILINE)


class Lines(NamedTuple):
    file_page: int
    left: float
    baselines: tuple[float, ...]


@dataclass(frozen=True)
class MarkedPage:
    body: tuple[str, ...]
    mark: str
    note: str

    def draw_on(self, page) -> None:
        for baseline, line in zip(BODY_BASELINES, self.body):
            page.insert_text((MARGIN, baseline), line, fontsize=BODY_SIZE, fontname=FONT)
        last_baseline = BODY_BASELINES[len(self.body) - 1]
        mark_left = MARGIN + pymupdf.get_text_length(self.body[-1], FONT, BODY_SIZE)
        page.insert_text((mark_left, last_baseline - MARK_RISE), self.mark, fontsize=MARK_SIZE, fontname=FONT)
        page.insert_text((MARGIN, NOTE_BASELINE), f"{self.mark} {self.note}", fontsize=NOTE_SIZE, fontname=FONT)

    def blocks(self, file_page: int) -> list[Block]:
        body = Lines(file_page, MARGIN, BODY_BASELINES[:len(self.body)])
        return [_block(TEXT_KIND, f"<p>{' '.join(self.body)}<sup>{self.mark}</sup></p>", body),
                _block(FOOTNOTE_KIND, f"<p><sup>{self.mark}</sup> {self.note}</p>",
                       Lines(file_page, MARGIN, (NOTE_BASELINE,)))]


@dataclass(frozen=True)
class FootOfThePage:
    note_before: str
    quotation_left: float
    quotation_baselines: tuple[float, ...] = QUOTATION_BASELINES

    def write(self, path: Path) -> Path:
        with pymupdf.open() as document:
            self._first().draw_on(document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT))
            second = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            self._second().draw_on(second)
            for baseline, line in zip(self.quotation_baselines, QUOTATION_LINES):
                second.insert_text((self.quotation_left, baseline), line, fontsize=NOTE_SIZE, fontname=FONT)
            document.save(path)
        return path

    def engine_reading(self) -> list[PageBlocks]:
        quotation = _block(TEXT_KIND, f"<p>{' '.join(QUOTATION_LINES)}</p>",
                           Lines(2, self.quotation_left, self.quotation_baselines))
        body, note = self._second().blocks(2)
        return [PageBlocks(1, self._first().blocks(1)), PageBlocks(2, [body, quotation, note])]

    def _first(self) -> MarkedPage:
        return MarkedPage(FIRST_BODY, FIRST_MARK, self.note_before)

    @staticmethod
    def _second() -> MarkedPage:
        return MarkedPage(SECOND_BODY, SECOND_MARK, SECOND_NOTE)


def _block(kind: str, html: str, lines: Lines) -> Block:
    box = (lines.left, lines.baselines[0] - LINE_HALF_HEIGHT, RIGHT, lines.baselines[-1] + LINE_HALF_HEIGHT / 2)
    return Block(lines.file_page, kind, html, box, {}, f"/page/{lines.file_page}/{kind}/{lines.baselines[0]}")


class TestBlockQuotationsSetInNoteTypeJustAboveTheFootnotes(unittest.TestCase):
    def definitions(self, foot: FootOfThePage) -> list[str]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(foot.write(Path(directory.name) / "foot.pdf"))
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(foot.engine_reading()), [], WorkerReadings.none(), keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=frozenset({1, 2}))
        structure = NoteStructure(work, inputs)
        text = NoteWriter().render(structure.elements(), structure.definitions()).text
        return [note for _label, note in DEFINITION_RE.findall(text)]

    def test_an_indented_block_quotation_above_the_notes_stays_out_of_them(self) -> None:
        definitions = self.definitions(FootOfThePage(FINISHED_NOTE, INDENTED))
        self.assertEqual([FINISHED_NOTE, SECOND_NOTE], definitions)

    def test_a_note_type_block_set_flush_above_the_notes_is_read_as_note_text(self) -> None:
        definitions = self.definitions(FootOfThePage(FINISHED_NOTE, MARGIN))
        self.assertTrue(any(" ".join(QUOTATION_LINES) in definition for definition in definitions))

    def test_an_indented_block_above_the_notes_runs_on_a_note_the_page_before_leaves_unfinished(self) -> None:
        definitions = self.definitions(FootOfThePage(UNFINISHED_NOTE, INDENTED))
        self.assertIn(" ".join((UNFINISHED_NOTE,) + QUOTATION_LINES), definitions)

    def test_an_indented_block_below_a_note_opening_stays_among_the_notes(self) -> None:
        definitions = self.definitions(FootOfThePage(FINISHED_NOTE, INDENTED, AMONG_THE_NOTES))
        self.assertTrue(any(" ".join(QUOTATION_LINES) in definition for definition in definitions))


if __name__ == "__main__":
    unittest.main()
