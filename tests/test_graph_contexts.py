from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import vault
from citation_graph import KIND_AUTHOR_DATE, KIND_FOOTNOTE, KIND_MENTION, CitationContexts
from references import WorkFactory
from _references_fixtures import LINK_LINE, VaultTestCase

KANT = "Kant - 1998 - Critique of Pure Reason"
ALLISON = "Allison - 2004 - Kant's Transcendental Idealism"
HEIDEGGER = "Heidegger - 1929 - Kant und das Problem der Metaphysik"
KANT_FRONTMATTER = ("title: Critique of Pure Reason\nauthor:\n- Kant\nyear: 1998\norig_year: 1781\n"
                    "aliases:\n- Kritik der reinen Vernunft\n")
ALLISON_BODY = (f"{LINK_LINE}\n\n# One\n\n%% p. 3 (file p. 12) %%\n\n"
                "The Deduction opens the question.[^1] Later readers disagree.[^2]\n\n"
                "Kant (1781) calls this the highest point; see also Kant 1998, p. 130.\n\n"
                "A sentence naming nothing.\n\n"
                f"[^1]: [[{KANT}|Kant, Critique of Pure Reason, A 84.]]\n\n"
                "[^2]: Strawson, The Bounds of Sense, p. 86.\n\n"
                f"## References\n\n%% p. 400 (file p. 409) %%\n\n"
                f"[[{KANT}|Kant, Immanuel. Critique of Pure Reason. 1998.]]\n")
HEIDEGGER_BODY = (f"{LINK_LINE}\n\n# Eins\n\n%% p. 1 (file p. 9) %%\n\n"
                  "Kants Kritik der reinen Vernunft wird hier als Grundlegung der Metaphysik gelesen.\n\n"
                  "Die reine Vernunft allein, ohne Namen, sagt nichts.\n")


class ContextsTestCase(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_note(KANT, KANT_FRONTMATTER)
        self.write_note(ALLISON, "title: Kant's Transcendental Idealism\nauthor:\n- Allison\nyear: 2004\n",
                        ALLISON_BODY)
        self.write_note(HEIDEGGER, "title: Kant und das Problem der Metaphysik\nauthor:\n- Heidegger\nyear: 1929\n",
                        HEIDEGGER_BODY)

    def passages(self, citing: str) -> list[dict]:
        factory = WorkFactory()
        _frontmatter, body = vault.read_frontmatter(vault.corpus_path(citing))
        contexts = CitationContexts(factory.of(vault.corpus_path(citing)), factory.of(vault.corpus_path(KANT)), body)
        return contexts.passages()

    def of_kind(self, citing: str, kind: str) -> list[dict]:
        return [passage for passage in self.passages(citing) if passage["kind"] == kind]


class TestFootnoteCallSites(ContextsTestCase):
    def test_the_sentence_calling_a_linked_footnote_is_a_passage_with_its_folio(self) -> None:
        found = self.of_kind(ALLISON, KIND_FOOTNOTE)
        self.assertEqual(1, len(found))
        self.assertEqual(("3", 12), (found[0]["folio"], found[0]["file_page"]))
        self.assertIn("The Deduction opens the question.", found[0]["text"])

    def test_a_footnote_linking_another_work_contributes_no_passage(self) -> None:
        self.assertNotIn("Strawson", " ".join(passage["text"] for passage in self.passages(ALLISON)))


class TestAuthorDateCitations(ContextsTestCase):
    def test_a_surname_followed_by_one_of_the_works_years_is_a_passage(self) -> None:
        found = self.of_kind(ALLISON, KIND_AUTHOR_DATE)
        self.assertEqual(1, len(found))
        self.assertIn("Kant (1781)", found[0]["text"])

    def test_a_reference_list_entry_is_not_a_passage(self) -> None:
        self.assertNotIn("Kant, Immanuel.", " ".join(passage["text"] for passage in self.passages(ALLISON)))


class TestTitleMentions(ContextsTestCase):
    def test_a_genitive_surname_beside_the_works_title_is_a_mention(self) -> None:
        found = self.of_kind(HEIDEGGER, KIND_MENTION)
        self.assertEqual(1, len(found))
        self.assertTrue(found[0]["text"].startswith("Kants Kritik der reinen Vernunft"))

    def test_the_title_words_without_the_surname_are_no_mention(self) -> None:
        self.assertNotIn("ohne Namen", " ".join(passage["text"] for passage in self.passages(HEIDEGGER)))


class TestPassagesInOrder(ContextsTestCase):
    def test_passages_come_in_the_order_of_the_body(self) -> None:
        kinds = [passage["kind"] for passage in self.passages(ALLISON)]
        self.assertEqual([KIND_FOOTNOTE, KIND_AUTHOR_DATE], kinds)

    def test_a_pair_without_corpus_files_is_refused(self) -> None:
        with self.assertRaises(LookupError):
            CitationContexts.between(ALLISON, "Nobody - 1999 - Nothing")


if __name__ == "__main__":
    unittest.main()
