from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from citation_graph import Neighbourhood
from _graph_fixtures import GraphTestCase, entry_body

HOULGATE = "Houlgate - 2006 - The Opening of Hegel's Logic"
STERN = "Stern - 2023 - Understanding Hegel's Logic"
PIPPIN = "Pippin - 2019 - Hegel's Realm of Shadows"
SHABEL = "Shabel - 2003 - Mathematics in Kant's Critical Philosophy"
DUNPHY_ENTRY = "Dunphy, Robb. Hegel and the Problem of Beginning. Lanham: Rowman, 2023."
BURBIDGE_ENTRY = "Burbidge, John. On Hegel's Logic. Atlantic Highlands: Humanities Press, 1981."
FRIEDMAN_ENTRY = "Friedman, Michael. Kant and the Exact Sciences. Cambridge: Harvard University Press, 1992."
PIPPIN_LINK = f"[[{PIPPIN}|Pippin, Robert. Hegel's Realm of Shadows. 2019.]]"
HEGEL = "Hegel"
KANT = "Kant"


class NeighbourhoodTestCase(GraphTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_work(PIPPIN, year="2019", field=(HEGEL,))
        self.write_work(HOULGATE, entry_body([DUNPHY_ENTRY, BURBIDGE_ENTRY]), year="2006", field=(HEGEL,))
        self.write_work(STERN, entry_body([DUNPHY_ENTRY, BURBIDGE_ENTRY, PIPPIN_LINK]), year="2023")
        self.write_work(SHABEL, entry_body([FRIEDMAN_ENTRY]), year="2003", field=(KANT,))
        self.sync()
        self.neighbourhood = Neighbourhood(self.graph())


class TestNeighbours(NeighbourhoodTestCase):
    def test_the_nearest_works_come_first_with_their_signals(self) -> None:
        listed = self.neighbourhood.of(STERN)["neighbours"]
        self.assertEqual([PIPPIN, HOULGATE], [neighbour["basename"] for neighbour in listed])
        self.assertEqual(1.0, listed[0]["signals"]["direct"])

    def test_a_neighbour_shows_the_references_it_shares(self) -> None:
        houlgate = self.neighbour_named(HOULGATE)
        self.assertEqual([BURBIDGE_ENTRY, DUNPHY_ENTRY], houlgate["shared_references"])
        self.assertEqual(2, houlgate["shared_reference_count"])

    def neighbour_named(self, basename: str) -> dict:
        listed = self.neighbourhood.of(STERN)["neighbours"]
        return next(neighbour for neighbour in listed if neighbour["basename"] == basename)

    def test_a_work_sharing_nothing_is_not_a_neighbour(self) -> None:
        listed = self.neighbourhood.of(STERN)["neighbours"]
        self.assertNotIn(SHABEL, [neighbour["basename"] for neighbour in listed])

    def test_the_bibliographies_tally_weighs_each_neighbours_bibliographies_by_its_score(self) -> None:
        report = self.neighbourhood.of(STERN)
        expected = round(sum(neighbour["score"] for neighbour in report["neighbours"]), 3)
        self.assertEqual([HEGEL], list(report["bibliographies"]))
        self.assertAlmostEqual(expected, report["bibliographies"][HEGEL], places=3)

    def test_the_count_caps_the_listing(self) -> None:
        self.assertEqual(1, len(Neighbourhood(self.graph(), 1).of(STERN)["neighbours"]))

    def test_a_basename_without_a_corpus_file_is_refused(self) -> None:
        with self.assertRaises(LookupError):
            self.neighbourhood.of("Nobody - 1999 - Nothing")


if __name__ == "__main__":
    unittest.main()
