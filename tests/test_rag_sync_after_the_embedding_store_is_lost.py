from __future__ import annotations

import io
import unittest

from _support import LiveTree

LiveTree.activate()

import rag
import vault
from _rag_fakes import CorpusStoreTestCase, FakeEmbedder, FakeEmbeddingStore

BASENAME = "Doe - 2020 - A Work"
NOTE = ("---\ntitle: A Work\nauthor: [Doe]\nyear: 2020\n---\n\n# One\n\nBeing is the indeterminate immediate.\n\n"
        "# Two\n\nNothing is the same as pure being.\n")


class WordBudget:
    def count(self, text: str) -> int:
        return len(text.split())


class SyncOverALostEmbeddingStoreTestCase(CorpusStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        (vault.CORPUS_DIR / f"{BASENAME}.md").write_text(NOTE, encoding="utf-8")
        self.synced(FakeEmbeddingStore())

    def synced(self, embeddings: FakeEmbeddingStore) -> rag.StoreSync:
        index = rag.SearchIndex(self.fulltext, embeddings, FakeEmbedder(), rag.IndexableDocuments())
        sync = rag.StoreSync(index, rag.ParentChildChunker(WordBudget()), rag.SyncProgress(io.StringIO()))
        sync.run()
        return sync


class TestSyncReEmbedsAWorkWhoseVectorsTheEmbeddingStoreLost(SyncOverALostEmbeddingStoreTestCase):
    def test_every_recorded_chunk_is_embedded_again_into_an_emptied_store(self) -> None:
        emptied = FakeEmbeddingStore()
        self.synced(emptied)
        self.assertEqual(set(self.fulltext.chunk_ids_of(BASENAME)), emptied.ids())

    def test_the_work_is_reported_as_changed_with_its_chunks_embedded(self) -> None:
        report = self.synced(FakeEmbeddingStore()).report()
        expected = (len(self.fulltext.chunk_ids_of(BASENAME)), [BASENAME])
        self.assertEqual(expected, (report["embedded_chunks"], report["changed"]))

    def test_a_work_whose_vectors_are_all_held_is_skipped(self) -> None:
        held = FakeEmbeddingStore()
        self.synced(held)
        self.assertEqual([BASENAME], self.synced(held).report()["skipped"])


if __name__ == "__main__":
    unittest.main()
