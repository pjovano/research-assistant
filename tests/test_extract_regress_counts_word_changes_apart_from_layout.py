from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.wordchanges import WordChanges

STORED = "%% p. 1 (file p. 1) %%\n\n# A Heading\n\nOne paragraph of words.[^1]\n\nAnother one.\n\n# Notes\n\n[^1]: A note."


class TestWordChanges(unittest.TestCase):
    def test_a_body_rearranged_without_changing_a_word_counts_none(self) -> None:
        rearranged = "%% p. 1 (file p. 1) %%\n\n## A Heading\n\nAnother one. One paragraph of words.[^2]\n\n" \
                     "# Notes\n\n[^2]: A note."
        self.assertEqual(0, WordChanges(STORED, rearranged).count())

    def test_a_word_spelled_otherwise_counts_as_one_lost_and_one_gained(self) -> None:
        self.assertEqual(2, WordChanges(STORED, STORED.replace("words", "wards")).count())

    def test_a_lost_paragraph_counts_each_of_its_words(self) -> None:
        self.assertEqual(2, WordChanges(STORED, STORED.replace("\n\nAnother one.", "")).count())

    def test_page_markers_and_note_labels_are_never_words(self) -> None:
        relabelled = STORED.replace("(file p. 1)", "(file p. 2)").replace("[^1]", "[^9]")
        self.assertEqual(0, WordChanges(STORED, relabelled).count())


if __name__ == "__main__":
    unittest.main()
