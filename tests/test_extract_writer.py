from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.elements import Heading, PageMarker, Paragraph
from _extract.footnotes import FootnoteDefinition
from _extract.markdown import HtmlToMarkdown, TableMarkdown
from _extract.writer import NoteWriter


def rendered(elements: list, definitions: list | None = None) -> str:
    return NoteWriter().render(elements, definitions or []).text


class TestHtmlToMarkdown(unittest.TestCase):
    def test_italics_are_dropped(self) -> None:
        self.assertEqual("A word here", HtmlToMarkdown().text("<p>A <i>word</i> here</p>"))

    def test_bold_is_marked(self) -> None:
        self.assertEqual("A **word** here", HtmlToMarkdown().text("<p>A <b>word</b> here</p>"))

    def test_a_break_becomes_a_newline(self) -> None:
        self.assertEqual("so\non", HtmlToMarkdown().text("<p>so<br>on</p>"))

    def test_an_entity_is_unescaped(self) -> None:
        self.assertEqual("this & that", HtmlToMarkdown().text("<p>this &amp; that</p>"))

    def test_a_regular_table_becomes_a_pipe_table(self) -> None:
        table = TableMarkdown().text("<table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>")
        self.assertEqual("| a | b |\n| --- | --- |\n| 1 | 2 |", table)

    def test_a_table_with_a_cell_spanning_columns_is_written_as_its_html(self) -> None:
        html = '<table><tr><th>a</th><th>b</th></tr><tr><td colspan="2"><i>wide</i></td></tr></table>'
        self.assertEqual('<table>\n<tr><th>a</th><th>b</th></tr>\n<tr><td colspan="2">wide</td></tr>\n</table>',
                         TableMarkdown().text(html))

    def test_a_pipe_inside_a_cell_is_escaped_whether_or_not_it_is_notation(self) -> None:
        html = "<table><tr><td>❲s ¬ | B❳</td><td>a | b</td></tr></table>"
        self.assertEqual("| ❲s ¬ \\| B❳ | a \\| b |\n| --- | --- |", TableMarkdown().text(html))

    def test_a_table_with_a_cell_spanning_rows_is_written_as_its_html(self) -> None:
        html = '<table><tr><td rowspan="2">tall</td><td>one</td></tr><tr><td>two</td></tr></table>'
        self.assertEqual('<table>\n<tr><td rowspan="2">tall</td><td>one</td></tr>\n<tr><td>two</td></tr>\n</table>',
                         TableMarkdown().text(html))

    def test_a_spanning_tables_cell_text_is_escaped_but_keeps_its_raised_marks(self) -> None:
        html = '<table><tr><td colspan="2">a &lt; b<sup>2</sup> &amp; c</td></tr></table>'
        self.assertEqual('<table>\n<tr><td colspan="2">a &lt; b<sup>2</sup> &amp; c</td></tr>\n</table>',
                         TableMarkdown().text(html))


class TestNoteWriter(unittest.TestCase):
    def test_a_page_beginning_at_a_block_boundary_gets_a_marker_line_before_the_block(self) -> None:
        elements = [PageMarker(1, "1"), Paragraph("It ends here.", False, 1), PageMarker(2, "2"),
                    Paragraph("another starts.", False, 2)]
        self.assertEqual("%% p. 1 (file p. 1) %%\n\nIt ends here.\n\n%% p. 2 (file p. 2) %%\n\nanother starts.\n",
                         rendered(elements))

    def test_a_continuing_paragraph_joins_across_the_page_with_the_marker_at_the_break(self) -> None:
        elements = [PageMarker(1, "1"), Paragraph("Begins here", True, 1), PageMarker(2, "2"),
                    Paragraph("and ends.", False, 2)]
        self.assertEqual("%% p. 1 (file p. 1) %%\n\nBegins here %% p. 2 (file p. 2) %% and ends.\n", rendered(elements))

    def test_a_sentence_running_across_a_page_break_is_rejoined_with_the_marker_at_the_break(self) -> None:
        elements = [PageMarker(1, "1"), Paragraph("The claim is that", False, 1), PageMarker(2, "2"),
                    Paragraph("being is nothing.", False, 2)]
        self.assertEqual("%% p. 1 (file p. 1) %%\n\nThe claim is that %% p. 2 (file p. 2) %% being is nothing.\n",
                         rendered(elements))

    def test_a_word_hyphenated_across_a_page_break_is_rejoined_and_the_marker_follows_it(self) -> None:
        elements = [PageMarker(1, "1"), Paragraph("friends and col-", False, 1), PageMarker(2, "2"),
                    Paragraph("leagues who", False, 2)]
        self.assertEqual("%% p. 1 (file p. 1) %%\n\nfriends and colleagues %% p. 2 (file p. 2) %% who\n",
                         rendered(elements))

    def test_a_marker_precedes_a_heading_on_its_own_line(self) -> None:
        elements = [PageMarker(4, None), Heading(2, "Semantics", 4), Paragraph("❲x❳", False, 4)]
        self.assertEqual("%% file p. 4 %%\n\n## Semantics\n\n❲x❳\n", rendered(elements))

    def test_a_page_without_content_leaves_no_marker(self) -> None:
        elements = [PageMarker(1, "1"), Paragraph("Text", False, 1), PageMarker(2, "2"), PageMarker(3, "3"),
                    Paragraph("More.", False, 3)]
        self.assertEqual("%% p. 1 (file p. 1) %%\n\nText\n\n%% p. 3 (file p. 3) %%\n\nMore.\n", rendered(elements))

    def test_footnote_definitions_sit_under_a_notes_heading_at_the_end(self) -> None:
        text = rendered([Paragraph("Text.[^1]", False, 1)], [FootnoteDefinition(1, "1", "A note.")])
        self.assertEqual("Text.[^1]\n\n# Notes\n\n[^1]: A note.\n", text)

    def test_a_marker_after_the_last_block_is_dropped(self) -> None:
        elements = [PageMarker(1, "1"), Paragraph("Text.", False, 1), PageMarker(2, None)]
        self.assertEqual("%% p. 1 (file p. 1) %%\n\nText.\n", rendered(elements))


class TestBracketedLabels(unittest.TestCase):
    def _rendered(self, text: str) -> str:
        return rendered([Paragraph(text, False, 1)]).strip()

    def test_a_label_beside_a_placeholder_has_its_brackets_escaped(self) -> None:
        self.assertEqual("applying \\[L❲∧❳\\] to it", self._rendered("applying [L❲∧❳] to it"))

    def test_a_label_of_words_alone_has_its_brackets_escaped(self) -> None:
        self.assertEqual("we apply \\[Mixed-Cut\\] here", self._rendered("we apply [Mixed-Cut] here"))

    def test_brackets_inside_a_placeholder_are_left_alone(self) -> None:
        self.assertEqual("❲∼B[q]❳ holds", self._rendered("❲∼B[q]❳ holds"))

    def test_a_label_in_a_paragraph_continued_across_a_page_is_resolved(self) -> None:
        elements = [Paragraph("we apply", True, 1), PageMarker(2, "2"), Paragraph("[Cut] here", False, 2)]
        self.assertIn("\\[Cut\\] here", rendered(elements))

    def test_a_footnote_mark_is_not_a_label(self) -> None:
        self.assertEqual("lexicon.[^3]", self._rendered("lexicon.[^3]"))


if __name__ == "__main__":
    unittest.main()
