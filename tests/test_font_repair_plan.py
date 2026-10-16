from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _font_fixtures import (
    SYMBOL_CODE,
    SYMBOL_PRIVATE_USE_CHAR,
    FontFace,
    symbol_record,
)
from _clean.cmap import ZERO_WIDTH_SPACE
from _clean.fontrepair import RepairPlan
from _clean.fontscan import FlaggedCode
from _clean.glyphs import (
    METHOD_TABLE,
    Identity,
)
from _clean.lines import Glyph
from _font_repair_fixtures import (
    WIN_ANSI,
    MAC_ROMAN,
)

LIGATURE_CHAR = "ﬁ"
SYMBOL_INTO_LIGATURE = (
    "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
    "1 beginbfchar\n<0005> <FB01>\nendbfchar\n"
)
SUPERSCRIPT_TWO = "²"
SUPERSCRIPT_TWO_AT_B2 = (
    "1 begincodespacerange <00> <FF> endcodespacerange\n"
    "1 beginbfchar\n<B2> <00B2>\nendbfchar\n"
)
SUPERSCRIPT_TWO_AT_23 = (
    "1 begincodespacerange <00> <FF> endcodespacerange\n"
    "1 beginbfchar\n<23> <00B2>\nendbfchar\n"
)


class TestConfirmedCodes(unittest.TestCase):
    def test_a_code_whose_identity_is_its_own_character_is_neither_patched_nor_unresolved(self) -> None:
        identity = Identity(SYMBOL_PRIVATE_USE_CHAR, METHOD_TABLE)
        confirmed = FlaggedCode(symbol_record(1), SYMBOL_CODE, SYMBOL_PRIVATE_USE_CHAR, identity)
        self.assertTrue(RepairPlan([confirmed]).is_empty())

    def test_a_code_already_repaired_to_the_empty_identity_is_not_patched_again(self) -> None:
        repaired = FlaggedCode(symbol_record(1), SYMBOL_CODE, ZERO_WIDTH_SPACE, Identity("", METHOD_TABLE))
        self.assertTrue(RepairPlan([repaired]).is_empty())


class TestRepairRecords(unittest.TestCase):
    def test_identical_patches_from_two_font_objects_make_one_record(self) -> None:
        identity = Identity("∀", METHOD_TABLE)
        twins = [FlaggedCode(symbol_record(xref), SYMBOL_CODE, SYMBOL_PRIVATE_USE_CHAR, identity) for xref in (1, 2)]
        self.assertEqual(1, len(RepairPlan(twins).records()))


class TestOverridesReachEverySubsetOfTheFamily(unittest.TestCase):
    def test_a_subset_that_emits_the_flagged_character_takes_its_sibling_override(self) -> None:
        identity = Identity("∀", METHOD_TABLE)
        flagged_subset, sibling = (symbol_record(xref, face=FontFace(basefont=f"{prefix}+Symbol"))
                                   for xref, prefix in ((1, "ABCDEF"), (2, "GHIJKL")))
        plan = RepairPlan([FlaggedCode(flagged_subset, SYMBOL_CODE, SYMBOL_PRIVATE_USE_CHAR, identity)])
        self.assertEqual({SYMBOL_CODE: "∀"}, plan.overrides_for(sibling))

    def test_two_encodings_of_one_family_keep_their_overrides_apart(self) -> None:
        identity = Identity("́", METHOD_TABLE)
        records = [symbol_record(xref, face=FontFace(encoding=encoding)) for xref,
                   encoding in ((1, WIN_ANSI), (2, MAC_ROMAN))]
        plan = RepairPlan([FlaggedCode(record, code, SYMBOL_PRIVATE_USE_CHAR, identity)
                           for record, code in zip(records, ("B4", "AB"))])
        self.assertEqual([{"B4": "́"}, {"AB": "́"}], [plan.overrides_for(record) for record in records])

    def test_a_subset_whose_code_emits_another_character_keeps_its_own_mapping(self) -> None:
        ligature_subset = symbol_record(2, SYMBOL_INTO_LIGATURE, FontFace(basefont="GHIJKL+Symbol"))
        plan = RepairPlan([FlaggedCode(symbol_record(1), SYMBOL_CODE, SYMBOL_PRIVATE_USE_CHAR,
                                       Identity("1", METHOD_TABLE))])
        self.assertEqual({}, plan.overrides_for(ligature_subset))

    def test_subsets_that_share_a_code_for_different_glyphs_each_take_their_own_override(self) -> None:
        ligature_subset = symbol_record(2, SYMBOL_INTO_LIGATURE, FontFace(basefont="GHIJKL+Symbol"))
        digit_subset = symbol_record(1)
        plan = RepairPlan([FlaggedCode(digit_subset, SYMBOL_CODE, SYMBOL_PRIVATE_USE_CHAR, Identity("1", METHOD_TABLE)),
                           FlaggedCode(ligature_subset, SYMBOL_CODE, LIGATURE_CHAR, Identity("fi", METHOD_TABLE))])
        self.assertEqual([{SYMBOL_CODE: "1"}, {SYMBOL_CODE: "fi"}],
                         [plan.overrides_for(record) for record in (digit_subset, ligature_subset)])


class TestRetiredCharactersASiblingObjectStillEmits(unittest.TestCase):
    def setUp(self) -> None:
        self.patched = symbol_record(1, SUPERSCRIPT_TWO_AT_B2, FontFace(encoding=WIN_ANSI))
        self.sibling = symbol_record(2, SUPERSCRIPT_TWO_AT_23)
        self.plan = RepairPlan([FlaggedCode(self.patched, "B2", SUPERSCRIPT_TWO, Identity("2", METHOD_TABLE))])

    def test_a_character_no_other_object_emits_is_retired(self) -> None:
        self.assertEqual({Glyph("Symbol", SUPERSCRIPT_TWO)}, self.plan.retired_characters([self.patched]))

    def test_a_character_an_unpatched_object_of_the_same_name_emits_is_not_retired(self) -> None:
        self.assertEqual(set(), self.plan.retired_characters([self.patched, self.sibling]))


if __name__ == "__main__":
    unittest.main()
