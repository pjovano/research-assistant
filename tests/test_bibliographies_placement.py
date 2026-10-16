from __future__ import annotations

import contextlib
import io
import sys
import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import bibliographies
import vault
from _bibliographies.placement import WorkOrder
from _bibliography_fixtures import (
    PRIMARY_WORKS_HEADING,
    SECONDARY_WORKS_HEADING,
    EMPTY_SECTION_MARKER,
    HEGEL,
    HOULGATE,
    PIPPIN_TALK,
    TemporaryVault,
    works_section,
)

TRANSCRIPTS_HEADING = "Talk transcripts"
BACON = "Bacon - 1620 - Novum Organum"
FRE_DECOMPOSED = "Fre\u0301 - 2018 - Categories"
FRE_COMPOSED = "Fr\u00e9 - 2018 - Categories"


class TestPlacementOnATopicBibliography(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.note(HOULGATE, field=["[[Logic]]"], source_role="secondary")

    def test_the_work_is_added_to_the_works_section(self) -> None:
        self.vault.bibliography("Logic", works_section())
        self.vault.place(HOULGATE)
        self.assertIn(f"- [[{HOULGATE}]]", self.vault.body_of("Logic"))

    def test_the_new_work_is_inserted_at_its_sorted_position(self) -> None:
        self.vault.bibliography("Logic", works_section(f"- [[{BACON}]]", f"- [[{HOULGATE}]]"))
        self.vault.note(HEGEL, field=["[[Logic]]"], source_role="secondary")
        self.vault.place(HEGEL)
        listed = bibliographies.Section(SECONDARY_WORKS_HEADING).lines_in(self.vault.body_of("Logic"))
        self.assertEqual([f"- [[{BACON}]]", f"- [[{HEGEL}]]", f"- [[{HOULGATE}]]"], listed)

    def test_the_existing_order_of_the_works_is_kept(self) -> None:
        self.vault.bibliography("Logic", works_section(f"- [[{HEGEL}]]", f"- [[{BACON}]]"))
        self.vault.place(HOULGATE)
        listed = bibliographies.Section(SECONDARY_WORKS_HEADING).lines_in(self.vault.body_of("Logic"))
        self.assertEqual([f"- [[{HEGEL}]]", f"- [[{BACON}]]", f"- [[{HOULGATE}]]"], listed)

    def test_the_empty_marker_gives_way_to_the_first_work(self) -> None:
        self.vault.bibliography("Logic", works_section(EMPTY_SECTION_MARKER))
        self.vault.place(HOULGATE)
        self.assertNotIn(EMPTY_SECTION_MARKER, self.vault.body_of("Logic"))
        self.assertIn(f"- [[{HOULGATE}]]", self.vault.body_of("Logic"))

    def test_placing_the_same_work_twice_changes_nothing(self) -> None:
        self.vault.bibliography("Logic", works_section())
        self.vault.place(HOULGATE)
        self.assertEqual([], self.vault.plan_for(HOULGATE))

    def test_a_missing_works_section_is_appended_last(self) -> None:
        self.vault.bibliography("Logic", "## Scope\n\nWhat this bibliography covers.\n")
        self.vault.place(HOULGATE)
        headings = [line for line in self.vault.body_of("Logic").splitlines()
                    if line.startswith("## ")]
        self.assertEqual(["## Scope", f"## {SECONDARY_WORKS_HEADING}"], headings)

    def test_a_field_naming_no_bibliography_is_unresolved(self) -> None:
        with self.assertRaises(bibliographies.BibliographyNotFound):
            self.vault.plan_for(HOULGATE)


class TestAPrimaryWorkOnATopicBibliography(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.note(HEGEL, field=["[[Logic]]"], source_role="primary")

    def test_is_listed_under_the_primary_works(self) -> None:
        self.vault.bibliography("Logic", works_section(f"- [[{HOULGATE}]]"))
        self.vault.place(HEGEL)
        listed = bibliographies.Section(PRIMARY_WORKS_HEADING).lines_in(self.vault.body_of("Logic"))
        self.assertEqual([f"- [[{HEGEL}]]"], listed)

    def test_a_listing_under_the_works_in_library_moves_to_the_primary_works(self) -> None:
        self.vault.bibliography("Logic", works_section(f"- [[{HEGEL}]]", f"- [[{HOULGATE}]]"))
        self.vault.place(HEGEL)
        listed = bibliographies.Section(SECONDARY_WORKS_HEADING).lines_in(self.vault.body_of("Logic"))
        self.assertEqual([f"- [[{HOULGATE}]]"], listed)


class TestPlacementKeepsWhatItDoesNotOwn(unittest.TestCase):
    RAW = ("---\n# the root of the logic tree\nparent: \"[[Philosophy]]\"\n---\n\n"
           "## Secondary literature\n\nA line of prose.\n\n- [[%s]]\n")

    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.note(HOULGATE, field=["[[Logic]]"], source_role="secondary")
        self.path = self.vault.raw_bibliography("Logic", self.RAW % HEGEL)
        self.vault.place(HOULGATE)
        self.text = self.path.read_text(encoding="utf-8")

    def test_the_hand_written_frontmatter_survives_byte_for_byte(self) -> None:
        self.assertTrue(self.text.startswith("---\n# the root of the logic tree\nparent: \"[[Philosophy]]\"\n---\n"))

    def test_a_prose_line_in_the_list_stays_above_the_works(self) -> None:
        listed = bibliographies.Section(SECONDARY_WORKS_HEADING).lines_in(self.vault.body_of("Logic"))
        self.assertEqual(["A line of prose.", f"- [[{HEGEL}]]", f"- [[{HOULGATE}]]"], listed)

    def test_a_blank_run_outside_the_works_section_is_kept(self) -> None:
        self.vault.raw_bibliography("Logic", "---\nparent: \"[[Philosophy]]\"\n---\n\n## Scope\n\n\n\n"
                                             f"Spaced prose.\n\n## Secondary literature\n\n- [[{HEGEL}]]\n")
        self.vault.place(HOULGATE)
        self.assertIn("## Scope\n\n\n\nSpaced prose.\n", self.vault.body_of("Logic"))

    def test_a_prose_line_between_two_works_stays_between_them(self) -> None:
        self.vault.raw_bibliography("Logic", f"---\n---\n\n## Secondary literature\n\n- [[{BACON}]]\n\n"
                                             f"Prose between.\n\n- [[{HOULGATE}]]\n")
        self.vault.note(HEGEL, field=["[[Logic]]"], source_role="secondary")
        self.vault.place(HEGEL)
        listed = bibliographies.Section(SECONDARY_WORKS_HEADING).lines_in(self.vault.body_of("Logic"))
        self.assertEqual([f"- [[{BACON}]]", "Prose between.", f"- [[{HEGEL}]]", f"- [[{HOULGATE}]]"], listed)

    def test_an_annotated_listing_is_not_duplicated(self) -> None:
        self.vault.raw_bibliography("Logic", self.RAW % f"{HOULGATE}]] — a note on it")
        self.vault.place(HOULGATE)
        listed = bibliographies.Section(SECONDARY_WORKS_HEADING).lines_in(self.vault.body_of("Logic"))
        self.assertEqual(1, sum(HOULGATE in line for line in listed))


class TestABibliographyCarryingAListOfWorksTwice(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.bibliography("Logic", works_section(f"- [[{HEGEL}]]") + "\n" + works_section(f"- [[{BACON}]]"))
        self.vault.note(HOULGATE, field=["[[Logic]]"])

    def test_a_list_of_works_carried_twice_refuses_the_placement(self) -> None:
        with self.assertRaises(bibliographies.RepeatedWorkList):
            self.vault.plan_for(HOULGATE)

    def test_a_list_of_works_carried_twice_refuses_the_place_command_with_its_own_code(self) -> None:
        argv = ["bibliographies.py", "place", HOULGATE, "--apply"]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                bibliographies.CommandLine().run()
        self.assertEqual(bibliographies.EXIT_REPEATED_WORK_LIST, stopped.exception.code)
        self.assertIn(f"- [[{BACON}]]", self.vault.body_of("Logic"))

    def test_a_list_of_works_carried_twice_blocks_the_check(self) -> None:
        self.assertIn(f"Logic: carries ## {SECONDARY_WORKS_HEADING} twice", self.vault.printed_report())
        self.assertFalse(self.vault.report().is_clean)


class TestPlacementAcrossNormalizationForms(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def test_a_composed_listing_is_not_duplicated_by_a_decomposed_basename(self) -> None:
        self.vault.note(FRE_COMPOSED, field=["[[Logic]]"])
        self.vault.bibliography("Logic", works_section(f"- [[{FRE_COMPOSED}]]"))
        self.vault.place(FRE_DECOMPOSED)
        listed = bibliographies.Section(SECONDARY_WORKS_HEADING).lines_in(self.vault.body_of("Logic"))
        self.assertEqual([f"- [[{FRE_COMPOSED}]]"], listed)

    def test_a_new_listing_is_written_composed(self) -> None:
        self.vault.note(FRE_COMPOSED, field=["[[Logic]]"])
        self.vault.bibliography("Logic", works_section())
        self.vault.place(FRE_DECOMPOSED)
        self.assertIn(f"- [[{FRE_COMPOSED}]]", self.vault.body_of("Logic"))

    def test_a_composed_listing_of_a_decomposed_corpus_file_is_backed(self) -> None:
        self.vault.note(FRE_DECOMPOSED, field=["[[Logic]]"])
        self.vault.bibliography("Logic", works_section(f"- [[{FRE_COMPOSED}]]"))
        self.assertTrue(self.vault.report().is_clean)


class TestPlacementOnAnAuthorBibliography(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.bibliography("Hegel", author="Hegel")

    def test_a_work_the_author_wrote_goes_to_the_primary_works_section(self) -> None:
        self.vault.note(HEGEL, field=["[[Hegel]]"], author=["Hegel"], source_role="primary")
        self.vault.place(HEGEL)
        listed = bibliographies.Section(PRIMARY_WORKS_HEADING).lines_in(self.vault.body_of("Hegel"))
        self.assertEqual([f"- [[{HEGEL}]]"], listed)

    def test_an_unclassified_work_the_author_wrote_goes_to_the_primary_works_section(self) -> None:
        self.vault.note(HEGEL, field=["[[Hegel]]"], author=["Hegel"])
        self.vault.place(HEGEL)
        listed = bibliographies.Section(PRIMARY_WORKS_HEADING).lines_in(self.vault.body_of("Hegel"))
        self.assertEqual([f"- [[{HEGEL}]]"], listed)

    def test_a_work_by_another_hand_goes_to_the_secondary_literature_section(self) -> None:
        self.vault.note(HOULGATE, field=["[[Hegel]]"], author=["Houlgate"], source_role="secondary")
        self.vault.place(HOULGATE)
        listed = bibliographies.Section(SECONDARY_WORKS_HEADING).lines_in(
            self.vault.body_of("Hegel"))
        self.assertEqual([f"- [[{HOULGATE}]]"], listed)

    def test_a_work_the_author_wrote_with_another_goes_to_the_primary_works_section(self) -> None:
        collaboration = "Kaufmann and Hegel - 2017 - On Calculus"
        self.vault.note(collaboration, field=["[[Hegel]]"], author=["Kaufmann", "Hegel"])
        self.vault.place(collaboration)
        listed = bibliographies.Section(PRIMARY_WORKS_HEADING).lines_in(self.vault.body_of("Hegel"))
        self.assertEqual([f"- [[{collaboration}]]"], listed)

    def test_no_work_lands_in_the_topic_works_section(self) -> None:
        self.vault.note(HEGEL, field=["[[Hegel]]"], author=["Hegel"], source_role="primary")
        self.vault.place(HEGEL)
        self.assertNotIn(f"## {SECONDARY_WORKS_HEADING}", self.vault.body_of("Hegel"))


class TestAnAuthorBibliographyWhoseAuthorIsAList(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.bibliography("Hegel", author=["Hegel"])

    def test_a_work_the_listed_author_wrote_goes_to_the_primary_works_section(self) -> None:
        self.vault.note(HEGEL, field=["[[Hegel]]"], author=["Hegel"])
        self.vault.place(HEGEL)
        listed = bibliographies.Section(PRIMARY_WORKS_HEADING).lines_in(self.vault.body_of("Hegel"))
        self.assertEqual([f"- [[{HEGEL}]]"], listed)

    def test_the_listed_author_is_covered_by_the_bibliography(self) -> None:
        self.assertEqual({"hegel"}, bibliographies.Bibliographies().authors())


class TestPlacementOfATranscript(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def test_a_transcript_goes_to_the_transcripts_section_of_a_topic_bibliography(self) -> None:
        self.vault.bibliography("Logic")
        self.vault.transcript(PIPPIN_TALK, field=["[[Logic]]"], author=["Pippin"], source_role="secondary")
        self.vault.place(PIPPIN_TALK)
        listed = bibliographies.Section(TRANSCRIPTS_HEADING).lines_in(self.vault.body_of("Logic"))
        self.assertEqual([f"- [[{PIPPIN_TALK}]]"], listed)

    def test_a_transcript_by_the_author_goes_to_the_transcripts_section_of_the_author_bibliography(self) -> None:
        self.vault.bibliography("Pippin", author="Pippin")
        self.vault.transcript(PIPPIN_TALK, field=["[[Pippin]]"], author=["Pippin"], source_role="primary")
        self.vault.place(PIPPIN_TALK)
        self.assertNotIn(f"## {PRIMARY_WORKS_HEADING}", self.vault.body_of("Pippin"))
        listed = bibliographies.Section(TRANSCRIPTS_HEADING).lines_in(self.vault.body_of("Pippin"))
        self.assertEqual([f"- [[{PIPPIN_TALK}]]"], listed)

    def test_a_transcript_listing_its_field_names_is_clean(self) -> None:
        self.vault.transcript(PIPPIN_TALK, field=["[[Logic]]"], author=["Pippin"], source_role="secondary")
        self.vault.bibliography("Logic", f"## {TRANSCRIPTS_HEADING}\n\n- [[{PIPPIN_TALK}]]\n")
        self.assertTrue(self.vault.report().is_clean)

    def test_a_transcript_listing_no_transcript_backs_blocks(self) -> None:
        self.vault.bibliography("Logic", f"## {TRANSCRIPTS_HEADING}\n\n- [[{PIPPIN_TALK}]]\n")
        self.assertFalse(self.vault.report().is_clean)

    def test_a_transcript_whose_source_type_is_not_transcript_blocks(self) -> None:
        vault.write_frontmatter(vault.TRANSCRIPTS_DIR / f"{PIPPIN_TALK}.md", {"source_type": "article"}, "")
        self.assertIn(f"{PIPPIN_TALK}: a transcript's source_type is 'article'", self.vault.printed_report())
        self.assertFalse(self.vault.report().is_clean)

    def test_a_corpus_file_whose_source_type_is_transcript_blocks(self) -> None:
        self.vault.note(HEGEL, source_type="transcript")
        self.assertIn(f"{HEGEL}: a corpus file's source_type is 'transcript'", self.vault.printed_report())
        self.assertFalse(self.vault.report().is_clean)

    def test_a_transcript_is_found_by_its_basename(self) -> None:
        self.vault.transcript(PIPPIN_TALK, source_role="secondary")
        self.assertEqual(PIPPIN_TALK, bibliographies.Corpus().note(PIPPIN_TALK).basename)


if __name__ == "__main__":
    unittest.main()


ARISTOTLE = "Aristotle - 1984 - Metaphysics"
KANT_CRITIQUE = "Kant - 1998 - Critique of Pure Reason"
KANT_DISSERTATION = "Kant - 1894 - Kant's Inaugural Dissertation of 1770"
GROUPED = ("## Secondary literature\n\n### On the Deduction\n\n- [[%s]] — reads the Deduction as a regress.\n\n"
           "### On the Antinomies\n\nThese works, unlike [[Kant]]'s own, read the antinomies apart.\n\n- [[%s]]\n")


class TestChronologicalPlacement(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def listed(self) -> list[str]:
        return bibliographies.Section(SECONDARY_WORKS_HEADING).lines_in(self.vault.body_of("Logic"))

    def test_a_work_is_placed_by_its_original_year_before_its_edition_year(self) -> None:
        self.vault.bibliography("Logic", works_section(f"- [[{BACON}]]", f"- [[{HOULGATE}]]"))
        self.vault.note(KANT_CRITIQUE, field=["[[Logic]]"], year=1998, orig_year=1781)
        self.vault.place(KANT_CRITIQUE)
        self.assertEqual([f"- [[{BACON}]]", f"- [[{KANT_CRITIQUE}]]", f"- [[{HOULGATE}]]"], self.listed())

    def test_a_listed_works_original_year_orders_the_newcomer_after_it(self) -> None:
        self.vault.bibliography("Logic", works_section(f"- [[{KANT_DISSERTATION}]]"))
        self.vault.note(KANT_DISSERTATION, field=["[[Logic]]"], year=1894, orig_year=1770)
        self.vault.note(KANT_CRITIQUE, field=["[[Logic]]"], year=1998, orig_year=1781)
        self.vault.place(KANT_CRITIQUE)
        self.assertEqual([f"- [[{KANT_DISSERTATION}]]", f"- [[{KANT_CRITIQUE}]]"], self.listed())

    def test_a_work_without_a_corpus_file_is_ordered_by_its_filename_year(self) -> None:
        self.vault.bibliography("Logic", works_section(f"- [[{ARISTOTLE}]]", f"- [[{HOULGATE}]]"))
        self.vault.note(HEGEL, field=["[[Logic]]"])
        self.vault.place(HEGEL)
        self.assertEqual([f"- [[{HEGEL}]]", f"- [[{ARISTOTLE}]]", f"- [[{HOULGATE}]]"], self.listed())

    def test_works_of_one_year_sort_by_basename(self) -> None:
        self.vault.bibliography("Logic", works_section(f"- [[{HEGEL}]]"))
        self.vault.note("Adorno - 1969 - Negative Dialectics", field=["[[Logic]]"], year=1969)
        self.vault.place("Adorno - 1969 - Negative Dialectics")
        self.assertEqual(["- [[Adorno - 1969 - Negative Dialectics]]", f"- [[{HEGEL}]]"], self.listed())


class TestPlacementAmongGroups(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.note(HOULGATE, field=["[[Logic]]"], source_role="secondary", year=2006)
        self.vault.note(BACON, field=["[[Logic]]"], year=1620)

    def body(self) -> str:
        return self.vault.body_of("Logic")

    def test_a_new_work_lands_in_an_unsorted_group_at_the_end(self) -> None:
        self.vault.bibliography("Logic", GROUPED % (HOULGATE, BACON))
        self.vault.note(HEGEL, field=["[[Logic]]"], year=1969)
        self.vault.place(HEGEL)
        self.assertTrue(self.body().rstrip().endswith(f"### Unsorted\n\n- [[{HEGEL}]]"))

    def test_a_second_new_work_joins_the_unsorted_group_in_order(self) -> None:
        self.vault.bibliography("Logic", GROUPED % (HOULGATE, BACON) + f"\n### Unsorted\n\n- [[{HEGEL}]]\n")
        self.vault.note(ARISTOTLE, field=["[[Logic]]"], year=1984, orig_year=-350)
        self.vault.place(ARISTOTLE)
        self.assertIn(f"### Unsorted\n\n- [[{ARISTOTLE}]]\n- [[{HEGEL}]]", self.body())

    def listed_in_group(self, group: str) -> str:
        bibliography = self.vault.named("Logic")
        section = bibliographies.Section("Secondary literature")
        work_list = bibliographies.WorkList(section, bibliography.body, WorkOrder(bibliographies.Corpus()))
        return work_list.with_listing(HEGEL, f"- [[{HEGEL}]] — a gloss.", group)

    def test_a_listing_for_a_named_group_lands_in_that_group(self) -> None:
        self.vault.bibliography("Logic", GROUPED % (HOULGATE, BACON))
        self.vault.note(HEGEL, field=["[[Logic]]"], year=1969)
        self.assertIn(f"- [[{HEGEL}]] — a gloss.", self.listed_in_group("Openings").split("### Openings")[1])

    def test_a_new_named_group_sits_before_the_unsorted_group(self) -> None:
        self.vault.bibliography("Logic", GROUPED % (HOULGATE, BACON) + f"\n### Unsorted\n\n- [[{ARISTOTLE}]]\n")
        self.vault.note(HEGEL, field=["[[Logic]]"], year=1969)
        content = self.listed_in_group("Responses")
        self.assertLess(content.index("### Responses"), content.index("### Unsorted"))

    def test_a_new_named_group_keeps_the_blank_line_before_the_next_section(self) -> None:
        self.vault.bibliography("Logic", f"## Secondary literature\n\n- [[{HOULGATE}]]\n\n## Primary works\n\n- [[{BACON}]]\n")
        self.vault.note(HEGEL, field=["[[Logic]]"], year=1969)
        self.assertTrue(self.listed_in_group("Responses").endswith(f"- [[{HEGEL}]] — a gloss.\n\n"))

    def test_a_named_group_on_an_empty_list_replaces_the_empty_marker(self) -> None:
        self.vault.bibliography("Logic", works_section("*(none)*"))
        self.vault.note(HEGEL, field=["[[Logic]]"], year=1969)
        self.assertEqual(f"\n### Responses\n\n- [[{HEGEL}]] — a gloss.\n", self.listed_in_group("Responses"))

    def test_the_groups_and_their_annotations_are_untouched(self) -> None:
        self.vault.bibliography("Logic", GROUPED % (HOULGATE, BACON))
        self.vault.note(HEGEL, field=["[[Logic]]"], year=1969)
        self.vault.place(HEGEL)
        self.assertIn(GROUPED % (HOULGATE, BACON), self.body())

    def test_a_prose_line_with_a_wikilink_is_no_listing(self) -> None:
        self.vault.bibliography("Logic", GROUPED % (HOULGATE, BACON))
        self.assertEqual([HOULGATE, BACON], self.listed_basenames())

    def test_a_group_heading_with_a_wikilink_is_no_listing(self) -> None:
        self.vault.bibliography("Logic", f"## Secondary literature\n\n### Readers of [[Kant]]\n\n- [[{HOULGATE}]]\n")
        self.assertEqual([HOULGATE], self.listed_basenames())

    def test_an_annotated_group_passes_the_listing_check(self) -> None:
        self.vault.bibliography("Logic", GROUPED % (HOULGATE, BACON))
        self.vault.bibliography("Kant")
        self.assertNotIn("Listings", self.vault.report().as_dict()["blocking"])

    def listed_basenames(self) -> list[str]:
        lines = bibliographies.Section(SECONDARY_WORKS_HEADING).lines_in(self.body())
        return bibliographies.WorkList.listed_basenames(lines)
