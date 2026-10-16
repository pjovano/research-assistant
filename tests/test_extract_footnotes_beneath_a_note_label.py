from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer

FONT = "cour"
FONT_SIZE = 9.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
BODY = "The body raises a first mark.1 It raises a second.2"
BODY_HTML = "<p>The body raises a first mark.<sup>1</sup> It raises a second.<sup>2</sup></p>"
LABEL_TEXT = "The rows give the counts of each year."
FOOTNOTES = ["1 The first footnote.", "2 The second footnote."]
BODY_BASELINE = 100.0
LABEL_BASELINE = 300.0
LABEL_TEXT_BASELINE = 312.0
FIRST_NOTE_BASELINE = 330.0
NOTE_PITCH = 20.0
LINE_HALF_HEIGHT = 8.0


def footnote_lines() -> list[tuple[float, str]]:
    return [(FIRST_NOTE_BASELINE + row * NOTE_PITCH, note) for row, note in enumerate(FOOTNOTES)]


class LabelledPagePdf:
    def __init__(self, path: Path, label: str) -> None:
        self._path = path
        self._label = label

    def write(self) -> Path:
        lines = [(BODY_BASELINE, BODY), (LABEL_BASELINE, self._label), (LABEL_TEXT_BASELINE, LABEL_TEXT)]
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for baseline, text in lines + footnote_lines():
                page.insert_text((LEFT, baseline), text, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def engine_block(kind: str, html: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(1, kind, html, box, {}, f"/page/1/{kind}/{baseline}")


def engine_reading(label_kind: str, label: str) -> list[Block]:
    notes = [engine_block(FOOTNOTE_KIND, f"<p>{note}</p>", baseline) for baseline, note in footnote_lines()]
    return [engine_block(TEXT_KIND, BODY_HTML, BODY_BASELINE),
            engine_block(label_kind, f"<p>{label}</p>", LABEL_BASELINE),
            engine_block(TEXT_KIND, f"<p>{LABEL_TEXT}</p>", LABEL_TEXT_BASELINE)] + notes


class TestFootnotesBeneathANoteLabel(unittest.TestCase):
    def _definitions(self, label_kind: str, label: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            layer = TextLayer(LabelledPagePdf(Path(directory) / "labelled.pdf", label).write())
            try:
                assembler = page_assembler(layer, keep_everything())
                result = assembler.assemble(PageBlocks(1, engine_reading(label_kind, label)), [], 1)
            finally:
                layer.close()
        return [definition.text for definition in result.definitions]

    def test_footnotes_beneath_a_note_label_closing_with_a_colon_stay_footnotes(self) -> None:
        self.assertEqual(2, len(self._definitions(TEXT_KIND, "Note:")))

    def test_footnotes_beneath_a_notes_heading_block_closing_with_a_period_are_entries_of_the_notes_list(
            self) -> None:
        self.assertEqual([], self._definitions(HEADING_KIND, "NOTES."))


if __name__ == "__main__":
    unittest.main()
