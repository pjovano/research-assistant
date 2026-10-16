from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_backfill_driver import BackfillCase, StubScript
from test_extract_backfill_reading_chapters_of_doubtful_pages_from_pixels import retrial_case


def extractions(case: BackfillCase) -> int:
    return sum(call[0] == "extract" for call in case.script.calls)


class TestReadingsThePageReaderNeverWrote(unittest.TestCase):
    def test_a_listing_with_no_readings_file_asks_for_the_page_reader_again(self) -> None:
        case = retrial_case(self, StubScript())
        (case.work_dir / "readings-0.json").unlink()
        self.assertEqual(("unwritten", 0), (case.call("retrial")["state"], extractions(case)))

    def test_a_listing_beside_an_answered_one_with_no_readings_file_asks_for_the_page_reader_again(self) -> None:
        case = retrial_case(self, StubScript())
        case.put("doubtful-1.json", {"pages": [{"file_page": 20}]})
        self.assertEqual("unwritten", case.call("retrial")["state"])

    def test_empty_readings_ask_for_the_page_reader_again(self) -> None:
        case = retrial_case(self, StubScript())
        case.put("readings-0.json", [])
        self.assertEqual("unwritten", case.call("retrial")["state"])

    def test_a_malformed_readings_file_still_sets_the_work_aside(self) -> None:
        case = retrial_case(self, StubScript())
        (case.work_dir / "readings-0.json").write_text("not json")
        self.assertEqual("aside", case.call("retrial")["state"])


if __name__ == "__main__":
    unittest.main()
