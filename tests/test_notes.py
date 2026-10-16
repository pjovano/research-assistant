from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest import mock

from _writing_fixtures import IDEA, OTHER_IDEA, WritingTestCase

import vault
from _writing.atomic_note import AtomicNote
from _writing.claims import ClaimsBlock
from _writing.note_lines import ClaimLine, ClaimWording, Explication, NoteFile, NoteTask, ReferenceFraming, ReferenceWriting
from _writing.notes_cli import NotesCommandLine
from _writing.placement import NoteCreation
from _writing.task_list import ACCEPT_TASK
from _writing.quotations import (
    CompoundQuotation, HeldQuotations, PdfQuotation, QuotationRequest, TranscriptQuotation, UncitableQuotation,
    VerifiedQuotation,
)

SOURCE = "Kant - 1998 - Critique of Pure Reason"
PAGE_WORDS = "Thoughts without content are empty, intuitions without concepts are blind."
LINK = "zotero://open-pdf/library/items/ABCD1234?page=193"
HIT = {"pdf_page": 193, "printed_page": "A51/B75", "page_text": PAGE_WORDS, "link": LINK}
TALK = "Lawvere - 1992 - Categories of Space and of Quantity"
TALK_TEXT = ("[Recording](https://example.org/talk)\n\n%% 00:00:05 %%\n\n**Lawvere:** Being is the first "
             "category.\n\n%% 00:14:05 %%\n\n**Lawvere:** Quantity is the negation\nof quality.\n")


class StubVerification:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def payload(self, request: QuotationRequest) -> dict:
        return self._payload


def verdict(**fields) -> dict:
    return {"verified": True, "ambiguous": False, "notation_read_from_page": [], "hits": [HIT], **fields}


class TestNoteCreation(WritingTestCase):
    def test_the_note_is_named_by_its_title_and_written_as_a_blank_claim_above_its_references_and_its_accept_task(self) -> None:
        self.note()
        self.assertEqual(self.folders.atomic_note(IDEA).read_text(encoding="utf-8"),
                         f"- \n\n# References\n\n# Tasks\n\n{ACCEPT_TASK}\n")

    def test_the_plan_writes_nothing(self) -> None:
        NoteCreation(self.folders, IDEA).plan()
        self.assertFalse(self.folders.notes.exists())

    def test_an_existing_note_is_never_overwritten(self) -> None:
        self.note()
        with self.assertRaisesRegex(ValueError, "exists"):
            NoteCreation(self.folders, IDEA)

    def test_a_title_holding_a_character_no_filename_takes_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "holds none of"):
            NoteCreation(self.folders, "Is construction a proof?")

    def test_a_title_too_long_for_a_filename_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most"):
            NoteCreation(self.folders, "word " * 50)


class TestClaimsBlock(unittest.TestCase):
    BLOCK = "- first\n\t- a precision\n- second"

    def test_a_claim_is_reworded_in_its_place_with_its_explications_kept(self) -> None:
        self.assertEqual("- first, sharper\n\t- a precision\n- second",
                         ClaimsBlock(self.BLOCK).with_claim(1, "first, sharper").text)

    def test_explications_are_listed_beneath_their_claims(self) -> None:
        self.assertEqual([["a precision"], []], ClaimsBlock(self.BLOCK).explications())

    def test_a_claim_carrying_the_accepted_mark_is_never_reworded(self) -> None:
        with self.assertRaisesRegex(ValueError, "accepted mark"):
            ClaimsBlock("- first #accepted").with_claim(1, "first, sharper")

    def test_the_blank_claim_of_a_new_note_is_replaced_by_the_first_claim(self) -> None:
        self.assertEqual("- first", ClaimsBlock("- ").with_claim(1, "first").text)

    def test_the_next_claim_is_added_last(self) -> None:
        self.assertEqual(["first", "second", "third"], ClaimsBlock(self.BLOCK).with_claim(3, "third").claims())

    def test_a_claim_past_the_next_one_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "no claim 3"):
            ClaimsBlock("- first").with_claim(3, "third")

    def test_a_fourth_claim_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most 3"):
            ClaimsBlock("- a\n- b\n- c").with_claim(4, "d")

    def test_an_explication_goes_last_beneath_its_claim_and_above_the_next(self) -> None:
        self.assertEqual("- first\n\t- a precision\n\t- another\n- second",
                         ClaimsBlock(self.BLOCK).with_explication(1, "another").text)

    def test_an_explication_of_an_absent_claim_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "no claim 3"):
            ClaimsBlock(self.BLOCK).with_explication(3, "another")


class NoteTestCase(WritingTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.note()
        self.file = NoteFile(self.folders, IDEA)

    def written(self) -> str:
        return self.folders.atomic_note(IDEA).read_text(encoding="utf-8")


class TestNoteLines(NoteTestCase):
    def test_a_claim_is_written_with_the_review_mark(self) -> None:
        ClaimWording(self.file, ClaimLine(1, "Construction is proof")).apply()
        self.assertTrue(self.written().startswith("- Construction is proof #review\n"))

    def test_a_claim_already_marked_is_marked_once(self) -> None:
        ClaimWording(self.file, ClaimLine(1, "Construction is proof #review")).apply()
        self.assertEqual(1, self.written().count("#review"))

    def test_a_blank_claim_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "holds words"):
            ClaimWording(self.file, ClaimLine(1, "  "))

    def test_the_plan_of_a_claim_writes_nothing(self) -> None:
        before = self.written()
        ClaimWording(self.file, ClaimLine(1, "Construction is proof")).plan()
        self.assertEqual(before, self.written())

    def test_an_explication_is_written_beneath_its_claim_with_the_review_mark(self) -> None:
        ClaimWording(self.file, ClaimLine(1, "Construction is proof")).apply()
        Explication(self.file, ClaimLine(1, "Proof here means exhibition in intuition")).apply()
        self.assertIn("\n\t- Proof here means exhibition in intuition #review\n\n# References", self.written())

    def test_a_task_is_written_last_under_the_tasks_after_the_accept_task_without_a_review_mark(self) -> None:
        NoteTask(self.file, "#enrich · Read the Discipline of Pure Reason").apply()
        self.assertTrue(self.written().endswith(f"# Tasks\n\n{ACCEPT_TASK}\n- [ ] #enrich · Read the Discipline of Pure Reason\n"))

    def test_a_note_that_is_not_written_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "no note named"):
            NoteFile(self.folders, "An unwritten idea")


class TestReferenceWriting(NoteTestCase):
    QUOTATION = VerifiedQuotation(SOURCE, PAGE_WORDS, "p. A51/B75", LINK)

    GROUP = "Primary texts"

    def write(self, framing: ReferenceFraming, quotation: VerifiedQuotation = QUOTATION) -> None:
        ReferenceWriting(self.file, quotation, framing).apply()

    def test_a_reference_is_its_quotation_line_its_source_line_and_its_comment_line(self) -> None:
        self.write(ReferenceFraming("states", "The locus classicus.", group=self.GROUP))
        self.assertIn(f"# References\n\n### Primary texts\n\n> **states** · “{PAGE_WORDS}” #review\n"
                      f"> \t[[{SOURCE}]], [p. A51/B75]({LINK})\n> \tThe locus classicus.\n\n# Tasks",
                      self.written())

    def test_a_reference_without_a_comment_has_no_comment_line(self) -> None:
        self.write(ReferenceFraming("states", group=self.GROUP))
        self.assertEqual(2, len(AtomicNote(self.written()).reference_blocks()[0].splitlines()))

    def test_each_line_of_a_comment_stands_on_a_line_of_its_own_beneath_the_source(self) -> None:
        self.write(ReferenceFraming("states", "Cf. one work.\nParallels: another.", group=self.GROUP))
        self.assertIn("\n> \tCf. one work.\n> \tParallels: another.\n", self.written())

    def test_a_reference_without_a_link_cites_its_place_alone(self) -> None:
        self.write(ReferenceFraming("states", group=self.GROUP), VerifiedQuotation(SOURCE, PAGE_WORDS, "p. 3"))
        self.assertIn(f"> \t[[{SOURCE}]], p. 3\n", self.written())

    def test_a_reference_goes_last_unless_placed_after_another(self) -> None:
        self.write(ReferenceFraming("states", "first", group=self.GROUP))
        self.write(ReferenceFraming("supports", "third", group=self.GROUP))
        self.write(ReferenceFraming("discusses", "second", after=1))
        order = [block.splitlines()[2] for block in AtomicNote(self.written()).reference_blocks()]
        self.assertEqual(["> \tfirst", "> \tsecond", "> \tthird"], order)

    def test_a_reference_carries_one_review_mark_on_its_quotation_line(self) -> None:
        self.write(ReferenceFraming("states", "The locus classicus.", group=self.GROUP))
        self.assertEqual(1, self.written().count("#review"))

    def test_a_reference_named_neither_a_group_nor_the_reference_it_follows_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "stands under a group"):
            ReferenceWriting(self.file, self.QUOTATION, ReferenceFraming("states"))

    def test_a_reference_stands_last_under_its_group_and_a_new_group_stands_last(self) -> None:
        self.write(ReferenceFraming("states", "first", group=self.GROUP))
        self.write(ReferenceFraming("discusses", "third", group="Secondary literature"))
        self.write(ReferenceFraming("states", "second", group=self.GROUP))
        lines = [line for line in self.written().splitlines() if line.startswith("### ") or line in (
            "> \tfirst", "> \tsecond", "> \tthird")]
        self.assertEqual(["### Primary texts", "> \tfirst", "> \tsecond", "### Secondary literature", "> \tthird"], lines)

    def group_headings(self) -> list[str]:
        return [line for line in self.written().splitlines() if line.startswith("### ")]

    def test_a_new_group_named_before_a_held_group_stands_before_it(self) -> None:
        self.write(ReferenceFraming("discusses", group="Secondary literature"))
        self.write(ReferenceFraming("discusses", group="The debate"))
        self.write(ReferenceFraming("states", group=self.GROUP, before="The debate"))
        self.assertEqual(["### Secondary literature", "### Primary texts", "### The debate"], self.group_headings())

    def test_a_reference_under_a_new_group_placed_before_another_stands_under_the_new_group(self) -> None:
        self.write(ReferenceFraming("discusses", "later", group="Secondary literature"))
        self.write(ReferenceFraming("states", "earlier", group=self.GROUP, before="Secondary literature"))
        self.assertIn("### Primary texts\n\n> **states**", self.written())
        self.assertLess(self.written().index("> \tearlier"), self.written().index("> \tlater"))

    def test_a_new_group_named_before_a_group_the_note_lacks_is_refused(self) -> None:
        self.write(ReferenceFraming("discusses", group="Secondary literature"))
        with self.assertRaisesRegex(ValueError, "holds no group 'The debate'"):
            ReferenceWriting(self.file, self.QUOTATION, ReferenceFraming("states", group=self.GROUP, before="The debate"))

    def test_a_held_group_named_before_another_is_refused_and_never_moved(self) -> None:
        self.write(ReferenceFraming("discusses", group="Secondary literature"))
        self.write(ReferenceFraming("states", group=self.GROUP))
        with self.assertRaisesRegex(ValueError, "a held group is never moved"):
            ReferenceWriting(self.file, self.QUOTATION,
                             ReferenceFraming("states", group=self.GROUP, before="Secondary literature"))
        self.assertEqual(["### Secondary literature", "### Primary texts"], self.group_headings())

    def test_a_group_placed_before_another_beside_the_reference_it_follows_is_refused(self) -> None:
        self.write(ReferenceFraming("discusses", group="Secondary literature"))
        with self.assertRaisesRegex(ValueError, "never goes with --after"):
            ReferenceWriting(self.file, self.QUOTATION,
                             ReferenceFraming("states", after=1, group=self.GROUP, before="Secondary literature"))

    def test_a_reference_placed_after_another_stands_in_that_references_group(self) -> None:
        self.write(ReferenceFraming("states", "first", group=self.GROUP))
        self.write(ReferenceFraming("discusses", "third", group="Secondary literature"))
        self.write(ReferenceFraming("states", "second", after=1))
        self.assertIn("> \tfirst\n\n> **states**", self.written())

    def test_the_references_to_one_work_stand_together_in_their_group_in_the_order_of_its_pages(self) -> None:
        other = VerifiedQuotation("Friedman - 1992 - Kant and the Exact Sciences", "Other words.", "p. 9", f"{LINK}9")
        late = VerifiedQuotation(SOURCE, "Later words.", "p. 300", f"{LINK[:-3]}300")
        early = VerifiedQuotation(SOURCE, "Earlier words.", "p. 12", f"{LINK[:-3]}012")
        for quotation in (late, other, early):
            self.write(ReferenceFraming("states", group=self.GROUP), quotation)
        order = [block.splitlines()[0] for block in AtomicNote(self.written()).reference_blocks()]
        self.assertEqual(["Earlier words.", "Later words.", "Other words."], [line.split("“")[1].split("”")[0] for line in order])

    def test_a_group_heading_is_no_reference(self) -> None:
        self.write(ReferenceFraming("states", group=self.GROUP))
        self.assertEqual(1, len(AtomicNote(self.written()).reference_blocks()))

    def test_a_reference_placed_after_one_the_note_lacks_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "none is number 2"):
            ReferenceWriting(self.file, self.QUOTATION, ReferenceFraming("states", after=2))

    def test_a_relation_outside_the_vocabulary_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "a quotation's relation is one of"):
            ReferenceWriting(self.file, self.QUOTATION, ReferenceFraming("proves", group=self.GROUP))

    def test_the_plan_names_the_notation_to_read_on_the_page(self) -> None:
        quotation = VerifiedQuotation(SOURCE, PAGE_WORDS, "p. 3", notation_to_read=("$a + b$",))
        plan = ReferenceWriting(self.file, quotation, ReferenceFraming("states", group=self.GROUP)).plan()
        self.assertEqual(["$a + b$"], plan["notation_to_read_on_the_page"])


class PassagesByWords:
    def __init__(self, pages: dict[str, int]) -> None:
        self._pages = pages

    def verified(self, request: QuotationRequest) -> VerifiedQuotation:
        page = self._pages[request.quotation]
        return VerifiedQuotation(request.source, request.quotation.upper(), f"p. {page}", f"{LINK}{page}",
                                 file_page=page)


class TestCompoundQuotation(unittest.TestCase):
    def verified(self, quotation: str, pages: dict[str, int]) -> VerifiedQuotation:
        return CompoundQuotation(PassagesByWords(pages)).verified(QuotationRequest(SOURCE, quotation))

    def test_the_passages_of_one_page_are_one_quotation_joined_where_words_are_left_out(self) -> None:
        quotation = self.verified("one passage […] another passage", {"one passage": 7, "another passage": 7})
        self.assertEqual(("ONE PASSAGE […] ANOTHER PASSAGE", "p. 7", f"{LINK}7"),
                         (quotation.wording, quotation.locator, quotation.link))

    def test_passages_that_run_on_to_the_next_page_are_cited_by_both_folios(self) -> None:
        quotation = self.verified("one passage […] another passage", {"one passage": 7, "another passage": 8})
        self.assertEqual("pp. 7–8", quotation.locator)

    def test_a_passage_two_pages_on_is_refused_a_place_in_the_reference(self) -> None:
        with self.assertRaisesRegex(ValueError, "a reference of its own"):
            self.verified("one passage […] another passage", {"one passage": 7, "another passage": 9})

    def test_passages_given_out_of_the_pages_order_are_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "in the page's order"):
            self.verified("one passage […] another passage", {"one passage": 8, "another passage": 7})

    def test_a_quotation_without_an_omission_is_verified_as_it_stands(self) -> None:
        self.assertEqual("ONE PASSAGE", self.verified("one passage", {"one passage": 7}).wording)


class TestPdfQuotation(unittest.TestCase):
    REQUEST = QuotationRequest(SOURCE, "Thoughts without content are empty")

    def verified(self, payload: dict) -> VerifiedQuotation:
        return PdfQuotation(StubVerification(payload)).verified(self.REQUEST)

    def test_a_confirmed_quotation_takes_the_pages_words_its_folio_and_its_link(self) -> None:
        quotation = self.verified(verdict())
        self.assertEqual((PAGE_WORDS, "p. A51/B75", LINK), (quotation.wording, quotation.locator, quotation.link))

    def test_a_page_that_prints_no_folio_is_cited_by_its_file_page(self) -> None:
        self.assertEqual("file p. 193", self.verified(verdict(hits=[{**HIT, "printed_page": None}])).locator)

    def test_a_quotation_found_on_no_page_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "on no page"):
            self.verified(verdict(verified=False, hits=[]))

    def test_a_near_match_is_refused_with_the_pages_words(self) -> None:
        with self.assertRaisesRegex(ValueError, "file p. 193 reads"):
            self.verified(verdict(verified=False))

    def test_a_quotation_on_more_than_one_page_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "more than one page"):
            self.verified(verdict(ambiguous=True))


class HeldSourceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        import shutil
        import tempfile
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def held(self, name: str, text: str) -> Path:
        path = self.root / f"{name}.md"
        path.write_text(text, encoding="utf-8")
        return path


class TestTranscriptQuotation(HeldSourceTestCase):
    def quoted(self, quotation: str) -> VerifiedQuotation:
        return TranscriptQuotation(self.held(TALK, TALK_TEXT)).verified(QuotationRequest(TALK, quotation))

    def test_a_passage_is_cited_by_the_time_marker_before_it_with_the_recording(self) -> None:
        quotation = self.quoted("Quantity is the negation of quality.")
        self.assertEqual(("00:14:05", "https://example.org/talk"), (quotation.locator, quotation.link))

    def test_a_passage_broken_over_two_lines_is_quoted_on_one(self) -> None:
        self.assertEqual("Quantity is the negation of quality.", self.quoted("Quantity is the negation of quality.").wording)

    def test_words_the_transcript_does_not_carry_are_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "0 times"):
            self.quoted("Quality is the negation of quantity.")

    def test_a_span_the_transcript_carries_twice_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "2 times"):
            self.quoted("is the")


class TestUncitableQuotation(HeldSourceTestCase):
    REQUEST = QuotationRequest(SOURCE, "Thoughts without content are empty", "Transcendental Logic, Introduction, §I")

    def test_a_quotation_of_an_uncitable_work_cites_chapter_and_section_with_the_folio_unverified(self) -> None:
        corpus_file = self.held(SOURCE, "---\nuncitable: a reset edition\n---\n\nbody\n")
        self.assertEqual("Transcendental Logic, Introduction, §I (folio unverified)",
                         UncitableQuotation(corpus_file).verified(self.REQUEST).locator)

    def test_a_locator_for_a_citable_work_is_refused(self) -> None:
        corpus_file = self.held(SOURCE, "---\ntitle: Critique\n---\n\nbody\n")
        with self.assertRaisesRegex(ValueError, "takes no locator"):
            UncitableQuotation(corpus_file).verified(self.REQUEST)


class TestHeldQuotations(HeldSourceTestCase):
    def verified(self, source: str) -> VerifiedQuotation:
        request = QuotationRequest(source, "Quantity is the negation of quality.")
        with mock.patch.object(vault, "transcript_path", lambda name: self.root / "talks" / f"{name}.md"), \
                mock.patch.object(vault, "corpus_path", lambda name: self.root / f"{name}.md"):
            return HeldQuotations(StubVerification(verdict())).verified(request)

    def test_a_corpus_file_is_verified_in_its_pdf(self) -> None:
        self.held(SOURCE, "body")
        self.assertEqual("p. A51/B75", self.verified(SOURCE).locator)

    def test_a_transcript_is_read_in_its_own_text(self) -> None:
        (self.root / "talks").mkdir()
        (self.root / "talks" / f"{TALK}.md").write_text(TALK_TEXT, encoding="utf-8")
        self.assertEqual("00:14:05", self.verified(TALK).locator)

    def test_an_unheld_work_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "an unheld work takes a task"):
            self.verified("Ghost - 1900 - Nothing")


class TestNotesCommandLine(WritingTestCase):
    def run_command(self, *argv: str) -> dict:
        out = io.StringIO()
        with mock.patch.object(vault, "WRITING_DIR", self.writing_dir), contextlib.redirect_stdout(out):
            NotesCommandLine().run(list(argv))
        return json.loads(out.getvalue())

    def written(self) -> str:
        return self.folders.atomic_note(IDEA).read_text(encoding="utf-8")

    def test_note_without_apply_writes_nothing(self) -> None:
        self.assertFalse(self.run_command("note", IDEA)["applied"])
        self.assertFalse(self.folders.notes.exists())

    def test_a_note_built_through_the_commands_passes_its_check(self) -> None:
        self.run_command("note", IDEA, "--apply")
        self.run_command("claim", IDEA, "1", "Construction is proof", "--apply")
        self.run_command("explicate", IDEA, "1", "Proof here means exhibition", "--apply")
        self.run_command("task", IDEA, "#enrich · Read the Discipline of Pure Reason", "--apply")
        report = self.run_command("check", IDEA)
        self.assertEqual(([], 1, 2, 1), (report["findings"], report["claims"], report["to_review"], report["open_tasks"]))

    def test_a_task_given_with_its_checkbox_is_written_with_one(self) -> None:
        self.run_command("note", IDEA, "--apply")
        self.run_command("task", IDEA, "- [ ] #conceptual · Take notes on “Proof”: proof is exhibition", "--apply")
        self.assertIn("\n- [ ] #conceptual · Take notes on “Proof”", self.written())
        self.assertNotIn("- [ ] - [ ]", self.written())

    def test_check_finds_a_claim_with_a_second_explication_besides_its_relations(self) -> None:
        self.run_command("note", IDEA, "--apply")
        self.run_command("note", OTHER_IDEA, "--apply")
        self.run_command("claim", IDEA, "1", "Construction is proof", "--apply")
        self.run_command("explicate", IDEA, "1", "Proof here means exhibition", "--apply")
        self.run_command("relate", IDEA, "extends", OTHER_IDEA, "--apply")
        self.run_command("explicate", IDEA, "1", "Exhibition is in intuition", "--apply")
        with self.assertRaises(SystemExit):
            self.run_command("check", IDEA)

    def test_a_relation_is_no_second_explication(self) -> None:
        self.run_command("note", IDEA, "--apply")
        self.run_command("note", OTHER_IDEA, "--apply")
        self.run_command("claim", IDEA, "1", "Construction is proof", "--apply")
        self.run_command("explicate", IDEA, "1", "Proof here means exhibition", "--apply")
        self.run_command("relate", IDEA, "extends", OTHER_IDEA, "--apply")
        self.assertEqual([], self.run_command("check", IDEA)["findings"])

    def test_check_of_a_blank_note_exits_non_zero(self) -> None:
        self.run_command("note", IDEA, "--apply")
        with self.assertRaises(SystemExit) as refusal:
            self.run_command("check", IDEA)
        self.assertEqual(1, refusal.exception.code)

    def test_a_relation_is_marked_for_review_unless_the_user_stated_it(self) -> None:
        self.run_command("note", IDEA, "--apply")
        self.run_command("note", OTHER_IDEA, "--apply")
        self.run_command("relate", IDEA, "extends", OTHER_IDEA, "--apply")
        self.assertIn(f"\t- extends [[{OTHER_IDEA}]] #review", self.written())

    def test_a_relation_the_user_stated_carries_no_review_mark(self) -> None:
        self.run_command("note", IDEA, "--apply")
        self.run_command("note", OTHER_IDEA, "--apply")
        self.run_command("relate", IDEA, "extends", OTHER_IDEA, "--stated", "--apply")
        self.assertNotIn("#review", self.written())

    def test_a_reference_to_an_unheld_work_exits_with_its_reason(self) -> None:
        self.run_command("note", IDEA, "--apply")
        with mock.patch.object(vault, "transcript_path", lambda name: self.writing_dir / "no" / name), \
                mock.patch.object(vault, "corpus_path", lambda name: self.writing_dir / "no" / name):
            with self.assertRaisesRegex(SystemExit, "an unheld work takes a task"):
                self.run_command("reference", IDEA, "Ghost - 1900 - Nothing", "states", "words")


if __name__ == "__main__":
    unittest.main()
