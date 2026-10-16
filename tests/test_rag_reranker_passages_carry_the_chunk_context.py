from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import rag
from _rag_fakes import CorpusStoreTestCase, FakeEmbedder, FakeEmbeddingStore, FakeReranker, hashed_vector

BASENAME = "Hegel - 1812 - Science of Logic"
WORK_LABEL = "Hegel, 1812, Science of Logic"
HEADING_PATH = "Essence"
TEXT = "Essence is reflected being."


class PassageRecordingReranker(FakeReranker):
    def __init__(self) -> None:
        super().__init__()
        self.passages: list[str] = []

    def scores(self, query: str, passages: list[str]) -> list[float]:
        self.passages.extend(passages)
        return super().scores(query, passages)


def chunked_work() -> rag.ChunkedDocument:
    metadata = {"heading_path": HEADING_PATH, "parent_id": "p1", "basename": BASENAME}
    context = rag.chunk_context(WORK_LABEL, HEADING_PATH)
    child = rag.Child("c1", "p1", BASENAME, TEXT, context, rag.embedded_text(context, TEXT), metadata)
    return rag.ChunkedDocument((rag.Parent("p1", BASENAME, TEXT, metadata),), (child,))


class TestTheRerankerScoresThePassageUnderTheContextItWasEmbeddedUnder(CorpusStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.chunked = chunked_work()
        self.fulltext.replace_document(BASENAME, self.chunked, rag.ManifestRecord.unstamped("hash"))
        embeddings = FakeEmbeddingStore()
        children = list(self.chunked.children)
        embeddings.add(children, [hashed_vector(child.embedded_text) for child in children])
        self.reranker = PassageRecordingReranker()
        index = rag.SearchIndex(self.fulltext, embeddings, FakeEmbedder(), rag.IndexableDocuments())
        rag.HybridSearch(index, self.reranker).results("essence")

    def test_the_passage_is_the_embedded_text_of_the_child(self) -> None:
        self.assertEqual([self.chunked.children[0].embedded_text], self.reranker.passages)

    def test_the_passage_names_the_work(self) -> None:
        self.assertIn(WORK_LABEL, self.reranker.passages[0])


if __name__ == "__main__":
    unittest.main()
