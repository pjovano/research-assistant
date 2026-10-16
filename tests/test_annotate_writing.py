from __future__ import annotations

import unittest

from _annotate_fixtures import (BREAK_END, BREAK_START, ENDING_MARKER, LEADING_PAGE, MARKED_PAGE, PAGE_WORDS,
                                TRAILING_PAGE, WordSpan, WritableCopyTestCase)
import annotate
import pymupdf

TEMPORARY_SUFFIX = ".annotate.tmp.pdf"


class TestAnnotationWriting(WritableCopyTestCase):
    LINK = "Alpha - 2001 - First Link"
    OTHER = "Beta - 2002 - Second Link"
    PAGE = MARKED_PAGE
    SPAN = (26, 58)

    def test_a_highlight_is_written_and_reads_back(self) -> None:
        self.write([self.highlight(WordSpan(self.PAGE, *self.SPAN), self.LINK)])
        self.assertEqual(1, len(annotate.AnnotationInventory(self.copy).records()))

    def test_the_author_is_stamped(self) -> None:
        self.write([self.highlight(WordSpan(self.PAGE, *self.SPAN), self.LINK)])
        self.assertEqual("Tester", annotate.AnnotationInventory(self.copy).records()[0].author)

    def test_the_outline_survives_a_write(self) -> None:
        with pymupdf.open(self.copy) as document:
            before = document.get_toc()
        self.write([self.highlight(WordSpan(self.PAGE, *self.SPAN), self.LINK)])
        with pymupdf.open(self.copy) as document:
            self.assertEqual(before, document.get_toc())

    def test_an_overlapping_second_pass_merges_instead_of_stacking(self) -> None:
        self.write([self.highlight(WordSpan(self.PAGE, *self.SPAN), self.LINK)])
        self.write([self.highlight(WordSpan(self.PAGE, 30, 52), self.OTHER)])
        self.assertEqual(1, len(annotate.AnnotationInventory(self.copy).records()))

    def test_a_merged_note_carries_both_commentators(self) -> None:
        self.write([self.highlight(WordSpan(self.PAGE, *self.SPAN), self.LINK)])
        self.write([self.highlight(WordSpan(self.PAGE, 30, 52), self.OTHER)])
        note = annotate.AnnotationInventory(self.copy).records()[0].note
        self.assertIn(self.LINK, note)
        self.assertIn(self.OTHER, note)

    def test_repeating_the_same_pass_does_not_duplicate_a_note(self) -> None:
        request = self.highlight(WordSpan(self.PAGE, *self.SPAN), self.LINK)
        self.write([request])
        self.write([request])
        note = annotate.AnnotationInventory(self.copy).records()[0].note
        self.assertEqual(1, note.count(self.LINK))

    def test_a_distant_span_is_added_rather_than_merged(self) -> None:
        self.write([self.highlight(WordSpan(self.PAGE, *self.SPAN), self.LINK)])
        self.write([self.highlight(WordSpan(self.PAGE, 200, 220), self.OTHER)])
        self.assertEqual(2, len(annotate.AnnotationInventory(self.copy).records()))

    def test_a_tag_round_trips_through_the_pdf(self) -> None:
        self._write_tagged("Mathematics")
        self.assertEqual("Mathematics",
                         annotate.AnnotationInventory(self.copy).records()[0].tag)

    def test_listing_by_tag_finds_the_tagged_highlight(self) -> None:
        self._write_tagged("Mathematics")
        self.assertEqual(1, len(annotate.AnnotationInventory(self.copy).records("Mathematics")))

    def test_listing_by_another_tag_finds_nothing(self) -> None:
        self._write_tagged("Mathematics")
        self.assertEqual([], annotate.AnnotationInventory(self.copy).records("Causality"))

    def _write_tagged(self, tag: str) -> None:
        note = annotate.Note(self.LINK, "gloss", annotate.Tag(tag))
        request = annotate.AnnotationRequest(self.PAGE, self.SPAN[0], self.SPAN[1], note)
        annotate.AnnotationWriter(self.copy, "Tester").apply([request])


class TestCrossPageWriting(WritableCopyTestCase):
    LINK = "Alpha - 2001 - First Link"
    OTHER = "Beta - 2002 - Second Link"
    FIRST_PAGE = LEADING_PAGE
    SECOND_PAGE = TRAILING_PAGE
    START = BREAK_START
    END = BREAK_END
    FIRST_LAST_WORD = PAGE_WORDS
    MARKER_ENDED_PAGE = MARKED_PAGE
    MARKER_WORD = ENDING_MARKER[0] + 1

    def _cross_page(self, link: str = LINK, colour=None) -> annotate.AnnotationRequest:
        note = annotate.Note(link, "a gloss", annotate.Tag("Continuity"))
        return annotate.AnnotationRequest(self.FIRST_PAGE, self.START, self.END, note,
                                          colour=colour, end_page=self.SECOND_PAGE)

    def _annotations_on(self, page_number: int) -> list:
        with pymupdf.open(self.copy) as document:
            return [a.info | {"colour": (a.colors or {}).get("stroke")}
                    for a in document[page_number - 1].annots()]

    def _merging_report(self) -> annotate.DecisionReport:
        self.write([self.highlight(WordSpan(self.FIRST_PAGE, self.START, self.FIRST_LAST_WORD), self.OTHER)])
        writer = annotate.AnnotationWriter(self.copy, "Tester")
        writer.apply([self._cross_page()])
        return writer.report

    def test_the_plan_reports_a_pair_on_one_line(self) -> None:
        rendered = annotate.AnnotationPlan(self.copy).decisions([self._cross_page()]).rendered()
        self.assertTrue(rendered.startswith(
            f"p{LEADING_PAGE}–{TRAILING_PAGE} [{self.START}:{self.FIRST_LAST_WORD} | 0:19] ADDED"))

    def test_the_planned_text_is_joined_across_the_break(self) -> None:
        rendered = annotate.AnnotationPlan(self.copy).decisions([self._cross_page()]).rendered()
        self.assertIn("empirical, we cannot anticipate", rendered)

    def test_one_highlight_is_written_on_each_page(self) -> None:
        self.write([self._cross_page()])
        self.assertEqual(1, len(self._annotations_on(self.FIRST_PAGE)))
        self.assertEqual(1, len(self._annotations_on(self.SECOND_PAGE)))

    def test_both_halves_carry_the_same_note_tag_colour_and_author(self) -> None:
        self.write([self._cross_page(colour=(0.0, 1.0, 0.0))])
        first, second = self._annotations_on(self.FIRST_PAGE)[0], self._annotations_on(self.SECOND_PAGE)[0]
        for key in ("content", "subject", "title", "colour"):
            self.assertEqual(first[key], second[key], key)

    def test_the_pair_is_listed_as_one_record(self) -> None:
        self.write([self._cross_page()])
        self.assertEqual(1, len(annotate.AnnotationInventory(self.copy).records()))

    def test_the_listed_record_names_both_halves(self) -> None:
        self.write([self._cross_page()])
        rendered = annotate.AnnotationInventory(self.copy).records()[0].rendered()
        self.assertTrue(rendered.startswith(f"p{LEADING_PAGE}–{TRAILING_PAGE} #0/#0 "))

    def test_the_listed_text_is_joined_across_the_break(self) -> None:
        self.write([self._cross_page()])
        covered = annotate.AnnotationInventory(self.copy).records()[0].covered
        self.assertIn("empirical, we cannot anticipate", covered)

    def test_a_pair_is_found_by_its_tag(self) -> None:
        self.write([self._cross_page()])
        self.assertEqual(1, len(annotate.AnnotationInventory(self.copy).records("continuity")))

    def test_a_first_half_over_an_existing_highlight_is_merged(self) -> None:
        report = self._merging_report()
        self.assertEqual("merged", report.decisions[0].action)
        self.assertEqual(1, len(self._annotations_on(self.FIRST_PAGE)))

    def test_the_second_half_is_still_added_when_the_first_merges(self) -> None:
        report = self._merging_report()
        self.assertEqual("added", report.decisions[0].continuation.action)
        self.assertEqual(1, len(self._annotations_on(self.SECOND_PAGE)))

    def test_a_merged_pair_renders_both_actions_on_one_line(self) -> None:
        report = self._merging_report()
        self.assertIn("MERGED+ADDED", report.rendered().splitlines()[0])

    def test_repeating_the_pass_writes_nothing_new(self) -> None:
        self.write([self._cross_page()])
        self.write([self._cross_page()])
        self.assertEqual(1, len(self._annotations_on(self.FIRST_PAGE)))
        self.assertEqual(1, len(self._annotations_on(self.SECOND_PAGE)))

    def test_a_first_segment_that_is_only_a_marker_is_rejected(self) -> None:
        request = annotate.AnnotationRequest(self.MARKER_ENDED_PAGE, self.MARKER_WORD, 6,
                                             annotate.Note("", "body"),
                                             end_page=self.MARKER_ENDED_PAGE + 1)
        decision = annotate.AnnotationPlan(self.copy).decisions([request]).decisions[0]
        self.assertEqual("skipped", decision.action)
        self.assertIn("first segment", decision.detail)
        self.assertIn("debris", decision.detail)


class TestCrossPageRevision(WritableCopyTestCase):
    FIRST_PAGE = LEADING_PAGE
    SECOND_PAGE = TRAILING_PAGE

    def setUp(self) -> None:
        super().setUp()
        note = annotate.Note("Alpha - 2001 - First Link", "a gloss")
        self.write([annotate.AnnotationRequest(self.FIRST_PAGE, BREAK_START, BREAK_END, note,
                                               end_page=self.SECOND_PAGE)])

    def _colours(self) -> list:
        with pymupdf.open(self.copy) as document:
            return [tuple(a.colors["stroke"]) for n in (self.FIRST_PAGE, self.SECOND_PAGE)
                    for a in document[n - 1].annots()]

    def _notes(self) -> list[str]:
        with pymupdf.open(self.copy) as document:
            return [a.info["content"] for n in (self.FIRST_PAGE, self.SECOND_PAGE)
                    for a in document[n - 1].annots()]

    def test_the_dry_run_names_both_segments(self) -> None:
        change = annotate.RevisionChange(self.SECOND_PAGE, 0, delete=True)
        outcome = annotate.AnnotationRevision(self.copy).plan([change])[0]
        self.assertTrue(outcome.rendered().startswith(
            f"p{TRAILING_PAGE} #0 + p{LEADING_PAGE} #0 DELETE But since"))

    def test_a_colour_change_on_the_later_half_recolours_both(self) -> None:
        change = annotate.RevisionChange(self.SECOND_PAGE, 0, colour=(0, 1, 0))
        annotate.AnnotationRevision(self.copy).apply([change])
        self.assertEqual([(0.0, 1.0, 0.0)] * 2, self._colours())

    def test_a_note_replaced_on_the_earlier_half_replaces_both(self) -> None:
        change = annotate.RevisionChange(self.FIRST_PAGE, 0, note="replaced")
        annotate.AnnotationRevision(self.copy).apply([change])
        self.assertEqual(["replaced"] * 2, self._notes())

    def test_an_append_on_either_half_keeps_the_pair_listed_as_one(self) -> None:
        change = annotate.RevisionChange(self.SECOND_PAGE, 0, append="an afterthought")
        annotate.AnnotationRevision(self.copy).apply([change])
        self.assertEqual(1, len(annotate.AnnotationInventory(self.copy).records()))

    def test_deleting_the_later_half_removes_both(self) -> None:
        change = annotate.RevisionChange(self.SECOND_PAGE, 0, delete=True)
        annotate.AnnotationRevision(self.copy).apply([change])
        self.assertEqual([], self._notes())

    def test_a_single_highlight_on_the_next_page_is_left_alone(self) -> None:
        self.write([self.highlight(WordSpan(self.SECOND_PAGE, 200, 220), "Other - 2001 - Z")])
        change = annotate.RevisionChange(self.FIRST_PAGE, 0, delete=True)
        annotate.AnnotationRevision(self.copy).apply([change])
        self.assertEqual(1, len(annotate.AnnotationInventory(self.copy).records()))


class TestHandMadePairs(WritableCopyTestCase):
    FIRST_PAGE = LEADING_PAGE
    SECOND_PAGE = TRAILING_PAGE

    def _hand_highlight(self, span: WordSpan, note: str) -> None:
        request = self.highlight(span, "")
        quads = annotate.AnnotationPlan(self.copy).decisions([request]).decisions[0].quads
        with pymupdf.open(self.copy) as document:
            page = document[span.page - 1]
            page.add_highlight_annot(quads).set_info(content=note)
            document.save(self.copy, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)

    def test_hand_made_halves_with_the_same_note_list_as_one_unit(self) -> None:
        self._hand_highlight(WordSpan(self.FIRST_PAGE, BREAK_START, PAGE_WORDS), "same note")
        self._hand_highlight(WordSpan(self.SECOND_PAGE, 0, BREAK_END), "same note")
        self.assertEqual(1, len(annotate.AnnotationInventory(self.copy).records()))

    def test_adjacent_highlights_with_different_notes_stay_separate(self) -> None:
        self._hand_highlight(WordSpan(self.FIRST_PAGE, BREAK_START, PAGE_WORDS), "one note")
        self._hand_highlight(WordSpan(self.SECOND_PAGE, 0, BREAK_END), "another note")
        self.assertEqual(2, len(annotate.AnnotationInventory(self.copy).records()))

    def test_adjacent_highlights_with_empty_notes_stay_separate(self) -> None:
        self._hand_highlight(WordSpan(self.FIRST_PAGE, BREAK_START, PAGE_WORDS), "")
        self._hand_highlight(WordSpan(self.SECOND_PAGE, 0, BREAK_END), "")
        self.assertEqual(2, len(annotate.AnnotationInventory(self.copy).records()))

    def test_an_earlier_half_that_stops_mid_page_does_not_pair(self) -> None:
        self._hand_highlight(WordSpan(self.FIRST_PAGE, 200, 230), "same note")
        self._hand_highlight(WordSpan(self.SECOND_PAGE, 0, BREAK_END), "same note")
        self.assertEqual(2, len(annotate.AnnotationInventory(self.copy).records()))


class TestPlannedSpans(WritableCopyTestCase):
    LINK = "Alpha - 2001 - First Link"
    PAGE = LEADING_PAGE
    SHORT_SPAN = (20, 35)
    LONG_SPAN = (20, 60)
    MARKER_TRIMMED_PAGE = MARKED_PAGE
    MARKER_TRIMMED_SPAN = (26, 58)

    def _quads(self, span: tuple[int, int]) -> list:
        request = self.highlight(WordSpan(self.PAGE, span[0], span[1]), "X - 2000 - Y")
        return annotate.AnnotationPlan(self.copy).decisions([request]).decisions[0].quads

    def test_a_span_over_two_lines_yields_two_quads(self) -> None:
        self.assertEqual(2, len(self._quads(self.SHORT_SPAN)))

    def test_a_longer_span_yields_more_line_quads(self) -> None:
        self.assertGreater(len(self._quads(self.LONG_SPAN)), len(self._quads(self.SHORT_SPAN)))

    def test_a_line_quad_spans_more_than_a_single_word(self) -> None:
        widest = max(q.rect.width for q in self._quads(self.SHORT_SPAN))
        self.assertGreater(widest, 100)

    def test_quads_are_ordered_down_the_page(self) -> None:
        tops = [q.rect.y0 for q in self._quads(self.LONG_SPAN)]
        self.assertEqual(tops, sorted(tops))

    def test_a_trailing_marker_is_trimmed_from_the_covered_text(self) -> None:
        request = self.highlight(WordSpan(self.MARKER_TRIMMED_PAGE, *self.MARKER_TRIMMED_SPAN), self.LINK)
        decision = annotate.AnnotationPlan(self.copy).decisions([request]).decisions[0]
        self.assertTrue(decision.covered_text.endswith("composed."))


class TestAnnotationRevision(WritableCopyTestCase):
    LINK = "Alpha - 2001 - First Link"
    PAGE = MARKED_PAGE
    SPAN = (26, 58)

    def setUp(self) -> None:
        super().setUp()
        self.write([self.highlight(WordSpan(self.PAGE, *self.SPAN), self.LINK)])

    def test_a_dry_run_reports_what_it_would_touch(self) -> None:
        change = annotate.RevisionChange(self.PAGE, 0, colour=(0, 1, 0))
        outcome = annotate.AnnotationRevision(self.copy).plan([change])[0]
        self.assertEqual("modify", outcome.action)

    def test_a_dry_run_writes_nothing(self) -> None:
        change = annotate.RevisionChange(self.PAGE, 0, delete=True)
        annotate.AnnotationRevision(self.copy).plan([change])
        self.assertEqual(1, len(annotate.AnnotationInventory(self.copy).records()))

    def test_a_colour_change_is_applied(self) -> None:
        change = annotate.RevisionChange(self.PAGE, 0, colour=(0, 1, 0))
        annotate.AnnotationRevision(self.copy).apply([change])
        self.assertEqual((0.0, 1.0, 0.0),
                         annotate.AnnotationInventory(self.copy).records()[0].colour)

    def test_no_temporary_copy_survives_an_apply(self) -> None:
        change = annotate.RevisionChange(self.PAGE, 0, colour=(0, 1, 0))
        annotate.AnnotationRevision(self.copy).apply([change])
        leftovers = [p for p in self.directory.iterdir() if p.name.endswith(TEMPORARY_SUFFIX)]
        self.assertEqual([], leftovers)

    def test_a_note_can_be_replaced(self) -> None:
        change = annotate.RevisionChange(self.PAGE, 0, note="replaced")
        annotate.AnnotationRevision(self.copy).apply([change])
        self.assertEqual("replaced", annotate.AnnotationInventory(self.copy).records()[0].note)

    def test_a_note_can_be_appended_to(self) -> None:
        change = annotate.RevisionChange(self.PAGE, 0, append="an afterthought")
        annotate.AnnotationRevision(self.copy).apply([change])
        note = annotate.AnnotationInventory(self.copy).records()[0].note
        self.assertIn(self.LINK, note)
        self.assertIn("an afterthought", note)

    def test_an_annotation_can_be_deleted(self) -> None:
        change = annotate.RevisionChange(self.PAGE, 0, delete=True)
        annotate.AnnotationRevision(self.copy).apply([change])
        self.assertEqual([], annotate.AnnotationInventory(self.copy).records())

    def test_a_reference_with_no_annotation_is_reported_missing(self) -> None:
        change = annotate.RevisionChange(self.PAGE, 9, delete=True)
        self.assertEqual("missing", annotate.AnnotationRevision(self.copy).plan([change])[0].action)

    def test_applying_to_a_missing_index_reports_it_and_writes_nothing(self) -> None:
        change = annotate.RevisionChange(self.PAGE, 9, delete=True)
        revision = annotate.AnnotationRevision(self.copy)
        revision.apply([change])
        outcome = revision.outcomes[0]
        self.assertEqual("missing", outcome.action)
        self.assertEqual(1, len(annotate.AnnotationInventory(self.copy).records()))


if __name__ == "__main__":
    unittest.main()
