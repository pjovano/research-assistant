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
CARRIED_BASELINE = FIRST_NOTE_BASELINE + 2 * NOTE_PITCH
CLOSING_NOTE_BASELINE = 680.0
OPEN_NOTE_NUMBER = "3"
CLOSING_NOTE_NUMBER = "4"
CONTINUATION_LABEL = f"Footnote {OPEN_NOTE_NUMBER} continued"
CARRIED_OPENING = f"as in section {OPEN_NOTE_NUMBER} of"


@dataclass(frozen=True)
class SetRows:
    baseline: float
    size: float
    rows: tuple[str, ...]

    @property
    def pitch(self) -> float:
        return BODY_PITCH if self.size == BODY_SIZE else NOTE_PITCH

    @property
    def top(self) -> float:
        return self.baseline - self.size

    @property
    def bottom(self) -> float:
        return self.baseline + (len(self.rows) - 1) * self.pitch + self.size / 2

    @property
    def text(self) -> str:
        return " ".join(self.rows)

    def draw_on(self, page) -> None:
        for index, row in enumerate(self.rows):
            page.insert_text((LEFT, self.baseline + index * self.pitch), row, fontsize=self.size, fontname=FONT)

    def raise_after(self, page, mark: str) -> None:
        last_left = LEFT + pymupdf.get_text_length(self.rows[-1], FONT, self.size)
        last_baseline = self.baseline + (len(self.rows) - 1) * self.pitch
        page.insert_text((last_left, last_baseline - MARK_RISE), mark, fontsize=MARK_SIZE, fontname=FONT)

    def raise_before(self, page, mark: str) -> None:
        page.insert_text((LEFT, self.baseline - MARK_RISE), mark, fontsize=MARK_SIZE, fontname=FONT)

    def block_on(self, file_page: int, kind: str, html: str) -> Block:
        identifier = f"/page/{file_page}/{kind}/{self.top}"
        return Block(file_page, kind, html, (LEFT, self.top, RIGHT, self.bottom), {}, identifier)


OPENING_BODY = SetRows(FIRST_BODY_BASELINE, BODY_SIZE,
                       ("The argument opens with a claim about intentional states and",
                        "their bearers, which the next pages develop at length."))
OPEN_NOTE = SetRows(FIRST_NOTE_BASELINE, NOTE_SIZE,
                    ("The term is sometimes used to mean a state that has",
                     "intentional properties and not the other features of"))
NEXT_BODY = SetRows(FIRST_BODY_BASELINE, BODY_SIZE,
                    ("Many mental states have both intentional properties and phenomenal",
                     "properties, and the next section takes up the second kind."))
CARRIED = SetRows(CARRIED_BASELINE, NOTE_SIZE,
                  ("states that might happen to be intentional, such as their modes, while",
                   "we use the term to pick out instantiations of intentional properties."))
CLOSING_NOTE = SetRows(CLOSING_NOTE_BASELINE, NOTE_SIZE, ("See also the longer study of these questions.",))


class CarriedNotePdf:
    def __init__(self, path: Path, carried_opening: str) -> None:
        self._path = path
        self._carried_opening = SetRows(FIRST_NOTE_BASELINE, NOTE_SIZE, (carried_opening,))

    def write(self) -> Path:
        with pymupdf.open() as document:
            self._opening_page(document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT))
            self._carrying_page(document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT))
            document.save(self._path)
        return self._path

    @staticmethod
    def _opening_page(page) -> None:
        OPENING_BODY.draw_on(page)
        OPENING_BODY.raise_after(page, OPEN_NOTE_NUMBER)
        OPEN_NOTE.draw_on(page)
        OPEN_NOTE.raise_before(page, OPEN_NOTE_NUMBER)

    def _carrying_page(self, page) -> None:
        NEXT_BODY.draw_on(page)
        NEXT_BODY.raise_after(page, CLOSING_NOTE_NUMBER)
        self._carried_opening.draw_on(page)
        CARRIED.draw_on(page)
        CLOSING_NOTE.draw_on(page)
        CLOSING_NOTE.raise_before(page, CLOSING_NOTE_NUMBER)

    def engine_reading(self) -> DocumentBlocks:
        opening = PageBlocks(1, [
            OPENING_BODY.block_on(1, TEXT_KIND, f"<p>{OPENING_BODY.text}<sup>{OPEN_NOTE_NUMBER}</sup></p>"),
            OPEN_NOTE.block_on(1, FOOTNOTE_KIND, f"<p><sup>{OPEN_NOTE_NUMBER}</sup>{OPEN_NOTE.text}</p>")])
        carrying = PageBlocks(2, [
            NEXT_BODY.block_on(2, TEXT_KIND, f"<p>{NEXT_BODY.text}<sup>{CLOSING_NOTE_NUMBER}</sup></p>"),
            self._carried_opening.block_on(2, FOOTNOTE_KIND, f"<p>{self._carried_opening.text}</p>"),
            CARRIED.block_on(2, FOOTNOTE_KIND, f"<p>{CARRIED.text}</p>"),
            CLOSING_NOTE.block_on(2, FOOTNOTE_KIND, f"<p><sup>{CLOSING_NOTE_NUMBER}</sup>{CLOSING_NOTE.text}</p>")])
        return DocumentBlocks([opening, carrying])


class TestFootnoteContinuationLabelsNamingTheCarriedNote(unittest.TestCase):
    def definitions(self, carried_opening: str) -> dict[int, str]:
        with tempfile.TemporaryDirectory() as directory:
            pdf = CarriedNotePdf(Path(directory) / "carried.pdf", carried_opening)
            layer = TextLayer(pdf.write())
            try:
                inputs = StructureInputs(pdf.engine_reading(), [], WorkerReadings.none(), keep_everything())
                structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
                return {definition.label: definition.text for definition in structure.definitions()}
            finally:
                layer.close()

    def test_a_short_line_naming_the_carried_note_above_its_continuation_is_dropped(self) -> None:
        definitions = self.definitions(CONTINUATION_LABEL)
        self.assertEqual(f"{OPEN_NOTE.text} {CARRIED.text}", definitions[int(OPEN_NOTE_NUMBER)])

    def test_a_longer_opening_of_the_continuation_naming_the_number_is_kept(self) -> None:
        definitions = self.definitions(CARRIED_OPENING)
        self.assertEqual(f"{OPEN_NOTE.text} {CARRIED_OPENING} {CARRIED.text}", definitions[int(OPEN_NOTE_NUMBER)])


if __name__ == "__main__":
    unittest.main()
