from __future__ import annotations

import unittest
from dataclasses import dataclass

from _correction_fixtures import BODY, OUTLINE_TITLES, FakeLayer

from _extract.correctionanchors import CorrectionContext
from _extract.correctionops import NO_EFFECT, Effect
from _extract.correctionrun import (
    APPLIED,
    REFUSED,
    Correction,
    CorrectionPass,
    MalformedCorrections,
    parsed_corrections,
)
from _extract.correctiontext import TrialText

FAMILY = {"family": "paragraphs", "defect_class": "a property of the page"}


@dataclass(frozen=True)
class RespellingOperation:
    def apply(self, text: TrialText, _context: CorrectionContext) -> Effect:
        text.units[1] = text.units[1].with_text(text.units[1].text.replace("Introduction", "Introductian"))
        return NO_EFFECT


class TestLetterBalance(unittest.TestCase):
    def _run(self, operation: object):
        text = TrialText.parsed(BODY)
        context = CorrectionContext(TrialText.parsed(BODY), OUTLINE_TITLES, FakeLayer())
        return text, CorrectionPass(context).run(text, [Correction({"op": "respell", "page": 1}, operation)])

    def test_a_correction_changing_a_letter_is_refused(self) -> None:
        _text, result = self._run(RespellingOperation())
        self.assertEqual(REFUSED, result.outcomes[0]["outcome"])

    def test_a_refused_correction_leaves_the_body_as_it_was(self) -> None:
        text, _result = self._run(RespellingOperation())
        self.assertEqual(BODY, text.rendered())

    def test_only_the_applied_corrections_are_kept_for_the_record(self) -> None:
        text = TrialText.parsed(BODY)
        context = CorrectionContext(TrialText.parsed(BODY), OUTLINE_TITLES, FakeLayer())
        split = {**FAMILY, "op": "split", "page": 1, "anchor": "The second claim follows in the same paragraph"}
        result = CorrectionPass(context).run(text, parsed_corrections([split, split]))
        self.assertEqual(([split], 1), (result.applied, result.counts()[APPLIED]))


class TestMalformedCorrections(unittest.TestCase):
    def test_a_file_holding_no_list_is_refused(self) -> None:
        with self.assertRaises(MalformedCorrections):
            parsed_corrections({"op": "split"})

    def test_an_unknown_op_is_refused(self) -> None:
        with self.assertRaises(MalformedCorrections):
            parsed_corrections([{**FAMILY, "op": "rewrite", "page": 1}])

    def test_a_correction_without_its_defect_family_is_refused(self) -> None:
        with self.assertRaises(MalformedCorrections):
            parsed_corrections([{"op": "split", "page": 1, "anchor": "x", "defect_class": "y"}])

    def test_a_heading_without_a_level_is_refused(self) -> None:
        with self.assertRaises(MalformedCorrections):
            parsed_corrections([{**FAMILY, "op": "role", "page": 1, "anchor": "x", "to": "heading"}])

    def test_restored_lines_must_name_a_first_and_a_last(self) -> None:
        with self.assertRaises(MalformedCorrections):
            parsed_corrections([{**FAMILY, "op": "restore", "page": 1, "lines": [4]}])


if __name__ == "__main__":
    unittest.main()
