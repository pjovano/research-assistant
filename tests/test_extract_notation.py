from __future__ import annotations

import unittest
from dataclasses import dataclass

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import Block
from _extract.enginemath import EngineNotation
from _extract.layer import LayerChar
from _extract.layerhtml import BlockHtml
from _extract.layerlines import PageLines
from _extract.markdown import HtmlToMarkdown
from _extract.statements import StatementLabel
from _extract_fixtures import DESCENT_SHARE, FakeHyphens, FakeLayer

PROSE_FONT = "Sabon"
SYMBOL_FONT = "CMSY10"
BODY_SIZE = 10.0
SCRIPT_SIZE = 7.0
BASELINE = 100.0
ADVANCE = 6.0
SPACE_SHARE = 0.25
SHRUNK_LINE_SIZE = 12.0
SHRUNK_WORD_GAP = 1.8
KERNED_LETTER_GAP = 1.6
SMALL_TYPE_WORD_GAP = 1.5


@dataclass(frozen=True)
class CharStyle:
    font: str = PROSE_FONT
    size: float = BODY_SIZE
    baseline: float = BASELINE
    raised: bool = False
    italic: bool = False
    bold: bool = False
    gap: float = 0.0


class Line:
    def __init__(self, number: int = 0) -> None:
        self._chars: list[LayerChar] = []
        self._x = 10.0
        self._number = number

    def add(self, text: str, style: CharStyle = CharStyle()) -> "Line":
        self._x += style.gap
        size, baseline = style.size, style.baseline
        for char in text:
            width = SPACE_SHARE * size if char == " " else ADVANCE * size / BODY_SIZE
            box = (self._x, baseline - size, self._x + width, baseline + size * DESCENT_SHARE)
            self._chars.append(LayerChar(char, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), style.raised, size,
                                         style.bold, style.italic, style.font, (self._x, baseline), box,
                                         self._number))
            self._x = box[2]
        return self

    def chars(self) -> list[LayerChar]:
        return list(self._chars)


def written(chars: list[LayerChar], hyphens: FakeHyphens | None = None) -> str:
    return BlockHtml(hyphens or FakeHyphens()).of([chars])


class TestBlockHtml(unittest.TestCase):
    def test_notation_characters_are_written_as_the_page_sets_them(self) -> None:
        chars = Line().add("Let ").add("Γ≻Δ", CharStyle(SYMBOL_FONT)).add(" hold.").chars()
        self.assertEqual("Let Γ≻Δ hold.", written(chars))

    def test_prose_italics_and_bold_keep_their_tags(self) -> None:
        chars = (Line().add("4.5 Definition", CharStyle(bold=True)).add(" is ")
                 .add("true", CharStyle(italic=True)).chars())
        self.assertEqual("<b>4.5 Definition</b> is <i>true</i>", written(chars))

    def test_a_word_gap_where_the_style_changes_sits_outside_the_new_tag(self) -> None:
        chars = Line().add("ABSTRACT").add("This paper", CharStyle(italic=True, gap=5.0)).chars()
        self.assertEqual("ABSTRACT <i>This paper</i>", written(chars))

    def test_a_word_gap_shrunk_under_two_points_still_opens_a_word_at_its_type_size(self) -> None:
        chars = (Line().add("What", CharStyle(size=SHRUNK_LINE_SIZE))
                 .add("are", CharStyle(size=SHRUNK_LINE_SIZE, gap=SHRUNK_WORD_GAP)).chars())
        self.assertEqual("What are", written(chars))

    def test_a_gap_narrower_than_a_word_gap_for_its_type_size_stays_inside_the_word(self) -> None:
        chars = (Line().add("Wh", CharStyle(size=SHRUNK_LINE_SIZE))
                 .add("at", CharStyle(size=SHRUNK_LINE_SIZE, gap=KERNED_LETTER_GAP)).chars())
        self.assertEqual("What", written(chars))

    def test_a_word_gap_of_small_type_opens_a_word_below_two_points(self) -> None:
        chars = (Line().add("see", CharStyle(size=SCRIPT_SIZE))
                 .add("note", CharStyle(size=SCRIPT_SIZE, gap=SMALL_TYPE_WORD_GAP)).chars())
        self.assertEqual("see note", written(chars))

    def test_a_small_raised_digit_is_a_superscript(self) -> None:
        chars = Line().add("word").add("1", CharStyle(size=SCRIPT_SIZE, baseline=BASELINE - 3.0, raised=True)).chars()
        self.assertEqual("word<sup>1</sup>", written(chars))

    def test_a_full_size_character_the_layer_flags_raised_is_not_a_superscript(self) -> None:
        chars = Line().add("word").add("s", CharStyle(raised=True)).chars()
        self.assertEqual("words", written(chars))

    def test_a_letter_set_in_a_fraktur_font_is_written_as_the_fraktur_letter(self) -> None:
        self.assertEqual("ℑ and ℑ", written(Line().add("I", CharStyle("EUFM10")).add(" and ")
                                            .add("ℑ", CharStyle("EUFM10")).chars()))

    def test_a_letter_set_in_a_blackboard_font_is_written_as_the_double_struck_letter(self) -> None:
        self.assertEqual("ℕ", written(Line().add("N", CharStyle("ABCDEF+MSBM10")).chars()))

    def test_a_capital_in_the_tex_symbol_font_is_written_as_the_script_letter(self) -> None:
        self.assertEqual("𝒜ℒ", written(Line().add("AL", CharStyle(SYMBOL_FONT)).chars()))

    def test_a_ligature_is_written_as_its_letters(self) -> None:
        self.assertEqual("finite", written(Line().add("ﬁnite").chars()))

    def test_a_negation_overlay_composes_with_the_character_after_it(self) -> None:
        chars = (Line().add("x").add("\u0338", CharStyle(SYMBOL_FONT)).add(" ")
                 .add("=", CharStyle(SYMBOL_FONT)).add(" y").chars())
        self.assertEqual("x ≠ y", written(chars))

    def test_a_less_than_sign_is_escaped_in_the_html_and_restored_in_the_markdown(self) -> None:
        chars = Line().add("k").add("<", CharStyle(SYMBOL_FONT)).add("A and more").chars()
        self.assertEqual(("k&lt;A and more", "k<A and more"),
                         (written(chars), HtmlToMarkdown().text(written(chars))))

    def test_flowed_rows_join_into_one_line(self) -> None:
        rows = [Line(0).add("Γ", CharStyle(SYMBOL_FONT)).chars(), Line(1).add("Δ", CharStyle(SYMBOL_FONT)).chars()]
        self.assertEqual("Γ Δ", BlockHtml(FakeHyphens()).of(rows))

    def test_the_rows_of_a_display_keep_their_own_lines(self) -> None:
        rows = [Line(0).add("Γ", CharStyle(SYMBOL_FONT)).chars(), Line(1).add("Δ", CharStyle(SYMBOL_FONT)).chars()]
        self.assertEqual("Γ<br>Δ", BlockHtml(FakeHyphens()).stacked(rows))


class TestLineBreakHyphens(unittest.TestCase):
    def _joined(self, kept: set[str]) -> str:
        rows = [Line(0).add("de-").chars(), Line(1).add("fined").chars()]
        return BlockHtml(FakeHyphens(kept)).of(rows)

    def test_a_hyphen_broken_across_lines_is_dropped(self) -> None:
        self.assertEqual("defined", self._joined(set()))

    def test_a_word_the_document_hyphenates_inside_a_line_keeps_its_hyphen(self) -> None:
        self.assertEqual("de-fined", self._joined({"de-fined"}))

    def test_a_hyphen_broken_across_lines_inside_italics_rejoins_the_word_in_one_run(self) -> None:
        rows = [Line(0).add("Come For-", CharStyle(italic=True)).chars(),
                Line(1).add("ward as Science", CharStyle(italic=True)).chars()]
        self.assertEqual("<i>Come Forward as Science</i>", BlockHtml(FakeHyphens()).of(rows))

    def test_an_italic_run_crossing_a_line_break_stays_one_run(self) -> None:
        rows = [Line(0).add("See ").add("Encyclopedia of", CharStyle(italic=True)).chars(),
                Line(1).add("the Sciences", CharStyle(italic=True)).add(" here.").chars()]
        self.assertEqual("See <i>Encyclopedia of the Sciences</i> here.", BlockHtml(FakeHyphens()).of(rows))

    def test_a_line_closing_one_style_and_the_next_opening_another_keeps_both(self) -> None:
        rows = [Line(0).add("Title", CharStyle(italic=True)).chars(),
                Line(1).add("Heading", CharStyle(bold=True)).chars()]
        self.assertEqual("<i>Title</i> <b>Heading</b>", BlockHtml(FakeHyphens()).of(rows))


class TestPageLines(unittest.TestCase):
    def test_a_line_belongs_to_the_block_whose_box_holds_it(self) -> None:
        blocks = [Block(1, "Text", "", (0.0, 80.0, 200.0, 120.0), {}, "first"),
                  Block(1, "Text", "", (0.0, 120.0, 200.0, 160.0), {}, "second")]
        chars = Line(0).add("above").chars() + Line(1).add("below", CharStyle(baseline=BASELINE + 40.0)).chars()
        lines = PageLines(FakeLayer(chars), 1, blocks)
        self.assertEqual([["above"], ["below"]], [[_spelled(row) for row in lines.of(block)] for block in blocks])

    def test_a_line_under_two_overlapping_boxes_is_written_once(self) -> None:
        blocks = [Block(1, "Text", "", (0.0, 80.0, 200.0, 120.0), {}, "first"),
                  Block(1, "Text", "", (0.0, 85.0, 200.0, 130.0), {}, "second")]
        lines = PageLines(FakeLayer(Line(0).add("once").chars()), 1, blocks)
        self.assertEqual(1, sum(len(lines.of(block)) for block in blocks))


def _spelled(row: list[LayerChar]) -> str:
    return "".join(char.char for char in row)


class TestStatementLabel(unittest.TestCase):
    def test_a_numbered_bold_label_names_a_statement(self) -> None:
        self.assertEqual("1.10 Henkin's Theorem", StatementLabel().of("**1.10 Henkin's Theorem.** Let Φ be"))

    def test_a_bold_word_without_a_number_is_not_a_statement(self) -> None:
        self.assertIsNone(StatementLabel().of("**Proof.** We proceed"))

    def test_the_label_is_taken_off_the_paragraph(self) -> None:
        self.assertEqual("Let Φ be", StatementLabel().without("**1.10 Henkin's Theorem.** Let Φ be"))


class TestControlCharacters(unittest.TestCase):
    def test_a_control_character_in_prose_is_dropped(self) -> None:
        self.assertEqual("A word", HtmlToMarkdown().text("<p>A \x02word\x10</p>"))

    def test_a_zero_width_space_in_prose_is_dropped(self) -> None:
        self.assertEqual("A word", HtmlToMarkdown().text("<p>A \u200bword\ufeff</p>"))


class TestEngineNotation(unittest.TestCase):
    def test_an_inline_engine_math_element_becomes_inline_latex(self) -> None:
        replaced = EngineNotation().replaced("a <math>\\Gamma \\succ \\Delta</math> b")
        self.assertEqual("a $\\Gamma \\succ \\Delta$ b", replaced)

    def test_a_display_engine_math_element_becomes_display_latex(self) -> None:
        html_text = '<p><math display="block">\\frac{a}{b}</math></p>'
        self.assertEqual("<p>$$\\frac{a}{b}$$</p>", EngineNotation().replaced(html_text))

    def test_a_less_than_sign_in_latex_survives_the_markdown_conversion(self) -> None:
        text = HtmlToMarkdown().text(EngineNotation().replaced("<p>so <math>a < b</math> holds</p>"))
        self.assertEqual("so $a < b$ holds", text)

    def test_a_symbol_outside_a_math_element_stays_as_written(self) -> None:
        self.assertEqual("<td>Sat Φ</td>", EngineNotation().replaced("<td>Sat Φ</td>"))

    def test_a_math_element_holding_only_control_characters_is_not_written(self) -> None:
        self.assertEqual("a  b", EngineNotation().replaced("a <math>\x03</math> b"))


if __name__ == "__main__":
    unittest.main()
