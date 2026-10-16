from __future__ import annotations

import contextlib
import io
import json
from unittest import mock

from _writing_fixtures import IDEA, WritingTestCase

import vault
from _writing.chosen_tasks import ChosenTasks
from _writing.notes_cli import NotesCommandLine

FURTHER = "Proof in geometry"
OTHER_FURTHER = "Construction in algebra"
CHOSEN = f"- [x] #focus · Take notes on “{FURTHER}”: a figure drawn proves; from [[Euclid - 1956 - Elements]], p. 4"
OPEN = f"- [ ] #contrary · Take notes on “{OTHER_FURTHER}”: algebra constructs symbols"
RETIRED = "- [x] Read Euclid's Elements, book I"
REFERENCE = "> **states** · “A line is drawn.” #review\n> \t[[Euclid - 1956 - Elements]], p. 4"


class ChosenTasksTestCase(WritingTestCase):
    def note(self, title: str, tasks: list[str], references: str = "") -> None:
        self.folders.notes.mkdir(parents=True, exist_ok=True)
        text = f"- a claim\n\n# References\n\n{references}\n\n# Tasks\n\n" + "\n".join(tasks) + "\n"
        self.folders.atomic_note(title).write_text(text, encoding="utf-8")

    def plan(self, limit: int = 8) -> dict:
        return ChosenTasks(self.folders, limit).plan()


class TestChosenTasks(ChosenTasksTestCase):
    def test_a_checked_task_is_chosen_and_an_open_one_is_not(self) -> None:
        self.note(IDEA, [CHOSEN, OPEN])
        self.assertEqual([FURTHER], [task["title"] for task in self.plan()["tasks"]])

    def test_a_chosen_task_names_its_reviewed_note_and_thread(self) -> None:
        self.note(IDEA, [CHOSEN])
        task = self.plan()["tasks"][0]
        self.assertEqual((IDEA, "focus", CHOSEN), (task["reviewed"], task["thread"], task["line"]))

    def test_a_chosen_task_without_its_note_awaits_research(self) -> None:
        self.note(IDEA, [CHOSEN])
        self.assertEqual(("research", [FURTHER]), (self.plan()["tasks"][0]["state"], self.plan()["to_create"]))

    def test_a_chosen_task_whose_note_holds_references_awaits_review(self) -> None:
        self.note(IDEA, [CHOSEN])
        self.note(FURTHER, [], REFERENCE)
        self.assertEqual(("review", []), (self.plan()["tasks"][0]["state"], self.plan()["to_create"]))

    def test_a_chosen_task_whose_note_holds_no_reference_awaits_research(self) -> None:
        self.note(IDEA, [CHOSEN])
        self.note(FURTHER, [])
        self.assertEqual("research", self.plan()["tasks"][0]["state"])

    def test_a_checked_line_in_a_retired_form_is_unparsed(self) -> None:
        self.note(IDEA, [RETIRED])
        self.assertEqual([{"reviewed": IDEA, "line": RETIRED}], self.plan()["unparsed"])

    def test_further_notes_past_the_limit_are_deferred(self) -> None:
        self.note(IDEA, [CHOSEN, OPEN.replace("- [ ]", "- [x]")])
        plan = self.plan(limit=1)
        self.assertEqual(([FURTHER], [OTHER_FURTHER]),
                         ([task["title"] for task in plan["tasks"]], [task["title"] for task in plan["deferred"]]))

    def test_two_notes_choosing_one_title_create_it_once(self) -> None:
        self.note(IDEA, [CHOSEN])
        self.note("Another idea", [CHOSEN])
        plan = self.plan(limit=1)
        self.assertEqual((2, [FURTHER]), (len(plan["tasks"]), plan["to_create"]))

    def test_a_title_no_note_can_carry_is_refused(self) -> None:
        self.note(IDEA, [CHOSEN.replace(FURTHER, "Proof: in geometry")])
        self.assertEqual(([], ["Proof: in geometry"]),
                         (self.plan()["tasks"], [refusal["title"] for refusal in self.plan()["refused"]]))

    def test_the_done_date_obsidian_stamps_on_a_checked_task_is_no_part_of_its_claim(self) -> None:
        self.note(IDEA, [CHOSEN.split("; from")[0] + " ✅ 2026-10-14"])
        ChosenTasks(self.folders, 8).apply()
        self.assertIn("- a figure drawn proves #review", self.folders.atomic_note(FURTHER).read_text(encoding="utf-8"))

    def test_apply_creates_the_note_with_the_task_claim(self) -> None:
        self.note(IDEA, [CHOSEN])
        ChosenTasks(self.folders, 8).apply()
        self.assertIn("- a figure drawn proves #review", self.folders.atomic_note(FURTHER).read_text(encoding="utf-8"))

    def test_the_plan_writes_nothing(self) -> None:
        self.note(IDEA, [CHOSEN])
        self.plan()
        self.assertFalse(self.folders.atomic_note(FURTHER).exists())


class TestEnrichTasks(ChosenTasksTestCase):
    ENRICH = "- [x] #enrich · Read Klein 1968 for this note: the Greek genus and species of number; from Redding 2023, p. 31"

    def test_a_checked_enrich_task_is_chosen_on_its_own_note(self) -> None:
        self.note(IDEA, [self.ENRICH], REFERENCE)
        task = self.plan()["tasks"][0]
        self.assertEqual(("enrich", IDEA, "enrich"), (task["thread"], task["title"], task["state"]))

    def test_an_enrich_task_creates_no_note(self) -> None:
        self.note(IDEA, [self.ENRICH], REFERENCE)
        self.assertEqual([], self.plan()["to_create"])

    def test_each_enrich_task_takes_a_place_under_the_limit(self) -> None:
        self.note(IDEA, [self.ENRICH, self.ENRICH.replace("Klein 1968", "Heath 1921")], REFERENCE)
        plan = self.plan(limit=1)
        self.assertEqual((1, 1), (len(plan["tasks"]), len(plan["deferred"])))


class TestStubNotes(ChosenTasksTestCase):
    def test_a_note_with_a_claim_and_no_reference_is_a_stub(self) -> None:
        self.note(IDEA, [])
        self.assertEqual([IDEA], self.plan()["stubs"])

    def test_a_note_holding_a_reference_is_no_stub(self) -> None:
        self.note(IDEA, [], REFERENCE)
        self.assertEqual([], self.plan()["stubs"])

    def test_a_blank_note_is_no_stub(self) -> None:
        self.folders.notes.mkdir(parents=True, exist_ok=True)
        self.folders.atomic_note(IDEA).write_text("- \n\n# References\n\n# Tasks\n", encoding="utf-8")
        self.assertEqual([], self.plan()["stubs"])

    def test_the_further_note_of_a_chosen_task_is_no_stub(self) -> None:
        self.note(IDEA, [CHOSEN], REFERENCE)
        self.note(FURTHER, [])
        self.assertEqual([], self.plan()["stubs"])

    def test_stubs_take_what_the_limit_leaves_after_the_tasks(self) -> None:
        self.note(IDEA, [CHOSEN], REFERENCE)
        self.note("A stub", [])
        self.note("Another stub", [])
        plan = self.plan(limit=2)
        self.assertEqual((["A stub"], ["Another stub"]), (plan["stubs"], plan["deferred_stubs"]))


class TestChosenCommandLine(ChosenTasksTestCase):
    def test_chosen_prints_one_json_line(self) -> None:
        self.note(IDEA, [CHOSEN])
        out = io.StringIO()
        with mock.patch.object(vault, "WRITING_DIR", self.writing_dir), contextlib.redirect_stdout(out):
            NotesCommandLine().run(["chosen"])
        lines = out.getvalue().strip().splitlines()
        self.assertEqual((1, False), (len(lines), json.loads(lines[0])["applied"]))
