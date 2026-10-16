from __future__ import annotations

import json
import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import vault

from _extract.records import ExtractionRecord, ExtractionRecords, RecordsFileCorrupt
from _extract.request import ExtractionRequest
from _vaults import TempVault

BASENAME = "Doe - 2020 - A Work"
OTHER_BASENAME = "Roe - 2021 - Another"
LATE_BASENAME = "Poe - 2022 - A Late Arrival"
SPANS = (("1", "3"),)
TODAY = "2026-09-24"


def record_of(spans: tuple) -> ExtractionRecord:
    return ExtractionRecord(ExtractionRequest(spans), None, TODAY)


class RecordsVaultTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.records = ExtractionRecords()
        self.records.write(OTHER_BASENAME, record_of(()))

    def library_names(self) -> list[str]:
        return sorted(path.name for path in vault.LIBRARY_DIR.iterdir())


class AnotherWriter:
    def __init__(self, records: ExtractionRecords) -> None:
        self._records = records
        self._real_loads = json.loads
        self._fired = False

    def loads(self, text: str, **kwargs) -> object:
        parsed = self._real_loads(text, **kwargs)
        if not self._fired:
            self._fired = True
            self._write_late_record(parsed)
        return parsed

    def _write_late_record(self, parsed: dict) -> None:
        entries = {**parsed, LATE_BASENAME: record_of(()).stored()}
        self._records.path.write_text(json.dumps(entries), encoding="utf-8")


class TestARecordsFileAnotherWriterChangesBetweenTheReadAndTheWrite(RecordsVaultTestCase):
    def test_both_writers_records_are_kept(self) -> None:
        with mock.patch("_extract.records.json.loads", AnotherWriter(self.records).loads):
            self.records.write(BASENAME, record_of(SPANS))
        self.assertEqual({BASENAME, OTHER_BASENAME, LATE_BASENAME},
                         set(json.loads(self.records.path.read_text(encoding="utf-8"))))


class TestARecordsFileWriteInterruptedBeforeItReachesTheDisk(RecordsVaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.before = self.records.path.read_bytes()
        with mock.patch("os.fsync", side_effect=OSError("disk full")), self.assertRaises(OSError):
            self.records.write(BASENAME, record_of(SPANS))

    def test_the_earlier_records_stay_whole(self) -> None:
        self.assertEqual(self.before, self.records.path.read_bytes())

    def test_no_partial_file_is_left_in_the_library(self) -> None:
        self.assertEqual([self.records.path.name], self.library_names())


class TestACorruptRecordsFile(RecordsVaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.records.path.write_text('{"truncated": ', encoding="utf-8")

    def test_a_read_is_refused_naming_the_file(self) -> None:
        with self.assertRaisesRegex(RecordsFileCorrupt, str(self.records.path)):
            self.records.entry(BASENAME)

    def test_a_write_is_refused_and_leaves_the_file_as_it_was(self) -> None:
        with self.assertRaises(RecordsFileCorrupt):
            self.records.write(BASENAME, record_of(SPANS))
        self.assertEqual('{"truncated": ', self.records.path.read_text(encoding="utf-8"))

    def test_a_file_holding_json_other_than_an_object_is_refused(self) -> None:
        self.records.path.write_text("[]", encoding="utf-8")
        with self.assertRaises(RecordsFileCorrupt):
            self.records.entry(BASENAME)


if __name__ == "__main__":
    unittest.main()
