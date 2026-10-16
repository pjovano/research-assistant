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
BODY_SIZE = 12.0
NOTE_SIZE = 10.0
MARK_SIZE = 7.0
MARK_RISE = 4.0
PAGE_WIDTH = 612.0
PAGE_HEIGHT = 792.0
LEFT = 108.0
RIGHT = 502.0
BODY_PITCH = 24.0
NOTE_PITCH = 12.0
FIRST_BODY_BASELINE = 140.0
FIRST_NOTE_BASELINE = 600.0
SECOND_NOTE_BASELINE = 660.0
OPEN_NOTE_NUMBER = "3"
CLOSING_NOTE_NUMBER = "4"


@dataclass(frozen=True)
class SetRows:
    baseline: float
    size: float
    rows: tuple[str, ...]
    indent: float = 0.0

    @property
    def pitch(self) -> float:
        return BODY_PITCH if self.size == BODY_SIZE else NOTE_PITCH

    @property
    def bottom(self) -> float:
        return self.baseline + (len(self.rows) - 1) * self.pitch + self.size / 2

    @property
    def text(self) -> str:
        return " ".join(self.rows)

    def draw_on(self, page) -> None:
        for index, row in enumerate(self.rows):
            page.insert_text((LEFT + self.indent, self.baseline + index * self.pitch), row, fontsize=self.size,
                             fontname=FONT)

    def raise_after(self, page, mark: str) -> None:
        last_left = LEFT + pymupdf.get_text_length(self.rows[-1], FONT, self.size)
        last_baseline = self.baseline + (len(self.rows) - 1) * self.pitch
        page.insert_text((last_left, last_baseline - MARK_RISE), mark, fontsize=MARK_SIZE, fontname=FONT)

    def raise_before(self, page, mark: str) -> None:
        page.insert_text((LEFT, self.baseline - MARK_RISE), mark, fontsize=MARK_SIZE, fontname=FONT)


@dataclass(frozen=True)
class EngineBlock:
    kind: str
    html: str
    top: float
    bottom: float

    def on(self, file_page: int) -> Block:
        identifier = f"/page/{file_page}/{self.kind}/{self.top}"
        return Block(file_page, self.kind, self.html, (LEFT, self.top, RIGHT, self.bottom), {}, identifier)


OPENING_BODY = SetRows(FIRST_BODY_BASELINE, BODY_SIZE,
                       ("The argument opens with a claim about intentional states and",
                        "their bearers, which the next pages develop at length"))
OPEN_NOTE = SetRows(FIRST_NOTE_BASELINE, NOTE_SIZE,
                    ("The term is sometimes used to mean a state that has",
                     "intentional properties and not the other features of"), MARK_SIZE)
BODY = SetRows(FIRST_BODY_BASELINE, BODY_SIZE,
               ("Many mental states have both intentional properties and phenomenal",
                "properties. When you see a rose, there is something it is like for you",
                "to see the rose, and your mind is directed at something, such as a"))
CARRIED = SetRows(FIRST_BODY_BASELINE + 3 * BODY_PITCH, NOTE_SIZE,
                  ("states that might happen to be intentional, such as their modes,",
                   "we use the term to pick out instantiations of intentional properties."))
CLOSING_NOTE = SetRows(SECOND_NOTE_BASELINE, NOTE_SIZE, ("See also the longer study of these questions.",), MARK_SIZE)
NEXT_BODY = SetRows(FIRST_BODY_BASELINE, BODY_SIZE, ("rose or a possible state of affairs involving a rose.",))


class CarriedNotePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            self._opening_page(document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT))
            self._carrying_page(document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT))
            NEXT_BODY.draw_on(document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT))
            document.save(self._path)
        return self._path

    @staticmethod
    def _opening_page(page) -> None:
        OPENING_BODY.draw_on(page)
        OPENING_BODY.raise_after(page, OPEN_NOTE_NUMBER)
        OPEN_NOTE.draw_on(page)
        OPEN_NOTE.raise_before(page, OPEN_NOTE_NUMBER)

    @staticmethod
    def _carrying_page(page) -> None:
        BODY.draw_on(page)
        CARRIED.draw_on(page)
        CLOSING_NOTE.draw_on(page)
        CLOSING_NOTE.raise_before(page, CLOSING_NOTE_NUMBER)


def _block_of(kind: str, rows: SetRows, html: str) -> EngineBlock:
    return EngineBlock(kind, html, rows.baseline - rows.size, rows.bottom)


def engine_reading() -> DocumentBlocks:
    opening = PageBlocks(1, [
        _block_of(TEXT_KIND, OPENING_BODY, f"<p>{OPENING_BODY.text}<sup>{OPEN_NOTE_NUMBER}</sup></p>").on(1),
        _block_of(FOOTNOTE_KIND, OPEN_NOTE, f"<p><sup>{OPEN_NOTE_NUMBER}</sup>{OPEN_NOTE.text}</p>").on(1)])
    merged = EngineBlock(TEXT_KIND, f"<p>{BODY.text} {CARRIED.text}</p>", BODY.baseline - BODY.size, CARRIED.bottom)
    carrying = PageBlocks(2, [
        merged.on(2),
        _block_of(FOOTNOTE_KIND, CLOSING_NOTE, f"<p><sup>{CLOSING_NOTE_NUMBER}</sup>{CLOSING_NOTE.text}</p>").on(2)])
    following = PageBlocks(3, [_block_of(TEXT_KIND, NEXT_BODY, f"<p>{NEXT_BODY.text}</p>").on(3)])
    return DocumentBlocks([opening, carrying, following])


class TestFootnotesContinuedAtTheFootOfABodyBlockReachingIntoTheNotes(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(CarriedNotePdf(Path(directory.name) / "carried.pdf").write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(engine_reading(), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.text = NoteWriter().render(structure.elements(), structure.definitions()).text
        self.definitions = {definition.label: definition.text for definition in structure.definitions()}

    def test_the_note_type_rows_at_the_blocks_foot_continue_the_open_note(self) -> None:
        self.assertEqual(f"{OPEN_NOTE.text} {CARRIED.text}", self.definitions[int(OPEN_NOTE_NUMBER)])

    def test_the_body_rows_above_run_on_across_the_page_break(self) -> None:
        self.assertIn(f"{BODY.rows[-1]} %% file p. 3 %% {NEXT_BODY.text}", self.text)


if __name__ == "__main__":
    unittest.main()
