from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _graph_fixtures import FakeParser
from _ports.compute import CitationParser

from references import ParsedReference

ENTRY = "Roe, J. 2001. A Placeholder Title. City: Press."
REFERENCE_FIELDS = ("authors", "title", "container", "year", "publisher", "pages")


class CitationParserContract:
    def parser(self) -> CitationParser:
        raise NotImplementedError

    def test_a_parsed_entry_carries_every_reference_field(self) -> None:
        parsed = self.parser().parse(ENTRY)
        self.assertEqual([], [field for field in REFERENCE_FIELDS if not hasattr(parsed, field)])

    def test_the_authors_are_a_tuple(self) -> None:
        self.assertIsInstance(self.parser().parse(ENTRY).authors, tuple)

    def test_one_entry_parses_alike_twice(self) -> None:
        parser = self.parser()
        self.assertEqual(parser.parse(ENTRY), parser.parse(ENTRY))


class TestFakeParserKeepsTheContract(CitationParserContract, unittest.TestCase):
    def parser(self) -> CitationParser:
        return FakeParser({ENTRY: ParsedReference(("Roe",), "A Placeholder Title", None, "2001", "Press", None)})


if __name__ == "__main__":
    unittest.main()
