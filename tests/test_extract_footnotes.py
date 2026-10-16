from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.labels import BracketedNotation
from _extract.footnotes import FootnoteLabels, FootnoteLog, FootnotePairer


def definition_texts(paired) -> list[str]:
    return [definition.rendered() for definition in paired.definitions]


class TestFootnotePairer(unittest.TestCase):
    def setUp(self) -> None:
        self.log = FootnoteLog()
        self.pairer = FootnotePairer(FootnoteLabels(), self.log)

    def test_a_mark_is_replaced_by_a_label_of_its_printed_numeral_and_the_definition_follows(self) -> None:
        paired = self.pairer.paired(1, ["text<sup>18</sup> more"], ["18. Burkhardt, p. 527."])
        self.assertEqual((["text[^18] more"], ["[^18]: Burkhardt, p. 527."]),
                         (paired.body_texts, definition_texts(paired)))

    def test_a_footnote_opening_on_a_bold_number_defines_its_mark_under_its_printed_numeral(self) -> None:
        paired = self.pairer.paired(1, ["whole<sup>2</sup> more"], ["**2** For the description see KrV, B 466."])
        self.assertEqual((["whole[^2] more"], ["[^2]: For the description see KrV, B 466."]),
                         (paired.body_texts, definition_texts(paired)))

    def test_a_footnote_opening_on_a_bold_superscript_number_defines_its_mark_under_its_printed_numeral(self) -> None:
        paired = self.pairer.paired(1, ["whole<sup>12</sup>"], ["**<sup>12</sup>** See Allison (2004)."])
        self.assertEqual(["[^12]: See Allison (2004)."], definition_texts(paired))

    def test_a_footnote_opening_on_bold_prose_keeps_its_emphasis_under_its_printed_numeral(self) -> None:
        paired = self.pairer.paired(1, ["a<sup>3</sup>"], ["3 **Nota bene** the text."])
        self.assertEqual(["[^3]: **Nota bene** the text."], definition_texts(paired))

    def test_labels_keep_counting_across_pages_that_restart_numbering(self) -> None:
        self.pairer.paired(1, ["a<sup>1</sup>"], ["1. First."])
        paired = self.pairer.paired(2, ["b<sup>1</sup>"], ["1. Second."])
        self.assertEqual(["b[^2]"], paired.body_texts)

    def test_an_unnumbered_footnote_block_continues_the_previous_definition(self) -> None:
        self.pairer.paired(1, ["a<sup>1</sup>"], ["1. Begins here"])
        self.pairer.paired(2, [], ["and ends here."])
        self.assertEqual("[^1]: Begins here and ends here.", self.pairer.continuations()[0].rendered())

    def test_a_mark_with_no_definition_stays_a_superscript(self) -> None:
        paired = self.pairer.paired(1, ["a<sup>7</sup>"], [])
        self.assertEqual(["a<sup>7</sup>"], paired.body_texts)

    def test_a_mark_with_no_definition_is_logged(self) -> None:
        self.pairer.paired(1, ["a<sup>7</sup>"], [])
        self.assertIn("mark 7 has no footnote", self.log.entries()[0])

    def test_a_definition_with_no_mark_is_written_unmarked_keeping_its_printed_number(self) -> None:
        paired = self.pairer.paired(1, ["prose"], ["4. Orphan."])
        self.assertEqual((["[^1]: 4. Orphan."], [False]),
                         (definition_texts(paired), [definition.marked for definition in paired.definitions]))

    def test_a_definition_with_no_mark_counts_toward_the_page_text_the_checks_measure(self) -> None:
        paired = self.pairer.paired(1, ["prose"], ["4. Orphan."])
        self.assertEqual(["4. Orphan."], paired.footnote_texts())

    def test_a_definition_with_no_mark_is_logged(self) -> None:
        self.pairer.paired(1, ["prose"], ["4. Orphan."])
        self.assertIn("footnote 4 has no mark", self.log.entries()[0])


class TestRunOnFootnotes(unittest.TestCase):
    def setUp(self) -> None:
        self.pairer = FootnotePairer(FootnoteLabels(), FootnoteLog())

    def test_consecutive_notes_set_on_one_line_each_define_their_mark(self) -> None:
        paired = self.pairer.paired(1, ["the matter<sup>1</sup> and notion<sup>2</sup>"],
                                    ["1 die Sache selbst. 2 Vorstellung."])
        self.assertEqual((["the matter[^1] and notion[^2]"], ["[^1]: die Sache selbst.", "[^2]: Vorstellung."]),
                         (paired.body_texts, definition_texts(paired)))

    def test_a_run_of_three_notes_after_an_italic_gloss_is_split_each_under_its_printed_numeral(self) -> None:
        paired = self.pairer.paired(1, ["a<sup>47</sup> b<sup>48</sup> c<sup>49</sup>"],
                                    ["47 *an der Sache selbst*. 48 der Grund. 49 aufgefaßt."])
        self.assertEqual(["[^47]: *an der Sache selbst*.", "[^48]: der Grund.", "[^49]: aufgefaßt."],
                         definition_texts(paired))

    def test_a_note_opening_inside_a_block_that_continues_the_note_above_is_split(self) -> None:
        paired = self.pairer.paired(1, ["freedom<sup>1</sup> and nature<sup>2</sup>"],
                                    ["1 Dennett, Freedom Evolves; see his Breaking the Spell",
                                     "(New York: Penguin, 2002). 2 Most naturalists are methodological."])
        self.assertEqual(["[^1]: Dennett, Freedom Evolves; see his Breaking the Spell (New York: Penguin, 2002).",
                          "[^2]: Most naturalists are methodological."], definition_texts(paired))

    def test_a_note_without_end_punctuation_splits_from_the_next_opening_on_a_capital_each_under_its_numeral(
            self) -> None:
        paired = self.pairer.paired(1, ["a<sup>9</sup> b<sup>10</sup>"],
                                    ["9 Hegel, Philosophy of Right, §38 10 See the remark to §46."])
        self.assertEqual(["[^9]: Hegel, Philosophy of Right, §38", "[^10]: See the remark to §46."],
                         definition_texts(paired))

    def test_a_page_reference_inside_a_note_is_not_a_new_note_and_each_note_keeps_its_printed_numeral(self) -> None:
        paired = self.pairer.paired(1, ["a<sup>3</sup> b<sup>4</sup>"], ["3 See p. 4 below.", "4 Second."])
        self.assertEqual(["[^3]: See p. 4 below.", "[^4]: Second."], definition_texts(paired))

    def test_a_following_number_with_no_mark_on_the_page_is_not_a_new_note_and_the_note_keeps_its_printed_numeral(
            self) -> None:
        paired = self.pairer.paired(1, ["a<sup>3</sup>"], ["3 Read it. 4 times over."])
        self.assertEqual(["[^3]: Read it. 4 times over."], definition_texts(paired))


class TestContinuations(unittest.TestCase):
    def setUp(self) -> None:
        self.pairer = FootnotePairer(FootnoteLabels(), FootnoteLog())
        self.pairer.paired(1, ["a<sup>1</sup>"], ["1. Begins here"])
        self.pairer.paired(2, [], ["and ends here."])

    def test_asking_for_continuations_leaves_them_in_place(self) -> None:
        self.pairer.continuations()
        self.assertEqual(1, len(self.pairer.continuations()))

    def test_clearing_continuations_empties_them(self) -> None:
        self.pairer.clear_continuations()
        self.assertEqual([], self.pairer.continuations())

    def test_leading_unnumbered_text_with_no_open_note_is_an_unmarked_definition_counted_apart_from_the_marked_notes(
            self) -> None:
        paired = FootnotePairer(FootnoteLabels(), FootnoteLog()).paired(1, ["a<sup>1</sup>"], ["stray", "1. One."])
        self.assertEqual(["[^1]: One.", "[^1]: stray"], definition_texts(paired))

    def test_a_note_opening_with_a_parenthesised_number_under_no_superscript_mark_is_an_unmarked_definition(
            self) -> None:
        paired = FootnotePairer(FootnoteLabels(), FootnoteLog()).paired(1, ["dit Hegel (1), par"], ["(1) Voyez."])
        self.assertEqual(["[^1]: (1) Voyez."], definition_texts(paired))


class TestBracketedNotation(unittest.TestCase):
    def test_brackets_are_escaped_except_footnote_marks_and_placeholders(self) -> None:
        resolved = BracketedNotation().resolved("see [Kant] and ❲[x]❳ and [^1]")
        self.assertEqual("see \\[Kant\\] and ❲[x]❳ and [^1]", resolved)

    def test_a_bracket_whose_partner_is_on_another_line_is_escaped(self) -> None:
        resolved = BracketedNotation().resolved("❲n❳] ❲t0❳tr\n(c) [❲ft′1❳xr :❲=❳ xr .")
        self.assertEqual("❲n❳\\] ❲t0❳tr\n(c) \\[❲ft′1❳xr :❲=❳ xr .", resolved)

    def test_an_escaped_bracket_is_not_escaped_twice(self) -> None:
        self.assertEqual("\\[Weakening\\]", BracketedNotation().resolved("\\[Weakening\\]"))


if __name__ == "__main__":
    unittest.main()
