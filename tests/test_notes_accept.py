from __future__ import annotations

import unittest

from _writing_fixtures import IDEA, OTHER_IDEA, WritingTestCase

from _writing.acceptance import NoteAcceptance
from _writing.chosen_tasks import ChosenTasks
from _writing.note_check import HeldSources, NoteCheck
from _writing.relations import NoteRelation, RelationLine
from _writing.task_list import ACCEPT_TASK

CHECKED_ACCEPT_TASK = ACCEPT_TASK.replace("- [ ] ", "- [x] ", 1)
PRIMARY_SOURCE = "Kant - 1998 - Critique of Pure Reason"
SECONDARY_SOURCE = "Friedman - 1992 - Kant and the Exact Sciences"
UNCLASSIFIED_SOURCE = "Hegel - 2010 - The Science of Logic"
ROLES = {PRIMARY_SOURCE: "primary", SECONDARY_SOURCE: "secondary", UNCLASSIFIED_SOURCE: ""}
MARKED_NOTE = ("- Construction is proof #review\n\t- Proof is exhibition #review\n\n# References\n\n### Primary texts\n\n"
               f"> **states** · “Thoughts without content are empty.” #review\n> \t[[{PRIMARY_SOURCE}]], p. A51/B75\n\n"
               "# Tasks\n\n")


def reference(source: str) -> str:
    return f"> **states** · “Words of the page.”\n> \t[[{source}]], p. 9\n"


class NoteTextTestCase(WritingTestCase):
    def write(self, text: str, title: str = IDEA) -> None:
        self.folders.notes.mkdir(parents=True, exist_ok=True)
        self.folders.atomic_note(title).write_text(text, encoding="utf-8")

    def read(self, title: str = IDEA) -> str:
        return self.folders.atomic_note(title).read_text(encoding="utf-8")


class TestNoteAcceptance(NoteTextTestCase):
    def test_a_checked_accept_task_turns_every_review_mark_into_the_accepted_mark(self) -> None:
        self.write(f"{MARKED_NOTE}{CHECKED_ACCEPT_TASK} ✅ 2026-10-15\n")
        NoteAcceptance(self.folders).apply()
        self.assertEqual((0, 3), (self.read().count("#review"), self.read().count("#accepted")))

    def test_the_accept_task_is_unchecked_once_its_note_is_accepted(self) -> None:
        self.write(f"{MARKED_NOTE}{CHECKED_ACCEPT_TASK} ✅ 2026-10-15\n- [ ] Read on\n")
        NoteAcceptance(self.folders).apply()
        self.assertTrue(self.read().endswith(f"# Tasks\n\n{ACCEPT_TASK}\n- [ ] Read on\n"))

    def test_an_unchecked_accept_task_accepts_nothing(self) -> None:
        self.write(f"{MARKED_NOTE}{ACCEPT_TASK}\n")
        NoteAcceptance(self.folders).apply()
        self.assertEqual(3, self.read().count("#review"))

    def test_a_note_lacking_the_accept_task_gains_it_first_under_its_tasks(self) -> None:
        self.write(f"{MARKED_NOTE}- [ ] Read on\n")
        NoteAcceptance(self.folders).apply()
        self.assertTrue(self.read().endswith(f"# Tasks\n\n{ACCEPT_TASK}\n- [ ] Read on\n"))

    def test_the_plan_counts_the_lines_to_accept_and_writes_nothing(self) -> None:
        self.write(f"{MARKED_NOTE}{CHECKED_ACCEPT_TASK}\n")
        plan = NoteAcceptance(self.folders).plan()
        self.assertEqual(([{"note": IDEA, "lines": 3}], []), (plan["accepted"], plan["accept_task_written"]))
        self.assertIn(CHECKED_ACCEPT_TASK, self.read())

    def test_a_checked_accept_task_is_no_chosen_task(self) -> None:
        self.write(f"{MARKED_NOTE}{CHECKED_ACCEPT_TASK}\n")
        plan = ChosenTasks(self.folders, 8).plan()
        self.assertEqual(([], []), (plan["tasks"], plan["unparsed"]))


class TestNoteCheckFindings(NoteTextTestCase):
    def findings(self, claims: str, references: str = "", tasks: str = ACCEPT_TASK) -> list[str]:
        grouped = f"### Literature\n\n{references}" if references else ""
        self.write(f"{claims}\n# References\n\n{grouped}\n# Tasks\n\n{tasks}\n")
        return NoteCheck(self.folders, IDEA, HeldSources(set(ROLES), ROLES)).findings()

    def test_tasks_not_opening_with_the_accept_task_are_a_finding(self) -> None:
        self.assertIn("accept task", self.findings("- a claim\n", tasks="- [ ] Read on")[0])

    def test_claims_and_explications_past_three_lines_are_a_finding(self) -> None:
        self.assertIn("come to 4 lines", self.findings("- a\n\t- b\n- c\n\t- d\n")[0])

    def test_three_lines_of_claims_and_explications_are_no_finding(self) -> None:
        self.assertEqual([], self.findings("- a\n\t- b\n- c\n"))

    def test_references_to_secondary_literature_alone_are_a_finding(self) -> None:
        self.assertIn("to secondary literature", self.findings("- a claim\n", reference(SECONDARY_SOURCE))[0])

    def test_secondary_literature_beside_a_primary_text_is_no_finding(self) -> None:
        both = f"{reference(PRIMARY_SOURCE)}\n{reference(SECONDARY_SOURCE)}"
        self.assertEqual([], self.findings("- a claim\n", both))

    def test_secondary_literature_beside_a_work_no_role_classifies_is_no_finding(self) -> None:
        both = f"{reference(UNCLASSIFIED_SOURCE)}\n{reference(SECONDARY_SOURCE)}"
        self.assertEqual([], self.findings("- a claim\n", both))


class TestGenealogicalRelation(NoteTextTestCase):
    def test_a_note_descends_from_another(self) -> None:
        self.note()
        self.note(OTHER_IDEA)
        NoteRelation(self.folders, IDEA, RelationLine("descends from", OTHER_IDEA, proposed=True)).apply()
        self.assertIn(f"\t- descends from [[{OTHER_IDEA}]] #review", self.read())


if __name__ == "__main__":
    unittest.main()
