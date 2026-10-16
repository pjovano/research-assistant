from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _references_fixtures import LINK_LINE, PDF_BYTES, VaultTestCase
from cite import (
    STATUS_NO_BODY,
    STATUS_REWRITTEN,
    STATUS_UNCHANGED,
    ConflictCopies,
    LinksRebuild,
    NoteLinks,
)
from references import AUTOMATIC_THRESHOLD, CitationScoring, HeldWorks, ParsedReference

CITING = "Brandom - 2019 - A Spirit of Trust"
EARLIER = "Brandom - 1994 - Making It Explicit"
TRANSLATION = "Hegel - 2018 - Phenomenology of Spirit"
LATER = "Doe - 2024 - Later Work"
KANT = "Kant - 1998 - Critique of Pure Reason"
CITING_FRONTMATTER = "title: A Spirit of Trust\nyear: 2019\n"
TRANSLATION_FRONTMATTER = ("title: Phenomenology of Spirit\nyear: 2018\norig_year: 1807\n"
                           "aliases:\n- Phänomenologie des Geistes\n")
ENTRY = "Brandom, Robert. *Making It Explicit*. Cambridge, MA: Harvard University Press, 1994."
BIBLIOGRAPHY_BODY = (f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n%% p. 400 (file p. 420) %%\n\n"
                     f"{ENTRY}\n\nDoe, Jane. *Later Work*. 2024.\n\n[^1]: A note.\n")
FOOTNOTE_BODY = f"{LINK_LINE}\n\n# One\n\nProse.[^1]\n\n[^1]: See Brandom, Making It Explicit, ch. 1.\n"
UNMARKED_NOTE = "[^2]: 1. See Brandom, Making It Explicit, ch. 1."
UNMARKED_FOOTNOTE_BODY = f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Notes\n\n{UNMARKED_NOTE}\n"
BROKEN_ENTRY = "Brandom, Robert. *Making It Ex- plicit*. Cambridge, MA: Harvard University Press, 1994."
REVIEW_ENTRY = "Doe, Jane. Brandom's Making It Explicit. Mind 105 (1996)."
COMMENTARY_ENTRY = ("Strawson, P. F. The Bounds of Sense: An Essay on Kant's Critique of Pure Reason. "
                    "London: Methuen, 1966.")
SCORED_BODY = (f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n{BROKEN_ENTRY}\n\n{REVIEW_ENTRY}\n\n"
               f"{COMMENTARY_ENTRY}\n")
BRACKETED_ENTRY = ("Hegel, G.W.F. \\[1807\\] (1994) *Making It Explicit* \\[*MIE*\\]. "
                   "Cambridge, MA: Harvard University Press.")
BRACKETED_BODY = f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n{BRACKETED_ENTRY}\n"
EARLIER_FRONTMATTER = "title: Making It Explicit\nyear: 1994\n"
KANT_FRONTMATTER = "title: Critique of Pure Reason\nyear: 1998\n"
NOTHING = ParsedReference((), None, None, None, None, None)
HARVARD = "Harvard University Press"
MAKING_IT_EXPLICIT = ParsedReference(("Brandom, Robert",), "Making It Explicit", None, "1994", HARVARD, None)
MAKING_IT_EXPLICIT_REVIEW = ParsedReference(("Doe, Jane",), "Brandom's Making It Explicit", "Mind", "1996", None, None)
BOUNDS_OF_SENSE_TITLE = "The Bounds of Sense: An Essay on Kant's Critique of Pure Reason"
BOUNDS_OF_SENSE = ParsedReference(("Strawson, P. F.",), BOUNDS_OF_SENSE_TITLE, None, "1966", "Methuen", None)
MAKING_IT_EXPLICIT_FOOTNOTE = ParsedReference(("Brandom",), "Making It Explicit", None, None, None, None)
NAMED_ENTRY = "Brandom, Robert (1989), Inference and Expression. Oxford: Oxford University Press."
REPEATED_ENTRY = "—— (1994), Making It Explicit. Cambridge, MA: Harvard University Press."
RESTORED_ENTRY = "Brandom, Robert (1994), Making It Explicit. Cambridge, MA: Harvard University Press."
REPEATED_BODY = (f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n{NAMED_ENTRY}\n\n{REPEATED_ENTRY}\n")
ORPHAN_BODY = f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n{REPEATED_ENTRY}\n"
NOTE_ENTRY = "1. See Brandom, Making It Explicit, ch. 1."
ENDNOTES_BODY = f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Notes\n\n{NOTE_ENTRY}\n"
SINGULAR_NOTES_BODY = f"{LINK_LINE}\n\n# One\n\nProse.\n\n# NOTE\n\n{NOTE_ENTRY}\n"
INFERENCE = ParsedReference(("Brandom, Robert",), "Inference and Expression", None, "1989", None, None)
HYPHENATED = "Merleau-Ponty - 1945 - Phenomenology of Perception"
APOSTROPHE = "O'Neill - 1996 - Towards Justice and Virtue"
HYPHENATED_FRONTMATTER = "title: Phenomenology of Perception\nauthor:\n- Merleau-Ponty\nyear: 1945\n"
APOSTROPHE_FRONTMATTER = "title: Towards Justice and Virtue\nauthor:\n- O'Neill\nyear: 1996\n"
HYPHENATED_ENTRY = "Merleau-Ponty, Maurice. *Phenomenology of Perception*. London: Routledge, 1945."
APOSTROPHE_ENTRY = "O'Neill, Onora. *Towards Justice and Virtue*. Cambridge: Cambridge University Press, 1996."
PUNCTUATED_BODY = f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n{HYPHENATED_ENTRY}\n\n{APOSTROPHE_ENTRY}\n"
PHENOMENOLOGY_OF_PERCEPTION = ParsedReference(("Merleau-Ponty, Maurice",), "Phenomenology of Perception", None,
                                              "1945", "Routledge", None)
TOWARDS_JUSTICE_AND_VIRTUE = ParsedReference(("O'Neill, Onora",), "Towards Justice and Virtue", None, "1996",
                                             "Cambridge University Press", None)

PARSED = {
    BROKEN_ENTRY: MAKING_IT_EXPLICIT,
    REVIEW_ENTRY: MAKING_IT_EXPLICIT_REVIEW,
    COMMENTARY_ENTRY: BOUNDS_OF_SENSE,
    ENTRY: MAKING_IT_EXPLICIT,
    BRACKETED_ENTRY: MAKING_IT_EXPLICIT,
    "See Brandom, Making It Explicit, ch. 1.": MAKING_IT_EXPLICIT_FOOTNOTE,
    NOTE_ENTRY: MAKING_IT_EXPLICIT_FOOTNOTE,
    NAMED_ENTRY: INFERENCE,
    RESTORED_ENTRY: MAKING_IT_EXPLICIT,
    HYPHENATED_ENTRY: PHENOMENOLOGY_OF_PERCEPTION,
    APOSTROPHE_ENTRY: TOWARDS_JUSTICE_AND_VIRTUE,
}


def linked(entry: str, work: str) -> str:
    return f"{entry} [[{work}|↗]]"


class FakeParser:
    def parse(self, entry_text: str) -> ParsedReference:
        return PARSED.get(entry_text, NOTHING)


class CountingParser(FakeParser):
    def __init__(self) -> None:
        self.parsed: list[str] = []

    def parse(self, entry_text: str) -> ParsedReference:
        self.parsed.append(entry_text)
        return super().parse(entry_text)


class LibraryTestCase(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        for basename in (CITING, EARLIER, TRANSLATION, LATER, KANT):
            self.write_pdf(basename)
        self.write_note(TRANSLATION, TRANSLATION_FRONTMATTER)
        self.write_note(EARLIER, EARLIER_FRONTMATTER)
        self.write_note(KANT, KANT_FRONTMATTER)

    def links_for(self, parser: FakeParser | None = None) -> NoteLinks:
        return NoteLinks(CITING, CitationScoring(HeldWorks.from_library(), parser or FakeParser()))


class TestBibliographyLinks(LibraryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_note(CITING, CITING_FRONTMATTER, BIBLIOGRAPHY_BODY)
        self.links = self.links_for()

    def test_the_entry_naming_a_held_work_gains_its_wikilink(self) -> None:
        self.links.apply()
        self.assertIn(linked(ENTRY, EARLIER), self.note_text(CITING))

    def test_apply_reports_the_corpus_file_rewritten(self) -> None:
        self.assertEqual(STATUS_REWRITTEN, self.links.apply()["status"])

    def test_a_later_work_gains_no_link(self) -> None:
        self.links.apply()
        self.assertIn("\nDoe, Jane. *Later Work*. 2024.\n", self.note_text(CITING))

    def test_the_frontmatter_the_prose_and_the_footnotes_are_untouched(self) -> None:
        self.links.apply()
        text = self.note_text(CITING)
        self.assertTrue(text.startswith("---\ntitle: A Spirit of Trust\nyear: 2019\n---\n"))
        self.assertIn("# One\n\nProse.\n", text)
        self.assertTrue(text.endswith("[^1]: A note.\n"))

    def test_a_second_apply_finds_nothing_to_change(self) -> None:
        self.links.apply()
        self.assertEqual(STATUS_UNCHANGED, self.links.apply()["status"])

    def test_the_status_names_the_works_that_would_be_linked(self) -> None:
        self.assertEqual([EARLIER], self.links.status()["linked_works"])


class TestRepeatedAuthorEntries(LibraryTestCase):
    def test_an_entry_opening_with_a_dash_run_is_scored_under_the_author_above_it(self) -> None:
        self.write_note(CITING, CITING_FRONTMATTER, REPEATED_BODY)
        self.links_for().apply()
        self.assertIn(linked(REPEATED_ENTRY, EARLIER), self.note_text(CITING))

    def test_a_dash_run_with_no_author_above_it_gains_no_link(self) -> None:
        self.write_note(CITING, CITING_FRONTMATTER, ORPHAN_BODY)
        self.links_for().apply()
        self.assertIn(f"\n{REPEATED_ENTRY}\n", self.note_text(CITING))


class TestPunctuatedSurnameLinks(LibraryTestCase):
    def setUp(self) -> None:
        super().setUp()
        for basename, frontmatter in ((HYPHENATED, HYPHENATED_FRONTMATTER), (APOSTROPHE, APOSTROPHE_FRONTMATTER)):
            self.write_pdf(basename)
            self.write_note(basename, frontmatter)
        self.write_note(CITING, CITING_FRONTMATTER, PUNCTUATED_BODY)
        self.links_for().apply()

    def test_an_entry_naming_a_hyphenated_surname_gains_its_link(self) -> None:
        self.assertIn(linked(HYPHENATED_ENTRY, HYPHENATED), self.note_text(CITING))

    def test_an_entry_naming_a_surname_with_an_apostrophe_gains_its_link(self) -> None:
        self.assertIn(linked(APOSTROPHE_ENTRY, APOSTROPHE), self.note_text(CITING))


class TestEndnoteLinks(LibraryTestCase):
    def test_an_endnote_naming_a_held_work_gains_its_link(self) -> None:
        self.write_note(CITING, CITING_FRONTMATTER, ENDNOTES_BODY)
        self.links_for().apply()
        self.assertIn(linked(NOTE_ENTRY, EARLIER), self.note_text(CITING))

    def test_a_notes_chapter_headed_in_the_singular_is_a_link_surface(self) -> None:
        self.write_note(CITING, CITING_FRONTMATTER, SINGULAR_NOTES_BODY)
        self.links_for().apply()
        self.assertIn(linked(NOTE_ENTRY, EARLIER), self.note_text(CITING))


class TestStaleLinks(LibraryTestCase):
    def _stale(self, entry: str) -> list[tuple[str, str]]:
        body = f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n{linked(entry, EARLIER)}\n"
        self.write_note(CITING, CITING_FRONTMATTER, body)
        return [(item["entry"], item["basename"]) for item in self.links_for().status()["stale"]]

    def test_a_link_whose_entry_now_names_nothing_is_reported(self) -> None:
        stray = "Doe, Jane. An Unrelated Monograph. 1994."
        self.assertEqual([(stray, EARLIER)], self._stale(stray))

    def test_a_link_whose_entry_still_names_its_work_is_not_reported(self) -> None:
        self.assertEqual([], self._stale(ENTRY))


class TestFootnoteLinks(LibraryTestCase):
    def test_without_a_bibliography_the_footnote_naming_the_work_gains_the_link(self) -> None:
        self.write_note(CITING, CITING_FRONTMATTER, FOOTNOTE_BODY)
        self.links_for().apply()
        self.assertIn(f"[^1]: {linked('See Brandom, Making It Explicit, ch. 1.', EARLIER)}", self.note_text(CITING))

    def test_a_footnote_written_without_a_mark_still_gains_the_link(self) -> None:
        self.write_note(CITING, CITING_FRONTMATTER, UNMARKED_FOOTNOTE_BODY)
        self.links_for().apply()
        self.assertIn(linked(UNMARKED_NOTE, EARLIER), self.note_text(CITING))


class TestScoredLinks(LibraryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_note(CITING, CITING_FRONTMATTER, SCORED_BODY)
        self.links = self.links_for()

    def test_an_entry_whose_title_is_broken_by_a_hyphen_is_linked_when_its_score_is_automatic(self) -> None:
        self.links.apply()
        self.assertIn(linked(BROKEN_ENTRY, EARLIER), self.note_text(CITING))

    def test_an_entry_naming_the_author_only_in_its_title_is_reported_for_confirmation(self) -> None:
        self.assertEqual([{"entry": REVIEW_ENTRY, "basename": EARLIER, "score": AUTOMATIC_THRESHOLD - 1}],
                         self.links.status()["to_confirm"])

    def test_a_commentary_whose_title_mentions_the_held_work_is_not_linked_to_it(self) -> None:
        self.links.apply()
        self.assertIn(f"\n{COMMENTARY_ENTRY}\n", self.note_text(CITING))

    def test_a_commentary_whose_title_mentions_the_held_work_is_not_offered_for_confirmation(self) -> None:
        self.assertEqual([REVIEW_ENTRY], [row["entry"] for row in self.links.status()["to_confirm"]])

    def test_apply_leaves_a_middle_band_entry_unlinked(self) -> None:
        self.links.apply()
        self.assertIn(f"\n{REVIEW_ENTRY}\n", self.note_text(CITING))


class TestOnlyAnEntryNamingAHeldSurnameReachesTheParser(LibraryTestCase):
    UNHELD_ENTRY = "Doe, Jane. *Later Work*. 2024."

    def setUp(self) -> None:
        super().setUp()
        self.write_note(CITING, CITING_FRONTMATTER, BIBLIOGRAPHY_BODY)
        self.parser = CountingParser()
        self.links = self.links_for(self.parser)

    def test_an_entry_naming_no_citable_surname_is_never_parsed(self) -> None:
        self.links.status()
        self.assertNotIn(self.UNHELD_ENTRY, self.parser.parsed)

    def test_an_entry_naming_a_citable_surname_is_parsed(self) -> None:
        self.links.status()
        self.assertIn(ENTRY, self.parser.parsed)

    def test_the_unparsed_entry_gains_no_link(self) -> None:
        self.links.apply()
        self.assertIn(f"\n{self.UNHELD_ENTRY}\n", self.note_text(CITING))

    def test_the_entry_naming_a_citable_surname_still_gains_its_link(self) -> None:
        self.links.apply()
        self.assertIn(linked(ENTRY, EARLIER), self.note_text(CITING))


class TestApplyScoresEachEntryOnce(LibraryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_note(CITING, CITING_FRONTMATTER, BIBLIOGRAPHY_BODY)
        self.parser = CountingParser()

    def test_apply_parses_the_entry_it_links_once(self) -> None:
        self.links_for(self.parser).apply()
        self.assertEqual(1, self.parser.parsed.count(ENTRY))

    def test_a_rebuild_over_two_corpus_files_parses_each_entry_once(self) -> None:
        self.write_note(KANT, "title: Critique of Pure Reason\nyear: 1998\n", BIBLIOGRAPHY_BODY)
        LinksRebuild([CITING, KANT], self.parser).apply()
        self.assertEqual(2, self.parser.parsed.count(ENTRY))


class TestALinkedEntryIsRevisited(LibraryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_note(CITING, CITING_FRONTMATTER, BIBLIOGRAPHY_BODY)
        self.links_for().apply()
        self.parser = CountingParser()
        self.links = self.links_for(self.parser)

    def test_the_linked_entry_is_scored_again_by_its_alias_text(self) -> None:
        self.links.status()
        self.assertIn(ENTRY, self.parser.parsed)

    def test_an_entry_linked_to_its_best_match_is_left_as_it_is(self) -> None:
        self.assertEqual(STATUS_UNCHANGED, self.links.apply()["status"])
        self.assertEqual(1, self.note_text(CITING).count("[["))


class TestALinkedEntryWhoseBestMatchIsAnotherWork(LibraryTestCase):
    def setUp(self) -> None:
        super().setUp()
        body = BIBLIOGRAPHY_BODY.replace(ENTRY, linked(ENTRY, KANT))
        self.write_note(CITING, CITING_FRONTMATTER, body)
        self.links = self.links_for()

    def test_the_other_work_is_reported_for_confirmation(self) -> None:
        offered = [(row["entry"], row["basename"]) for row in self.links.status()["to_confirm"]]
        self.assertEqual([(ENTRY, EARLIER)], offered)

    def test_apply_never_overwrites_the_existing_link(self) -> None:
        self.assertEqual(STATUS_UNCHANGED, self.links.apply()["status"])
        self.assertIn(linked(ENTRY, KANT), self.note_text(CITING))


class TestAFormattedEntryKeepsItsTextOutsideTheLink(LibraryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_note(CITING, CITING_FRONTMATTER, BRACKETED_BODY)
        self.links = self.links_for()
        self.links.apply()

    def test_the_entry_text_stands_unchanged_before_the_link(self) -> None:
        self.assertIn(f"\n{linked(BRACKETED_ENTRY, EARLIER)}\n", self.note_text(CITING))

    def test_a_second_apply_reads_the_entry_back_and_changes_nothing(self) -> None:
        before = self.note_text(CITING)
        self.assertEqual(STATUS_UNCHANGED, self.links.apply()["status"])
        self.assertEqual(before, self.note_text(CITING))


class TestAHeldWorkWithoutACorpusFileIsNotLinked(LibraryTestCase):
    def setUp(self) -> None:
        super().setUp()
        (self.vault.corpus / f"{EARLIER}.md").unlink()
        self.write_note(CITING, CITING_FRONTMATTER, BIBLIOGRAPHY_BODY)
        self.links = self.links_for()

    def test_apply_leaves_the_entry_unlinked(self) -> None:
        self.assertEqual(STATUS_UNCHANGED, self.links.apply()["status"])
        self.assertIn(f"\n{ENTRY}\n", self.note_text(CITING))


class TestConflictCopies(LibraryTestCase):
    def test_a_conflict_copy_of_a_corpus_file_and_of_a_library_pdf_are_both_named(self) -> None:
        self.write_note(f"{CITING} (Someone's conflicted copy 2026-01-01)", "title: A Spirit of Trust\n")
        (self.vault.library / f"{EARLIER} 2.pdf").write_bytes(PDF_BYTES)
        self.assertEqual([f"{EARLIER} 2.pdf", f"{CITING} (Someone's conflicted copy 2026-01-01).md"],
                         ConflictCopies().names())

    def test_a_clean_vault_names_no_conflict_copy(self) -> None:
        self.assertEqual([], ConflictCopies().names())


class TestNoteWithoutBody(LibraryTestCase):
    def test_a_note_with_only_its_link_line_is_reported_without_a_body(self) -> None:
        self.write_note(CITING, CITING_FRONTMATTER)
        self.assertEqual(STATUS_NO_BODY, self.links_for().status()["status"])


if __name__ == "__main__":
    unittest.main()


class TestLinksIntoAWorkFromTheCorpusFilesNamingItsAuthor(LibraryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_note(CITING, CITING_FRONTMATTER, BIBLIOGRAPHY_BODY)
        self.write_note(LATER, "title: Later Work\nyear: 2024\n", f"{LINK_LINE}\n\n# One\n\nNo Brandom here.\n")

    def citing(self, cited: str = EARLIER) -> LinksRebuild:
        return LinksRebuild.citing(cited, FakeParser())

    def test_the_corpus_files_naming_the_works_author_gain_their_links(self) -> None:
        self.citing().apply()
        self.assertIn(linked(ENTRY, EARLIER), self.note_text(CITING))

    def test_the_rows_cover_the_citing_files_alone(self) -> None:
        basenames = [row["basename"] for row in self.citing().status()]
        self.assertEqual([CITING, LATER], basenames)

    def test_the_cited_work_itself_is_not_a_citing_file(self) -> None:
        self.assertNotIn(EARLIER, [row["basename"] for row in self.citing().status()])

    def test_a_work_no_corpus_file_names_covers_itself_alone(self) -> None:
        self.assertEqual([KANT], [row["basename"] for row in self.citing(KANT).status()])

    def test_a_basename_outside_the_library_is_refused(self) -> None:
        with self.assertRaises(LookupError):
            self.citing("Nobody - 1999 - Nothing")
