from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import bibliographies
from _bibliographies.reshaping import Reshape, ReshapeAnswers, ReshapeRefused
from _bibliographies.routing import RoutingFindings
from _bibliography_fixtures import HEGEL, HOULGATE, TemporaryVault

THINKER = "Hegel"
PART = "Hegel's Logic"
OTHER_PART = "Hegel's Dialectic"
STERN = "Stern - 2023 - Understanding Hegel's Logic"
READINGS = (HOULGATE, STERN, "Burbidge - 1981 - On Hegel's Logic", "Winfield - 2012 - Hegel's Science of Logic")


class AuthorCatalogueCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.scratch = Path(tempfile.mkdtemp())
        self.vault.bibliography_in("2 authors", THINKER, f"## Maps\n\n- [[{PART}]]\n- [[{OTHER_PART}]]\n",
                                   author=THINKER)
        self.vault.bibliography_in("3 topics", PART, "## Maps\n\n## Secondary literature\n")
        self.vault.bibliography_in("3 topics", OTHER_PART, "## Maps\n\n## Secondary literature\n")

    def own_work(self, *field: str) -> None:
        self.vault.note(HEGEL, field=[f"[[{name}]]" for name in field], source_role="primary", author=[THINKER],
                        year=1969)

    def other_work(self, basename: str, *field: str) -> None:
        creator, year, _title = basename.split(" - ")
        self.vault.note(basename, field=[f"[[{name}]]" for name in field], source_role="secondary",
                        author=[creator], year=int(year))

    def reshape(self, **given) -> dict:
        path = self.scratch / "answers.json"
        path.write_text(json.dumps(given), encoding="utf-8")
        return Reshape(ReshapeAnswers.read(path)).apply()

    def field_of(self, basename: str) -> list[str]:
        return bibliographies.Corpus().note(basename).bibliographies


class TestAnAuthorsOwnWorkOnTheAuthorsBibliographyAndBeneathIt(AuthorCatalogueCase):
    def test_is_no_ancestor_placement(self) -> None:
        self.own_work(THINKER, PART)
        self.assertNotIn("Placement", self.vault.report().as_dict()["blocking"])

    def test_by_another_author_is_an_ancestor_placement(self) -> None:
        self.other_work(HOULGATE, THINKER, PART)
        self.assertIn("Placement", self.vault.report().as_dict()["blocking"])

    def test_roled_secondary_keeps_the_authors_bibliography_when_a_creation_beneath_it_takes_the_work(self) -> None:
        self.other_work(HEGEL, THINKER, PART)
        for basename in READINGS:
            self.other_work(basename, PART)
        self.reshape(create=[{"name": "Being", "kind": "topic", "parent": PART, "works": [HEGEL, *READINGS]}])
        self.assertEqual([THINKER, "Being"], self.field_of(HEGEL))

    def test_cannot_be_moved_off_the_authors_bibliography(self) -> None:
        self.own_work(THINKER)
        with self.assertRaises(ReshapeRefused) as refused:
            self.reshape(move=[{"work": HEGEL, "from": THINKER, "to": PART}])
        self.assertIn("its author's bibliography", str(refused.exception))


class TestAScholarsOwnWorkOnASubjectAndOnTheScholarsBibliographyBeneathIt(AuthorCatalogueCase):
    def test_is_no_ancestor_placement(self) -> None:
        self.vault.bibliography_in("3 topics", PART, "## Maps\n\n- [[Houlgate]]\n\n## Secondary literature\n")
        self.vault.bibliography_in("2 authors", "Houlgate", "## Maps\n", author="Houlgate")
        self.other_work(HOULGATE, PART, "Houlgate")
        self.assertNotIn("Placement", self.vault.report().as_dict()["blocking"])


class TestAnAuthorsWorkMissingFromTheAuthorsBibliography(AuthorCatalogueCase):
    def test_is_named_in_an_advisory_group(self) -> None:
        self.own_work(PART)
        advisory = self.vault.report().as_dict()["advisory"]
        self.assertEqual([f"{HEGEL}: not on ['{THINKER}']"], next(
            problems for heading, problems in advisory.items() if heading.startswith("Catalogue")))

    def test_is_added_to_it_by_the_reshaping(self) -> None:
        self.other_work(HEGEL, PART)
        self.reshape(add=[{"work": HEGEL, "to": THINKER}])
        self.assertEqual([PART, THINKER], self.field_of(HEGEL))
        self.assertIn(f"- [[{HEGEL}]]", bibliographies.Section("Primary works").lines_in(
            self.vault.body_in("2 authors", THINKER)))


class TestAnAdditionByTheReshaping(AuthorCatalogueCase):
    def test_places_the_work_on_a_second_bibliography(self) -> None:
        self.other_work(HOULGATE, PART)
        report = self.reshape(add=[{"work": HOULGATE, "to": OTHER_PART}])
        self.assertEqual([PART, OTHER_PART], self.field_of(HOULGATE))
        self.assertEqual([{"work": HOULGATE, "to": OTHER_PART}], report["added"])

    def test_onto_an_ancestor_of_a_bibliography_the_work_sits_on_is_refused(self) -> None:
        self.other_work(HOULGATE, PART)
        with self.assertRaises(ReshapeRefused) as refused:
            self.reshape(add=[{"work": HOULGATE, "to": THINKER}])
        self.assertIn("one line of descent", str(refused.exception))


class TestAPrimaryWorkWhoseAuthorCarriesABibliography(AuthorCatalogueCase):
    def refused(self, **given) -> str:
        with self.assertRaises(ReshapeRefused) as refused:
            self.reshape(**given)
        return str(refused.exception)

    def test_is_taken_off_every_other_bibliography_by_the_reshaping(self) -> None:
        self.own_work(THINKER, PART)
        self.vault.place(HEGEL)
        report = self.reshape()
        self.assertEqual([THINKER], self.field_of(HEGEL))
        self.assertNotIn(HEGEL, self.vault.body_in("3 topics", PART))
        self.assertEqual([{"work": HEGEL, "from": PART, "to": THINKER}], report["moved"])

    def test_roled_secondary_stays_on_the_other_bibliography(self) -> None:
        self.other_work(HEGEL, THINKER, PART)
        self.assertEqual([], self.reshape()["moved"])
        self.assertEqual([THINKER, PART], self.field_of(HEGEL))

    def test_by_an_author_without_a_bibliography_stays_where_it_sits(self) -> None:
        self.vault.note(STERN, field=[f"[[{PART}]]"], source_role="primary", author=["Stern"], year=2023)
        self.assertEqual([], self.reshape()["moved"])

    def test_on_another_bibliography_is_named_in_an_advisory_group(self) -> None:
        self.own_work(THINKER, PART)
        advisory = self.vault.report().as_dict()["advisory"]
        self.assertEqual([f"{HEGEL}: sits on [[{PART}]] as well"],
                         advisory["Catalogue -- a primary work off its author's bibliography"])

    def test_is_refused_among_the_works_of_a_creation(self) -> None:
        self.own_work(THINKER)
        for basename in READINGS:
            self.other_work(basename, PART)
        creation = {"name": "Being", "kind": "topic", "parent": PART, "works": [HEGEL, *READINGS]}
        self.assertIn("author's bibliography alone", self.refused(create=[creation]))

    def test_is_refused_as_an_added_placement(self) -> None:
        self.own_work(THINKER)
        self.assertIn("author's bibliography alone", self.refused(add=[{"work": HEGEL, "to": OTHER_PART}]))

    def test_is_no_routing_placement(self) -> None:
        self.own_work(THINKER, PART)
        self.vault.bibliography_in("3 topics", PART, f"## Maps\n\n- [[{OTHER_PART}]]\n")
        findings = RoutingFindings(bibliographies.Bibliographies(), bibliographies.Corpus().notes())
        self.assertEqual([], findings.routing_placements())
        self.assertEqual([{"work": HEGEL, "on": [PART]}], findings.stray_placements())


if __name__ == "__main__":
    unittest.main()
