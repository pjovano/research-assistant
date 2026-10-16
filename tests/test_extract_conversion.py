from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _extract.build import FreshConversionCache, PageConversion


class RecordingEngine:
    def __init__(self) -> None:
        self.converted: list[list[int]] = []

    def convert(self, _pdf_path: Path, file_pages: list[int]) -> dict:
        self.converted.append(file_pages)
        return {"pages": file_pages}


class DictCache:
    def __init__(self, held: dict | None = None) -> None:
        self.held = held or {}

    def missing(self, file_pages: list[int]) -> list[int]:
        return [] if tuple(file_pages) in self.held else list(file_pages)

    def load(self, file_pages: list[int]) -> dict | None:
        return self.held.get(tuple(file_pages))

    def save(self, file_pages: list[int], payload: dict) -> None:
        self.held[tuple(file_pages)] = payload


class TestPageConversion(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = RecordingEngine()
        self.cache = DictCache()

    def test_a_cached_payload_is_returned_without_converting(self) -> None:
        cache = DictCache({(1, 2): {"cached": True}})
        self.assertEqual({"cached": True}, PageConversion(Path("a.pdf"), self.engine, cache).payload([1, 2]))
        self.assertEqual([], self.engine.converted)

    def test_a_cache_miss_converts(self) -> None:
        payload = PageConversion(Path("a.pdf"), self.engine, self.cache).payload([1, 2])
        self.assertEqual({"pages": [1, 2]}, payload)

    def test_a_cache_miss_saves_the_conversion(self) -> None:
        PageConversion(Path("a.pdf"), self.engine, self.cache).payload([1, 2])
        self.assertEqual({(1, 2): {"pages": [1, 2]}}, self.cache.held)

    def test_a_fresh_conversion_ignores_the_cache_but_still_saves(self) -> None:
        cache = DictCache({(1,): {"stale": True}})
        payload = PageConversion(Path("a.pdf"), self.engine, FreshConversionCache(cache)).payload([1])
        self.assertEqual(({"pages": [1]}, {(1,): {"pages": [1]}}), (payload, cache.held))


if __name__ == "__main__":
    unittest.main()
