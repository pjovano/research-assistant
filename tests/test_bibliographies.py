from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import bibliographies
import vault
from _bibliography_fixtures import (
    SECONDARY_WORKS_HEADING,
    PRIMARY_WORKS_HEADING,
    EMPTY_SECTION_MARKER,
    HEGEL,
    TemporaryVault,
    works_section,
)

AUTHORS_FOLDER = bibliographies.AUTHORS_FOLDER


class TestTheMapsABibliographyLists(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def test_the_listed_maps_are_the_bibliographies_beneath_it(self) -> None:
        self.vault.parent_of("German Idealism", "Hegel", "Kant")
        self.assertEqual(["Hegel", "Kant"], self.vault.named("German Idealism").children)

    def test_a_bibliography_listing_no_map_has_none_beneath_it(self) -> None:
        self.vault.bibliography("German Idealism")
        self.assertEqual([], self.vault.named("German Idealism").children)

    def test_a_work_listing_is_not_read_as_a_map(self) -> None:
        self.vault.bibliography("German Idealism", works_section(f"- [[{HEGEL}]]"))
        self.assertEqual([], self.vault.named("German Idealism").children)


class TestBibliographyTreeAncestors(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def test_the_chain_of_listings_is_followed_to_the_root(self) -> None:
        self.vault.parent_of("Philosophy", "German Idealism")
        self.vault.parent_of("German Idealism", "Hegel")
        self.vault.bibliography("Hegel")
        self.assertEqual(["German Idealism", "Philosophy"],
                         self.vault.tree().ancestors_of("Hegel"))

    def test_a_bibliography_no_map_lists_has_no_ancestors(self) -> None:
        self.vault.bibliography("Philosophy")
        self.assertEqual([], self.vault.tree().ancestors_of("Philosophy"))

    def test_a_cycle_of_listings_is_walked_once_and_stops(self) -> None:
        self.vault.parent_of("Hegel", "German Idealism")
        self.vault.parent_of("German Idealism", "Hegel")
        self.assertEqual(["German Idealism", "Hegel"],
                         sorted(self.vault.tree().ancestors_of("Hegel")))


class TestTheGraphChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def test_a_listed_map_that_is_no_bibliography_blocks(self) -> None:
        self.vault.parent_of("German Idealism", "Ghost")
        self.assertFalse(self.vault.report().is_clean)
        self.assertIn("which is not a bibliography", self.vault.printed_report())

    def test_two_bibliographies_listing_one_map_are_clean(self) -> None:
        self.vault.parent_of("German Idealism", "Hegel")
        self.vault.parent_of("Analytic Philosophy", "Hegel")
        self.vault.bibliography("Hegel")
        self.assertTrue(self.vault.report().is_clean)

    def test_a_cycle_blocks(self) -> None:
        self.vault.parent_of("Hegel", "German Idealism")
        self.vault.parent_of("German Idealism", "Hegel")
        self.assertFalse(self.vault.report().is_clean)
        self.assertIn("sits beneath itself", self.vault.printed_report())

    def test_a_plain_tree_is_clean(self) -> None:
        self.vault.parent_of("German Idealism", "Hegel")
        self.vault.bibliography("Hegel")
        self.assertTrue(self.vault.report().is_clean)


class TestBibliographiesInSubfolders(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def test_a_bibliography_in_a_subfolder_is_found_by_its_name(self) -> None:
        self.vault.bibliography_in(AUTHORS_FOLDER, "Hegel", author="Hegel")
        self.assertEqual("Hegel", self.vault.named("Hegel").name)

    def test_a_work_is_listed_in_the_subfolder_the_bibliography_sits_in(self) -> None:
        self.vault.bibliography_in(AUTHORS_FOLDER, "Hegel", author="Hegel")
        self.vault.note(HEGEL, field=["[[Hegel]]"], author=["Hegel"])
        self.vault.place(HEGEL)
        listed = bibliographies.Section(PRIMARY_WORKS_HEADING).lines_in(
            self.vault.body_in(AUTHORS_FOLDER, "Hegel"))
        self.assertEqual([f"- [[{HEGEL}]]"], listed)

    def test_a_subfolder_never_enters_the_wikilink(self) -> None:
        self.vault.bibliography_in(AUTHORS_FOLDER, "Hegel", author="Hegel")
        self.vault.note(HEGEL, field=[f"[[{AUTHORS_FOLDER}/Hegel]]"], author=["Hegel"])
        with self.assertRaises(bibliographies.BibliographyNotFound):
            self.vault.plan_for(HEGEL)

    def test_a_conflict_copy_in_a_subfolder_blocks(self) -> None:
        self.vault.bibliography_in(AUTHORS_FOLDER, "Hegel", author="Hegel")
        self.vault.bibliography_in(AUTHORS_FOLDER, "Hegel 2", author="Hegel")
        self.assertFalse(self.vault.report().is_clean)

    def test_a_note_of_the_reading_lists_folder_is_no_bibliography(self) -> None:
        self.vault.bibliography_in(AUTHORS_FOLDER, "Hegel", author="Hegel")
        self.vault.bibliography_in(vault.READING_LISTS_FOLDER, "Hegel - Reading list")
        self.assertEqual(["Hegel.md"], [path.name for path in vault.list_bibliographies()])

    def test_a_numbered_copy_in_the_reading_lists_folder_blocks_nothing(self) -> None:
        self.vault.bibliography_in(vault.READING_LISTS_FOLDER, "Hegel - Reading list")
        self.vault.bibliography_in(vault.READING_LISTS_FOLDER, "Hegel - Reading list 2")
        self.assertEqual([], vault.bibliography_conflict_copies())

    def test_one_name_in_two_folders_blocks(self) -> None:
        self.vault.bibliography_in(AUTHORS_FOLDER, "Hegel", author="Hegel")
        self.vault.bibliography_in("topics", "Hegel")
        printed = self.vault.printed_report()
        self.assertIn("2 bibliographies carry this name", printed)
        self.assertFalse(self.vault.report().is_clean)

    def test_an_author_bibliography_outside_the_authors_folder_is_advisory(self) -> None:
        self.vault.bibliography("Hegel", author="Hegel")
        printed = self.vault.printed_report()
        self.assertIn(f"an author bibliography outside {AUTHORS_FOLDER}/", printed)
        self.assertTrue(self.vault.report().is_clean)

    def test_an_author_bibliography_in_the_authors_folder_is_not_reported(self) -> None:
        self.vault.bibliography_in(AUTHORS_FOLDER, "Hegel", author="Hegel")
        self.assertNotIn("outside", self.vault.printed_report())

    def test_a_topic_bibliography_outside_the_authors_folder_is_not_reported(self) -> None:
        self.vault.bibliography("Hegel")
        self.assertNotIn("outside", self.vault.printed_report())


class TestCorpusLookup(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def test_a_basename_with_no_note_is_unresolved(self) -> None:
        with self.assertRaises(bibliographies.NoteNotFound):
            bibliographies.Corpus().note(HEGEL)

    def test_a_written_note_is_found_by_its_basename(self) -> None:
        self.vault.note(HEGEL, source_role="primary")
        self.assertEqual(HEGEL, bibliographies.Corpus().note(HEGEL).basename)


class TestSectionLines(unittest.TestCase):
    def test_the_empty_section_marker_is_not_a_work(self) -> None:
        body = works_section(EMPTY_SECTION_MARKER)
        self.assertEqual([], bibliographies.Section(SECONDARY_WORKS_HEADING).lines_in(body))

    def test_an_absent_section_has_no_lines(self) -> None:
        self.assertEqual([], bibliographies.Section(SECONDARY_WORKS_HEADING).lines_in("## Scope\n\nProse.\n"))


if __name__ == "__main__":
    unittest.main()
