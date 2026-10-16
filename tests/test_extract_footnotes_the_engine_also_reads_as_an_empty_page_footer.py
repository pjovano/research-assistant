from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_SENTENCE, FooterCase, NotedPage, body_block, notes_block,
)
from _extract.blocks import FOOTER_KIND, FOOTNOTE_KIND, PageBlocks

PRINTED_NOTE = "Good proposes a theory of 'reasonable' behavior in complex circumstances."
ENGINE_NOTE = "Good proposes a theory of <sup>&amp;#</sup>x27;reasonable' behavior in complex circumstances."


class TestFootnotesTheEngineAlsoReadsAsAnEmptyPageFooter(FooterCase):
    def setUp(self) -> None:
        pages = [NotedPage(FIRST_SENTENCE, "1", (f"1 {PRINTED_NOTE}",))]
        engine_pages = [PageBlocks(1, [body_block(1, FIRST_SENTENCE, "<sup>1</sup>"),
                                       notes_block(1, FOOTER_KIND, ""),
                                       notes_block(1, FOOTNOTE_KIND, f"<sup>1</sup> {ENGINE_NOTE}")])]
        self.structure = self.built(pages, engine_pages)

    def test_the_footnote_is_written_from_the_text_layer_the_empty_footer_leaves_to_it(self) -> None:
        self.assertEqual([PRINTED_NOTE], [definition.text for definition in self.structure.definitions()])


if __name__ == "__main__":
    unittest.main()
