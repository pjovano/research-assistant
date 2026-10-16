from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import bibliographies
import vault
from _bibliographies.drive import BibliographiesScript, ClassifyDriver
from _bibliography_fixtures import HEGEL, HOULGATE, PIPPIN_TALK, TemporaryVault
from _drive.script import ScriptRun

STAGE_ONE_FRONTMATTER = {"title": "The Opening of Hegel's Logic", "author": ["Houlgate"], "year": 2006,
                         "source_type": "", "source_role": "", "field": []}


def answers(**fields) -> dict:
    return {"source_type": "monograph", "source_role": "secondary", "field": ["Logic"], "questions": [], **fields}


class StubPlace(BibliographiesScript):
    def __init__(self, result: ScriptRun | None = None) -> None:
        super().__init__()
        self._result = result or ScriptRun(0, json.dumps({"bibliographies": ["Logic"], "applied": True}))
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> ScriptRun:
        self.calls.append(args)
        return self._result


class ClassifyCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.bibliography("Logic")
        self.vault.note(HOULGATE, **STAGE_ONE_FRONTMATTER)
        self.place = StubPlace()

    def classify(self, given: dict, basename: str = HOULGATE) -> dict:
        path = vault.BIBLIOGRAPHIES_DIR.parent / "answers.json"
        path.write_text(json.dumps(given), encoding="utf-8")
        return ClassifyDriver(self.place).classify(basename, path)

    def meta(self, basename: str = HOULGATE) -> dict:
        return vault.read_frontmatter(vault.held_note_path(basename))[0]

    def note_text(self) -> str:
        return vault.held_note_path(HOULGATE).read_text(encoding="utf-8")


class TestSettledAnswers(ClassifyCase):
    def test_the_three_fields_are_written(self) -> None:
        self.classify(answers())
        meta = self.meta()
        self.assertEqual(("monograph", "secondary", ["[[Logic]]"]),
                         (meta["source_type"], meta["source_role"], meta["field"]))

    def test_every_other_frontmatter_line_is_kept(self) -> None:
        self.classify(answers())
        self.assertEqual(("The Opening of Hegel's Logic", ["Houlgate"], 2006),
                         (self.meta()["title"], self.meta()["author"], self.meta()["year"]))

    def test_a_commentary_names_its_primary_work(self) -> None:
        self.classify(answers(commentary_on=HEGEL))
        self.assertEqual(f"[[{HEGEL}]]", self.meta()["commentary_on"])

    def test_the_work_is_placed_after_the_read_only_form(self) -> None:
        outcome = self.classify(answers())
        self.assertEqual(("placed", [("place", HOULGATE, "--json"), ("place", HOULGATE, "--json", "--apply")]),
                         (outcome["state"], self.place.calls))

    def test_answers_matching_a_written_classification_are_placed_again(self) -> None:
        self.classify(answers())
        self.assertEqual("placed", self.classify(answers())["state"])


class TestAnAuthorsOwnWork(ClassifyCase):
    def test_sits_on_the_authors_bibliography_beside_the_chosen_ones(self) -> None:
        self.vault.bibliography("Houlgate", author="Houlgate")
        self.classify(answers())
        self.assertEqual(["Houlgate", "Logic"], vault.field_topics(self.meta()))

    def test_by_an_author_without_a_bibliography_sits_on_the_chosen_ones_alone(self) -> None:
        self.classify(answers())
        self.assertEqual(["Logic"], vault.field_topics(self.meta()))

    def test_roled_primary_sits_on_the_authors_bibliography_alone(self) -> None:
        self.vault.bibliography("Houlgate", author="Houlgate")
        self.classify(answers(source_role="primary"))
        self.assertEqual(["Houlgate"], vault.field_topics(self.meta()))

    def test_roled_primary_records_no_nomination(self) -> None:
        self.vault.bibliography("Houlgate", author="Houlgate")
        nomination = {"name": "The Opening", "kind": "topic", "parent": "Logic"}
        self.assertFalse(self.classify(answers(source_role="primary", nomination=nomination))["nominated"])

    def test_roled_primary_by_an_author_without_a_bibliography_sits_on_the_chosen_ones(self) -> None:
        self.classify(answers(source_role="primary"))
        self.assertEqual(["Logic"], vault.field_topics(self.meta()))


class TestAFieldNamingABibliographyAndItsAncestor(ClassifyCase):
    def test_a_scholars_own_work_keeps_the_chosen_bibliography_above_the_scholars(self) -> None:
        self.vault.parent_of("Logic", "Houlgate")
        self.vault.bibliography("Houlgate", author="Houlgate")
        self.classify(answers())
        self.assertEqual(["Houlgate", "Logic"], vault.field_topics(self.meta()))

    def test_a_placement_from_before_stage_four_above_the_chosen_one_is_dropped(self) -> None:
        self.vault.parent_of("Philosophy", "Logic")
        self.vault.note(HOULGATE, **{**STAGE_ONE_FRONTMATTER, "field": ["[[Philosophy]]"]})
        self.classify(answers())
        self.assertEqual(["Logic"], vault.field_topics(self.meta()))

    def test_a_thinkers_own_work_keeps_the_thinkers_bibliography_above_the_chosen_one(self) -> None:
        self.vault.parent_of("Houlgate", "Logic", author="Houlgate")
        self.classify(answers())
        self.assertEqual(["Houlgate", "Logic"], vault.field_topics(self.meta()))


class TestAnswersThatSetTheWorkAside(ClassifyCase):
    def assert_set_aside_untouched(self, given: dict) -> None:
        before = self.note_text()
        outcome = self.classify(given)
        self.assertEqual(("aside", before, []), (outcome["state"], self.note_text(), self.place.calls))

    def test_a_question(self) -> None:
        self.assert_set_aside_untouched(answers(questions=["Is this a commentary on the Logic?"]))

    def test_a_bibliography_that_does_not_exist_yet(self) -> None:
        self.assert_set_aside_untouched(answers(field=["Logic", "Dialectic"]))

    def test_a_value_outside_the_vocabulary(self) -> None:
        self.assert_set_aside_untouched(answers(source_role="tertiary"))

    def test_a_commentary_not_roled_secondary(self) -> None:
        self.assert_set_aside_untouched(answers(source_role="primary", commentary_on=HEGEL))

    def test_a_corpus_file_typed_as_a_transcript(self) -> None:
        self.assert_set_aside_untouched(answers(source_type="transcript"))

    def test_a_classification_already_written_otherwise(self) -> None:
        self.classify(answers())
        self.place.calls.clear()
        self.assert_set_aside_untouched(answers(source_role="primary"))

    def test_an_unreadable_answers_file(self) -> None:
        path = vault.BIBLIOGRAPHIES_DIR.parent / "answers.json"
        path.write_text("not json", encoding="utf-8")
        self.assertEqual("aside", ClassifyDriver(self.place).classify(HOULGATE, path)["state"])


class TestATranscript(ClassifyCase):
    def test_takes_the_transcript_type(self) -> None:
        vault.write_frontmatter(vault.TRANSCRIPTS_DIR / f"{PIPPIN_TALK}.md",
                                {"title": "A talk", "source_type": "", "source_role": "", "field": []}, "")
        self.classify(answers(source_type="transcript"), PIPPIN_TALK)
        self.assertEqual("transcript", self.meta(PIPPIN_TALK)["source_type"])


class TestPreparation(unittest.TestCase):
    def setUp(self) -> None:
        self.works_dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.driver = ClassifyDriver(StubPlace(), self.works_dir)

    def test_names_the_answers_file_in_the_works_batch_work_directory(self) -> None:
        line = self.driver.prepare(HOULGATE)
        self.assertEqual(("classify", str(self.works_dir / HOULGATE / "classify-answers.json")),
                         (line["state"], line["answers"]))

    def test_discards_the_answers_of_an_earlier_run(self) -> None:
        stale = Path(self.driver.prepare(HOULGATE)["answers"])
        stale.write_text("{}", encoding="utf-8")
        self.driver.prepare(HOULGATE)
        self.assertFalse(stale.exists())


class TestPlacementRefused(ClassifyCase):
    def test_a_list_of_works_carried_twice_sets_the_work_aside(self) -> None:
        self.place = StubPlace(ScriptRun(4, "", "Logic: carries ## Secondary literature twice"))
        outcome = self.classify(answers())
        self.assertEqual(("aside", True), (outcome["state"], "merge the two lists" in outcome["question"]))

    def test_a_refused_placement_leaves_the_corpus_file_unclassified(self) -> None:
        before = self.note_text()
        self.place = StubPlace(ScriptRun(2, "", "Logic: no such bibliography"))
        self.classify(answers())
        self.assertEqual(before, self.note_text())

    def test_a_refused_placement_keeps_a_classification_written_earlier(self) -> None:
        self.classify(answers())
        written = self.note_text()
        self.place = StubPlace(ScriptRun(1, "", "place failed"))
        self.classify(answers())
        self.assertEqual(written, self.note_text())


class TestNoBibliographyChosen(ClassifyCase):
    def test_answers_with_no_bibliography_and_no_question_classify_the_work_unplaced(self) -> None:
        outcome = self.classify(answers(field=[]))
        self.assertEqual(("placed", [], "monograph", [], []),
                         (outcome["state"], outcome["bibliographies"], self.meta()["source_type"],
                          self.meta()["field"], self.place.calls))

    def test_no_bibliography_beside_a_proposal_sets_the_work_aside(self) -> None:
        outcome = self.classify(answers(field=[], questions=["propose Dialectic, under Logic"]))
        self.assertEqual("aside", outcome["state"])


class TestConflictCopies(ClassifyCase):
    def test_a_conflict_copy_among_the_bibliographies_halts_the_batch(self) -> None:
        (vault.BIBLIOGRAPHIES_DIR / "Logic 2.md").write_text("---\n---\n", encoding="utf-8")
        self.assertEqual("halt", self.classify(answers())["state"])


class CommandCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def printed(self, *argv: str) -> str:
        output = io.StringIO()
        with mock.patch.object(sys, "argv", ["bibliographies.py", *argv]), contextlib.redirect_stdout(output):
            bibliographies.CommandLine().run()
        return output.getvalue()


class TestPlaceAsJson(CommandCase):
    def test_names_the_bibliographies_it_would_change(self) -> None:
        self.vault.bibliography("Logic")
        self.vault.note(HOULGATE, field=["[[Logic]]"])
        self.assertEqual({"bibliographies": ["Logic"], "applied": False},
                         json.loads(self.printed("place", HOULGATE, "--json")))


class TestTree(CommandCase):
    def test_lists_each_bibliography_with_the_bibliographies_its_maps_list(self) -> None:
        self.vault.parent_of("Philosophy", "Logic")
        self.vault.bibliography("Logic", aliases=["Formal logic"])
        tree = {entry["name"]: entry for entry in json.loads(self.printed("tree"))}
        self.assertEqual((["Logic"], ["Formal logic"]), (tree["Philosophy"]["maps"], tree["Logic"]["aliases"]))


class TestACaveatThatLeavesEveryValueSettled(ClassifyCase):
    CAVEAT = "the opening carries headings and notes only; the description rests on them"

    def test_the_work_is_placed(self) -> None:
        self.assertEqual("placed", self.classify(answers(notes=[self.CAVEAT]))["state"])

    def test_the_caveat_is_carried_as_a_note(self) -> None:
        self.assertEqual([self.CAVEAT], self.classify(answers(notes=[self.CAVEAT]))["notes"])

    def test_answers_without_notes_carry_none(self) -> None:
        self.assertEqual([], self.classify(answers())["notes"])


if __name__ == "__main__":
    unittest.main()


class TestTheDescription(ClassifyCase):
    def test_the_description_is_written_beside_the_classification(self) -> None:
        self.classify(answers(description="Argues that the Logic opens without presupposition (Houlgate 2006, p. 29)."))
        self.assertEqual("Argues that the Logic opens without presupposition (Houlgate 2006, p. 29).",
                         self.meta()["description"])

    def test_an_empty_description_writes_no_field(self) -> None:
        self.classify(answers(description=""))
        self.assertNotIn("description", self.meta())

    def test_a_description_with_a_colon_and_a_quotation_mark_reads_back_whole(self) -> None:
        given = 'Reads Kant\'s "I think": the unity of apperception as logical, not psychological (p. 3).'
        self.classify(answers(description=given))
        self.assertEqual(given, self.meta()["description"])


class TestANomination(ClassifyCase):
    def nominate(self) -> dict:
        nomination = {"name": "Openings of the Logic", "kind": "topic", "parent": "Logic"}
        return self.classify(answers(field=[], nomination=nomination))

    def test_the_work_is_classified_and_placed_nowhere(self) -> None:
        outcome = self.nominate()
        self.assertEqual(("placed", [], True), (outcome["state"], outcome["bibliographies"], outcome["nominated"]))
        self.assertEqual("monograph", self.meta()["source_type"])

    def test_the_nomination_is_recorded_for_the_shaper_with_the_work(self) -> None:
        self.nominate()
        ledger = json.loads((vault.SCRATCH_DIR / "ingest" / "nominations.json").read_text(encoding="utf-8"))
        self.assertEqual([{"name": "Openings of the Logic", "kind": "topic", "parent": "Logic", "works": [HOULGATE],
                           "placed_on": []}], ledger["nominations"])

    def test_a_work_placed_on_the_nearest_bibliography_records_where_it_sits(self) -> None:
        nomination = {"name": "Openings of the Logic", "kind": "topic", "parent": "Logic"}
        self.classify(answers(nomination=nomination))
        ledger = json.loads((vault.SCRATCH_DIR / "ingest" / "nominations.json").read_text(encoding="utf-8"))
        self.assertEqual(["Logic"], ledger["nominations"][0]["placed_on"])

    def test_answers_without_a_nomination_record_none(self) -> None:
        self.assertFalse(self.classify(answers())["nominated"])
