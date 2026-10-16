from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _ports.compute import EmbeddingStore
from _rag.chunking import Child
from _rag_fakes import FakeEmbeddingStore

MODEL = "placeholder-embedding"
NEAR = [1.0, 0.0, 0.0]
FAR = [0.0, 1.0, 0.0]


def child(chunk_id: str) -> Child:
    return Child(chunk_id, "parent", "work", f"text of {chunk_id}", "", f"text of {chunk_id}", {})


class EmbeddingStoreContract:
    def store(self) -> EmbeddingStore:
        raise NotImplementedError

    def filled(self) -> EmbeddingStore:
        store = self.store()
        store.add([child("near"), child("far")], [NEAR, FAR])
        return store

    def test_an_empty_store_holds_nothing(self) -> None:
        store = self.store()
        self.assertEqual((False, 0, set()), (store.present(), store.count(), store.ids()))

    def test_the_added_children_are_held_by_their_ids(self) -> None:
        store = self.filled()
        self.assertEqual((True, 2, {"near", "far"}), (store.present(), store.count(), store.ids()))

    def test_the_nearest_child_comes_first_within_the_limit(self) -> None:
        self.assertEqual(["near"], self.filled().nearest(NEAR, 1))

    def test_a_deleted_child_is_no_longer_held(self) -> None:
        store = self.filled()
        store.delete(["far"])
        self.assertEqual({"near"}, store.ids())

    def test_a_cleared_store_holds_nothing_and_records_no_model(self) -> None:
        store = self.filled()
        store.clear()
        self.assertEqual((0, None), (store.count(), store.recorded_model()))


class TestFakeEmbeddingStoreKeepsTheContract(EmbeddingStoreContract, unittest.TestCase):
    def store(self) -> EmbeddingStore:
        return FakeEmbeddingStore(MODEL)


if __name__ == "__main__":
    unittest.main()
