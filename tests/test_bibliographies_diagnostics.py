from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import bibliographies
from _bibliography_fixtures import (
    PRIMARY_WORKS_HEADING,
    SECONDARY_WORKS_HEADING,
    HEGEL,
    HOULGATE,
    PIPPIN_TALK,
    TemporaryVault,
    works_section,
)


class TestConflictCopies(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.note(HEGEL, source_type="historical", source_role="primary")

    def test_a_numbered_sibling_of_a_note_is_not_a_note(self) -> None:
        self.vault.raw_note(f"{HEGEL} 2", "---\ntitle: copy\n---\n")
        self.assertEqual({HEGEL}, bibliographies.Corpus().basenames())

    def test_a_numbered_stem_without_an_original_is_a_note(self) -> None:
        self.vault.note("Russell - 1910 - Principia Mathematica Volume 2", source_role="primary")
        self.assertIn("Russell - 1910 - Principia Mathematica Volume 2", bibliographies.Corpus().basenames())

    def test_a_conflict_copy_blocks_check(self) -> None:
        self.vault.raw_note(f"{HEGEL} 2", "---\ntitle: copy\n---\n")
        self.assertFalse(self.vault.report().is_clean)

    def test_a_conflict_copy_is_named_in_the_report(self) -> None:
        self.vault.raw_note(f"{HEGEL} 2", "---\ntitle: copy\n---\n")
        self.assertIn("sync conflict copy", self.vault.printed_report())

    def test_a_conflicted_copy_of_a_bibliography_blocks_check(self) -> None:
        self.vault.bibliography("Logic")
        self.vault.raw_bibliography("Logic (conflicted copy 2026-09-03)", "---\n---\n")
        self.assertFalse(self.vault.report().is_clean)


class TestListingChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def test_a_listing_the_note_does_not_name_blocks(self) -> None:
        self.vault.note(HOULGATE, field=["[[Being]]"], source_role="secondary")
        self.vault.bibliography("Being")
        self.vault.bibliography("Logic", works_section(f"- [[{HOULGATE}]]"))
        self.assertFalse(self.vault.report().is_clean)

    def test_a_listing_the_note_does_not_name_is_named_in_the_report(self) -> None:
        self.vault.note(HOULGATE, field=["[[Being]]"], source_role="secondary")
        self.vault.bibliography("Being")
        self.vault.bibliography("Logic", works_section(f"- [[{HOULGATE}]]"))
        self.assertIn("whose corpus file's field: does not name it", self.vault.printed_report())

    def test_a_work_in_both_sections_of_an_author_bibliography_blocks(self) -> None:
        self.vault.note(HEGEL, field=["[[Hegel]]"], source_role="primary")
        body = f"## {PRIMARY_WORKS_HEADING}\n\n- [[{HEGEL}]]\n\n## {SECONDARY_WORKS_HEADING}\n\n- [[{HEGEL}]]\n"
        self.vault.bibliography("Hegel", body, author="Hegel")
        self.assertIn("under both", self.vault.printed_report())

    def test_a_backed_listing_is_clean(self) -> None:
        self.vault.note(HOULGATE, field=["[[Logic]]"], source_type="monograph", source_role="secondary")
        self.vault.bibliography("Logic", works_section(f"- [[{HOULGATE}]]"))
        self.assertTrue(self.vault.report().is_clean)


class TestAuthorsToPropose(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def works_by(self, author: str, count: int) -> None:
        for number in range(count):
            self.vault.note(f"{author} - 19{70 + number} - Work {number}", author=[author])

    def test_an_author_at_the_threshold_is_proposed(self) -> None:
        self.works_by("Hegel", bibliographies.WORKS_FOR_AN_AUTHOR_BIBLIOGRAPHY)
        self.assertIn("Hegel: 5 works in the library; propose an author bibliography",
                      self.vault.printed_report())

    def test_an_author_below_the_threshold_is_not_proposed(self) -> None:
        self.works_by("Hegel", bibliographies.WORKS_FOR_AN_AUTHOR_BIBLIOGRAPHY - 1)
        self.assertNotIn("propose an author bibliography", self.vault.printed_report())

    def test_an_author_with_a_bibliography_is_not_proposed(self) -> None:
        self.vault.bibliography("Hegel", author="Hegel")
        self.works_by("Hegel", bibliographies.WORKS_FOR_AN_AUTHOR_BIBLIOGRAPHY)
        self.assertNotIn("propose an author bibliography", self.vault.printed_report())

    def test_a_topic_bibliography_named_for_the_author_does_not_cover_them(self) -> None:
        self.vault.bibliography("Hegel")
        self.works_by("Hegel", bibliographies.WORKS_FOR_AN_AUTHOR_BIBLIOGRAPHY)
        self.assertIn("propose an author bibliography", self.vault.printed_report())

    def test_each_creator_of_a_work_is_counted(self) -> None:
        for number in range(bibliographies.WORKS_FOR_AN_AUTHOR_BIBLIOGRAPHY):
            self.vault.note(f"Kaufmann and Yeomans - 200{number} - Work {number}",
                            author=["Kaufmann", "Yeomans"])
        printed = self.vault.printed_report()
        self.assertIn("Kaufmann: 5 works", printed)
        self.assertIn("Yeomans: 5 works", printed)

    def test_a_presenter_of_a_transcript_is_not_counted(self) -> None:
        self.works_by("Pippin", bibliographies.WORKS_FOR_AN_AUTHOR_BIBLIOGRAPHY - 1)
        self.vault.transcript(PIPPIN_TALK, author=["Pippin"])
        self.assertNotIn("propose an author bibliography", self.vault.printed_report())

    def test_an_author_to_propose_does_not_block(self) -> None:
        self.works_by("Hegel", bibliographies.WORKS_FOR_AN_AUTHOR_BIBLIOGRAPHY)
        self.assertTrue(self.vault.report().is_clean)


class TestReportBuilder(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def test_a_listed_map_that_is_no_bibliography_blocks(self) -> None:
        self.vault.parent_of("German Idealism", "Ghost")
        self.assertFalse(self.vault.report().is_clean)

    def test_a_listed_map_that_is_no_bibliography_is_named_in_the_report(self) -> None:
        self.vault.parent_of("German Idealism", "Ghost")
        self.assertIn("lists [[Ghost]] as a map beneath it", self.vault.printed_report())

    def test_an_unplaced_note_does_not_block(self) -> None:
        self.vault.note(HEGEL, source_type="historical", source_role="primary")
        self.assertTrue(self.vault.report().is_clean)

    def test_an_unplaced_note_is_reported_as_advisory(self) -> None:
        self.vault.note(HEGEL, source_type="historical", source_role="primary")
        printed = self.vault.printed_report()
        self.assertIn("(advisory)", printed)
        self.assertIn(f"{HEGEL}: sits on no bibliography yet", printed)


if __name__ == "__main__":
    unittest.main()


class TestReissuesWithoutAnOriginalYear(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def advisory(self) -> list[str]:
        return self.vault.report().as_dict()["advisory"].get(bibliographies.REISSUES_HEADING, [])

    def test_a_primary_work_with_no_orig_year_is_reported(self) -> None:
        self.vault.note(HEGEL, source_type="historical", source_role="primary", year=1969)
        self.assertEqual([f"{HEGEL}: a primary historical with no orig_year; set it if the held edition is not the "
                          "first"], self.advisory())

    def test_a_primary_work_with_an_orig_year_is_not_reported(self) -> None:
        self.vault.note(HEGEL, source_type="historical", source_role="primary", year=1969, orig_year=1812)
        self.assertEqual([], self.advisory())

    def test_a_secondary_work_is_not_reported(self) -> None:
        self.vault.note(HOULGATE, source_type="monograph", source_role="secondary", year=2006)
        self.assertEqual([], self.advisory())

    def test_the_advisory_does_not_block(self) -> None:
        self.vault.note(HEGEL, source_type="historical", source_role="primary", year=1969)
        self.assertTrue(self.vault.report().is_clean)
