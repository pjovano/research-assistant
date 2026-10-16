from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import PrintedWork, keep_everything, page_assembler
from test_extract_notes_lists_on_a_page_whose_text_layer_is_not_drawn import (
    BODY, BODY_BASELINE, FILE_PAGE, FIRST_NOTE_BASELINE, FONT, FONT_SIZE, INVISIBLE, LEFT, NOTE_PITCH, NOTES_TITLE,
    PAGE_HEIGHT, PAGE_WIDTH, TITLE_BASELINE, engine_block,
)
from _extract.blocks import HEADING_KIND, LIST_ITEM_KIND, TEXT_KIND, PageBlocks
from _extract.elements import Verbatim
from _extract.layer import TextLayer

NOTE_OPENING = "36. Cf. Nagel (1961), p. 94"
NOTE_CLOSING = "f."
NEXT_NOTE = "37. Ibid., p. 101."
ITEMS = [NOTE_OPENING, NOTE_CLOSING, NEXT_NOTE]


def item_baselines() -> list[tuple[float, str]]:
    return [(FIRST_NOTE_BASELINE + row * NOTE_PITCH, item) for row, item in enumerate(ITEMS)]


class ListedNotesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for baseline, text in [(BODY_BASELINE, BODY), (TITLE_BASELINE, NOTES_TITLE)] + item_baselines():
                page.insert_text((LEFT, baseline), text, fontsize=FONT_SIZE, fontname=FONT, render_mode=INVISIBLE)
            document.save(self._path)
        return self._path


class TestNotesListItemsTheEngineSplitsAtALineBreak(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(ListedNotesPdf(Path(directory.name) / "notes.pdf").write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))
        blocks = [engine_block(TEXT_KIND, BODY, BODY_BASELINE), engine_block(HEADING_KIND, NOTES_TITLE, TITLE_BASELINE)]
        blocks += [engine_block(LIST_ITEM_KIND, item, baseline) for baseline, item in item_baselines()]
        self.result = assembler.assemble(PageBlocks(FILE_PAGE, blocks), [], 1)

    def test_the_unnumbered_item_closes_the_numbered_item_above_it(self) -> None:
        items = [element.text for element in self.result.elements if isinstance(element, Verbatim)]
        self.assertEqual([f"- {NOTE_OPENING} {NOTE_CLOSING}", f"- {NEXT_NOTE}"], items)


if __name__ == "__main__":
    unittest.main()
