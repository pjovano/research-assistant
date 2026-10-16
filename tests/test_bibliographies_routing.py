from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import bibliographies
from citation_graph import GraphStore
from _bibliographies.reshaping import ShapeListing
from _bibliographies.routing import RoutingFindings
from _bibliography_fixtures import HEGEL, HOULGATE, TemporaryVault

PERIOD = "German Idealism"
SUBJECT = "Logic"
DISCIPLINE = "Philosophy of Science"
COMPARISON = "Logic and Science"
STERN = "Stern - 2023 - Understanding Hegel's Logic"


class RoutingCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.bibliography_in("1 historical periods", PERIOD, f"## Maps\n\n- [[{SUBJECT}]]\n")
        self.vault.bibliography_in("3 topics", SUBJECT, "## Maps\n\n## Secondary literature\n")
        self.vault.bibliography_in("3 topics", DISCIPLINE, "## Maps\n\n## Secondary literature\n")

    def work(self, basename: str, *field: str) -> None:
        self.vault.note(basename, field=[f"[[{name}]]" for name in field], source_role="secondary",
                        author=[basename.split(" - ")[0]], year=int(basename.split(" - ")[1]))

    def findings(self) -> RoutingFindings:
        return RoutingFindings(bibliographies.Bibliographies(), bibliographies.Corpus().notes())


class TestAWorkOnABibliographyThatListsMaps(RoutingCase):
    def test_is_a_routing_placement_with_the_maps_beneath_it(self) -> None:
        self.work(HOULGATE, PERIOD)
        self.assertEqual([{"work": HOULGATE, "on": PERIOD, "maps": [SUBJECT]}], self.findings().routing_placements())

    def test_on_a_bibliography_listing_no_maps_is_no_routing_placement(self) -> None:
        self.work(HOULGATE, SUBJECT)
        self.assertEqual([], self.findings().routing_placements())

    def test_is_named_in_an_advisory_group(self) -> None:
        self.work(HOULGATE, PERIOD)
        advisory = self.vault.report().as_dict()["advisory"]
        self.assertTrue(any(heading.startswith("Routing") for heading in advisory))


class TestAScholarsBibliographyBeneathASubject(RoutingCase):
    def test_leaves_the_subject_no_routing_bibliography(self) -> None:
        self.vault.bibliography_in("3 topics", SUBJECT, "## Maps\n\n- [[Houlgate]]\n")
        self.vault.bibliography_in("2 authors", "Houlgate", "## Maps\n", author="Houlgate")
        self.work(STERN, SUBJECT)
        self.assertEqual([], self.findings().routing_placements())


class TestAThinkersBibliographyBeneathAPeriod(RoutingCase):
    def test_makes_the_period_a_routing_bibliography(self) -> None:
        self.vault.bibliography_in("1 historical periods", PERIOD, "## Maps\n\n- [[Hegel]]\n")
        self.vault.bibliography_in("2 authors", "Hegel", "## Maps\n", author="Hegel")
        self.work(STERN, PERIOD)
        self.assertEqual([PERIOD], [finding["on"] for finding in self.findings().routing_placements()])


class TestTwoBibliographiesThatShareWorks(RoutingCase):
    def test_sharing_two_works_are_co_placed(self) -> None:
        self.work(HOULGATE, SUBJECT, DISCIPLINE)
        self.work(STERN, SUBJECT, DISCIPLINE)
        self.assertEqual([{"bibliographies": [SUBJECT, DISCIPLINE], "works": [HOULGATE, STERN]}],
                         self.findings().co_placed())

    def test_sharing_one_work_are_not_co_placed(self) -> None:
        self.work(HOULGATE, SUBJECT, DISCIPLINE)
        self.assertEqual([], self.findings().co_placed())

    def test_that_list_one_comparison_map_are_not_co_placed(self) -> None:
        self.vault.bibliography_in("3 topics", SUBJECT, f"## Maps\n\n- [[{COMPARISON}]]\n")
        self.vault.bibliography_in("3 topics", DISCIPLINE, f"## Maps\n\n- [[{COMPARISON}]]\n")
        self.vault.bibliography_in("3 topics", COMPARISON, "## Maps\n\n## Secondary literature\n")
        self.work(HOULGATE, SUBJECT, DISCIPLINE)
        self.work(STERN, SUBJECT, DISCIPLINE)
        self.assertEqual([], self.findings().co_placed())


class TestTheShapeListingsRoutingFindings(RoutingCase):
    def test_carries_the_routing_placements_described(self) -> None:
        self.work(HOULGATE, PERIOD)
        self.work(HEGEL, SUBJECT)
        store = GraphStore(Path(tempfile.mkdtemp()) / "graph.sqlite")
        self.addCleanup(store.close)
        listing = ShapeListing(bibliographies.Bibliographies(), bibliographies.Corpus(), store).of([])
        self.assertEqual([HOULGATE], [finding["work"] for finding in listing["routing_placements"]])
        self.assertIn(HOULGATE, listing["descriptions"])
        self.assertEqual([], listing["co_placed"])


if __name__ == "__main__":
    unittest.main()
