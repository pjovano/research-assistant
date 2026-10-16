from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import pagetext

from _extract.checks import (
    REASON_EMPTY_PIXELS,
    REPEAT_SAMPLE_CHARS,
    SOURCE_EXCLUDED,
    SOURCE_NONE,
    SOURCE_PIXELS,
    CheckedPage,
    PageChecks,
)
from _extract_fixtures import PROSE
from _pagetext_fixtures import FakePredictor, fake_classifier, failing_classifier

REPEATED_SLICE_CHARS = 150
REPEATS = 5
SHORT_OUTPUT_CHARS = 40
BAD_PROBABILITY = 0.9
COUNTER_ROWS = 40
REPEATED_PASSAGE = PROSE[:REPEATED_SLICE_CHARS] * REPEATS
NO_LAYER_REASON = "no text layer and no output: pass --force-ocr"


def checks(label: str = "good", probability: float | None = None) -> PageChecks:
    return PageChecks(fake_classifier(label, probability) if probability is not None else fake_classifier())


class TestPageChecks(unittest.TestCase):
    def test_a_repeated_passage_is_doubtful_naming_the_repetition(self) -> None:
        verdict = checks().verdict(1, REPEATED_PASSAGE, PROSE)
        self.assertEqual((True, True), (verdict.is_doubtful, "repeated passage" in verdict.reason))

    def test_a_repetition_reason_quotes_a_fixed_sample_of_the_passage(self) -> None:
        verdict = checks().verdict(1, REPEATED_PASSAGE, PROSE)
        self.assertEqual(f"repeated passage: {PROSE[:REPEAT_SAMPLE_CHARS]!r}", verdict.reason)

    def test_rows_that_differ_only_by_a_counter_are_a_repeated_passage(self) -> None:
        rows = "".join(f"| {number} | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |\n"
                       for number in range(1, COUNTER_ROWS))
        self.assertIn("repeated passage", checks().verdict(1, PROSE + rows, PROSE + rows).reason)

    def test_a_page_of_prose_beside_placeholders_is_kept(self) -> None:
        output = PROSE + "\n❲Γ ≻ Δ / Γ, A ≻ Δ❳\n"
        self.assertFalse(checks().verdict(1, output, PROSE).is_doubtful)

    def test_a_page_whose_output_is_far_shorter_than_its_kept_text_layer_is_doubtful(self) -> None:
        self.assertIn("output length", checks().verdict(1, PROSE[:SHORT_OUTPUT_CHARS], PROSE * 3).reason)

    def test_notation_is_stripped_before_the_quality_gate(self) -> None:
        output = PROSE + " $\\forall x$ " + "∀∃¬∧∨→ " * COUNTER_ROWS
        self.assertFalse(checks().verdict(1, output, PROSE).is_doubtful)

    def test_the_html_markup_of_a_spanning_table_is_stripped_before_the_page_checks(self) -> None:
        cells = "".join(f'<td colspan="2">{word}</td>' for word in PROSE.split())
        output = f"<table>\n<tr>{cells}</tr>\n</table>"
        self.assertFalse(checks().verdict(1, output, PROSE).is_doubtful)

    def test_a_page_with_no_text_layer_and_no_output_is_doubtful_and_names_force_ocr(self) -> None:
        [verdict] = checks().verdicts([CheckedPage(1, "", "", SOURCE_NONE)])
        self.assertEqual((True, NO_LAYER_REASON), (verdict.is_doubtful, verdict.reason))

    def test_a_page_read_from_pixels_with_no_output_is_doubtful_naming_the_empty_reading(self) -> None:
        [verdict] = checks().verdicts([CheckedPage(1, "", "", SOURCE_PIXELS)])
        self.assertEqual((True, REASON_EMPTY_PIXELS), (verdict.is_doubtful, verdict.reason))

    def test_a_page_the_scope_excludes_whole_is_kept_with_no_output(self) -> None:
        [verdict] = checks().verdicts([CheckedPage(1, "", "", SOURCE_EXCLUDED)])
        self.assertFalse(verdict.is_doubtful)

    def test_a_page_whose_content_the_policy_dropped_is_kept(self) -> None:
        self.assertFalse(checks().verdict(1, "", "").is_doubtful)

    def test_a_transcription_that_passes_is_kept_as_a_worker_transcription(self) -> None:
        [verdict] = checks().verdicts([CheckedPage.transcribed(1, PROSE)])
        self.assertEqual(("kept", "worker transcription"), (verdict.status, verdict.reason))

    def test_a_transcription_is_never_measured_against_the_text_layer(self) -> None:
        [verdict] = checks().verdicts([CheckedPage.transcribed(1, PROSE[:SHORT_OUTPUT_CHARS])])
        self.assertFalse(verdict.is_doubtful)

    def test_a_transcription_the_classifier_calls_bad_is_doubtful_again(self) -> None:
        [verdict] = checks("bad", BAD_PROBABILITY).verdicts([CheckedPage.transcribed(1, PROSE * 2)])
        self.assertEqual((True, "quality gate: classifier reads the page as bad (p=0.900)"),
                         (verdict.is_doubtful, verdict.reason))

    def test_a_transcription_repeating_a_passage_is_doubtful_again(self) -> None:
        [verdict] = checks().verdicts([CheckedPage.transcribed(1, REPEATED_PASSAGE)])
        self.assertIn("repeated passage", verdict.reason)

    def test_a_page_with_a_kept_text_layer_but_no_output_is_doubtful(self) -> None:
        self.assertIn("no text", checks().verdict(1, "", PROSE).reason)

    def test_emphasis_marks_are_stripped_before_the_quality_gate(self) -> None:
        predictor = FakePredictor("good")
        marked = "*a* * * **B** __c__ " + PROSE * 2
        PageChecks(pagetext.PageClassifier(lambda: predictor)).verdict(1, marked, PROSE * 2)
        self.assertNotIn("*", predictor.seen[0])
        self.assertNotIn("_", predictor.seen[0])

    def test_a_page_the_classifier_calls_bad_is_doubtful_naming_the_classifier(self) -> None:
        verdict = checks("bad", BAD_PROBABILITY).verdict(1, PROSE * 2, PROSE * 2)
        self.assertEqual((True, True), (verdict.is_doubtful, "classifier reads the page as bad" in verdict.reason))

    def test_an_unavailable_classifier_makes_the_page_doubtful_naming_the_unavailable_classifier(self) -> None:
        verdict = PageChecks(failing_classifier()).verdict(1, PROSE * 2, PROSE * 2)
        self.assertEqual((True, True), (verdict.is_doubtful, "classifier unavailable" in verdict.reason))


if __name__ == "__main__":
    unittest.main()
