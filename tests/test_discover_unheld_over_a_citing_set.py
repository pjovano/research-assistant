from __future__ import annotations

import re
import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from references import MIN_COMMON_ENTRIES, EditionIdentity, HeldWorks, ParsedReference
from _discover.cited import SAME_LIST_KEY, UnheldWorks
from _discover.merging import CandidateParser, LocalCitations
from _discover_fixtures import CitedWork, Sighting, candidate, report
from _references_fixtures import LINK_LINE, VaultTestCase

FIRST_CHAPTER = "Adler - 2019 - Tolerance and Its Limits"
SECOND_CHAPTER = "Brandt - 2019 - Borderline Cases Reconsidered"
ARTICLE = "Castell - 2021 - Higher-Order Vagueness Again"
SURNAME_HEADS = ("Bar", "Del", "Fen", "Gor", "Hal", "Jor", "Kes", "Lun")
SURNAME_TAILS = ("mann", "ovic", "sen", "wald", "ini")
PUBLISHER = "Leiden: Brill"
FIRST_YEAR = 1950
MANY = 40
SHARED_TITLE = "A Treatise on the Boundaries of Predicates"
ENTRY_RE = re.compile(r"^(?P<author>\w+, Anna)\. (?P<title>.+?)\. .*?(?P<year>\d{4})\.$")
MATCHER = "_references.matching.SequenceMatcher"


class EntryFieldsParser:
    def parse(self, entry_text: str) -> ParsedReference:
        fields = ENTRY_RE.match(entry_text)
        return ParsedReference((fields["author"],), fields["title"], None, fields["year"], None, None)


class CitingSetTestCase(VaultTestCase):
    def surnames(self, count: int) -> list[str]:
        return [f"{head}{tail}" for head in SURNAME_HEADS for tail in SURNAME_TAILS][:count]

    def entries_with_publisher(self, count: int) -> list[str]:
        return [f"{surname}, Anna. {SHARED_TITLE}. {PUBLISHER}, {FIRST_YEAR + position}."
                for position, surname in enumerate(self.surnames(count))]

    def entries_without_publisher(self, count: int) -> list[str]:
        return [f"{surname}, Anna. {SHARED_TITLE}. Brill {FIRST_YEAR + position}."
                for position, surname in enumerate(self.surnames(count))]

    def hold(self, basename: str, entries: list[str]) -> None:
        surname, year, title = basename.split(" - ")
        listed = "\n\n".join(entries)
        body = f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n%% p. 301 (file p. 310) %%\n\n{listed}\n"
        self.write_pdf(basename)
        self.write_note(basename, f"title: {title}\nauthor:\n- {surname}\nyear: {year}\n", body)

    def unheld(self, *basenames: str, min_citing: int = 1) -> dict:
        return UnheldWorks(HeldWorks.from_library(), EntryFieldsParser()).over(list(basenames), min_citing)

    def entry_citing(self, result: dict, surname: str) -> dict:
        return next(entry for entry in result["entries"] if entry["text"].startswith(surname))


class TestUnheldMergesACitingSetOfManyEntries(CitingSetTestCase):
    def test_entries_that_share_no_surname_are_never_compared(self) -> None:
        self.hold(ARTICLE, self.entries_without_publisher(MANY))
        with mock.patch.object(EditionIdentity, "names_same_work_as", return_value=False) as compared:
            self.unheld(ARTICLE)
        self.assertEqual(0, compared.call_count)

    def test_titles_under_different_first_authors_are_never_measured_for_similarity(self) -> None:
        self.hold(ARTICLE, self.entries_with_publisher(MANY))
        with mock.patch(MATCHER) as matcher:
            self.unheld(ARTICLE)
        self.assertEqual(0, matcher.call_count)

    def test_entries_under_different_first_authors_stay_apart(self) -> None:
        self.hold(ARTICLE, self.entries_with_publisher(MANY))
        self.assertEqual(MANY, len(self.unheld(ARTICLE)["entries"]))

    def test_an_entry_sharing_only_its_first_author_with_another_still_joins_it(self) -> None:
        self.hold(FIRST_CHAPTER, self.entries_with_publisher(1))
        self.hold(ARTICLE, [f"Barmann, Anna. {SHARED_TITLE}. Trans. B. Fenwald. London 2004."])
        self.assertEqual([2], [entry["cited_by_count"] for entry in self.unheld(FIRST_CHAPTER, ARTICLE)["entries"]])


class TestWorksPrintingOneReferenceListInCommonCountOnce(CitingSetTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.common = self.entries_with_publisher(MIN_COMMON_ENTRIES)
        self.cited = self.surnames(1)[0]

    def test_two_works_printing_a_list_in_common_count_once(self) -> None:
        self.hold(FIRST_CHAPTER, self.common)
        self.hold(SECOND_CHAPTER, self.common)
        result = self.unheld(FIRST_CHAPTER, SECOND_CHAPTER)
        self.assertEqual(1, self.entry_citing(result, self.cited)["cited_by_count"])

    def test_the_later_work_of_a_common_list_is_listed_under_the_earlier(self) -> None:
        self.hold(FIRST_CHAPTER, self.common)
        self.hold(SECOND_CHAPTER, self.common)
        locators = self.entry_citing(self.unheld(FIRST_CHAPTER, SECOND_CHAPTER), self.cited)["cited_by"]
        self.assertEqual([(FIRST_CHAPTER, None), (SECOND_CHAPTER, FIRST_CHAPTER)],
                         [(locator["basename"], locator.get(SAME_LIST_KEY)) for locator in locators])

    def test_two_works_sharing_fewer_entries_than_a_common_list_count_twice(self) -> None:
        self.hold(FIRST_CHAPTER, self.common)
        self.hold(SECOND_CHAPTER, self.common[:MIN_COMMON_ENTRIES - 1])
        result = self.unheld(FIRST_CHAPTER, SECOND_CHAPTER)
        self.assertEqual(2, self.entry_citing(result, self.cited)["cited_by_count"])

    def test_a_work_outside_the_common_list_adds_to_the_count(self) -> None:
        self.hold(FIRST_CHAPTER, self.common)
        self.hold(SECOND_CHAPTER, self.common)
        self.hold(ARTICLE, self.common[:1])
        result = self.unheld(FIRST_CHAPTER, SECOND_CHAPTER, ARTICLE)
        self.assertEqual(2, self.entry_citing(result, self.cited)["cited_by_count"])

    def test_a_minimum_of_citing_works_drops_an_entry_only_a_common_list_carries(self) -> None:
        self.hold(FIRST_CHAPTER, self.common)
        self.hold(SECOND_CHAPTER, self.common)
        self.assertEqual([], self.unheld(FIRST_CHAPTER, SECOND_CHAPTER, min_citing=2)["entries"])

    def test_a_candidate_cited_from_a_common_list_is_counted_once(self) -> None:
        self.hold(FIRST_CHAPTER, self.common)
        self.hold(SECOND_CHAPTER, self.common)
        found = candidate(CitedWork(SHARED_TITLE, [f"Anna {self.cited}"], FIRST_YEAR),
                          Sighting("PhilPapers", "https://philpapers.org/rec/TREATISE"))
        candidates = CandidateParser().parse([report("PhilPapers", [found])])
        LocalCitations(self.unheld(FIRST_CHAPTER, SECOND_CHAPTER)).attach(candidates)
        self.assertEqual(1, candidates[0].as_dict()["cited_by_count"])


if __name__ == "__main__":
    unittest.main()
