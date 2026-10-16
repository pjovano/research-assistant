from __future__ import annotations

import importlib.util
import sys
import unittest

from _support import SKILLS_DIR, LiveTree

LiveTree.activate()

import rag
import search
from _vaults import TempVault

SERVER_PATH = SKILLS_DIR / "search" / "server.py"
UNHELD = "Nobody - 1999 - Nothing"


class SearchServerModule:
    @staticmethod
    def loaded():
        spec = importlib.util.spec_from_file_location("entry_search_server_error_key", SERVER_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module


class TestTheErrorKeyHasOneHome(unittest.TestCase):
    def test_the_search_cli_reports_errors_under_the_key_rag_defines(self) -> None:
        self.assertIs(rag.ERROR_KEY, search.ERROR_KEY)

    def test_the_search_server_reports_errors_under_the_key_rag_defines(self) -> None:
        self.assertIs(rag.ERROR_KEY, SearchServerModule.loaded().ERROR_KEY)


class TestTheOutlineOfAnUnheldWorkIsReportedUnderTheErrorKey(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)

    def test_an_unheld_basename_is_reported_under_the_error_key(self) -> None:
        self.assertEqual([rag.ERROR_KEY], list(rag.CorpusOutline.of(UNHELD)))


if __name__ == "__main__":
    unittest.main()
