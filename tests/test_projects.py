from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest import mock

from _writing_fixtures import (
    LONGER, PAPER, SHORT, THESIS, WritingTestCase,
)

import vault
from _writing.actions import DraftCut, ProjectCreation, ProjectLink, Publication
from _writing.cli import CommandLine
from _writing.drafts import DraftName
from _writing.linked_note import LinkedNote
from _writing.placement import HeadingLine, StatusChange
from _writing.board_file import BoardFile
from _writing.project_file import DRAFTS, FEEDBACK, ProjectFile

class TestProjectFile(unittest.TestCase):
    def test_a_blank_project_file_carries_its_status_parents_and_children_in_its_frontmatter(self) -> None:
        self.assertTrue(ProjectFile.blank(PAPER).text.startswith("---\nstatus: planning\nparents: []\nchildren: []\n---\n"))

    def test_a_blank_project_file_carries_its_headings_in_order_those_of_the_project_card_a_level_down(self) -> None:
        headings = [line for line in ProjectFile.blank(PAPER).text.splitlines() if line.startswith("#")]
        self.assertEqual(["# Research question", "# Project", "## Abstract", "## Reading list", "## Drafts", "## Change log"],
                         headings)

    def test_the_project_card_links_the_projects_reading_list(self) -> None:
        self.assertIn(f"## Reading list\n\n[[{PAPER} - Reading list]]", ProjectFile.blank(PAPER).text)


    def test_the_feedback_heading_is_written_once_it_holds_a_line(self) -> None:
        project_file = ProjectFile.blank(PAPER).with_line_last(FEEDBACK, "- Referee 2: clarify the scope")
        self.assertIn("# Feedback\n\n- Referee 2: clarify the scope", project_file.markdown_side(PAPER))

    def test_a_project_file_holds_no_task_its_tasks_heading_dropped_with_its_body(self) -> None:
        earlier = ProjectFile.blank(PAPER).with_body("Tasks", "- [ ] Read Friedman").with_body("All tasks", "```tasks\nnot done\n```")
        self.assertNotIn("Tasks", earlier.markdown_side(PAPER))

    def test_a_heading_the_markdown_side_no_longer_carries_is_dropped_with_its_body(self) -> None:
        project_file = ProjectFile.blank(PAPER).with_body("Glossary", "- **measure** (*Maß*): the unity")
        self.assertNotIn("Glossary", project_file.markdown_side(PAPER))

    def test_a_heading_written_at_the_top_level_by_an_earlier_layout_is_read_and_kept(self) -> None:
        earlier = ProjectFile("---\nstatus: drafting\n---\n\n# Abstract\n\nMeasure unites.\n\n# Tasks\n\n- [ ] Read\n")
        self.assertIn("## Abstract\n\nMeasure unites.\n\n## Reading list", earlier.markdown_side(PAPER))

    def test_a_heading_added_to_a_file_that_holds_a_drawing_is_written_before_the_drawing(self) -> None:
        drawn = ProjectFile("---\nstatus: planning\n---\n\n# Research question\n\n# Excalidraw Data\n\n## Text Elements\n")
        written = drawn.with_line_last(FEEDBACK, "- a point").text
        self.assertLess(written.index("# Feedback"), written.index("# Excalidraw Data"))

    def test_a_line_put_first_precedes_the_existing_lines(self) -> None:
        project_file = ProjectFile.blank(PAPER).with_line_first(DRAFTS, "- old").with_line_first(DRAFTS, "- new")
        self.assertEqual(project_file.body(DRAFTS), "- new\n- old")

    def test_writing_under_one_heading_leaves_the_others_as_they_were(self) -> None:
        project_file = ProjectFile.blank(PAPER).with_line_last(FEEDBACK, "- Referee 2: clarify the scope")
        self.assertEqual(project_file.body(DRAFTS), "")

    def test_a_heading_the_user_removed_is_put_back_at_the_end(self) -> None:
        project_file = ProjectFile("---\nstatus: planning\n---\n\n# Abstract\n").with_line_first(DRAFTS, "- v")
        self.assertEqual(project_file.body(DRAFTS), "- v")

    def test_a_heading_runs_over_its_second_and_third_level_headings_to_the_next_top_heading(self) -> None:
        project_file = ProjectFile.blank(PAPER).with_body(FEEDBACK, "## A reader\n\n### A point")
        self.assertEqual(project_file.body(FEEDBACK), "## A reader\n\n### A point")

    def test_the_links_under_a_heading_are_its_wikilink_targets(self) -> None:
        project_file = ProjectFile.blank(PAPER).with_line_last(DRAFTS, f"- [[{PAPER} - v01]]\n- [[A|alias]]")
        self.assertEqual(project_file.linked(DRAFTS), [f"{PAPER} - v01", "A"])

    def test_the_project_file_survives_its_own_text(self) -> None:
        project_file = ProjectFile.blank(PAPER).with_status("drafting")
        self.assertEqual(ProjectFile(project_file.text).status, "drafting")

    def test_a_parent_is_listed_as_a_wikilink_in_the_frontmatter(self) -> None:
        self.assertIn(f"parents:\n- '[[{THESIS}]]'\n", ProjectFile.blank(PAPER).with_parent(THESIS).text)

    def test_a_link_listed_twice_is_kept_once(self) -> None:
        self.assertEqual(ProjectFile.blank(PAPER).with_child(PAPER).with_child(PAPER).children, [PAPER])

    def test_a_status_change_keeps_the_body(self) -> None:
        project_file = ProjectFile.blank(PAPER).with_line_last(DRAFTS, "- [[A draft - v01]]").with_status("revising")
        self.assertEqual(project_file.body(DRAFTS), "- [[A draft - v01]]")


class TestLinkedNote(unittest.TestCase):
    def test_a_single_link_written_without_a_list_is_read(self) -> None:
        self.assertEqual(LinkedNote.parsed(f'---\nparents: "[[{THESIS}]]"\n---\n').links("parents"), [THESIS])

    def test_a_note_without_a_frontmatter_has_no_links(self) -> None:
        self.assertEqual(LinkedNote.parsed("- a claim\n").links("parents"), [])


class TestDraftName(unittest.TestCase):
    def test_a_whole_draft_is_named_by_its_project_and_version(self) -> None:
        self.assertEqual(DraftName(THESIS, None, 3).basename, f"{THESIS} - v03")

    def test_a_section_draft_names_its_section_between(self) -> None:
        self.assertEqual(DraftName(THESIS, "Introduction", 1).basename, f"{THESIS} - Introduction - v01")

    def test_a_section_draft_is_read_back_from_its_filename(self) -> None:
        name = DraftName.parsed(THESIS, f"{THESIS} - Introduction - v12.md")
        self.assertEqual((name.section, name.version), ("Introduction", 12))

    def test_a_file_of_another_project_is_not_its_draft(self) -> None:
        self.assertIsNone(DraftName.parsed(THESIS, f"{PAPER} - v01.md"))

    def test_a_file_without_a_version_is_not_a_draft(self) -> None:
        self.assertIsNone(DraftName.parsed(THESIS, f"{THESIS} - notes.md"))


class TestProjectTree(WritingTestCase):
    def test_a_child_is_a_project_its_parent_lists_among_its_children(self) -> None:
        self.create(THESIS)
        self.create(PAPER, parent=THESIS)
        tree = self.tree()
        self.assertEqual([child.name for child in tree.children(tree.named(THESIS))], [PAPER])

    def test_a_child_names_its_parent(self) -> None:
        self.create(THESIS)
        self.create(PAPER, parent=THESIS)
        tree = self.tree()
        self.assertEqual([parent.name for parent in tree.parents(tree.named(PAPER))], [THESIS])

    def test_a_child_link_naming_no_project_is_no_child(self) -> None:
        self.create(THESIS)
        self.tree().named(THESIS).list_child("Nowhere")
        self.assertEqual(self.tree().children(self.tree().named(THESIS)), [])

    def test_a_link_listed_on_both_projects_is_not_one_sided(self) -> None:
        self.create(THESIS)
        self.create(PAPER, parent=THESIS)
        self.assertEqual(self.tree().one_sided_links(self.tree().named(PAPER)), [])

    def test_a_parent_that_does_not_list_its_child_is_reported(self) -> None:
        self.create(THESIS)
        self.create(PAPER)
        self.tree().named(PAPER).list_parent(THESIS)
        self.assertEqual(self.tree().one_sided_links(self.tree().named(PAPER)),
                         [f"{THESIS} does not list it among its children"])

    def test_an_unknown_project_is_refused_by_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "no project file named 'Nowhere'"):
            self.tree().named("Nowhere")

    def test_a_draft_belongs_to_the_longest_project_name_it_opens_with(self) -> None:
        self.create(SHORT)
        self.create(LONGER)
        self.draft(f"{LONGER} - v01.md")
        self.assertEqual(self.tree().named(SHORT).drafts.all(), [])

    def test_a_section_draft_of_the_shorter_name_stays_with_it(self) -> None:
        self.create(SHORT)
        self.create(LONGER)
        self.draft(f"{SHORT} - Introduction - v01.md")
        self.assertEqual([name.section for name in self.tree().named(SHORT).drafts.all()], ["Introduction"])


class TestProjectCreation(WritingTestCase):
    def test_the_project_file_is_written_into_the_projects_folder_with_its_markdown_side(self) -> None:
        self.create(THESIS)
        board = BoardFile((self.folders.projects / f"{THESIS}.md").read_text(encoding="utf-8"))
        self.assertEqual(ProjectFile.blank(THESIS).markdown_side(THESIS).strip(), board.markdown_side.strip())

    def test_a_new_board_shows_the_project_card_and_the_research_question(self) -> None:
        self.create(THESIS)
        board = BoardFile((self.folders.projects / f"{THESIS}.md").read_text(encoding="utf-8"))
        self.assertEqual([f"[[{THESIS}#Project]]", f"[[{THESIS}#Research question]]"],
                         [element["link"] for element in board.elements() if element["link"]])

    def test_a_new_project_gains_its_blank_reading_list(self) -> None:
        self.create(THESIS)
        reading_list = self.folders.reading_lists / f"{THESIS} - Reading list.md"
        self.assertIn("# Held\n\n# Wanted\n", reading_list.read_text(encoding="utf-8"))

    def test_a_child_is_listed_among_its_parents_children(self) -> None:
        self.create(THESIS)
        self.create(PAPER, parent=THESIS)
        self.assertEqual(self.project_file(THESIS).children, [PAPER])

    def test_a_child_lists_its_parent(self) -> None:
        self.create(THESIS)
        self.create(PAPER, parent=THESIS)
        self.assertEqual(self.project_file(PAPER).parents, [THESIS])

    def test_the_plan_writes_nothing(self) -> None:
        ProjectCreation(self.tree(), THESIS, None).plan()
        self.assertFalse(self.folders.projects.exists())

    def test_a_taken_name_is_refused(self) -> None:
        self.create(THESIS)
        with self.assertRaisesRegex(ValueError, "exists"):
            ProjectCreation(self.tree(), THESIS, None)

    def test_a_name_holding_a_link_character_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "holds none of"):
            ProjectCreation(self.tree(), "A [draft]", None)

    def test_an_unknown_parent_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "no project file named"):
            ProjectCreation(self.tree(), PAPER, "Nowhere")


class TestProjectLink(WritingTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.create(THESIS)
        self.create(PAPER)

    def test_a_link_is_written_on_both_projects(self) -> None:
        ProjectLink(self.tree(), THESIS, PAPER).apply()
        self.assertEqual((self.project_file(THESIS).children, self.project_file(PAPER).parents), ([PAPER], [THESIS]))

    def test_a_project_may_have_several_parents(self) -> None:
        self.create(SHORT)
        ProjectLink(self.tree(), THESIS, PAPER).apply()
        ProjectLink(self.tree(), SHORT, PAPER).apply()
        self.assertEqual(self.project_file(PAPER).parents, [THESIS, SHORT])

    def test_a_project_is_refused_as_its_own_parent(self) -> None:
        with self.assertRaisesRegex(ValueError, "never its own parent"):
            ProjectLink(self.tree(), PAPER, PAPER)

    def test_an_unknown_child_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "no project file named"):
            ProjectLink(self.tree(), THESIS, "Nowhere")


class TestDraftCut(WritingTestCase):
    def cut(self, section: str | None = None) -> None:
        DraftCut(self.tree().named(THESIS), section).apply()

    def test_the_first_draft_is_version_one_and_empty(self) -> None:
        self.create(THESIS)
        self.cut()
        self.assertEqual((self.folders.drafts / f"{THESIS} - v01.md").read_text(encoding="utf-8"), "")

    def test_the_next_version_copies_the_latest(self) -> None:
        self.create(THESIS)
        self.draft(f"{THESIS} - v01.md", "first")
        self.draft(f"{THESIS} - v02.md", "second")
        self.cut()
        self.assertEqual((self.folders.drafts / f"{THESIS} - v03.md").read_text(encoding="utf-8"), "second")

    def test_a_section_is_versioned_apart_from_the_whole_draft(self) -> None:
        self.create(THESIS)
        self.draft(f"{THESIS} - v04.md", "whole")
        self.cut("Introduction")
        self.assertTrue((self.folders.drafts / f"{THESIS} - Introduction - v01.md").exists())

    def test_the_new_version_is_linked_first_under_drafts(self) -> None:
        self.create(THESIS)
        self.cut()
        self.cut()
        self.assertEqual(self.project_file(THESIS).body(DRAFTS), f"- [[{THESIS} - v02]]\n- [[{THESIS} - v01]]")

    def test_the_plan_names_the_draft_and_its_source_and_writes_nothing(self) -> None:
        self.create(THESIS)
        self.draft(f"{THESIS} - v01.md")
        plan = DraftCut(self.tree().named(THESIS), None).plan()
        self.assertEqual((Path(plan["draft"]).name, Path(plan["copied_from"]).name),
                         (f"{THESIS} - v02.md", f"{THESIS} - v01.md"))


class TestPublication(WritingTestCase):
    TITLE = "Essays on Transcendental Logic"

    def test_the_latest_whole_draft_is_copied_under_its_title(self) -> None:
        self.create(THESIS)
        self.draft(f"{THESIS} - v01.md", "old")
        self.draft(f"{THESIS} - v02.md", "final")
        Publication(self.tree(), THESIS, self.TITLE).apply()
        self.assertEqual((self.folders.published / f"{self.TITLE}.md").read_text(encoding="utf-8"), "final")

    def test_the_published_piece_is_listed_first_under_drafts(self) -> None:
        self.create(THESIS)
        self.draft(f"{THESIS} - v01.md")
        Publication(self.tree(), THESIS, self.TITLE).apply()
        self.assertEqual(self.project_file(THESIS).linked(DRAFTS)[0], self.TITLE)

    def test_a_project_with_only_section_drafts_is_refused(self) -> None:
        self.create(THESIS)
        self.draft(f"{THESIS} - Introduction - v01.md")
        with self.assertRaisesRegex(ValueError, "no whole draft"):
            Publication(self.tree(), THESIS, self.TITLE)

    def test_a_title_naming_a_project_file_is_refused(self) -> None:
        self.create(THESIS)
        self.draft(f"{THESIS} - v01.md")
        with self.assertRaisesRegex(ValueError, "names a project file"):
            Publication(self.tree(), THESIS, THESIS)

    def test_an_existing_published_piece_is_never_overwritten(self) -> None:
        self.create(THESIS)
        self.draft(f"{THESIS} - v01.md")
        Publication(self.tree(), THESIS, self.TITLE).apply()
        with self.assertRaisesRegex(ValueError, "never overwritten"):
            Publication(self.tree(), THESIS, self.TITLE)


class TestHeadingLineAndStatus(WritingTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.create(PAPER)

    def test_a_line_is_added_last_under_the_named_heading(self) -> None:
        HeadingLine(self.tree().named(PAPER), "feedback", "- Referee 2: clarify the scope").apply()
        self.assertEqual(self.project_file(PAPER).body(FEEDBACK), "- Referee 2: clarify the scope")

    def test_a_task_for_the_project_file_is_refused_as_an_unknown_heading(self) -> None:
        with self.assertRaisesRegex(ValueError, "a heading is one of"):
            HeadingLine(self.tree().named(PAPER), "tasks", "- [ ] Read Friedman")

    def test_an_unknown_heading_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "a heading is one of"):
            HeadingLine(self.tree().named(PAPER), "venue", "Kant-Studien")

    def test_the_status_is_written_into_the_frontmatter(self) -> None:
        StatusChange(self.tree().named(PAPER), "drafting").apply()
        self.assertEqual(self.tree().named(PAPER).status, "drafting")

    def test_an_unknown_status_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "a status is one of"):
            StatusChange(self.tree().named(PAPER), "finished")


class TestCommandLine(WritingTestCase):
    def run_command(self, *argv: str) -> object:
        out = io.StringIO()
        with mock.patch.object(vault, "WRITING_DIR", self.writing_dir), contextlib.redirect_stdout(out):
            CommandLine().run(list(argv))
        return json.loads(out.getvalue())

    def test_new_without_apply_writes_nothing(self) -> None:
        self.assertFalse(self.run_command("new", THESIS)["applied"])
        self.assertFalse(self.folders.projects.exists())

    def test_tree_lists_each_project_with_its_status_field_parents_children_one_sided_links_and_drafts(self) -> None:
        self.run_command("new", THESIS, "--apply")
        self.run_command("new", PAPER, "--parent", THESIS, "--apply")
        DraftCut(self.tree().named(PAPER), None).apply()
        listing = {row["project"]: row for row in self.run_command("tree")}
        self.assertEqual(listing[PAPER], {"project": PAPER, "status": "planning", "field": [], "parents": [THESIS],
                                          "children": [], "one_sided_links": [], "drafts": [f"{PAPER} - v01"]})

    def test_a_refusal_exits_with_its_reason(self) -> None:
        with self.assertRaisesRegex(SystemExit, "no project file named"):
            self.run_command("status", "Nowhere", "drafting")


if __name__ == "__main__":
    unittest.main()
