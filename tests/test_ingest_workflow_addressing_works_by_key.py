from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

BY_KEY = "/Users/someone/.research-vault/cache/ingest/by-key"
LISTED = {"state": "batch", "count": 3, "by_key": BY_KEY, "stages": {"extract": [7, 9], "clean": [2]}}


class WorkflowCase(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = WorkflowSource.ingest()

    def value_of(self, expression: str, *declarations: str) -> object:
        return self.runtime.value_of(self.source.declarations(*declarations), expression)


class TestTheListedWorks(WorkflowCase):
    def test_each_key_is_carried_from_the_stage_its_listing_names(self) -> None:
        works = self.value_of(f"listedWorks({json.dumps(LISTED)})", "STAGES", "listedWorks")
        self.assertEqual([{"key": 2, "from": "clean"}, {"key": 7, "from": "extract"}, {"key": 9, "from": "extract"}], works)

    def test_a_listing_without_stages_carries_nothing(self) -> None:
        self.assertEqual([], self.value_of('listedWorks({state: "batch"})', "STAGES", "listedWorks"))


class TestTheWorkFile(WorkflowCase):
    def test_a_worker_is_pointed_at_the_keys_work_file(self) -> None:
        path = self.value_of(f"workFileOf({json.dumps(BY_KEY)}, 7)", "WORK_FILE", "workFileOf")
        self.assertEqual(f"{BY_KEY}/7/work.json", path)


class TestTheCommandsRelayed(WorkflowCase):
    def test_a_key_quoted_for_the_shell_is_the_key(self) -> None:
        self.assertEqual("'7'", self.value_of("quoted(7)", "quoted"))

    def test_the_works_option_names_keys(self) -> None:
        source = "const args = {from: 'extract', works: [7, 9]}\n" + self.source.declarations("ARGS", "FROM", "batchOptions")
        self.assertEqual("--from extract --works 7 9", self.runtime.value_of(source, "batchOptions()"))


if __name__ == "__main__":
    unittest.main()


class TestTheStageOrder(WorkflowCase):
    def test_the_citation_links_come_after_the_extraction_and_before_the_classification(self) -> None:
        self.assertEqual(["clean", "file", "extract", "cite", "classify"], self.value_of("STAGES", "STAGES"))

    def test_a_work_listed_at_cite_is_carried_from_there(self) -> None:
        works = self.value_of('listedWorks({stages: {cite: [4], classify: [5]}})', "STAGES", "listedWorks")
        self.assertEqual([{"key": 4, "from": "cite"}, {"key": 5, "from": "classify"}], works)
