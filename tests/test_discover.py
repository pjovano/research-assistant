from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest import mock

import pymupdf

from _support import LiveTree

LiveTree.activate()

from references import HeldWorks, ParsedReference
from _discover.cited import ANY_CITING_WORK, SOURCE_CORPUS, SOURCE_PDF, UnheldWorks
from _discover.cli import CommandLine
from _discover.matching import CitationMatch, Record, RecordMatch
from _discover.merging import (
    CandidateMerge, CandidateParser, HeldMarking, LocalCitations, Ordering, UnseenKnownItems,
)
from _discover_fixtures import CitedWork, Sighting, candidate, report
from _references_fixtures import LINK_LINE, VaultTestCase

HOULGATE = "Houlgate - 2006 - The Opening of Hegel's Logic"
STERN = "Stern - 2023 - Understanding Hegel's Logic"
BURBIDGE = "Burbidge - 1981 - On Hegel's Logic"
PDF_ONLY = "Tabak - 2017 - The Doctrine of Being"
BURBIDGE_ENTRY = ("Burbidge, John. On Hegel's Logic: Fragments of a Commentary. "
                  "Atlantic Highlands: Humanities Press, 1981.")
DUNPHY_ENTRY = ("Dunphy, Robb. Hegel and the Problem of Beginning: Scepticism and Presuppositionlessness. "
                "Lanham: Rowman, 2023.")
TABAK_ENTRY = "Tabak, Mehmet. The Doctrine of Being in Hegel's Science of Logic. London: Palgrave, 2017."
HOULGATE_BODY = (f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n%% p. 443 (file p. 464) %%\n\n"
                 f"{BURBIDGE_ENTRY}\n\n"
                 f"{DUNPHY_ENTRY}\n\n%% p. 444 (file p. 465) %%\n\n{TABAK_ENTRY}\n")
STERN_BODY = (f"{LINK_LINE}\n\n# One\n\nProse.[^1]\n\n%% p. 12 (file p. 3) %%\n\n"
              "[^1]: Dunphy, Robb, Hegel and the Problem of Beginning (Lanham: Rowman, 2023), p. 4.\n")
COLLECTED = "Moyar - 2017 - The Oxford Handbook of Hegel"
PIPPIN_FOOTNOTE = "Pippin, Robert, Hegel's Realm of Shadows (Chicago: University of Chicago Press, 2019), p. 3."
PINKARD_ENTRY = "Pinkard, Terry. Hegel's Naturalism. Oxford: Oxford University Press, 2012."
SUTHER_NOTE = "1. Suther, Jensen. Hegel's Metaphysics of Rational Life. Hegel Bulletin 44 (2023)."
COLLECTED_BODY = (f"{LINK_LINE}\n\n# One\n\nProse.[^1]\n\n%% p. 5 (file p. 6) %%\n\n[^1]: {PIPPIN_FOOTNOTE}\n\n"
                  f"## References\n\n%% p. 20 (file p. 21) %%\n\n{DUNPHY_ENTRY}\n\n"
                  f"# Two\n\nProse.\n\n## References\n\n%% p. 40 (file p. 41) %%\n\n{PINKARD_ENTRY}\n\n"
                  f"# Notes\n\n%% p. 60 (file p. 61) %%\n\n{SUTHER_NOTE}\n")
PDF_PAGES = ["Chapter One\n\nBody text about being and nothing.",
             "References\n\nSuther, J. (2023). Hegel's Metaphysics of Rational Life. Hegel Bulletin 44.\n"
             "Dunphy, R. (2023). Hegel and the Problem of Beginning. Lanham: Rowman."]
PDF_TEXT_ORIGIN = (72, 72)
PDF_TEXT_SIZE = 11
NOTHING_PARSED = ParsedReference((), None, None, None, None, None)
SHABEL = "Shabel - 2003 - Mathematics in Kant's Critical Philosophy"
SUTHERLAND = "Sutherland - 2022 - Kant's Mathematical World"
KANT_GUYER_ENTRY = ("Kant, Immanuel. Critique of Pure Reason. Trans. Paul Guyer and Allen Wood. "
                    "Cambridge: Cambridge University Press, 1998.")
KANT_KEMP_SMITH_ENTRY = "Kant, Immanuel. Critique of Pure Reason. Trans. Norman Kemp Smith. London: Macmillan, 1929."
KANT_PRACTICAL_ENTRY = ("Kant, Immanuel. Critique of Practical Reason. Trans. Mary Gregor. "
                        "Cambridge: Cambridge University Press, 1997.")
MOREAU_ENTRY = "Moreau, Lucien. Hegel. Paris: Presses Universitaires, 1975."
MOREAU_LATER_ENTRY = "Moreau, Lucien. Hegel: A Reading. Paris: Presses Universitaires, 1999."
HYPHENATED = "Merleau-Ponty - 1945 - Phenomenology of Perception"
HYPHENATED_FRONTMATTER = "title: Phenomenology of Perception\nauthor:\n- Merleau-Ponty\nyear: 1945\n"
PARSED = {
    BURBIDGE_ENTRY: ParsedReference(("Burbidge, John",), "On Hegel's Logic: Fragments of a Commentary", None, "1981",
                                    "Humanities Press", None),
    KANT_GUYER_ENTRY: ParsedReference(("Kant, Immanuel",), "Critique of Pure Reason", None, "1998",
                                      "Cambridge University Press", None),
    KANT_KEMP_SMITH_ENTRY: ParsedReference(("Kant, Immanuel",), "Critique of Pure Reason", None, "1929",
                                           "Macmillan", None),
    KANT_PRACTICAL_ENTRY: ParsedReference(("Kant, Immanuel",), "Critique of Practical Reason", None, "1997",
                                          "Cambridge University Press", None),
    MOREAU_ENTRY: ParsedReference(("Moreau, Lucien",), "Hegel", None, "1975", "Presses Universitaires", None),
    MOREAU_LATER_ENTRY: ParsedReference(("Moreau, Lucien",), "Hegel: A Reading", None, "1999",
                                        "Presses Universitaires", None),
}


class FakeParser:
    def parse(self, entry_text: str) -> ParsedReference:
        return PARSED.get(entry_text, NOTHING_PARSED)


class LibraryTestCase(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        for basename in (HOULGATE, STERN, BURBIDGE):
            self.write_pdf(basename)
        self.write_note(HOULGATE, "title: The Opening of Hegel's Logic\nauthor:\n- Houlgate\nyear: 2006\n",
                        HOULGATE_BODY)
        self.write_note(STERN, "title: Understanding Hegel's Logic\nauthor:\n- Stern\nyear: 2023\n", STERN_BODY)
        self.write_note(BURBIDGE, "title: On Hegel's Logic\nauthor:\n- Burbidge\nyear: 1981\n")
        self.write_text_pdf(PDF_ONLY, PDF_PAGES)

    def write_text_pdf(self, basename: str, pages: list[str]) -> Path:
        path = self.vault.library / f"{basename}.pdf"
        document = pymupdf.open()
        for text in pages:
            document.new_page().insert_text(PDF_TEXT_ORIGIN, text, fontsize=PDF_TEXT_SIZE)
        document.save(path)
        document.close()
        return path

    def unheld(self, *basenames: str, min_citing: int = ANY_CITING_WORK) -> dict:
        return UnheldWorks(HeldWorks.from_library(), FakeParser()).over(list(basenames), min_citing)

    def entry_texts(self, result: dict) -> list[str]:
        return [entry["text"] for entry in result["entries"]]


class TestEveryEntryListOfACollectedVolumeIsRead(LibraryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_pdf(COLLECTED)
        self.write_note(COLLECTED, "title: The Oxford Handbook of Hegel\nauthor:\n- Moyar\nyear: 2017\n",
                        COLLECTED_BODY)

    def test_a_footnote_beside_a_reference_list_is_read(self) -> None:
        self.assertIn(PIPPIN_FOOTNOTE, self.entry_texts(self.unheld(COLLECTED)))

    def test_a_second_reference_list_is_read(self) -> None:
        self.assertIn(PINKARD_ENTRY, self.entry_texts(self.unheld(COLLECTED)))

    def test_an_endnotes_list_beside_the_reference_lists_is_read(self) -> None:
        self.assertIn(SUTHER_NOTE, self.entry_texts(self.unheld(COLLECTED)))

    def test_an_entry_of_the_second_reference_list_carries_that_lists_folio(self) -> None:
        pinkard = next(entry for entry in self.unheld(COLLECTED)["entries"] if entry["text"] == PINKARD_ENTRY)
        self.assertEqual("40", pinkard["cited_by"][0]["folio"])


class TestUnheld(LibraryTestCase):
    def test_the_corpus_file_is_the_source_when_it_has_a_bibliography_section(self) -> None:
        self.assertEqual(SOURCE_CORPUS, self.unheld(HOULGATE)["works"][0]["source"])

    def test_an_entry_naming_a_held_work_is_not_listed(self) -> None:
        self.assertNotIn(BURBIDGE_ENTRY, self.entry_texts(self.unheld(HOULGATE)))

    def test_an_entry_naming_no_held_work_is_listed(self) -> None:
        self.assertIn(DUNPHY_ENTRY, self.entry_texts(self.unheld(HOULGATE)))

    def test_the_locator_carries_the_folio_of_the_page_marker_before_the_entry(self) -> None:
        tabak = next(entry for entry in self.unheld(HOULGATE)["entries"] if entry["text"] == TABAK_ENTRY)
        self.assertEqual({"basename": HOULGATE, "folio": "444", "file_page": 465, "text": TABAK_ENTRY},
                         tabak["cited_by"][0])

    def test_a_footnote_definition_is_an_entry_when_the_work_has_no_bibliography_section(self) -> None:
        self.assertEqual("12", self.unheld(STERN)["entries"][0]["cited_by"][0]["folio"])

    def test_the_same_work_cited_by_two_held_works_is_one_entry_with_two_citing_works(self) -> None:
        dunphy = next(entry for entry in self.unheld(HOULGATE, STERN)["entries"] if "Dunphy" in entry["text"])
        self.assertEqual([HOULGATE, STERN], [locator["basename"] for locator in dunphy["cited_by"]])

    def test_the_entries_are_ordered_by_the_count_of_citing_works(self) -> None:
        self.assertIn("Dunphy", self.unheld(HOULGATE, STERN)["entries"][0]["text"])

    def test_a_minimum_of_citing_works_keeps_only_the_entries_cited_that_often(self) -> None:
        self.assertEqual([DUNPHY_ENTRY], self.entry_texts(self.unheld(HOULGATE, STERN, min_citing=2)))

    def test_a_minimum_of_citing_works_still_reports_every_work_read(self) -> None:
        self.assertEqual([HOULGATE, STERN],
                         [work["basename"] for work in self.unheld(HOULGATE, STERN, min_citing=2)["works"]])

    def test_a_work_without_a_corpus_file_falls_back_to_its_pdf_reference_zone(self) -> None:
        self.assertEqual(SOURCE_PDF, self.unheld(PDF_ONLY)["works"][0]["source"])

    def test_the_pdf_reference_zone_yields_every_entry_it_lists(self) -> None:
        self.assertEqual(2, len(self.unheld(PDF_ONLY)["entries"]))

    def test_a_pdf_locator_carries_the_zone_file_page_and_no_folio(self) -> None:
        locator = self.unheld(PDF_ONLY)["entries"][0]["cited_by"][0]
        self.assertEqual((None, 2), (locator["folio"], locator["file_page"]))

    def test_the_unheld_report_of_a_work_is_pinned_whole(self) -> None:
        expected = {
            "works": [{"basename": HOULGATE, "source": SOURCE_CORPUS, "unheld_entries": 2}],
            "entries": [
                {"text": DUNPHY_ENTRY, "surnames": ["dunphy", "rowman"], "years": ["2023"],
                 "cited_by": [{"basename": HOULGATE, "folio": "443", "file_page": 464, "text": DUNPHY_ENTRY}],
                 "cited_by_count": 1},
                {"text": TABAK_ENTRY, "surnames": ["tabak", "palgrave"], "years": ["2017"],
                 "cited_by": [{"basename": HOULGATE, "folio": "444", "file_page": 465, "text": TABAK_ENTRY}],
                 "cited_by_count": 1},
            ],
        }
        self.assertEqual(expected, self.unheld(HOULGATE))

    def test_a_basename_that_is_not_held_is_refused(self) -> None:
        with self.assertRaises(LookupError):
            self.unheld("Nobody - 1999 - Nothing")


class TestUnheldEditions(LibraryTestCase):
    def cite(self, shabel_entry: str, sutherland_entry: str) -> dict:
        self.hold(SHABEL, shabel_entry)
        self.hold(SUTHERLAND, sutherland_entry)
        return self.unheld(SHABEL, SUTHERLAND)

    def hold(self, basename: str, entry: str) -> None:
        surname, year, title = basename.split(" - ")
        self.write_pdf(basename)
        body = f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n%% p. 301 (file p. 310) %%\n\n{entry}\n"
        self.write_note(basename, f"title: {title}\nauthor:\n- {surname}\nyear: {year}\n", body)

    def test_two_editions_of_one_work_are_one_entry_cited_by_both_works(self) -> None:
        entries = self.cite(KANT_GUYER_ENTRY, KANT_KEMP_SMITH_ENTRY)["entries"]
        self.assertEqual([2], [entry["cited_by_count"] for entry in entries])

    def test_the_merged_entry_carries_the_year_of_every_edition(self) -> None:
        self.assertEqual(["1998", "1929"], self.cite(KANT_GUYER_ENTRY, KANT_KEMP_SMITH_ENTRY)["entries"][0]["years"])

    def test_two_works_of_one_author_under_different_titles_stay_two_entries(self) -> None:
        self.assertEqual(2, len(self.cite(KANT_GUYER_ENTRY, KANT_PRACTICAL_ENTRY)["entries"]))

    def test_editions_whose_main_title_is_too_short_to_identify_the_work_stay_apart(self) -> None:
        self.assertEqual(2, len(self.cite(MOREAU_ENTRY, MOREAU_LATER_ENTRY)["entries"]))

    def test_a_candidate_of_either_edition_is_cited_by_the_works_citing_both(self) -> None:
        unheld = self.cite(KANT_GUYER_ENTRY, KANT_KEMP_SMITH_ENTRY)
        found = candidate(CitedWork("Critique of Pure Reason", ["Immanuel Kant"], 1929),
                          Sighting("Google Scholar", "https://scholar.google.com/kant"))
        candidates = CandidateParser().parse([report("Google Scholar", [found])])
        LocalCitations(unheld).attach(candidates)
        self.assertEqual([SHABEL, SUTHERLAND], [locator["basename"] for locator in candidates[0].cited_by])


class TestRecordMatch(unittest.TestCase):
    def match(self, left: Record, right: Record) -> bool:
        return RecordMatch(left, right).holds()

    def test_the_same_title_author_and_year_match(self) -> None:
        self.assertTrue(self.match(Record.of("Hegel's Logic as Presuppositionless Science", ["Miles Hentrup"], 2019),
                                   Record.of("Hegel’s logic as presuppositionless science", ["Hentrup, M."], 2019)))

    def test_a_subtitle_does_not_break_the_match(self) -> None:
        self.assertTrue(self.match(Record.of("Hegel and the Problem of Beginning", ["Robb Dunphy"], 2023),
                                   Record.of("Hegel and the Problem of Beginning: "
                                             "Scepticism and Presuppositionlessness",
                                             ["R Dunphy"], 2023)))

    def test_a_candidate_without_authors_matches_on_title_and_year(self) -> None:
        self.assertTrue(self.match(Record.of("The Opening of Hegel's Logic", [], 2006),
                                   Record.of("The Opening of Hegel's Logic", ["Stephen Houlgate"], 2006)))

    def test_a_candidate_without_a_year_matches_on_title_and_author(self) -> None:
        self.assertTrue(self.match(Record.of("The Opening of Hegel's Logic", ["Houlgate"], None),
                                   Record.of("The Opening of Hegel's Logic", ["Stephen Houlgate"], 2006)))

    def test_years_three_apart_do_not_match(self) -> None:
        self.assertFalse(self.match(Record.of("The Opening of Hegel's Logic", ["Houlgate"], 2003),
                                    Record.of("The Opening of Hegel's Logic", ["Houlgate"], 2006)))

    def test_adjacent_years_match(self) -> None:
        self.assertTrue(self.match(Record.of("The Opening of Hegel's Logic", ["Houlgate"], 2005),
                                   Record.of("The Opening of Hegel's Logic", ["Houlgate"], 2006)))

    def test_a_different_author_on_the_same_title_and_year_does_not_match(self) -> None:
        self.assertFalse(self.match(Record.of("Hegel's Logic", ["Burbidge"], 2006),
                                    Record.of("Hegel's Logic", ["Houlgate"], 2006)))

    def test_a_shared_doi_matches_whatever_the_titles(self) -> None:
        self.assertTrue(self.match(Record.of("Presuppositionless Science", [], None).identified_by(
                                       ("https://doi.org/10.5840/idstudies2019115107",)),
                                   Record.of("Hegel's Logic as Presuppositionless Science", ["Hentrup"], 2019)
                                   .identified_by(("https://www.pdcnet.org/x?doi=10.5840/idstudies2019115107",))))

    def test_two_works_read_off_the_same_results_page_do_not_merge(self) -> None:
        listing = "https://scholar.google.com/scholar?q=hegel+beginning"
        self.assertFalse(self.match(Record.of("Reason and Justice", ["Winfield"], 1988).identified_by((listing,)),
                                    Record.of("Hegel: A Non-Metaphysical View", ["Hartmann"], 1972)
                                    .identified_by((listing,))))

    def test_a_listing_that_truncates_the_title_matches_the_full_title(self) -> None:
        self.assertTrue(self.match(Record.of("Hegel and Wittgenstein on Difficulties of Beginning at the ...",
                                             [], None),
                                   Record.of("Hegel and Wittgenstein on Difficulties of Beginning at the Beginning",
                                             ["Mácha, J."], 2022)))

    def test_a_title_that_extends_another_without_a_truncation_mark_does_not_match(self) -> None:
        self.assertFalse(self.match(Record.of("Hegel's Logic and Metaphysics", ["McNulty"], 2023),
                                    Record.of("Hegel's Logic and Metaphysics, by Jacob McNulty (review)",
                                              ["Houlgate"], 2025)))

    def test_a_short_main_title_is_compared_with_its_subtitle(self) -> None:
        self.assertFalse(self.match(Record.of("Hegel: Three Studies", [], 1994),
                                    Record.of("Hegel: A Collection of Critical Essays", [], 1972)))


class TestCitationMatch(unittest.TestCase):
    def test_the_title_and_a_surname_in_the_entry_text_with_the_year_hold(self) -> None:
        record = Record.of("Hegel and the Problem of Beginning", ["Robb Dunphy"], 2023)
        self.assertTrue(CitationMatch(record, DUNPHY_ENTRY, frozenset({2023})).holds())

    def test_a_different_year_does_not_hold(self) -> None:
        record = Record.of("Hegel and the Problem of Beginning", ["Robb Dunphy"], 2019)
        self.assertFalse(CitationMatch(record, DUNPHY_ENTRY, frozenset({2023})).holds())

    def test_a_candidate_without_authors_is_never_counted_as_cited(self) -> None:
        record = Record.of("Hegel and the Problem of Beginning", [], 2023)
        self.assertFalse(CitationMatch(record, DUNPHY_ENTRY, frozenset({2023})).holds())

    def test_the_year_of_any_edition_the_entry_carries_holds(self) -> None:
        record = Record.of("Critique of Pure Reason", ["Immanuel Kant"], 1929)
        self.assertTrue(CitationMatch(record, KANT_GUYER_ENTRY, frozenset({1998, 1929})).holds())

    def test_a_title_absent_from_the_entry_does_not_hold(self) -> None:
        record = Record.of("The Beginning of Hegel's Logic", ["Robb Dunphy"], 2023)
        self.assertFalse(CitationMatch(record, DUNPHY_ENTRY, frozenset({2023})).holds())


class TestCandidateMerge(unittest.TestCase):
    REPORTS = [
        report("PhilPapers",
               [candidate(CitedWork("Hegel's Logic as Presuppositionless Science", ["Miles Hentrup"], 2019),
                          Sighting("PhilPapers", "https://philpapers.org/rec/HENHLA-2",
                                   obtain={"url": "https://doi.org/10.5840/idstudies2019115107",
                                           "kind": "publisher"}))]),
        report("Google Scholar",
               [candidate(CitedWork("Hegel’s logic as presuppositionless science", ["M Hentrup"], 2019),
                          Sighting("Google Scholar", "https://scholar.google.com/scholar?q=hentrup", citations=4))]),
        report("PhilArchive",
               [candidate(CitedWork("Hegel's Logic as Presuppositionless Science", [], 2019),
                          Sighting("PhilArchive", "https://philarchive.org/rec/HENHLA-2",
                                   obtain={"url": "https://philarchive.org/archive/HENHLA-2",
                                           "kind": "open copy"})),
                candidate(CitedWork("The Beginning of Hegel's Logic", ["Robb Dunphy"], 2020),
                          Sighting("PhilArchive", "https://philarchive.org/rec/DUNTBO-7"))]),
    ]

    def merged(self) -> list:
        return CandidateMerge().merged(CandidateParser().parse(self.REPORTS))

    def test_three_sightings_of_one_work_merge_into_one_candidate(self) -> None:
        self.assertEqual(2, len(self.merged()))

    def test_the_merged_candidate_keeps_every_sighting(self) -> None:
        hentrup = next(item for item in self.merged() if "Hentrup" in item.authors[0])
        self.assertEqual(["PhilPapers", "Google Scholar", "PhilArchive"],
                         [sighting.source for sighting in hentrup.sightings])

    def test_the_merged_candidate_keeps_every_distinct_obtain_link(self) -> None:
        hentrup = next(item for item in self.merged() if "Hentrup" in item.authors[0])
        self.assertEqual(["publisher", "open copy"], [link["kind"] for link in hentrup.obtain_links])

    def test_a_truncated_title_is_replaced_by_the_full_title_it_merges_with(self) -> None:
        reports = [report("PhilArchive",
                          [candidate(CitedWork("Hegel and Wittgenstein on Difficulties of Beginning at the ...", [],
                                               None),
                                     Sighting("PhilArchive", "https://philarchive.org/archive/MCHHAW"))]),
                   report("OpenAlex",
                          [candidate(CitedWork("Hegel and Wittgenstein on Difficulties of Beginning at the Beginning",
                                               ["Mácha, Jakub"], 2022),
                                     Sighting("OpenAlex", "https://api.openalex.org/works?search=x"))])]
        merged = CandidateMerge().merged(CandidateParser().parse(reports))
        self.assertEqual(["Hegel and Wittgenstein on Difficulties of Beginning at the Beginning"],
                         [item.title for item in merged])

    def test_the_source_citation_count_is_the_largest_reported(self) -> None:
        hentrup = next(item for item in self.merged() if "Hentrup" in item.authors[0])
        self.assertEqual(4, hentrup.source_citations)


class TestCandidateParser(unittest.TestCase):
    def test_a_candidate_without_a_seen_page_is_dropped(self) -> None:
        raw = candidate(CitedWork("Some Work", ["Someone"], 2020), Sighting("PhilPapers", ""))
        self.assertEqual([], CandidateParser().parse([report("PhilPapers", [raw])]))

    def test_an_obtain_link_of_an_unknown_kind_is_dropped(self) -> None:
        raw = candidate(CitedWork("Some Work", ["Someone"], 2020),
                        Sighting("PhilPapers", "https://philpapers.org/rec/X",
                                 obtain={"url": "https://sci-hub.example/x", "kind": "mirror"}))
        self.assertEqual([], CandidateParser().parse([report("PhilPapers", [raw])])[0].obtain_links)

    def test_an_obtain_link_that_is_only_a_site_root_is_dropped(self) -> None:
        raw = candidate(CitedWork("Some Work", ["Someone"], 2020),
                        Sighting("Google Scholar", "https://scholar.google.com/scholar?q=x",
                                 obtain={"url": "https://academia.edu", "kind": "open copy"}))
        self.assertEqual([], CandidateParser().parse([report("Google Scholar", [raw])])[0].obtain_links)


class TestHeldMarking(LibraryTestCase):
    def parsed(self, raw: dict) -> list:
        return CandidateParser().parse([report("PhilPapers", [raw])])

    def test_a_candidate_naming_a_held_work_is_marked_with_its_basename(self) -> None:
        candidates = self.parsed(candidate(CitedWork("The Opening of Hegel's Logic: From Being to Infinity",
                                                     ["Stephen Houlgate"], 2006),
                                           Sighting("PhilPapers", "https://philpapers.org/rec/HOUTOO-2")))
        HeldMarking(HeldWorks.from_library()).mark(candidates)
        self.assertEqual(HOULGATE, candidates[0].held_as)

    def test_a_candidate_the_library_lacks_is_unmarked(self) -> None:
        candidates = self.parsed(candidate(CitedWork("Hegel and the Problem of Beginning", ["Robb Dunphy"], 2023),
                                           Sighting("PhilPapers", "https://philpapers.org/rec/DUNHAT-4")))
        HeldMarking(HeldWorks.from_library()).mark(candidates)
        self.assertIsNone(candidates[0].held_as)

    def test_a_candidate_by_a_hyphenated_author_is_marked_with_the_held_works_basename(self) -> None:
        self.write_pdf(HYPHENATED)
        self.write_note(HYPHENATED, HYPHENATED_FRONTMATTER)
        candidates = self.parsed(candidate(CitedWork("Phenomenology of Perception", ["Maurice Merleau-Ponty"], 1945),
                                           Sighting("PhilPapers", "https://philpapers.org/rec/MERPOP")))
        HeldMarking(HeldWorks.from_library()).mark(candidates)
        self.assertEqual(HYPHENATED, candidates[0].held_as)


class TestLocalCitations(LibraryTestCase):
    def test_the_held_works_citing_the_candidate_are_attached(self) -> None:
        raw = candidate(CitedWork("Hegel and the Problem of Beginning", ["Robb Dunphy"], 2023),
                        Sighting("PhilPapers", "https://philpapers.org/rec/DUNHAT-4"))
        candidates = CandidateParser().parse([report("PhilPapers", [raw])])
        LocalCitations(self.unheld(HOULGATE, STERN)).attach(candidates)
        self.assertEqual([HOULGATE, STERN], [locator["basename"] for locator in candidates[0].cited_by])


class TestUnseenKnownItems(LibraryTestCase):
    def unseen_texts(self, raws: list[dict]) -> list[str]:
        candidates = CandidateParser().parse([report("PhilPapers", raws)])
        return [entry["text"] for entry in UnseenKnownItems(self.unheld(HOULGATE)).among(candidates)]

    def test_every_known_item_is_unseen_when_no_scout_returned_a_candidate(self) -> None:
        self.assertEqual([DUNPHY_ENTRY, TABAK_ENTRY], self.unseen_texts([]))


class TestOrdering(unittest.TestCase):
    def ordered_titles(self, reports: list[dict], unheld: dict) -> list[str]:
        candidates = CandidateParser().parse(reports)
        LocalCitations(unheld).attach(candidates)
        return [item.title for item in Ordering().ordered(candidates)]

    def test_local_citations_outrank_source_citations_which_outrank_year(self) -> None:
        reports = [report("Google Scholar", [
            candidate(CitedWork("Newest", ["A"], 2025), Sighting("Google Scholar", "https://s/1")),
            candidate(CitedWork("Most Cited Online", ["B"], 2010),
                      Sighting("Google Scholar", "https://s/2", citations=80)),
            candidate(CitedWork("Cited Locally", ["C"], 2000),
                      Sighting("Google Scholar", "https://s/3", citations=1))])]
        unheld = {"entries": [{"text": "C. Cited Locally. 2000.", "years": ["2000"],
                               "cited_by": [{"basename": "X", "folio": "1", "file_page": 1, "text": ""}]}]}
        self.assertEqual(["Cited Locally", "Most Cited Online", "Newest"], self.ordered_titles(reports, unheld))


class TestCommandLine(LibraryTestCase):
    def run_merge(self, reports: list[dict], *options: str) -> dict:
        buffer = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(reports))), contextlib.redirect_stdout(buffer):
            CommandLine().run(["merge", *options])
        return json.loads(buffer.getvalue())

    def write_json(self, name: str, content: dict) -> Path:
        path = self.vault.named(name)
        path.write_text(json.dumps(content), encoding="utf-8")
        return path

    def test_merge_separates_held_candidates_from_unheld(self) -> None:
        reports = [report("PhilPapers", [
            candidate(CitedWork("The Opening of Hegel's Logic", ["Stephen Houlgate"], 2006),
                      Sighting("PhilPapers", "https://philpapers.org/rec/HOUTOO-2")),
            candidate(CitedWork("Hegel and the Problem of Beginning", ["Robb Dunphy"], 2023),
                      Sighting("PhilPapers", "https://philpapers.org/rec/DUNHAT-4"))])]
        result = self.run_merge(reports)
        self.assertEqual([HOULGATE], [item["held_as"] for item in result["held"]])
        self.assertEqual(["Hegel and the Problem of Beginning"], [item["title"] for item in result["candidates"]])

    def test_merge_report_carries_the_queries_run(self) -> None:
        result = self.run_merge([report("PhilPapers", [], unreachable="403")])
        self.assertEqual([{"source": "PhilPapers", "query": "q"}], result["queries_run"])

    def test_merge_report_carries_the_unreachable_sources(self) -> None:
        result = self.run_merge([report("PhilPapers", [], unreachable="403")])
        self.assertEqual([{"source": "PhilPapers", "unreachable": "403"}], result["unreachable"])

    def test_merge_report_carries_the_known_items_no_candidate_names(self) -> None:
        dunphy = candidate(CitedWork("Hegel and the Problem of Beginning", ["Robb Dunphy"], 2023),
                           Sighting("PhilPapers", "https://philpapers.org/rec/DUNHAT-4"))
        known = self.write_json("known.json", self.unheld(HOULGATE))
        result = self.run_merge([report("PhilPapers", [dunphy])], "--known", str(known))
        self.assertEqual([TABAK_ENTRY], [entry["text"] for entry in result["known_unseen"]])

    def test_merge_attaches_the_local_citations_from_the_unheld_file(self) -> None:
        dunphy = candidate(CitedWork("Hegel and the Problem of Beginning", ["Robb Dunphy"], 2023),
                           Sighting("PhilPapers", "https://philpapers.org/rec/DUNHAT-4"))
        unheld = self.write_json("unheld.json", self.unheld(HOULGATE))
        result = self.run_merge([report("PhilPapers", [dunphy])], "--unheld", str(unheld))
        self.assertEqual([HOULGATE], [locator["basename"] for locator in result["candidates"][0]["cited_by"]])

    def test_merge_report_without_known_items_has_none_unseen(self) -> None:
        self.assertEqual([], self.run_merge([])["known_unseen"])


if __name__ == "__main__":
    unittest.main()
