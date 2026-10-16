from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from citation_graph import MAX_BIBLIOGRAPHY_WORKS, ClusterReport
from _graph_fixtures import GraphTestCase, entry_body

HEGEL = "Hegel"
KANT = "Kant"
HEGEL_ENTRIES = [f"Author{n}, Hegelian. Study {n} of Hegel's Logic. Press, 199{n}." for n in range(3)]
KANT_ENTRIES = [f"Writer{n}, Kantian. Study {n} of Kant's Deduction. Press, 198{n}." for n in range(3)]


class ClusterTestCase(GraphTestCase):
    def hegel_works(self, count: int, field: tuple[str, ...] = (HEGEL,), start: int = 0) -> list[str]:
        return [self.work(f"Hegelian{n} - 200{n % 10} - Logic Study {n}", HEGEL_ENTRIES, field)
                for n in range(start, start + count)]

    def kant_works(self, count: int, field: tuple[str, ...] = (KANT,)) -> list[str]:
        return [self.work(f"Kantian{n} - 199{n % 10} - Deduction Study {n}", KANT_ENTRIES, field) for n in range(count)]

    def work(self, basename: str, entries: list[str], field: tuple[str, ...]) -> str:
        self.write_work(basename, entry_body(entries), field=field)
        return basename

    def report(self) -> dict:
        self.sync()
        return ClusterReport(self.graph()).report()


class TestCommunities(ClusterTestCase):
    def test_works_sharing_references_cluster_together_and_apart_from_the_rest(self) -> None:
        hegel, kant = self.hegel_works(3), self.kant_works(3)
        clusters = [set(cluster["works"]) for cluster in self.report()["clusters"]]
        self.assertIn(set(hegel), clusters)
        self.assertIn(set(kant), clusters)

    def test_two_runs_give_one_answer(self) -> None:
        self.hegel_works(4)
        self.kant_works(4)
        first = self.report()["clusters"]
        self.assertEqual(first, ClusterReport(self.graph()).report()["clusters"])

    def test_a_cluster_names_the_bibliographies_and_references_of_its_works(self) -> None:
        self.hegel_works(3)
        cluster = self.report()["clusters"][0]
        self.assertEqual({HEGEL: 3}, cluster["bibliographies"])
        self.assertEqual(3, cluster["references"][0]["citers"])


class TestFindings(ClusterTestCase):
    def test_a_cluster_on_no_shared_bibliography_is_a_new_finding(self) -> None:
        hegel = self.hegel_works(3, field=())
        found = self.report()["findings"]["new"]
        self.assertEqual([set(hegel)], [set(finding["works"]) for finding in found])

    def test_a_cluster_whose_majority_shares_a_bibliography_is_not_new(self) -> None:
        self.hegel_works(3)
        self.assertEqual([], self.report()["findings"]["new"])

    def test_a_large_bibliography_spanning_two_clusters_is_a_split_finding(self) -> None:
        self.hegel_works(MAX_BIBLIOGRAPHY_WORKS // 2 + 1, field=("Idealism",))
        self.kant_works(MAX_BIBLIOGRAPHY_WORKS // 2 + 1, field=("Idealism",))
        found = self.report()["findings"]["split"]
        self.assertEqual(["Idealism"], [finding["bibliography"] for finding in found])
        self.assertEqual(2, len(found[0]["parts"]))

    def test_a_bibliography_within_the_cap_is_not_split(self) -> None:
        self.hegel_works(3, field=("Idealism",))
        self.kant_works(3, field=("Idealism",))
        self.assertEqual([], self.report()["findings"]["split"])

    def test_a_work_whose_neighbours_all_sit_elsewhere_is_a_misfit(self) -> None:
        self.hegel_works(3)
        stray = self.work("Stray - 2005 - Logic Study", HEGEL_ENTRIES, (KANT,))
        found = self.report()["findings"]["misfit"]
        self.assertEqual([stray], [finding["work"] for finding in found])
        self.assertEqual({HEGEL: 3}, found[0]["neighbours_on"])

    def test_an_unheld_work_a_cluster_keeps_citing_is_a_missing_finding(self) -> None:
        self.hegel_works(3)
        found = self.report()["findings"]["missing"]
        self.assertEqual(sorted(HEGEL_ENTRIES), sorted(finding["reference"] for finding in found))
        self.assertEqual(3, found[0]["citers"])


if __name__ == "__main__":
    unittest.main()
