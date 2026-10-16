from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from references import EntryParser, RepeatedAuthors
from test_cite_links import (
    CITING,
    CITING_FRONTMATTER,
    EARLIER,
    LINK_LINE,
    MAKING_IT_EXPLICIT,
    NAMED_ENTRY,
    PARSED,
    FakeParser,
    LibraryTestCase,
    linked,
)

NAMED_HEAD = "Brandom, Robert "
PARENTHESIZED_YEAR_ENTRY = "(1994). Making It Explicit. Cambridge, MA: Harvard University Press."
BARE_YEAR_ENTRY = "1994. Making It Explicit. Cambridge, MA: Harvard University Press."
EDITED_YEAR_ENTRY = "ed. (1994). Making It Explicit. Cambridge, MA: Harvard University Press."
FOLLOWING_AUTHOR_ZONE = (f"Quine, W. V. O. (1960). Word and Object. Cambridge, MA: MIT Press.\n"
                         f"{PARENTHESIZED_YEAR_ENTRY}\n")


def body_of(*entries: str) -> str:
    listed = "\n\n".join(entries)
    return f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n{listed}\n"


class YearOpeningParser(FakeParser):
    PARSED_RESTORED = {f"{NAMED_HEAD}{entry}": MAKING_IT_EXPLICIT
                       for entry in (PARENTHESIZED_YEAR_ENTRY, BARE_YEAR_ENTRY, EDITED_YEAR_ENTRY)}

    def parse(self, entry_text: str):
        return self.PARSED_RESTORED.get(entry_text) or PARSED.get(entry_text) or super().parse(entry_text)


class TestAnEntryOpeningWithItsYearIsScoredUnderTheAuthorAbove(LibraryTestCase):
    def linked_after_apply(self, entry: str) -> bool:
        self.write_note(CITING, CITING_FRONTMATTER, body_of(NAMED_ENTRY, entry))
        self.links_for(YearOpeningParser()).apply()
        return linked(entry, EARLIER) in self.note_text(CITING)

    def test_an_entry_opening_with_a_parenthesized_year_gains_its_link(self) -> None:
        self.assertTrue(self.linked_after_apply(PARENTHESIZED_YEAR_ENTRY))

    def test_an_entry_opening_with_a_bare_year_gains_its_link(self) -> None:
        self.assertTrue(self.linked_after_apply(BARE_YEAR_ENTRY))

    def test_an_entry_opening_with_an_editor_mark_and_its_year_gains_its_link(self) -> None:
        self.assertTrue(self.linked_after_apply(EDITED_YEAR_ENTRY))

    def test_an_entry_opening_with_its_year_and_no_author_above_gains_no_link(self) -> None:
        self.write_note(CITING, CITING_FRONTMATTER, body_of(PARENTHESIZED_YEAR_ENTRY))
        self.links_for(YearOpeningParser()).apply()
        self.assertIn(f"\n{PARENTHESIZED_YEAR_ENTRY}\n", self.note_text(CITING))


class TestTheRestoredText(unittest.TestCase):
    def test_the_author_above_stands_before_the_year(self) -> None:
        authors = RepeatedAuthors()
        authors.restored(NAMED_ENTRY)
        self.assertEqual(f"{NAMED_HEAD}{PARENTHESIZED_YEAR_ENTRY}", authors.restored(PARENTHESIZED_YEAR_ENTRY))

    def test_an_entry_naming_its_author_is_left_as_it_is(self) -> None:
        self.assertEqual(NAMED_ENTRY, RepeatedAuthors().restored(NAMED_ENTRY))

    def test_a_numbered_entry_is_not_read_as_opening_with_its_year(self) -> None:
        authors = RepeatedAuthors()
        authors.restored(NAMED_ENTRY)
        numbered = "1. K. R. Apt: Logic Programming. Elsevier, Amsterdam 1990."
        self.assertEqual(numbered, authors.restored(numbered))


class TestTheEntryParserInheritsTheAuthorAbove(unittest.TestCase):
    def test_an_entry_opening_with_its_year_inherits_the_surname_above(self) -> None:
        self.assertEqual(("quine",), EntryParser().parse(FOLLOWING_AUTHOR_ZONE)[1].surnames)


if __name__ == "__main__":
    unittest.main()
