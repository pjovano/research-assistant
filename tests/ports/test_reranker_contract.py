from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _ports.compute import Reranker
from _rag_fakes import FakeReranker

QUERY = "the unity of being and nothing"
PASSAGES = ["Being passes into nothing.", "Essence is reflection.", "Becoming is their unity."]


class RerankerContract:
    def reranker(self) -> Reranker:
        raise NotImplementedError

    def test_an_available_reranker_names_no_cause(self) -> None:
        self.assertIsNone(self.reranker().unavailable_cause())

    def test_each_passage_gets_one_score(self) -> None:
        scores = self.reranker().scores(QUERY, PASSAGES)
        self.assertEqual(len(PASSAGES), len(scores))
        self.assertTrue(all(isinstance(score, float) for score in scores))

    def test_stopping_twice_is_harmless(self) -> None:
        reranker = self.reranker()
        reranker.stop()
        reranker.stop()
        self.assertIsNone(reranker.unavailable_cause())


class TestFakeRerankerKeepsTheContract(RerankerContract, unittest.TestCase):
    def reranker(self) -> Reranker:
        return FakeReranker({"unity": 0.9})


if __name__ == "__main__":
    unittest.main()
