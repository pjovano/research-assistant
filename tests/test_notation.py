from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pikepdf
import pymupdf

from _support import LiveTree

LiveTree.activate()

from confusables import compatible
from latex_symbols import LatexGate, MathMacros, with_supplementary_unicode
from math_fonts import MathFonts, is_listed_math_font
from notation import blanked_notation, delimited_spans, inside_notation, without_notation
from pylatexenc.latex2text import LatexNodes2Text

import pagetext

LOGIC_SYMBOLS = "ΓΘΛΠΣ∅∆¬·×̸′↑→∀∃∈−∧∨∩∪∼≈≤⊂⊆⊑⊓⊔⊕⊗⊢⊥⋄◦⟨⟩⪯⪰αβγδθλνπχψωϕφ⋐⋑⋓■⋆⊨□◊◁▷⟦⟧≠∗…"
PROSE_ORIGIN = (72, 100)
SYMBOL_ORIGIN = (72, 130)
DINGBAT_ORIGIN = (72, 160)
GREEK_TABLE = {"Symbol": {0x47: "Γ", 0x44: "Δ"}, "ZapfDingbats": {0x33: "✓", 0x34: "✔"}}
CMAP_TEMPLATE = ("/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
                 "1 begincodespacerange <00> <FF> endcodespacerange\n{count} beginbfchar\n{chars}endbfchar\n"
                 "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n")


def _with_unicode_tables(pdf: Path) -> None:
    with pikepdf.open(pdf, allow_overwriting_input=True) as document:
        for font in document.pages[0].Resources.Font.values():
            table = GREEK_TABLE.get(str(font.BaseFont).lstrip("/"))
            if table:
                chars = "".join(f"<{code:02X}> <{ord(char):04X}>\n" for code, char in table.items())
                font.ToUnicode = document.make_stream(CMAP_TEMPLATE.format(count=len(table), chars=chars).encode())
        document.save(pdf)


def _read_back(macro: str) -> str:
    return LatexNodes2Text().latex_to_text(with_supplementary_unicode(macro)).strip()


class TestDelimitedSpans(unittest.TestCase):
    def test_every_placeholder_on_a_page_is_found(self) -> None:
        text = "Let ❲x❳ hold.\n❲y = z❳\nDone."
        self.assertEqual(["❲x❳", "❲y = z❳"], delimited_spans(text))

    def test_without_notation_leaves_the_prose(self) -> None:
        self.assertEqual("Let   be an axiom.", without_notation("Let ❲Γ ≻ Δ❳ be an axiom."))

    def test_blanked_notation_keeps_length_and_line_breaks(self) -> None:
        text = "a ❲[[x]]❳ b\n❲[[y]]❳\nc"
        blanked = blanked_notation(text)
        self.assertEqual((len(text), text.count("\n")), (len(blanked), blanked.count("\n")))
        self.assertNotIn("[[", blanked)
        self.assertEqual("c", blanked.split("\n")[-1])

    def test_a_position_inside_a_span_is_inside_notation(self) -> None:
        text = "a ❲b. c❳ d. e"
        self.assertTrue(inside_notation(4, text))
        self.assertFalse(inside_notation(10, text))


class TestLatexNotation(unittest.TestCase):
    def test_inline_and_display_latex_are_notation_spans(self) -> None:
        text = "Let $x_0 \\neq y$ hold.\n$$\\begin{cases} a & b \\end{cases}$$\nDone."
        self.assertEqual(["$x_0 \\neq y$", "$$\\begin{cases} a & b \\end{cases}$$"], delimited_spans(text))

    def test_prose_around_latex_is_kept_when_the_latex_is_removed(self) -> None:
        self.assertEqual("Let   be an axiom.", without_notation("Let $\\Gamma \\succ \\Delta$ be an axiom."))

    def test_a_display_spanning_lines_is_one_span(self) -> None:
        text = "a\n$$x\n= y$$\nb"
        self.assertEqual(["$$x\n= y$$"], delimited_spans(text))

    def test_dollar_amounts_in_prose_are_not_notation(self) -> None:
        self.assertEqual([], delimited_spans("It cost $5 and later $10 in 1807."))

    def test_a_position_inside_latex_is_inside_notation(self) -> None:
        text = "a $b. c$ d. e"
        self.assertEqual((True, False), (inside_notation(4, text), inside_notation(10, text)))


class TestMathMacros(unittest.TestCase):
    def test_every_logic_symbol_maps_to_a_macro_that_reads_back_as_itself(self) -> None:
        macros = MathMacros()
        failures = [(char, macros.macro(char)) for char in LOGIC_SYMBOLS
                    if macros.macro(char) is None or compatible(_read_back(macros.macro(char))) != compatible(char)]
        self.assertEqual([], failures)

    def test_a_text_mode_form_is_replaced_by_its_math_macro(self) -> None:
        self.assertEqual("\\neg", MathMacros().macro("¬"))

    def test_the_ensuremath_wrapper_is_removed(self) -> None:
        self.assertEqual("\\Gamma", MathMacros().macro("Γ"))

    def test_a_latin_letter_stays_a_letter(self) -> None:
        self.assertEqual("A", MathMacros().macro("A"))

    def test_a_character_with_no_representation_has_no_macro(self) -> None:
        self.assertIsNone(MathMacros().macro("\x07"))


class TestLatexGate(unittest.TestCase):
    def test_an_unbalanced_brace_is_rejected(self) -> None:
        self.assertFalse(LatexGate().parses("x_{2"))

    def test_a_stray_closing_brace_is_rejected(self) -> None:
        self.assertFalse(LatexGate().parses("x^{2}}"))

    def test_a_well_formed_span_passes(self) -> None:
        self.assertTrue(LatexGate().parses("\\Gamma \\succ \\Delta_{\\mathfrak{B}}"))


class TestMathFonts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.mkdtemp()
        cls.pdf = Path(cls.directory) / "fonts.pdf"
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text(PROSE_ORIGIN, "Prose set in the text face, with words enough.", fontname="helv")
            page.insert_text(SYMBOL_ORIGIN, "GD", fontname="symb")
            page.insert_text(DINGBAT_ORIGIN, "34", fontname="zadb")
            document.save(cls.pdf)
        _with_unicode_tables(cls.pdf)
        cls.fonts = MathFonts(cls.pdf)

    def test_a_listed_font_is_a_math_font(self) -> None:
        self.assertTrue(self.fonts.is_math("Symbol"))

    def test_the_prose_font_is_not(self) -> None:
        self.assertFalse(self.fonts.is_math("Helvetica"))

    def test_a_font_of_symbols_is_a_math_font_by_measure(self) -> None:
        self.assertTrue(self.fonts.is_math("ZapfDingbats"))

    def test_the_families_are_listed(self) -> None:
        self.assertEqual(["Symbol", "ZapfDingbats"], self.fonts.families())

    def test_the_prose_text_of_a_page_omits_the_math_font_characters(self) -> None:
        prose = self.fonts.prose_text(1)
        self.assertIn("Prose set in the text face", prose)
        self.assertNotIn("Γ", prose)
        self.assertNotIn("Δ", prose)

    def test_notation_characters_are_those_never_set_in_a_prose_font(self) -> None:
        self.assertEqual({"Γ", "Δ", "✓", "✔"}, self.fonts.notation_characters())

    def test_a_subset_prefix_does_not_hide_a_listed_name(self) -> None:
        self.assertTrue(is_listed_math_font("ABCDEF+CMSY10"))

    def test_a_math_token_in_a_name_lists_it(self) -> None:
        self.assertTrue(is_listed_math_font("STIXTwoMath-Regular"))
        self.assertFalse(is_listed_math_font("Mathematica"))



class TestProseOnlyVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        TestMathFonts.setUpClass()
        cls.pdf = TestMathFonts.pdf

    def test_a_delimited_span_is_removed_from_the_quotation_and_reported(self) -> None:
        quoted = pagetext.QuotedNotation(self.pdf, "Prose set in the ❲Γ Δ❳ text face")
        self.assertEqual(("❲Γ Δ❳",), quoted.removed().spans)
        self.assertEqual("Prose set in the   text face", quoted.prose())

    def test_the_prose_verifies_against_the_page_with_notation_removed(self) -> None:
        quoted = pagetext.QuotedNotation(self.pdf, "Prose set in the text face, ❲Γ❳ with words enough")
        [hit, *_rest] = pagetext.find_quote_in_texts(self.pdf, quoted.prose(), quoted.prose_pages())
        self.assertTrue(hit.exact)

    def test_a_quotation_without_notation_removes_nothing(self) -> None:
        self.assertTrue(pagetext.QuotedNotation(self.pdf, "Prose set in the text face").removed().is_empty)

    def test_a_notation_character_written_bare_is_removed_by_font(self) -> None:
        quoted = pagetext.QuotedNotation(self.pdf, "Prose set in the Γ text face")
        self.assertEqual(("Γ",), quoted.removed().characters)


class TestNotationSetPartlyInTheProseFont(unittest.TestCase):
    QUOTE = "The things at the end are clearly $\\Gamma P$. In the middle there appear to be borderline cases."

    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.mkdtemp()
        cls.pdf = Path(cls.directory) / "variables.pdf"
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((72, 100), "The things at the end are clearly", fontname="helv")
            page.insert_text((250, 100), "G", fontname="symb")
            page.insert_text((260, 100), "P. In the middle there appear to be borderline cases.", fontname="helv")
            document.save(cls.pdf)
        _with_unicode_tables(cls.pdf)

    def test_the_prose_with_the_span_removed_does_not_match_the_page_that_keeps_its_letter(self) -> None:
        quoted = pagetext.QuotedNotation(self.pdf, self.QUOTE)
        hits = pagetext.find_quote_in_texts(self.pdf, quoted.prose(), quoted.prose_pages())
        self.assertFalse(any(hit.exact for hit in hits))

    def test_the_prose_around_the_span_is_found_with_the_page_setting_the_span_its_own_way(self) -> None:
        [hit] = pagetext.find_quote_around_notation(self.pdf, self.QUOTE)
        self.assertEqual((True, "The things at the end are clearly Γ P. In the middle there appear to be borderline cases."),
                         (hit.exact, hit.page_text))

    def test_prose_the_page_sets_otherwise_is_not_found_whatever_the_span(self) -> None:
        altered = self.QUOTE.replace("borderline", "doubtful")
        self.assertEqual([], pagetext.find_quote_around_notation(self.pdf, altered))

    def test_more_on_the_page_than_the_span_could_set_is_not_taken_for_the_span(self) -> None:
        skipping = "The things at the end are $x$ In the middle there appear to be borderline cases."
        self.assertEqual([], pagetext.find_quote_around_notation(self.pdf, skipping))


class TestConfusableNotation(unittest.TestCase):
    def test_a_confusable_form_of_a_notation_character_is_removed_by_font(self) -> None:
        TestMathFonts.setUpClass()
        quoted = pagetext.QuotedNotation(TestMathFonts.pdf, "Prose set in the ∆ text face")
        self.assertEqual(("∆",), quoted.removed().characters)


class TestWordHyphens(unittest.TestCase):
    def test_a_true_hyphen_inside_a_word_is_dropped_on_both_sides(self) -> None:
        self.assertEqual(pagetext.normalize("Ketonen-\nstyle rules"), pagetext.normalize("Ketonen-style rules"))
        self.assertEqual("ketonenstyle rules", pagetext.normalize("Ketonen-style rules"))


if __name__ == "__main__":
    unittest.main()
