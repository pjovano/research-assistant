from __future__ import annotations

import dataclasses
import unittest

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import (BODY_BOX, FOOT_BOX, BlockPlace, BoxedLayer, FakeLayer, RunSetting, keep_everything,
                               page_assembler, positioned)
from _extract.box import Box
from _extract.blocks import EQUATION_KIND, FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import LayerChar, OverlappedSpaces
from _extract.strays import StrayFootnotes
from _extract.structure import Paragraph

TWIN_BOX = (0.0, 101.0, 100.0, 110.0)
ENGINE_FOOTNOTE_BOX = (0.0, 101.0, 100.0, 111.0)
MARKED_BODY = "<p>The object is known<sup>31</sup> as it is.</p>"


class PagedLayer(FakeLayer):
    def __init__(self, pages: dict[int, list[LayerChar]]) -> None:
        super().__init__()
        self._pages = pages

    def chars_in(self, file_page: int, bbox) -> list[LayerChar]:
        return [char for char in self._pages.get(file_page, []) if Box.of(bbox).contains(char.center)]


def assembled(blocks: list[Block]):
    assembler = page_assembler(FakeLayer(), keep_everything())
    return assembler.assemble(PageBlocks(1, blocks), [], 1)


def placed(kind: str, html: str, place: BlockPlace) -> Block:
    return place.block(kind, html)


def paragraph_texts(result) -> list[str]:
    return [element.text for element in result.elements if isinstance(element, Paragraph)]


class TestStrayFootnotes(unittest.TestCase):
    def test_a_numbered_text_block_below_the_body_defines_the_mark_it_names_under_its_printed_numeral(self) -> None:
        result = assembled([placed(TEXT_KIND, MARKED_BODY, BlockPlace(BODY_BOX, 0)),
                            placed(TEXT_KIND, "<p>31 erkennt.</p>", BlockPlace(FOOT_BOX, 1))])
        self.assertEqual((["The object is known[^31] as it is."], "[^31]: erkennt."),
                         (paragraph_texts(result), result.definitions[0].rendered()))

    def test_stacked_numbered_text_blocks_below_the_body_each_define_their_mark_under_its_printed_numeral(self) -> None:
        result = assembled([placed(TEXT_KIND, "<p>Known<sup>10</sup> and given<sup>11</sup>.</p>",
                                   BlockPlace(BODY_BOX, 0)),
                            placed(TEXT_KIND, "<p><b>10</b> Longuenesse (2005).</p>",
                                   BlockPlace((0.0, 82.0, 100.0, 90.0), 1)),
                            placed(TEXT_KIND, "<p><b>11</b> Keller (1998).</p>", BlockPlace(FOOT_BOX, 2))])
        self.assertEqual((["Known[^10] and given[^11]."], ["[^10]: Longuenesse (2005).", "[^11]: Keller (1998)."]),
                         (paragraph_texts(result), [definition.rendered() for definition in result.definitions]))

    def test_a_block_below_a_stray_footnote_the_engine_also_read_as_one_continues_it_under_its_printed_numeral(
            self) -> None:
        result = assembled([placed(TEXT_KIND, MARKED_BODY, BlockPlace(BODY_BOX, 0)),
                            placed(TEXT_KIND, "<p>31 erkennt.</p>", BlockPlace(FOOT_BOX, 1)),
                            placed(TEXT_KIND, "<p>Der Raum als Gegenstand.</p>", BlockPlace(TWIN_BOX, 2)),
                            placed(FOOTNOTE_KIND, "<p></p>", BlockPlace(ENGINE_FOOTNOTE_BOX, 3))])
        self.assertEqual((["The object is known[^31] as it is."], "[^31]: erkennt. Der Raum als Gegenstand."),
                         (paragraph_texts(result), result.definitions[0].rendered()))

    def test_a_block_the_engine_also_read_as_a_footnote_stays_a_paragraph_under_no_stray_footnote(self) -> None:
        result = assembled([placed(TEXT_KIND, MARKED_BODY, BlockPlace(BODY_BOX, 0)),
                            placed(TEXT_KIND, "<p>There is, however, some truth.</p>", BlockPlace(TWIN_BOX, 1)),
                            placed(FOOTNOTE_KIND, "<p></p>", BlockPlace(ENGINE_FOOTNOTE_BOX, 2))])
        self.assertIn("There is, however, some truth.", paragraph_texts(result))

    def test_an_empty_block_doubling_a_footnote_the_engine_read_leaves_the_text_to_it_under_its_printed_numeral(
            self) -> None:
        layer = BoxedLayer(positioned("31 erkennt.", RunSetting(0.0, 96.0, 0))
                           + positioned("Der Raum.", RunSetting(0.0, 108.0, 1)))
        assembler = page_assembler(layer, keep_everything())
        result = assembler.assemble(PageBlocks(1, [placed(TEXT_KIND, MARKED_BODY, BlockPlace(BODY_BOX, 0)),
                                                   placed(FOOTNOTE_KIND, "<p>31 erkennt.</p>", BlockPlace(FOOT_BOX, 1)),
                                                   placed(TEXT_KIND, "", BlockPlace(TWIN_BOX, 2)),
                                                   placed(FOOTNOTE_KIND, "<p>Der Raum.</p>",
                                                          BlockPlace(ENGINE_FOOTNOTE_BOX, 3))]),
                                    [], 1)
        self.assertEqual((["The object is known[^31] as it is."], "[^31]: erkennt. Der Raum."),
                         (paragraph_texts(result), result.definitions[0].rendered()))

    def test_a_block_in_note_type_between_body_and_notes_continues_the_carried_note_under_its_printed_numeral(
            self) -> None:
        carried_over = (positioned("Body prose.", RunSetting(0.0, 40.0, 0))
                        + positioned("carried over.", RunSetting(0.0, 86.0, 1, size=8.0)))
        layer = PagedLayer({2: carried_over + positioned("32 Keller.", RunSetting(0.0, 96.0, 2, size=8.0))})
        assembler = page_assembler(layer, keep_everything())
        assembler.assemble(PageBlocks(1, [placed(TEXT_KIND, MARKED_BODY, BlockPlace(BODY_BOX, 0)),
                                          placed(FOOTNOTE_KIND, "<p>31 erkennt.</p>", BlockPlace(FOOT_BOX, 1))]), [], 1)
        result = assembler.assemble(PageBlocks(2, [placed(TEXT_KIND, "", BlockPlace((0.0, 0.0, 100.0, 50.0), 0)),
                                                   placed(TEXT_KIND, "", BlockPlace((0.0, 78.0, 100.0, 88.0), 1)),
                                                   placed(FOOTNOTE_KIND, "", BlockPlace(FOOT_BOX, 2))]), [], 1)
        self.assertEqual((["Body prose."], ["[^31]: erkennt. carried over."], ["[^1]: 32. Keller."]),
                         (paragraph_texts(result), [definition.rendered() for definition in result.continuations],
                          [definition.rendered() for definition in result.definitions]))

    def test_two_stacked_blocks_in_note_type_above_the_notes_continue_the_carried_note_under_its_printed_numeral(
            self) -> None:
        carried = (positioned("Body prose.", RunSetting(0.0, 30.0, 0))
                   + positioned("carried over", RunSetting(0.0, 66.0, 1, size=8.0))
                   + positioned("and on.", RunSetting(0.0, 80.0, 2, size=8.0))
                   + positioned("32 Keller.", RunSetting(0.0, 96.0, 3, size=8.0)))
        assembler = page_assembler(PagedLayer({2: carried}), keep_everything())
        assembler.assemble(PageBlocks(1, [placed(TEXT_KIND, MARKED_BODY, BlockPlace(BODY_BOX, 0)),
                                          placed(FOOTNOTE_KIND, "<p>31 erkennt.</p>", BlockPlace(FOOT_BOX, 1))]), [], 1)
        result = assembler.assemble(PageBlocks(2, [placed(TEXT_KIND, "", BlockPlace((0.0, 0.0, 100.0, 40.0), 0)),
                                                   placed(TEXT_KIND, "", BlockPlace((0.0, 58.0, 100.0, 70.0), 1)),
                                                   placed(TEXT_KIND, "", BlockPlace((0.0, 72.0, 100.0, 86.0), 2)),
                                                   placed(FOOTNOTE_KIND, "", BlockPlace(FOOT_BOX, 3))]), [], 1)
        self.assertEqual(["[^31]: erkennt. carried over and on."],
                         [definition.rendered() for definition in result.continuations][-1:])

    def test_body_text_above_the_notes_in_type_unlike_the_notes_stays_body_text(self) -> None:
        layer = PagedLayer({1: positioned("By R. S.", RunSetting(0.0, 20.0, 0, size=14.0))
                               + positioned("Body prose.", RunSetting(0.0, 60.0, 1))
                            + positioned("31 erkennt.", RunSetting(0.0, 96.0, 2, size=8.0))})
        assembler = page_assembler(layer, keep_everything())
        result = assembler.assemble(PageBlocks(1, [placed(TEXT_KIND, "", BlockPlace((0.0, 5.0, 100.0, 25.0), 0)),
                                                   placed(TEXT_KIND, "", BlockPlace((0.0, 45.0, 100.0, 88.0), 1)),
                                                   placed(FOOTNOTE_KIND, "", BlockPlace(FOOT_BOX, 2))]), [], 1)
        self.assertEqual((["By R. S.", "Body prose."], ["[^1]: 31. erkennt."]),
                         (paragraph_texts(result), [definition.rendered() for definition in result.definitions]))

    def test_a_numbered_block_is_judged_by_the_text_layer_when_the_engine_left_it_empty(self) -> None:
        body = placed(TEXT_KIND, MARKED_BODY, BlockPlace(BODY_BOX, 0))
        emptied = placed(TEXT_KIND, "<p></p>", BlockPlace(FOOT_BOX, 1))
        strays = StrayFootnotes([body, emptied], [MARKED_BODY, "<p><b>31</b> erkennt.</p>"])
        self.assertEqual([TEXT_KIND, FOOTNOTE_KIND], [block.kind for block in strays.reclassified([body, emptied])])

    def test_a_numbered_block_between_body_text_stays_a_paragraph(self) -> None:
        result = assembled([placed(TEXT_KIND, MARKED_BODY, BlockPlace(BODY_BOX, 0)),
                            placed(TEXT_KIND, "<p>31 erkennt.</p>", BlockPlace((0.0, 82.0, 100.0, 88.0), 1)),
                            placed(TEXT_KIND, "<p>The body goes on.</p>", BlockPlace(FOOT_BOX, 2))])
        self.assertIn("31 erkennt.", paragraph_texts(result))

    def test_an_equation_block_of_glosses_below_the_body_is_a_footnote_under_its_printed_numeral(self) -> None:
        result = assembled([placed(TEXT_KIND, MARKED_BODY, BlockPlace(BODY_BOX, 0)),
                            placed(EQUATION_KIND, "<p>31 der Grund.</p>", BlockPlace(FOOT_BOX, 1))])
        self.assertEqual(["The object is known[^31] as it is."], paragraph_texts(result))

    def test_a_numbered_block_whose_number_no_mark_names_stays_a_paragraph(self) -> None:
        result = assembled([placed(TEXT_KIND, MARKED_BODY, BlockPlace(BODY_BOX, 0)),
                            placed(TEXT_KIND, "<p>12 apostles went out.</p>", BlockPlace(FOOT_BOX, 1))])
        self.assertIn("12 apostles went out.", paragraph_texts(result))

    def test_a_numbered_block_beneath_a_notes_heading_stays_an_endnote_though_the_page_marks_it(self) -> None:
        result = assembled([placed(TEXT_KIND, "<p>The problem will remain.<sup>11</sup></p>", BlockPlace(BODY_BOX, 0)),
                            placed(HEADING_KIND, "<h2>NOTES</h2>", BlockPlace((0.0, 81.0, 100.0, 84.0), 1)),
                            placed(TEXT_KIND, "<p>10 Shoemaker (1982).</p>", BlockPlace((0.0, 85.0, 100.0, 89.0), 2)),
                            placed(TEXT_KIND, "<p>11 An earlier version.</p>", BlockPlace(FOOT_BOX, 3))])
        self.assertEqual(([], "11 An earlier version."), (result.definitions, paragraph_texts(result)[-1]))

    def test_a_numbered_block_above_body_text_stays_a_paragraph(self) -> None:
        result = assembled([placed(TEXT_KIND, "<p>31 erkennt.</p>", BlockPlace(BODY_BOX, 0)),
                            placed(TEXT_KIND, MARKED_BODY, BlockPlace(FOOT_BOX, 1))])
        self.assertIn("31 erkennt.", paragraph_texts(result))


if __name__ == "__main__":
    unittest.main()


class TestSpaceDrawnOverTheCharacterBefore(unittest.TestCase):
    def _chars(self, *placed: tuple[str, float, float]) -> list[LayerChar]:
        return [LayerChar(char, ((left + right) / 2, 5.0), False, 10.0, bbox=(left, 0.0, right, 10.0))
                for char, left, right in placed]

    def _text(self, *placed: tuple[str, float, float]) -> str:
        return "".join(char.char for char in OverlappedSpaces().dropped(self._chars(*placed)))

    def test_a_space_that_does_not_advance_past_the_character_before_is_dropped(self) -> None:
        self.assertEqual("The",
                         self._text(("T", 84.6, 96.1), ("h", 96.1, 101.9), (" ", 90.3, 92.8), ("e", 96.1, 100.6)))

    def test_a_space_that_advances_past_the_character_before_is_a_word_break(self) -> None:
        self.assertEqual(". T", self._text((".", 80.3, 82.8), (" ", 82.8, 85.2), ("T", 84.6, 96.1)))

    def test_a_space_on_a_line_of_its_own_is_kept(self) -> None:
        chars = self._chars(("a", 10.0, 14.0), (" ", 8.0, 10.0))
        moved = [chars[0], dataclasses.replace(chars[1], line=1)]
        self.assertEqual("a ", "".join(char.char for char in OverlappedSpaces().dropped(moved)))
