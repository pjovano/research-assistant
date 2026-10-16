from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import pymupdf

from _annotate_fixtures import WritableCopyTestCase
from _book_fixtures import PAGE_WORDS, BookPage, BookPdf, ProseLines

import annotate
from _annotate.quotation_span import FoldedWords
import vault
from _writing.highlight_colours import HighlightChoices
from _writing.highlights import (NoteHighlighting, PageSpan, PdfHighlights, TaggedEntries,
                                 WrittenReference)
from _writing.note_lines import NoteFile
from _writing.tree import WritingFolders

IDEA = "Thoughts need intuitions"
SAYING = dict(enumerate(("Thoughts", "without", "content", "are", "empty,", "intuitions", "are", "blind."), start=30))
SPLIT_WORD = {108: "sound", 109: "judg-", 110: "ment", 111: "here"}
REPEATED = {200: "pure", 201: "reason", 220: "pure", 221: "reason"}
BREAK_OPENING = {PAGE_WORDS - 3: "Reason", PAGE_WORDS - 2: "must", PAGE_WORDS - 1: "approach"}
BREAK_CLOSING = {0: "nature", 1: "with", 2: "principles."}
QUOTATION = "Thoughts without content are empty, intuitions are blind."
BROKEN_QUOTATION = "Reason must approach nature with principles."
LINK = "zotero://open-pdf/library/items/ABCD1234?page="
OUTLINE = [[1, "First chapter", 1]]


def reference(quotation: str = QUOTATION, page: int = 1, comment: str = "> \tThe locus classicus.\n", mark: str = "accepted") -> str:
    return f"> **states** · “{quotation}” #{mark}\n> \t[[book]], [p. {page}]({LINK}{page})\n{comment}"


def note_text(references: str, frontmatter: str = "---\nprojects:\n- '[[Paper]]'\nfield:\n- '[[Kant]]'\n---\n") -> str:
    return f"{frontmatter}- Thoughts need intuitions to have content\n\n# References\n\n{references}\n# Tasks\n"


class SayingBook(WritableCopyTestCase):
    BOOK = BookPdf([BookPage(ProseLines(0).placing({**SAYING, **SPLIT_WORD, **REPEATED})),
                    BookPage(ProseLines(3).placing(BREAK_OPENING)),
                    BookPage(ProseLines(7).placing(BREAK_CLOSING))], OUTLINE)

    def grid(self, page: int) -> annotate.WordGrid:
        with pymupdf.open(self.copy) as document:
            return annotate.WordGrid(document[page - 1])

    def records(self) -> list:
        return annotate.AnnotationInventory(self.copy).records()


class TestQuotationSpan(SayingBook):
    def test_a_quotation_is_located_at_its_first_word_and_past_its_last(self) -> None:
        self.assertEqual((30, 38), annotate.QuotationSpan(self.grid(1), QUOTATION).located())

    def test_a_quotation_differing_in_case_and_punctuation_is_still_located(self) -> None:
        self.assertEqual((30, 38), annotate.QuotationSpan(self.grid(1), QUOTATION.upper().replace(",", ";")).located())

    def test_a_word_hyphenated_over_a_line_break_is_located_as_one_word(self) -> None:
        self.assertEqual((108, 112), annotate.QuotationSpan(self.grid(1), "sound judgment here").located())

    def test_a_letter_the_page_sets_as_a_spacing_accent_before_its_base_folds_as_the_accented_letter(self) -> None:
        self.assertEqual(FoldedWords.folded("Vern\u00a8unftigen]"), FoldedWords.folded("Vernünftigen"))

    def test_words_the_page_carries_twice_are_not_located(self) -> None:
        self.assertIsNone(annotate.QuotationSpan(self.grid(1), "pure reason").located())

    def test_words_the_page_does_not_carry_are_not_located(self) -> None:
        self.assertIsNone(annotate.QuotationSpan(self.grid(1), "an absent phrase").located())

    def test_a_quotation_over_a_page_break_is_located_from_its_first_page_to_its_second(self) -> None:
        located = annotate.CrossPageQuotationSpan(self.grid(2), self.grid(3), BROKEN_QUOTATION).located()
        self.assertEqual((PAGE_WORDS - 3, 3), located)

    def test_a_quotation_on_one_page_alone_is_not_located_over_the_break(self) -> None:
        self.assertIsNone(annotate.CrossPageQuotationSpan(self.grid(1), self.grid(2), QUOTATION).located())


class TestPassageOnTheNextPage(WritableCopyTestCase):
    BOOK = BookPdf([BookPage(ProseLines(3).placing({10: "Reason"})),
                    BookPage(ProseLines(7).placing({0: "Reason", 1: "alone", 2: "decides."}))], OUTLINE)

    def test_a_passage_wholly_on_the_next_page_is_not_taken_to_open_on_the_page_cited(self) -> None:
        cited = WrittenReference("Reason alone decides.", "book", 1, "")
        self.assertEqual({"page": 2, "start": 0, "end": 3}, PageSpan(Path(self.copy), cited).entry())


class TestSeveralTags(unittest.TestCase):
    def test_a_spec_entry_carries_each_tag_on_one_line_after_the_note(self) -> None:
        payload = {"annotations": [{"page": 1, "start": 0, "end": 3, "link": IDEA, "body": "why", "tags": ["Paper", "Kant"]}]}
        note = annotate.AnnotationSpec(payload).requests()[0].note
        self.assertEqual(f"[[{IDEA}]] — why\n#[[Paper]] #[[Kant]]", note.rendered)

    def test_a_single_tag_is_still_read(self) -> None:
        payload = {"annotations": [{"page": 1, "start": 0, "end": 3, "body": "why", "tag": "Kant"}]}
        self.assertEqual("why\n#[[Kant]]", annotate.AnnotationSpec(payload).requests()[0].note.rendered)


class TestWrittenReference(unittest.TestCase):
    def test_a_reference_is_read_back_as_its_quotation_source_file_page_and_comment(self) -> None:
        parsed = WrittenReference.parsed(reference().strip())
        self.assertEqual((QUOTATION, "book", 1, "The locus classicus."),
                         (parsed.quotation, parsed.source, parsed.file_page, parsed.comment))

    def test_a_reference_citing_a_recording_names_no_file_page(self) -> None:
        block = f"> **states** · “{QUOTATION}”\n> \t[[talk]], [00:14:05](https://example.org/talk)"
        self.assertIsNone(WrittenReference.parsed(block).file_page)

    def test_a_block_out_of_the_shape_is_not_a_reference(self) -> None:
        self.assertIsNone(WrittenReference.parsed("> a stray line"))


class TestHighlightChoices(unittest.TestCase):
    CLAIM = "Cf. Houlgate 2022, p. 152: holds that Hegel asserts this."
    DISPUTE = "Cf. Brandom 2002, p. 180: reads it as material incompatibility.\nContra: Pippin 2019, p. 162: reads it otherwise."
    POINTER = "Cf. Logic (Hegel 2010, p. 290).\nParallels: Lectures (p. 163)."

    def colour(self, comment: str, choices: HighlightChoices = HighlightChoices(group="blue")) -> str:
        return choices.colour_of("book", comment)

    def test_a_claim_comment_takes_the_notes_group(self) -> None:
        self.assertEqual("blue", self.colour(self.CLAIM))

    def test_a_claim_comment_in_a_note_of_practical_philosophy_takes_green(self) -> None:
        self.assertEqual("green", self.colour(self.CLAIM, HighlightChoices(group="green")))

    def test_a_claim_comment_in_a_core_work_takes_yellow(self) -> None:
        self.assertEqual("yellow", self.colour(self.CLAIM, HighlightChoices(core=("book",))))

    def test_a_reference_without_a_comment_takes_the_claim_kinds_colour(self) -> None:
        self.assertEqual("blue", self.colour(""))

    def test_a_dispute_comment_takes_orange_even_in_a_core_work(self) -> None:
        self.assertEqual("orange", self.colour(self.DISPUTE, HighlightChoices(core=("book",))))

    def test_a_pointer_comment_takes_gray(self) -> None:
        self.assertEqual("gray", self.colour(self.POINTER))

    def test_a_pointer_comment_in_a_core_work_takes_gray(self) -> None:
        self.assertEqual("gray", self.colour(self.POINTER, HighlightChoices(core=("book",))))

    def test_a_search_term_line_makes_a_claim_comment(self) -> None:
        self.assertEqual("blue", self.colour("Hegel on Kant's antinomies.\nParallels: Logic (p. 290)."))

    def test_a_claim_comment_outside_the_core_works_of_a_note_naming_no_group_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "--group"):
            self.colour(self.CLAIM, HighlightChoices())

    def test_a_group_other_than_blue_or_green_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "--group"):
            HighlightChoices(group="magenta")

    def test_a_named_colour_overrides_the_kind_outside_the_core_works(self) -> None:
        self.assertEqual("purple", self.colour(self.POINTER, HighlightChoices(named="purple")))


class TestTaggedEntries(unittest.TestCase):
    def test_the_entry_of_the_note_takes_the_new_tags(self) -> None:
        content = f"[[{IDEA}]] — why\n#[[Old]]"
        self.assertEqual(f"[[{IDEA}]] — why\n#[[Paper]] #[[Kant]]", TaggedEntries(IDEA, ["Paper", "Kant"]).of(content))

    def test_an_entry_closing_on_the_link_separator_loses_it(self) -> None:
        self.assertEqual(f"[[{IDEA}]]\n#[[Kant]]", TaggedEntries(IDEA, ["Kant"]).of(f"[[{IDEA}]] —\n#[[Old]]"))

    def test_another_commentators_entry_is_left_as_it_is(self) -> None:
        content = f"[[Another note]] — other\n#[[Old]]\n\n[[{IDEA}]] — why"
        self.assertEqual(f"[[Another note]] — other\n#[[Old]]\n\n[[{IDEA}]] — why\n#[[Kant]]",
                         TaggedEntries(IDEA, ["Kant"]).of(content))


class TestNoteHighlighting(SayingBook):
    def setUp(self) -> None:
        super().setUp()
        self.folders = WritingFolders(self.directory / "writing")
        self.folders.notes.mkdir(parents=True)
        located = mock.patch.object(vault, "LibraryPdf", lambda source: mock.Mock(path=lambda: Path(self.copy)))
        located.start()
        self.addCleanup(located.stop)

    def highlighting(self, text: str, colour: str | None = None) -> NoteHighlighting:
        self.folders.atomic_note(IDEA).write_text(text, encoding="utf-8")
        return NoteHighlighting(NoteFile(self.folders, IDEA), HighlightChoices(colour, group="blue"))

    def test_a_reference_becomes_a_highlight_over_its_quotation(self) -> None:
        self.highlighting(note_text(reference())).apply()
        self.assertEqual("Thoughts without content are empty, intuitions are blind.", self.records()[0].covered)

    def test_a_reference_that_joins_two_passages_of_a_page_takes_one_highlight_over_both(self) -> None:
        joined = "Thoughts without content […] intuitions are blind."
        self.highlighting(note_text(reference(joined))).apply()
        self.assertEqual([joined], [record.covered for record in self.records()])

    def test_a_joint_highlight_written_once_is_not_written_again(self) -> None:
        joined = "Thoughts without content […] intuitions are blind."
        self.highlighting(note_text(reference(joined))).apply()
        self.highlighting(note_text(reference(joined))).apply()
        self.assertEqual(1, len(self.records()))

    def test_a_field_the_comment_names_stands_in_the_comment_and_not_among_the_tags(self) -> None:
        self.highlighting(note_text(reference(comment="> \tThe locus classicus in kant.\n"))).apply()
        self.assertEqual(f"[[{IDEA}]] — The locus classicus in #[[Kant]].\n#[[Paper]]", self.records()[0].note)

    def test_a_project_the_comment_names_stays_among_the_tags(self) -> None:
        self.highlighting(note_text(reference(comment="> \tThe paper's locus classicus.\n"))).apply()
        self.assertEqual(f"[[{IDEA}]] — The paper's locus classicus.\n#[[Paper]] #[[Kant]]", self.records()[0].note)

    def test_a_field_set_in_the_comment_returns_to_plain_words_once_the_note_leaves_the_field(self) -> None:
        self.highlighting(note_text(reference(comment="> \tThe locus classicus in kant.\n"))).apply()
        moved = note_text(reference(comment="> \tThe locus classicus in kant.\n"),
                          "---\nprojects:\n- '[[Paper]]'\nfield:\n- '[[Logic]]'\n---\n")
        self.highlighting(moved).apply()
        self.assertEqual(f"[[{IDEA}]] — The locus classicus in kant.\n#[[Paper]] #[[Logic]]", self.records()[0].note)

    def test_a_work_named_generic_takes_yellow_whatever_colour_the_note_takes(self) -> None:
        self.folders.atomic_note(IDEA).write_text(note_text(reference()), encoding="utf-8")
        NoteHighlighting(NoteFile(self.folders, IDEA), HighlightChoices("blue", ("book",))).apply()
        self.assertEqual("yellow", PdfHighlights("book", "").as_json()["highlights"][0]["colour"])

    def test_a_work_named_generic_after_its_highlight_was_written_is_recoloured_yellow(self) -> None:
        self.highlighting(note_text(reference()), "blue").apply()
        NoteHighlighting(NoteFile(self.folders, IDEA), HighlightChoices(core=("book",))).apply()
        self.assertEqual("yellow", PdfHighlights("book", "").as_json()["highlights"][0]["colour"])

    def test_a_generic_work_the_note_does_not_cite_is_refused(self) -> None:
        self.folders.atomic_note(IDEA).write_text(note_text(reference()), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no accepted reference"):
            NoteHighlighting(NoteFile(self.folders, IDEA), HighlightChoices(core=("another book",)))

    def another(self, text: str) -> NoteHighlighting:
        self.folders.atomic_note("Another idea").write_text(text, encoding="utf-8")
        return NoteHighlighting(NoteFile(self.folders, "Another idea"), HighlightChoices(group="blue"))

    def test_a_second_notes_longer_passage_extends_the_highlight_the_first_note_wrote(self) -> None:
        self.highlighting(note_text(reference("Thoughts without content are empty,"))).apply()
        self.another(note_text(reference(comment="> \tSecond.\n"))).apply()
        self.assertEqual([QUOTATION], [record.covered for record in self.records()])

    def test_a_second_notes_passage_within_the_highlight_leaves_its_extent(self) -> None:
        self.highlighting(note_text(reference())).apply()
        self.another(note_text(reference("Thoughts without content are empty,", comment="> \tSecond.\n"))).apply()
        self.assertEqual([QUOTATION], [record.covered for record in self.records()])

    def test_an_extended_highlight_keeps_both_notes_entries(self) -> None:
        self.highlighting(note_text(reference("Thoughts without content are empty,"))).apply()
        self.another(note_text(reference(comment="> \tSecond.\n"))).apply()
        self.assertEqual(f"[[{IDEA}]] — The locus classicus.\n#[[Paper]] #[[Kant]]\n\n"
                         "[[Another idea]] — Second.\n#[[Paper]] #[[Kant]]", self.records()[0].note)

    def test_a_named_colour_leaves_the_colour_of_a_highlight_another_note_shares(self) -> None:
        self.highlighting(note_text(reference()), "blue").apply()
        self.folders.atomic_note("Another idea").write_text(note_text(reference(comment="")), encoding="utf-8")
        NoteHighlighting(NoteFile(self.folders, "Another idea"), HighlightChoices("yellow")).apply()
        self.assertEqual("blue", PdfHighlights("book", "").as_json()["highlights"][0]["colour"])

    def test_a_comment_changed_in_the_note_is_rewritten_in_the_highlight_it_already_has(self) -> None:
        self.highlighting(note_text(reference())).apply()
        self.highlighting(note_text(reference(comment="> \tA later comment.\n"))).apply()
        self.assertEqual([f"[[{IDEA}]] — A later comment.\n#[[Paper]] #[[Kant]]"], [r.note for r in self.records()])

    def test_another_notes_entry_on_the_highlight_is_kept_beside_the_rewritten_one(self) -> None:
        self.highlighting(note_text(reference())).apply()
        self.folders.atomic_note("Another idea").write_text(note_text(reference(comment="> \tSecond.\n")), encoding="utf-8")
        NoteHighlighting(NoteFile(self.folders, "Another idea"), HighlightChoices(group="blue")).apply()
        self.highlighting(note_text(reference(comment="> \tA later comment.\n"))).apply()
        self.assertEqual(f"[[{IDEA}]] — A later comment.\n#[[Paper]] #[[Kant]]\n\n"
                         "[[Another idea]] — Second.\n#[[Paper]] #[[Kant]]", self.records()[0].note)

    def test_a_comment_of_several_lines_stands_line_by_line_beneath_the_notes_link(self) -> None:
        self.highlighting(note_text(reference(comment="> \tCf. one work.\n> \tParallels: another passage.\n"))).apply()
        self.assertEqual(f"[[{IDEA}]]\nCf. one work.\nParallels: another passage.\n#[[Paper]] #[[Kant]]",
                         self.records()[0].note)

    def test_a_comment_of_several_lines_is_written_once_however_often_the_note_is_highlighted(self) -> None:
        lines = note_text(reference(comment="> \tCf. one work.\n> \tParallels: another passage.\n"))
        self.highlighting(lines).apply()
        self.highlighting(lines).apply()
        self.assertEqual(f"[[{IDEA}]]\nCf. one work.\nParallels: another passage.\n#[[Paper]] #[[Kant]]",
                         self.records()[0].note)

    def test_a_named_colour_recolours_the_highlight_the_note_already_has(self) -> None:
        self.highlighting(note_text(reference())).apply()
        self.highlighting(note_text(reference()), "blue").apply()
        self.assertEqual("blue", PdfHighlights("book", "").as_json()["highlights"][0]["colour"])

    def test_a_joined_passage_the_page_does_not_carry_is_reported_alone(self) -> None:
        joined = "Thoughts without content are empty, […] Words the page never prints."
        plan = self.highlighting(note_text(reference(joined))).plan()
        self.assertEqual(["Words the page never prints."], plan["pdfs"][0]["quotations_not_located"])

    def test_a_reference_still_marked_for_review_takes_no_highlight(self) -> None:
        self.highlighting(note_text(reference(mark="review"))).apply()
        self.assertEqual([], self.records())

    def test_a_reference_that_carries_neither_mark_takes_no_highlight(self) -> None:
        self.highlighting(note_text(reference().replace(" #accepted", ""))).apply()
        self.assertEqual([], self.records())

    def test_the_plan_counts_the_references_the_user_has_not_accepted(self) -> None:
        plan = self.highlighting(note_text(reference(mark="review") + "\n" + reference(QUOTATION, 1))).plan()
        self.assertEqual((1, 1), (plan["references_not_accepted"], len(plan["pdfs"])))

    def test_the_highlight_carries_the_notes_link_the_comment_and_the_notes_projects_and_topics(self) -> None:
        self.highlighting(note_text(reference())).apply()
        self.assertEqual(f"[[{IDEA}]] — The locus classicus.\n#[[Paper]] #[[Kant]]", self.records()[0].note)

    def test_a_reference_without_a_comment_carries_the_notes_link_alone_before_its_tags(self) -> None:
        self.highlighting(note_text(reference(comment=""))).apply()
        self.assertEqual(f"[[{IDEA}]]\n#[[Paper]] #[[Kant]]", self.records()[0].note)

    def test_a_highlight_without_a_comment_is_retagged_when_the_note_joins_another_project(self) -> None:
        self.highlighting(note_text(reference(comment=""))).apply()
        moved = note_text(reference(comment=""), "---\nprojects:\n- '[[Thesis]]'\nfield:\n- '[[Kant]]'\n---\n")
        self.highlighting(moved).apply()
        self.assertTrue(self.records()[0].note.endswith("#[[Thesis]] #[[Kant]]"))

    def test_the_highlight_takes_the_colour_of_the_notes_group_whatever_its_topic(self) -> None:
        self.highlighting(note_text(reference())).apply()
        self.assertEqual("blue", PdfHighlights("book", "").as_json()["highlights"][0]["colour"])

    def test_a_highlight_the_note_already_has_takes_its_references_new_role_colour(self) -> None:
        self.highlighting(note_text(reference())).apply()
        self.highlighting(note_text(reference(comment="> \tCf. Logic (Hegel 2010, p. 290).\n"))).apply()
        self.assertEqual("gray", PdfHighlights("book", "").as_json()["highlights"][0]["colour"])

    def test_a_named_colour_overrides_the_topics(self) -> None:
        self.highlighting(note_text(reference()), "blue").apply()
        self.assertEqual("blue", PdfHighlights("book", "").as_json()["highlights"][0]["colour"])

    def test_writing_twice_leaves_one_highlight_and_one_entry(self) -> None:
        self.highlighting(note_text(reference())).apply()
        self.highlighting(note_text(reference())).apply()
        self.assertEqual((1, 1), (len(self.records()), self.records()[0].note.count(f"[[{IDEA}]] —")))

    def test_a_note_placed_on_another_project_retags_its_highlights(self) -> None:
        self.highlighting(note_text(reference())).apply()
        self.highlighting(note_text(reference(), "---\nprojects:\n- '[[Thesis]]'\nfield:\n- '[[Kant]]'\n---\n")).apply()
        self.assertTrue(self.records()[0].note.endswith("#[[Thesis]] #[[Kant]]"))

    def test_a_quotation_over_a_page_break_becomes_one_cross_page_span(self) -> None:
        self.highlighting(note_text(reference(BROKEN_QUOTATION, 2))).apply()
        self.assertEqual((2, 3), (self.records()[0].page, self.records()[0].end_page))

    def test_a_quotation_the_page_does_not_carry_is_reported_and_not_written(self) -> None:
        plan = self.highlighting(note_text(reference("Words the page never prints."))).plan()
        self.assertEqual(["Words the page never prints."], plan["pdfs"][0]["quotations_not_located"])

    def test_the_plan_writes_nothing(self) -> None:
        self.highlighting(note_text(reference())).plan()
        self.assertEqual([], self.records())

    def test_a_note_without_a_field_takes_its_groups_colour(self) -> None:
        self.highlighting(note_text(reference(), "")).apply()
        self.assertEqual("blue", PdfHighlights("book", "").as_json()["highlights"][0]["colour"])


if __name__ == "__main__":
    unittest.main()
