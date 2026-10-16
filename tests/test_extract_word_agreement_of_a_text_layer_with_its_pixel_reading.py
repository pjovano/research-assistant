from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.layersample import MIN_AGREEMENT
from _extract.wordagreement import WordSequence

PASSAGES = {
    "English": "The understanding prescribes its laws to nature, and reason seeks the unconditioned beyond them.",
    "German": "Der Verstand schöpft seine Gesetze nicht aus der Natur, sondern schreibt sie dieser vor.",
    "French": "La conscience de soi n'est pas une chose parmi les choses, mais la condition de leur apparaître.",
    "Latin": "Cogito ergo sum, quod est primum et certissimum omnium quae ordine philosophanti occurrunt.",
    "Greek": "Πάντες ἄνθρωποι τοῦ εἰδέναι ὀρέγονται φύσει· σημεῖον δ' ἡ τῶν αἰσθήσεων ἀγάπησις.",
}
LEFT_PAGE = ["the first page opens its argument here", "and carries the argument further down",
             "until the first page closes its case"]
RIGHT_PAGE = ["a second page answers every objection", "that its readers raised against the view",
              "and ends by restating the second thesis"]
MISREAD_EVERY = 4


def misread(text: str) -> str:
    words = text.split()
    return " ".join(word[::-1] + "x" if index % MISREAD_EVERY == 0 else word for index, word in enumerate(words))


def agreement(layer: str, pixels: str) -> float:
    return WordSequence(layer).agreement_with(WordSequence(pixels))


class TestTheAgreementOfALayerWithItsPixelReading(unittest.TestCase):
    def test_a_layer_holding_the_same_words_agrees_fully_in_every_script(self) -> None:
        for language, passage in PASSAGES.items():
            with self.subTest(language=language):
                self.assertEqual(1.0, agreement(passage, passage))

    def test_a_layer_misreading_a_quarter_of_its_words_falls_below_the_agreement_a_sample_needs(self) -> None:
        for language, passage in PASSAGES.items():
            with self.subTest(language=language):
                self.assertLess(agreement(misread(passage), passage), MIN_AGREEMENT)

    def test_a_layer_interleaving_the_lines_of_two_pages_falls_below_the_agreement_a_sample_needs(self) -> None:
        interleaved = "\n".join(line for pair in zip(LEFT_PAGE, RIGHT_PAGE) for line in pair)
        self.assertLess(agreement(interleaved, "\n".join(LEFT_PAGE + RIGHT_PAGE)), MIN_AGREEMENT)

    def test_a_word_broken_across_a_line_end_by_a_hyphen_counts_as_the_word(self) -> None:
        self.assertEqual(1.0, agreement("the transcen-\ndental deduction", "the transcendental deduction"))

    def test_case_and_digits_never_count_against_the_layer(self) -> None:
        self.assertEqual(1.0, agreement("THE Critique, 1781", "the critique 1787"))

    def test_a_pixel_reading_without_words_agrees_with_nothing(self) -> None:
        self.assertEqual(0.0, agreement("some words", ""))


if __name__ == "__main__":
    unittest.main()
