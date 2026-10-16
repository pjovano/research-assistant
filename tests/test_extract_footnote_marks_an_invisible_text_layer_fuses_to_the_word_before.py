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
from _extract.elements import Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FILE_PAGE = 1
INVISIBLE = 3
FONT = "helv"
SIZE = 10.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
BODY_BASELINE = 100.0
NOTE_BASELINE = 560.0
NUMERAL = "7"
BEFORE_THE_MARK = "whether we do not, as Achinstein and Shapere do not"
AFTER_THE_MARK = "seems to be an open issue."
ENGINE_BODY = f"{BEFORE_THE_MARK}—{AFTER_THE_MARK}"
NOTE = "See Feyerabend and Kuhn for arguments relevant to this controversy."


@dataclass(frozen=True)
class InvisibleLayerPdf:
    path: Path
    body_line: str

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((LEFT, BODY_BASELINE), self.body_line, fontsize=SIZE, fontname=FONT,
                             render_mode=INVISIBLE)
            page.insert_text((LEFT, NOTE_BASELINE), f"{NUMERAL}{NOTE}", fontsize=SIZE, fontname=FONT,
                             render_mode=INVISIBLE)
            document.save(self.path)
        return self.path


def engine_block(kind: str, html: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(FILE_PAGE, kind, html, box, {}, f"/page/{FILE_PAGE}/{kind}/{baseline}")


class TestFootnoteMarksAnInvisibleTextLayerFusesToTheWordBefore(unittest.TestCase):
    def built(self, body_line: str) -> NoteStructure:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(InvisibleLayerPdf(Path(directory.name) / "scan.pdf", body_line).write())
        self.addCleanup(layer.close)
        reading = PageBlocks(FILE_PAGE, [engine_block(TEXT_KIND, f"<p>{ENGINE_BODY}</p>", BODY_BASELINE),
                                         engine_block(FOOTNOTE_KIND, f"<p><sup>{NUMERAL}</sup> {NOTE}</p>",
                                                      NOTE_BASELINE)])
        inputs = StructureInputs(DocumentBlocks([reading]), [], WorkerReadings.none(), keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=frozenset({FILE_PAGE}))
        return NoteStructure(work, inputs)

    def paragraphs(self, structure: NoteStructure) -> list[str]:
        return [element.text for element in structure.elements() if isinstance(element, Paragraph)]

    def test_a_note_numeral_the_layer_fuses_to_a_word_marks_that_word_in_the_engines_reading(self) -> None:
        structure = self.built(f"{BEFORE_THE_MARK}{NUMERAL} {AFTER_THE_MARK}")
        self.assertEqual([f"{BEFORE_THE_MARK}[^{NUMERAL}]—{AFTER_THE_MARK}"], self.paragraphs(structure))

    def test_the_note_is_paired_with_the_mark(self) -> None:
        structure = self.built(f"{BEFORE_THE_MARK}{NUMERAL} {AFTER_THE_MARK}")
        self.assertEqual([(int(NUMERAL), True)],
                         [(definition.label, definition.marked) for definition in structure.definitions()])

    def test_a_layer_printing_no_numeral_after_the_word_leaves_the_reading_unmarked(self) -> None:
        structure = self.built(f"{BEFORE_THE_MARK} {AFTER_THE_MARK}")
        self.assertEqual([ENGINE_BODY], self.paragraphs(structure))


if __name__ == "__main__":
    unittest.main()
