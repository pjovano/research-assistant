from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import pagetext
import vault

from _vaults import TempVault, TextPdf

WORK = "Roe - 2021 - A Rendered Work"


class TestRenderDirectory(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = self.vault.library / f"{WORK}.pdf"
        TextPdf(self.pdf).write()

    def test_a_render_lands_in_the_scratch_directory_in_force_when_it_is_rendered(self) -> None:
        [render] = pagetext.render_pages(self.pdf, [1])
        self.assertEqual(vault.SCRATCH_DIR / WORK / "page-0001.png", render)


if __name__ == "__main__":
    unittest.main()
