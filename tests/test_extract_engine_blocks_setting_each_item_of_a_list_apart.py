from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import PrintedWork, keep_everything, page_assembler
from _extract.blocks import Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Paragraph

FILE_PAGE = 1
FONT = "tiro"
FONT_SIZE = 10.0
LINE_PITCH = 14.0
FIRST_BASELINE = 100.0
MARGIN = 50.0
HANGING_INDENT = 20.0
PAGE_WIDTH, PAGE_HEIGHT = 400.0, 600.0
SUBLEVEL = 2
BULLET = "•"
BULLETED_ITEMS = ["N, about ten to the thirty-six, the ratio of the forces;",
                  "E, about 0.007, the efficiency of fusion;",
                  "Omega, the ratio of the actual density to the critical density."]
LABELLED_ITEMS = [("E, SL", "Encyclopédie, I. La science de la logique, Paris, Vrin, 1970."),
                  ("VG", "Die Vernunft in der Geschichte, Hambourg, Meiner, 1963."),
                  ("CE", "Cours d'esthétique, Paris, Aubier, 1997.")]


class ItemListPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, rows: list[tuple[str, str]]) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for row, (label, text) in enumerate(rows):
                baseline = FIRST_BASELINE + row * LINE_PITCH
                page.insert_text((MARGIN, baseline), label, fontsize=FONT_SIZE, fontname=FONT)
                page.insert_text((MARGIN + HANGING_INDENT, baseline), text, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def list_group(html: str, rows: int) -> Block:
    bottom = FIRST_BASELINE + rows * LINE_PITCH
    return Block(FILE_PAGE, "ListGroup", html, (MARGIN, FIRST_BASELINE - LINE_PITCH, PAGE_WIDTH - MARGIN, bottom),
                 {}, f"/page/{FILE_PAGE}/ListGroup/0")


class TestEngineBlocksSettingEachItemOfAListApart(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "items.pdf"

    def paragraphs(self, rows: list[tuple[str, str]], html: str) -> list[str]:
        layer = TextLayer(ItemListPdf(self._path).write(rows))
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))
        elements = assembler.assemble(PageBlocks(FILE_PAGE, [list_group(html, len(rows))]), [], SUBLEVEL).elements
        return [element.text for element in elements if isinstance(element, Paragraph)]

    def test_a_list_group_setting_each_bulleted_item_in_its_own_list_element_writes_one_paragraph_each(
            self) -> None:
        html = "<ul>" + "".join(f"<li>{BULLET} {item}</li>" for item in BULLETED_ITEMS) + "</ul>"
        rows = [(BULLET, item) for item in BULLETED_ITEMS]
        self.assertEqual([f"{BULLET} {item}" for item in BULLETED_ITEMS], self.paragraphs(rows, html))

    def test_a_list_group_setting_each_labelled_entry_in_its_own_paragraph_element_writes_one_paragraph_each(
            self) -> None:
        html = "".join(f"<p><b>{label}</b> {text}</p>" for label, text in LABELLED_ITEMS)
        expected = [f"**{label}** {text}" for label, text in LABELLED_ITEMS]
        self.assertEqual(expected, self.paragraphs(LABELLED_ITEMS, html))


if __name__ == "__main__":
    unittest.main()
