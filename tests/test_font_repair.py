from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _clean.cmap import ZERO_WIDTH_SPACE, ToUnicodeCMap
from _clean.fonts import glyph_name_char
from _clean.glyphs import GlyphName

BFCHAR_ONE_BYTE = (
    "1 begincodespacerange <00> <FF> endcodespacerange\n"
    "2 beginbfchar\n<01> <2738>\n<02> <00660069>\nendbfchar\n"
)
BFRANGE_ONE_BYTE = (
    "1 begincodespacerange <01> <04> endcodespacerange\n"
    "2 beginbfrange\n<01> <03> <0041>\n<04> <04> <2742>\nendbfrange\n"
)
BFCHAR_TWO_BYTE = (
    "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
    "1 beginbfchar\n<0041> <E000>\nendbfchar\n"
)
BFRANGE_TWO_BYTE = (
    "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
    "1 beginbfrange\n<0010> <0012> [<0061> <0062> <0063>]\nendbfrange\n"
)
BFRANGE_UNPAIRED_SURROGATE = (
    "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
    "1 beginbfrange\n<0020> <0021> <D800>\nendbfrange\n"
)


class TestCMapParsing(unittest.TestCase):
    def test_bfchar_maps_each_one_byte_code_to_its_target(self) -> None:
        self.assertEqual({"01": "✸", "02": "fi"}, ToUnicodeCMap(BFCHAR_ONE_BYTE).mappings())

    def test_bfrange_one_byte_codes_increment_the_target(self) -> None:
        self.assertEqual({"01": "A", "02": "B", "03": "C", "04": "❂"},
                         ToUnicodeCMap(BFRANGE_ONE_BYTE).mappings())

    def test_bfchar_maps_a_two_byte_code_to_its_target(self) -> None:
        self.assertEqual({"0041": ""}, ToUnicodeCMap(BFCHAR_TWO_BYTE).mappings())

    def test_bfrange_with_an_array_maps_each_code_to_its_listed_target(self) -> None:
        self.assertEqual({"0010": "a", "0011": "b", "0012": "c"}, ToUnicodeCMap(BFRANGE_TWO_BYTE).mappings())


class TestCMapRegeneration(unittest.TestCase):
    def _round_trip(self, text: str, overrides: dict | None = None) -> ToUnicodeCMap:
        return ToUnicodeCMap(ToUnicodeCMap(text).patched(overrides or {}))

    def test_bfchar_one_byte_codes_round_trip(self) -> None:
        self.assertEqual(ToUnicodeCMap(BFCHAR_ONE_BYTE).mappings(), self._round_trip(BFCHAR_ONE_BYTE).mappings())

    def test_bfrange_one_byte_codes_round_trip(self) -> None:
        self.assertEqual(ToUnicodeCMap(BFRANGE_ONE_BYTE).mappings(), self._round_trip(BFRANGE_ONE_BYTE).mappings())

    def test_bfchar_two_byte_codes_round_trip(self) -> None:
        self.assertEqual(ToUnicodeCMap(BFCHAR_TWO_BYTE).mappings(), self._round_trip(BFCHAR_TWO_BYTE).mappings())

    def test_bfrange_two_byte_codes_round_trip(self) -> None:
        self.assertEqual(ToUnicodeCMap(BFRANGE_TWO_BYTE).mappings(), self._round_trip(BFRANGE_TWO_BYTE).mappings())

    def test_the_codespace_lines_are_preserved(self) -> None:
        self.assertIn("1 begincodespacerange <01> <04> endcodespacerange", ToUnicodeCMap(BFRANGE_ONE_BYTE).patched({}))

    def test_a_patched_code_takes_its_new_target(self) -> None:
        self.assertEqual("◊", self._round_trip(BFCHAR_ONE_BYTE, {"01": "◊"}).mappings()["01"])

    def test_a_deleted_code_maps_to_a_zero_width_space(self) -> None:
        self.assertEqual(ZERO_WIDTH_SPACE, self._round_trip(BFCHAR_ONE_BYTE, {"01": ""}).mappings()["01"])

    def test_a_multi_character_target_is_written_as_utf16(self) -> None:
        self.assertIn("<02> <00660069>", ToUnicodeCMap(BFCHAR_ONE_BYTE).patched({}))

    def test_an_unpaired_surrogate_target_round_trips(self) -> None:
        self.assertEqual(ToUnicodeCMap(BFRANGE_UNPAIRED_SURROGATE).mappings(),
                         self._round_trip(BFRANGE_UNPAIRED_SURROGATE).mappings())

    def test_a_code_is_patched_alongside_an_unpaired_surrogate_target(self) -> None:
        self.assertEqual(".", self._round_trip(BFRANGE_UNPAIRED_SURROGATE, {"0021": "."}).mappings()["0021"])


class TestGlyphNameCharacter(unittest.TestCase):
    def test_a_standard_glyph_name_resolves_to_its_character(self) -> None:
        self.assertEqual(["A", "ś", "ę"], [glyph_name_char(name) for name in ("A", "sacute", "eogonek")])

    def test_an_unknown_glyph_name_resolves_to_nothing(self) -> None:
        self.assertIsNone(glyph_name_char("notaglyph"))


class TestGlyphNameIdentity(unittest.TestCase):
    def _identity(self, name: str) -> str | None:
        return GlyphName(name).identity()

    def test_an_sc_suffix_resolves_to_the_lowercase_letter(self) -> None:
        self.assertEqual("e", self._identity("e.sc"))

    def test_an_smcp_suffix_resolves_to_the_lowercase_letter(self) -> None:
        self.assertEqual("a", self._identity("A.smcp"))

    def test_a_small_suffix_resolves_to_the_lowercase_letter(self) -> None:
        self.assertEqual("a", self._identity("Asmall"))

    def test_a_two_letter_small_capital_resolves_to_both_lowercase_letters(self) -> None:
        self.assertEqual("ae", self._identity("AEsmall"))

    def test_a_joined_oldstyle_figure_resolves_to_its_digit(self) -> None:
        self.assertEqual("0", self._identity("zerooldstyle"))

    def test_a_dotted_oldstyle_figure_resolves_to_its_digit(self) -> None:
        self.assertEqual("1", self._identity("one.oldstyle"))

    def test_an_onum_figure_resolves_to_its_digit(self) -> None:
        self.assertEqual("2", self._identity("two.onum"))

    def test_a_lining_figure_resolves_to_its_digit(self) -> None:
        self.assertEqual("3", self._identity("three.lf"))

    def test_a_fitted_figure_resolves_to_its_digit(self) -> None:
        self.assertEqual("4", self._identity("four.fitted"))

    def test_an_underscored_ligature_resolves_to_its_letters(self) -> None:
        self.assertEqual("ffi", self._identity("f_f_i"))

    def test_a_plain_ligature_resolves_to_its_letters(self) -> None:
        self.assertEqual("fl", self._identity("fl"))

    def test_the_th_ligature_resolves_to_th(self) -> None:
        self.assertEqual("Th", self._identity("T_h"))

    def test_a_uni_name_outside_the_suspect_blocks_resolves_to_its_character(self) -> None:
        self.assertEqual("é", self._identity("uni00E9"))

    def test_a_u_name_beyond_the_basic_plane_resolves_to_its_character(self) -> None:
        self.assertEqual("\U0001F600", self._identity("u1F600"))

    def test_uni_name_inside_the_private_use_area_is_unresolved(self) -> None:
        self.assertIsNone(self._identity("uniF6BE"))

    def test_uni_name_inside_dingbats_is_unresolved(self) -> None:
        self.assertIsNone(self._identity("uni2738"))

    def test_a_bare_glyph_name_is_unresolved(self) -> None:
        self.assertIsNone(self._identity("a51"))

    def test_a_word_before_small_is_not_a_small_capital(self) -> None:
        self.assertIsNone(self._identity("ampersandsmall"))


if __name__ == "__main__":
    unittest.main()
