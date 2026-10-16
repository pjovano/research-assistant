from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import bibliographies
import vault
from _bibliographies.glossing import (
    KIND_AUTHOR,
    KIND_PERIOD,
    KIND_TOPIC,
    Descriptions,
    GlossCopy,
    GlossPlan,
    Introduction,
    ListedWorks,
)
from _bibliographies.introducing import (
    MAX_GROUP_NOTE_WORDS,
    MAX_INTRODUCTION_WORDS,
    IntroductionListing,
    IntroductionWrite,
)
from _bibliographies.placement import WorkOrder
from _bibliography_fixtures import HEGEL, HOULGATE, TemporaryVault

PIPPIN = "Pippin - 2019 - Hegel's Realm of Shadows"
STERN = "Stern - 2023 - Understanding Hegel's Logic"
LOGIC = "Logic"
IDEALISM = "German Idealism"
ETHICS = "Ethics"
HEGEL_BIBLIOGRAPHY = "Hegel"
SECONDARY = "Secondary literature"
OPENINGS = "Openings"
METAPHYSICAL = "Metaphysical Readings"
HEGEL_DESCRIPTION = "Opens the science of logic with being (Hegel 1812, p. 11)."
HOULGATE_DESCRIPTION = "Reads the opening as presuppositionless (Houlgate 2006, p. 29)."
STALE_GLOSS = "Reads the Logic some other way (Houlgate 2006, p. 3)."
PIPPIN_GLOSS = "Reads the Logic as metaphysics (Pippin 2019, p. 5)."
LOGIC_INTRODUCTION = "The Logic bibliography."
NEW_INTRODUCTION = "Works on the science of logic and its opening."
LOGIC_BODY = (f"{LOGIC_INTRODUCTION}\n\n## Maps\n\n## {SECONDARY}\n\n- [[{HEGEL}]]\n"
              f"- [[{HOULGATE}]] — {STALE_GLOSS}\n- [[{PIPPIN}]] — {PIPPIN_GLOSS}\n")
GROUPED_BODY = (f"## Maps\n\n## {SECONDARY}\n\n### {OPENINGS}\n\nReadings of the opening.\n\n- [[{HOULGATE}]]\n\n"
                f"### Unsorted\n\n- [[{HEGEL}]]\n- [[{PIPPIN}]]\n")


class GlossingVault(TemporaryVault):
    def work(self, basename: str, **meta) -> None:
        defaults = {"title": basename.split(" - ")[-1], "author": [basename.split(" - ")[0]],
                    "year": int(basename.split(" - ")[1])}
        vault.write_frontmatter(vault.CORPUS_DIR / f"{basename}.md", {**defaults, **meta}, "")

    def copy(self) -> GlossCopy:
        return GlossCopy(bibliographies.Bibliographies(), Descriptions(bibliographies.Corpus()))

    def copied(self) -> list[str]:
        changes = self.copy().changes()
        for change in changes:
            change.write()
        return [change.name for change in changes]

    def plan(self) -> GlossPlan:
        return GlossPlan(bibliographies.Bibliographies(), bibliographies.Corpus())

    def listing(self, name: str) -> dict:
        return IntroductionListing(bibliographies.Bibliographies(), bibliographies.Corpus()).of(name)

    def write(self, name: str, answers: dict) -> IntroductionWrite:
        order = WorkOrder(bibliographies.Corpus())
        return IntroductionWrite(bibliographies.Bibliographies().named(name), answers, order)


class GlossingCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = GlossingVault(self)
        self.vault.bibliography_in("1 historical periods", IDEALISM, f"## Maps\n\n- [[{LOGIC}]] — The logic.\n")
        self.vault.bibliography_in("3 topics", LOGIC, LOGIC_BODY)
        self.vault.work(HEGEL, field=[f"[[{LOGIC}]]"], orig_year=1812, description=HEGEL_DESCRIPTION)
        self.vault.work(HOULGATE, field=[f"[[{LOGIC}]]"], description=HOULGATE_DESCRIPTION)
        self.vault.work(PIPPIN, field=[f"[[{LOGIC}]]"])

    def logic(self) -> str:
        return self.vault.body_in("3 topics", LOGIC)

    def grouped(self) -> None:
        self.vault.bibliography_in("3 topics", LOGIC, GROUPED_BODY)


class TestCopyingTheDescriptions(GlossingCase):
    def test_a_listing_without_a_gloss_takes_its_works_description(self) -> None:
        self.vault.copied()
        self.assertIn(f"- [[{HEGEL}]] — {HEGEL_DESCRIPTION}\n", self.logic())

    def test_a_gloss_other_than_the_description_is_replaced_by_it(self) -> None:
        self.vault.copied()
        self.assertIn(f"- [[{HOULGATE}]] — {HOULGATE_DESCRIPTION}\n", self.logic())
        self.assertNotIn(STALE_GLOSS, self.logic())

    def test_a_listing_whose_work_carries_no_description_keeps_its_line(self) -> None:
        self.vault.copied()
        self.assertIn(f"- [[{PIPPIN}]] — {PIPPIN_GLOSS}\n", self.logic())

    def test_a_description_written_over_several_lines_is_copied_as_one(self) -> None:
        self.vault.work(HEGEL, field=[f"[[{LOGIC}]]"], description="Opens with being\n  (Hegel 1812, p. 11).")
        self.vault.copied()
        self.assertIn(f"- [[{HEGEL}]] — Opens with being (Hegel 1812, p. 11).\n", self.logic())

    def test_a_maps_listing_is_left_as_it_stands(self) -> None:
        self.vault.note(LOGIC, description="A work named as the map is.")
        self.vault.copied()
        self.assertIn(f"- [[{LOGIC}]] — The logic.\n", self.vault.body_in("1 historical periods", IDEALISM))

    def test_only_the_bibliographies_a_description_changes_are_written(self) -> None:
        self.assertEqual([LOGIC], self.vault.copied())

    def test_a_bibliography_carrying_its_descriptions_is_changed_no_further(self) -> None:
        self.vault.copied()
        self.assertEqual([], self.vault.copied())

    def test_the_introduction_and_the_headings_survive_the_copy(self) -> None:
        self.vault.copied()
        self.assertTrue(self.logic().lstrip().startswith(f"{LOGIC_INTRODUCTION}\n\n## Maps\n\n## {SECONDARY}\n\n"))


class TestThePlan(GlossingCase):
    def introduced(self) -> None:
        self.vault.bibliography_in("1 historical periods", IDEALISM, f"The idealists.\n\n## Maps\n\n- [[{LOGIC}]]\n")

    def test_the_bibliographies_a_placed_work_sits_on_are_planned(self) -> None:
        self.introduced()
        self.assertEqual([LOGIC], self.vault.plan().for_works([HEGEL]))

    def test_a_bibliography_the_reshaping_touched_is_planned(self) -> None:
        self.introduced()
        self.assertEqual([IDEALISM], self.vault.plan().for_works([], [IDEALISM]))

    def test_a_bibliography_without_an_introduction_is_planned_whatever_was_placed(self) -> None:
        self.assertEqual([IDEALISM], self.vault.plan().for_works([]))

    def test_an_introduced_bibliography_nothing_touched_is_not_planned(self) -> None:
        self.introduced()
        self.assertEqual([], self.vault.plan().for_works([]))

    def test_a_bibliography_listing_no_work_and_no_map_is_never_planned(self) -> None:
        self.vault.bibliography_in("3 topics", ETHICS, f"## Maps\n\n## {SECONDARY}\n")
        self.assertNotIn(ETHICS, self.vault.plan().for_works([], [ETHICS]))
        self.assertNotIn(ETHICS, self.vault.plan().for_all())

    def test_every_bibliography_listing_a_work_or_a_map_is_planned_with_all(self) -> None:
        self.introduced()
        self.assertEqual([IDEALISM, LOGIC], self.vault.plan().for_all())


class TestTheBibliographyIntroducersListing(GlossingCase):
    def test_the_listing_carries_the_kind_and_the_introduction(self) -> None:
        listing = self.vault.listing(LOGIC)
        self.assertEqual((KIND_TOPIC, LOGIC_INTRODUCTION), (listing["kind"], listing["introduction"]))

    def test_a_period_and_an_author_bibliography_are_of_their_kinds(self) -> None:
        self.vault.bibliography_in("2 authors", HEGEL_BIBLIOGRAPHY, f"## Primary works\n\n- [[{HEGEL}]]\n",
                                   author="Hegel")
        kinds = [self.vault.listing(name)["kind"] for name in (IDEALISM, HEGEL_BIBLIOGRAPHY)]
        self.assertEqual([KIND_PERIOD, KIND_AUTHOR], kinds)

    def test_each_map_comes_with_its_own_introduction(self) -> None:
        self.assertEqual([{"name": LOGIC, "introduction": LOGIC_INTRODUCTION}], self.vault.listing(IDEALISM)["maps"])

    def test_each_work_comes_with_its_description_and_the_year_it_was_written(self) -> None:
        works = {work["basename"]: work for work in self.vault.listing(LOGIC)["works"]}
        self.assertEqual((HEGEL_DESCRIPTION, 1812), (works[HEGEL]["description"], works[HEGEL]["year"]))
        self.assertIsNone(works[PIPPIN]["description"])

    def test_each_group_comes_with_its_note(self) -> None:
        self.grouped()
        self.assertEqual([{"section": SECONDARY, "title": OPENINGS, "note": "Readings of the opening."}],
                         self.vault.listing(LOGIC)["groups"])

    def test_the_works_of_the_unsorted_group_are_named_as_unsorted(self) -> None:
        self.grouped()
        self.assertEqual([HEGEL, PIPPIN], self.vault.listing(LOGIC)["unsorted"])

    def test_a_list_of_works_without_groups_holds_no_unsorted_work(self) -> None:
        self.assertEqual([], self.vault.listing(LOGIC)["unsorted"])


class TestWritingTheIntroduction(GlossingCase):
    def written(self, answers: dict) -> str:
        write = self.vault.write(LOGIC, answers)
        self.assertEqual([], write.problems())
        write.write()
        return self.logic()

    def test_the_introduction_replaces_the_one_before_the_first_section(self) -> None:
        body = self.written({"introduction": NEW_INTRODUCTION})
        self.assertTrue(body.lstrip().startswith(f"{NEW_INTRODUCTION}\n\n## Maps\n"))
        self.assertNotIn(LOGIC_INTRODUCTION, body)

    def test_the_listings_stand_as_they_stood(self) -> None:
        before = ListedWorks(self.logic()).all()
        self.assertEqual(before, ListedWorks(self.written({"introduction": NEW_INTRODUCTION})).all())

    def test_the_frontmatter_survives_the_write(self) -> None:
        self.written({"introduction": NEW_INTRODUCTION})
        text = (vault.BIBLIOGRAPHIES_DIR / "3 topics" / f"{LOGIC}.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))

    def test_an_empty_introduction_is_a_problem(self) -> None:
        self.assertEqual(["the introduction is empty"], self.vault.write(LOGIC, {"introduction": " "}).problems())

    def test_an_introduction_over_the_word_limit_is_a_problem(self) -> None:
        long = " ".join(["word"] * (MAX_INTRODUCTION_WORDS + 1))
        self.assertEqual([f"the introduction runs over {MAX_INTRODUCTION_WORDS} words"],
                         self.vault.write(LOGIC, {"introduction": long}).problems())

    def test_an_introduction_at_the_word_limit_is_none(self) -> None:
        at_limit = " ".join(["word"] * MAX_INTRODUCTION_WORDS)
        self.assertEqual([], self.vault.write(LOGIC, {"introduction": at_limit}).problems())

    def test_an_introduction_of_two_paragraphs_is_a_problem(self) -> None:
        problems = self.vault.write(LOGIC, {"introduction": "One.\n\nTwo."}).problems()
        self.assertEqual(["the introduction runs over one paragraph"], problems)

    def test_an_introduction_naming_a_listed_work_is_a_problem(self) -> None:
        problems = self.vault.write(LOGIC, {"introduction": f"[[{HEGEL}]] opens with being."}).problems()
        self.assertEqual(["the introduction names a listed work; it says what the works share"], problems)


class TestWritingTheGroupNotesAndTheGroups(GlossingCase):
    def setUp(self) -> None:
        super().setUp()
        self.grouped()

    def written(self, **answers) -> str:
        write = self.vault.write(LOGIC, {"introduction": NEW_INTRODUCTION, **answers})
        self.assertEqual([], write.problems())
        write.write()
        return self.logic()

    def problems(self, **answers) -> list[str]:
        return self.vault.write(LOGIC, {"introduction": NEW_INTRODUCTION, **answers}).problems()

    def test_a_note_replaces_the_one_beneath_its_groups_heading(self) -> None:
        body = self.written(groups=[{"section": SECONDARY, "title": OPENINGS, "note": "How the Logic begins."}])
        self.assertIn(f"### {OPENINGS}\n\nHow the Logic begins.\n\n- [[{HOULGATE}]]\n\n### Unsorted\n", body)
        self.assertNotIn("Readings of the opening.", body)

    def test_a_note_on_the_last_group_keeps_the_next_section_apart(self) -> None:
        self.vault.bibliography_in("3 topics", LOGIC, f"## {SECONDARY}\n\n### {OPENINGS}\n\n- [[{HOULGATE}]]\n\n"
                                   f"## Talk transcripts\n\n- [[{PIPPIN}]]\n")
        body = self.written(groups=[{"section": SECONDARY, "title": OPENINGS, "note": "How the Logic begins."}])
        self.assertIn(f"How the Logic begins.\n\n- [[{HOULGATE}]]\n\n## Talk transcripts\n", body)

    def test_an_unsorted_work_moves_into_the_group_named_for_it(self) -> None:
        listed = ListedWorks(self.written(sorted=[{"basename": HEGEL, "group": OPENINGS}]))
        self.assertEqual({HEGEL: OPENINGS, HOULGATE: OPENINGS, PIPPIN: "Unsorted"},
                         {listing.basename: listing.group for listing in listed.all()})

    def test_a_group_no_list_carries_is_opened_before_the_unsorted_group(self) -> None:
        listed = ListedWorks(self.written(sorted=[{"basename": PIPPIN, "group": METAPHYSICAL}]))
        self.assertEqual([OPENINGS, METAPHYSICAL, "Unsorted"], listed.groups())

    def test_the_unsorted_group_goes_once_its_last_work_is_sorted(self) -> None:
        body = self.written(sorted=[{"basename": HEGEL, "group": OPENINGS}, {"basename": PIPPIN, "group": OPENINGS}])
        self.assertNotIn("Unsorted", body)

    def test_a_group_opened_by_a_sorting_takes_a_note(self) -> None:
        body = self.written(sorted=[{"basename": PIPPIN, "group": METAPHYSICAL}],
                            groups=[{"section": SECONDARY, "title": METAPHYSICAL, "note": "The Logic as ontology."}])
        self.assertIn(f"### {METAPHYSICAL}\n\nThe Logic as ontology.\n\n- [[{PIPPIN}]]\n", body)

    def test_a_note_on_a_group_no_list_carries_is_a_problem(self) -> None:
        problems = self.problems(groups=[{"section": SECONDARY, "title": METAPHYSICAL, "note": "A note."}])
        self.assertEqual([f"the note on ### {METAPHYSICAL}: ## {SECONDARY} carries no such group"], problems)

    def test_a_note_on_the_unsorted_group_is_a_problem(self) -> None:
        problems = self.problems(groups=[{"section": SECONDARY, "title": "Unsorted", "note": "A note."}])
        self.assertEqual([f"the note on ### Unsorted: ## {SECONDARY} carries no such group"], problems)

    def test_a_note_over_the_word_limit_is_a_problem(self) -> None:
        long = " ".join(["word"] * (MAX_GROUP_NOTE_WORDS + 1))
        problems = self.problems(groups=[{"section": SECONDARY, "title": OPENINGS, "note": long}])
        self.assertEqual([f"the note on ### {OPENINGS} runs over {MAX_GROUP_NOTE_WORDS} words"], problems)

    def test_sorting_a_work_that_already_sits_in_a_group_is_a_problem(self) -> None:
        problems = self.problems(sorted=[{"basename": HOULGATE, "group": METAPHYSICAL}])
        self.assertEqual([f"[[{HOULGATE}]] is no unsorted listing of a list of works that carries groups"], problems)

    def test_sorting_a_work_into_the_unsorted_group_is_a_problem(self) -> None:
        problems = self.problems(sorted=[{"basename": HEGEL, "group": "Unsorted"}])
        self.assertEqual([f"[[{HEGEL}]] is sorted into no group"], problems)


class TestListedWorksAndIntroduction(unittest.TestCase):
    def test_a_gloss_is_the_text_after_the_wikilink_and_its_dash(self) -> None:
        listed = ListedWorks(LOGIC_BODY).all()
        self.assertEqual(STALE_GLOSS, listed[1].gloss)
        self.assertEqual("", listed[0].gloss)

    def test_a_group_is_carried_by_the_listings_beneath_it(self) -> None:
        self.assertEqual([OPENINGS, "Unsorted", "Unsorted"], [item.group for item in ListedWorks(GROUPED_BODY).all()])
        self.assertEqual([OPENINGS, "Unsorted"], ListedWorks(GROUPED_BODY).groups())

    def test_the_introduction_is_the_text_before_the_first_section(self) -> None:
        self.assertEqual(LOGIC_INTRODUCTION, Introduction(LOGIC_BODY).text())

    def test_a_body_without_a_section_is_all_introduction(self) -> None:
        self.assertEqual(f"{NEW_INTRODUCTION}\n", Introduction(LOGIC_INTRODUCTION).replaced_by(NEW_INTRODUCTION))


if __name__ == "__main__":
    unittest.main()
