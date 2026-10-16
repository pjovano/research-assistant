from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _vaults import TempVault

REFERENCE_DIRS = ("LIBRARY_DIR", "CORPUS_DIR")
LINK_LINE = "[x.pdf](zotero://open-pdf/x)"
PDF_BYTES = b"%PDF-1.7"


class VaultTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*REFERENCE_DIRS).activate()
        self.addCleanup(self.vault.discard)

    def write_note(self, basename: str, frontmatter: str, body: str = LINK_LINE) -> None:
        (self.vault.corpus / f"{basename}.md").write_text(f"---\n{frontmatter}---\n\n{body}\n", encoding="utf-8")

    def note_text(self, basename: str) -> str:
        return (self.vault.corpus / f"{basename}.md").read_text(encoding="utf-8")

    def write_pdf(self, basename: str) -> None:
        (self.vault.library / f"{basename}.pdf").write_bytes(PDF_BYTES)
