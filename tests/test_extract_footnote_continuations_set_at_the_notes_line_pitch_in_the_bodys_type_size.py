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
TYPE_SIZE = 10.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
BODY_PITCH = 14.0
NOTE_PITCH = 10.0
BODY_TOP_BASELINE = 100.0
FIRST_NOTE_BASELINE = 560.0
SECOND_NOTE_BASELINE = 540.0
FIRST_MARK = "1"
SECOND_MARK = "2"
FIRST_BODY = "Kant takes up the case of the rotating earth in the last chapter."
SECOND_BODY = ("I now return to the main argument of this chapter and its place in the Analytic.",
               "The usual comment on this passage is that Kant insists on the ideality of space.",
               "Yet the passage says more than the comment allows, and the rest of this section",
               "argues that the paradox is not resolved by the doctrine of the Aesthetic.")
SECOND_BODY_MARKED_LINE = 1
FIRST_NOTE_OPENING = "He observes in the same work that one can refer to the latter part of Newton's"
CONTINUATION = ("scholium to the definitions, where motion is shown to be given in experience,",
                "and that the paradox of the rotating earth follows from the same scholium.")
SECOND_NOTE = ("See the second edition, where the passage is revised and the scholium is cited",
               "by its page in the Principia.")
DEFINITION_RE = re.compile(r"^\[\^(\d+)\]: (.*)$", re.MULTILINE)


class Place(NamedTuple):
    file_page: int
    baselines: tuple[float, ...]


class MarkedLine(NamedTuple):
    baseline: float
    text: str
    mark: str

    def write(self, page) -> None:
        page.insert_text((LEFT, self.baseline), self.text, fontsize=TYPE_SIZE, fontname=FONT)
        mark_left = LEFT + pymupdf.get_text_length(self.text, FONT, TYPE_SIZE)
        page.insert_text((mark_left, self.baseline - MARK_RISE), self.mark, fontsize=MARK_SIZE, fontname=FONT)


@dataclass(frozen=True)
class ContinuedNote:
    continuation_pitch: float

    def write(self, path: Path) -> Path:
        with pymupdf.open() as document:
            first = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            MarkedLine(BODY_TOP_BASELINE, FIRST_BODY, FIRST_MARK).write(first)
            first.insert_text((LEFT, FIRST_NOTE_BASELINE), f"{FIRST_MARK} {FIRST_NOTE_OPENING}", fontsize=TYPE_SIZE,
                              fontname=FONT)
            second = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for index, (baseline, line) in enumerate(zip(_body_baselines(), SECOND_BODY)):
                mark = SECOND_MARK if index == SECOND_BODY_MARKED_LINE else ""
                MarkedLine(baseline, line, mark).write(second)
            for baseline, line in zip(self._continuation_baselines(), CONTINUATION):
                second.insert_text((LEFT, baseline), line, fontsize=TYPE_SIZE, fontname=FONT)
            for baseline, line in zip(_second_note_baselines(), (f"{SECOND_MARK} {SECOND_NOTE[0]}",) + SECOND_NOTE[1:]):
                second.insert_text((LEFT, baseline), line, fontsize=TYPE_SIZE, fontname=FONT)
            document.save(path)
        return path

    def engine_reading(self) -> list[PageBlocks]:
        first = [_block(TEXT_KIND, f"<p>{FIRST_BODY}<sup>{FIRST_MARK}</sup></p>", Place(1, (BODY_TOP_BASELINE,))),
                 _block(FOOTNOTE_KIND, f"<p><sup>{FIRST_MARK}</sup> {FIRST_NOTE_OPENING}</p>",
                        Place(1, (FIRST_NOTE_BASELINE,)))]
        marked_body = list(SECOND_BODY)
        marked_body[SECOND_BODY_MARKED_LINE] += f"<sup>{SECOND_MARK}</sup>"
        second = [_block(TEXT_KIND, f"<p>{' '.join(marked_body)}</p>", Place(2, _body_baselines())),
                  _block(TEXT_KIND, f"<p>{' '.join(CONTINUATION)}</p>", Place(2, self._continuation_baselines())),
                  _block(FOOTNOTE_KIND, f"<p><sup>{SECOND_MARK}</sup> {' '.join(SECOND_NOTE)}</p>",
                         Place(2, _second_note_baselines()))]
        return [PageBlocks(1, first), PageBlocks(2, second)]

    def _continuation_baselines(self) -> tuple[float, ...]:
        last = SECOND_NOTE_BASELINE - NOTE_PITCH
        return tuple(last - self.continuation_pitch * step for step in reversed(range(len(CONTINUATION))))


def _body_baselines() -> tuple[float, ...]:
    return tuple(BODY_TOP_BASELINE + BODY_PITCH * step for step in range(len(SECOND_BODY)))


def _second_note_baselines() -> tuple[float, ...]:
    return tuple(SECOND_NOTE_BASELINE + NOTE_PITCH * step for step in range(len(SECOND_NOTE)))


def _block(kind: str, html: str, place: Place) -> Block:
    box = (LEFT, place.baselines[0] - LINE_HALF_HEIGHT, RIGHT, place.baselines[-1] + LINE_HALF_HEIGHT / 2)
    return Block(place.file_page, kind, html, box, {}, f"/page/{place.file_page}/{kind}/{place.baselines[0]}")


class TestFootnoteContinuationsSetAtTheNotesLinePitchInTheBodysTypeSize(unittest.TestCase):
    def rendered(self, continued: ContinuedNote) -> str:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(continued.write(Path(directory.name) / "continued.pdf"))
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(continued.engine_reading()), [], WorkerReadings.none(),
                                 keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts())
        structure = NoteStructure(work, inputs)
        return NoteWriter().render(structure.elements(), structure.definitions()).text

    def test_a_block_at_the_notes_pitch_continues_the_open_note(self) -> None:
        text = self.rendered(ContinuedNote(NOTE_PITCH))
        self.assertEqual((FIRST_MARK, " ".join((FIRST_NOTE_OPENING,) + CONTINUATION)), DEFINITION_RE.findall(text)[0])

    def test_a_block_at_the_notes_pitch_leaves_the_body(self) -> None:
        body = DEFINITION_RE.sub("", self.rendered(ContinuedNote(NOTE_PITCH)))
        self.assertEqual([], [line for line in CONTINUATION if line in body])

    def test_a_block_at_the_bodys_pitch_stays_in_the_body(self) -> None:
        text = self.rendered(ContinuedNote(BODY_PITCH))
        self.assertEqual((FIRST_MARK, FIRST_NOTE_OPENING), DEFINITION_RE.findall(text)[0])


if __name__ == "__main__":
    unittest.main()
