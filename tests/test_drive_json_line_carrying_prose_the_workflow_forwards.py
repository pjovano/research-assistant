from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.steps import RELAYED_LINE_LIMIT, SPILLED_TEXT_OPENING, JsonLine
from _vaults import TempVault

DEFECT_CLASS = "A word set in one face inside a run of another is read by the text layer as a third face."
DEFECT_CLASSES = 12
PART = {"listing": "/scratch/by-key/1/review-part-1.json", "verdicts": "/scratch/by-key/1/review-verdicts-1-1.json"}
PARTS = 8
LONG_QUESTION_REPEATS = 60


def emitted(outcome: dict) -> dict:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        JsonLine.emit(outcome)
    return json.loads(output.getvalue())


def printed_length(outcome: dict) -> int:
    return len(json.dumps(emitted(outcome), ensure_ascii=False))


class TestAJsonLineCarryingProseTheWorkflowForwardsKeepsWithinTheRelayedLimit(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault().activate()
        self.addCleanup(self.vault.discard)
        self.classes = [f"{DEFECT_CLASS} {index}" for index in range(DEFECT_CLASSES)]
        self.accepted = {"state": "accepted", "pdf": "/scratch/by-key/1/work.pdf", "notes": self.classes}

    def test_the_line_fits_the_relayed_limit(self) -> None:
        self.assertLessEqual(printed_length(self.accepted), RELAYED_LINE_LIMIT)

    def test_the_forwarded_list_is_written_to_the_file_its_one_item_names(self) -> None:
        pointer = emitted(self.accepted)["notes"][0]
        self.assertEqual(self.classes, Path(pointer.split(" in ", 1)[1]).read_text(encoding="utf-8").splitlines())

    def test_the_fields_the_workflow_reads_are_kept(self) -> None:
        line = emitted(self.accepted)
        self.assertEqual(("accepted", self.accepted["pdf"]), (line["state"], line["pdf"]))

    def test_a_long_question_keeps_its_opening_and_names_the_file_holding_it_whole(self) -> None:
        question = "convert failed: Inference error: Connection error. " * LONG_QUESTION_REPEATS
        line = emitted({"state": "aside", "question": question})
        opening, path = line["question"].split(" […] whole in ", 1)
        self.assertEqual((question[:SPILLED_TEXT_OPENING], question),
                         (opening, Path(path).read_text(encoding="utf-8").rstrip("\n")))

    def test_a_list_the_workflow_reads_is_never_spilled_for_the_relayed_limit(self) -> None:
        parts = [PART] * PARTS
        self.assertEqual(parts, emitted({"state": "review", "parts": parts})["parts"])


if __name__ == "__main__":
    unittest.main()
