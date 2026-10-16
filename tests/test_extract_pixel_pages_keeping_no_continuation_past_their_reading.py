from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import TEXT_KIND, Block, DocumentBlocks, PageBlocks

BOX = (72.0, 100.0, 520.0, 700.0)
CONTINUING_HTML = '<p class="has-continuation">the paragraph runs on to</p>'
ENDING_HTML = "<p>a paragraph that ends.</p>"
HEADER_KIND = "PageHeader"


def page(file_page: int, html: str) -> PageBlocks:
    header = Block(file_page, HEADER_KIND, "<p>Running head</p>", BOX, {}, f"/page/{file_page}/header")
    return PageBlocks(file_page, [header, Block(file_page, TEXT_KIND, html, BOX, {}, f"/page/{file_page}/text")])


def text_layer_reading(file_pages: range) -> DocumentBlocks:
    return DocumentBlocks([page(file_page, ENDING_HTML) for file_page in file_pages])


def continues_after(document: DocumentBlocks, file_page: int) -> bool:
    held = next(held for held in document.pages if held.file_page == file_page)
    return held.of_kind(TEXT_KIND)[-1].continues


class TestPixelPagesKeepingNoContinuationPastTheirReading(unittest.TestCase):
    def test_a_pixel_page_followed_by_a_text_layer_page_drops_the_engines_continuation(self) -> None:
        replaced = text_layer_reading(range(1, 7)).replaced([page(2, CONTINUING_HTML), page(5, CONTINUING_HTML)])
        self.assertFalse(continues_after(replaced, 2))

    def test_a_pixel_page_followed_by_a_pixel_page_keeps_the_engines_continuation(self) -> None:
        replaced = text_layer_reading(range(1, 7)).replaced([page(2, CONTINUING_HTML), page(3, CONTINUING_HTML)])
        self.assertEqual((True, False), (continues_after(replaced, 2), continues_after(replaced, 3)))

    def test_the_text_layer_pages_keep_their_own_reading(self) -> None:
        reading = DocumentBlocks([page(1, CONTINUING_HTML), page(2, ENDING_HTML)])
        self.assertTrue(continues_after(reading.replaced([page(2, ENDING_HTML)]), 1))


if __name__ == "__main__":
    unittest.main()
