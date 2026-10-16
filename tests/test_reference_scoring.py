from __future__ import annotations

import dataclasses
import unittest

from _support import LiveTree

LiveTree.activate()

from references import (
    AUTOMATIC_THRESHOLD, CONFIRMATION_THRESHOLD, CitedReference, HeldTitles, LibraryWork, ParsedReference,
    ReferenceScore, ScoredMatch,
)

EXPLICIT = LibraryWork("Brandom - 1994 - Making It Explicit", ("brandom",), ("1994",), frozenset(),
                       ("making it explicit",))
CRITIQUE = LibraryWork("Kant - 1998 - Critique of Pure Reason", ("kant",), ("1998",), frozenset(),
                       ("critique of pure reason",))
ENTRY = "Brandom, Robert. Making It Explicit. Cambridge, MA: Harvard University Press, 1994."
QUOTED_ENTRY = "Brandom, Robert. “Making It Explicit.” Mind 103 (1994): 1–20."
TITLE_ONLY_CEILING = AUTOMATIC_THRESHOLD - 1
UNRELATED_TITLE_CEILING = 50.0
YEAR_DISAGREEMENT_SCORE = 90.0


MAKING_IT_EXPLICIT = ParsedReference(("Brandom, Robert",), "Making It Explicit", None, "1994", None, None)


def parsed(**differences: object) -> ParsedReference:
    return dataclasses.replace(MAKING_IT_EXPLICIT, **differences)


def score(reference: ParsedReference, work: LibraryWork = EXPLICIT, entry: str = ENTRY) -> float:
    return ReferenceScore(CitedReference(reference, entry), work, HeldTitles(work.titles)).value()


def ratio(cited: str, held: str) -> float:
    return HeldTitles((held,)).best_for(cited)


class TestTitleMatching(unittest.TestCase):
    def test_the_same_title_scores_one_hundred(self) -> None:
        self.assertEqual(100.0, ratio("Making It Explicit", "Making It Explicit"))

    def test_case_and_punctuation_do_not_count(self) -> None:
        self.assertEqual(100.0, ratio("MAKING IT EXPLICIT!", "making it explicit"))

    def test_a_subtitle_after_a_non_breaking_space_is_stripped(self) -> None:
        cited = "Freedom and Reflection:\xa0 Hegel and the Logic of Agency"
        self.assertEqual(100.0, ratio(cited, "Freedom and Reflection"))

    def test_a_leading_article_does_not_count(self) -> None:
        self.assertEqual(100.0, ratio("The Phenomenology of Spirit", "Phenomenology of Spirit"))

    def test_a_cited_title_that_extends_the_held_title_is_identical(self) -> None:
        cited = "Prolegomena to Any Future Metaphysics That Will Be Able to Present Itself as a Science"
        self.assertEqual(100.0, ratio(cited, "Prolegomena to Any Future Metaphysics"))

    def test_a_held_title_that_extends_the_cited_title_is_not_identical(self) -> None:
        self.assertLess(ratio("Hegel", "Hegel's Naturalism"), UNRELATED_TITLE_CEILING)

    def test_a_held_title_buried_inside_the_cited_title_is_not_identical(self) -> None:
        cited = "Some Major Issues in the Philosophy of Logical Empiricism"
        self.assertLess(ratio(cited, "Logical Empiricism"), CONFIRMATION_THRESHOLD)

    def test_an_unrelated_title_scores_low(self) -> None:
        self.assertLess(ratio("Making It Explicit", "The Bounds of Sense"), UNRELATED_TITLE_CEILING)

    def test_an_empty_title_scores_zero(self) -> None:
        self.assertEqual(0.0, ratio("", "Making It Explicit"))

    def test_the_best_of_the_held_titles_is_taken(self) -> None:
        held = HeldTitles(("Articulating Reasons", "Making It Explicit"))
        self.assertEqual(100.0, held.best_for("Making It Explicit"))


class TestReferenceScore(unittest.TestCase):
    def test_a_shared_surname_the_same_title_and_the_same_year_score_one_hundred(self) -> None:
        self.assertEqual(100.0, score(parsed()))

    def test_no_shared_surname_in_the_authors_or_the_title_scores_zero(self) -> None:
        self.assertEqual(0.0, score(parsed(authors=("Doe, Jane",)), entry="Doe. Making It Explicit. 1994."))

    def test_the_entry_text_supplies_the_surname_when_no_author_was_parsed(self) -> None:
        self.assertEqual(100.0, score(parsed(authors=())))

    def test_a_missing_year_leaves_the_title_score(self) -> None:
        self.assertEqual(100.0, score(parsed(year=None)))

    def test_a_disagreeing_year_costs_ten_points(self) -> None:
        self.assertEqual(YEAR_DISAGREEMENT_SCORE, score(parsed(year="2001")))

    def test_a_surname_found_only_in_the_title_is_capped_below_the_automatic_threshold(self) -> None:
        reference = parsed(authors=("Doe, Jane",), title="Brandom's Making It Explicit")
        entry = "Doe, Jane. Brandom's Making It Explicit. 1994."
        self.assertEqual(TITLE_ONLY_CEILING, score(reference, entry=entry))

    def test_a_commentary_whose_title_mentions_the_held_work_scores_below_the_band(self) -> None:
        title = "The Bounds of Sense: An Essay on Kant's Critique of Pure Reason"
        reference = parsed(authors=("Strawson, P. F.",), title=title, year="1966")
        self.assertLess(score(reference, CRITIQUE, "Strawson. The Bounds of Sense. 1966."), CONFIRMATION_THRESHOLD)

    def test_a_container_of_two_words_or_more_counts_as_a_title(self) -> None:
        self.assertEqual(100.0, score(parsed(title="Some Chapter", container="Making It Explicit")))

    def test_the_entry_text_stands_in_for_a_title_the_parser_did_not_name(self) -> None:
        entry = "Brandom, Making It Explicit, §206"
        self.assertGreaterEqual(score(parsed(authors=(), title=None, year=None), entry=entry),
                                CONFIRMATION_THRESHOLD)

    def test_an_entry_naming_no_held_title_still_scores_below_the_band(self) -> None:
        entry = "Brandom, some remarks made in conversation, §206"
        self.assertLess(score(parsed(authors=(), title=None, year=None), entry=entry), CONFIRMATION_THRESHOLD)

    def test_a_one_word_container_is_ignored(self) -> None:
        self.assertLess(score(parsed(title="Some Chapter", container="Explicit")), CONFIRMATION_THRESHOLD)

    def test_a_collection_whose_main_title_is_one_word_names_nothing(self) -> None:
        container = "Explicit: A Collection of Critical Essays"
        self.assertLess(score(parsed(title="Some Chapter", container=container)), CONFIRMATION_THRESHOLD)

    def test_a_container_whose_main_title_is_two_words_or_more_still_counts(self) -> None:
        container = "Making It Explicit: A Collection of Critical Essays"
        self.assertEqual(100.0, score(parsed(title="Some Chapter", container=container)))

    def test_a_page_range_costs_the_entry_nothing(self) -> None:
        self.assertEqual(100.0, score(parsed(pages="1–20")))

    def test_a_quoted_title_costs_the_entry_nothing(self) -> None:
        self.assertEqual(100.0, score(parsed(), entry=QUOTED_ENTRY))

    def test_an_entry_citing_a_held_book_as_a_piece_of_a_volume_still_names_it(self) -> None:
        self.assertEqual(100.0, score(parsed(pages="287–433"), entry=QUOTED_ENTRY))


class TestHeldTitleForms(unittest.TestCase):
    def test_a_short_title_form_never_matches_when_the_work_has_a_longer_one(self) -> None:
        cited = "Hegel's Phenomenology: The Sociality of Reason"
        self.assertLess(HeldTitles(("hegel", "hegel a life")).best_for(cited), CONFIRMATION_THRESHOLD)

    def test_a_work_whose_only_title_is_one_word_matches_a_title_opening_with_it(self) -> None:
        self.assertEqual(100.0, HeldTitles(("pragmatism",)).best_for("Pragmatism as a Principle and Method"))

    def test_an_alias_that_is_no_shortening_of_the_title_is_kept(self) -> None:
        titles = ("elements of the philosophy of right", "philosophy of right")
        self.assertEqual(100.0, HeldTitles(titles).best_for("Philosophy of Right"))


class TestScoredMatchBands(unittest.TestCase):
    def test_a_score_at_the_automatic_threshold_is_automatic(self) -> None:
        self.assertTrue(ScoredMatch(EXPLICIT, AUTOMATIC_THRESHOLD).is_automatic)

    def test_a_score_between_the_thresholds_needs_confirmation(self) -> None:
        match = ScoredMatch(EXPLICIT, CONFIRMATION_THRESHOLD)
        self.assertEqual((False, True), (match.is_automatic, match.needs_confirmation))

    def test_a_score_below_the_confirmation_threshold_is_neither(self) -> None:
        match = ScoredMatch(EXPLICIT, CONFIRMATION_THRESHOLD - 1)
        self.assertEqual((False, False), (match.is_automatic, match.needs_confirmation))


if __name__ == "__main__":
    unittest.main()
