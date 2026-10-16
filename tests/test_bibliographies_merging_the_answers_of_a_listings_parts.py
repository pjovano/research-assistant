from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import bibliographies
from _bibliographies.answermerge import MergedAnswers
from _bibliographies.partsdir import PartAnswers, PartsDirectory
from _bibliographies.reshaping import Reshape, ReshapeAnswers
from _bibliography_fixtures import HOULGATE, TemporaryVault

STERN = "Stern - 2023 - Understanding Hegel's Logic"
LOGIC = "Logic"
BEING = "The Doctrine of Being"
ESSENCE = "The Doctrine of Essence"
TO_BEING = {"work": HOULGATE, "from": LOGIC, "to": BEING}
TO_ESSENCE = {"work": HOULGATE, "from": LOGIC, "to": ESSENCE}
STERN_TO_BEING = {"work": STERN, "from": LOGIC, "to": BEING}


def merged(*parts: dict) -> dict:
    return MergedAnswers(list(parts)).merged()


class TestMovesFromTwoParts(unittest.TestCase):
    def test_one_move_named_by_both_is_made_once(self) -> None:
        self.assertEqual([TO_BEING], merged({"move": [TO_BEING]}, {"move": [TO_BEING]})["move"])

    def test_a_works_conflicting_moves_are_both_dropped(self) -> None:
        answers = merged({"move": [TO_BEING, STERN_TO_BEING]}, {"move": [TO_ESSENCE]})
        self.assertEqual([STERN_TO_BEING], answers["move"])

    def test_the_dropped_moves_are_a_question_naming_the_work_and_both_targets(self) -> None:
        question = merged({"move": [TO_BEING]}, {"move": [TO_ESSENCE]})["questions"][0]
        self.assertTrue(all(name in question for name in (HOULGATE, BEING, ESSENCE)))

    def test_a_works_moves_off_two_bibliographies_both_stand(self) -> None:
        off_another = {"work": HOULGATE, "from": "Metaphysics", "to": ESSENCE}
        self.assertEqual([TO_BEING, off_another], merged({"move": [TO_BEING]}, {"move": [off_another]})["move"])


class TestCreationsFromTwoParts(unittest.TestCase):
    def creation(self, *works: str, parent: str = LOGIC) -> dict:
        return {"name": BEING, "kind": "topic", "parent": parent, "author": None, "works": list(works)}

    def test_one_name_is_one_creation_gathering_the_works_of_both(self) -> None:
        answers = merged({"create": [self.creation(HOULGATE)]}, {"create": [self.creation(STERN, HOULGATE)]})
        self.assertEqual([self.creation(HOULGATE, STERN)], answers["create"])

    def test_creations_that_agree_ask_nothing(self) -> None:
        answers = merged({"create": [self.creation(HOULGATE)]}, {"create": [self.creation(STERN)]})
        self.assertEqual([], answers["questions"])

    def test_one_name_under_two_parents_keeps_the_first_and_asks(self) -> None:
        answers = merged({"create": [self.creation(HOULGATE)]}, {"create": [self.creation(STERN, parent="Hegel")]})
        self.assertEqual((LOGIC, True), (answers["create"][0]["parent"], BEING in answers["questions"][0]))


class TestFoldsFromTwoParts(unittest.TestCase):
    FOLD = {"name": ESSENCE, "into": LOGIC, "group": "Essence"}

    def test_one_fold_named_by_both_is_made_once(self) -> None:
        self.assertEqual([self.FOLD], merged({"fold": [self.FOLD]}, {"fold": [self.FOLD]})["fold"])

    def test_a_fold_into_two_bibliographies_is_dropped_and_asked(self) -> None:
        answers = merged({"fold": [self.FOLD]}, {"fold": [{**self.FOLD, "into": BEING}]})
        self.assertEqual(([], True), (answers["fold"], ESSENCE in answers["questions"][0]))

    def test_a_fold_of_a_bibliography_another_part_moves_a_work_to_is_dropped_and_asked(self) -> None:
        answers = merged({"fold": [self.FOLD]}, {"move": [TO_ESSENCE]})
        self.assertEqual(([], [TO_ESSENCE], True),
                         (answers["fold"], answers["move"], ESSENCE in answers["questions"][0]))

    def test_a_fold_into_a_bibliography_another_part_folds_drops_that_other_fold(self) -> None:
        onward = {"name": LOGIC, "into": "Hegel", "group": "Logic"}
        self.assertEqual([self.FOLD], merged({"fold": [self.FOLD]}, {"fold": [onward]})["fold"])


class TestTheOtherAnswersFromTwoParts(unittest.TestCase):
    def test_a_repeated_link_unlink_or_added_placement_is_made_once(self) -> None:
        part = {"link": [{"name": BEING, "parent": LOGIC}], "unlink": [{"name": BEING, "parent": "Hegel"}],
                "add": [{"work": STERN, "to": BEING}]}
        answers = merged(part, part)
        self.assertEqual(part, {name: answers[name] for name in part})

    def test_every_parts_questions_are_carried_once(self) -> None:
        answers = merged({"questions": ["which period?"]}, {"questions": ["which period?", "which root?"]})
        self.assertEqual(["which period?", "which root?"], answers["questions"])


class PartAnswersCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp()) / "parts"
        self.directory = PartsDirectory(self.root)
        self.directory.write([{"tree": []}, {"tree": []}])

    def answer(self, number: int, text: str) -> None:
        (self.root / str(number) / "answers.json").write_text(text, encoding="utf-8")

    def part_answers(self) -> PartAnswers:
        return PartAnswers(self.directory)


class TestAPartWithoutAnAnswersFile(PartAnswersCase):
    def test_is_counted_as_unanswered(self) -> None:
        self.answer(1, json.dumps({"move": [TO_BEING]}))
        self.assertEqual({"parts": 2, "answered": 1}, self.part_answers().report())

    def test_is_a_question_naming_the_part_beside_the_answers_of_the_rest(self) -> None:
        self.answer(1, json.dumps({"move": [TO_BEING]}))
        answers = self.part_answers().merged()
        self.assertEqual(([TO_BEING], True), (answers["move"], "part 2 of 2" in answers["questions"][0]))

    def test_an_answers_file_that_is_no_json_object_is_unanswered(self) -> None:
        self.answer(1, "not json")
        self.answer(2, "[]")
        self.assertEqual({"parts": 2, "answered": 0}, self.part_answers().report())


class TestTheMergedAnswersOfTwoPartsReshapingAVault(PartAnswersCase):
    def setUp(self) -> None:
        super().setUp()
        self.vault = TemporaryVault(self)
        for name in (LOGIC, BEING, ESSENCE):
            self.vault.bibliography_in("3 topics", name, "## Maps\n\n## Works in library\n")
        for basename in (HOULGATE, STERN):
            self.vault.note(basename, field=[f"[[{LOGIC}]]"], source_role="secondary", title=basename,
                            author=[basename.split(" - ")[0]], year=int(basename.split(" - ")[1]))
        self.answer(1, json.dumps({"move": [TO_BEING, STERN_TO_BEING]}))
        self.answer(2, json.dumps({"move": [TO_ESSENCE, STERN_TO_BEING]}))
        answers = self.root / "answers.json"
        answers.write_text(json.dumps(self.part_answers().merged()), encoding="utf-8")
        self.report = Reshape(ReshapeAnswers.read(answers)).apply()

    def field_of(self, basename: str) -> list[str]:
        return bibliographies.Corpus().note(basename).bibliographies

    def test_the_work_two_parts_moved_apart_stays_where_it_sat(self) -> None:
        self.assertEqual([LOGIC], self.field_of(HOULGATE))

    def test_the_work_two_parts_moved_alike_is_moved_once(self) -> None:
        self.assertEqual([BEING], self.field_of(STERN))

    def test_the_report_carries_the_question_of_the_dropped_moves(self) -> None:
        self.assertTrue(any(HOULGATE in question for question in self.report["questions"]))


if __name__ == "__main__":
    unittest.main()
