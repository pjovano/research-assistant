from __future__ import annotations

import unittest

from _writing_fixtures import IDEA, WritingTestCase

from _writing.chosen_tasks import ChosenTasks
from _writing.note_check import HeldSources, NoteCheck
from _writing.note_lines import NoteFile, NoteTask
from _writing.task_list import ACCEPT_TASK

ENRICH_LINE = "#enrich · Read Klein 1968 for this note: the Greek genus of number; from Redding 2023, p. 31"


class TaggedNoteTestCase(WritingTestCase):
    def write(self, tasks: list[str]) -> None:
        self.folders.notes.mkdir(parents=True, exist_ok=True)
        text = "- a claim\n\n# References\n\n# Tasks\n\n" + "\n".join([ACCEPT_TASK, *tasks]) + "\n"
        self.folders.atomic_note(IDEA).write_text(text, encoding="utf-8")


class TestTheTaskCommand(WritingTestCase):
    def test_a_task_opening_with_its_threads_tag_is_written(self) -> None:
        self.note()
        NoteTask(NoteFile(self.folders, IDEA), ENRICH_LINE).apply()
        self.assertIn(f"- [ ] {ENRICH_LINE}", self.folders.atomic_note(IDEA).read_text(encoding="utf-8"))

    def test_a_task_without_a_threads_tag_is_refused(self) -> None:
        self.note()
        with self.assertRaisesRegex(ValueError, "thread's tag"):
            NoteTask(NoteFile(self.folders, IDEA), "**enrich** · Read Klein 1968 for this note")

    def test_the_accept_tag_is_no_thread_a_task_takes(self) -> None:
        self.note()
        with self.assertRaisesRegex(ValueError, "thread's tag"):
            NoteTask(NoteFile(self.folders, IDEA), "#accept · Accept this note")


class TestTheCheckOfTaskTags(TaggedNoteTestCase):
    def findings(self) -> list[str]:
        return NoteCheck(self.folders, IDEA, HeldSources(set())).findings()

    def test_a_task_line_without_a_tag_is_a_finding(self) -> None:
        self.write(["- [ ] **conceptual** · Take notes on “Proof”: proof is exhibition"])
        self.assertIn("thread's tag", self.findings()[0])

    def test_tagged_task_lines_are_no_finding(self) -> None:
        self.write([f"- [ ] {ENRICH_LINE}", "- [ ] #conceptual · Take notes on “Proof”: proof is exhibition"])
        self.assertEqual([], self.findings())


class TestARetaggedTask(TaggedNoteTestCase):
    def test_an_enrich_task_retagged_to_a_note_thread_is_listed_as_retagged(self) -> None:
        self.write([f"- [x] {ENRICH_LINE.replace('#enrich', '#conceptual')}"])
        plan = ChosenTasks(self.folders, 8).plan()
        self.assertEqual(([], [], ["conceptual"]),
                         (plan["tasks"], plan["unparsed"], [each["thread"] for each in plan["retagged"]]))

    def test_a_note_thread_task_retagged_to_enrich_is_an_enrich_task(self) -> None:
        self.write(["- [x] #enrich · Take notes on “Proof”: proof is exhibition; from Kant 1998, A713"])
        [task] = ChosenTasks(self.folders, 8).plan()["tasks"]
        self.assertEqual(("enrich", IDEA), (task["thread"], task["title"]))


if __name__ == "__main__":
    unittest.main()
