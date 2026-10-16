from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import vault
from _bibliographies.opening import MAX_WORDS, Opening
from _bibliography_fixtures import HEGEL, TemporaryVault

FIRST_PAGE_TEXT = "Do categories have senses? The first page argues that they must."
SECOND_PAGE_TEXT = "The second page carries the argument on to its conclusion."
PAGE_DIVIDED_BODY = (
    "%% p. 1 (file p. 1) %%\n\n## p. 1\n\n## p. 2\n\n" + FIRST_PAGE_TEXT + "\n\n"
    "%% p. 2 (file p. 2) %%\n\n## p. 3\n\n" + SECOND_PAGE_TEXT + "\n"
)
LONG_SECTION_WORDS = MAX_WORDS + 10


def opening_of(body: str) -> dict:
    vault.write_frontmatter(vault.CORPUS_DIR / f"{HEGEL}.md", {"title": "Wissenschaft der Logik"}, body)
    return Opening(HEGEL).report()


class TestTheOpeningOfABodyWhoseFirstHeadingsHoldNoText(unittest.TestCase):
    def setUp(self) -> None:
        TemporaryVault(self)

    def test_the_text_opens_with_the_first_section_that_holds_text(self) -> None:
        self.assertTrue(opening_of(PAGE_DIVIDED_BODY)["text"].startswith(FIRST_PAGE_TEXT))

    def test_the_text_runs_on_through_the_following_sections_within_the_budget(self) -> None:
        self.assertIn(SECOND_PAGE_TEXT, opening_of(PAGE_DIVIDED_BODY)["text"])

    def test_a_heading_with_no_text_is_not_among_the_chosen_sections(self) -> None:
        self.assertEqual(["p. 2", "p. 3"], opening_of(PAGE_DIVIDED_BODY)["prefatory"])

    def test_every_heading_is_still_listed(self) -> None:
        self.assertEqual(["## p. 1", "## p. 2", "## p. 3"], opening_of(PAGE_DIVIDED_BODY)["headings"])

    def test_a_first_section_past_the_budget_is_the_whole_opening(self) -> None:
        body = "## One\n\n" + "word " * LONG_SECTION_WORDS + "\n\n## Two\n\n" + SECOND_PAGE_TEXT + "\n"
        self.assertEqual(["One"], opening_of(body)["prefatory"])

    def test_an_empty_prefatory_heading_gives_way_to_the_first_section_with_text(self) -> None:
        body = "## Introduction\n\n## 1. The Problem\n\n" + FIRST_PAGE_TEXT + "\n"
        self.assertEqual(["1. The Problem"], opening_of(body)["prefatory"])


if __name__ == "__main__":
    unittest.main()
