from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from _support import LiveTree

LiveTree.activate()

import rag
import search
import vault
from _rag_fakes import CorpusStoreTestCase, FakeEmbedder, FakeEmbeddingStore

READABLE_BEFORE = "Doe - 2020 - A Work"
UNREADABLE = "Moe - 2021 - Broken"
READABLE_AFTER = "Roe - 2022 - Later Work"
GONE = "Zoe - 1999 - Removed Work"
READABLE_NOTE = ("---\ntitle: {title}\nauthor: [Doe]\nyear: 2020\n---\n\n"
                 "# One\n\nBeing is the indeterminate immediate.\n")
BROKEN_NOTE = "---\ntitle: [unclosed\nyear: 2021\n---\n\n# One\n\nNothing is the same as pure being.\n"


class WordBudget:
    def count(self, text: str) -> int:
        return len(text.split())


class SyncOverAnUnreadableNoteTestCase(CorpusStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write(READABLE_BEFORE, READABLE_NOTE.format(title="A Work"))
        self.write(UNREADABLE, BROKEN_NOTE)
        self.write(READABLE_AFTER, READABLE_NOTE.format(title="Later Work"))
        self.fulltext.replace_document(GONE, rag.ChunkedDocument((), ()), rag.ManifestRecord.unstamped("hash"))
        index = rag.SearchIndex(self.fulltext, FakeEmbeddingStore(), FakeEmbedder(), rag.IndexableDocuments())
        self.sync = rag.StoreSync(index, rag.ParentChildChunker(WordBudget()), rag.SyncProgress(io.StringIO()))
        self.sync.run()

    def write(self, basename: str, text: str) -> None:
        (vault.CORPUS_DIR / f"{basename}.md").write_text(text, encoding="utf-8")


class TestSyncSkipsANoteWithUnreadableFrontmatterAndFinishesTheRest(SyncOverAnUnreadableNoteTestCase):
    def test_every_readable_note_is_synced(self) -> None:
        self.assertEqual([READABLE_BEFORE, READABLE_AFTER], self.sync.report()["changed"])

    def test_the_unreadable_note_is_reported_by_name(self) -> None:
        self.assertEqual([UNREADABLE], [row["basename"] for row in self.sync.report()["unreadable"]])

    def test_a_note_no_longer_held_is_still_pruned(self) -> None:
        self.assertEqual([GONE], self.sync.report()["pruned"])


class ReportingSync:
    def __init__(self, **_collaborators) -> None:
        pass

    def run(self) -> None:
        pass

    def report(self) -> dict:
        return {"changed": [], "skipped": [], "pruned": [], "embedded_chunks": 0,
                "unreadable": [{"basename": UNREADABLE, "error": "while parsing a flow sequence"}]}


class TestASyncThatSkippedAnUnreadableNoteExitsNonZero(unittest.TestCase):
    def test_the_sync_command_exits_one(self) -> None:
        with patch.object(rag, "StoreSync", ReportingSync), patch.object(vault, "ensure_dirs", lambda: None):
            with redirect_stdout(io.StringIO()) as printed:
                status = search.SearchCli().run(["sync"])
        self.assertEqual((1, UNREADABLE), (status, json.loads(printed.getvalue())["unreadable"][0]["basename"]))


if __name__ == "__main__":
    unittest.main()
