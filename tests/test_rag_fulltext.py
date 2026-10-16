from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from _support import LiveTree

LiveTree.activate()

import rag
from _rag import fulltext
from _rag.fulltext import UNSTAMPED, fts_query
from _rag_chunks import BASENAME
from _rag_fakes import temp_directory

OTHER = "Aristotle - 1924 - Metaphysics"
HASH = "abc123"
RANK_LIMIT = 10
RECORD = rag.ManifestRecord(HASH, "qwen3-embedding:4b", rag.FileStamp(11, 22))
BODY = ("# Gamma\n\nτὸ ὂν λέγεται πολλαχῶς.\n\n# Delta\n\nBeing and becoming, being again.\n\n"
        "# Epsilon\n\nEssence and reflection.\n")
OTHER_BODY = "# Sein\n\nDas Sein ist das unbestimmte Unmittelbare.\n"
CONTEXT_ONLY = "Kant - 1781 - Kritik"
BODY_MATCH = "Hegel - 1812 - Logik"
PARENTS_DDL = ("CREATE TABLE parents(parent_id TEXT PRIMARY KEY, basename TEXT NOT NULL, text TEXT NOT NULL, "
               "metadata TEXT NOT NULL);")
MANIFEST_DDL = "CREATE TABLE manifest(basename TEXT PRIMARY KEY, chunk_ids TEXT NOT NULL, document_hash TEXT NOT NULL);"
MANIFEST_ROW = f"INSERT INTO manifest VALUES ('{BASENAME}', '[\"{BASENAME}::0\"]', 'old');"
PREVIOUS_SCHEMA = f"""
{PARENTS_DDL}
CREATE TABLE children(chunk_id TEXT PRIMARY KEY, parent_id TEXT NOT NULL, basename TEXT NOT NULL,
    text TEXT NOT NULL, metadata TEXT NOT NULL);
CREATE VIRTUAL TABLE children_fts USING fts5(text, content='children', content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 0');
{MANIFEST_DDL}
INSERT INTO children VALUES ('{BASENAME}::0', 'p', '{BASENAME}', 'Being.', '{{}}');
INSERT INTO children_fts(rowid, text) SELECT rowid, text FROM children;
{MANIFEST_ROW}
"""
VERSION_ONE_SCHEMA = f"""
{PARENTS_DDL}
CREATE TABLE children(chunk_id TEXT PRIMARY KEY, parent_id TEXT NOT NULL, basename TEXT NOT NULL,
    text TEXT NOT NULL, context TEXT NOT NULL DEFAULT '', metadata TEXT NOT NULL);
CREATE VIRTUAL TABLE children_fts USING fts5(text, context, content='children', content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 0');
{MANIFEST_DDL}
INSERT INTO children VALUES ('{BASENAME}::0', 'p', '{BASENAME}', 'Being.', 'Logik', '{{}}');
INSERT INTO children_fts(rowid, text, context) SELECT rowid, text, context FROM children;
{MANIFEST_ROW}
PRAGMA user_version = 1;
"""


def chunked(basename: str, body: str) -> rag.ChunkedDocument:
    document = rag.IndexedDocument(basename, Path(f"{basename}.md"), {"title": basename}, body)
    return rag.ParentChildChunker().chunked(document)


class FullTextStoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.store = rag.FullTextStore(temp_directory(self))
        self.chunked = chunked(BASENAME, BODY)
        self.store.replace_document(BASENAME, self.chunked, RECORD)

    def first_hit_text(self, query: str) -> str:
        [chunk_id, *_] = self.store.bm25_ranked(query, RANK_LIMIT)
        [child] = self.store.children([chunk_id])
        return child["text"]


class TestRoundTrip(FullTextStoreTestCase):
    def test_the_parents_and_children_are_stored(self) -> None:
        stored = self.store.stored_of(BASENAME)
        self.assertEqual((len(self.chunked.parents), len(self.chunked.children)),
                         (len(stored["parents"]), len(stored["children"])))

    def test_the_metadata_is_read_back_as_a_dict(self) -> None:
        [child] = self.store.children(self.chunked.chunk_ids[:1])
        self.assertEqual("Gamma", child["metadata"]["heading_path"])

    def test_children_by_id_keys_each_row_by_its_chunk_id(self) -> None:
        children = self.store.children_by_id(self.chunked.chunk_ids)
        self.assertEqual(set(self.chunked.chunk_ids), {child["chunk_id"] for child in children.values()})
        self.assertEqual(set(self.chunked.chunk_ids), set(children))

    def test_the_manifest_records_the_hash_and_the_chunk_ids(self) -> None:
        self.assertEqual((HASH, self.chunked.chunk_ids),
                         (self.store.document_hash(BASENAME), self.store.chunk_ids_of(BASENAME)))

    def test_an_unknown_basename_has_no_hash_and_no_chunk_ids(self) -> None:
        self.assertEqual((None, []), (self.store.document_hash("nobody"), self.store.chunk_ids_of("nobody")))

    def test_replacing_a_document_leaves_no_duplicate_rows(self) -> None:
        self.store.replace_document(BASENAME, self.chunked, RECORD)
        self.assertEqual(len(self.chunked.children), self.store.counts()["children"])

    def test_removing_a_document_empties_its_rows_and_its_index(self) -> None:
        self.store.remove_document(BASENAME)
        self.assertEqual(({"parents": 0, "children": 0, "manifest": 0}, []),
                         (self.store.counts(), self.store.bm25_ranked("being", RANK_LIMIT)))

    def test_clear_empties_every_table(self) -> None:
        self.store.clear()
        self.assertEqual(set(), self.store.child_ids() | self.store.manifest_chunk_ids())


class TestBm25Ranking(FullTextStoreTestCase):
    def test_the_denser_chunk_ranks_first(self) -> None:
        self.assertIn("being again", self.first_hit_text("being"))

    def test_a_term_absent_from_the_store_ranks_nothing(self) -> None:
        self.assertEqual([], self.store.bm25_ranked("phenomenology", RANK_LIMIT))

    def test_a_greek_query_finds_the_greek_chunk(self) -> None:
        self.assertIn("πολλαχῶς", self.first_hit_text("ὂν"))

    def test_a_query_with_fts_syntax_characters_does_not_raise(self) -> None:
        self.assertEqual([], self.store.bm25_ranked('"Sein: (und) -Zeit" OR NOT *', RANK_LIMIT))

    def test_the_limit_caps_the_ranking(self) -> None:
        self.assertEqual(1, len(self.store.bm25_ranked("being essence", 1)))

    def test_a_second_document_is_searchable_beside_the_first(self) -> None:
        self.store.replace_document(OTHER, chunked(OTHER, OTHER_BODY), RECORD)
        self.assertIn("Unmittelbare", self.first_hit_text("unbestimmte"))


class TestContextColumn(FullTextStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.store.replace_document(CONTEXT_ONLY, chunked(CONTEXT_ONLY, "# One\n\nReason.\n"), RECORD)
        self.store.replace_document(BODY_MATCH, chunked(BODY_MATCH, "# Two\n\nKant replies to reason.\n"), RECORD)

    def test_the_context_is_stored_beside_the_text(self) -> None:
        [child] = self.store.stored_of(CONTEXT_ONLY)["children"]
        self.assertEqual((f"{CONTEXT_ONLY}\nOne", "Reason."), (child["context"], child["text"]))

    def test_a_query_naming_a_work_reaches_its_chunks_through_the_context(self) -> None:
        self.assertEqual("Reason.", self.first_hit_text("Kritik"))

    def test_a_body_match_outranks_a_match_in_the_context_alone(self) -> None:
        self.assertEqual("Kant replies to reason.", self.first_hit_text("Kant"))

    def test_the_context_weighs_less_than_the_text(self) -> None:
        self.assertLess(rag.CONTEXT_WEIGHT, 1.0)


class UpgradeTestCase(unittest.TestCase):
    SCHEMA = ""

    def setUp(self) -> None:
        self.directory = temp_directory(self)
        with sqlite3.connect(self.directory / "fulltext.sqlite") as previous:
            previous.executescript(self.SCHEMA)
        self.store = rag.FullTextStore(self.directory)


class TestSchemaUpgrade(UpgradeTestCase):
    SCHEMA = PREVIOUS_SCHEMA

    def test_a_store_of_the_previous_schema_keeps_its_manifest(self) -> None:
        self.assertEqual("old", self.store.document_hash(BASENAME))

    def test_a_store_of_the_previous_schema_gains_an_empty_context(self) -> None:
        [child] = self.store.children([f"{BASENAME}::0"])
        self.assertEqual("", child["context"])

    def test_a_store_of_the_previous_schema_accepts_a_document_after_opening(self) -> None:
        self.store.replace_document(BASENAME, chunked(BASENAME, BODY), RECORD)
        self.assertIn("being again", self.store.children(self.store.bm25_ranked("being", 1))[0]["text"])


class TestManifestUpgrade(UpgradeTestCase):
    SCHEMA = VERSION_ONE_SCHEMA

    def test_a_version_one_store_keeps_its_manifest(self) -> None:
        row = self.store.manifest_row(BASENAME)
        self.assertEqual(("old", [f"{BASENAME}::0"]), (row.record.document_hash, row.chunk_ids))

    def test_a_version_one_row_carries_no_model_and_an_unstamped_file(self) -> None:
        record = self.store.manifest_row(BASENAME).record
        self.assertEqual(("", rag.FileStamp(UNSTAMPED, UNSTAMPED)), (record.embedding_model, record.stamp))

    def test_a_version_one_store_accepts_a_stamped_document_after_opening(self) -> None:
        self.store.replace_document(BASENAME, chunked(BASENAME, BODY), RECORD)
        self.assertEqual(RECORD, self.store.manifest_row(BASENAME).record)

    def test_restamping_leaves_the_hash_and_the_chunk_ids(self) -> None:
        self.store.restamp_document(BASENAME, RECORD)
        row = self.store.manifest_row(BASENAME)
        self.assertEqual(("old", RECORD.stamp, [f"{BASENAME}::0"]),
                         (row.record.document_hash, row.record.stamp, row.chunk_ids))


class TestAbsentStore(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = temp_directory(self) / "rag"
        self.store = rag.FullTextStore(self.directory)

    def test_reading_an_absent_store_answers_empty(self) -> None:
        answers = (self.store.manifest_basenames(), self.store.bm25_ranked("being", 5), self.store.child_ids())
        self.assertEqual(([], [], set()), answers)

    def test_reading_an_absent_store_creates_no_file(self) -> None:
        self.store.manifest_basenames()
        self.assertFalse(self.directory.exists())

    def test_the_first_write_creates_the_store(self) -> None:
        self.store.replace_document(BASENAME, chunked(BASENAME, BODY), RECORD)
        self.assertTrue(self.store.present())

    def test_repeated_reads_of_an_absent_store_build_the_empty_schema_once(self) -> None:
        with patch.object(fulltext, "_opened", wraps=fulltext._opened) as opened:
            self.store.manifest_basenames()
            self.store.child_ids()
        self.assertEqual(1, opened.call_count)

    def test_a_store_written_after_an_empty_read_is_read_back(self) -> None:
        self.store.manifest_basenames()
        self.store.replace_document(BASENAME, chunked(BASENAME, BODY), RECORD)
        self.assertEqual([BASENAME], self.store.manifest_basenames())


class TestFtsQuery(unittest.TestCase):
    def test_each_term_is_quoted_and_any_term_may_match(self) -> None:
        self.assertEqual('"Sein" OR "und" OR "Zeit"', fts_query("Sein: (und) -Zeit"))

    def test_an_empty_query_yields_no_match_expression(self) -> None:
        self.assertEqual("", fts_query("..."))


if __name__ == "__main__":
    unittest.main()
