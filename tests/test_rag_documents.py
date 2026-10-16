from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import rag
import vault
from _rag_chunks import BASENAME, LINK_LINE, NOTE_META
from _rag_fakes import temp_directory
from _vaults import TempVault

TALK = "Pippin - 2019 - Hegel on Logic as Metaphysics"
RECORDING_LINE = "[Recording](https://www.youtube.com/watch?v=abc123)"

BIBLIOGRAPHY = ("# Chapter\n\nArgument.\n\n## Bibliography\n\nKant, I. Critique.\n\n### Primary sources\n\n"
                "Hegel, G. Logic.\n\n## Index\n\nBeing, 12.\n")
FOOTNOTED = "# Chapter\n\nArgument.[^1]\n\n## References\n\nKant, I. Critique.\n\n[^1]: A note on Kant.\n"


class TestIndexableDocuments(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = temp_directory(self)

    def loaded(self, body: str) -> rag.IndexedDocument:
        path = self.directory / f"{BASENAME}.md"
        vault.write_frontmatter(path, NOTE_META, f"{LINK_LINE}\n\n{body}")
        return rag.IndexableDocuments().loaded(path)

    def test_the_pdf_link_line_is_stripped_from_the_body(self) -> None:
        self.assertNotIn("zotero://", self.loaded("# One\n\nText.\n").body)

    def test_a_recording_link_line_is_stripped_from_a_transcript_body(self) -> None:
        path = self.directory / f"{TALK}.md"
        vault.write_frontmatter(path, {"title": "Hegel on Logic"}, f"{RECORDING_LINE}\n\n## Talk\n\nSpoken.\n")
        self.assertEqual("## Talk\n\nSpoken.\n", rag.IndexableDocuments().loaded(path).body)

    def test_the_frontmatter_becomes_the_metadata_and_the_key_is_the_basename(self) -> None:
        document = self.loaded("# One\n\nText.\n")
        self.assertEqual(("Wissenschaft der Logik", BASENAME), (document.meta["title"], document.key))

    def test_the_bibliography_section_and_its_subsections_are_excluded(self) -> None:
        body = self.loaded(BIBLIOGRAPHY).body
        self.assertNotIn("Kant, I.", body)
        self.assertNotIn("Hegel, G.", body)

    def test_the_section_after_the_bibliography_survives(self) -> None:
        self.assertIn("Being, 12.", self.loaded(BIBLIOGRAPHY).body)

    def test_the_bibliography_ends_where_the_footnote_definitions_begin(self) -> None:
        body = self.loaded(FOOTNOTED).body
        self.assertNotIn("Kant, I.", body)
        self.assertIn("[^1]: A note on Kant.", body)

    def test_a_heading_carrying_an_inline_page_marker_still_ends_the_bibliography(self) -> None:
        body = "## Bibliography\n\nKant, I. Critique.\n\n## Index %% p. 500 (file p. 520) %%\n\nBeing, 12.\n"
        self.assertIn("Being, 12.", self.loaded(body).body)

    def test_the_bibliography_heading_matches_case_insensitively_in_any_named_language(self) -> None:
        for heading in ("REFERENCES", "Literaturverzeichnis", "Works Cited"):
            with self.subTest(heading=heading):
                self.assertNotIn("Kant, I.", self.loaded(f"# A\n\nText.\n\n## {heading}\n\nKant, I.\n").body)

    def test_a_carriage_return_file_yields_its_frontmatter_and_a_line_feed_body(self) -> None:
        path = self.directory / f"{BASENAME}.md"
        path.write_bytes(b"---\r\ntitle: Windows\r\n---\r\n\r\n# One\r\n\r\nText.\r\n")
        document = rag.IndexableDocuments().loaded(path)
        self.assertEqual(("Windows", "# One\n\nText.\n"), (document.meta["title"], document.body.lstrip()))

    def test_the_content_hash_follows_the_file(self) -> None:
        before = self.loaded("# One\n\nText.\n").content_hash
        self.assertNotEqual(before, self.loaded("# One\n\nOther.\n").content_hash)


if __name__ == "__main__":
    unittest.main()



class TestIndexablePaths(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("CORPUS_DIR", "TRANSCRIPTS_DIR").activate()
        self.addCleanup(self.vault.discard)

    def test_the_transcripts_are_indexed_after_the_corpus_files(self) -> None:
        vault.write_frontmatter(vault.CORPUS_DIR / f"{BASENAME}.md", NOTE_META, "Text.")
        vault.write_frontmatter(vault.TRANSCRIPTS_DIR / f"{TALK}.md", {"title": "Talk"}, "Spoken.")
        names = [vault.basename_of(path) for path in rag.IndexableDocuments().paths()]
        self.assertEqual([BASENAME, TALK], names)

    def test_both_directories_are_watched_for_staleness(self) -> None:
        self.assertEqual((vault.CORPUS_DIR, vault.TRANSCRIPTS_DIR), rag.IndexableDocuments().directories)
