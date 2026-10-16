from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _annotate.cli import ReferenceLookup
from _vaults import TextPdf


class TestAReferenceNamesAnEditionOrAnAkademieVolume(unittest.TestCase):
    def setUp(self) -> None:
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.lookup = ReferenceLookup(TextPdf(Path(directory) / "work.pdf", pages=1).write())

    def test_a_reference_in_either_edition_is_looked_up(self) -> None:
        for reference in ("A137", "b176", " B12 "):
            with self.subTest(reference=reference):
                self.assertIsInstance(self.lookup.rendered(reference), str)

    def test_a_reference_under_any_siglum_is_looked_up(self) -> None:
        for reference in ("C12", "GA 41"):
            with self.subTest(reference=reference):
                self.assertIsInstance(self.lookup.rendered(reference), str)

    def test_a_reference_naming_no_siglum_is_refused(self) -> None:
        for reference in ("A", "Ax1", "", "137"):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                self.lookup.rendered(reference)


if __name__ == "__main__":
    unittest.main()
