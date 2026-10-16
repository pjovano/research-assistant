from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from _support import LiveTree

LiveTree.activate()

import verify
from _vaults import TempVault, TextPdf

BASENAME = "Hegel - 1969 - Wissenschaft der Logik"
QUOTE_ON_EVERY_PAGE = "of the work, with words enough to measure"
VERIFIED_EXIT_CODE = 0


class ExitCodeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("CORPUS_DIR", "LIBRARY_DIR").activate()
        self.addCleanup(self.vault.discard)
        TextPdf(self.vault.library / f"{BASENAME}.pdf").write()

    def status_of(self, *arguments: str) -> int:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return verify.VerifyCli().run(list(arguments))


class TestEveryOutcomeHasItsOwnExitCode(unittest.TestCase):
    def test_the_five_outcomes_exit_with_five_codes(self) -> None:
        codes = {VERIFIED_EXIT_CODE, verify.NOT_VERIFIED_EXIT_CODE, verify.USAGE_EXIT_CODE,
                 verify.POOR_TEXT_LAYER_EXIT_CODE, verify.FAILURE_EXIT_CODE}
        self.assertEqual(5, len(codes))


class TestAFailureIsNotReportedAsANotVerifiedQuotation(ExitCodeTestCase):
    def test_a_missing_pdf_exits_with_the_failure_code(self) -> None:
        self.assertEqual(verify.FAILURE_EXIT_CODE, self.status_of("verify", "nope.pdf", "x"))

    def test_an_ambiguous_quotation_exits_with_the_not_verified_code(self) -> None:
        self.assertEqual(verify.NOT_VERIFIED_EXIT_CODE, self.status_of("verify", BASENAME, QUOTE_ON_EVERY_PAGE))


class TestAPoorTextLayerIsNotReportedAsAUsageError(ExitCodeTestCase):
    def test_a_poor_text_layer_exits_with_its_own_code(self) -> None:
        self.assertEqual(verify.POOR_TEXT_LAYER_EXIT_CODE, self.status_of("quality", BASENAME))

    def test_no_arguments_exit_with_the_usage_code(self) -> None:
        self.assertEqual(verify.USAGE_EXIT_CODE, self.status_of())

    def test_an_unknown_command_exits_with_the_usage_code(self) -> None:
        with self.assertRaises(SystemExit) as exit_status:
            self.status_of("nonsense")
        self.assertEqual(verify.USAGE_EXIT_CODE, exit_status.exception.code)


if __name__ == "__main__":
    unittest.main()
