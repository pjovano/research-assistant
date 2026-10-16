from __future__ import annotations

import unittest
from http import HTTPStatus

from _support import LiveTree

LiveTree.activate()

from _file.resolvers import ArxivResolver, Fetched, LookupFailed

ARXIV_ID = "2101.00001"


class UrlRecorder:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def fetch(self, url: str) -> Fetched:
        self.urls.append(url)
        return Fetched(HTTPStatus.NOT_FOUND, "")


class TestTheArxivLookup(unittest.TestCase):
    def test_the_query_is_sent_over_https(self) -> None:
        recorder = UrlRecorder()
        with self.assertRaises(LookupFailed):
            ArxivResolver(recorder).resolve(ARXIV_ID)
        self.assertTrue(recorder.urls[0].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
