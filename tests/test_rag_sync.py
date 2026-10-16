from __future__ import annotations

import io
import json
import os
import unicodedata
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from _support import LiveTree

LiveTree.activate()

import rag
import search
import vault
from _rag.chroma import _Upsert as Upsert
from _rag_chunks import BASENAME, SOLE_AUTHOR_META
from _rag_fakes import FAKE_MODEL, CorpusStoreTestCase, FakeEmbedder, FakeEmbeddingStore, temp_directory

BODY = "# One\n\nBeing is the indeterminate immediate.\n\n# Two\n\n{second}\n"
CHILDREN_IN_BODY = 2
NEXT_VERSION = rag.CHUNKING_VERSION + 1
CONFIGURED_MODEL = "qwen3-embedding:4b"
OTHER_MODEL = "qwen3-embedding:8b"
ACCENTED = "Gödel - 1931 - Über Formal Unentscheidbare Sätze"
DECOMPOSED = unicodedata.normalize("NFD", ACCENTED)


class ReadRecordingDocuments(rag.IndexableDocuments):
    def __init__(self) -> None:
        self.reads: list[str] = []

    def loaded(self, path: Path) -> rag.IndexedDocument:
        self.reads.append(vault.basename_of(path))
        return super().loaded(path)


class SyncTestCase(CorpusStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.embeddings = FakeEmbeddingStore()
        self.embedder = FakeEmbedder()
        self.progress = io.StringIO()

    def path_of(self, basename: str = BASENAME) -> Path:
        return self.temp_vault.corpus / f"{basename}.md"

    def lines(self) -> list[str]:
        return self.progress.getvalue().splitlines()

    def write(self, second: str = "Nothing is the same.", basename: str = BASENAME) -> None:
        vault.write_frontmatter(self.path_of(basename), SOLE_AUTHOR_META, BODY.format(second=second))

    def index(self, documents: rag.IndexableDocuments | None = None,
              embedder: FakeEmbedder | None = None) -> rag.SearchIndex:
        return rag.SearchIndex(self.fulltext, self.embeddings, embedder or self.embedder,
                               documents or rag.IndexableDocuments())

    def sync(self, version: int = rag.CHUNKING_VERSION,
             documents: rag.IndexableDocuments | None = None) -> rag.StoreSync:
        return rag.StoreSync(index=self.index(documents), chunker=rag.ParentChildChunker(version=version),
                             progress=rag.SyncProgress(self.progress))

    def synced(self, version: int = rag.CHUNKING_VERSION, documents: rag.IndexableDocuments | None = None) -> dict:
        sync = self.sync(version, documents)
        sync.run()
        return sync.report()

    def rebuilt(self) -> dict:
        sync = self.sync()
        sync.rebuild()
        return sync.report()

    def status(self, embedder: FakeEmbedder | None = None) -> dict:
        return rag.IndexStatus(self.index(embedder=embedder)).report()


class TestSync(SyncTestCase):
    def test_the_report_is_empty_before_the_sync_runs(self) -> None:
        self.write()
        self.assertEqual({"changed": [], "skipped": [], "pruned": [], "unreadable": [],
                          "embedded_chunks": 0}, self.sync().report())

    def test_a_new_document_is_chunked_and_every_child_embedded(self) -> None:
        self.write()
        report = self.synced()
        self.assertEqual(([BASENAME], CHILDREN_IN_BODY, CHILDREN_IN_BODY),
                         (report["changed"], report["embedded_chunks"], self.embeddings.count()))

    def test_an_unchanged_document_is_skipped_without_embedding(self) -> None:
        self.write()
        self.synced()
        report = self.synced()
        self.assertEqual(([BASENAME], 0, 1), (report["skipped"], report["embedded_chunks"], len(self.embedder.batches)))

    def test_only_the_changed_chunk_is_re_embedded(self) -> None:
        self.write()
        self.synced()
        self.write(second="Nothing is now different.")
        report = self.synced()
        self.assertEqual(1, report["embedded_chunks"])
        self.assertIn("Two\nNothing is now different.", self.embedder.embedded_texts[-1])

    def test_every_embedded_text_opens_with_the_work_label(self) -> None:
        self.write()
        self.synced()
        self.assertTrue(all(text.startswith("Hegel, 1969, Wissenschaft der Logik\n")
                            for text in self.embedder.embedded_texts))

    def test_a_chunking_version_bump_re_chunks_an_unchanged_document(self) -> None:
        self.write()
        self.synced()
        report = self.synced(NEXT_VERSION)
        self.assertEqual(([BASENAME], []), (report["changed"], report["skipped"]))

    def test_a_chunking_version_bump_leaves_the_stores_consistent(self) -> None:
        self.write()
        self.synced()
        self.synced(NEXT_VERSION)
        self.assertEqual(self.fulltext.child_ids(), self.embeddings.ids())

    def test_the_stale_chunk_leaves_the_embedding_store(self) -> None:
        self.write()
        self.synced()
        self.write(second="Nothing is now different.")
        self.synced()
        self.assertEqual(self.fulltext.child_ids(), self.embeddings.ids())

    def test_a_deleted_document_is_pruned_from_both_stores(self) -> None:
        self.write()
        self.synced()
        self.path_of().unlink()
        report = self.synced()
        self.assertEqual(([BASENAME], 0, set()), (report["pruned"], self.embeddings.count(), self.fulltext.child_ids()))

    def test_a_document_under_a_decomposed_filename_is_skipped_not_pruned_on_the_next_sync(self) -> None:
        self.write(basename=DECOMPOSED)
        self.synced()
        report = self.synced()
        self.assertEqual(([ACCENTED], []), (report["skipped"], report["pruned"]))

    def test_a_rebuild_empties_the_stores_and_embeds_everything_again(self) -> None:
        self.write()
        self.synced()
        report = self.rebuilt()
        self.assertEqual((CHILDREN_IN_BODY, 2), (report["embedded_chunks"], len(self.embedder.batches)))

    def test_a_document_untouched_since_its_sync_is_not_read_again(self) -> None:
        self.write()
        self.synced()
        documents = ReadRecordingDocuments()
        self.assertEqual(([BASENAME], []), (self.synced(documents=documents)["skipped"], documents.reads))

    def test_a_changed_document_is_read_once(self) -> None:
        self.write()
        documents = ReadRecordingDocuments()
        self.synced(documents=documents)
        self.assertEqual([BASENAME], documents.reads)

    def test_a_touched_but_unchanged_document_is_skipped_and_restamped(self) -> None:
        self.write()
        self.synced()
        os.utime(self.path_of(), ns=(0, 0))
        report = self.synced()
        self.assertEqual(([BASENAME], rag.FileStamp.of(self.path_of())),
                         (report["skipped"], self.fulltext.manifest_row(BASENAME).record.stamp))

    def test_the_manifest_records_the_model_that_embedded_the_chunks(self) -> None:
        self.write()
        self.synced()
        self.assertEqual(FAKE_MODEL, self.fulltext.manifest_row(BASENAME).record.embedding_model)

    def test_an_interrupted_sync_does_not_embed_what_it_already_embedded(self) -> None:
        self.write()
        self.synced()
        self.fulltext.clear()
        report = self.synced()
        self.assertEqual((0, self.fulltext.child_ids()), (report["embedded_chunks"], self.embeddings.ids()))

    def test_each_document_is_reported_with_its_children_and_its_embeddings(self) -> None:
        self.write()
        self.synced()
        self.assertEqual([f"{BASENAME}: {CHILDREN_IN_BODY} children, {CHILDREN_IN_BODY} embedded"], self.lines())

    def test_a_skipped_document_and_a_pruned_one_are_each_reported(self) -> None:
        self.write()
        self.synced()
        self.synced()
        self.path_of().unlink()
        self.synced()
        self.assertEqual([f"{BASENAME}: unchanged", f"{BASENAME}: pruned"], self.lines()[1:])

    def test_the_stores_agree_after_a_sync(self) -> None:
        self.write()
        self.synced()
        report = self.status()
        self.assertEqual((True, []), (report["consistent"], report["stale_or_new"]))


class TestChangedEmbeddingModel(SyncTestCase):
    def synced_under_the_other_model(self) -> None:
        self.write()
        self.embeddings = FakeEmbeddingStore(model=OTHER_MODEL)
        self.embedder = FakeEmbedder(model=OTHER_MODEL)
        self.synced()
        self.embedder = FakeEmbedder(model=CONFIGURED_MODEL)

    def test_a_store_recorded_under_another_model_refuses_the_sync_naming_the_rebuild(self) -> None:
        self.synced_under_the_other_model()
        with self.assertRaisesRegex(rag.EmbeddingModelMismatch, "sync --rebuild"):
            self.synced()

    def test_a_refused_sync_leaves_the_manifest_under_the_recorded_model(self) -> None:
        self.synced_under_the_other_model()
        with self.assertRaises(rag.EmbeddingModelMismatch):
            self.synced()
        self.assertEqual(OTHER_MODEL, self.fulltext.manifest_row(BASENAME).record.embedding_model)

    def test_a_rebuild_under_the_new_model_is_not_refused(self) -> None:
        self.synced_under_the_other_model()
        self.assertEqual([BASENAME], self.rebuilt()["changed"])


class RefusingSync:
    def __init__(self, **_collaborators) -> None:
        pass

    def run(self) -> None:
        raise rag.EmbeddingModelMismatch("vectors from A, B is configured -- run `search.py sync --rebuild`")


class TestSyncCommand(unittest.TestCase):
    def test_a_refused_sync_exits_one_with_the_refusal_as_the_error(self) -> None:
        printed = io.StringIO()
        with patch.object(rag, "StoreSync", RefusingSync), patch.object(vault, "ensure_dirs", lambda: None):
            with redirect_stdout(printed):
                status = search.SearchCli().run(["sync"])
        self.assertEqual((1, "vectors from A, B is configured -- run `search.py sync --rebuild`"),
                         (status, json.loads(printed.getvalue())["error"]))


class TestStatus(SyncTestCase):
    def test_an_unsynced_document_is_listed_as_stale(self) -> None:
        self.write()
        self.assertEqual([BASENAME], self.status()["stale_or_new"])

    def test_a_document_synced_under_another_chunking_version_is_listed_as_stale(self) -> None:
        self.write()
        self.synced(NEXT_VERSION)
        self.assertEqual([BASENAME], self.status()["stale_or_new"])

    def test_a_missing_vector_makes_the_stores_inconsistent(self) -> None:
        self.write()
        self.synced()
        self.embeddings.delete([self.fulltext.chunk_ids_of(BASENAME)[0]])
        self.assertIn("sync --rebuild", self.status()["inconsistency"])

    def test_an_absent_embedding_store_reports_a_null_count(self) -> None:
        self.assertIsNone(self.status()["chroma_chunk_count"])


class TestReportedModels(SyncTestCase):
    def report(self, recorded: str | None) -> dict:
        self.write()
        self.embeddings = FakeEmbeddingStore(model=recorded)
        self.embedder = FakeEmbedder(model=recorded or FAKE_MODEL)
        self.synced()
        return self.status(embedder=FakeEmbedder(model=CONFIGURED_MODEL))

    def test_the_report_names_the_configured_and_the_recorded_model(self) -> None:
        report = self.report(CONFIGURED_MODEL)
        self.assertEqual((CONFIGURED_MODEL, CONFIGURED_MODEL),
                         (report["embedding_model"], report["recorded_embedding_model"]))

    def test_a_store_built_under_another_model_is_an_inconsistency(self) -> None:
        report = self.report(OTHER_MODEL)
        self.assertEqual(False, report["consistent"])
        self.assertIn("sync --rebuild", report["inconsistency"])

    def test_a_store_that_records_no_model_is_reported_unrecorded(self) -> None:
        report = self.report(None)
        self.assertEqual((True, "unrecorded"), (report["consistent"], report["recorded_embedding_model"]))


class RecordingCollection:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def upsert(self, ids: list[str], embeddings: list[list[float]], documents: list[str],
               metadatas: list[dict]) -> None:
        self.batch_sizes.append(len(ids))


class TestChromaStore(unittest.TestCase):
    VECTORS = [[1.0, 0.0], [0.0, 1.0]]

    def setUp(self) -> None:
        self.directory = temp_directory(self) / "chroma"
        self.store = self.opened(CONFIGURED_MODEL)
        body = BODY.format(second="Nothing.")
        document = rag.IndexedDocument(BASENAME, Path(f"{BASENAME}.md"), SOLE_AUTHOR_META, body)
        self.children = list(rag.ParentChildChunker().chunked(document).children)

    def opened(self, model: str) -> rag.EmbeddingStore:
        return rag.EmbeddingStore(self.directory, rag.MachineSettings({"embedding_model": model}))

    def test_the_store_is_absent_before_the_first_write(self) -> None:
        self.assertFalse(self.store.present())

    def test_added_vectors_are_counted(self) -> None:
        self.store.add(self.children, self.VECTORS)
        self.assertEqual(CHILDREN_IN_BODY, self.store.count())

    def test_added_vectors_are_ranked_by_nearness(self) -> None:
        self.store.add(self.children, self.VECTORS)
        self.assertEqual(self.children[1].chunk_id, self.store.nearest([0.1, 0.9], 2)[0])

    def test_the_collection_records_the_model_that_built_it(self) -> None:
        self.store.add(self.children, self.VECTORS)
        self.assertEqual(CONFIGURED_MODEL, self.opened(OTHER_MODEL).recorded_model())

    def test_adding_under_another_model_refuses_and_names_the_rebuild(self) -> None:
        self.store.add(self.children, self.VECTORS)
        with self.assertRaisesRegex(rag.EmbeddingModelMismatch, "sync --rebuild"):
            self.opened(OTHER_MODEL).add(self.children, self.VECTORS)

    def test_an_upsert_is_split_into_batches_no_larger_than_the_client_allows(self) -> None:
        collection = RecordingCollection()
        Upsert(2).into(collection, self.children * 3, [[1.0, 0.0]] * 6)
        self.assertEqual([2, 2, 2], collection.batch_sizes)

    def test_deleting_removes_the_named_vectors(self) -> None:
        self.store.add(self.children, self.VECTORS)
        self.store.delete([self.children[0].chunk_id])
        self.assertEqual({self.children[1].chunk_id}, self.store.ids())

    def test_clearing_removes_the_store(self) -> None:
        self.store.add(self.children, self.VECTORS)
        self.store.clear()
        self.assertFalse(self.store.present())


if __name__ == "__main__":
    unittest.main()
