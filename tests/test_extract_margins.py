from __future__ import annotations

import dataclasses
import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import TEXT_KIND, Block
from _extract.layerlines import PageLines
from _extract.blocks import PageBlocks
from _extract_fixtures import ADVANCE, FakeLayer, PrintedWork, RunSetting, keep_everything, page_assembler, positioned

PAGE_BOX = (0.0, 0.0, 500.0, 200.0)
COLUMN_LEFT = 60.0
BASELINE = 100.0
MARGIN_SIZE = 8.0
MARGIN_LEFT = 30.0
MARGIN_GAP = 10.0
CLOSE_GAP = 8.0
LINE = "the general character of his complaint"


def page_block() -> Block:
    return Block(1, TEXT_KIND, "", PAGE_BOX, {}, "/page/1/Text/0")


def bold(chars: list) -> list:
    return [dataclasses.replace(char, bold=True) for char in chars]


def row_texts(chars: list) -> list[str]:
    rows = PageLines(FakeLayer(chars), 1, [page_block()]).of(page_block())
    return ["".join(char.char for char in row) for row in rows]


class TestMarginalNumbers(unittest.TestCase):
    def test_a_bold_number_in_the_margin_beside_a_line_opens_that_line(self) -> None:
        margin = bold(positioned("10", RunSetting(MARGIN_LEFT, BASELINE, 1, size=MARGIN_SIZE)))
        self.assertEqual([f"10 {LINE}"], row_texts(positioned(LINE, RunSetting(COLUMN_LEFT, BASELINE, 0)) + margin))

    def test_a_number_in_the_right_margin_opens_the_line_beside_it(self) -> None:
        column_right = COLUMN_LEFT + len(LINE) * ADVANCE
        margin = bold(positioned("185", RunSetting(column_right + MARGIN_GAP, BASELINE, 1, size=MARGIN_SIZE)))
        self.assertEqual([f"185 {LINE}"], row_texts(positioned(LINE, RunSetting(COLUMN_LEFT, BASELINE, 0)) + margin))

    def test_a_number_in_the_margin_set_in_the_columns_own_style_is_kept(self) -> None:
        hanging = positioned("14", RunSetting(MARGIN_LEFT, BASELINE, 1))
        self.assertEqual([f"14{LINE}"], row_texts(positioned(LINE, RunSetting(COLUMN_LEFT, BASELINE, 0)) + hanging))

    def test_a_number_set_close_against_the_column_is_kept(self) -> None:
        mark = bold(positioned("7", RunSetting(COLUMN_LEFT - CLOSE_GAP, BASELINE, 1, size=MARGIN_SIZE)))
        self.assertEqual([f"7{LINE}"], row_texts(positioned(LINE, RunSetting(COLUMN_LEFT, BASELINE, 0)) + mark))


FOOTER_BASELINE = 180.0
FOOTER_TEXT = "the publisher's copyright line printed at the foot"


def body_block() -> Block:
    return Block(1, TEXT_KIND, "", (0.0, 0.0, 500.0, 160.0), {}, "/page/1/Text/0")


FOOTER_BOX = (0.0, 170.0, 500.0, 190.0)


def footer_block() -> Block:
    return Block(1, "PageFooter", "", FOOTER_BOX, {}, "/page/1/PageFooter/0")


def shadow_block() -> Block:
    return Block(1, TEXT_KIND, "", FOOTER_BOX, {}, "/page/1/Text/1")


class TestFurnitureLines(unittest.TestCase):
    def _rows_of(self, chars: list, wanted: Block) -> list[str]:
        blocks = [body_block(), shadow_block(), footer_block()]
        rows = PageLines(FakeLayer(chars), 1, blocks).of(wanted)
        return ["".join(char.char for char in row) for row in rows]

    def _page(self) -> list:
        return (positioned(LINE, RunSetting(COLUMN_LEFT, BASELINE, 0))
                + positioned(FOOTER_TEXT, RunSetting(COLUMN_LEFT, FOOTER_BASELINE, 1)))

    def test_a_line_a_furniture_block_shares_with_a_content_block_belongs_to_the_furniture(self) -> None:
        self.assertEqual([], self._rows_of(self._page(), shadow_block()))

    def test_the_body_block_keeps_its_own_line(self) -> None:
        self.assertEqual([LINE], self._rows_of(self._page(), body_block()))


class TestFurnitureInTheBody(unittest.TestCase):
    def test_a_furniture_line_is_not_written_into_the_body_paragraph(self) -> None:
        chars = (positioned(LINE, RunSetting(COLUMN_LEFT, BASELINE, 0))
                 + positioned(FOOTER_TEXT, RunSetting(COLUMN_LEFT, FOOTER_BASELINE, 1)))
        assembler = page_assembler(FakeLayer(chars), keep_everything())
        result = assembler.assemble(PageBlocks(1, [body_block(), shadow_block(), footer_block()]), [], 2)
        self.assertEqual([LINE], [element.text for element in result.elements[1:]])


class TestFurnitureTextElsewhere(unittest.TestCase):
    def _texts(self, kind: str) -> list[str]:
        stray = Block(1, kind, f"<p>{FOOTER_TEXT}</p>", FOOTER_BOX, {}, "/page/1/stray/0")
        chars = (positioned(LINE, RunSetting(COLUMN_LEFT, BASELINE, 0))
                 + positioned(FOOTER_TEXT, RunSetting(COLUMN_LEFT, FOOTER_BASELINE, 1)))
        assembler = page_assembler(FakeLayer(chars), keep_everything(), PrintedWork(furniture=[FOOTER_TEXT]))
        result = assembler.assemble(PageBlocks(1, [body_block(), stray]), [], 2)
        return [element.text for element in result.elements[1:]]

    def test_a_block_the_works_furniture_names_is_not_written_into_the_body(self) -> None:
        self.assertEqual([LINE], self._texts(TEXT_KIND))

    def test_a_footnote_block_the_works_furniture_names_is_not_written_either(self) -> None:
        self.assertEqual([LINE], self._texts("Footnote"))


RIGHT_COLUMN_LEFT = 330.0
COLUMN_PITCH = 14.0


class TestTwoColumnBlocks(unittest.TestCase):
    def _rows(self, right_left: float) -> list[str]:
        chars = []
        for row in range(3):
            baseline = BASELINE + row * COLUMN_PITCH
            chars += positioned(f"left line {row} of the column that runs down",
                                RunSetting(COLUMN_LEFT, baseline, row * 2))
            chars += positioned(f"right line {row} of the column beside it",
                                RunSetting(right_left, baseline, row * 2 + 1))
        body = Block(1, TEXT_KIND, "", (0.0, 0.0, 620.0, 200.0), {}, "/page/1/Text/0")
        rows = PageLines(FakeLayer(chars), 1, [body]).of(body)
        return ["".join(char.char for char in row) for row in rows]

    def test_a_block_holding_two_columns_is_read_one_column_at_a_time(self) -> None:
        rows = self._rows(RIGHT_COLUMN_LEFT)
        self.assertEqual([row.startswith("left") for row in rows], [True, True, True, False, False, False])

    def test_columns_with_no_gutter_between_them_are_read_as_one(self) -> None:
        touching = COLUMN_LEFT + len("left line 0 of the column that runs down") * ADVANCE
        self.assertTrue(all(row.startswith("left") for row in self._rows(touching)))


class TestLineOwnership(unittest.TestCase):
    def test_a_line_equally_inside_two_stacked_blocks_belongs_to_the_earlier_block(self) -> None:
        earlier = Block(1, TEXT_KIND, "", PAGE_BOX, {}, "/page/1/Text/0")
        duplicate = Block(1, TEXT_KIND, "", PAGE_BOX, {}, "/page/1/Text/1")
        lines = PageLines(FakeLayer(positioned(LINE, RunSetting(COLUMN_LEFT, BASELINE, 0))), 1, [earlier, duplicate])
        self.assertEqual((1, 0), (len(lines.of(earlier)), len(lines.of(duplicate))))


if __name__ == "__main__":
    unittest.main()
