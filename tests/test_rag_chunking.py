from __future__ import annotations

import re
import unittest

from _support import LiveTree

LiveTree.activate()

import rag
from _rag_chunks import BASENAME, NESTED, NOTE_META, ChunkingTestCase, tokens_in

WORK_LABEL = "Hegel and Miller, 1969, Wissenschaft der Logik"
HEADING_PATH = "Part Two > Chapter Nine > 9.2 Becoming"
SENTENCE = "Being and nothing pass over into becoming. "
LONG_PARAGRAPH = SENTENCE * 60
CHUNK_ID_RE = re.compile(r"^(?P<basename>.+)::(?P<digest>[0-9a-f]{16})$")


class TestEmbeddedTextStripsNotation(unittest.TestCase):
    def test_every_placeholder_is_stripped_before_embedding(self) -> None:
        text = "Rules ❲Γ ≻ Δ❳ hold.\n❲a/b❳\nAlways."
        self.assertEqual("Logic\nRules hold.\n \nAlways.", rag.embedded_text("Logic", text))

    def test_every_latex_span_is_stripped_before_embedding(self) -> None:
        text = "Rules $\\Gamma \\succ \\Delta$ hold.\n$$\\frac{a}{b}$$\nAlways."
        self.assertEqual("Logic\nRules hold.\n \nAlways.", rag.embedded_text("Logic", text))

    def test_prose_without_notation_embeds_unchanged(self) -> None:
        self.assertEqual("Being passes into nothing.", rag.embedded_text("", "Being passes into nothing."))


class TestHeadingPaths(ChunkingTestCase):
    def test_nested_headings_join_into_the_heading_path(self) -> None:
        self.assertEqual(["Part Two > Chapter Nine > 9.2 Becoming"], self.chunk(NESTED).heading_paths())

    def test_a_sibling_heading_replaces_the_previous_one_at_its_level(self) -> None:
        body = "# Part\n\n## One\n\nA.\n\n## Two\n\nB.\n"
        self.assertEqual(["Part > One", "Part > Two"], self.chunk(body).heading_paths())

    def test_a_higher_heading_closes_the_deeper_ones(self) -> None:
        body = "# Part\n\n## One\n\n### Deep\n\nA.\n\n# Next Part\n\nB.\n"
        self.assertEqual(["Part > One > Deep", "Next Part"], self.chunk(body).heading_paths())

    def test_text_before_any_heading_has_an_empty_path_and_the_work_label_as_its_context(self) -> None:
        [child] = self.chunk("Preamble.\n").children
        self.assertEqual(("", WORK_LABEL), (child.metadata["heading_path"], child.context))

    def test_the_embedded_text_is_the_context_a_newline_and_the_text(self) -> None:
        [child] = self.chunk(NESTED).children
        self.assertEqual(f"{WORK_LABEL}\n{HEADING_PATH}\nBeing passes into nothing.", child.embedded_text)

    def test_a_heading_with_no_text_yields_no_chunk(self) -> None:
        self.assertEqual(0, len(self.chunk("# Empty\n\n## Also empty\n").children))


class TestChunkContext(ChunkingTestCase):
    def _context(self, meta: dict) -> str:
        return self.chunk(NESTED, meta).child_containing("Being").context

    def test_the_context_is_the_work_label_then_the_heading_path(self) -> None:
        self.assertEqual(f"{WORK_LABEL}\n{HEADING_PATH}", self._context(NOTE_META))

    def test_the_work_label_takes_the_main_title_without_the_subtitle(self) -> None:
        meta = {**NOTE_META, "title": "Wissenschaft der Logik: Die Lehre vom Sein"}
        self.assertTrue(self._context(meta).startswith(f"{WORK_LABEL}\n"))

    def test_the_work_label_drops_a_dash_separated_subtitle_too(self) -> None:
        meta = {**NOTE_META, "title": "Wissenschaft der Logik — Die Lehre vom Sein"}
        self.assertTrue(self._context(meta).startswith(f"{WORK_LABEL}\n"))

    def test_a_missing_year_makes_the_basename_the_work_label(self) -> None:
        meta = {**NOTE_META, "year": None}
        self.assertEqual(f"{BASENAME}\n{HEADING_PATH}", self._context(meta))

    def test_a_missing_author_makes_the_basename_the_work_label(self) -> None:
        self.assertEqual(f"{BASENAME}\n{HEADING_PATH}", self._context({**NOTE_META, "author": []}))

    def test_the_context_stays_out_of_the_child_and_parent_text(self) -> None:
        chunks = self.chunk(NESTED)
        self.assertEqual(("Being passes into nothing.", "Being passes into nothing."),
                         (chunks.children[0].text, chunks.parents[0].text))

    def test_a_child_id_changes_with_the_work_label(self) -> None:
        before = self.chunk(NESTED).child_containing("Being").chunk_id
        after = self.chunk(NESTED, {**NOTE_META, "year": 1812}).child_containing("Being").chunk_id
        self.assertNotEqual(before, after)


class TestTimeMarkers(ChunkingTestCase):
    TALK = ("## Talk\n\n%% 00:00:05 %%\n**Pippin:** Logic is metaphysics.\n\n"
            "%% 00:12:40 %%\n**Pippin:** Being is thought.\n")

    def test_a_chunk_carries_the_times_of_its_first_and_last_marker(self) -> None:
        [parent] = self.chunk(self.TALK).parents
        self.assertEqual(("00:00:05", "00:12:40"), (parent.metadata["time_first"], parent.metadata["time_last"]))

    def test_a_timed_chunk_carries_no_folio_and_no_file_page(self) -> None:
        [parent] = self.chunk(self.TALK).parents
        self.assertEqual((None, None), (parent.metadata["folio_first"], parent.metadata["file_page_first"]))

    def test_a_paged_chunk_carries_no_time(self) -> None:
        [parent] = self.chunk("# One\n\n%% p. 3 (file p. 5) %%\nText.\n").parents
        self.assertEqual((None, "3"), (parent.metadata["time_first"], parent.metadata["folio_first"]))


class TestSizeLimits(ChunkingTestCase):
    PARAGRAPHS = [f"Paragraph {number}. " + SENTENCE * 12 for number in range(30)]

    def test_a_section_under_the_limit_is_one_parent(self) -> None:
        self.assertEqual(1, len(self.chunk("# One\n\n" + "\n\n".join(self.PARAGRAPHS[:5])).parents))

    def test_an_oversized_section_splits_into_parents_within_the_limit(self) -> None:
        chunks = self.chunk("# One\n\n" + "\n\n".join(self.PARAGRAPHS))
        self.assertGreater(len(chunks.parents), 1)
        for parent in chunks.parents:
            self.assertLessEqual(tokens_in(parent.text), rag.MAX_PARENT_TOKENS)

    def test_parents_split_only_at_paragraph_boundaries(self) -> None:
        whole = {paragraph.strip() for paragraph in self.PARAGRAPHS}
        for parent in self.chunk("# One\n\n" + "\n\n".join(self.PARAGRAPHS)).parents:
            self.assertTrue(set(parent.text.split("\n\n")) <= whole)

    def test_children_stay_within_the_child_limit(self) -> None:
        for text in self.chunk("# One\n\n" + LONG_PARAGRAPH).child_texts():
            self.assertLessEqual(tokens_in(text), rag.MAX_CHILD_TOKENS)

    def test_an_oversized_paragraph_splits_its_children_at_sentence_boundaries(self) -> None:
        texts = self.chunk("# One\n\n" + LONG_PARAGRAPH).child_texts()
        self.assertGreater(len(texts), 1)
        self.assertTrue(all(text.endswith("becoming.") for text in texts))

    def test_every_child_names_a_parent_that_exists(self) -> None:
        chunks = self.chunk("# One\n\n" + "\n\n".join(self.PARAGRAPHS))
        parent_ids = {parent.parent_id for parent in chunks.parents}
        self.assertTrue({child.parent_id for child in chunks.children} <= parent_ids)


class TestChunkIds(ChunkingTestCase):
    STABLE = "# One\n\nStable paragraph.\n\n# Two\n\n{other}\n"

    def _id_of(self, body: str, fragment: str) -> str:
        return self.chunk(body).child_containing(fragment).chunk_id

    def test_a_chunk_id_joins_the_basename_and_sixteen_hex_digits(self) -> None:
        match = CHUNK_ID_RE.match(self._id_of(NESTED, "Being"))
        self.assertEqual(BASENAME, match.group("basename"))

    def test_a_child_id_is_unchanged_when_an_unrelated_paragraph_changes(self) -> None:
        before = self._id_of(self.STABLE.format(other="Old text."), "Stable")
        after = self._id_of(self.STABLE.format(other="New text entirely."), "Stable")
        self.assertEqual(before, after)

    def test_a_child_id_changes_with_its_heading_path(self) -> None:
        self.assertNotEqual(self._id_of("# One\n\nSame.\n", "Same"), self._id_of("# Two\n\nSame.\n", "Same"))

    def test_a_parent_id_is_unchanged_when_another_section_changes(self) -> None:
        before = self.chunk(self.STABLE.format(other="Old.")).parent_containing("Stable").parent_id
        after = self.chunk(self.STABLE.format(other="New.")).parent_containing("Stable").parent_id
        self.assertEqual(before, after)


class TestChunkMetadata(ChunkingTestCase):
    def _metadata(self, meta: dict | None = None) -> dict:
        return self.chunk(NESTED, meta).child_containing("Being").metadata

    def test_authors_are_joined_into_a_string(self) -> None:
        self.assertEqual("Hegel, Miller", self._metadata()["author"])

    def test_fields_are_joined_into_a_string(self) -> None:
        self.assertEqual("[[Being]], [[Logic]]", self._metadata()["field"])

    def test_year_title_citekey_and_basename_are_recorded(self) -> None:
        metadata = self._metadata()
        self.assertEqual(("1969", "Wissenschaft der Logik", "hegel1812", BASENAME),
                         (metadata["year"], metadata["title"], metadata["citekey"], metadata["basename"]))

    def test_a_string_author_is_kept_whole(self) -> None:
        self.assertEqual("Kant", self._metadata({**NOTE_META, "author": "Kant"})["author"])

    def test_absent_metadata_becomes_empty_strings(self) -> None:
        metadata = self._metadata({})
        self.assertEqual({""}, {metadata[key] for key in ("title", "author", "year", "citekey", "field")})

    def test_a_null_year_becomes_an_empty_string(self) -> None:
        self.assertEqual("", self._metadata({**NOTE_META, "year": None})["year"])

    def test_a_parents_metadata_names_itself_as_parent(self) -> None:
        [parent] = self.chunk(NESTED).parents
        self.assertEqual(parent.parent_id, parent.metadata["parent_id"])


if __name__ == "__main__":
    unittest.main()
