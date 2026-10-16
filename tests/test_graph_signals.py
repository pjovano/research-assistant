from __future__ import annotations

import math
import unittest

from _support import LiveTree

LiveTree.activate()

from citation_graph import (
    COCITATION_WEIGHT,
    COUPLING_WEIGHT,
    DIRECT_WEIGHT,
    EMBEDDING_WEIGHT,
    SHARED_AUTHOR_FACTOR,
    Centroids,
    CitationRow,
    PairSignals,
    ReferenceSets,
    Signals,
    held_key,
    unheld_key,
)

A, B, C, D = "A - 2001 - One", "B - 2002 - Two", "C - 2003 - Three", "D - 2004 - Four"


def row(citing: str, cited: str) -> CitationRow:
    return CitationRow(citing, cited, None, None, cited)


def signals_over(rows: list[CitationRow], centroids: dict | None = None, surnames: dict | None = None) -> PairSignals:
    return PairSignals(ReferenceSets(rows), Centroids(centroids or {}), surnames or {})


class TestDirectCitation(unittest.TestCase):
    def test_a_work_citing_another_scores_full(self) -> None:
        pairs = signals_over([row(A, held_key(B))])
        self.assertEqual(1.0, pairs.between(A, B).direct)

    def test_the_direction_does_not_matter(self) -> None:
        pairs = signals_over([row(A, held_key(B))])
        self.assertEqual(1.0, pairs.between(B, A).direct)

    def test_a_citation_between_works_sharing_an_author_is_down_weighted(self) -> None:
        pairs = signals_over([row(A, held_key(B))], surnames={A: frozenset({"kant"}), B: frozenset({"kant"})})
        self.assertEqual(SHARED_AUTHOR_FACTOR, pairs.between(A, B).direct)

    def test_works_that_do_not_cite_each_other_score_nothing(self) -> None:
        self.assertEqual(0.0, signals_over([]).between(A, B).direct)


class TestBibliographicCoupling(unittest.TestCase):
    def test_coupling_is_the_salton_cosine_of_the_reference_sets(self) -> None:
        rows = [row(A, unheld_key(1)), row(A, unheld_key(2)), row(B, unheld_key(1))]
        self.assertAlmostEqual(1 / math.sqrt(2), signals_over(rows).between(A, B).coupling)

    def test_held_and_unheld_references_both_count(self) -> None:
        rows = [row(A, held_key(C)), row(A, unheld_key(1)), row(B, held_key(C)), row(B, unheld_key(1))]
        self.assertAlmostEqual(1.0, signals_over(rows).between(A, B).coupling)

    def test_a_work_with_no_references_couples_with_nothing(self) -> None:
        self.assertEqual(0.0, signals_over([row(A, unheld_key(1))]).between(A, B).coupling)


class TestCoCitation(unittest.TestCase):
    def test_two_works_cited_by_the_same_third_are_co_cited(self) -> None:
        rows = [row(C, held_key(A)), row(C, held_key(B))]
        self.assertAlmostEqual(1.0, signals_over(rows).between(A, B).cocitation)

    def test_co_citation_is_normalised_by_each_works_citers(self) -> None:
        rows = [row(C, held_key(A)), row(C, held_key(B)), row(D, held_key(A))]
        self.assertAlmostEqual(1 / math.sqrt(2), signals_over(rows).between(A, B).cocitation)


class TestEmbeddingSimilarity(unittest.TestCase):
    def test_the_cosine_of_the_centroids(self) -> None:
        pairs = signals_over([], centroids={A: [1.0, 0.0], B: [1.0, 1.0]})
        self.assertAlmostEqual(1 / math.sqrt(2), pairs.between(A, B).embedding)

    def test_a_negative_cosine_is_no_signal(self) -> None:
        pairs = signals_over([], centroids={A: [1.0, 0.0], B: [-1.0, 0.0]})
        self.assertEqual(0.0, pairs.between(A, B).embedding)

    def test_a_work_without_a_centroid_has_no_embedding_signal(self) -> None:
        self.assertEqual(0.0, signals_over([], centroids={A: [1.0]}).between(A, B).embedding)


class TestCombinedScore(unittest.TestCase):
    def test_the_signals_combine_by_their_weights(self) -> None:
        expected = DIRECT_WEIGHT + 0.5 * COUPLING_WEIGHT + 0.25 * COCITATION_WEIGHT + 0.1 * EMBEDDING_WEIGHT
        self.assertAlmostEqual(expected, Signals(1.0, 0.5, 0.25, 0.1).combined())

    def test_the_weights_sum_to_one(self) -> None:
        self.assertAlmostEqual(1.0, DIRECT_WEIGHT + COUPLING_WEIGHT + COCITATION_WEIGHT + EMBEDDING_WEIGHT)


if __name__ == "__main__":
    unittest.main()
