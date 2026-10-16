from __future__ import annotations

import json
import unicodedata
import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.records import ExtractionRecord, ExtractionRecords
from _extract.request import ExtractionRequest
from _vaults import TempVault

COMPOSED_BASENAME = unicodedata.normalize("NFC", "Égré et al. - 2019 - The Sorites Paradox")
DECOMPOSED_BASENAME = unicodedata.normalize("NFD", COMPOSED_BASENAME)
OTHER_BASENAME = "Kant - 1998 - Critique of Pure Reason"
REVIEWED = "2026-09-28"


class TestARecordKeyedInADecomposedUnicodeForm(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.records = ExtractionRecords()
        self.records.path.parent.mkdir(parents=True, exist_ok=True)
        stored = {DECOMPOSED_BASENAME: {**ExtractionRequest(()).stored(), "reviewed": REVIEWED}}
        self.records.path.write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")

    def test_is_found_under_the_composed_basename(self) -> None:
        self.assertEqual(REVIEWED, self.records.reviewed(COMPOSED_BASENAME))

    def test_is_found_under_the_decomposed_basename(self) -> None:
        self.assertEqual(REVIEWED, self.records.reviewed(DECOMPOSED_BASENAME))

    def test_is_stored_composed_once_another_record_is_written(self) -> None:
        self.records.write(OTHER_BASENAME, ExtractionRecord(ExtractionRequest(())))
        keys = set(json.loads(self.records.path.read_text(encoding="utf-8")))
        self.assertEqual({COMPOSED_BASENAME, OTHER_BASENAME}, keys)

    def test_rewritten_for_the_same_work_leaves_one_record(self) -> None:
        self.records.write(COMPOSED_BASENAME, ExtractionRecord(ExtractionRequest(()), None, REVIEWED))
        self.assertEqual(1, len(json.loads(self.records.path.read_text(encoding="utf-8"))))


if __name__ == "__main__":
    unittest.main()
