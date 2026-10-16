from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading, Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

LEFT = 70.0
RIGHT = 530.0
BASELINE = 340.0
BODY_SIZE = 10.0
LINE_HALF_HEIGHT = 8.0
PROSE = "Continuity means that the morphism preserves the order of positions."
PRINTED = f"h1 only depends on first parameter: {PROSE}"
NOTATION_LABEL = "<b><math>h_1</math> only depends on first parameter:</b>"
NUMBERED_LABEL = "<b>Lemma B.23</b>"


class RunInLabelPdf:
    def __init__(self, path: Path, label_html: str) -> None:
        self._path = path
        self._label_html = label_html

    def write(self) -> Path:
        with pymupdf.open() as document:
            document.new_page().insert_text((LEFT, BASELINE), PRINTED, fontsize=BODY_SIZE)
            document.save(self._path)
        return self._path

    def blocks(self) -> DocumentBlocks:
        box = (LEFT, BASELINE - BODY_SIZE - LINE_HALF_HEIGHT, RIGHT, BASELINE + LINE_HALF_HEIGHT)
        block = Block(1, TEXT_KIND, f"<p>{self._label_html} {PROSE}</p>", box, {}, "/page/1/Text/0")
        return DocumentBlocks([PageBlocks(1, [block])])


class TestBoldRunInLabelsWhoseOnlyNumberIsInsideTheirNotation(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, label_html: str) -> list[tuple[str, str]]:
        pdf = RunInLabelPdf(self._directory / "run-in.pdf", label_html)
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks(), [], WorkerReadings.none(), keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=frozenset({1}))
        return [(type(element).__name__, element.title if isinstance(element, Heading) else element.text)
                for element in NoteStructure(work, inputs).elements() if isinstance(element, (Heading, Paragraph))]

    def test_a_bold_label_numbered_only_by_a_subscript_in_its_notation_stays_in_the_paragraph(self) -> None:
        self.assertEqual([Paragraph.__name__], [kind for kind, _text in self._written(NOTATION_LABEL)])

    def test_a_bold_label_numbered_in_its_words_opens_a_heading(self) -> None:
        self.assertEqual((Heading.__name__, "Lemma B.23"), self._written(NUMBERED_LABEL)[0])


if __name__ == "__main__":
    unittest.main()
