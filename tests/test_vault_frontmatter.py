from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import vault
from _vault.frontmatter import StoredNote

CARRIAGE_RETURN = b"\r"
CRLF_BODY = "line one\r\nline two\r\n"
LF_BODY = "line one\nline two\n"

SAMPLE_META = {
    "title": "Wissenschaft der Logik",
    "author": ["Hegel"],
    "year": 1969,
    "orig_year": 1812,
    "source_role": "primary",
    "field": ["[[Being]]", "[[Logic]]"],
    "aliases": ["Science of Logic"],
}
SAMPLE_BODY = "## Argument\n\nThe doctrine of being.\n"


class FrontmatterFile:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "note.md"

    @property
    def path(self) -> Path:
        return self._path

    def write(self, meta: dict, body: str) -> None:
        vault.write_frontmatter(self._path, meta, body)

    def read(self) -> tuple[dict, str]:
        return vault.read_frontmatter(self._path)

    def raw_bytes(self) -> bytes:
        return self._path.read_bytes()


class FrontmatterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.note = FrontmatterFile(Path(self._tmp.name))
        self.addCleanup(self._tmp.cleanup)


class TestFrontmatterRoundTrip(FrontmatterTestCase):
    def test_metadata_survives_a_write_then_read(self) -> None:
        self.note.write(SAMPLE_META, SAMPLE_BODY)
        meta, _ = self.note.read()
        self.assertEqual(SAMPLE_META, meta)

    def test_body_survives_a_write_then_read(self) -> None:
        self.note.write(SAMPLE_META, SAMPLE_BODY)
        _, body = self.note.read()
        self.assertEqual(SAMPLE_BODY.strip(), body.strip())

    def test_unicode_is_not_escaped(self) -> None:
        self.note.write({"title": "Cantù, Poincaré"}, "body")
        self.assertIn("Cantù, Poincaré".encode("utf-8"), self.note.raw_bytes())


class TestFrontmatterLineEndings(FrontmatterTestCase):
    def test_written_note_contains_no_carriage_returns(self) -> None:
        self.note.write(SAMPLE_META, SAMPLE_BODY)
        self.assertNotIn(CARRIAGE_RETURN, self.note.raw_bytes())

    def test_platform_newline_translation_is_suppressed(self) -> None:
        self.note.write(SAMPLE_META, LF_BODY)
        self.assertNotIn(CARRIAGE_RETURN, self.note.raw_bytes())

    def test_crlf_already_in_the_body_is_normalized(self) -> None:
        self.note.write(SAMPLE_META, CRLF_BODY)
        self.assertNotIn(CARRIAGE_RETURN, self.note.raw_bytes())

    def test_normalizing_crlf_keeps_the_line_break(self) -> None:
        self.note.write(SAMPLE_META, CRLF_BODY)
        self.assertIn(b"line one\nline two", self.note.raw_bytes())


class TestFrontmatterAbsent(FrontmatterTestCase):
    def test_a_note_without_frontmatter_reads_as_empty_metadata(self) -> None:
        self.note.path.write_text("no frontmatter here\n", encoding="utf-8", newline="\n")
        meta, body = self.note.read()
        self.assertEqual(({}, "no frontmatter here\n"), (meta, body))


class TestByteOrderMarkedNote(FrontmatterTestCase):
    MARKED = "\ufeff---\ntitle: Marked\n---\n\nbody\n"

    def setUp(self) -> None:
        super().setUp()
        self.note.path.write_text(self.MARKED, encoding="utf-8", newline="\n")

    def test_the_whole_read_finds_the_frontmatter_behind_the_mark(self) -> None:
        self.assertEqual(({"title": "Marked"}, "\nbody\n"), self.note.read())

    def test_the_header_read_finds_the_frontmatter_behind_the_mark(self) -> None:
        self.assertEqual({"title": "Marked"}, vault.read_frontmatter_only(self.note.path))

    def test_the_split_keeps_the_block_and_drops_the_mark(self) -> None:
        self.assertEqual(("---\ntitle: Marked\n---\n", "\nbody\n"), vault.split_note(self.MARKED))


class TestStoredNote(FrontmatterTestCase):
    UNPARSEABLE_BODY = "\n---\n: [unbalanced\n"

    def setUp(self) -> None:
        super().setUp()
        self.stored = StoredNote(self.note.path)
        self.stored.write(SAMPLE_META, self.UNPARSEABLE_BODY)

    def test_the_class_writes_what_the_frozen_reader_reads(self) -> None:
        self.assertEqual(SAMPLE_META, vault.read_frontmatter(self.note.path)[0])

    def test_the_header_read_stops_at_the_closing_fence(self) -> None:
        self.assertEqual(SAMPLE_META, self.stored.frontmatter())

    def test_the_header_read_is_the_frozen_header_reader(self) -> None:
        self.assertEqual(self.stored.frontmatter(), vault.read_frontmatter_only(self.note.path))


class TestParseNote(unittest.TestCase):
    CRLF_NOTE = "\ufeff---\r\ntitle: Windows\r\n---\r\n\r\nline one\r\nline two\r\n"

    def test_a_carriage_return_note_is_parsed_behind_its_mark(self) -> None:
        self.assertEqual(({"title": "Windows"}, "\nline one\nline two\n"), vault.parse_note(self.CRLF_NOTE))

    def test_a_text_without_frontmatter_is_all_body_with_line_feeds(self) -> None:
        self.assertEqual(({}, "just body\n"), vault.parse_note("just body\r\n"))

    def test_the_file_reader_parses_the_same_way(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.md"
            path.write_bytes(self.CRLF_NOTE.encode("utf-8"))
            self.assertEqual(vault.parse_note(self.CRLF_NOTE), vault.read_frontmatter(path))


class TestNoteParts(unittest.TestCase):
    RAW = "---\n# kept comment\nparent: \"[[X]]\"\n---\n\nbody\n"

    def test_the_frontmatter_block_is_returned_verbatim(self) -> None:
        block, _ = vault.split_note(self.RAW)
        self.assertEqual("---\n# kept comment\nparent: \"[[X]]\"\n---\n", block)

    def test_a_note_without_frontmatter_has_an_empty_block(self) -> None:
        self.assertEqual(("", "just body\n"), vault.split_note("just body\n"))

    def test_join_reassembles_the_note_with_one_blank_line(self) -> None:
        block, body = vault.split_note(self.RAW)
        self.assertEqual(self.RAW, vault.join_note(block, body))


class TestPdfLinkUpsert(unittest.TestCase):
    LINK = "zotero://open-pdf/library/items/ABCD1234"

    def test_link_is_placed_at_the_top(self) -> None:
        result = vault.upsert_pdf_link("body text", "Kripke - 1980 - Naming", self.LINK)
        self.assertTrue(result.startswith(f"[Kripke - 1980 - Naming.pdf]({self.LINK})"))

    def test_an_existing_link_is_replaced_not_duplicated(self) -> None:
        once = vault.upsert_pdf_link("body text", "Basename", self.LINK)
        twice = vault.upsert_pdf_link(once, "Basename", self.LINK)
        self.assertEqual(once, twice)

    def test_passing_no_link_strips_a_stale_one(self) -> None:
        linked = vault.upsert_pdf_link("body text", "Basename", self.LINK)
        self.assertEqual("body text", vault.upsert_pdf_link(linked, "Basename", None))


if __name__ == "__main__":
    unittest.main()


class TestASequenceWrittenWithoutIndentation(unittest.TestCase):
    BLOCK = "---\ntitle: T\nfield:\n- '[[Logic]]'\n- '[[Being]]'\nyear: 1969\n---\n"

    def test_replacing_the_sequence_in_place_drops_every_unindented_item(self) -> None:
        from _vault.frontmatter import FrontmatterFields
        block = FrontmatterFields().replaced_in_place(self.BLOCK, {"field": ['"[[Dialectic]]"']})
        self.assertEqual("---\ntitle: T\nfield:\n  - \"[[Dialectic]]\"\nyear: 1969\n---\n", block)

    def test_upserting_over_the_sequence_drops_every_unindented_item(self) -> None:
        from _vault.frontmatter import FrontmatterFields
        block = FrontmatterFields().upserted(self.BLOCK, {"field": ['"[[Dialectic]]"']})
        self.assertNotIn("Logic", block)
        self.assertIn("year: 1969", block)
