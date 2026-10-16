from __future__ import annotations

import unittest
from dataclasses import dataclass

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import (
    BBOX, BELOW_BODY, BODY_BOX, BODY_SIZE, ENTRY_LEFT, FLUSH_LEFT, FOOT_BOX, FULL_MEASURE, HANGING_LEFT,
    NOTE_NUMBER_LEFT, NOTE_RUN_ON_LEFT, FakeLayer, LineExtent, PrintedWork, RunSetting, excluding, keep_everything,
    layer_line, page_assembler, positioned,
)
from _extract.blocks import Block, PageBlocks
from _extract.candidates import OpenedHeadings
from _extract.headings import HeadingLevels
from _extract.layer import LayerChar, LayerLine
from _extract.outline import Heading as OutlineHeading
from _extract.policy import SectionOpening, SectionPolicy
from _extract.spans import PagePlace
from _extract.structure import Heading, PageAssembler, PageMarker, Paragraph, Verbatim

HEADING_BOX = (40.0, 90.0, 380.0, 104.0)
PARAGRAPH_LEFT, PARAGRAPH_RIGHT = 40.0, 380.0
FIRST_PARAGRAPH_TOP, PARAGRAPH_PITCH, PARAGRAPH_HEIGHT, PARAGRAPH_BASELINE_DROP = 110.0, 30.0, 20.0, 15.0


class TestPixelPages(unittest.TestCase):
    HTML = "<p>Let <math>\\Gamma \\succ \\Delta</math> agree.</p>"

    def _assembler(self, pixel_pages: frozenset[int], layer_text: str = "Let G > D agree."):
        layer = BoxedLayer(positioned(layer_text, RunSetting(10.0, 50.0, 0)), layer_text)
        return page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=pixel_pages))

    def _text(self, pixel_pages: frozenset[int], layer_text: str = "Let G > D agree.", html: str = HTML) -> str:
        assembler = self._assembler(pixel_pages, layer_text)
        return assembler.assemble(PageBlocks(1, [block("Text", html)]), [], 1).elements[1].text

    def test_a_prose_word_and_an_apostrophe_the_engine_misread_take_the_text_layers_forms(self) -> None:
        html = "<p>5 of Peirce's <math>\\Gamma</math> figure.</p>"
        self.assertEqual("5 cf Peirce’s $\\Gamma$ figure.", self._text(frozenset({1}), "5 cf Peirce’s Γ figure.", html))

    def test_a_prose_word_keeps_the_engines_reading_where_the_layer_lies_invisibly_under_a_scan(self) -> None:
        layer = UndrawnLayer(positioned("5 cf Peirce’s Γ figure.", RunSetting(10.0, 50.0, 0)),
                             "5 cf Peirce’s Γ figure.")
        assembler = page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=frozenset({1})))
        html = "<p>5 of Peirce's <math>\\Gamma</math> figure.</p>"
        text = assembler.assemble(PageBlocks(1, [block("Text", html)]), [], 1).elements[1].text
        self.assertEqual("5 of Peirce's $\\Gamma$ figure.", text)

    def test_a_prose_word_unlike_the_layers_keeps_the_engines_reading_beside_a_curled_apostrophe(self) -> None:
        html = "<p>5 of Peirce's <math>\\Gamma</math> figure.</p>"
        self.assertEqual("5 of Peirce’s $\\Gamma$ figure.", self._text(frozenset({1}), "5 by Peirce’s Γ figure.", html))

    def test_a_symbol_the_engine_misread_is_corrected_from_the_text_layer(self) -> None:
        self.assertEqual("Let $\\Gamma \\succ \\Lambda$ agree.", self._text(frozenset({1}), "Let Γ ≻ Λ agree."))

    def test_a_corrected_formula_is_logged(self) -> None:
        assembler = self._assembler(frozenset({1}), "Let Γ ≻ Λ agree.")
        assembler.assemble(PageBlocks(1, [block("Text", self.HTML)]), [], 1)
        expected = "file p. 1: corrected \\Gamma \\succ \\Delta to \\Gamma \\succ \\Lambda (text layer: Γ ≻ Λ)"
        self.assertEqual([expected], assembler.notation_log())

    def test_a_page_read_from_pixels_keeps_the_engines_latex(self) -> None:
        self.assertEqual("Let $\\Gamma \\succ \\Delta$ agree.", self._text(frozenset({1})))

    def test_a_page_read_from_the_text_layer_takes_the_layers_characters(self) -> None:
        self.assertEqual("Let G > D agree.", self._text(frozenset()))


class BoxedLayer(FakeLayer):
    def chars_in(self, file_page: int, bbox) -> list[LayerChar]:
        return [char for char in self._chars if bbox.contains(char.center)]


class UndrawnLayer(BoxedLayer):
    def is_drawn(self, file_page: int) -> bool:
        return False


def chars(text: str, raised: str = "", small: str = "") -> list[LayerChar]:
    return [LayerChar(char, (1.0, 1.0), char in raised, BODY_SIZE / 2 if char in small else BODY_SIZE) for char in text]


def block(kind: str, html: str, file_page: int = 1) -> Block:
    return Block(file_page, kind, html, BBOX, {}, f"/page/{file_page}/{kind}/0")


@dataclass(frozen=True)
class Due:
    headings: list
    sublevel: int | None


@dataclass(frozen=True)
class PageSetting:
    layer_text: str = ""
    policy: SectionPolicy | None = None


@dataclass(frozen=True)
class HeaderPage:
    file_page: int
    htmls: list[str]


def levelled(elements: list) -> list:
    return [element.at_level(element.level) if isinstance(element, Heading) else element for element in elements]


class TestPageAssembler(unittest.TestCase):
    def _assembled(self, kind: str, html: str, layer_text: str = "") -> list:
        return self._page([block(kind, html)], Due([], 1), PageSetting(layer_text))

    def _page(self, blocks: list, due: Due, setting: PageSetting = PageSetting()) -> list:
        layer = FakeLayer(chars(setting.layer_text), setting.layer_text)
        assembler = page_assembler(layer, setting.policy or keep_everything())
        return assembler.assemble(PageBlocks(1, blocks), due.headings, due.sublevel).elements[1:]

    def test_a_bare_chapter_label_absorbs_the_engines_title_heading(self) -> None:
        blocks = [block("SectionHeader", "<h1>Chapter Two</h1>"),
                  block("SectionHeader", "<h1>Presuppositionless Thinking</h1>"),
                  block("SectionHeader", "<h1><i>Beginning with Pure Being</i></h1>")]
        elements = self._page(blocks, Due([OutlineHeading(1, "Chapter 2", 1)], 2))
        expected = [Heading(1, "Chapter 2: Presuppositionless Thinking", 1), Heading(2, "Beginning with Pure Being", 1)]
        self.assertEqual(expected, levelled(elements))

    def test_an_engine_label_and_title_already_opened_from_the_outline_are_not_repeated(self) -> None:
        blocks = [block("SectionHeader", "<h1>Part I</h1>"), block("SectionHeader", "<h1>Propositional Logic</h1>")]
        elements = self._page(blocks, Due([OutlineHeading(1, "Part I Propositional Logic", 1)], 2))
        self.assertEqual([Heading(1, "Part I Propositional Logic", 1)], levelled(elements))

    def test_an_engine_heading_differing_from_the_outline_only_in_spacing_is_not_repeated(self) -> None:
        blocks = [block("SectionHeader", "<h1>3.6a The Tense Logic K t</h1>")]
        elements = self._page(blocks, Due([OutlineHeading(3, "3.6a The Tense Logic Kt", 1)], 4))
        self.assertEqual([Heading(3, "3.6a The Tense Logic Kt", 1)], levelled(elements))

    def test_a_run_in_label_the_engine_calls_a_heading_is_a_bold_paragraph(self) -> None:
        blocks = [block("SectionHeader", "<h1>Proof:</h1>"), block("Text", "<p>Suppose not.</p>")]
        elements = self._page(blocks, Due([], 4))
        self.assertEqual([Paragraph("**Proof:**", False, 1), Paragraph("Suppose not.", False, 1)], elements)

    def test_a_section_headed_acknowledgements_is_kept_when_no_span_excludes_it(self) -> None:
        blocks = [block("SectionHeader", "<h1>Acknowledgements</h1>"), block("Text", "<p>Thanks.</p>")]
        elements = self._page(blocks, Due([], 1))
        self.assertEqual([Heading(1, "Acknowledgements", 1), Paragraph("Thanks.", False, 1)], levelled(elements))

    def test_an_outline_section_inside_a_span_is_dropped(self) -> None:
        blocks = [block("SectionHeader", "<h1>Reprinted Text</h1>"), block("Text", "<p>Hegel.</p>")]
        policy = excluding(PagePlace(1), PagePlace(2))
        elements = self._page(blocks, Due([OutlineHeading(1, "Reprinted Text", 1)], 2), PageSetting(policy=policy))
        self.assertEqual([], elements)

    def test_a_chapter_label_inside_a_span_is_dropped_even_when_it_absorbs_a_title(self) -> None:
        blocks = [block("SectionHeader", "<h1>Chapter Nine</h1>"), block("SectionHeader", "<h1>Being: Text</h1>"),
                  block("Text", "<p>Hegel.</p>")]
        policy = excluding(PagePlace(1), PagePlace(2))
        elements = self._page(blocks, Due([OutlineHeading(1, "Chapter 9", 1)], 2), PageSetting(policy=policy))
        self.assertEqual([], elements)

    def test_an_engine_part_label_absorbs_its_title_at_the_top_level(self) -> None:
        blocks = [block("SectionHeader", "<h1>Part One</h1>"), block("SectionHeader", "<h1>The Project</h1>")]
        elements = self._page(blocks, Due([], 2))
        self.assertEqual([Heading(1, "Part One: The Project", 1)], levelled(elements))

    def test_an_index_and_what_follows_it_are_kept_unless_a_span_excludes_them(self) -> None:
        blocks = [block("SectionHeader", "<h1>Index</h1>"), block("Text", "<p>absolute, 55</p>"),
                  block("SectionHeader", "<h2>Of Related Interest</h2>"), block("Text", "<p>Ads.</p>")]
        texts = [getattr(element, "text", None) or element.title for element in self._page(blocks, Due([], 1))]
        self.assertEqual((True, True), ("absolute, 55" in texts, "Ads." in texts))

    def test_a_reference_list_is_rebuilt_from_the_text_layers_hanging_indents(self) -> None:
        lines = [layer_line("Allison, Kant's Transcendental", LineExtent(ENTRY_LEFT, 300.0), 0),
                 layer_line("Idealism (New Haven, 1983).", LineExtent(HANGING_LEFT, 240.0), 1),
                 layer_line("Beiser, Hegel (London, 2005).", LineExtent(ENTRY_LEFT, 290.0), 2)]
        assembler = page_assembler(FakeLayer(lines=lines), keep_everything())
        entries = "Allison, Kant's Transcendental Idealism (New Haven, 1983). Beiser, Hegel (London, 2005)."
        blocks = [block("SectionHeader", "<h1>Bibliography</h1>"), block("Text", f"<p>{entries}</p>")]
        elements = levelled(assembler.assemble(PageBlocks(1, blocks), [], 1).elements[1:])
        expected = [Heading(1, "Bibliography", 1),
                    Paragraph("Allison, Kant's Transcendental Idealism (New Haven, 1983).", False, 1),
                    Paragraph("Beiser, Hegel (London, 2005).", False, 1)]
        self.assertEqual(expected, elements)

    def test_an_outline_entry_matches_the_engines_spelled_out_chapter_number(self) -> None:
        elements = self._page([block("SectionHeader", "<h1>Chapter One</h1>")],
                              Due([OutlineHeading(1, "Chapter 1", 1)], 2))
        self.assertEqual([Heading(1, "Chapter 1", 1)], elements)

    def test_an_unmatched_outline_entry_opens_the_page_and_absorbs_the_title_that_follows(self) -> None:
        blocks = [block("SectionHeader", "<h2><b>The Categories</b></h2>"), block("Text", "<p>Prose.</p>")]
        elements = self._page(blocks, Due([OutlineHeading(1, "Chapter 1", 1)], 2))
        self.assertEqual([Heading(1, "Chapter 1: The Categories", 1), Paragraph("Prose.", False, 1)], elements)

    def test_a_compound_chapter_number_matches_its_outline_entry(self) -> None:
        blocks = [block("SectionHeader", "<h1>Chapter Twenty-one</h1>")]
        elements = self._page(blocks, Due([OutlineHeading(1, "Chapter 21", 1)], 2))
        self.assertEqual([Heading(1, "Chapter 21", 1)], levelled(elements))

    def test_an_unmatched_outline_entry_stays_alone_when_prose_follows_it(self) -> None:
        blocks = [block("Text", "<p>Prose.</p>"), block("SectionHeader", "<h2>Later</h2>")]
        elements = self._page(blocks, Due([OutlineHeading(1, "Chapter 1", 1)], 2))
        expected = [Heading(1, "Chapter 1", 1), Paragraph("Prose.", False, 1), Heading(2, "Later", 1)]
        self.assertEqual(expected, levelled(elements))

    def test_an_engine_heading_before_the_outline_begins_is_a_bold_paragraph(self) -> None:
        elements = self._page([block("SectionHeader", "<h1>PURDUE UNIVERSITY PRESS</h1>")], Due([], None))
        self.assertEqual([Paragraph("**PURDUE UNIVERSITY PRESS**", False, 1)], elements)

    def test_a_heading_set_in_two_faces_keeps_the_space_between_them(self) -> None:
        elements = self._page([block("SectionHeader", "<h2><b>Note on Hegel's</b><i>Science of Logic</i></h2>")],
                              Due([], 2))
        self.assertEqual([Heading(2, "Note on Hegel's Science of Logic", 1)], levelled(elements))

    def test_without_size_information_an_engine_heading_takes_the_sublevel(self) -> None:
        elements = self._page([block("SectionHeader", "<h3>Semantics</h3>")], Due([], 1))
        self.assertEqual([Heading(1, "Semantics", 1)], levelled(elements))

    def test_engine_math_in_prose_becomes_inline_latex_in_the_paragraph(self) -> None:
        elements = self._assembled("Text", "<p>Let <math>\\Gamma \\succ \\Delta</math> agree.</p>")
        self.assertEqual([Paragraph("Let $\\Gamma \\succ \\Delta$ agree.", False, 1)], elements)

    def test_an_equation_table_becomes_a_markdown_table_of_latex(self) -> None:
        html = ('<p block-type="Equation"><table><tr><td><math display="block">\\Gamma</math></td><td>iff</td>'
                '<td><math>\\Delta</math></td></tr></table></p>')
        expected = [Verbatim("| $$\\Gamma$$ | iff | $\\Delta$ |\n| --- | --- | --- |", 1)]
        self.assertEqual(expected, self._assembled("Equation", html))

    def test_an_equation_contributes_its_latex_to_the_page_text(self) -> None:
        html = '<p block-type="Equation"><math display="block">\\forall x</math></p>'
        assembler = page_assembler(FakeLayer(), keep_everything())
        self.assertIn("$$\\forall x$$", assembler.assemble(PageBlocks(1, [block("Equation", html)]), [], 1).text)


class TestHeadingLevels(unittest.TestCase):
    def test_recurring_heading_styles_are_levelled_by_size_then_first_appearance_below_the_outline(self) -> None:
        elements = [Heading(2, "Section", 1, (12.0, True, True)), Heading(2, "Sub", 1, (12.0, True, False)),
                    Heading(2, "Section again", 1, (12.0, True, True)), Heading(2, "Big", 1, (14.0, True, False)),
                    Heading(2, "Sub again", 1, (12.0, True, False)), Heading(2, "Big again", 1, (14.0, True, False)),
                    Heading(1, "Outline", 1)]
        self.assertEqual([3, 4, 3, 2, 4, 2, 1], [element.level for element in HeadingLevels().levelled(elements)])

    def test_a_one_off_heading_style_sits_directly_under_its_parent(self) -> None:
        elements = [Heading(2, "Odd", 1, (14.0, True, False)), Heading(2, "Section", 1, (12.0, True, True)),
                    Heading(2, "Section again", 1, (12.0, True, True)), Heading(2, "Tiny", 1, (11.0, True, True))]
        self.assertEqual([2, 2, 2, 2], [element.level for element in HeadingLevels().levelled(elements)])


class TestEntryNotation(unittest.TestCase):
    def test_notation_in_a_rebuilt_entry_keeps_the_pages_characters(self) -> None:
        chars = (positioned("14 Note ", RunSetting(60.0, 100.0, 0))
                 + positioned("\u0393\u22a2\u0394", RunSetting(108.0, 100.0, 0, "CMSY10"))
                 + positioned(" holds.", RunSetting(126.0, 100.0, 0)))
        line = LayerLine("14 Note \u0393\u22a2\u0394 holds.", 60.0, 168.0, 90.0, (114.0, 96.0))
        layer = FakeLayer(chars, "", lines=[line])
        assembler = page_assembler(layer, keep_everything())
        [entry] = assembler.hanging_entries(1, [block("Text", "")])
        self.assertEqual("14 Note \u0393\u22a2\u0394 holds.", entry.text)


class TestMeasuredPageText(unittest.TestCase):
    def test_a_pages_footnotes_count_toward_the_text_layer_it_is_measured_against(self) -> None:
        blocks = [block("Text", "<p>Body.</p>"), block("Footnote", "<p>1 A note.</p>")]
        layer = FakeLayer(chars("Body. 1 A note."))
        assembler = page_assembler(layer, keep_everything())
        self.assertIn("A note.", assembler.assemble(PageBlocks(1, blocks), [], 1).layer_text)


class TestMeasuredPageOutput(unittest.TestCase):
    def test_a_pages_paired_footnotes_count_toward_its_output(self) -> None:
        blocks = [block("Text", "<p>Body.<sup>1</sup></p>"), block("Footnote", "<p>1 A note.</p>")]
        assembler = page_assembler(FakeLayer(), keep_everything())
        self.assertIn("A note.", assembler.assemble(PageBlocks(1, blocks), [], 1).text)


class TestExcludedFootnotes(unittest.TestCase):
    def test_a_footnote_inside_an_excluded_span_defines_nothing(self) -> None:
        blocks = [Block(1, "Text", "<p>Body.<sup>57</sup></p>", BODY_BOX, {}, "/page/1/Text/0"),
                  Block(1, "Footnote", "<p>57 I am grateful.</p>", FOOT_BOX, {}, "/page/1/Footnote/0")]
        policy = excluding(PagePlace(1, BELOW_BODY), PagePlace(2, 0.0))
        assembler = page_assembler(FakeLayer(), policy)
        self.assertEqual([], assembler.assemble(PageBlocks(1, blocks), [], 1).definitions)


class TestNotesSections(unittest.TestCase):
    def _elements(self, layer: FakeLayer, html: str) -> list:
        policy = keep_everything()
        policy.opens(SectionOpening(1, "Introduction"))
        policy.opens(SectionOpening(1, "Notes"))
        assembler = page_assembler(layer, policy)
        return assembler.assemble(PageBlocks(1, [block("Text", html)]), [], 1).elements[1:]

    def test_a_notes_section_of_prose_keeps_its_paragraphs(self) -> None:
        text = "Besides the first edition of the Logic, Hegel produced several other versions."
        self.assertEqual([Paragraph(text, False, 1)], self._elements(FakeLayer(), f"<p>{text}</p>"))

    def test_a_block_opening_on_no_note_number_continues_the_note_the_engine_split_it_from(self) -> None:
        policy = keep_everything()
        policy.opens(SectionOpening(1, "Notes"))
        assembler = page_assembler(FakeLayer(), policy)
        blocks = [block("Text", "<p>1 Ferrini traces the works that deal</p>"),
                  block("Text", "<p>with topics in mechanics.</p>")]
        elements = assembler.assemble(PageBlocks(1, blocks), [], 1).elements[1:]
        self.assertEqual(["1 Ferrini traces the works that deal with topics in mechanics."],
                         [element.text for element in elements])

    def test_a_notes_section_of_numbered_notes_is_rebuilt_one_entry_per_note(self) -> None:
        lines = [layer_line("1 First note runs on", LineExtent(NOTE_NUMBER_LEFT, FULL_MEASURE), 0),
                 layer_line("to a second line.", LineExtent(NOTE_RUN_ON_LEFT, 300.0), 1),
                 layer_line("2 Second note.", LineExtent(NOTE_NUMBER_LEFT, 200.0), 2)]
        html = "<p>1 First note runs on to a second line. 2 Second note.</p>"
        elements = self._elements(FakeLayer(lines=lines), html)
        self.assertEqual(["1 First note runs on to a second line.", "2 Second note."],
                         [element.text for element in elements])


class TestOpenedHeadingScope(unittest.TestCase):
    def _assembler(self, policy: SectionPolicy) -> PageAssembler:
        return page_assembler(FakeLayer(), policy)

    def _titles(self, assembler: PageAssembler, page: HeaderPage, due: list) -> list[str]:
        blocks = [block("SectionHeader", html, page.file_page) for html in page.htmls]
        elements = assembler.assemble(PageBlocks(page.file_page, blocks), due, 2).elements[1:]
        return [element.title for element in elements if isinstance(element, Heading)]

    def test_a_title_opened_on_an_unkept_page_does_not_block_it_later(self) -> None:
        assembler = self._assembler(excluding(PagePlace(1), PagePlace(2)))
        self._titles(assembler, HeaderPage(1, ["<h2>Becoming</h2>"]), [])
        self.assertEqual(["Becoming"], self._titles(assembler, HeaderPage(2, ["<h2>Becoming</h2>"]), []))

    def test_the_same_section_title_is_written_in_two_chapters(self) -> None:
        assembler = self._assembler(keep_everything())
        self._titles(assembler, HeaderPage(1, ["<h2>Logic as Ontology</h2>"]),
                     [OutlineHeading(1, "The Opening of Logic", 1)])
        titles = self._titles(assembler, HeaderPage(2, ["<h2>Logic as Ontology</h2>"]),
                              [OutlineHeading(1, "The Doctrine of Being", 2)])
        self.assertIn("Logic as Ontology", titles)

    def test_a_repeat_within_one_chapter_is_still_suppressed(self) -> None:
        assembler = self._assembler(keep_everything())
        titles = self._titles(assembler, HeaderPage(1, ["<h2>Becoming</h2>", "<h2>Becoming</h2>"]),
                              [OutlineHeading(1, "The Opening of Logic", 1)])
        self.assertEqual(1, titles.count("Becoming"))

    def test_a_top_level_heading_resets_the_scope(self) -> None:
        opened = OpenedHeadings()
        opened.add("Becoming", 2)
        opened.add("Chapter 2", 1)
        self.assertFalse(opened.names("Becoming"))


class TestFootnoteMarksOnHeadings(unittest.TestCase):
    def _elements(self, html: str) -> list:
        assembler = page_assembler(FakeLayer(), keep_everything())
        due = [OutlineHeading(1, "The Opening of Logic", 1)]
        return assembler.assemble(PageBlocks(1, [block("SectionHeader", html, 1)]), due, 2).elements[1:]

    def test_a_footnote_mark_is_not_part_of_the_heading_title(self) -> None:
        elements = self._elements("<h2>Logic as Ontology [^3]</h2>")
        titles = [element.title for element in elements if isinstance(element, Heading)]
        self.assertEqual(["The Opening of Logic", "Logic as Ontology"], titles)

    def test_the_mark_sits_on_its_own_line_below_the_heading(self) -> None:
        elements = self._elements("<h2>Logic as Ontology [^3]</h2>")
        self.assertEqual(Paragraph("[^3]", False, 1), elements[-1])

    def test_an_endnote_mark_raised_on_a_heading_sits_on_its_own_line_below_it(self) -> None:
        elements = self._elements("<h2>Logic as Ontology<sup>3</sup></h2>")
        self.assertEqual(["Logic as Ontology", "<sup>3</sup>"],
                         [getattr(element, "title", None) or element.text for element in elements[-2:]])


class TestHeadingAtAResumePoint(unittest.TestCase):
    def test_an_outline_heading_at_the_top_of_the_page_a_span_resumes_on_opens_at_the_resume_point(self) -> None:
        blocks = [Block(50, "Text", "<p>1. In the preface to a philosophical work.</p>", (0.0, 176.0, 100.0, 526.0), {},
                        "/page/50/Text/0")]
        policy = excluding(PagePlace(48, 0.0), PagePlace(50, 88.0))
        assembler = page_assembler(FakeLayer(), policy)
        elements = assembler.assemble(PageBlocks(50, blocks), [OutlineHeading(1, "Preface", 50, 0.0)], 1).elements[1:]
        texts = [getattr(element, "title", None) or element.text for element in elements]
        self.assertEqual(["Preface", "1. In the preface to a philosophical work."], texts)


class TestSpansWithinAPage(unittest.TestCase):
    def _texts(self, heading: str | None, paragraphs: list[str], policy: SectionPolicy) -> list:
        blocks, chars, due = [], [], []
        if heading is not None:
            blocks.append(Block(1, "SectionHeader", f"<h1>{heading}</h1>", HEADING_BOX, {}, "/page/1/SectionHeader/0"))
            due.append(OutlineHeading(1, heading, 1))
        for index, text in enumerate(paragraphs):
            top = self._paragraph_top(index)
            box = (PARAGRAPH_LEFT, top, PARAGRAPH_RIGHT, top + PARAGRAPH_HEIGHT)
            blocks.append(Block(1, "Text", f"<p>{text}</p>", box, {}, f"/page/1/Text/{index}"))
            chars += positioned(text, RunSetting(PARAGRAPH_LEFT, top + PARAGRAPH_BASELINE_DROP, index + 1))
        assembler = page_assembler(BoxedLayer(chars), policy)
        elements = assembler.assemble(PageBlocks(1, blocks), due, 2).elements[1:]
        return [getattr(element, "title", None) or element.text for element in elements]

    @staticmethod
    def _paragraph_top(index: int) -> float:
        return FIRST_PARAGRAPH_TOP + index * PARAGRAPH_PITCH

    def test_a_headed_abstract_inside_a_span_is_dropped_and_the_body_it_resumes_at_is_kept(self) -> None:
        policy = excluding(PagePlace(1, HEADING_BOX[1]), PagePlace(1, self._paragraph_top(1)))
        texts = self._texts("Abstract", ["Abstract text.", "Body text begins."], policy)
        self.assertEqual(["Body text begins."], texts)

    def test_an_unheaded_abstract_sharing_a_page_with_the_body_is_dropped_alone(self) -> None:
        policy = excluding(PagePlace(1, self._paragraph_top(1)), PagePlace(1, self._paragraph_top(2)))
        texts = self._texts(None, ["Title block.", "Abstract text.", "Body text begins."], policy)
        self.assertEqual(["Title block.", "Body text begins."], texts)

    def test_a_section_headed_preface_is_kept_when_no_span_excludes_it(self) -> None:
        self.assertEqual(["Preface", "Thanks to many."], self._texts("Preface", ["Thanks to many."], keep_everything()))


class TestTranscribedPage(unittest.TestCase):
    def _elements(self, text: str, due: list) -> list:
        policy = keep_everything()
        policy.opens(SectionOpening(1, "Introduction"))
        assembler = page_assembler(FakeLayer(), policy)
        return assembler.transcribed(PageBlocks(16, []), text, due).elements[1:]

    def test_an_outline_heading_opens_where_the_transcribed_page_prints_it(self) -> None:
        text = "The conclusion ends here.\n\nNotes\n\n1 A first note."
        elements = self._elements(text, [OutlineHeading(1, "Notes", 16)])
        self.assertEqual([Paragraph("The conclusion ends here.", False, 16), Heading(1, "Notes", 16),
                          Paragraph("1 A first note.", False, 16)], elements)

    def test_a_transcribed_page_with_no_outline_heading_is_one_paragraph(self) -> None:
        self.assertEqual([Paragraph("Plain page text.", False, 16)], self._elements("Plain page text.", []))

    def test_an_outline_heading_the_transcription_does_not_print_opens_before_the_text(self) -> None:
        elements = self._elements("Body only.", [OutlineHeading(1, "Notes", 16)])
        self.assertEqual([Heading(1, "Notes", 16), Paragraph("Body only.", False, 16)], elements)


class TestOmittedPage(unittest.TestCase):
    def _assembler(self) -> PageAssembler:
        policy = keep_everything()
        policy.opens(SectionOpening(1, "Introduction"))
        return page_assembler(FakeLayer(), policy)

    def test_an_outline_heading_due_on_an_unreadable_page_still_opens(self) -> None:
        result = self._assembler().omitted([OutlineHeading(1, "Notes", 16)])
        self.assertEqual([Heading(1, "Notes", 16)], result.elements)

    def test_an_unreadable_page_contributes_no_text(self) -> None:
        result = self._assembler().omitted([OutlineHeading(1, "Notes", 16)])
        self.assertEqual(("", ""), (result.text, result.layer_text))

    def test_an_unreadable_page_contributes_no_page_marker(self) -> None:
        result = self._assembler().omitted([OutlineHeading(1, "Notes", 16)])
        self.assertEqual([], [element for element in result.elements if isinstance(element, PageMarker)])

    def test_an_unreadable_page_with_no_outline_heading_contributes_nothing(self) -> None:
        self.assertEqual([], self._assembler().omitted([]).elements)

    def test_a_reference_list_opening_on_an_unreadable_page_rebuilds_the_next_page(self) -> None:
        lines = [layer_line("Allison, H. E. (2004), Kant's Transcendental", LineExtent(FLUSH_LEFT, FULL_MEASURE), 0),
                 layer_line("Idealism. New Haven: Yale University Press.", LineExtent(FLUSH_LEFT, 189.4), 1)]
        policy = keep_everything()
        assembler = page_assembler(FakeLayer(lines=lines), policy)
        assembler.omitted([OutlineHeading(1, "Bibliography", 17)])
        self.assertTrue(policy.in_entry_list)


if __name__ == "__main__":
    unittest.main()
