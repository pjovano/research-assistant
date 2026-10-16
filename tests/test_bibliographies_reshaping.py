from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import bibliographies
import vault
from citation_graph import GraphStore
from _bibliographies.reshaping import MapsList, Reshape, ReshapeAnswers, ReshapeRefused, ShapeListing, WorkListRemoval
from _bibliography_fixtures import HEGEL, HOULGATE, TemporaryVault

PIPPIN = "Pippin - 2019 - Hegel's Realm of Shadows"
STERN = "Stern - 2023 - Understanding Hegel's Logic"
BURBIDGE = "Burbidge - 1981 - On Hegel's Logic"
WINFIELD = "Winfield - 2012 - Hegel's Science of Logic"
SHARING_A_SUBJECT = (HOULGATE, PIPPIN, STERN, BURBIDGE, WINFIELD)
UNPLACED = "Rosen - 2014 - The Idea of Hegel's Science of Logic"
DISCIPLINE = "Philosophy of Logic"
LOGIC = "Logic"
IDEALISM = "German Idealism"
BEGINNING = "The Beginning of the Logic"
LOGIC_BODY = (f"## Maps\n\n## Secondary literature\n\n- [[{HEGEL}]]\n- [[{BURBIDGE}]]\n- [[{HOULGATE}]] — on the opening.\n"
              f"- [[{WINFIELD}]]\n- [[{PIPPIN}]]\n- [[{STERN}]]\n")


def answers_file(directory: Path, **given) -> Path:
    path = directory / "answers.json"
    path.write_text(json.dumps({"create": [], "move": [], "questions": [], **given}), encoding="utf-8")
    return path


def creation(name: str = BEGINNING, parent: str | None = LOGIC, works: tuple[str, ...] = SHARING_A_SUBJECT,
             kind: str = "topic", author: str | None = None) -> dict:
    return {"name": name, "kind": kind, "parent": parent, "author": author, "works": list(works)}


class ReshapingCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.scratch = Path(tempfile.mkdtemp())
        self.vault.bibliography_in("1 historical periods", IDEALISM, f"## Maps\n\n- [[{LOGIC}]]\n")
        self.vault.bibliography_in("3 topics", LOGIC, LOGIC_BODY)
        for basename in (HEGEL, *SHARING_A_SUBJECT):
            self.vault.note(basename, field=[f"[[{LOGIC}]]"], source_role="secondary", title=basename,
                            author=[basename.split(" - ")[0]], year=int(basename.split(" - ")[1]))

    def reshape(self, **given) -> dict:
        return Reshape(ReshapeAnswers.read(answers_file(self.scratch, **given))).apply()

    def field_of(self, basename: str) -> list[str]:
        return bibliographies.Corpus().note(basename).bibliographies

    def body_of(self, folder: str, name: str) -> str:
        return self.vault.body_in(folder, name)


class TestCreatingABibliography(ReshapingCase):
    def test_the_file_sits_in_the_folder_of_its_kind_with_its_lists(self) -> None:
        self.reshape(create=[creation()])
        body = self.body_of("3 topics", BEGINNING)
        self.assertIn("## Maps", body)
        self.assertIn("## Secondary literature", body)

    def test_an_author_bibliography_carries_author_and_the_two_lists(self) -> None:
        self.reshape(create=[creation("Houlgate", IDEALISM, kind="author", author="Houlgate")])
        meta, body = vault.read_frontmatter(vault.BIBLIOGRAPHIES_DIR / "2 authors" / "Houlgate.md")
        self.assertEqual("Houlgate", meta["author"])
        self.assertIn("## Primary works", body)
        self.assertIn("## Secondary literature", body)

    def test_the_parent_lists_the_creation_under_its_maps(self) -> None:
        self.reshape(create=[creation()])
        self.assertIn(f"- [[{BEGINNING}]]", bibliographies.Section("Maps").lines_in(self.body_of("3 topics", LOGIC)))

    def test_the_works_move_from_the_parent_to_the_creation(self) -> None:
        self.reshape(create=[creation()])
        self.assertEqual([BEGINNING], self.field_of(HOULGATE))
        self.assertIn(f"- [[{HOULGATE}]]", self.body_of("3 topics", BEGINNING))
        self.assertNotIn(HOULGATE, self.body_of("3 topics", LOGIC))

    def test_a_work_not_named_stays_where_it_was(self) -> None:
        self.reshape(create=[creation()])
        self.assertEqual([LOGIC], self.field_of(HEGEL))
        self.assertIn(f"- [[{HEGEL}]]", self.body_of("3 topics", LOGIC))

    def test_the_report_names_the_bibliographies_touched_and_the_works_moved(self) -> None:
        report = self.reshape(create=[creation()])
        self.assertEqual([BEGINNING], report["created"])
        self.assertEqual(sorted([BEGINNING, LOGIC]), report["touched"])
        self.assertEqual(sorted(SHARING_A_SUBJECT), report["works"])


class TestMovingAWork(ReshapingCase):
    def setUp(self) -> None:
        super().setUp()
        self.vault.bibliography_in("3 topics", "Dialectic", "## Maps\n\n## Secondary literature\n\n*(none)*\n")

    def test_the_work_leaves_its_source_and_joins_its_target(self) -> None:
        self.reshape(move=[{"work": HEGEL, "from": LOGIC, "to": "Dialectic"}])
        self.assertEqual(["Dialectic"], self.field_of(HEGEL))
        self.assertNotIn(HEGEL, self.body_of("3 topics", LOGIC))
        self.assertIn(f"- [[{HEGEL}]]", self.body_of("3 topics", "Dialectic"))

    def test_the_other_listings_keep_their_glosses(self) -> None:
        self.reshape(move=[{"work": HEGEL, "from": LOGIC, "to": "Dialectic"}])
        self.assertIn(f"- [[{HOULGATE}]] — on the opening.", self.body_of("3 topics", LOGIC))


class TestRefusals(ReshapingCase):
    def refuse(self, **given) -> str:
        with self.assertRaises(ReshapeRefused) as refused:
            self.reshape(**given)
        return str(refused.exception)

    def test_a_name_in_use_is_refused(self) -> None:
        self.assertIn("no new name", self.refuse(create=[creation(LOGIC)]))

    def test_four_works_that_share_a_subject_are_refused(self) -> None:
        self.assertIn("needs 5 works", self.refuse(create=[creation(works=SHARING_A_SUBJECT[:4])]))

    def test_five_works_that_share_a_subject_are_kept(self) -> None:
        self.assertEqual([BEGINNING], self.reshape(create=[creation()])["created"])

    def test_an_unknown_parent_is_refused(self) -> None:
        self.assertIn("is not a bibliography", self.refuse(create=[creation(parent="Nowhere")]))

    def test_an_author_bibliography_without_an_author_is_refused(self) -> None:
        self.assertIn("carries author", self.refuse(create=[creation(kind="author")]))

    def test_a_work_without_a_corpus_file_is_refused(self) -> None:
        self.assertIn("no corpus file", self.refuse(move=[{"work": "Nobody - 1999 - Nothing", "from": LOGIC,
                                                            "to": LOGIC}]))

    def test_a_refusal_writes_nothing(self) -> None:
        self.refuse(create=[creation(LOGIC)])
        self.assertEqual(LOGIC_BODY.strip(), self.body_of("3 topics", LOGIC).strip())

    def test_a_parent_created_in_the_same_answers_is_known(self) -> None:
        report = self.reshape(create=[creation("Readings", IDEALISM), creation("Openings", "Readings")])
        self.assertEqual(["Readings", "Openings"], report["created"])

    def test_a_topic_creation_below_the_third_tier_is_kept(self) -> None:
        report = self.reshape(create=[creation("Readings", LOGIC, ()), creation("Openings", "Readings")])
        self.assertEqual(["Readings", "Openings"], report["created"])

    def test_a_period_beneath_a_period_is_kept(self) -> None:
        report = self.reshape(create=[creation("School", IDEALISM, kind="period")])
        self.assertIn("- [[School]]", bibliographies.Section("Maps").lines_in(
            self.body_of("1 historical periods", IDEALISM)))
        self.assertEqual(["School"], report["created"])

    def test_an_author_creation_on_the_fourth_tier_is_kept(self) -> None:
        report = self.reshape(create=[creation("Readings", LOGIC, ()),
                                      creation("Houlgate", "Readings", kind="author", author="Houlgate")])
        self.assertEqual(["Readings", "Houlgate"], report["created"])

    def test_an_author_creation_below_the_fourth_tier_is_kept(self) -> None:
        report = self.reshape(create=[creation("Readings", LOGIC, ()), creation("Openings", "Readings", ()),
                                      creation("Houlgate", "Openings", kind="author", author="Houlgate")])
        self.assertEqual(["Readings", "Openings", "Houlgate"], report["created"])

    def test_an_author_root_is_refused(self) -> None:
        self.assertIn("a root is a discipline or a period",
                      self.refuse(create=[creation("Houlgate", None, kind="author", author="Houlgate")]))


class TestLinkingABibliographyUnderASecondParent(ReshapingCase):
    def setUp(self) -> None:
        super().setUp()
        self.vault.bibliography_in("3 topics", DISCIPLINE, "## Maps\n\n## Secondary literature\n")

    def maps_of(self, folder: str, name: str) -> list[str]:
        return bibliographies.Section("Maps").lines_in(self.body_of(folder, name))

    def test_the_second_parent_lists_it_and_the_first_keeps_it(self) -> None:
        self.reshape(link=[{"name": LOGIC, "parent": DISCIPLINE}])
        self.assertIn(f"- [[{LOGIC}]]", self.maps_of("3 topics", DISCIPLINE))
        self.assertIn(f"- [[{LOGIC}]]", self.maps_of("1 historical periods", IDEALISM))

    def test_the_report_names_the_link_and_both_bibliographies_touched(self) -> None:
        report = self.reshape(link=[{"name": LOGIC, "parent": DISCIPLINE}])
        self.assertEqual([{"name": LOGIC, "parent": DISCIPLINE}], report["linked"])
        self.assertTrue({LOGIC, DISCIPLINE} <= set(report["touched"]))

    def test_a_new_root_gathers_the_works_on_the_bibliographies_linked_beneath_it(self) -> None:
        report = self.reshape(create=[creation("Philosophy", None, ())], link=[{"name": LOGIC, "parent": "Philosophy"}])
        self.assertEqual(["Philosophy"], report["created"])
        self.assertIn(f"- [[{LOGIC}]]", self.maps_of("3 topics", "Philosophy"))

    def test_a_link_that_sets_a_bibliography_beneath_itself_is_refused(self) -> None:
        self.assertIn("sits beneath itself", self.refuse(link=[{"name": IDEALISM, "parent": LOGIC}]))

    def test_a_link_to_no_bibliography_is_refused(self) -> None:
        self.assertIn("is not a bibliography", self.refuse(link=[{"name": LOGIC, "parent": "Nowhere"}]))

    def refuse(self, **given) -> str:
        with self.assertRaises(ReshapeRefused) as refused:
            self.reshape(**given)
        return str(refused.exception)


class TestUnlinkingABibliographyFromAParent(ReshapingCase):
    def setUp(self) -> None:
        super().setUp()
        self.vault.bibliography_in("2 authors", "Houlgate", "## Maps\n\n## Primary works\n\n## Secondary literature\n",
                                   author="Houlgate")
        self.vault.bibliography_in("1 historical periods", IDEALISM, f"## Maps\n\n- [[Houlgate]]\n- [[{LOGIC}]]\n")

    def test_the_parent_no_longer_lists_it(self) -> None:
        self.reshape(link=[{"name": "Houlgate", "parent": LOGIC}], unlink=[{"name": "Houlgate", "parent": IDEALISM}])
        maps = bibliographies.Section("Maps").lines_in(self.body_of("1 historical periods", IDEALISM))
        self.assertEqual([f"- [[{LOGIC}]]"], maps)

    def test_an_author_bibliography_left_with_no_parent_is_refused(self) -> None:
        with self.assertRaises(ReshapeRefused) as refused:
            self.reshape(unlink=[{"name": "Houlgate", "parent": IDEALISM}])
        self.assertIn("no bibliography lists", str(refused.exception))

    def test_unlinking_from_a_bibliography_that_does_not_list_it_is_refused(self) -> None:
        with self.assertRaises(ReshapeRefused) as refused:
            self.reshape(link=[{"name": "Houlgate", "parent": LOGIC}], unlink=[{"name": "Houlgate", "parent": LOGIC}])
        self.assertIn("does not list", str(refused.exception))


class TestALinkThatMakesABibliographyAWorkSitsOnAnAncestorOfAnother(ReshapingCase):
    def setUp(self) -> None:
        super().setUp()
        self.vault.bibliography_in("3 topics", BEGINNING, f"## Maps\n\n## Secondary literature\n\n- [[{HOULGATE}]]\n")
        self.vault.bibliography_in("1 historical periods", IDEALISM, f"## Maps\n\n- [[{BEGINNING}]]\n- [[{LOGIC}]]\n")
        self.vault.note(HOULGATE, field=[f"[[{LOGIC}]]", f"[[{BEGINNING}]]"], source_role="secondary",
                        title=HOULGATE, author=["Houlgate"], year=2006)
        self.reshape(link=[{"name": BEGINNING, "parent": LOGIC}], unlink=[{"name": BEGINNING, "parent": IDEALISM}])

    def test_the_work_keeps_the_deeper_bibliography_alone(self) -> None:
        self.assertEqual([BEGINNING], self.field_of(HOULGATE))

    def test_the_ancestor_no_longer_lists_the_work(self) -> None:
        self.assertNotIn(f"[[{HOULGATE}]]", self.body_of("3 topics", LOGIC).split("## Secondary literature")[1])

    def test_a_work_beneath_no_link_is_untouched(self) -> None:
        self.assertEqual([LOGIC], self.field_of(PIPPIN))


class TestALinkThatSetsAnAuthorsOwnBibliographyBeneathOneTheWorkSitsOn(ReshapingCase):
    def setUp(self) -> None:
        super().setUp()
        self.vault.bibliography_in("2 authors", "Houlgate", f"## Maps\n\n## Primary works\n\n- [[{HOULGATE}]]\n",
                                   author="Houlgate")
        self.vault.bibliography_in("1 historical periods", IDEALISM, f"## Maps\n\n- [[Houlgate]]\n- [[{LOGIC}]]\n")
        self.vault.note(HOULGATE, field=[f"[[{LOGIC}]]", "[[Houlgate]]"], source_role="secondary", title=HOULGATE,
                        author=["Houlgate"], year=2006)
        self.reshape(link=[{"name": "Houlgate", "parent": LOGIC}], unlink=[{"name": "Houlgate", "parent": IDEALISM}])

    def test_the_work_keeps_both(self) -> None:
        self.assertEqual([LOGIC, "Houlgate"], self.field_of(HOULGATE))


class TestTheShapeListing(ReshapingCase):
    def test_the_listing_carries_the_tree_the_findings_the_nominations_and_descriptions(self) -> None:
        store = GraphStore(self.scratch / "graph.sqlite")
        self.addCleanup(store.close)
        self.vault.note(UNPLACED, field=[], source_role="secondary", title=UNPLACED, author=["Rosen"], year=2014)
        nominations = [{"name": BEGINNING, "kind": "topic", "parent": LOGIC, "works": [UNPLACED]}]
        listing = ShapeListing(bibliographies.Bibliographies(), bibliographies.Corpus(), store).of(nominations)
        self.assertEqual({IDEALISM, LOGIC}, {entry["name"] for entry in listing["tree"]})
        self.assertEqual(nominations, listing["nominations"])
        self.assertEqual([], listing["descriptions"][UNPLACED]["bibliographies"])
        self.assertIn("findings", listing["clusters"])
        self.assertNotIn("missing", listing["clusters"]["findings"])

    def shaped(self) -> dict:
        store = GraphStore(self.scratch / "graph.sqlite")
        self.addCleanup(store.close)
        self.vault.bibliography_in("2 authors", "Hegel", f"## Maps\n\n- [[{LOGIC}]]\n", author="Hegel")
        return ShapeListing(bibliographies.Bibliographies(), bibliographies.Corpus(), store).of([])

    def test_an_author_map_counts_its_own_works_and_others_beneath_it(self) -> None:
        hegel = next(entry for entry in self.shaped()["author_maps"] if entry["name"] == "Hegel")
        self.assertEqual((1, len(SHARING_A_SUBJECT)), (hegel["own_works"], hegel["works_by_others"]))

    def test_an_author_map_names_the_authors_own_works(self) -> None:
        hegel = next(entry for entry in self.shaped()["author_maps"] if entry["name"] == "Hegel")
        self.assertEqual([HEGEL], hegel["works"])

    def test_a_subtopic_listed_by_an_author_alone_is_named(self) -> None:
        self.vault.bibliography_in("1 historical periods", IDEALISM, "## Maps\n\n- [[Hegel]]\n")
        self.assertEqual([{"name": LOGIC, "parents": ["Hegel"]}], self.shaped()["unlinked_subtopics"])

    def test_a_subtopic_a_discipline_also_lists_is_not_named(self) -> None:
        self.vault.bibliography_in("3 topics", DISCIPLINE, f"## Maps\n\n- [[{LOGIC}]]\n")
        self.assertEqual([], self.shaped()["unlinked_subtopics"])


class TestANewRoot(ReshapingCase):
    def test_a_root_sits_in_the_folder_of_its_kind_and_no_bibliography_lists_it(self) -> None:
        self.reshape(create=[creation(DISCIPLINE, None)])
        self.assertIn("## Secondary literature", self.body_of("3 topics", DISCIPLINE))
        self.assertNotIn(f"[[{DISCIPLINE}]]", self.body_of("1 historical periods", IDEALISM))

    def test_the_root_is_not_reported_with_a_parent(self) -> None:
        self.assertNotIn(None, self.reshape(create=[creation(DISCIPLINE, None)])["touched"])

    def test_a_root_whose_works_gather_beneath_it_needs_none_of_its_own(self) -> None:
        report = self.reshape(create=[creation(DISCIPLINE, None, ()), creation(BEGINNING, DISCIPLINE)])
        self.assertEqual([DISCIPLINE, BEGINNING], report["created"])
        self.assertIn(f"[[{BEGINNING}]]", self.body_of("3 topics", DISCIPLINE))

    def test_a_root_with_fewer_than_five_works_beneath_it_is_refused(self) -> None:
        with self.assertRaises(ReshapeRefused):
            self.reshape(create=[creation(DISCIPLINE, None, ()), creation(BEGINNING, DISCIPLINE, (HOULGATE,))])


class TestACreationTwoTiersBeneathAWorksBibliography(ReshapingCase):
    def setUp(self) -> None:
        super().setUp()
        for basename in (HEGEL, *SHARING_A_SUBJECT):
            self.vault.note(basename, field=[f"[[{IDEALISM}]]"], source_role="secondary", title=basename,
                            author=[basename.split(" - ")[0]], year=int(basename.split(" - ")[1]))
        self.reshape(create=[creation("Systems", IDEALISM, ()), creation(BEGINNING, "Systems")])

    def test_takes_the_work_off_the_ancestor(self) -> None:
        self.assertEqual([BEGINNING], self.field_of(HOULGATE))


class TestANominationWhoseWorkAReshapingHasMoved(ReshapingCase):
    def listed(self, placed_on: list[str]) -> list[dict]:
        store = GraphStore(self.scratch / "graph.sqlite")
        self.addCleanup(store.close)
        nominations = [{"name": BEGINNING, "kind": "topic", "parent": LOGIC, "works": [HOULGATE],
                        "placed_on": placed_on}]
        return ShapeListing(bibliographies.Bibliographies(), bibliographies.Corpus(), store).of(nominations)["nominations"]

    def test_is_left_out_of_the_listing(self) -> None:
        self.assertEqual([], self.listed([]))

    def test_a_work_still_where_it_was_nominated_stays_in_the_listing(self) -> None:
        self.assertEqual([HOULGATE], self.listed([LOGIC])[0]["works"])


class TestTheListHelpers(unittest.TestCase):
    def test_a_child_joins_the_maps_in_alphabetical_order(self) -> None:
        body = MapsList("## Maps\n\n- [[Kant]]\n- [[Plato]]\n").with_child("Hegel")
        self.assertEqual(["- [[Hegel]]", "- [[Kant]]", "- [[Plato]]"], bibliographies.Section("Maps").lines_in(body))

    def test_an_empty_maps_marker_gives_way_to_the_child(self) -> None:
        body = MapsList("## Maps\n\n*(none)*\n\n## Secondary literature\n").with_child("Hegel")
        self.assertEqual(["- [[Hegel]]"], bibliographies.Section("Maps").lines_in(body))

    def test_a_listed_work_is_removed_and_the_rest_kept(self) -> None:
        body = WorkListRemoval(LOGIC_BODY).without(PIPPIN)
        self.assertNotIn(PIPPIN, body)
        self.assertIn(f"- [[{HOULGATE}]] — on the opening.", body)


if __name__ == "__main__":
    unittest.main()
