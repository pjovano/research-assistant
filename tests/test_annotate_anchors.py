from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _book_fixtures import PAGE_WORDS, WORDS_PER_LINE, BookPage, BookPdf, BuiltPdfTestCase, ProseLines
import annotate

MARKED_PAGE = 2
MARKED_PAGES = [BookPage(ProseLines(0).placing({40: "[A", 41: "97]", 120: "[A", 121: "718/B", 122: "746]"})),
                BookPage(ProseLines(4).placing({60: "[A", 61: "137]", 150: "[A", 151: "719/B", 152: "747]"}))]
AKADEMIE_PAGES = [BookPage(ProseLines(2).placing({40: "[4:260]"}))]

SPREAD_PAGE = 1
SPREAD_LEFT_SPAN = (100, 120)
SPREAD_GUTTER_SPAN = (PAGE_WORDS - 10, PAGE_WORDS + 10)
SPREAD_PAGES = [BookPage(ProseLines(0).placing(), right_lines=ProseLines(5).placing())]

NOTE_LINES = 3
NOTES_START = PAGE_WORDS
HEAD_START = NOTES_START + NOTE_LINES * WORDS_PER_LINE
HEADED_PAGES = [BookPage(ProseLines(0).placing(), notes=ProseLines(2, NOTE_LINES).placing(),
                         head="Running head of the chapter 115"),
                BookPage(ProseLines(4).placing(), head="116 Running head of the chapter")]


class TestInlineMarkerIndex(BuiltPdfTestCase):
    BOOK = BookPdf(MARKED_PAGES)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.index = annotate.EditionAnchorIndex(cls.pdf)

    def test_inline_markers_make_the_inline_marker_strategy_available(self) -> None:
        self.assertIn("inline-marker", self.index.strategies())

    def test_both_marker_forms_are_present(self) -> None:
        self.assertEqual({"single", "combined"}, set(self.index.inline.coverage()))

    def test_combined_markers_are_a_substantial_share(self) -> None:
        coverage = self.index.inline.coverage()
        self.assertGreater(coverage["combined"], coverage["single"] * 0.5)

    def test_a_reference_inside_a_combined_marker_resolves(self) -> None:
        self.assertTrue(self.index.inline.resolve("A", 718))

    def test_a_reference_in_a_single_marker_resolves(self) -> None:
        self.assertTrue(self.index.inline.resolve("A", 97))

    def test_a_marker_resolves_to_the_page_that_prints_it(self) -> None:
        marker = self.index.inline.resolve("A", 137)[0]
        self.assertEqual(MARKED_PAGE, marker.page)

    def test_an_absent_reference_yields_bracketing_markers(self) -> None:
        below, above = self.index.inline.bracketing("A", 900)
        self.assertIsNotNone(below)
        self.assertIsNone(above)

    def test_quote_match_is_always_offered_as_a_strategy(self) -> None:
        self.assertIn("quote-match", self.index.strategies())


class TestAkademieAnchoring(BuiltPdfTestCase):
    BOOK = BookPdf(AKADEMIE_PAGES)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.index = annotate.EditionAnchorIndex(cls.pdf)

    def test_akademie_markers_are_found(self) -> None:
        self.assertEqual(["akademie"], list(self.index.inline.coverage()))

    def test_an_akademie_reference_resolves(self) -> None:
        self.assertTrue(self.index.inline.resolve("Ak4", 260))


class TestSpreadValidation(BuiltPdfTestCase):
    BOOK = BookPdf(SPREAD_PAGES)

    def _decision(self, span: tuple[int, int]):
        request = annotate.AnnotationRequest(SPREAD_PAGE, span[0], span[1],
                                             annotate.Note("X - 2000 - Y", "body"))
        return annotate.AnnotationPlan(self.pdf).decisions([request]).decisions[0]

    def test_a_span_inside_one_page_of_a_spread_is_accepted(self) -> None:
        self.assertEqual("added", self._decision(SPREAD_LEFT_SPAN).action)

    def test_a_span_crossing_the_gutter_is_skipped_and_the_gutter_is_named(self) -> None:
        decision = self._decision(SPREAD_GUTTER_SPAN)
        self.assertEqual(("skipped", True), (decision.action, "gutter" in decision.detail))


class TestCrossPageMargins(BuiltPdfTestCase):
    BOOK = BookPdf(HEADED_PAGES)
    FIRST_PAGE = 1
    SECOND_PAGE = 2
    SENTENCE_START = PAGE_WORDS - 2
    SENTENCE_END = 35
    SHORT_END = 20
    BODY_FIRST_WORD = 0
    FOOTNOTE_WORD = NOTES_START + WORDS_PER_LINE
    HEAD_WORD = HEAD_START
    NEXT_HEAD_WORD = PAGE_WORDS + 2

    def _decision(self, start: int, end: int):
        request = annotate.AnnotationRequest(self.FIRST_PAGE, start, end,
                                             annotate.Note("", "body"), end_page=self.SECOND_PAGE)
        return annotate.AnnotationPlan(self.pdf).decisions([request]).decisions[0]

    def test_a_sentence_across_the_break_is_accepted(self) -> None:
        self.assertEqual("added", self._decision(self.SENTENCE_START, self.SENTENCE_END).action)

    def test_the_second_segment_starts_after_the_running_head(self) -> None:
        decision = self._decision(self.SENTENCE_START, self.SENTENCE_END)
        self.assertEqual(0, decision.continuation.span.start)

    def test_the_first_segment_stops_before_the_footnotes(self) -> None:
        decision = self._decision(self.SENTENCE_START, self.SENTENCE_END)
        self.assertEqual(self.SENTENCE_START + 2, decision.span.end)

    def test_a_first_segment_starting_in_the_footnotes_is_rejected(self) -> None:
        decision = self._decision(self.FOOTNOTE_WORD, self.SENTENCE_END)
        self.assertEqual("skipped", decision.action)
        self.assertIn("first segment", decision.detail)

    def test_a_first_segment_starting_on_the_running_head_is_rejected(self) -> None:
        self.assertIn("first segment", self._decision(self.HEAD_WORD, self.SENTENCE_END).detail)

    def test_a_second_segment_ending_on_the_running_head_is_rejected(self) -> None:
        decision = self._decision(self.SENTENCE_START, self.NEXT_HEAD_WORD)
        self.assertEqual("skipped", decision.action)
        self.assertIn("second segment", decision.detail)

    def test_the_second_segment_starts_at_the_first_body_word(self) -> None:
        decision = self._decision(self.SENTENCE_START, self.SHORT_END)
        self.assertEqual(self.BODY_FIRST_WORD, decision.continuation.span.start)


if __name__ == "__main__":
    unittest.main()
