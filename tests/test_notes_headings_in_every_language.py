from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import references
import vault

SECTION_HEADINGS = ("Notes", "Endnotes", "Anmerkungen", "Noten", "Notes to the Text", "NOTES TO CHAPTERS")
NOTES_HEADINGS = SECTION_HEADINGS + ("Note", "Endnote")
OTHER_HEADINGS = ("Notes on Contributors", "Bibliography", "Chapter One")


class TestANotesHeadingInAnyLanguageOfTheVaultOpensAnEntryList(unittest.TestCase):
    def test_every_notes_heading_is_a_notes_heading(self) -> None:
        for heading in NOTES_HEADINGS:
            with self.subTest(heading=heading):
                self.assertTrue(vault.is_notes_heading(heading))

    def test_a_heading_naming_something_else_is_not_a_notes_heading(self) -> None:
        for heading in OTHER_HEADINGS:
            with self.subTest(heading=heading):
                self.assertFalse(vault.is_notes_heading(heading))


class TestTheZoneNotesTestIsTheVaultsRule(unittest.TestCase):
    def test_every_heading_naming_a_section_of_notes_opens_a_notes_zone(self) -> None:
        for heading in SECTION_HEADINGS:
            with self.subTest(heading=heading):
                self.assertTrue(references.SectionHeading.of_notes().matches(heading))

    def test_the_zone_notes_test_agrees_with_the_vault(self) -> None:
        for heading in NOTES_HEADINGS + OTHER_HEADINGS + ("Notes 213",):
            with self.subTest(heading=heading):
                self.assertEqual(vault.names_notes_section(heading),
                                 references.SectionHeading.of_notes().matches(heading))


if __name__ == "__main__":
    unittest.main()
