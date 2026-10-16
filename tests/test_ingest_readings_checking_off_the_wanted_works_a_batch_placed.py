from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import vault
from _ingest.readings import PlacedWorks, ReadingsStep
from _vaults import TempVault
from _writing.reading_list import HELD, WANTED, ProjectReadingLists, ReadingAddition, ReadingEntry, ReadingListFile

PAPER = "Kant's Critique of Mathematical Reason"
OTHER_PAPER = "Hegel's Theory of Measure"
WANTED_LINE = "- **high** · Friedman 1992, *Kant and the Exact Sciences* — the standard reading. [publisher](https://example.org)"
PLACED = "Friedman - 1992 - Kant and the Exact Sciences"
HELD_LINE = f"- [[{PLACED}]] — the standard reading."
BIBLIOGRAPHY = "[[Kant's Philosophy of Mathematics]]"


class ReadingsStepTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._vault = TempVault("CORPUS_DIR", "BIBLIOGRAPHIES_DIR").activate()
        self.addCleanup(self._vault.discard)
        self.directory = vault.BIBLIOGRAPHIES_DIR / vault.READING_LISTS_FOLDER

    def want(self, project: str) -> ReadingListFile:
        file = ReadingListFile(self.directory, project)
        ReadingAddition(file, ReadingEntry("wanted", WANTED_LINE)).apply()
        return file

    def hold(self, **meta) -> None:
        vault.write_frontmatter(vault.CORPUS_DIR / f"{PLACED}.md", meta, "")

    def run_step(self) -> dict:
        return ReadingsStep(ProjectReadingLists(self.directory), PlacedWorks(vault.list_held_notes())).run()


class TestCheckingOffTheWantedWorksABatchPlaced(ReadingsStepTestCase):
    def test_a_wanted_work_placed_on_a_bibliography_moves_under_held(self) -> None:
        file = self.want(PAPER)
        self.hold(field=[BIBLIOGRAPHY])
        self.run_step()
        self.assertEqual(([], [HELD_LINE]), (file.read().entries(WANTED), file.read().entries(HELD)))

    def test_the_line_names_each_entry_checked_off_with_its_project(self) -> None:
        self.want(PAPER)
        self.hold(field=[BIBLIOGRAPHY])
        self.assertEqual([f"{PAPER}: {HELD_LINE}"], self.run_step()["checked_off"])

    def test_a_held_work_placed_on_no_bibliography_stays_wanted(self) -> None:
        file = self.want(PAPER)
        self.hold(title="Kant and the Exact Sciences")
        self.assertEqual(([], [WANTED_LINE]), (self.run_step()["checked_off"], file.read().entries(WANTED)))

    def test_a_held_work_whose_frontmatter_does_not_parse_stays_wanted(self) -> None:
        file = self.want(PAPER)
        (vault.CORPUS_DIR / f"{PLACED}.md").write_text("---\nfield: [unclosed\n---\n", encoding="utf-8")
        self.assertEqual(([], [WANTED_LINE]), (self.run_step()["checked_off"], file.read().entries(WANTED)))

    def test_every_project_reading_list_wanting_the_work_checks_it_off(self) -> None:
        self.want(PAPER)
        self.want(OTHER_PAPER)
        self.hold(field=[BIBLIOGRAPHY])
        self.assertEqual([f"{OTHER_PAPER}: {HELD_LINE}", f"{PAPER}: {HELD_LINE}"], self.run_step()["checked_off"])

    def test_a_note_of_the_folder_that_is_no_project_reading_list_is_left_as_it_is(self) -> None:
        kept = self.directory / "kant-and-mathematics.md"
        self.directory.mkdir(parents=True)
        kept.write_text(f"# Wanted\n\n{WANTED_LINE}\n", encoding="utf-8")
        self.hold(field=[BIBLIOGRAPHY])
        self.assertEqual(([], f"# Wanted\n\n{WANTED_LINE}\n"),
                         (self.run_step()["checked_off"], kept.read_text(encoding="utf-8")))

    def test_no_reading_list_checks_nothing_off_and_asks_nothing(self) -> None:
        self.assertEqual({"state": "read", "checked_off": [], "questions": []}, self.run_step())


if __name__ == "__main__":
    unittest.main()
