from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.twins import EngineTwins
from _extract_fixtures import keep_everything, page_assembler

FONT_SIZE = 9.0
LINE_PITCH = 11.0
LEFT = 40.0
FIRST_BASELINE = 100.0
WORDS = ["Alpha", "Beta", "Gamma"]
FIRST_BOX = (38.0, 89.0, 70.0, 103.0)
STRADDLING_BOX = (38.0, 97.0, 64.0, 108.5)
REACHING_PAST_BOX = (38.0, 97.0, 64.0, 140.0)
SECOND_BOX = (38.0, 103.0, 70.0, 115.0)
THIRD_BOX = (38.0, 116.0, 75.0, 125.0)
ABOVE_GAP_BOX = (38.0, 89.0, 70.0, 100.0)
OVER_GAP_BOX = (38.0, 97.0, 64.0, 118.0)
BELOW_GAP_BOX = (38.0, 116.0, 75.0, 125.0)
EMPTY_ID = "/page/1/Text/1"


class StackedShortLinesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for row, word in enumerate(WORDS):
                page.insert_text((LEFT, FIRST_BASELINE + row * LINE_PITCH), word, fontname="helv", fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path


def text_block(html: str, box: tuple, identifier: str) -> Block:
    return Block(1, TEXT_KIND, html, box, {}, identifier)


def blocks_around(empty_box: tuple) -> list[Block]:
    return [text_block(f"<p>{WORDS[0]}</p>", FIRST_BOX, "/page/1/Text/0"),
            text_block("<p></p>", empty_box, EMPTY_ID),
            text_block(f"<p>{WORDS[1]}</p>", SECOND_BOX, "/page/1/Text/2"),
            text_block(f"<p>{WORDS[2]}</p>", THIRD_BOX, "/page/1/Text/3")]


def blocks_across_a_gap() -> list[Block]:
    return [text_block(f"<p>{WORDS[0]}</p>", ABOVE_GAP_BOX, "/page/1/Text/0"),
            text_block("<p></p>", OVER_GAP_BOX, EMPTY_ID),
            text_block(f"<p>{WORDS[2]}</p>", BELOW_GAP_BOX, "/page/1/Text/3")]


def identifiers(blocks: list[Block]) -> list[str]:
    return [block.identifier for block in blocks]


class TestEmptyBlockStraddlingTwoReadBlocks(unittest.TestCase):
    def test_an_empty_block_lying_within_the_read_blocks_it_overlaps_yields_to_them(self) -> None:
        blocks = blocks_around(STRADDLING_BOX)
        self.assertNotIn(EMPTY_ID, identifiers(EngineTwins(blocks).without(blocks)))

    def test_an_empty_block_reaching_past_the_read_blocks_it_overlaps_is_kept(self) -> None:
        blocks = blocks_around(REACHING_PAST_BOX)
        self.assertIn(EMPTY_ID, identifiers(EngineTwins(blocks).without(blocks)))

    def test_an_empty_block_over_a_gap_between_the_read_blocks_it_overlaps_is_kept(self) -> None:
        blocks = blocks_across_a_gap()
        self.assertIn(EMPTY_ID, identifiers(EngineTwins(blocks).without(blocks)))

    def test_the_line_an_empty_block_straddles_is_written_once(self) -> None:
        self.assertEqual(WORDS, self._written_words(blocks_around(STRADDLING_BOX)))

    def test_the_line_in_a_gap_under_an_empty_block_is_written(self) -> None:
        self.assertEqual(WORDS, self._written_words(blocks_across_a_gap()))

    def _written_words(self, blocks: list[Block]) -> list[str]:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        layer = TextLayer(StackedShortLinesPdf(directory / "stacked.pdf").write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything())
        elements = assembler.assemble(PageBlocks(1, blocks), [], None).elements[1:]
        return " ".join(element.text for element in elements).split()


if __name__ == "__main__":
    unittest.main()
