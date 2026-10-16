from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import rag

BASENAME = "Doe - 2020 - A Work"
META = {"title": "A Work", "author": ["Doe"], "year": 2020}
ROW_COUNT = 40
WORDS_IN_TABLE_OVER_THE_CHILD_BUDGET = ROW_COUNT * 10
SPANNING_ROW = '<tr><td rowspan="2">Being.</td><td colspan="2">Nothing is the same as being.</td></tr>'
ROWS = [f"<tr><td>Row {number}.</td><td>The cell says one thing. It says another.</td></tr>"
        for number in range(ROW_COUNT)]
HTML_TABLE = "\n".join(["<table>", SPANNING_ROW, *ROWS, "</table>"])
PROSE_BEFORE = "Prose opens the section and runs on into the table that follows it"
PROSE_AFTER = "Prose closes the section after the table."


class WordBudget:
    def count(self, text: str) -> int:
        return len(text.split())


class ChunksOf:
    def __init__(self, body: str) -> None:
        document = rag.IndexedDocument(BASENAME, Path(f"{BASENAME}.md"), META, body)
        self._children = rag.ParentChildChunker(WordBudget()).chunked(document).children

    def children_holding(self, fragment: str) -> list[str]:
        return [child.text for child in self._children if fragment in child.text]


class TestAnHtmlTableIsNeverCutAcrossChildren(unittest.TestCase):
    def setUp(self) -> None:
        self.assertGreater(WORDS_IN_TABLE_OVER_THE_CHILD_BUDGET, rag.MAX_CHILD_TOKENS)
        self.chunks = ChunksOf(f"# One\n\n{PROSE_BEFORE}\n{HTML_TABLE}\n\n{PROSE_AFTER}\n")

    def test_an_html_table_over_the_child_budget_is_one_child(self) -> None:
        [child] = self.chunks.children_holding("<table>")
        self.assertTrue(child.endswith("</table>"))

    def test_every_row_of_an_html_table_is_in_the_child_that_opens_it(self) -> None:
        self.assertEqual(self.chunks.children_holding("<table>"), self.chunks.children_holding(f"Row {ROW_COUNT - 1}."))

    def test_prose_set_directly_above_an_html_table_is_not_in_its_child(self) -> None:
        self.assertEqual([], [text for text in self.chunks.children_holding("<table>") if PROSE_BEFORE in text])


if __name__ == "__main__":
    unittest.main()
