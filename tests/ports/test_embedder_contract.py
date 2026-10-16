from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _ports.compute import Embedder
from _rag_fakes import FakeEmbedder

TEXTS = ["Being passes into nothing.", "Nothing passes into being.", "Becoming is their unity."]
QUERY = "the unity of being and nothing"


class EmbedderContract:
    def embedder(self) -> Embedder:
        raise NotImplementedError

    def test_the_model_is_named(self) -> None:
        self.assertTrue(self.embedder().model.strip())

    def test_each_text_gets_one_vector(self) -> None:
        self.assertEqual(len(TEXTS), len(self.embedder().embed(TEXTS)))

    def test_every_vector_shares_one_dimension(self) -> None:
        dimensions = {len(vector) for vector in self.embedder().embed(TEXTS)}
        self.assertEqual(1, len(dimensions))

    def test_a_query_embeds_as_a_text_does(self) -> None:
        embedder = self.embedder()
        self.assertEqual(embedder.embed([QUERY])[0], embedder.embed_query(QUERY))


class TestFakeEmbedderKeepsTheContract(EmbedderContract, unittest.TestCase):
    def embedder(self) -> Embedder:
        return FakeEmbedder()


if __name__ == "__main__":
    unittest.main()
