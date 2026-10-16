from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import rag
from _rag_fakes import CorpusStoreTestCase

BASENAME = "Doe - 2020 - A Work"


class TestTheFullTextStoreCountsTheRowsOfEachTable(CorpusStoreTestCase):
    def test_a_document_with_no_chunks_counts_one_manifest_row_and_no_chunk(self) -> None:
        self.fulltext.replace_document(BASENAME, rag.ChunkedDocument((), ()), rag.ManifestRecord.unstamped("hash"))
        self.assertEqual({"parents": 0, "children": 0, "manifest": 1}, self.fulltext.counts())


if __name__ == "__main__":
    unittest.main()
