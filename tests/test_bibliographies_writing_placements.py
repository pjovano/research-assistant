from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import vault
from _bibliographies.reshaping import Reshape
from _bibliography_fixtures import TemporaryVault
from test_bibliographies_folding import ELSEWHERE, NARROWER, SUBJECT, FoldingCase, fold

IDEA = "Truth predicates come in levels"
PROJECT = "Paradox and Hierarchy"
UNRELATED_IDEA = "Dialetheism is a live option"
CLAIM_BODY = "- Each level's truth predicate applies only to the sentences beneath it.\n\n## Sources\n"


def placed_text(*names: str, before: str = "") -> str:
    listed = "".join(f'- "[[{name}]]"\n' for name in names)
    return f"---\n{before}field:\n{listed}---\n\n{CLAIM_BODY}"


class TestAFoldCarriesTheWritingPlacedOnTheFoldedBibliography(FoldingCase):
    def setUp(self) -> None:
        super().setUp()
        self.idea = self.vault.writing_note(vault.ATOMIC_NOTES_FOLDER, IDEA, placed_text(NARROWER))
        self.project = self.vault.writing_note(vault.PROJECT_FILES_FOLDER, PROJECT,
                                               placed_text(NARROWER, before="status: drafting\n"))
        self.unrelated_text = placed_text(ELSEWHERE)
        self.unrelated = self.vault.writing_note(vault.ATOMIC_NOTES_FOLDER, UNRELATED_IDEA, self.unrelated_text)

    def field_of(self, path) -> list[str]:
        return vault.field_topics(vault.read_frontmatter_only(path))

    def test_an_atomic_note_on_the_folded_bibliography_moves_onto_the_target(self) -> None:
        self.fold()
        self.assertEqual([SUBJECT], self.field_of(self.idea))

    def test_the_atomic_notes_body_is_kept(self) -> None:
        self.fold()
        self.assertTrue(self.idea.read_text(encoding="utf-8").endswith(f"---\n\n{CLAIM_BODY}"))

    def test_a_project_file_keeps_its_other_fields(self) -> None:
        self.fold()
        self.assertEqual("drafting", vault.read_frontmatter_only(self.project)["status"])
        self.assertEqual([SUBJECT], self.field_of(self.project))

    def test_a_note_on_another_bibliography_is_left_as_it_was(self) -> None:
        self.fold()
        self.assertEqual(self.unrelated_text, self.unrelated.read_text(encoding="utf-8"))

    def test_the_report_names_each_note_carried(self) -> None:
        folded = self.fold()["folded"][0]
        self.assertEqual(sorted([IDEA, PROJECT]), folded["writing"])

    def test_the_read_only_form_writes_nothing_to_the_writing(self) -> None:
        Reshape(self.answers(fold=[fold()])).plan()
        self.assertEqual([NARROWER], self.field_of(self.idea))


class TestTheCheckOverWritingPlacements(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.parent_of("Logic", "Truth")
        self.vault.bibliography("Truth")

    def advisory(self) -> list[str]:
        return [problem for problems in self.vault.report().as_dict()["advisory"].values() for problem in problems]

    def test_a_note_naming_no_bibliography_never_blocks(self) -> None:
        self.vault.writing_note(vault.ATOMIC_NOTES_FOLDER, IDEA, placed_text("Ghost"))
        self.assertTrue(self.vault.report().is_clean)

    def test_a_note_naming_no_bibliography_is_named_in_the_advisory(self) -> None:
        self.vault.writing_note(vault.ATOMIC_NOTES_FOLDER, IDEA, placed_text("Ghost"))
        self.assertIn(f"{IDEA}: field: names [[Ghost]], which is not a bibliography", self.advisory())

    def test_a_project_on_a_bibliography_and_its_ancestor_is_named_in_the_advisory(self) -> None:
        self.vault.writing_note(vault.PROJECT_FILES_FOLDER, PROJECT, placed_text("Truth", "Logic"))
        self.assertTrue(any(problem.startswith(f"{PROJECT}: field: names [[Truth]] and its ancestor [[Logic]]")
                            for problem in self.advisory()))

    def test_a_note_without_a_frontmatter_is_not_reported(self) -> None:
        self.vault.writing_note(vault.ATOMIC_NOTES_FOLDER, IDEA, CLAIM_BODY)
        self.assertFalse(any(problem.startswith(IDEA) for problem in self.advisory()))


if __name__ == "__main__":
    unittest.main()
