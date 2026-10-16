from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import TEXT_KIND, Block
from _extract.elements import Heading, PageMarker, Paragraph
from _extract.indents import ParagraphIndents, WorkLayout
from _extract.layerlines import PageLines
from _extract.writer import NoteWriter
from _extract_fixtures import FakeLayer, RunSetting, positioned

COLUMN_LEFT = 60.0
INDENTED_LEFT = 71.0
TOP_BOX = (0.0, 0.0, 400.0, 50.0)
LOWER_BOX = (0.0, 60.0, 400.0, 120.0)
LINE = "then the sentence runs on as prose"
ROW_PITCH = 15.0
TOP_BASELINE = 20.0
LOWER_BASELINE = 80.0


def text_block(box: tuple, index: int) -> Block:
    return Block(1, TEXT_KIND, "", box, {}, f"/page/1/Text/{index}")


def two_line_paragraph(first_left: float, top_baseline: float, first_line_number: int) -> list:
    return (positioned(LINE, RunSetting(first_left, top_baseline, first_line_number))
            + positioned(LINE, RunSetting(COLUMN_LEFT, top_baseline + ROW_PITCH, first_line_number + 1)))


def two_block_indents(top_first_left: float, lower_first_left: float) -> tuple[ParagraphIndents, Block]:
    chars = (two_line_paragraph(top_first_left, TOP_BASELINE, 0)
             + two_line_paragraph(lower_first_left, LOWER_BASELINE, 2))
    blocks = [text_block(TOP_BOX, 0), text_block(LOWER_BOX, 1)]
    return ParagraphIndents(PageLines(FakeLayer(chars), 1, blocks), blocks), blocks[0]


def resumes(top_first_left: float, lower_first_left: float) -> bool:
    indents, top = two_block_indents(top_first_left, lower_first_left)
    return indents.resumes(top)


def lone_block_resumes(work_indents_openings: bool) -> bool:
    block = text_block(TOP_BOX, 0)
    lines = PageLines(FakeLayer(two_line_paragraph(COLUMN_LEFT, TOP_BASELINE, 0)), 1, [block])
    return ParagraphIndents(lines, [block], WorkLayout(work_indents_openings)).resumes(block)


class TestParagraphIndents(unittest.TestCase):
    def test_a_flush_block_on_a_page_that_indents_its_openings_resumes_a_paragraph(self) -> None:
        self.assertTrue(resumes(COLUMN_LEFT, INDENTED_LEFT))

    def test_an_indented_block_opens_a_paragraph(self) -> None:
        self.assertFalse(resumes(INDENTED_LEFT, INDENTED_LEFT))

    def test_a_flush_block_on_a_page_with_no_indented_openings_is_not_taken_to_resume(self) -> None:
        self.assertFalse(resumes(COLUMN_LEFT, COLUMN_LEFT))

    def test_a_page_with_an_indented_opening_reports_that_it_indents_openings(self) -> None:
        indents, _top = two_block_indents(COLUMN_LEFT, INDENTED_LEFT)
        self.assertTrue(indents.indents_openings())

    def test_a_lone_flush_block_resumes_in_a_work_already_seen_to_indent_openings(self) -> None:
        self.assertTrue(lone_block_resumes(True))

    def test_a_lone_flush_block_does_not_resume_before_the_work_shows_indented_openings(self) -> None:
        self.assertFalse(lone_block_resumes(False))


class TestResumedParagraphWriting(unittest.TestCase):
    def test_a_resuming_paragraph_joins_across_the_page_even_after_a_full_stop(self) -> None:
        elements = [PageMarker(1, "1"), Paragraph("It ends here.", False, 1), PageMarker(2, "2"),
                    Paragraph("Rather, it goes on.", False, 2, True)]
        self.assertEqual("%% p. 1 (file p. 1) %%\n\nIt ends here. %% p. 2 (file p. 2) %% Rather, it goes on.\n",
                         NoteWriter().render(elements, []).text)

    def test_a_resuming_block_on_the_same_page_joins_a_paragraph_broken_off_mid_sentence(self) -> None:
        elements = [PageMarker(1, "1"), Paragraph("It is through these", False, 1),
                    Paragraph("weapons that it preserves itself.", False, 1, True)]
        self.assertEqual("%% p. 1 (file p. 1) %%\n\nIt is through these weapons that it preserves itself.\n",
                         NoteWriter().render(elements, []).text)

    def test_a_resuming_block_on_the_same_page_after_a_finished_sentence_stays_its_own_paragraph(self) -> None:
        elements = [PageMarker(1, "1"), Paragraph("It ends here.", False, 1),
                    Paragraph("They are.", False, 1, True)]
        self.assertEqual("%% p. 1 (file p. 1) %%\n\nIt ends here.\n\nThey are.\n",
                         NoteWriter().render(elements, []).text)

    def test_a_resuming_paragraph_after_a_heading_stays_its_own_paragraph(self) -> None:
        elements = [PageMarker(1, "1"), Heading(2, "Religion", 1), PageMarker(2, "2"),
                    Paragraph("Rather, it goes on.", False, 2, True)]
        self.assertEqual("%% p. 1 (file p. 1) %%\n\n## Religion\n\n%% p. 2 (file p. 2) %%\n\nRather, it goes on.\n",
                         NoteWriter().render(elements, []).text)


if __name__ == "__main__":
    unittest.main()
