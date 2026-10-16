from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from citation_graph import held_key
from references import ParsedReference
from _graph_fixtures import FakeParser, FixedCentroids, GraphTestCase, entry_body

HOULGATE = "Houlgate - 2006 - The Opening of Hegel's Logic"
STERN = "Stern - 2023 - Understanding Hegel's Logic"
BURBIDGE = "Burbidge - 1981 - On Hegel's Logic"
DUNPHY_ENTRY = "Dunphy, Robb. Hegel and the Problem of Beginning. Lanham: Rowman, 2023."
DUNPHY_PAPERBACK = "Dunphy, Robb. Hegel and the Problem of Beginning. Lanham: Rowman and Littlefield, 2024."
PIPPIN_ENTRY = "Pippin, Robert. Hegel's Realm of Shadows. Chicago: University of Chicago Press, 2019."
BURBIDGE_LINK = f"[[{BURBIDGE}|Burbidge, John. On Hegel's Logic. 1981.]]"
DUNPHY_PARSED = ParsedReference(("Dunphy, Robb",), "Hegel and the Problem of Beginning", None, "2023", "Rowman", None)
DUNPHY_PAPERBACK_PARSED = ParsedReference(("Dunphy, Robb",), "Hegel and the Problem of Beginning", None, "2024",
                                          "Rowman and Littlefield", None)


class SyncedStoreTestCase(GraphTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_work(BURBIDGE, year="1981")
        self.write_work(HOULGATE, entry_body([BURBIDGE_LINK, DUNPHY_ENTRY], "443", 464), year="2006")
        self.write_work(STERN, entry_body([DUNPHY_ENTRY, PIPPIN_ENTRY]), year="2023")

    def rows_of(self, citing: str) -> list:
        return [row for row in self.store.citations() if row.citing == citing]


class TestHeldEdges(SyncedStoreTestCase):
    def test_a_linked_entry_is_a_citation_of_the_held_work_with_its_folio(self) -> None:
        self.sync()
        held = [row for row in self.rows_of(HOULGATE) if row.cites_held]
        self.assertEqual([(held_key(BURBIDGE), "443", 464)], [(row.cited, row.folio, row.file_page) for row in held])

    def test_the_citing_line_is_kept_with_the_edge(self) -> None:
        self.sync()
        held = [row for row in self.rows_of(HOULGATE) if row.cites_held]
        self.assertEqual(BURBIDGE_LINK, held[0].text)


class TestUnheldReferences(SyncedStoreTestCase):
    def test_one_unheld_work_cited_by_two_notes_is_one_node(self) -> None:
        self.sync()
        dunphy = {row.cited for row in self.store.citations() if row.text == DUNPHY_ENTRY}
        self.assertEqual(1, len(dunphy))
        self.assertEqual(1, len([row for row in self.store.unheld_rows() if row.text == DUNPHY_ENTRY]))

    def test_two_editions_of_one_unheld_work_merge_by_their_parsed_identity(self) -> None:
        self.touch(STERN, entry_body([DUNPHY_PAPERBACK]))
        self.sync(FakeParser({DUNPHY_ENTRY: DUNPHY_PARSED, DUNPHY_PAPERBACK: DUNPHY_PAPERBACK_PARSED}))
        keys = {row.cited for row in self.store.citations() if row.text.startswith("Dunphy")}
        self.assertEqual(1, len(keys))

    def test_distinct_unheld_works_are_distinct_nodes(self) -> None:
        self.sync()
        keys = {row.cited for row in self.rows_of(STERN)}
        self.assertEqual(2, len(keys))


class TestIncrementalSync(SyncedStoreTestCase):
    def test_a_second_run_over_unchanged_notes_syncs_nothing(self) -> None:
        self.sync()
        self.assertEqual({"synced": 0, "removed": 0, "notes": 3}, self.sync())

    def test_a_changed_note_is_synced_again_and_its_old_rows_dropped(self) -> None:
        self.sync()
        self.touch(STERN, entry_body([PIPPIN_ENTRY]))
        self.assertEqual(1, self.sync()["synced"])
        self.assertEqual([PIPPIN_ENTRY], [row.text for row in self.rows_of(STERN)])

    def test_a_removed_note_is_forgotten(self) -> None:
        self.sync()
        (self.vault.corpus / f"{STERN}.md").unlink()
        self.assertEqual(1, self.sync()["removed"])
        self.assertEqual([], self.rows_of(STERN))
        self.assertNotIn(STERN, self.store.stamps())

    def test_naming_basenames_syncs_those_alone(self) -> None:
        self.assertEqual(1, self.sync(basenames=[STERN])["synced"])
        self.assertEqual([], self.rows_of(HOULGATE))


class TestCentroids(SyncedStoreTestCase):
    def test_a_centroid_is_stored_for_a_work_the_embedding_store_holds(self) -> None:
        self.sync(centroids=FixedCentroids({STERN: [1.0, 0.0]}))
        self.assertEqual({STERN: [1.0, 0.0]}, self.store.centroids())

    def test_a_work_without_vectors_has_no_centroid(self) -> None:
        self.sync()
        self.assertEqual({}, self.store.centroids())


if __name__ == "__main__":
    unittest.main()
