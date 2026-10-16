from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import requests

from _support import LiveTree

LiveTree.activate()

import rag
from _rag.packing import CACHE_DIRECTORY_VARIABLE, ENCODING_NAME, TokenBudget

UNREACHABLE = requests.exceptions.ConnectionError("Tunnel connection failed: 403 Forbidden")


class TestAnEncodingThatCannotBeFetchedIsReportedByNameAndCache(unittest.TestCase):
    def setUp(self) -> None:
        with patch("tiktoken.get_encoding", side_effect=UNREACHABLE), \
                self.assertRaises(rag.TokenizerUnavailable) as raised:
            TokenBudget().count("Being is the indeterminate immediate.")
        self.message = str(raised.exception)

    def test_the_error_names_the_encoding(self) -> None:
        self.assertIn(ENCODING_NAME, self.message)

    def test_the_error_names_the_cache_directory(self) -> None:
        self.assertIn(os.environ[CACHE_DIRECTORY_VARIABLE], self.message)

    def test_the_error_says_the_encoding_is_fetched_once(self) -> None:
        self.assertIn("once", self.message)


if __name__ == "__main__":
    unittest.main()
