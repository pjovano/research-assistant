from __future__ import annotations

import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.numbered import NumberedFiles
from _drive.steps import RELAYED_LINE_LIMIT
from _extract.backfillparts import MAX_SCOPE_PAGES_PER_DISPATCH
from _extract.backfillrunner import ScriptRun
from _workflow_source import JsRuntime, WorkflowSource
from test_extract_backfill_driver import BackfillCase, listing, probed

MANY_PARTS = 40
MANY_SCOPED_PAGES = list(range(1, MANY_PARTS * MAX_SCOPE_PAGES_PER_DISPATCH + 1))
WORK = "/scratch/ingest/by-key/7"
GLOSS_ROOT = "/scratch/ingest/glosses"
BIBLIOGRAPHIES_PLANNED = 3
GLOSS_STUBS = """
const ARGS = {}
const glossed = []
const onBibliographies = task => task()
async function drive(line) { return { state: 'gloss', root: %s, count: %d } }
async function parallel(tasks) { return Promise.all(tasks.map(task => task())) }
async function glossOne(root, number) { glossed.push(`${root}/${number}`); return { state: 'glossed' } }
""" % (json.dumps(GLOSS_ROOT), BIBLIOGRAPHIES_PLANNED)
PARTS = {"count": 2, "listing": "scope-part-{n}.json", "verdicts": "scope-verdicts-0-{n}.json"}


class ScopeOfManyParts:
    def __init__(self, test: unittest.TestCase) -> None:
        script = probed()
        script.results["scope"] = ScriptRun(0, json.dumps(listing(MANY_SCOPED_PAGES)))
        self.case = BackfillCase(test, script)

    def line(self) -> dict:
        return self.case.invoke("prep", fonts_checked=True)


class TestADispatchListOfManyPartsNamedByCountAndFileName(unittest.TestCase):
    def setUp(self) -> None:
        self.line = ScopeOfManyParts(self).line()

    def test_the_line_fits_the_relayed_limit_whatever_the_count_of_parts(self) -> None:
        self.assertLessEqual(len(json.dumps(self.line, ensure_ascii=False)), RELAYED_LINE_LIMIT)

    def test_the_line_names_the_count_of_parts(self) -> None:
        self.assertEqual(MANY_PARTS, self.line["parts"]["count"])

    def test_every_listing_the_line_names_is_written_in_the_work_directory(self) -> None:
        parts = NumberedFiles.expanded(self.line["dir"], self.line["parts"])
        self.assertTrue(all(Path(part["listing"]).is_file() for part in parts))


class TestTheWorkflowReadingADispatchList(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = WorkflowSource.ingest().declarations("NUMBER_SLOT", "COUNT_FIELD", "numbered")

    def test_each_numbered_file_is_named_under_the_line_directory(self) -> None:
        program = f"{self.source}\nconsole.log(JSON.stringify(numbered({json.dumps(WORK)}, {json.dumps(PARTS)})))"
        self.assertEqual(NumberedFiles.expanded(WORK, PARTS), json.loads(self.runtime.printed(program)))


class TestTheWorkflowReadingAGlossPlan(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)

    def test_each_bibliography_of_the_count_is_glossed_in_its_numbered_directory(self) -> None:
        program = (GLOSS_STUBS + WorkflowSource.ingest().declarations("gloss")
                   + "\ngloss([1]).then(() => console.log(JSON.stringify(glossed)))")
        expected = [f"{GLOSS_ROOT}/{number}" for number in range(1, BIBLIOGRAPHIES_PLANNED + 1)]
        self.assertEqual(expected, json.loads(self.runtime.printed(program)))


if __name__ == "__main__":
    unittest.main()
