from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import bibliographies
from citation_graph import GraphStore
from _bibliographies.listingparts import SLICED_KEYS, ListingParts, json_bytes
from _bibliographies.partsdir import PartsDirectory
from _bibliographies.reshaping import ShapeListing
from _bibliography_fixtures import TemporaryVault

PERIOD = "German Idealism"
SUBJECT = "Logic"
ROUTED_WORKS = [f"Scholar{number:02d} - 2001 - A Reading of the Whole" for number in range(24)]
NOMINATED_WORKS = [f"Reader{number:02d} - 2002 - A Reading of One Part" for number in range(3)]
NOMINATED_NAMES = ["Quantity", "Being", "Measure"]
DESCRIPTION = "A study of one stretch of the subject, long enough to weigh on the size of a part."
BUDGET = 4_000
ROOMY_BUDGET = 1_000_000


def nomination(name: str, work: str) -> dict:
    return {"name": name, "kind": "topic", "parent": SUBJECT, "works": [work], "placed_on": [SUBJECT]}


class ListingCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.bibliography_in("1 historical periods", PERIOD, f"## Maps\n\n- [[{SUBJECT}]]\n")
        self.vault.bibliography_in("3 topics", SUBJECT, "## Maps\n\n## Works in library\n")
        for basename in ROUTED_WORKS:
            self.work(basename, PERIOD)
        for basename in NOMINATED_WORKS:
            self.work(basename, SUBJECT)
        self.listing = self.listed()

    def work(self, basename: str, on: str) -> None:
        self.vault.note(basename, field=[f"[[{on}]]"], source_role="secondary", title=basename, description=DESCRIPTION,
                        author=[basename.split(" - ")[0]], year=int(basename.split(" - ")[1]))

    def listed(self) -> dict:
        store = GraphStore(Path(tempfile.mkdtemp()) / "graph.sqlite")
        self.addCleanup(store.close)
        nominations = [nomination(name, work) for name, work in zip(NOMINATED_NAMES, NOMINATED_WORKS)]
        return ShapeListing(bibliographies.Bibliographies(), bibliographies.Corpus(), store).of(nominations)

    def parts(self, budget: int = BUDGET) -> list[dict]:
        return ListingParts(self.listing, budget).cut()

    @staticmethod
    def works_named(part: dict) -> set[str]:
        routed = {finding["work"] for finding in part["routing_placements"]}
        return routed | {work for nominated in part["nominations"] for work in nominated["works"]}


class TestAListingOverTheBudget(ListingCase):
    def test_is_larger_than_the_budget(self) -> None:
        self.assertGreater(json_bytes(self.listing), BUDGET)

    def test_is_cut_into_several_parts(self) -> None:
        self.assertGreater(len(self.parts()), 1)

    def test_every_part_keeps_within_the_budget(self) -> None:
        self.assertEqual([], [json_bytes(part) for part in self.parts() if json_bytes(part) > BUDGET])

    def test_every_part_carries_the_whole_tree(self) -> None:
        self.assertEqual([self.listing["tree"]] * len(self.parts()), [part["tree"] for part in self.parts()])

    def test_every_entry_sits_in_one_part_in_the_listings_order(self) -> None:
        routed = [finding for part in self.parts() for finding in part["routing_placements"]]
        self.assertEqual(self.listing["routing_placements"], routed)

    def test_each_part_describes_the_works_it_names_and_no_other(self) -> None:
        for part in self.parts():
            self.assertEqual(self.works_named(part), set(part["descriptions"]))

    def test_a_part_carries_each_description_as_the_listing_does(self) -> None:
        for part in self.parts():
            for basename, description in part["descriptions"].items():
                self.assertEqual(self.listing["descriptions"][basename], description)


class TestAListingUnderTheBudget(ListingCase):
    def test_is_one_part_holding_the_whole_listing(self) -> None:
        self.assertEqual([self.listing], self.parts(ROOMY_BUDGET))


class TestAnEntryLargerThanTheBudget(ListingCase):
    def test_takes_a_part_of_its_own(self) -> None:
        entries = sum(len(key.entries(self.listing)) for key in SLICED_KEYS)
        self.assertEqual(entries, len(self.parts(budget=1)))


class TestTheNominations(ListingCase):
    def test_are_listed_by_parent_then_name(self) -> None:
        self.assertEqual(sorted(NOMINATED_NAMES), [nominated["name"] for nominated in self.listing["nominations"]])

    def test_stay_in_one_part_where_one_part_holds_them(self) -> None:
        holding = [part for part in self.parts() if part["nominations"]]
        self.assertEqual([self.listing["nominations"]], [part["nominations"] for part in holding])


class TestAKeyThatFitsOnlyAPartOfItsOwn(unittest.TestCase):
    AUTHORS = [{"author": "Scholar", "works": [f"Scholar - 2001 - Work {number}" for number in range(5)]}]
    NOMINATIONS = [{"name": name, "kind": "topic", "parent": SUBJECT, "works": []} for name in ("Being", "Measure")]

    def listing(self, **held) -> dict:
        return {"tree": [{"name": SUBJECT}], "authors": [], "nominations": [], "descriptions": {}, **held}

    def test_opens_a_part_rather_than_be_cut_across_two(self) -> None:
        alone = ListingParts(self.listing(nominations=self.NOMINATIONS), ROOMY_BUDGET).cut()[0]
        budget = json_bytes(alone) + json_bytes(self.NOMINATIONS[0])
        parts = ListingParts(self.listing(authors=self.AUTHORS, nominations=self.NOMINATIONS), budget).cut()
        self.assertEqual([[], self.NOMINATIONS], [part["nominations"] for part in parts])


class TestTheClustersOfACutListing(unittest.TestCase):
    CLUSTERS = {"clusters": [{"cluster": 1, "works": ["A - 2000 - B"]}], "findings": {"new": [], "split": [],
                                                                                   "misfit": []}}
    AUTHORS = [{"author": name, "works": []} for name in ("Scholar", "Reader")]

    def parts(self, budget: int) -> list[dict]:
        listing = {"tree": [], "clusters": self.CLUSTERS, "authors": self.AUTHORS, "descriptions": {}}
        return ListingParts(listing, budget).cut()

    def test_are_left_out_of_every_part(self) -> None:
        self.assertEqual([[], []], [part["clusters"]["clusters"] for part in self.parts(budget=1)])

    def test_stay_in_a_listing_one_part_holds(self) -> None:
        self.assertEqual([self.CLUSTERS], [part["clusters"] for part in self.parts(ROOMY_BUDGET)])


class TestTheStrayPlacementsOfACutListing(unittest.TestCase):
    WORKS = ["Thinker - 1807 - A System", "Scholar - 2001 - A Reading"]
    STRAYS = [{"work": "Thinker - 1807 - A System", "on": [SUBJECT]}, {"work": "Thinker - 1812 - A Logic", "on": [SUBJECT]}]

    def parts(self) -> list[dict]:
        listing = {"tree": [], "authors": [{"author": work, "works": [work]} for work in self.WORKS],
                   "stray_placements": self.STRAYS, "descriptions": {work: {"title": work} for work in self.WORKS}}
        return ListingParts(listing, budget=1).cut()

    def test_go_to_the_part_that_names_their_work_and_to_no_other(self) -> None:
        self.assertEqual([self.STRAYS[:1], []], [part["stray_placements"] for part in self.parts()])


class TestAListingWithNothingToCut(unittest.TestCase):
    def test_is_one_part(self) -> None:
        self.assertEqual(1, len(ListingParts({"tree": [{"name": SUBJECT}], "descriptions": {}}, budget=1).cut()))


class TestThePartsDirectory(ListingCase):
    def setUp(self) -> None:
        super().setUp()
        self.root = Path(tempfile.mkdtemp()) / "parts"
        self.directory = PartsDirectory(self.root)

    def test_each_part_is_written_as_a_listing_under_its_number(self) -> None:
        parts = self.parts()
        self.directory.write(parts)
        read = [json.loads((self.root / str(number) / "listing.json").read_text(encoding="utf-8"))
                for number in self.directory.numbers()]
        self.assertEqual(parts, read)

    def test_a_new_cut_clears_the_parts_and_answers_of_the_cut_before(self) -> None:
        self.directory.write(self.parts())
        (self.root / "1" / "answers.json").write_text("{}", encoding="utf-8")
        self.directory.write(self.parts(ROOMY_BUDGET))
        self.assertEqual(([1], {}), (self.directory.numbers(), self.directory.answers()))


if __name__ == "__main__":
    unittest.main()
