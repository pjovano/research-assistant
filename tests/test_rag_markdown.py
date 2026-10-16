from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import rag
from _rag.markdown import InlineMarkup
from _rag_chunks import ChunkingTestCase, tokens_in

FILLER = "word " * 200
PAGED = ("# Chapter One\n\n%% p. xiv (file p. 3) %%\n\nFirst " + FILLER + "\n\n%% file p. 4 %%\n\n"
         "Second " + FILLER + "\n\n%% p. 1 (file p. 5) %%\n\nThird " + FILLER + "\n")
INLINE_MARKER = ("# One\n\n%% p. 12 (file p. 20) %%\n\nA sentence runs across %% p. 13 (file p. 21) %% the break, "
                 "and on.\n")
MATH_SENTENCES = "".join(f"Let $x. y$ hold in case {number}, so that it holds. " for number in range(40))


class TestAtomicUnits(ChunkingTestCase):
    MATH_BLOCK = "$$\n" + "a_{n+1} + b_{n} = c_{n} \\\\\n" * 80 + "$$"
    TABLE = "\n".join(f"| row {number} | value {number} |" for number in range(120))
    FOOTNOTE = "[^7]: " + "note " * 300

    def test_a_display_math_block_over_the_limit_is_one_oversized_child(self) -> None:
        child = self.chunk("# One\n\nBefore.\n\n" + self.MATH_BLOCK + "\n\nAfter.\n").child_containing("a_{n+1}")
        self.assertEqual(self.MATH_BLOCK, child.text)
        self.assertGreater(tokens_in(child.text), rag.MAX_CHILD_TOKENS)

    def test_inline_math_is_never_cut_by_a_sentence_boundary(self) -> None:
        texts = self.chunk("# One\n\n" + MATH_SENTENCES).child_texts()
        self.assertGreater(len(texts), 1)
        self.assertEqual(40, sum(text.count("$x. y$") for text in texts))

    def test_a_table_over_the_limit_is_one_oversized_child(self) -> None:
        child = self.chunk("# One\n\n" + self.TABLE + "\n").child_containing("row 119")
        self.assertEqual(self.TABLE, child.text)

    def test_a_footnote_definition_over_the_limit_is_one_oversized_child(self) -> None:
        child = self.chunk("# One\n\nText.\n\n" + self.FOOTNOTE + "\n").child_containing("[^7]:")
        self.assertEqual(self.FOOTNOTE.strip(), child.text)

    def test_footnote_marks_are_stripped_from_prose(self) -> None:
        self.assertEqual(["Being is."], self.chunk("# One\n\nBeing[^12] is.\n").child_texts())

    def test_an_image_is_reduced_to_its_alt_text(self) -> None:
        self.assertEqual(["Figure 3"], self.chunk("# One\n\n![Figure 3](figures/3.png)\n").child_texts())


class TestPageMarkers(ChunkingTestCase):
    def test_markers_are_stripped_from_the_text(self) -> None:
        for text in self.chunk(PAGED).child_texts():
            self.assertNotIn("%%", text)

    def test_a_roman_folio_in_force_at_the_chunk_start_is_recorded(self) -> None:
        metadata = self.chunk(PAGED).child_containing("First").metadata
        self.assertEqual(("xiv", 3), (metadata["folio_first"], metadata["file_page_first"]))

    def test_a_page_without_a_folio_records_none_and_its_file_page(self) -> None:
        metadata = self.chunk(PAGED).child_containing("Second").metadata
        self.assertEqual((None, 4), (metadata["folio_first"], metadata["file_page_first"]))

    def test_the_parent_spans_from_the_first_folio_to_the_last_marker_inside_it(self) -> None:
        metadata = self.chunk(PAGED).parent_containing("Third").metadata
        self.assertEqual(("xiv", "1", 3, 5), (metadata["folio_first"], metadata["folio_last"],
                                              metadata["file_page_first"], metadata["file_page_last"]))

    def test_a_chunk_before_any_marker_has_no_folio(self) -> None:
        metadata = self.chunk("# One\n\nText.\n").child_containing("Text").metadata
        self.assertEqual((None, None), (metadata["folio_first"], metadata["file_page_first"]))

    def test_a_marker_on_its_own_line_inside_a_paragraph_advances_only_the_last_folio(self) -> None:
        body = "# One\n\n%% p. 12 (file p. 20) %%\n\nA sentence runs across\n%% p. 13 (file p. 21) %%\nthe break.\n"
        metadata = self.chunk(body).child_containing("the break").metadata
        self.assertEqual(("12", "13"), (metadata["folio_first"], metadata["folio_last"]))

    def test_an_inline_marker_is_stripped_from_the_text(self) -> None:
        self.assertEqual(["A sentence runs across the break, and on."], self.chunk(INLINE_MARKER).child_texts())

    def test_an_inline_marker_advances_the_last_folio_and_file_page(self) -> None:
        metadata = self.chunk(INLINE_MARKER).child_containing("the break").metadata
        self.assertEqual(("12", "13", 20, 21), (metadata["folio_first"], metadata["folio_last"],
                                                metadata["file_page_first"], metadata["file_page_last"]))


class TestWikilinks(ChunkingTestCase):
    def test_an_aliased_wikilink_is_reduced_to_its_shown_text(self) -> None:
        body = "# One\n\nSee [[Kant - 1998 - Critique of Pure Reason|Kant's Critique]] here.\n"
        self.assertEqual(["See Kant's Critique here."], self.chunk(body).child_texts())

    def test_a_bare_wikilink_is_reduced_to_its_target(self) -> None:
        self.assertEqual(["See Being here."], self.chunk("# One\n\nSee [[Being]] here.\n").child_texts())

    def test_a_citation_link_after_an_entry_leaves_only_the_entry_text(self) -> None:
        body = "# References\n\nKant, I. (1998) *Critique*. [[Kant - 1998 - Critique of Pure Reason|↗]]\n"
        self.assertEqual(["Kant, I. (1998) *Critique*."], self.chunk(body).child_texts())


class TestComments(ChunkingTestCase):
    def test_a_comment_inside_prose_is_stripped(self) -> None:
        body = "# One\n\nThe equation ❲E = mc²❳ %% a comment %% holds.\n"
        self.assertEqual(["The equation ❲E = mc²❳ holds."], self.chunk(body).child_texts())

    def test_a_comment_alone_between_paragraphs_yields_no_chunk(self) -> None:
        body = "# One\n\nBefore.\n\n%% a comment %%\n\nAfter.\n"
        self.assertEqual(["Before.\n\nAfter."], self.chunk(body).child_texts())

    def test_a_comment_inside_a_heading_is_stripped_from_the_path(self) -> None:
        self.assertEqual(["Part"], self.chunk("# Part %% draft %%\n\nText.\n").heading_paths())


class TestWikilinksBesideMath(unittest.TestCase):
    def test_a_link_shows_its_text_and_math_brackets_stay_intact(self) -> None:
        cleaned = InlineMarkup.cleaned("Let ❲[[A ∧ B]]❳ hold; see [[Work - 2000 - Title|Shown]].")
        self.assertEqual("Let ❲[[A ∧ B]]❳ hold; see Shown.", cleaned)


if __name__ == "__main__":
    unittest.main()
