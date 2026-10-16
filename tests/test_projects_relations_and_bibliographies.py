from __future__ import annotations

from _writing_fixtures import IDEA, OTHER_IDEA, PAPER, WritingTestCase

from _writing.bibliography_placement import BibliographyPlacement
from _writing.atomic_note import REFERENCES, TASKS, AtomicNote, Relation
from _writing.linked_note import FIELD, LinkedNote
from _writing.note_check import HeldSources, NoteCheck
from _writing.task_list import ACCEPT_TASK
from _writing.relations import NoteRelation, RelationLine

GLOSS = "construction supplies what the concept alone cannot"
LOGIC = "Philosophy of Mathematics"
KANT = "Kant"
HELD = {LOGIC, KANT}


class TestAtomicNote(WritingTestCase):
    def test_a_line_goes_last_under_its_part(self) -> None:
        note = AtomicNote("- a claim\n\n# References\n\n# Tasks\n\n- [ ] Read A\n")
        self.assertEqual(note.with_line_last(TASKS, "- [ ] Read B").lines(TASKS), "- [ ] Read A\n- [ ] Read B")

    def test_a_missing_references_part_is_put_back_before_the_tasks(self) -> None:
        written = AtomicNote("- a claim\n\n# Tasks\n").with_line_last(REFERENCES, "> a block").text
        self.assertLess(written.index(f"# {REFERENCES}"), written.index(f"# {TASKS}"))

    def test_a_note_without_a_frontmatter_is_written_without_one(self) -> None:
        self.assertFalse(AtomicNote("- a claim\n").with_explication("extends [[A]]").text.startswith("---"))

    def test_an_explication_goes_last_beneath_the_claims_and_above_the_references(self) -> None:
        note = AtomicNote("- a claim\n\t- a precision\n\n# References\n\n# Tasks\n")
        self.assertTrue(note.with_explication("extends [[A]]").text.startswith(
            "- a claim\n\t- a precision\n\t- extends [[A]]\n\n# References"))

    def test_the_claims_are_the_bullets_that_open_the_note_without_their_explications(self) -> None:
        note = AtomicNote("- first\n- second\n\t- a precision\n\n# References\n")
        self.assertEqual(["first", "second"], note.claims())

    def test_a_relation_is_read_from_an_explication_and_from_a_reference(self) -> None:
        note = AtomicNote("- a claim\n\t- so it extends [[A]].\n\n# References\n\n"
                          "> **states** · “q”\n> \t[[W]], p. 3\n> \tpresupposes [[B]]\n\n# Tasks\n")
        self.assertEqual([Relation("extends", "A"), Relation("presupposes", "B")], note.relations())

    def test_a_quotations_relation_to_its_claim_is_no_relation_to_a_note(self) -> None:
        note = AtomicNote("- a claim\n\n# References\n\n> **supports** · “q”\n> \t[[W]], p. 3\n\n# Tasks\n")
        self.assertEqual([], note.relations())


class TestNoteRelation(WritingTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.note()
        self.note(OTHER_IDEA)

    def relate(self, relation: str = "extends", target: str = OTHER_IDEA, gloss: str = GLOSS) -> NoteRelation:
        return NoteRelation(self.folders, IDEA, RelationLine(relation, target, gloss))

    def written(self) -> str:
        return self.folders.atomic_note(IDEA).read_text(encoding="utf-8")

    def test_the_line_is_an_explication_naming_the_relation_the_other_note_and_the_gloss(self) -> None:
        self.relate().apply()
        self.assertIn(f"\n\t- extends [[{OTHER_IDEA}]]: {GLOSS}\n\n# {REFERENCES}", self.written())

    def test_a_relation_without_a_gloss_is_written_without_one(self) -> None:
        self.relate(gloss="  ").apply()
        self.assertIn(f"\n\t- extends [[{OTHER_IDEA}]]\n", self.written())

    def test_a_proposed_relation_carries_the_review_mark(self) -> None:
        NoteRelation(self.folders, IDEA, RelationLine("extends", OTHER_IDEA, proposed=True)).apply()
        self.assertIn(f"\n\t- extends [[{OTHER_IDEA}]] #review\n", self.written())

    def test_the_other_note_is_left_as_it_was(self) -> None:
        before = self.folders.atomic_note(OTHER_IDEA).read_text(encoding="utf-8")
        self.relate().apply()
        self.assertEqual(before, self.folders.atomic_note(OTHER_IDEA).read_text(encoding="utf-8"))

    def test_the_plan_writes_nothing(self) -> None:
        before = self.written()
        self.relate().plan()
        self.assertEqual(before, self.written())

    def test_a_relation_outside_the_vocabulary_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "a relation is one of"):
            self.relate(relation="refines")

    def test_a_note_related_to_itself_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "itself"):
            self.relate(target=IDEA)

    def test_an_unwritten_note_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "no note named"):
            self.relate(target="An unwritten idea")

    def test_a_second_relation_to_the_same_note_is_refused(self) -> None:
        self.relate().apply()
        with self.assertRaisesRegex(ValueError, "already"):
            self.relate(relation="supports")


class TestNoteCheck(WritingTestCase):
    SOURCE = "Kant - 1998 - Critique of Pure Reason"
    REFERENCE = f"> **states** · “Thoughts without content are empty.”\n> \t[[{SOURCE}]], p. A51/B75\n"

    def setUp(self) -> None:
        super().setUp()
        self.note(OTHER_IDEA)

    def written(self, text: str) -> dict:
        self.folders.atomic_note(IDEA).write_text(text, encoding="utf-8")
        return NoteCheck(self.folders, IDEA, HeldSources({self.SOURCE})).report()

    def note_with(self, references: str = "", claims: str = "- a claim\n") -> dict:
        grouped = f"### Primary texts\n\n{references}" if references else ""
        return self.written(f"{claims}\n# References\n\n{grouped}\n# Tasks\n\n{ACCEPT_TASK}\n- [ ] #enrich · Read the Dialectic\n")

    def test_a_works_references_parted_by_another_works_are_a_finding(self) -> None:
        other = "> **states** · “Other words.”\n> \t[[Friedman - 1992 - Kant and the Exact Sciences]], p. 9\n"
        parted = f"{self.REFERENCE}\n{other}\n{self.REFERENCE}"
        self.folders.atomic_note(IDEA).write_text(f"- a claim\n\n# References\n\n### Primary texts\n\n{parted}\n# Tasks\n\n{ACCEPT_TASK}\n",
                                                  encoding="utf-8")
        held = HeldSources({self.SOURCE, "Friedman - 1992 - Kant and the Exact Sciences"})
        report = NoteCheck(self.folders, IDEA, held).report()
        self.assertEqual([f"{self.SOURCE!r}: the references to one work stand together in their group"], report["findings"])

    def test_a_reference_under_no_group_is_a_finding(self) -> None:
        report = self.written(f"- a claim\n\n# References\n\n{self.REFERENCE}\n# Tasks\n\n{ACCEPT_TASK}\n")
        self.assertEqual(["1 references stand under no group: a reference stands under a ### group"], report["findings"])

    def test_a_note_in_the_shape_has_no_finding(self) -> None:
        self.assertEqual([], self.note_with(self.REFERENCE)["findings"])

    def test_the_report_counts_claims_references_review_marks_and_open_tasks(self) -> None:
        report = self.note_with(self.REFERENCE, "- a claim #review\n- another\n")
        self.assertEqual((2, 1, 1, 1),
                         (report["claims"], report["references"], report["to_review"], report["open_tasks"]))

    def test_a_reference_marked_for_review_is_in_the_shape(self) -> None:
        marked = self.REFERENCE.replace("empty.”", "empty.” #review")
        self.assertEqual([], self.note_with(marked)["findings"])

    def test_a_transcript_reference_cited_by_its_time_marker_is_in_the_shape(self) -> None:
        cited = self.REFERENCE.replace("p. A51/B75", "[00:14:05](https://example.org/talk)")
        self.assertEqual([], self.note_with(cited)["findings"])

    def test_a_fourth_claim_is_a_finding(self) -> None:
        self.assertIn("one to 3 claims", self.note_with(claims="- a\n- b\n- c\n- d\n")["findings"][0])

    def test_a_blank_claim_is_a_finding(self) -> None:
        self.assertEqual(["a claim is blank"], self.written(f"- \n\n# References\n\n# Tasks\n\n{ACCEPT_TASK}\n")["findings"])

    def test_a_heading_outside_the_two_parts_is_a_finding(self) -> None:
        report = self.written("- a claim\n\n# References\n\n# Related\n\n# Tasks\n")
        self.assertIn("headings", report["findings"][0])

    def test_a_quotation_relation_outside_the_vocabulary_is_a_finding(self) -> None:
        report = self.note_with(self.REFERENCE.replace("states", "proves"))
        self.assertIn("a quotation's relation is one of", report["findings"][0])

    def test_a_quotation_without_its_quotation_marks_is_a_finding(self) -> None:
        report = self.note_with(self.REFERENCE.replace("“", "").replace("”", ""))
        self.assertIn("a quotation line reads", report["findings"][0])

    def test_a_reference_without_its_source_line_is_a_finding(self) -> None:
        report = self.note_with("> **states** · “Thoughts without content are empty.”\n")
        self.assertIn("then its source line", report["findings"][0])

    def test_a_source_no_corpus_file_or_transcript_carries_is_a_finding(self) -> None:
        report = self.note_with(self.REFERENCE.replace(self.SOURCE, "Ghost - 1900 - Nothing"))
        self.assertIn("no corpus file or transcript", report["findings"][0])

    def test_a_relation_to_an_unwritten_note_is_a_finding(self) -> None:
        report = self.note_with(self.REFERENCE, "- a claim\n\t- extends [[An unwritten idea]]\n")
        self.assertIn("no note named", report["findings"][0])

    def test_a_relation_to_a_written_note_is_no_finding(self) -> None:
        report = self.note_with(self.REFERENCE, f"- a claim\n\t- extends [[{OTHER_IDEA}]]\n")
        self.assertEqual([], report["findings"])

    def test_an_unwritten_note_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "no note named"):
            NoteCheck(self.folders, "An unwritten idea", HeldSources(set()))


class TestBibliographyPlacement(WritingTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.note()
        self.create(PAPER)

    def place(self, name: str, *bibliographies: str) -> BibliographyPlacement:
        return BibliographyPlacement(self.tree(), name, list(bibliographies), HELD)

    def field_of(self, path) -> list[str]:
        return LinkedNote.parsed(path.read_text(encoding="utf-8")).links(FIELD)

    def test_an_atomic_note_gains_its_field(self) -> None:
        self.place(IDEA, LOGIC, KANT).apply()
        self.assertEqual([LOGIC, KANT], self.field_of(self.folders.atomic_note(IDEA)))

    def test_an_atomic_notes_body_is_kept(self) -> None:
        self.place(IDEA, LOGIC).apply()
        self.assertTrue(self.folders.atomic_note(IDEA).read_text(encoding="utf-8").endswith(f"# {REFERENCES}\n\n# {TASKS}\n\n{ACCEPT_TASK}\n"))

    def test_a_project_file_gains_its_field_and_keeps_its_status(self) -> None:
        self.place(PAPER, KANT).apply()
        self.assertEqual(([KANT], "planning"), (self.project_file(PAPER).bibliographies,
                                                self.project_file(PAPER).status))

    def test_a_second_placement_replaces_the_first(self) -> None:
        self.place(IDEA, LOGIC).apply()
        self.place(IDEA, KANT).apply()
        self.assertEqual([KANT], self.field_of(self.folders.atomic_note(IDEA)))

    def test_the_plan_names_what_the_field_was_and_writes_nothing(self) -> None:
        plan = self.place(IDEA, LOGIC).plan()
        self.assertEqual(([LOGIC], []), (plan["field"], plan["was"]))
        self.assertEqual([], self.field_of(self.folders.atomic_note(IDEA)))

    def test_a_name_that_is_no_bibliography_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "not a bibliography"):
            self.place(IDEA, "Ghost")

    def test_a_bibliography_named_twice_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "named once"):
            self.place(IDEA, KANT, KANT)

    def test_no_bibliography_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            self.place(IDEA)

    def test_an_unknown_note_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "no atomic note or project file"):
            self.place("Nowhere", KANT)
