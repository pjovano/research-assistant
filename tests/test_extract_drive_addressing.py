from __future__ import annotations

import contextlib
import io
import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.cli import CommandLine

BASENAME = "Author - 2000 - Work"


def parsed_work(*argv: str) -> int | str:
    return CommandLine().parser().parse_args(list(argv)).index


class TestDriveStepAddressing(unittest.TestCase):
    def test_a_number_names_a_listed_work_by_its_key(self) -> None:
        self.assertEqual(3, parsed_work("drive-prep", "3"))

    def test_a_basename_names_the_work_itself(self) -> None:
        self.assertEqual(BASENAME, parsed_work("drive-trial", BASENAME))

    def test_key_zero_is_refused(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parsed_work("drive-retrial", "0")


if __name__ == "__main__":
    unittest.main()
