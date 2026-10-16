from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import CAPTION_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading, Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

BODY_FONT = "helv"
BOLD_FONT = "hebo"
CAPTION_SIZE = 9.0
LEFT = 60.0
RIGHT = 560.0
BASELINE = 170.0
LINE_HALF_HEIGHT = 8.0
LABEL = "Figure 4.2"
CAPTION_WORDS = " An impossible triangle"


class LabelledCaptionPdf:
    def __init__(self, path: Path, kind: str) -> None:
        self._path = path
        self._kind = kind

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((LEFT, BASELINE), LABEL, fontsize=CAPTION_SIZE, fontname=BOLD_FONT)
            words_left = LEFT + pymupdf.get_text_length(LABEL, BOLD_FONT, CAPTION_SIZE)
            page.insert_text((words_left, BASELINE), CAPTION_WORDS, fontsize=CAPTION_SIZE, fontname=BODY_FONT)
            document.save(self._path)
        return self._path

    def blocks(self) -> DocumentBlocks:
        box = (LEFT - 1, BASELINE - CAPTION_SIZE - LINE_HALF_HEIGHT, RIGHT, BASELINE + LINE_HALF_HEIGHT)
        block = Block(1, self._kind, f"<p><b>{LABEL}</b>{CAPTION_WORDS}</p>", box, {}, f"/page/1/{self._kind}/0")
        return DocumentBlocks([PageBlocks(1, [block])])


class TestCaptionsOpeningWithABoldNumberedLabel(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, kind: str) -> list[tuple[str, str]]:
        pdf = LabelledCaptionPdf(self._directory / "caption.pdf", kind)
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks(), [], WorkerReadings.none(), keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        return [(type(element).__name__, element.title if isinstance(element, Heading) else element.text)
                for element in elements if isinstance(element, (Heading, Paragraph))]

    def test_a_caption_opening_with_a_bold_numbered_label_stays_one_paragraph(self) -> None:
        written = self._written(CAPTION_KIND)
        self.assertEqual([Paragraph.__name__], [kind for kind, _text in written])

    def test_a_caption_keeps_its_label_before_its_words(self) -> None:
        (_kind, text), = self._written(CAPTION_KIND)
        self.assertLess(text.index("4.2"), text.index("impossible"))

    def test_a_text_block_opening_with_the_same_label_opens_a_heading(self) -> None:
        written = self._written(TEXT_KIND)
        self.assertEqual((Heading.__name__, LABEL), written[0])


if __name__ == "__main__":
    unittest.main()
