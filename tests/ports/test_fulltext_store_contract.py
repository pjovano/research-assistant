from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _port_fakes import FakeFullTextStore
from _ports.compute import FullTextStore
from _rag.chunking import Child, ChunkedDocument, Parent
from _rag.documents import FileStamp
from _rag.fulltext import FullTextStore as SqliteFullTextStore
from _rag.fulltext import ManifestRecord
from _rag_fakes import temp_directory

WORK = "work"
OTHER_WORK = "other work"
RECORD = ManifestRecord("hash-one", "placeholder-embedding", FileStamp(11, 22))
RESTAMPED = ManifestRecord("hash-one", "placeholder-embedding", FileStamp(33, 44))
BEING = "Being passes into nothing."
ESSENCE = "Essence is reflection."


def chunked(basename: str, texts: tuple[str, ...]) -> ChunkedDocument:
    parent = Parent(f"{basename}::parent", basename, " ".join(texts), {})
    children = tuple(Child(f"{basename}::{index}", parent.parent_id, basename, text, "", text, {})
                     for index, text in enumerate(texts))
    return ChunkedDocument((parent,), children)


class FullTextStoreContract:
    def store(self) -> FullTextStore:
        raise NotImplementedError

    def filled(self) -> FullTextStore:
        store = self.store()
        store.replace_document(WORK, chunked(WORK, (BEING, ESSENCE)), RECORD)
        return store

    def test_an_empty_store_holds_no_document(self) -> None:
        store = self.store()
        self.assertEqual(([], None, []), (store.manifest_basenames(), store.document_hash(WORK),
                                          store.bm25_ranked("being", 5)))

    def test_a_replaced_document_is_listed_with_its_hash_and_chunk_ids(self) -> None:
        store = self.filled()
        self.assertEqual(([WORK], "hash-one", [f"{WORK}::0", f"{WORK}::1"]),
                         (store.manifest_basenames(), store.document_hash(WORK), store.chunk_ids_of(WORK)))

    def test_the_child_holding_the_query_term_is_ranked_and_the_other_is_not(self) -> None:
        self.assertEqual([f"{WORK}::0"], self.filled().bm25_ranked("nothing", 5))

    def test_the_children_and_parents_are_read_by_their_ids(self) -> None:
        store = self.filled()
        child_texts = [row["text"] for row in store.children([f"{WORK}::1"])]
        parent_ids = [row["parent_id"] for row in store.parents([f"{WORK}::parent"])]
        self.assertEqual(([ESSENCE], [f"{WORK}::parent"]), (child_texts, parent_ids))

    def test_the_child_ids_and_the_children_by_id_agree(self) -> None:
        store = self.filled()
        self.assertEqual(store.child_ids(), set(store.children_by_id(sorted(store.child_ids()))))

    def test_the_counts_name_the_parents_the_children_and_the_documents(self) -> None:
        self.assertEqual({"parents": 1, "children": 2, "manifest": 1}, self.filled().counts())

    def test_a_restamped_document_carries_its_new_record(self) -> None:
        store = self.filled()
        store.restamp_document(WORK, RESTAMPED)
        self.assertEqual(RESTAMPED, store.manifest_row(WORK).record)

    def test_a_removed_document_leaves_the_others(self) -> None:
        store = self.filled()
        store.replace_document(OTHER_WORK, chunked(OTHER_WORK, (BEING,)), RECORD)
        store.remove_document(WORK)
        self.assertEqual(([OTHER_WORK], []), (store.manifest_basenames(), store.chunk_ids_of(WORK)))

    def test_a_cleared_store_holds_no_document(self) -> None:
        store = self.filled()
        store.clear()
        self.assertEqual(([], set()), (store.manifest_rows(), store.child_ids()))


class TestFakeFullTextStoreKeepsTheContract(FullTextStoreContract, unittest.TestCase):
    def store(self) -> FullTextStore:
        return FakeFullTextStore()


class TestTheSqliteFullTextStoreKeepsTheContract(FullTextStoreContract, unittest.TestCase):
    def store(self) -> FullTextStore:
        return SqliteFullTextStore(temp_directory(self))


if __name__ == "__main__":
    unittest.main()
