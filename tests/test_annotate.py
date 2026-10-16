from __future__ import annotations

import contextlib
import io
import unittest

from _support import LiveTree

LiveTree.activate()

import annotate
from _vaults import TempVault, TextPdf


class TestMarkerNumber(unittest.TestCase):
    def test_plain_digits_parse(self) -> None:
        self.assertEqual(137, annotate.MarkerNumber.parsed("137"))

    def test_an_ocr_capital_o_is_read_as_zero(self) -> None:
        self.assertEqual(680, annotate.MarkerNumber.parsed("68O"))

    def test_an_ocr_lowercase_o_is_read_as_zero(self) -> None:
        self.assertEqual(200, annotate.MarkerNumber.parsed("2o0"))


class TestEditionMarker(unittest.TestCase):
    def test_an_ab_marker_renders_without_a_colon(self) -> None:
        self.assertEqual("A137", annotate.EditionMarker(1, 0, "A", 137, "single").label)

    def test_an_akademie_marker_renders_with_a_colon(self) -> None:
        self.assertEqual("4:260", annotate.EditionMarker(1, 0, "Ak4", 260, "akademie").label)


class TestMarkerGrammar(unittest.TestCase):
    def setUp(self) -> None:
        self.grammar = annotate.MarkerGrammar()

    def test_a_tight_single_marker_is_found(self) -> None:
        self.assertEqual([("A", 97, 0, "single")], self.grammar.scan("[A97]"))

    def test_a_spaced_single_marker_is_found(self) -> None:
        self.assertEqual([("B", 53, 0, "single")], self.grammar.scan("[B 53]"))

    def test_a_combined_marker_yields_both_editions(self) -> None:
        found = self.grammar.scan("[A 719/B 747]")
        self.assertEqual([("A", 719, 0, "combined"), ("B", 747, 0, "combined")], found)

    def test_a_reversed_combined_marker_yields_both_editions(self) -> None:
        found = self.grammar.scan("[B171/A132]")
        self.assertEqual([("B", 171, 0, "combined"), ("A", 132, 0, "combined")], found)

    def test_an_ocr_damaged_marker_is_still_read(self) -> None:
        found = self.grammar.scan("[A652/B68O]")
        self.assertEqual([("A", 652, 0, "combined"), ("B", 680, 0, "combined")], found)

    def test_prose_without_markers_yields_nothing(self) -> None:
        self.assertEqual([], self.grammar.scan("a sentence with [brackets] but no marker"))

    def test_an_akademie_marker_is_found(self) -> None:
        self.assertEqual([("Ak4", 255, 0, "akademie")], self.grammar.scan("[4:255]"))


class TestMarkerTail(unittest.TestCase):
    def test_a_glued_marker_is_stripped_from_a_word(self) -> None:
        self.assertEqual("composed.", annotate.MarkerTail.stripped("composed.[A"))

    def test_a_word_without_a_marker_is_left_alone(self) -> None:
        self.assertEqual("composed.", annotate.MarkerTail.stripped("composed."))

    def test_a_leading_bracket_word_is_not_stripped_to_nothing(self) -> None:
        self.assertEqual("[A137]", annotate.MarkerTail.stripped("[A137]"))

    def test_a_closing_fragment_is_pure_debris(self) -> None:
        self.assertTrue(annotate.MarkerTail.is_pure_debris("747]"))

    def test_a_middle_fragment_is_pure_debris(self) -> None:
        self.assertTrue(annotate.MarkerTail.is_pure_debris("719/B"))

    def test_an_ocr_damaged_middle_fragment_is_debris(self) -> None:
        self.assertTrue(annotate.MarkerTail.is_pure_debris("7I9/B"))

    def test_a_word_carrying_real_text_is_not_pure_debris(self) -> None:
        self.assertFalse(annotate.MarkerTail.is_pure_debris("composed.[A"))

    def test_a_word_carrying_real_text_is_still_debris(self) -> None:
        self.assertTrue(annotate.MarkerTail.is_debris("composed.[A"))

    def test_ordinary_prose_is_not_debris(self) -> None:
        self.assertFalse(annotate.MarkerTail.is_debris("composed."))


class TestNoteLedger(unittest.TestCase):
    def setUp(self) -> None:
        self.note = annotate.Note("Carson - 1997 - Kant on Intuition in Geometry", "a gloss")

    def test_an_empty_ledger_renders_a_single_note(self) -> None:
        self.assertEqual(self.note.rendered, annotate.NoteLedger("").appended(self.note))

    def test_a_note_without_a_link_renders_bare(self) -> None:
        self.assertEqual("just a body", annotate.Note("", "just a body").rendered)

    def test_a_second_commentator_is_appended_as_a_new_entry(self) -> None:
        ledger = annotate.NoteLedger("[[Friedman - 1992 - Kant and the Exact Sciences]] — other")
        self.assertEqual(2, len(ledger.appended(self.note).split("\n\n")))

    def test_the_same_commentator_is_not_appended_twice(self) -> None:
        ledger = annotate.NoteLedger(self.note.rendered)
        self.assertEqual(self.note.rendered, ledger.appended(self.note))

    def test_a_note_without_a_link_is_not_appended_twice(self) -> None:
        plain = annotate.Note("", "just a body")
        ledger = annotate.NoteLedger(plain.rendered)
        self.assertEqual(plain.rendered, ledger.appended(plain))

    def test_existing_entries_survive_a_round_trip(self) -> None:
        ledger = annotate.NoteLedger("one\n\ntwo")
        self.assertEqual(["one", "two"], ledger.entries)


class TestTag(unittest.TestCase):
    SUBTOPIC = "Kant's philosophy of mathematics"

    def test_a_phrase_becomes_a_slug(self) -> None:
        self.assertEqual("kant-s-philosophy-of-mathematics", annotate.Tag(self.SUBTOPIC).slug)

    def test_an_empty_tag_has_no_token(self) -> None:
        self.assertEqual("", annotate.Tag("").token)

    def test_an_empty_tag_reports_itself_empty(self) -> None:
        self.assertTrue(annotate.Tag("   ").is_empty)

    def test_matching_ignores_case_and_punctuation(self) -> None:
        self.assertTrue(annotate.Tag(self.SUBTOPIC).matches("KANT'S PHILOSOPHY OF MATHEMATICS"))

    def test_matching_accepts_the_slug_form(self) -> None:
        self.assertTrue(annotate.Tag(self.SUBTOPIC).matches("kant-s-philosophy-of-mathematics"))

    def test_different_subtopics_do_not_match(self) -> None:
        self.assertFalse(annotate.Tag(self.SUBTOPIC).matches("Kant on causality"))

    def test_a_tag_renders_as_a_wikilink_token(self) -> None:
        self.assertEqual("#[[Kant's philosophy of mathematics]]",
                         annotate.Tag(self.SUBTOPIC).token)

    def test_a_tagged_note_carries_the_token_on_its_own_line(self) -> None:
        note = annotate.Note("A - 1 - B", "gloss", annotate.Tag(self.SUBTOPIC))
        self.assertEqual(["[[A - 1 - B]] — gloss", "#[[Kant's philosophy of mathematics]]"],
                         note.rendered.splitlines())

    def test_an_untagged_note_has_no_tag_line(self) -> None:
        self.assertEqual("[[A - 1 - B]] — gloss", annotate.Note("A - 1 - B", "gloss").rendered)

    def test_a_tag_line_does_not_split_a_merged_note_into_extra_entries(self) -> None:
        first = annotate.Note("A - 1 - B", "one", annotate.Tag(self.SUBTOPIC))
        second = annotate.Note("C - 2 - D", "two", annotate.Tag(self.SUBTOPIC))
        merged = annotate.NoteLedger(first.rendered).appended(second)
        self.assertEqual(2, len(annotate.NoteLedger(merged).entries))

    def test_a_tag_is_recoverable_from_note_text(self) -> None:
        found = annotate.Tag.found_in("body\n#[[Kant's philosophy of mathematics]]")
        self.assertEqual([self.SUBTOPIC.lower()], [t.label.lower() for t in found])

    def test_untagged_text_yields_no_tags(self) -> None:
        self.assertEqual([], annotate.Tag.found_in("[[A - 1 - B]] — plain prose"))


class TestAnnotationSpec(unittest.TestCase):
    def test_a_spec_without_an_annotations_list_is_rejected(self) -> None:
        with self.assertRaises(annotate.SpecError):
            annotate.AnnotationSpec({}).requests()

    def test_an_annotation_without_a_page_is_rejected(self) -> None:
        with self.assertRaises(annotate.SpecError):
            annotate.AnnotationSpec({"annotations": [{"start": 1, "end": 2}]}).requests()

    def test_a_rectangle_annotation_is_recognised(self) -> None:
        payload = {"annotations": [{"page": 3, "rect": [1, 2, 3, 4]}]}
        self.assertTrue(annotate.AnnotationSpec(payload).requests()[0].is_rectangle)

    def test_a_word_span_annotation_is_not_a_rectangle(self) -> None:
        payload = {"annotations": [{"page": 3, "start": 0, "end": 5}]}
        self.assertFalse(annotate.AnnotationSpec(payload).requests()[0].is_rectangle)

    def test_a_tag_is_read_from_the_spec(self) -> None:
        payload = {"annotations": [{"page": 3, "start": 0, "end": 5, "tag": "Some Topic"}]}
        self.assertEqual("Some Topic",
                         annotate.AnnotationSpec(payload).requests()[0].note.tag.label)

    def test_an_end_page_marks_a_cross_page_span(self) -> None:
        payload = {"annotations": [{"page": 318, "start": 446, "end_page": 319, "end": 20}]}
        request = annotate.AnnotationSpec(payload).requests()[0]
        self.assertTrue(request.is_cross_page)

    def test_a_span_without_an_end_page_is_not_cross_page(self) -> None:
        payload = {"annotations": [{"page": 3, "start": 0, "end": 5}]}
        self.assertFalse(annotate.AnnotationSpec(payload).requests()[0].is_cross_page)

    def test_an_end_page_that_is_not_the_next_page_is_rejected(self) -> None:
        payload = {"annotations": [{"page": 318, "start": 446, "end_page": 320, "end": 20}]}
        with self.assertRaises(annotate.SpecError):
            annotate.AnnotationSpec(payload).requests()

    def test_further_spans_make_a_joint_highlight_of_one_page(self) -> None:
        payload = {"annotations": [{"page": 3, "start": 0, "end": 5, "further": [[9, 12]]}]}
        self.assertEqual(((0, 5), (9, 12)), annotate.AnnotationSpec(payload).requests()[0].spans)

    def test_further_spans_on_a_cross_page_span_are_rejected(self) -> None:
        payload = {"annotations": [{"page": 318, "start": 446, "end_page": 319, "end": 20, "further": [[1, 2]]}]}
        with self.assertRaises(annotate.SpecError):
            annotate.AnnotationSpec(payload).requests()

    def test_a_rectangle_with_an_end_page_is_rejected(self) -> None:
        payload = {"annotations": [{"page": 318, "rect": [1, 2, 3, 4], "end_page": 319, "end": 20}]}
        with self.assertRaises(annotate.SpecError):
            annotate.AnnotationSpec(payload).requests()


class TestRevisionSpec(unittest.TestCase):
    def test_a_change_without_an_index_is_rejected(self) -> None:
        with self.assertRaises(annotate.SpecError):
            annotate.RevisionSpec({"changes": [{"page": 1}]}).changes()

    def test_a_colour_is_read_as_a_tuple(self) -> None:
        payload = {"changes": [{"page": 1, "index": 0, "colour": [0, 1, 0]}]}
        self.assertEqual((0.0, 1.0, 0.0), annotate.RevisionSpec(payload).changes()[0].colour)

    def test_a_colour_name_resolves_to_the_palette(self) -> None:
        payload = {"changes": [{"page": 1, "index": 0, "colour": "green"}]}
        self.assertEqual(annotate.TagPalette().named("green").rgb,
                         annotate.RevisionSpec(payload).changes()[0].colour)

    def test_a_delete_flag_is_read(self) -> None:
        payload = {"changes": [{"page": 1, "index": 0, "delete": True}]}
        self.assertTrue(annotate.RevisionSpec(payload).changes()[0].delete)


class TestColour(unittest.TestCase):
    def test_a_hex_code_decodes_to_unit_channels(self) -> None:
        self.assertEqual((1.0, 212 / 255, 0.0), annotate.Colour("yellow", "#ffd400").rgb)

    def test_the_palette_names_zotero_yellow(self) -> None:
        self.assertEqual("#ffd400", annotate.TagPalette().named(" Yellow ").hex_code)


class TestWordSpan(unittest.TestCase):
    def test_length_is_the_index_difference(self) -> None:
        self.assertEqual(5, annotate.WordSpan(1, 10, 15).length)

    def test_indices_cover_the_half_open_range(self) -> None:
        self.assertEqual({10, 11, 12}, annotate.WordSpan(1, 10, 13).indices)


class TestLibraryPdfStaysInTheLibrary(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "VOLUMES_DIR").activate()
        self.addCleanup(self.vault.discard)

    def test_a_filed_pdf_is_found_by_name(self) -> None:
        filed = TextPdf(self.vault.library / "filed.pdf").write()
        self.assertEqual(filed, annotate.LibraryPdf("filed.pdf").path())

    def test_a_pdf_outside_the_library_is_refused_by_absolute_path(self) -> None:
        outside = TextPdf(self.vault.named("outside.pdf")).write()
        with self.assertRaises(FileNotFoundError):
            annotate.LibraryPdf(str(outside)).path()

    def test_a_volume_is_refused_because_it_has_no_corpus_file(self) -> None:
        volume = TextPdf(self.vault.volumes / "volume.pdf").write()
        with self.assertRaises(FileNotFoundError):
            annotate.LibraryPdf(str(volume)).path()

    def test_a_relative_path_escaping_the_library_is_refused(self) -> None:
        TextPdf(self.vault.named("outside.pdf")).write()
        with self.assertRaises(FileNotFoundError):
            annotate.LibraryPdf("../outside.pdf").path()


class TestCliSurface(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "VOLUMES_DIR").activate()
        self.addCleanup(self.vault.discard)
        TextPdf(self.vault.library / "filed.pdf").write()

    def _exit_code(self, argv: list[str]) -> int:
        with contextlib.redirect_stderr(io.StringIO()):
            return annotate.AnnotateCli().run(argv)

    def test_a_missing_pdf_is_reported_as_an_error_before_any_subcommand_runs(self) -> None:
        self.assertEqual(1, self._exit_code(["anchors", "no-such-file.pdf"]))

    def test_a_malformed_reference_is_reported_as_an_error(self) -> None:
        self.assertEqual(1, self._exit_code(["locate", "filed.pdf", "--ref", "nonsense"]))


if __name__ == "__main__":
    unittest.main()
