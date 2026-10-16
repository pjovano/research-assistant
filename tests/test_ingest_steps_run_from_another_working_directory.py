from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _ingest_home import EXTRACT, INGEST, QUEUED_WORK, TemporaryHome


class IngestStepsRunFromAnotherWorkingDirectory(unittest.TestCase):
    def setUp(self) -> None:
        base = tempfile.TemporaryDirectory()
        self.addCleanup(base.cleanup)
        self.home = TemporaryHome(Path(base.name)).build().with_queued_work()

    def test_preflight_prints_its_json_line(self) -> None:
        self.assertIn(self.home.last_line(INGEST, "preflight", "--from", "extract")["state"], {"ready", "halt"})

    def test_drive_batch_lists_the_backfill_queue_under_keys(self) -> None:
        listed = self.home.last_line(INGEST, "drive-batch", "--from", "extract")
        self.assertEqual((1, {"extract": [1]}), (listed["count"], listed["stages"]))

    def test_drive_batch_links_each_key_to_a_work_file_naming_its_pdf(self) -> None:
        listed = self.home.last_line(INGEST, "drive-batch", "--from", "extract")
        work_file = json.loads((Path(listed["by_key"]) / "1" / "work.json").read_text(encoding="utf-8"))
        self.assertEqual(QUEUED_WORK, work_file["pdf"])

    def test_list_works_names_each_work_with_its_key(self) -> None:
        listed = self.home.last_line(INGEST, "list-works", "--from", "extract")
        self.assertEqual([{"key": 1, "basename": QUEUED_WORK.removesuffix(".pdf"), "from": "extract"}], listed["works"])

    def test_an_extract_drive_step_prints_its_json_line(self) -> None:
        self.assertIn("state", self.home.last_line(EXTRACT, "drive-wait", "1"))


if __name__ == "__main__":
    unittest.main()
