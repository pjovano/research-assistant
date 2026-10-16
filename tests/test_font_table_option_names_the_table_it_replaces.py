from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from _clean.cli import Cli


class TestTheTableOptionsHelp(unittest.TestCase):
    def setUp(self) -> None:
        printed = io.StringIO()
        with mock.patch("sys.argv", ["clean.py", "fonts", "--help"]), contextlib.redirect_stdout(printed), \
                self.assertRaises(SystemExit):
            Cli().run()
        self.help = " ".join(printed.getvalue().split())

    def test_it_names_the_identity_table_in_the_library(self) -> None:
        self.assertIn("library/glyph-identities.json", self.help)

    def test_it_names_no_reference_file(self) -> None:
        self.assertNotIn("reference file", self.help)


if __name__ == "__main__":
    unittest.main()
