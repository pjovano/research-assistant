from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import vault


class TestHeadingPattern(unittest.TestCase):
    def test_the_hashes_and_the_text_are_the_two_groups(self) -> None:
        match = vault.HEADING_RE.match("### Becoming  ")
        self.assertEqual(("###", "Becoming"), (match.group("hashes"), match.group("text")))
        self.assertEqual(("###", "Becoming"), (match.group(1), match.group(2)))

    def test_hashes_without_text_are_not_a_heading(self) -> None:
        self.assertIsNone(vault.HEADING_RE.match("## "))

    def test_a_tag_line_is_not_a_heading(self) -> None:
        self.assertIsNone(vault.HEADING_RE.match("#tag"))


class TestFootnoteDefinitionPattern(unittest.TestCase):
    def test_the_label_and_the_text_are_the_two_groups(self) -> None:
        match = vault.FOOTNOTE_DEFINITION_RE.match("[^12]: See Brandom.")
        self.assertEqual(("[^12]: ", "See Brandom."), (match.group("label"), match.group("text")))

    def test_a_lettered_label_is_a_definition(self) -> None:
        self.assertIsNotNone(vault.FOOTNOTE_DEFINITION_RE.match("[^a]: A note."))

    def test_a_footnote_mark_in_prose_is_not_a_definition(self) -> None:
        self.assertIsNone(vault.FOOTNOTE_DEFINITION_RE.match("Prose.[^1] More."))


class TestWikilinkPattern(unittest.TestCase):
    def test_the_target_stops_at_a_heading_anchor(self) -> None:
        match = vault.WIKILINK_RE.search("see [[Kant - 1998 - Critique#Preface|the preface]]")
        self.assertEqual(("Kant - 1998 - Critique", "the preface"), (match.group("target"), match.group("shown")))

    def test_an_escaped_closing_bracket_pair_stays_inside_the_alias(self) -> None:
        match = vault.WIKILINK_RE.search("[[Work|Title [vol. 1\\]\\]. Press.]]")
        self.assertEqual("Title [vol. 1\\]\\]. Press.", match.group("shown"))

    def test_two_links_on_one_line_are_both_found(self) -> None:
        targets = [link.group("target") for link in vault.WIKILINK_RE.finditer("[[A]] and [[B|b]]")]
        self.assertEqual(["A", "B"], targets)

    def test_a_math_index_pair_is_not_a_link(self) -> None:
        self.assertIsNone(vault.WIKILINK_RE.search("a[[i]"))


class TestBibliographySpan(unittest.TestCase):
    BODY = ["# One", "Prose.", "## Bibliography", "Kant, I. Critique.", "### Primary sources", "Hegel, G. Logic.",
            "## Index", "Being, 12."]

    def _spans(self, lines: list[str]) -> list[tuple[int, int]]:
        return vault.BibliographySpan(lines).all()

    def test_the_span_runs_from_the_heading_to_the_next_heading_at_its_level(self) -> None:
        self.assertEqual([(2, 6)], self._spans(self.BODY))

    def test_a_deeper_heading_does_not_end_the_span(self) -> None:
        self.assertEqual([(2, 7)], self._spans(self.BODY[:6] + ["Tail."]))

    def test_a_heading_carrying_an_inline_page_marker_opens_the_span(self) -> None:
        lines = ["# One", "## Bibliography %% p. 400 (file p. 420) %%", "Kant, I. Critique.", "# Index"]
        self.assertEqual([(1, 3)], self._spans(lines))

    def test_a_heading_carrying_an_inline_page_marker_still_ends_the_span(self) -> None:
        lines = ["## Bibliography", "Kant, I. Critique.", "## Index %% p. 500 (file p. 520) %%", "Being, 12."]
        self.assertEqual([(0, 2)], self._spans(lines))

    def test_the_first_footnote_definition_ends_the_span(self) -> None:
        lines = ["## References", "Kant, I. Critique.", "[^1]: A note on Kant.", "More."]
        self.assertEqual([(0, 2)], self._spans(lines))

    def test_the_first_span_is_the_first_bibliography_heading(self) -> None:
        self.assertEqual((2, 6), vault.BibliographySpan(self.BODY).all()[0])

    def test_a_body_without_a_bibliography_heading_has_no_span(self) -> None:
        self.assertEqual([], vault.BibliographySpan(["# One", "Prose."]).all())


if __name__ == "__main__":
    unittest.main()
