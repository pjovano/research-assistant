from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _font_fixtures import (
    FIRST_PAGE_INDEX,
    SYMBOL_CODE,
    SYMBOL_PRIVATE_USE_CHAR,
    FontFace,
    ScratchDirectory,
    occurrence_in,
    symbol_record,
)
from _clean.cmap import ToUnicodeCMap
from _clean.fonts import NO_TOUNICODE, FontRecord
from _clean.fontscan import MISSING_FROM_TOUNICODE, FontScan, FontStatusRows, ScanInput
from _clean.textlayer import Occurrences
from _font_repair_fixtures import (
    WIN_ANSI,
    MAC_ROMAN,
)

IDENTITY_OVER_DINGBATS = (
    "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
    "1 beginbfrange\n<2700> <27FF> <2700>\nendbfrange\n"
)
LONG_BASEFONT = "SNFQPQ+SymbolProportionalBT-Regular"
LONG_BASEFONT_AS_MUPDF_NAMES_IT = "SymbolProportionalBT-Reg"


class TestFlaggedCodes(unittest.TestCase):
    def test_a_control_character_target_is_flagged(self) -> None:
        record = FontRecord(1, "stmary10", frozenset(), {}, ToUnicodeCMap.from_mappings({"03": "\x07"}), None)
        self.assertEqual([("03", "\x07")], record.flagged_codes())

    def test_a_replacement_character_target_is_flagged(self) -> None:
        record = FontRecord(1, "Any", frozenset(), {}, ToUnicodeCMap.from_mappings({"03": "\ufffd"}), None)
        self.assertEqual([("03", "\ufffd")], record.flagged_codes())

    def test_an_empty_target_is_flagged(self) -> None:
        record = FontRecord(1, "Any", frozenset(), {}, ToUnicodeCMap.from_mappings({"03": ""}), None)
        self.assertEqual([("03", "")], record.flagged_codes())

    def test_an_identity_range_over_the_suspect_blocks_flags_nothing(self) -> None:
        self.assertEqual([], symbol_record(1, IDENTITY_OVER_DINGBATS).flagged_codes())

    def test_a_private_use_target_is_flagged(self) -> None:
        self.assertEqual([(SYMBOL_CODE, SYMBOL_PRIVATE_USE_CHAR)], symbol_record(1).flagged_codes())


class TestGlyphNamesBesideAToUnicodeTable(unittest.TestCase):
    def _record(self) -> FontRecord:
        cmap = ToUnicodeCMap.from_mappings({"22": "A"})
        return FontRecord(1, "ABCDEF+Symbol", frozenset(), {"21": "onequarter"}, cmap, None)

    def test_a_character_only_a_glyph_name_emits_is_traced_to_that_code(self) -> None:
        self.assertEqual(["21"], self._record().codes_for("\u00bc"))

    def test_a_character_the_table_maps_is_traced_to_the_mapped_code(self) -> None:
        self.assertEqual(["22"], self._record().codes_for("A"))


class TestGlyphNamesOfAFontWithoutToUnicode(unittest.TestCase):
    def _flagged(self, glyph_names: dict[str, str], cmap: ToUnicodeCMap | None = None) -> list[tuple[str, str]]:
        return FontRecord(1, "ABCDEF+Garamond+f6", frozenset(), glyph_names, cmap, None).flagged_codes()

    def test_a_glyph_name_naming_a_private_use_character_is_flagged(self) -> None:
        self.assertEqual([("21", "\uf64b")], self._flagged({"21": "uniF64B"}))

    def test_a_glyph_name_naming_an_ordinary_character_is_not_flagged(self) -> None:
        self.assertEqual([], self._flagged({"21": "uniFB01", "22": "Pi"}))

    def test_a_code_a_tounicode_table_leaves_unmapped_is_flagged_by_its_glyph_name(self) -> None:
        cmap = ToUnicodeCMap.from_mappings({"22": "A"})
        self.assertEqual([("21", "\uf64b")], self._flagged({"21": "uniF64B", "22": "uniF645"}, cmap))


class TestGlyphNameContradictingItsToUnicode(unittest.TestCase):
    def _flagged(self, glyph_names: dict[str, str], mappings: dict[str, str]) -> list[tuple[str, str]]:
        cmap = ToUnicodeCMap.from_mappings(mappings)
        return FontRecord(1, "ABCDEF+Minion", frozenset(), glyph_names, cmap, None).flagged_codes()

    def test_a_ligature_whose_table_gives_only_one_of_its_letters_is_flagged(self) -> None:
        self.assertEqual([("21", "h")], self._flagged({"21": "T_h"}, {"21": "h"}))

    def test_a_ligature_whose_table_gives_the_precomposed_character_is_not_flagged(self) -> None:
        self.assertEqual([], self._flagged({"21": "fi"}, {"21": "ﬁ"}))

    def test_a_ligature_whose_table_gives_its_letters_is_not_flagged(self) -> None:
        self.assertEqual([], self._flagged({"21": "f_l"}, {"21": "fl"}))

    def test_a_small_capital_whose_table_gives_the_capital_is_not_flagged(self) -> None:
        self.assertEqual([], self._flagged({"21": "A.sc"}, {"21": "A"}))

    def test_a_ligature_emitting_an_ordinary_letter_is_used_though_no_occurrence_was_gathered(self) -> None:
        record = FontRecord(1, "ABCDEF+Minion", frozenset({FIRST_PAGE_INDEX}), {"21": "T_h"},
                            ToUnicodeCMap.from_mappings({"21": "h"}), None)
        scan = FontScan(ScanInput(Path("book.pdf"), [record]), ScratchDirectory(self).resolver({}))
        self.assertEqual(["21"], [flagged.code for flagged in scan.used(Occurrences([]))])


class TestCodesEmittedAsCharacters(unittest.TestCase):
    def test_a_font_with_neither_table_nor_glyph_names_emits_each_code_as_its_character(self) -> None:
        record = FontRecord(1, "stmary10", frozenset(), {}, None, NO_TOUNICODE)
        self.assertEqual(["07"], record.codes_for("\x07"))

    def test_a_character_beyond_one_byte_names_no_code(self) -> None:
        record = FontRecord(1, "stmary10", frozenset(), {}, None, NO_TOUNICODE)
        self.assertEqual([], record.codes_for("≻"))

    def test_a_code_a_simple_fonts_table_omits_is_traced_to_the_character_it_emits(self) -> None:
        record = FontRecord(1, "stmary10", frozenset(), {}, ToUnicodeCMap.from_mappings({"4C": "⦇"}), None)
        self.assertEqual(["4F"], record.codes_for("O"))

    def test_a_code_the_table_maps_elsewhere_is_not_traced_as_emitted(self) -> None:
        record = FontRecord(1, "stmary10", frozenset(), {}, ToUnicodeCMap.from_mappings({"4F": "⅋"}), None)
        self.assertEqual([], record.codes_for("O"))

    def test_a_font_with_glyph_names_does_not_guess(self) -> None:
        record = FontRecord(1, "Any", frozenset(), {"07": "succ"}, None, NO_TOUNICODE)
        self.assertEqual([], record.codes_for("\x07"))


class TestTextLayerName(unittest.TestCase):
    def test_a_long_basefont_is_matched_as_mupdf_truncates_it(self) -> None:
        self.assertEqual(LONG_BASEFONT_AS_MUPDF_NAMES_IT,
                         symbol_record(1, face=FontFace(basefont=LONG_BASEFONT)).text_layer_name)

    def test_a_short_basefont_is_matched_by_its_family(self) -> None:
        self.assertEqual("Symbol", symbol_record(1).text_layer_name)

    def test_occurrences_under_the_truncated_name_belong_to_the_font(self) -> None:
        record = symbol_record(1, face=FontFace(basefont=LONG_BASEFONT))
        found = Occurrences([occurrence_in(LONG_BASEFONT_AS_MUPDF_NAMES_IT)]).of(record, SYMBOL_PRIVATE_USE_CHAR)
        self.assertEqual(1, len(found))

    def test_occurrences_under_another_font_do_not(self) -> None:
        found = Occurrences([occurrence_in("Times")]).of(symbol_record(1), SYMBOL_PRIVATE_USE_CHAR)
        self.assertEqual([], found)


class TestFontStatusRows(unittest.TestCase):
    def test_a_character_the_table_maps_needs_no_row(self) -> None:
        self.assertEqual([], FontStatusRows(symbol_record(1), [occurrence_in("Symbol")]).rows())

    def test_a_character_missing_from_the_table_is_reported_with_its_count(self) -> None:
        found = [occurrence_in("Symbol", "\uf024"), occurrence_in("Symbol", "\uf024")]
        rows = FontStatusRows(symbol_record(1), found).rows()
        self.assertEqual([(MISSING_FROM_TOUNICODE, "U+F024", 2)],
                         [(row["status"], row["unicode"], row["count"]) for row in rows])

    def test_a_character_a_simple_fonts_table_omits_is_traced_not_missing(self) -> None:
        table = ToUnicodeCMap.from_mappings({"4C": "⦇"})
        record = FontRecord(1, "stmary10", frozenset({FIRST_PAGE_INDEX}), {}, table, None)
        self.assertEqual([], FontStatusRows(record, [occurrence_in("stmary10", "O")]).rows())

    def test_a_font_without_a_table_is_reported_once(self) -> None:
        record = FontRecord(1, "ABCDEF+Symbol", frozenset({FIRST_PAGE_INDEX}), {}, None, NO_TOUNICODE)
        rows = FontStatusRows(record, [occurrence_in("Symbol"), occurrence_in("Symbol", "\uf024")]).rows()
        self.assertEqual([NO_TOUNICODE], [row["status"] for row in rows])

    def test_a_font_the_text_layer_never_uses_needs_no_row(self) -> None:
        record = FontRecord(1, "ABCDEF+Symbol", frozenset({FIRST_PAGE_INDEX}), {}, None, NO_TOUNICODE)
        self.assertEqual([], FontStatusRows(record, []).rows())


class TestCodeOfAnEmittedCharacter(unittest.TestCase):
    def _code(self, encoding: str | None, char: str) -> list[str]:
        return FontRecord(1, "ABCDEF+Palatino-Roman", frozenset({FIRST_PAGE_INDEX}), {}, None, NO_TOUNICODE,
                          None, encoding).codes_for(char)

    def test_a_winansi_font_takes_the_code_from_the_windows_code_page(self) -> None:
        self.assertEqual(["B4"], self._code(WIN_ANSI, "´"))

    def test_a_macroman_font_takes_the_code_from_the_mac_table(self) -> None:
        self.assertEqual(["AB"], self._code(MAC_ROMAN, "´"))

    def test_a_font_naming_no_encoding_takes_the_code_point(self) -> None:
        self.assertEqual(["B4"], self._code(None, "´"))

    def test_a_character_the_encoding_cannot_write_has_no_code(self) -> None:
        self.assertEqual([], self._code(MAC_ROMAN, "̄"))


if __name__ == "__main__":
    unittest.main()
