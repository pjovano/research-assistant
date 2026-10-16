from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import bibliographies
import vault
from _bibliographies.foldfinding import FoldCandidates
from _bibliographies.reshaping import Reshape, ReshapeAnswers, ReshapeRefused
from _bibliography_fixtures import TemporaryVault

TOPICS = "3 topics"
DISCIPLINE = "Philosophy of Logic"
SUBJECT = "Liar Paradox"
NARROWER = "Responses to the Liar Paradox"
BENEATH_NARROWER = "Revision Theory"
BENEATH_SUBJECT = "Liar Paradox and Truth"
ELSEWHERE = "Metaphysics"
GROUP = "Responses"
SURVEY = "Beall - 2008 - The Liar Paradox Surveyed"
CONTEXTUALIST = "Glanzberg - 2004 - A Contextual-Hierarchical Approach"
TWO_SUBJECTS = "Priest - 2006 - Dialetheism and the Liar"
ON_BOTH = "Field - 2008 - Saving Truth from Paradox"
ON_A_DEEPER_ONE = "Kripke - 1975 - Outline of a Theory of Truth"
REVISIONIST = "Gupta and Belnap - 1993 - The Revision Theory of Truth"


def body(maps: tuple[str, ...] = (), works: tuple[str, ...] = ()) -> str:
    listed_maps = "".join(f"- [[{name}]]\n" for name in maps)
    listed_works = "".join(f"{line}\n" for line in works) or "*(none)*\n"
    return f"## Maps\n\n{listed_maps}\n## Secondary literature\n\n{listed_works}"


def answers_file(directory: Path, **given) -> Path:
    path = directory / "answers.json"
    path.write_text(json.dumps({"create": [], "move": [], "questions": [], **given}), encoding="utf-8")
    return path


def fold(name: str = NARROWER, into: str = SUBJECT, group: str = GROUP) -> dict:
    return {"name": name, "into": into, "group": group}


class FoldingCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.scratch = Path(tempfile.mkdtemp())
        self.vault.bibliography_in(TOPICS, DISCIPLINE, body((SUBJECT, NARROWER)))
        self.vault.bibliography_in(TOPICS, SUBJECT, body((BENEATH_SUBJECT, NARROWER), (f"- [[{SURVEY}]]",
                                                                                     f"- [[{ON_BOTH}]]")))
        self.vault.bibliography_in(TOPICS, NARROWER, body((BENEATH_NARROWER,), (
            f"- [[{CONTEXTUALIST}]] — a contextual hierarchy of truth predicates.", f"- [[{TWO_SUBJECTS}]]",
            f"- [[{ON_BOTH}]]", f"- [[{ON_A_DEEPER_ONE}]]")))
        self.vault.bibliography_in(TOPICS, BENEATH_NARROWER, body((), (f"- [[{REVISIONIST}]]",)))
        self.vault.bibliography_in(TOPICS, BENEATH_SUBJECT, body((), (f"- [[{ON_A_DEEPER_ONE}]]",)))
        self.vault.bibliography_in(TOPICS, ELSEWHERE, body((), (f"- [[{TWO_SUBJECTS}]]",)))
        self.work(SURVEY, SUBJECT)
        self.work(CONTEXTUALIST, NARROWER)
        self.work(TWO_SUBJECTS, ELSEWHERE, NARROWER)
        self.work(ON_BOTH, SUBJECT, NARROWER)
        self.work(ON_A_DEEPER_ONE, NARROWER, BENEATH_SUBJECT)
        self.work(REVISIONIST, BENEATH_NARROWER)

    def work(self, basename: str, *names: str) -> None:
        creator, year, _title = basename.split(" - ")
        self.vault.note(basename, field=[f"[[{name}]]" for name in names], source_role="secondary",
                        title=basename, author=[creator], year=int(year))

    def answers(self, **given) -> ReshapeAnswers:
        return ReshapeAnswers.read(answers_file(self.scratch, **given))

    def fold(self, **given) -> dict:
        return Reshape(self.answers(fold=[fold(**given)])).apply()

    def field_of(self, basename: str) -> list[str]:
        return bibliographies.Corpus().note(basename).bibliographies

    def body_of(self, name: str) -> str:
        return self.vault.body_in(TOPICS, name)

    def maps_of(self, name: str) -> list[str]:
        return bibliographies.Section("Maps").lines_in(self.body_of(name))


class TestFoldingABibliographyIntoTheOneWhoseSubjectItNarrows(FoldingCase):
    def setUp(self) -> None:
        super().setUp()
        self.report = self.fold()

    def test_the_folded_bibliography_is_deleted(self) -> None:
        self.assertFalse((vault.BIBLIOGRAPHIES_DIR / TOPICS / f"{NARROWER}.md").exists())

    def test_a_work_moves_onto_the_target_under_the_group_with_its_gloss(self) -> None:
        group = self.body_of(SUBJECT).split(f"### {GROUP}")[1]
        self.assertIn(f"- [[{CONTEXTUALIST}]] — a contextual hierarchy of truth predicates.", group)
        self.assertEqual([SUBJECT], self.field_of(CONTEXTUALIST))

    def test_a_work_on_a_second_bibliography_keeps_it(self) -> None:
        self.assertEqual([ELSEWHERE, SUBJECT], self.field_of(TWO_SUBJECTS))
        self.assertIn(f"- [[{TWO_SUBJECTS}]]", self.body_of(ELSEWHERE))

    def test_a_work_the_target_already_lists_keeps_its_one_listing(self) -> None:
        self.assertEqual([SUBJECT], self.field_of(ON_BOTH))
        self.assertEqual(1, self.body_of(SUBJECT).count(f"[[{ON_BOTH}]]"))

    def test_a_work_on_a_bibliography_beneath_the_target_stays_off_the_target(self) -> None:
        self.assertEqual([BENEATH_SUBJECT], self.field_of(ON_A_DEEPER_ONE))
        self.assertNotIn(f"[[{ON_A_DEEPER_ONE}]]", self.body_of(SUBJECT))

    def test_the_folded_bibliographys_maps_move_beneath_the_target(self) -> None:
        self.assertIn(f"- [[{BENEATH_NARROWER}]]", self.maps_of(SUBJECT))
        self.assertEqual([REVISIONIST], [note.basename for note in bibliographies.Corpus().notes()
                                         if BENEATH_NARROWER in note.bibliographies])

    def test_no_maps_listing_names_the_folded_bibliography(self) -> None:
        for name in (DISCIPLINE, SUBJECT):
            self.assertNotIn(f"[[{NARROWER}]]", self.body_of(name))

    def test_no_corpus_file_names_the_folded_bibliography(self) -> None:
        self.assertFalse([note for note in bibliographies.Corpus().notes() if NARROWER in note.bibliographies])

    def test_the_check_finds_nothing_blocking(self) -> None:
        self.assertTrue(self.vault.report().is_clean, self.vault.printed_report())

    def test_the_report_names_the_fold_its_works_and_the_bibliographies_touched(self) -> None:
        folded = self.report["folded"][0]
        self.assertEqual((NARROWER, SUBJECT, GROUP), (folded["name"], folded["into"], folded["group"]))
        self.assertEqual(sorted([CONTEXTUALIST, TWO_SUBJECTS, ON_BOTH, ON_A_DEEPER_ONE]), folded["works"])
        self.assertTrue({NARROWER, SUBJECT} <= set(self.report["touched"]))


class TestTheReadOnlyFormOfAFold(FoldingCase):
    def test_it_reports_the_fold_and_writes_nothing(self) -> None:
        before = self.body_of(NARROWER)
        report = Reshape(self.answers(fold=[fold()])).plan()
        self.assertEqual(NARROWER, report["folded"][0]["name"])
        self.assertEqual(before, self.body_of(NARROWER))
        self.assertEqual([NARROWER], self.field_of(CONTEXTUALIST))


class TestRefusedFolds(FoldingCase):
    def refuse(self, **given) -> str:
        with self.assertRaises(ReshapeRefused) as refused:
            Reshape(self.answers(**given)).apply()
        return str(refused.exception)

    def test_an_unknown_bibliography_is_refused(self) -> None:
        self.assertIn("is not a bibliography", self.refuse(fold=[fold(into="Nowhere")]))

    def test_a_target_beneath_the_folded_bibliography_is_refused(self) -> None:
        self.assertIn("sits beneath", self.refuse(fold=[fold(into=BENEATH_NARROWER)]))

    def test_an_author_bibliography_is_refused(self) -> None:
        self.vault.bibliography_in("2 authors", "Kripke", body(), author="Kripke")
        self.assertIn("author bibliography", self.refuse(fold=[fold(name="Kripke")]))

    def test_a_bibliography_carrying_aliases_is_refused(self) -> None:
        self.vault.bibliography_in(TOPICS, ELSEWHERE, body(), aliases=["Ontology"])
        self.assertIn("aliases", self.refuse(fold=[fold(name=ELSEWHERE)]))

    def test_a_group_carrying_a_heading_mark_is_refused(self) -> None:
        self.assertIn("group", self.refuse(fold=[fold(group="Responses # two")]))

    def test_a_folded_bibliography_another_answer_names_is_refused(self) -> None:
        move = {"work": SURVEY, "from": SUBJECT, "to": NARROWER}
        self.assertIn("named by another answer", self.refuse(fold=[fold()], move=[move]))

    def test_a_target_folded_itself_is_refused(self) -> None:
        self.assertIn("folded itself", self.refuse(fold=[fold(), fold(SUBJECT, DISCIPLINE)]))

    def test_a_refusal_writes_nothing(self) -> None:
        self.refuse(fold=[fold(into="Nowhere")])
        self.assertTrue((vault.BIBLIOGRAPHIES_DIR / TOPICS / f"{NARROWER}.md").exists())


class TestFoldCandidates(FoldingCase):
    def found(self) -> list[tuple[str, str, str]]:
        candidates = FoldCandidates(bibliographies.Bibliographies(), bibliographies.Corpus().notes()).found()
        return [(candidate["narrower"], candidate["broader"], candidate["by"]) for candidate in candidates]

    def test_a_name_holding_every_word_of_another_is_a_candidate(self) -> None:
        self.assertIn((NARROWER, SUBJECT, "name"), self.found())

    def test_a_bibliography_beneath_one_whose_head_noun_it_names_is_a_candidate(self) -> None:
        self.vault.bibliography_in(TOPICS, "Philosophical Skepticism", body(("Domain-Specific Skepticism",)))
        self.vault.bibliography_in(TOPICS, "Domain-Specific Skepticism", body())
        for number in range(5):
            self.work(f"Doubter{number} - 200{number} - Doubts about One Domain {number}", "Domain-Specific Skepticism")
        self.assertIn(("Domain-Specific Skepticism", "Philosophical Skepticism", "head"), self.found())

    def test_a_candidate_by_its_wording_that_gathers_fewer_than_five_works_is_a_candidate_by_size(self) -> None:
        self.vault.bibliography_in(TOPICS, "Philosophical Skepticism", body(("Domain-Specific Skepticism",)))
        self.vault.bibliography_in(TOPICS, "Domain-Specific Skepticism", body())
        self.assertIn(("Domain-Specific Skepticism", "Philosophical Skepticism", "size"), self.found())

    def test_a_bibliography_with_its_own_subject_is_no_candidate_by_its_wording(self) -> None:
        self.assertFalse([found for found in self.found() if found[0] == BENEATH_NARROWER and found[2] != "size"])

    def test_a_candidate_names_the_narrower_works_and_those_shared(self) -> None:
        candidates = FoldCandidates(bibliographies.Bibliographies(), bibliographies.Corpus().notes()).found()
        candidate = next(item for item in candidates if item["narrower"] == NARROWER and item["broader"] == SUBJECT)
        self.assertEqual([ON_BOTH], candidate["shared"])
        self.assertIn(CONTEXTUALIST, candidate["works"])


class TestFoldCandidatesBySize(FoldingCase):
    def found(self) -> list[tuple[str, str, str]]:
        candidates = FoldCandidates(bibliographies.Bibliographies(), bibliographies.Corpus().notes()).found()
        return [(candidate["narrower"], candidate["broader"], candidate["by"]) for candidate in candidates]

    def four_more_works_on(self, name: str) -> None:
        for number in range(4):
            self.work(f"Reviser{number} - 200{number} - Revision Rules {number}", name)

    def test_a_bibliography_of_fewer_than_five_works_is_a_candidate_with_its_parent(self) -> None:
        self.assertIn((BENEATH_NARROWER, NARROWER, "size"), self.found())

    def test_a_bibliography_of_five_works_is_no_candidate(self) -> None:
        self.four_more_works_on(BENEATH_NARROWER)
        self.assertNotIn((BENEATH_NARROWER, NARROWER, "size"), self.found())

    def test_a_bibliography_gathering_five_works_beneath_it_is_no_candidate(self) -> None:
        self.assertNotIn((SUBJECT, DISCIPLINE, "size"), self.found())

    def test_a_primary_work_whose_author_carries_a_bibliography_is_not_counted(self) -> None:
        self.four_more_works_on(BENEATH_NARROWER)
        self.vault.bibliography_in("2 authors", "Gupta and Belnap", body(), author="Gupta and Belnap")
        self.vault.note(REVISIONIST, field=[f"[[{BENEATH_NARROWER}]]", "[[Gupta and Belnap]]"], source_role="primary",
                        title=REVISIONIST, author=["Gupta and Belnap"], year=1993)
        self.assertIn((BENEATH_NARROWER, NARROWER, "size"), self.found())


AUTHOR = "Kripke"
PART = "Kripke's Theory of Truth"
PART_GROUP = "Theory of Truth"
OWN_WORK = "Kripke - 1975 - Outline of a Theory of Truth"
READING = "Burgess - 1986 - The Truth Is Never Simple"
ANOTHER_AUTHOR = "Tarski"
ANOTHERS_OWN_WORK = "Tarski - 1944 - The Semantic Conception of Truth"


class TestFoldingABibliographyIntoAnAuthorBibliography(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.bibliography_in("2 authors", AUTHOR, f"## Maps\n\n- [[{PART}]]\n\n## Primary works\n\n"
                                   f"- [[{OWN_WORK}]] — the fixed-point construction.\n\n## Secondary literature\n\n"
                                   "*(none)*\n", author=AUTHOR)
        self.vault.bibliography_in("2 authors", ANOTHER_AUTHOR, f"## Maps\n\n## Primary works\n\n"
                                   f"- [[{ANOTHERS_OWN_WORK}]]\n", author=ANOTHER_AUTHOR)
        self.vault.bibliography_in(TOPICS, PART, f"## Maps\n\n## Primary works\n\n- [[{ANOTHERS_OWN_WORK}]]\n"
                                   f"- [[{OWN_WORK}]]\n\n## Secondary literature\n\n- [[{READING}]] — on the levels.\n")
        self.work(OWN_WORK, "primary", AUTHOR, PART)
        self.work(ANOTHERS_OWN_WORK, "primary", ANOTHER_AUTHOR, PART)
        self.work(READING, "secondary", PART)
        scratch = Path(tempfile.mkdtemp())
        Reshape(ReshapeAnswers.read(answers_file(scratch, fold=[fold(PART, AUTHOR, PART_GROUP)]))).apply()

    def work(self, basename: str, role: str, *names: str) -> None:
        creator, year, _title = basename.split(" - ")
        self.vault.note(basename, field=[f"[[{name}]]" for name in names], source_role=role, title=basename,
                        author=[creator], year=int(year))

    def list_under(self, heading: str) -> str:
        return bibliographies.Section(heading).content_in(self.vault.body_in("2 authors", AUTHOR))

    def test_the_authors_own_work_joins_the_group_among_the_primary_works_with_its_gloss(self) -> None:
        group = self.list_under("Primary works").split(f"### {PART_GROUP}")[1]
        self.assertIn(f"- [[{OWN_WORK}]] — the fixed-point construction.", group)
        self.assertEqual(1, self.vault.body_in("2 authors", AUTHOR).count(f"[[{OWN_WORK}]]"))

    def test_a_work_by_another_joins_the_group_among_the_secondary_literature(self) -> None:
        group = self.list_under("Secondary literature").split(f"### {PART_GROUP}")[1]
        self.assertIn(f"- [[{READING}]] — on the levels.", group)

    def test_a_primary_work_of_another_author_with_a_bibliography_stays_on_that_bibliography_alone(self) -> None:
        self.assertEqual([ANOTHER_AUTHOR], bibliographies.Corpus().note(ANOTHERS_OWN_WORK).bibliographies)
        self.assertNotIn(ANOTHERS_OWN_WORK, self.vault.body_in("2 authors", AUTHOR))

    def test_the_authors_own_work_sits_on_the_authors_bibliography_alone(self) -> None:
        self.assertEqual([AUTHOR], bibliographies.Corpus().note(OWN_WORK).bibliographies)

    def test_the_check_finds_nothing_blocking(self) -> None:
        self.assertTrue(self.vault.report().is_clean, self.vault.printed_report())


if __name__ == "__main__":
    unittest.main()
