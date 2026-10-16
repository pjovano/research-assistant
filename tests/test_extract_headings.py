from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import PrintedWork, RunSetting, keep_everything, page_assembler, positioned
from _extract.blocks import Block, PageBlocks
from _extract.candidates import (
    CandidateBlock, CandidatePlace, HeadingCandidate, HeadingStyles, OpenedHeadings, RunningHeads,
)
from _extract.headings import HeadingMatch, HeadingText, LetterSpacedHeading, OutlineQueue, shape_of
from _extract.layer import LayerChar
from _extract.outline import Heading as OutlineHeading, Outline
from _extract.structure import Heading, PageAssembler, Paragraph

WORK_TITLE = "Reasons for Logic, Logic for Reasons"
HEADING_STYLE = (14.0, True, False)
BODY_STYLE = (10.0, False, False)
PAGE_WIDTH = 430.0
PAGE_HEIGHT = 649.0
FIRST_DESTINATION_FROM_TOP = 37.0
DESTINATION_Y_FROM_BOTTOM = 441.0


class EmptyHtmlLayer:
    def __init__(self, chars: list[LayerChar]) -> None:
        self._chars = chars

    def chars_in(self, file_page: int, bbox) -> list[LayerChar]:
        return list(self._chars)

    def lines_in(self, file_page: int, bbox) -> list:
        return []

    def rules_in(self, file_page: int, bbox) -> list:
        return []

    def shapes_in(self, file_page: int, bbox) -> list:
        return []

    def text(self, file_page: int) -> str:
        return ""


class FakeLayer:
    def __init__(self, size: float = 10.0, chars: list[LayerChar] | None = None) -> None:
        self._chars = chars or [LayerChar("x", (1.0, 1.0), False, size)]

    def chars_in(self, file_page: int, bbox) -> list[LayerChar]:
        return list(self._chars)

    def lines_in(self, file_page: int, bbox) -> list:
        return []

    def shapes_in(self, file_page: int, bbox) -> list:
        return []

    def text(self, file_page: int) -> str:
        return ""

    def unstacked(self) -> FakeLayer:
        return self


@dataclass(frozen=True)
class Band:
    top: float
    bottom: float


def block(kind: str, html: str, band: Band) -> Block:
    return Block(1, kind, html, (0.0, band.top, 100.0, band.bottom), {}, f"/page/1/{kind}/{band.top}")


class TestHeadingCandidate(unittest.TestCase):
    def _candidate(self, text: str, folio: str | None = None, key: tuple = BODY_STYLE) -> HeadingCandidate:
        return HeadingCandidate(CandidateBlock(HeadingText(text, False), key, CandidatePlace(folio)),
                                RunningHeads([]))

    def test_a_running_head_repeated_as_a_heading_is_dropped(self) -> None:
        candidate = self._candidate("116 Introducing Logical Vocabulary", folio="116")
        self.assertFalse(candidate.is_heading(OpenedHeadings(), HeadingStyles(), WORK_TITLE))

    def test_a_heading_repeating_the_works_title_is_dropped(self) -> None:
        candidate = self._candidate("Reasons for Logic, Logic for Reasons")
        self.assertFalse(candidate.is_heading(OpenedHeadings(), HeadingStyles(), WORK_TITLE))

    def test_a_number_followed_by_an_opened_chapter_title_is_a_running_head(self) -> None:
        opened = OpenedHeadings()
        opened.add("3 Introducing Logical Vocabulary", 1)
        candidate = self._candidate("256 Introducing Logical Vocabulary")
        self.assertFalse(candidate.is_heading(opened, HeadingStyles(), WORK_TITLE))

    def test_a_running_head_naming_a_chapter_title_with_a_subtitle_is_dropped(self) -> None:
        opened = OpenedHeadings()
        opened.add("3 Introducing Logical Vocabulary: Making ReasonRelations Logical", 1)
        candidate = self._candidate("116 Introducing Logical Vocabulary")
        self.assertFalse(candidate.is_heading(opened, HeadingStyles(), WORK_TITLE))

    def test_a_fragment_ending_in_a_colon_is_dropped(self) -> None:
        self.assertFalse(self._candidate("Axioms of NMMS:").is_heading(OpenedHeadings(), HeadingStyles(), WORK_TITLE))

    def test_a_fragment_opening_with_a_conjunction_is_dropped(self) -> None:
        self.assertFalse(self._candidate("But not").is_heading(OpenedHeadings(), HeadingStyles(), WORK_TITLE))

    def test_a_genuine_unlisted_heading_is_kept(self) -> None:
        candidate = self._candidate("Normative Governance")
        self.assertTrue(candidate.is_heading(OpenedHeadings(), HeadingStyles(), WORK_TITLE))

    def test_a_fragment_in_a_listed_heading_style_is_kept(self) -> None:
        styles = HeadingStyles()
        styles.learn(HEADING_STYLE)
        candidate = self._candidate("And again:", key=HEADING_STYLE)
        self.assertTrue(candidate.is_heading(OpenedHeadings(), styles, WORK_TITLE))


class TestOutlinePlacement(unittest.TestCase):
    def _assembler(self) -> PageAssembler:
        return page_assembler(FakeLayer(), keep_everything(), PrintedWork(work_title=WORK_TITLE))

    def _elements(self, assembler: PageAssembler, blocks: list[Block], due: list[OutlineHeading]) -> list:
        return assembler.assemble(PageBlocks(1, blocks), due, 2).elements[1:]

    def test_an_unmatched_outline_heading_opens_at_its_position_on_the_page(self) -> None:
        blocks = [block("Text", "<p>Preface prose.</p>", Band(40.0, 120.0)),
                  block("Text", "<p>Section prose.</p>", Band(220.0, 300.0))]
        due = [OutlineHeading(1, "Introduction", 1, 30.0), OutlineHeading(2, "0.1 Two Traditions", 1, 208.0)]
        titles = [element.title if isinstance(element, Heading) else element.text
                  for element in self._elements(self._assembler(), blocks, due)]
        self.assertEqual(["Introduction", "Preface prose.", "0.1 Two Traditions", "Section prose."], titles)

    def test_an_outline_entry_with_no_position_opens_at_the_paragraph_that_prints_its_title_once(self) -> None:
        blocks = [block("Text", "<p>My title is not intended as a pun.</p>", Band(40.0, 120.0)),
                  block("Text", "<p>1. What kind of logic is Hegel's logic?</p>", Band(130.0, 300.0))]
        titles = [element.title if isinstance(element, Heading) else element.text
                  for element in self._elements(self._assembler(), blocks, [OutlineHeading(1, "1.", 1)])]
        self.assertEqual(["My title is not intended as a pun.", "1.", "What kind of logic is Hegel's logic?"], titles)

    def test_a_running_head_never_opens_the_outline_entry_it_reads_like(self) -> None:
        assembler = page_assembler(FakeLayer(), keep_everything(),
                                   PrintedWork(work_title=WORK_TITLE, folios={1: "256"}))
        blocks = [block("SectionHeader", "<h4>256 Implication-Space Semantics</h4>", Band(39.0, 53.0)),
                  block("Text", "<p>Body prose.</p>", Band(63.0, 137.0)),
                  block("SectionHeader", "<h4>5.7.2 Implication-Space Semantics and NMMS</h4>", Band(478.0, 491.0))]
        due = [OutlineHeading(3, "5.7.2 Implication-Space Semantics and NMMS", 1, 479.0)]
        texts = [element.title if isinstance(element, Heading) else element.text
                 for element in self._elements(assembler, blocks, due)]
        self.assertEqual(["Body prose.", "5.7.2 Implication-Space Semantics and NMMS"], texts)

    def test_an_outline_entry_whose_printed_heading_repeats_the_work_title_opens_at_its_destination(self) -> None:
        blocks = [block("SectionHeader", f"<h1>{WORK_TITLE}</h1>", Band(80.0, 100.0)),
                  block("SectionHeader", "<h2>Abstract</h2>", Band(120.0, 130.0)),
                  block("Text", "<p>Prose.</p>", Band(140.0, 200.0))]
        titles = [element.title if isinstance(element, Heading) else element.text
                  for element in self._elements(self._assembler(), blocks, [OutlineHeading(1, WORK_TITLE, 1, 0.0)])]
        self.assertEqual([WORK_TITLE, "Abstract", "Prose."], titles)

    def test_a_heading_repeating_the_work_title_before_any_outline_entry_is_not_written(self) -> None:
        blocks = [block("SectionHeader", f"<h1>{WORK_TITLE}</h1>", Band(60.0, 90.0)),
                  block("Text", "<p>Prose.</p>", Band(140.0, 200.0))]
        elements = self._assembler().assemble(PageBlocks(1, blocks), [], None).elements[1:]
        self.assertEqual([Paragraph("Prose.", False, 1)], elements)

    def test_blocks_the_engine_reads_out_of_order_on_a_single_column_page_are_read_top_to_bottom(self) -> None:
        blocks = [block("Text", "<p>The theme is difficult.</p>", Band(218.0, 303.0)),
                  block("SectionHeader", "<h2>Normative Governance</h2>", Band(93.0, 136.0))]
        titles = [element.title if isinstance(element, Heading) else element.text
                  for element in self._elements(self._assembler(), blocks, [])]
        self.assertEqual(["Normative Governance", "The theme is difficult."], titles)

    def test_a_numbered_heading_matching_the_folio_below_other_content_opens_its_outline_entry(self) -> None:
        assembler = page_assembler(FakeLayer(), keep_everything(), PrintedWork(work_title=WORK_TITLE, folios={1: "1"}))
        blocks = [block("Text", "<p>Author.</p>", Band(135.0, 153.0)),
                  block("SectionHeader", "<h4>1 Introduction</h4>", Band(235.0, 255.0)),
                  block("Text", "<p>Body prose.</p>", Band(268.0, 554.0))]
        due = [OutlineHeading(1, "Introduction", 1, 231.0)]
        texts = [element.title if isinstance(element, Heading) else element.text
                 for element in self._elements(assembler, blocks, due)]
        self.assertEqual(["Author.", "Introduction", "Body prose."], texts)

    def test_a_numbered_heading_matching_the_folio_below_the_body_and_above_the_footnotes_is_a_running_foot(
            self) -> None:
        assembler = page_assembler(FakeLayer(), keep_everything(),
                                   PrintedWork(work_title=WORK_TITLE, folios={1: "116"}))
        blocks = [block("Text", "<p>Body prose.</p>", Band(63.0, 137.0)),
                  block("SectionHeader", "<h4>116 Introducing Logical Vocabulary</h4>", Band(500.0, 514.0)),
                  block("Footnote", "<p>A note.</p>", Band(560.0, 575.0))]
        texts = [element.title if isinstance(element, Heading) else element.text
                 for element in self._elements(assembler, blocks, [])]
        self.assertEqual(["Body prose."], texts)

    def test_an_outline_entry_is_never_written_twice(self) -> None:
        assembler = self._assembler()
        first = self._elements(assembler, [block("Text", "<p>One.</p>", Band(40.0, 80.0))],
                               [OutlineHeading(2, "0.1 Two Traditions in Language", 1, 0.0)])
        repeated = [block("SectionHeader", "<h2>0.1 Two Traditions in Language</h2>", Band(40.0, 60.0)),
                    block("Text", "<p>Two.</p>", Band(70.0, 90.0))]
        second = self._elements(assembler, repeated, [])
        headings = [element.title for element in first + second if isinstance(element, Heading)]
        self.assertEqual(["0.1 Two Traditions in Language"], headings)

    def test_an_unmatched_heading_waits_for_the_matched_heading_the_outline_lists_before_it(self) -> None:
        blocks = [block("SectionHeader", "<h1>C. (AA) Reason</h1>", Band(85.0, 105.0)),
                  block("Text", "<p>231. Consciousness has taken hold.</p>", Band(195.0, 483.0))]
        due = [OutlineHeading(1, "C. (AA) Reason", 1, 0.0),
               OutlineHeading(2, "V. The Certainty and Truth of Reason", 1, 0.0)]
        titles = [element.title if isinstance(element, Heading) else element.text
                  for element in self._elements(self._assembler(), blocks, due)]
        expected = ["C. (AA) Reason", "V. The Certainty and Truth of Reason", "231. Consciousness has taken hold."]
        self.assertEqual(expected, titles)

    def test_a_running_head_the_engine_calls_a_heading_is_not_written(self) -> None:
        blocks = [block("PageHeader", "<p>116 Introducing Logical Vocabulary</p>", Band(10.0, 20.0)),
                  block("SectionHeader", "<h6>116 Introducing Logical Vocabulary</h6>", Band(30.0, 40.0)),
                  block("Text", "<p>Prose.</p>", Band(50.0, 90.0))]
        elements = self._elements(self._assembler(), blocks, [])
        self.assertEqual([Paragraph("Prose.", False, 1)], elements)


LETTER_WIDTH = 5.0
LETTER_GAP = 2.2
WORD_GAP = 7.14
SPACED_SIZE = 10.5


def spaced_chars(words: str) -> list[LayerChar]:
    chars, x = [], 0.0
    for character in words:
        if character == " ":
            x += WORD_GAP - LETTER_GAP
            continue
        box = (x, 0.0, x + LETTER_WIDTH, SPACED_SIZE)
        chars.append(LayerChar(character, (x, 0.0), False, SPACED_SIZE, bbox=box))
        x += LETTER_WIDTH + LETTER_GAP
    return chars


class TestOutlineHeadingsTheEngineLeftEmpty(unittest.TestCase):
    def _titles(self, blocks: list[Block], chars: list, due: list[OutlineHeading]) -> list[str]:
        assembler = page_assembler(EmptyHtmlLayer(chars), keep_everything(), PrintedWork(work_title=WORK_TITLE))
        return [element.title if isinstance(element, Heading) else element.text
                for element in assembler.assemble(PageBlocks(1, blocks), due, 2).elements[1:]]

    def test_an_outline_entry_opens_at_the_heading_block_the_engine_left_empty(self) -> None:
        blocks = [block("Text", "", Band(30.0, 60.0)), block("SectionHeader", "", Band(90.0, 120.0))]
        chars = positioned("Prose.", RunSetting(10.0, 55.0, 0)) + positioned("References", RunSetting(10.0, 115.0, 1))
        self.assertEqual(["Prose.", "References"],
                         self._titles(blocks, chars, [OutlineHeading(1, "References", 1, 0.0)]))

    def test_an_outline_entry_no_block_on_the_page_names_opens_at_its_destination(self) -> None:
        blocks = [block("Text", "", Band(30.0, 60.0)), block("SectionHeader", "", Band(90.0, 120.0))]
        chars = positioned("Prose.", RunSetting(10.0, 55.0, 0)) + positioned("Appendix", RunSetting(10.0, 115.0, 1))
        self.assertEqual(["Prose.", "References", "Appendix"],
                         self._titles(blocks, chars, [OutlineHeading(1, "References", 1, 75.0)]))


class TestRunningHeadsOfTheWork(unittest.TestCase):
    def _titles(self, furniture: list[str], blocks: list[Block]) -> list[str]:
        assembler = page_assembler(FakeLayer(), keep_everything(),
                                   PrintedWork(work_title=WORK_TITLE, furniture=furniture))
        return [element.title if isinstance(element, Heading) else element.text
                for element in assembler.assemble(PageBlocks(1, blocks), [], 2).elements[1:]]

    def test_a_running_head_the_engine_calls_a_heading_is_dropped_on_a_page_carrying_no_furniture(self) -> None:
        blocks = [block("SectionHeader", "<h6>Philosophy Today</h6>", Band(30.0, 45.0)),
                  block("Text", "<p>Prose.</p>", Band(55.0, 95.0))]
        self.assertEqual(["Prose."], self._titles(["Philosophy Today"], blocks))

    def test_a_heading_the_works_furniture_does_not_name_is_kept(self) -> None:
        blocks = [block("SectionHeader", "<h6>Normative Governance</h6>", Band(30.0, 45.0)),
                  block("Text", "<p>Prose.</p>", Band(55.0, 95.0))]
        self.assertEqual(["Normative Governance", "Prose."], self._titles(["Philosophy Today"], blocks))


class TestLowercaseSectionHeadings(unittest.TestCase):
    def _titles(self, layer: FakeLayer, blocks: list[Block]) -> list[str]:
        assembler = page_assembler(layer, keep_everything(), PrintedWork(work_title=WORK_TITLE))
        return [element.title if isinstance(element, Heading) else element.text
                for element in assembler.assemble(PageBlocks(1, blocks), [], 2).elements[1:]]

    def test_a_letter_spaced_heading_opening_lowercase_opens_a_section(self) -> None:
        blocks = [block("SectionHeader", "<h3>b i b l i o g r a p h y</h3>", Band(30.0, 45.0))]
        layer = FakeLayer(chars=spaced_chars("bibliography"))
        self.assertEqual(["bibliography"], self._titles(layer, blocks))

    def test_a_continuation_line_opening_lowercase_is_dropped(self) -> None:
        blocks = [block("SectionHeader", "<h3>the same holds of the concept</h3>", Band(30.0, 45.0))]
        self.assertEqual([], self._titles(FakeLayer(), blocks))


class TestLetterSpacedHeading(unittest.TestCase):
    def test_a_letter_spaced_heading_is_rejoined_into_words(self) -> None:
        spaced = spaced_chars("correctness and truth")
        self.assertEqual("correctness and truth",
                         LetterSpacedHeading(spaced).rejoined("c o r r e c t n e s s a n d t r u t h"))

    def test_an_ordinary_heading_is_left_untouched(self) -> None:
        self.assertEqual("Correctness and Truth",
                         LetterSpacedHeading(spaced_chars("Correctness and Truth")).rejoined("Correctness and Truth"))

    def test_a_short_heading_of_single_letters_is_left_untouched(self) -> None:
        self.assertEqual("A B C", LetterSpacedHeading(spaced_chars("A B C")).rejoined("A B C"))


class TestTitleMatching(unittest.TestCase):
    def test_a_numbered_heading_names_the_unnumbered_outline_title(self) -> None:
        self.assertTrue(HeadingMatch().matches("1. Introduction", "Introduction"))

    def test_an_unnumbered_heading_names_the_numbered_outline_title(self) -> None:
        self.assertTrue(HeadingMatch().matches("Introduction", "1. Introduction"))

    def test_a_number_alone_does_not_make_two_titles_match(self) -> None:
        self.assertFalse(HeadingMatch().matches("1. Introduction", "2. Conclusion"))

    def test_a_title_missing_a_space_before_a_number_word_still_matches(self) -> None:
        self.assertTrue(HeadingMatch().matches("0.1 Two Traditions and Two Kinds of Metalanguage",
                                               "0.1 Two Traditions andTwo Kinds of Metalanguage"))


class TestMarginNumbersInHeadings(unittest.TestCase):
    def test_a_margin_number_inside_a_heading_does_not_block_its_match(self) -> None:
        printed = "iii. force and the understanding; appearance and the 82 supersensible world"
        outlined = "III. Force and the Understanding; Appearance and the Supersensible World"
        self.assertTrue(HeadingMatch().matches(printed, outlined))

    def test_a_label_number_still_tells_two_chapters_apart(self) -> None:
        self.assertFalse(HeadingMatch().matches("Chapter 2", "Chapter 3"))


class TestLabelledOutlineTitles(unittest.TestCase):
    def test_a_heading_printed_without_the_outline_label_matches_it(self) -> None:
        self.assertTrue(HeadingMatch().matches("Hegel's Advertisement and Hegel's Note to Himself",
                                               "Appendix: Hegel’s Advertisement and Hegel’s Note to Himself"))

    def test_a_label_alone_does_not_match_another_title(self) -> None:
        self.assertFalse(HeadingMatch().matches("Hegel's Advertisement", "Appendix: Further Reading"))


class TestOutlinePositions(unittest.TestCase):
    def test_a_destination_names_its_distance_from_the_page_top(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "outlined.pdf"
            with pymupdf.open() as document:
                document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
                first = {"kind": 1, "to": pymupdf.Point(0, FIRST_DESTINATION_FROM_TOP)}
                second = {"kind": 1, "to": pymupdf.Point(0, PAGE_HEIGHT - DESTINATION_Y_FROM_BOTTOM)}
                document.set_toc([[1, "Introduction", 1, first], [2, "0.1 Two Traditions", 1, second]])
                document.save(path)
            positions = [round(heading.position) for heading in Outline(path).headings()]
        self.assertEqual([round(FIRST_DESTINATION_FROM_TOP), round(PAGE_HEIGHT - DESTINATION_Y_FROM_BOTTOM)], positions)


class TestOutlineTitles(unittest.TestCase):
    def test_an_outline_title_carrying_a_character_reference_names_the_character(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "outlined.pdf"
            with pymupdf.open() as document:
                document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
                document.set_toc([[1, "On Immanent Critique in Hegel&#x2019;s Logic &amp; Method", 1]])
                document.save(path)
            titles = [heading.title for heading in Outline(path).headings()]
        self.assertEqual(["On Immanent Critique in Hegel’s Logic & Method"], titles)


class TestOutlineQueue(unittest.TestCase):
    def setUp(self) -> None:
        self.queue = OutlineQueue([OutlineHeading(1, "One", 1), OutlineHeading(2, "Two", 3)])

    def test_asking_what_is_due_releases_nothing(self) -> None:
        self.queue.due_on(3)
        self.assertEqual(["One", "Two"], [heading.title for heading in self.queue.due_on(3)])

    def test_releasing_a_page_drops_its_due_headings(self) -> None:
        self.queue.release(3)
        self.assertEqual([], self.queue.due_on(9))

    def test_releasing_a_page_sets_the_sublevel_below_its_last_heading(self) -> None:
        self.queue.release(3)
        self.assertEqual(3, self.queue.sublevel)


class TestCompoundNumberShapes(unittest.TestCase):
    def test_a_tens_word_followed_by_a_unit_digit_compounds(self) -> None:
        self.assertEqual("chapter 21", shape_of("Chapter Twenty-one"))

    def test_a_tens_word_followed_by_a_number_past_nine_stays_apart(self) -> None:
        self.assertEqual("chapter 20 10", shape_of("Chapter Twenty 10"))


if __name__ == "__main__":
    unittest.main()
