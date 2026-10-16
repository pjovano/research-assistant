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
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
BODY_BASELINES = (100.0, 114.0)
NOTE_BASELINE = 560.0
FOOT_BASELINES = (520.0, 540.0)
MARK = "1"
FIRST_BODY = "Kant takes up the case of the rotating earth in the last chapter."
SECOND_BODY = ("I now return to the main argument of this chapter and its place in the Analytic.",
               "The usual comment on this passage is that Kant insists on the ideality of space.")
UNFINISHED_NOTE = "He observes in the same work that one can refer to the latter part of Newton's"
FINISHED_NOTE = "He observes in the same work that one can refer to Newton."
FOOT = ("scholium to the definitions, where motion is shown to be given in experience.",
        "But it is not clear that this passage resolves the paradox.")
DEFINITION_RE = re.compile(r"^\[\^(\d+)\]: (.*)$", re.MULTILINE)


@dataclass(frozen=True)
class CarriedNote:
    note_opening: str

    def write(self, path: Path) -> Path:
        with pymupdf.open() as document:
            first = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            first.insert_text((LEFT, BODY_BASELINES[0]), FIRST_BODY, fontsize=BODY_SIZE, fontname=FONT)
            mark_left = LEFT + pymupdf.get_text_length(FIRST_BODY, FONT, BODY_SIZE)
            first.insert_text((mark_left, BODY_BASELINES[0] - MARK_RISE), MARK, fontsize=MARK_SIZE, fontname=FONT)
            first.insert_text((LEFT, NOTE_BASELINE), f"{MARK} {self.note_opening}", fontsize=NOTE_SIZE,
                              fontname=FONT)
            second = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for baseline, line in zip(BODY_BASELINES, SECOND_BODY):
                second.insert_text((LEFT, baseline), line, fontsize=BODY_SIZE, fontname=FONT)
            for baseline, line in zip(FOOT_BASELINES, FOOT):
                second.insert_text((LEFT, baseline), line, fontsize=NOTE_SIZE, fontname=FONT)
            document.save(path)
        return path

    def engine_reading(self) -> list[PageBlocks]:
        first = [_block(TEXT_KIND, f"<p>{FIRST_BODY}<sup>{MARK}</sup></p>", Place(1, BODY_BASELINES[0])),
                 _block(FOOTNOTE_KIND, f"<p><sup>{MARK}</sup> {self.note_opening}</p>", Place(1, NOTE_BASELINE))]
        second = [_block(TEXT_KIND, f"<p>{line}</p>", Place(2, baseline))
                  for baseline, line in zip(BODY_BASELINES + FOOT_BASELINES, SECOND_BODY + FOOT)]
        return [PageBlocks(1, first), PageBlocks(2, second)]


class Place(NamedTuple):
    file_page: int
    baseline: float


def _block(kind: str, html: str, place: Place) -> Block:
    box = (LEFT, place.baseline - LINE_HALF_HEIGHT, RIGHT, place.baseline + LINE_HALF_HEIGHT / 2)
    return Block(place.file_page, kind, html, box, {}, f"/page/{place.file_page}/{kind}/{place.baseline}")


class TestFootnotesCarriedOverInSeveralBlocksOntoAPageWithoutNotes(unittest.TestCase):
    def rendered(self, carried: CarriedNote) -> str:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(carried.write(Path(directory.name) / "carried.pdf"))
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(carried.engine_reading()), [], WorkerReadings.none(),
                                 keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=frozenset({1, 2}))
        structure = NoteStructure(work, inputs)
        return NoteWriter().render(structure.elements(), structure.definitions()).text

    def test_every_note_type_block_stacked_at_the_foot_continues_the_unfinished_note(self) -> None:
        text = self.rendered(CarriedNote(UNFINISHED_NOTE))
        self.assertEqual([(MARK, " ".join((UNFINISHED_NOTE,) + FOOT))], DEFINITION_RE.findall(text))

    def test_no_block_of_the_stack_stays_in_the_body(self) -> None:
        text = self.rendered(CarriedNote(UNFINISHED_NOTE))
        body = DEFINITION_RE.sub("", text)
        self.assertEqual([], [line for line in FOOT if line in body])

    def test_the_stack_stays_in_the_body_below_a_finished_note(self) -> None:
        text = self.rendered(CarriedNote(FINISHED_NOTE))
        self.assertEqual([(MARK, FINISHED_NOTE)], DEFINITION_RE.findall(text))


if __name__ == "__main__":
    unittest.main()
