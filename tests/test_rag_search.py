from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from _support import PROJECT_ROOT, LiveTree

LiveTree.activate()

import rag
import vault
from _rag_chunks import BASENAME, SOLE_AUTHOR_META as META
from _rag_fakes import CorpusStoreTestCase, FakeEmbedder, FakeEmbeddingStore, FakeReranker, hashed_vector

OTHER_BASENAME = "Kant - 1781 - Kritik der reinen Vernunft"
BODY = ("# Being\n\nBeing is the indeterminate immediate.\n\nNothing is the same as pure being.\n\n"
        "# Essence\n\nEssence is reflected being.\n\n# Concept\n\nThe concept is free.\n")
RESULT_KEYS = {"parent_id", "basename", "heading_path", "folio_first", "folio_last", "file_page_first",
               "file_page_last", "time_first", "time_last", "text", "matched_start", "matched_end", "score",
               "citekey", "title"}
LIB_DIR = PROJECT_ROOT / "lib"
TOKEN_ENCODER_PROBE = f"import sys; sys.path.insert(0, {str(LIB_DIR)!r}); import rag; print('tiktoken' in sys.modules)"


def _rewritten_child() -> rag.ChunkedDocument:
    metadata = {"heading_path": "Essence"}
    parent = rag.Parent("p1", BASENAME, "Essence is reflected being.", metadata)
    child = rag.Child("c1", "p1", BASENAME, "Essence reflected", "Essence", "Essence reflected", metadata)
    return rag.ChunkedDocument((parent,), (child,))


class TestReciprocalRankFusion(unittest.TestCase):
    def test_a_chunk_in_both_rankings_outranks_one_in_either(self) -> None:
        fused = rag.ReciprocalRankFusion().fused([["a", "b"], ["c", "b"]])
        self.assertEqual("b", fused[0][0])

    def test_the_top_of_one_ranking_scores_one_over_the_offset(self) -> None:
        [(chunk_id, score)] = rag.ReciprocalRankFusion(offset=60).fused([["a"]])
        self.assertEqual(("a", 1.0 / 60), (chunk_id, score))

    def test_an_empty_fusion_yields_nothing(self) -> None:
        self.assertEqual([], rag.ReciprocalRankFusion().fused([[], []]))


class HybridSearchTestCase(CorpusStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.embeddings = FakeEmbeddingStore()
        self.embedder = FakeEmbedder()
        document = rag.IndexedDocument(BASENAME, Path(f"{BASENAME}.md"), META, BODY)
        self.chunked = rag.ParentChildChunker().chunked(document)
        self.fulltext.replace_document(BASENAME, self.chunked, rag.ManifestRecord.unstamped("hash"))
        children = list(self.chunked.children)
        self.embeddings.add(children, [hashed_vector(child.embedded_text) for child in children])

    def search(self, reranker: FakeReranker | None = None) -> rag.HybridSearch:
        return rag.HybridSearch(self._index(), reranker or FakeReranker())

    def fused_search(self, embedder: FakeEmbedder | None = None, embeddings: FakeEmbeddingStore | None = None,
                     documents: rag.IndexableDocuments | None = None) -> rag.HybridSearch:
        return rag.HybridSearch(self._index(embedder, embeddings, documents))

    def _index(self, embedder: FakeEmbedder | None = None, embeddings: FakeEmbeddingStore | None = None,
               documents: rag.IndexableDocuments | None = None) -> rag.SearchIndex:
        return rag.SearchIndex(self.fulltext, embeddings or self.embeddings, embedder or self.embedder,
                               documents or rag.IndexableDocuments())

    def child_with(self, fragment: str) -> rag.Child:
        return next(child for child in self.chunked.children if fragment in child.text)

    @staticmethod
    def matched(result: dict) -> str:
        return result["text"][result["matched_start"]:result["matched_end"]]


class TestHybridSearch(HybridSearchTestCase):
    def test_a_result_carries_exactly_the_result_keys(self) -> None:
        [first, *_] = self.search().results("essence reflected")
        self.assertEqual(RESULT_KEYS, set(first))

    def test_a_result_carries_the_parent_text_and_the_offsets_of_the_matched_child(self) -> None:
        [first, *_] = self.search().results("essence reflected")
        self.assertEqual(("Essence is reflected being.", "Essence"), (self.matched(first), first["heading_path"]))

    def test_the_query_vector_pulls_in_a_semantically_nearest_child(self) -> None:
        target = self.child_with("concept is free")
        embedder = FakeEmbedder(vectors={"liberty": hashed_vector(target.embedded_text)})
        results = self.fused_search(embedder=embedder).results("liberty")
        self.assertEqual("The concept is free.", self.matched(results[0]))

    def test_results_are_deduplicated_by_parent(self) -> None:
        results = self.fused_search().results("being")
        self.assertEqual(len(results), len({result["parent_id"] for result in results}))

    def test_k_caps_the_number_of_parents(self) -> None:
        self.assertEqual(1, len(self.fused_search().results("being essence concept", k=1)))

    def test_a_failing_embedder_leaves_a_keyword_only_warning(self) -> None:
        results = self.fused_search(embedder=FakeEmbedder(failing=True)).results("essence")
        self.assertIn("keyword-only", results[-1]["warning"])

    def test_an_unavailable_reranker_leaves_the_fused_order_with_a_warning(self) -> None:
        results = self.search(reranker=FakeReranker(cause="no gguf")).results("essence")
        self.assertEqual("reranker unavailable: no gguf; results are the fused hybrid ordering", results[-1]["warning"])

    def test_a_search_without_a_reranker_warns_of_nothing(self) -> None:
        results = self.fused_search().results("essence")
        self.assertFalse(any("warning" in result for result in results))

    def test_the_reranker_reorders_the_fused_candidates(self) -> None:
        reranker = FakeReranker(scores_by_fragment={"concept is free": 0.9, "Essence": 0.1})
        results = self.search(reranker=reranker).results("being essence concept")
        self.assertEqual("The concept is free.", self.matched(results[0]))

    def test_a_reranked_result_list_says_the_reranker_was_used(self) -> None:
        results = self.search(reranker=FakeReranker()).results("essence")
        self.assertIn("used", results[-1]["reranker"])

    def test_a_result_list_without_the_reranker_carries_no_used_note(self) -> None:
        results = self.search(reranker=FakeReranker(cause="no gguf")).results("essence")
        self.assertFalse(any("reranker" in result for result in results))

    def test_the_reranker_receives_the_embedded_text_of_each_candidate(self) -> None:
        reranker = FakeReranker(scores_by_fragment={"Essence\nEssence is reflected being.": 1.0})
        results = self.search(reranker=reranker).results("being essence concept")
        self.assertEqual(1.0, results[0]["score"])

    def test_a_query_matching_no_keyword_still_yields_the_nearest_vectors(self) -> None:
        self.assertEqual(3, len(self.fused_search().results("phenomenology")))

    def test_with_no_vectors_a_query_matching_no_keyword_yields_no_results(self) -> None:
        search = self.fused_search(embeddings=FakeEmbeddingStore())
        self.assertEqual([], search.results("phenomenology"))


class ListingCountingDocuments(rag.IndexableDocuments):
    def __init__(self) -> None:
        self.listings = 0

    def paths(self) -> list[Path]:
        self.listings += 1
        return super().paths()


class TestStaleCorpus(HybridSearchTestCase):
    def written(self, basename: str = BASENAME) -> Path:
        path = self.temp_vault.corpus / f"{basename}.md"
        vault.write_frontmatter(path, META, BODY)
        return path

    def index(self, path: Path) -> None:
        record = rag.ManifestRecord("hash", "model", rag.FileStamp.of(path))
        self.fulltext.replace_document(BASENAME, self.chunked, record)

    def warnings(self) -> list[str]:
        return [entry["warning"] for entry in self.fused_search().results("essence") if "warning" in entry]

    def test_an_indexed_and_untouched_corpus_file_raises_no_warning(self) -> None:
        self.index(self.written())
        self.assertEqual([], self.warnings())

    def test_a_corpus_file_that_was_never_indexed_is_warned_as_stale(self) -> None:
        self.written()
        self.assertIn(f"stale: {BASENAME}", self.warnings()[0])

    def test_a_corpus_file_changed_since_it_was_indexed_is_warned_as_stale(self) -> None:
        path = self.written()
        self.index(path)
        path.write_text(path.read_text() + "\n\nAn added paragraph.\n", encoding="utf-8")
        self.assertIn(f"stale: {BASENAME}", self.warnings()[0])

    def test_a_corpus_file_only_touched_is_warned_as_stale(self) -> None:
        path = self.written()
        self.index(path)
        os.utime(path, ns=(0, 0))
        self.assertIn(f"stale: {BASENAME}", self.warnings()[0])

    def test_the_corpus_is_listed_once_while_the_directory_and_the_manifest_are_unchanged(self) -> None:
        self.index(self.written())
        documents = ListingCountingDocuments()
        search = self.fused_search(documents=documents)
        search.results("essence")
        search.results("essence")
        self.assertEqual(1, documents.listings)

    def test_a_corpus_file_added_after_a_query_is_warned_as_stale_by_the_same_search(self) -> None:
        self.index(self.written())
        search = self.fused_search()
        search.results("essence")
        self.written(OTHER_BASENAME)
        warnings = [entry["warning"] for entry in search.results("essence") if "warning" in entry]
        self.assertIn(f"stale: {OTHER_BASENAME}", warnings[0])

    def test_a_sync_after_a_query_clears_the_stale_warning_of_the_same_search(self) -> None:
        path = self.written()
        search = self.fused_search()
        before = [entry for entry in search.results("essence") if "warning" in entry]
        self.index(path)
        after = [entry for entry in search.results("essence") if "warning" in entry]
        self.assertEqual((1, 0), (len(before), len(after)))


class TestMultipleQueries(HybridSearchTestCase):
    def test_a_list_of_queries_reaches_the_parents_of_every_query(self) -> None:
        results = self.fused_search().results(["essence reflected", "concept free"])
        matched = {self.matched(result) for result in results if "matched_start" in result}
        self.assertLessEqual({"Essence is reflected being.", "The concept is free."}, matched)

    def test_a_parent_matched_by_two_queries_appears_once(self) -> None:
        results = self.fused_search().results(["essence", "essence reflected"])
        self.assertEqual(len(results), len({result["parent_id"] for result in results}))

    def test_k_caps_the_parents_of_a_list_of_queries(self) -> None:
        self.assertEqual(1, len(self.fused_search().results(["being", "essence", "concept"], k=1)))

    def test_the_reranker_is_asked_once_with_the_queries_joined(self) -> None:
        reranker = FakeReranker()
        self.search(reranker=reranker).results(["being", "essence"])
        self.assertEqual(["being essence"], reranker.queries)

    def test_one_query_as_a_list_ranks_as_the_bare_string(self) -> None:
        bare = self.fused_search().results("essence reflected")
        listed = self.fused_search().results(["essence reflected"])
        self.assertEqual([entry["parent_id"] for entry in bare], [entry["parent_id"] for entry in listed])


class TestUnlocatedChild(CorpusStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.fulltext.replace_document(BASENAME, _rewritten_child(), rag.ManifestRecord.unstamped("hash"))

    def test_a_child_absent_from_its_parent_keeps_its_matched_text(self) -> None:
        index = rag.SearchIndex(self.fulltext, FakeEmbeddingStore(), FakeEmbedder(), rag.IndexableDocuments())
        [result] = rag.HybridSearch(index).results("reflected")
        self.assertEqual(("Essence reflected", "Essence is reflected being."), (result["matched"], result["text"]))


class TestFacade(unittest.TestCase):
    def test_every_exported_name_is_reachable(self) -> None:
        self.assertEqual([], [name for name in rag.__all__ if not hasattr(rag, name)])

    def test_importing_the_facade_loads_no_token_encoder(self) -> None:
        probe = subprocess.run([sys.executable, "-c", TOKEN_ENCODER_PROBE], capture_output=True, text=True,
                               env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual("False", probe.stdout.strip(), probe.stderr)

    def test_the_facade_exposes_the_search_layer_entry_points(self) -> None:
        expected = {"HybridSearch", "IndexStatus", "StoreSync", "ParentChildChunker", "FullTextStore",
                    "EmbeddingStore", "OllamaEmbedder", "LlamaReranker", "EmbeddingCheck", "EmbeddingUnavailable",
                    "RerankerUnavailable", "DEFAULT_RESULTS"}
        self.assertTrue(expected <= set(rag.__all__))


if __name__ == "__main__":
    unittest.main()
