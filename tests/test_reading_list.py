from __future__ import annotations

import contextlib
import io
import json
from unittest import mock

from _writing_fixtures import PAPER, WritingTestCase

import vault
from _writing.cli import CommandLine
from _writing.linked_note import LinkedNote
from _writing.reading_list import (
    HELD, QUESTIONS, SUBJECTS, WANTED, ReadingAddition, ReadingEntry, ReadingList, ReadingListFile, ReadingListRefresh,
    ReadingListReport, WantedWork,
)

WANTED_LINE = "- **high** · Friedman 1992, *Kant and the Exact Sciences* — the standard reading. [publisher](https://example.org)"
HELD_BASENAME = "Friedman - 1992 - Kant and the Exact Sciences"
HELD_LINE = f"- [[{HELD_BASENAME}]] — the standard reading."
OTHER_HELD_LINE = "- [[Kant - 1998 - Critique of Pure Reason]] — the text the question is about."
PRIMARY, SECONDARY = "Primary texts", "Secondary literature"
QUESTION_LINE = "- How does Kant ground the certainty of geometry?"
SUBJECT_LINE = "- [ ] #discover \u00b7 Discover \u201cKant's theory of construction in intuition\u201d: the works on the question read it through construction."
OTHER_LINE = "- **low** · Shabel 2003, *Mathematics in Kant\u2019s Critical Philosophy: Reflections on Mathematical Practice* — on construction"


class TestWantedWork(WritingTestCase):
    def test_an_entry_is_read_as_its_author_year_title_and_reason(self) -> None:
        work = WantedWork.read(WANTED_LINE)
        self.assertEqual(("Friedman", "1992", "Kant and the Exact Sciences", "the standard reading."),
                         (work.author, work.year, work.title, work.reason))

    def test_a_line_out_of_the_shape_is_no_wanted_work(self) -> None:
        self.assertIsNone(WantedWork.read("- something to read some day"))

    def test_a_work_is_held_under_the_basename_of_its_author_year_and_main_title(self) -> None:
        self.assertTrue(WantedWork.read(OTHER_LINE).is_held_as("Shabel - 2003 - Mathematics in Kant's Critical Philosophy"))

    def test_a_work_of_another_year_is_not_the_held_one(self) -> None:
        self.assertFalse(WantedWork.read(WANTED_LINE).is_held_as("Friedman - 2013 - Kant and the Exact Sciences"))

    def test_a_work_of_another_author_is_not_the_held_one(self) -> None:
        self.assertFalse(WantedWork.read(WANTED_LINE).is_held_as("Buchdahl - 1992 - Kant and the Exact Sciences"))

    def test_a_held_line_links_the_work_and_keeps_the_reason_without_the_obtain_link(self) -> None:
        self.assertEqual(f"- [[{HELD_BASENAME}]] — the standard reading.", WantedWork.read(WANTED_LINE).held_line(HELD_BASENAME))


class ReadingListTestCase(WritingTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.create(PAPER)
        self.file = ReadingListFile(self.folders.reading_lists, PAPER)

    def add(self, status: str, line: str) -> None:
        ReadingAddition(self.file, ReadingEntry(status, line)).apply()

    def add_to_group(self, status: str, line: str, group: str) -> None:
        ReadingAddition(self.file, ReadingEntry(status, line, group)).apply()

    def groups_of(self, status: str) -> list[str]:
        section = self.file.path.read_text(encoding="utf-8").split(f"# {status}\n")[1].split("\n# ")[0]
        return [line.removeprefix("### ") for line in section.splitlines() if line.startswith("### ")]


class TestReadingList(ReadingListTestCase):
    def test_a_reading_list_is_written_into_the_reading_lists_folder_of_the_bibliographies(self) -> None:
        self.add("wanted", WANTED_LINE)
        folder = self.writing_dir.parent / "bibliographies" / "4 reading lists"
        self.assertEqual([f"{PAPER} - Reading list.md"], [path.name for path in folder.iterdir()])

    def test_a_blank_reading_list_names_its_project_and_its_two_statuses(self) -> None:
        text = ReadingList.blank(PAPER).text
        self.assertEqual(([PAPER], ["# Held", "# Wanted"]),
                         (LinkedNote.parsed(text).links("project"),
                          [line for line in text.splitlines() if line.startswith("# ")]))

    def test_an_entry_is_added_under_its_status_in_the_projects_file(self) -> None:
        self.add("wanted", WANTED_LINE)
        self.assertEqual(([WANTED_LINE], f"{PAPER} - Reading list.md"), (self.file.read().entries(WANTED), self.file.path.name))

    def test_an_entry_given_without_its_bullet_gains_it(self) -> None:
        self.add("held", "Ghost 1900, *Nothing* — off the question")
        self.assertEqual(["- Ghost 1900, *Nothing* — off the question"], self.file.read().entries(HELD))

    def test_a_status_the_reading_list_does_not_keep_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "a reading-list entry is one of"):
            self.add("discarded", "Ghost 1900, *Nothing* — off the question")

    def test_a_wanted_entry_is_no_task_and_carries_no_box(self) -> None:
        self.add("wanted", WANTED_LINE.removeprefix("- "))
        self.assertEqual([WANTED_LINE], self.file.read().entries(WANTED))

    def test_a_wanted_entry_an_earlier_shape_wrote_with_a_box_is_written_without_it(self) -> None:
        for box in ("- [ ] ", "- [x] "):
            with self.subTest(box=box):
                self.file.write(ReadingList("# Held\n\n# Wanted\n\n" + WANTED_LINE.replace("- ", box, 1) + "\n"))
                self.add("wanted", OTHER_LINE)
                self.assertEqual([WANTED_LINE, OTHER_LINE], self.file.read().entries(WANTED))

    def test_a_held_entry_carries_no_box(self) -> None:
        self.add("held", f"[[{HELD_BASENAME}]] — the standard reading.")
        self.assertEqual([f"- [[{HELD_BASENAME}]] — the standard reading."], self.file.read().entries(HELD))

    def test_an_entry_is_written_under_its_group_of_its_status(self) -> None:
        ReadingAddition(self.file, ReadingEntry("wanted", WANTED_LINE, "Secondary literature")).apply()
        self.assertIn(f"# Wanted\n\n### Secondary literature\n\n{WANTED_LINE}\n", self.file.path.read_text(encoding="utf-8"))

    def test_the_groups_of_a_status_keep_the_order_they_were_first_written_in(self) -> None:
        self.add_to_group("wanted", WANTED_LINE, PRIMARY)
        self.add_to_group("wanted", OTHER_LINE, SECONDARY)
        self.assertEqual([PRIMARY, SECONDARY], self.groups_of(WANTED))

    def test_a_group_first_written_under_one_status_stands_under_the_other_in_the_same_place(self) -> None:
        self.add_to_group("wanted", WANTED_LINE, PRIMARY)
        self.add_to_group("wanted", OTHER_LINE, SECONDARY)
        self.assertEqual([PRIMARY, SECONDARY], self.groups_of(HELD))

    def test_an_entry_arriving_under_the_other_status_leaves_the_order_of_the_groups(self) -> None:
        self.add_to_group("wanted", WANTED_LINE, PRIMARY)
        self.add_to_group("wanted", OTHER_LINE, SECONDARY)
        self.add_to_group("held", HELD_LINE, SECONDARY)
        self.add_to_group("held", OTHER_HELD_LINE, PRIMARY)
        self.assertEqual(([PRIMARY, SECONDARY], [PRIMARY, SECONDARY]), (self.groups_of(HELD), self.groups_of(WANTED)))

    def test_a_group_whose_last_entry_is_removed_keeps_its_place(self) -> None:
        self.add_to_group("wanted", WANTED_LINE, PRIMARY)
        self.add_to_group("wanted", OTHER_LINE, SECONDARY)
        self.file.write(self.file.read().without_entry(WANTED, WANTED_LINE))
        self.assertEqual([PRIMARY, SECONDARY], self.groups_of(WANTED))

    def test_an_entry_added_to_an_emptied_group_stands_where_the_group_stood(self) -> None:
        self.add_to_group("wanted", WANTED_LINE, PRIMARY)
        self.add_to_group("wanted", OTHER_LINE, SECONDARY)
        self.file.write(self.file.read().without_entry(WANTED, WANTED_LINE))
        self.add_to_group("wanted", WANTED_LINE, PRIMARY)
        self.assertIn(f"# Wanted\n\n### {PRIMARY}\n\n{WANTED_LINE}\n\n### {SECONDARY}\n\n{OTHER_LINE}\n",
                      self.file.path.read_text(encoding="utf-8"))

    def test_a_refresh_that_empties_a_group_of_wanted_keeps_the_order_of_both_statuses(self) -> None:
        self.add_to_group("wanted", WANTED_LINE, PRIMARY)
        self.add_to_group("wanted", OTHER_LINE, SECONDARY)
        ReadingListRefresh(self.file, [HELD_BASENAME]).apply()
        self.assertEqual(([PRIMARY, SECONDARY], [PRIMARY, SECONDARY]), (self.groups_of(HELD), self.groups_of(WANTED)))

    def test_an_emptied_group_is_read_back_from_the_file_in_its_place(self) -> None:
        self.file.write(ReadingList(f"# Held\n\n### {PRIMARY}\n\n### {SECONDARY}\n\n"
                                    f"# Wanted\n\n### {PRIMARY}\n\n### {SECONDARY}\n\n{OTHER_LINE}\n"))
        self.add_to_group("held", HELD_LINE, PRIMARY)
        self.assertIn(f"# Held\n\n### {PRIMARY}\n\n{HELD_LINE}\n\n### {SECONDARY}\n\n# Wanted",
                      self.file.path.read_text(encoding="utf-8"))

    def test_groups_the_two_statuses_were_given_in_different_orders_take_the_order_of_first_appearance(self) -> None:
        self.file.write(ReadingList(f"# Held\n\n### {SECONDARY}\n\n{HELD_LINE}\n\n# Wanted\n\n### {PRIMARY}\n\n"
                                    f"{WANTED_LINE}\n\n### {SECONDARY}\n\n{OTHER_LINE}\n"))
        self.add_to_group("held", OTHER_HELD_LINE, PRIMARY)
        self.assertEqual(([SECONDARY, PRIMARY], [SECONDARY, PRIMARY]), (self.groups_of(HELD), self.groups_of(WANTED)))

    def test_a_refresh_moves_a_work_into_the_group_of_held_it_stood_in_under_wanted(self) -> None:
        ReadingAddition(self.file, ReadingEntry("wanted", WANTED_LINE, "Secondary literature")).apply()
        ReadingListRefresh(self.file, [HELD_BASENAME]).apply()
        self.assertIn(f"# Held\n\n### Secondary literature\n\n- [[{HELD_BASENAME}]]", self.file.path.read_text(encoding="utf-8"))

    def test_an_entry_the_list_holds_with_a_box_an_earlier_shape_wrote_is_refused_a_second_time(self) -> None:
        self.file.write(ReadingList("# Held\n\n# Wanted\n\n" + WANTED_LINE.replace("- ", "- [x] ", 1) + "\n"))
        with self.assertRaisesRegex(ValueError, "holds the entry"):
            self.add("wanted", WANTED_LINE)

    def test_a_wanted_entry_out_of_the_shape_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "a wanted entry reads"):
            ReadingAddition(self.file, ReadingEntry("wanted", "something to read some day"))

    def test_an_entry_the_list_holds_is_refused(self) -> None:
        self.add("wanted", WANTED_LINE)
        with self.assertRaisesRegex(ValueError, "already"):
            ReadingAddition(self.file, ReadingEntry("wanted", WANTED_LINE))

    def test_the_report_names_the_wanted_entries_the_library_now_holds(self) -> None:
        self.add("wanted", WANTED_LINE)
        report = ReadingListReport(self.file, [HELD_BASENAME]).as_json()
        self.assertEqual([{"entry": WANTED_LINE, "held_as": HELD_BASENAME}], report["wanted_and_now_held"])

    def test_a_refresh_moves_a_wanted_work_the_library_now_holds_to_held_and_leaves_the_rest(self) -> None:
        self.add("wanted", WANTED_LINE)
        self.add("wanted", OTHER_LINE)
        ReadingListRefresh(self.file, [HELD_BASENAME]).apply()
        refreshed = self.file.read()
        self.assertEqual(([OTHER_LINE], [f"- [[{HELD_BASENAME}]] — the standard reading."]),
                         (refreshed.entries(WANTED), refreshed.entries(HELD)))

    def test_the_plan_of_a_refresh_writes_nothing(self) -> None:
        self.add("wanted", WANTED_LINE)
        ReadingListRefresh(self.file, [HELD_BASENAME]).plan()
        self.assertEqual([WANTED_LINE], self.file.read().entries(WANTED))


class TestReadingListQuestionsAndNeighbouringSubjects(ReadingListTestCase):
    def headings(self) -> list[str]:
        return [line for line in self.file.path.read_text(encoding="utf-8").splitlines() if line.startswith("# ")]

    def test_the_questions_open_the_list_and_the_neighbouring_subjects_close_it(self) -> None:
        self.add("subject", SUBJECT_LINE)
        self.add("wanted", WANTED_LINE)
        self.add("question", QUESTION_LINE)
        self.assertEqual(["# Questions", "# Held", "# Wanted", "# Neighbouring subjects"], self.headings())

    def test_a_list_without_questions_or_neighbouring_subjects_writes_neither_heading(self) -> None:
        self.add("wanted", WANTED_LINE)
        self.assertEqual(["# Held", "# Wanted"], self.headings())

    def test_adding_a_wanted_entry_keeps_the_questions_and_the_neighbouring_subjects(self) -> None:
        self.add("question", QUESTION_LINE)
        self.add("subject", SUBJECT_LINE)
        self.add("wanted", WANTED_LINE)
        self.assertEqual(([QUESTION_LINE], [SUBJECT_LINE]), (self.file.read().entries(QUESTIONS), self.file.read().entries(SUBJECTS)))

    def test_a_refresh_keeps_the_questions_and_the_neighbouring_subjects(self) -> None:
        self.add("question", QUESTION_LINE)
        self.add("subject", SUBJECT_LINE)
        self.add("wanted", WANTED_LINE)
        ReadingListRefresh(self.file, [HELD_BASENAME]).apply()
        self.assertEqual(([QUESTION_LINE], [SUBJECT_LINE]), (self.file.read().entries(QUESTIONS), self.file.read().entries(SUBJECTS)))

    def test_a_neighbouring_subject_given_without_its_box_gains_one_to_check(self) -> None:
        self.add("subject", SUBJECT_LINE.replace("- [ ] ", ""))
        self.assertEqual([SUBJECT_LINE], self.file.read().entries(SUBJECTS))

    def test_a_discover_task_the_user_checked_stays_checked(self) -> None:
        checked = SUBJECT_LINE.replace("- [ ]", "- [x]")
        self.file.write(ReadingList(f"# Held\n\n# Wanted\n\n# Neighbouring subjects\n\n{checked}\n"))
        self.add("wanted", OTHER_LINE)
        self.assertEqual([checked], self.file.read().entries(SUBJECTS))

    def test_a_neighbouring_subject_out_of_the_discover_task_shape_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "a neighbouring subject reads"):
            self.add("subject", "Kant's theory of construction")

    def test_a_question_given_a_group_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "stands in no group"):
            self.add_to_group("question", QUESTION_LINE, PRIMARY)

    def test_a_question_the_list_holds_is_refused(self) -> None:
        self.add("question", QUESTION_LINE)
        with self.assertRaisesRegex(ValueError, "holds the entry under Questions already"):
            self.add("question", QUESTION_LINE)


class TestReadingListCommands(ReadingListTestCase):
    def run_command(self, *argv: str) -> dict:
        out = io.StringIO()
        with mock.patch.object(vault, "WRITING_DIR", self.writing_dir), contextlib.redirect_stdout(out), \
                mock.patch.object(vault, "list_corpus_files", lambda: []), mock.patch.object(vault, "list_transcripts", lambda: []):
            CommandLine().run(list(argv))
        return json.loads(out.getvalue())

    def test_reading_with_apply_writes_the_entry_and_readings_lists_it(self) -> None:
        self.run_command("reading", PAPER, "wanted", WANTED_LINE, "--apply")
        self.assertEqual([WANTED_LINE], self.run_command("readings", PAPER)["wanted"])

    def test_readings_lists_the_questions_and_the_neighbouring_subjects(self) -> None:
        self.run_command("reading", PAPER, "question", QUESTION_LINE, "--apply")
        self.run_command("reading", PAPER, "subject", SUBJECT_LINE, "--apply")
        report = self.run_command("readings", PAPER)
        self.assertEqual(([QUESTION_LINE], [SUBJECT_LINE]), (report["question"], report["subject"]))

    def test_readings_of_an_unknown_project_exits_with_its_reason(self) -> None:
        with self.assertRaisesRegex(SystemExit, "no project file named"):
            self.run_command("readings", "Nowhere")
