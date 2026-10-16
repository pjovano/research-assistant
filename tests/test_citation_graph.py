from __future__ import annotations

import os
import unittest

from _support import LiveTree

LiveTree.activate()

from references import CitationGraph
from _references_fixtures import LINK_LINE, VaultTestCase

HOULGATE = "Houlgate - 2006 - The Opening of Hegel's Logic"
STERN = "Stern - 2023 - Understanding Hegel's Logic"
BURBIDGE = "Burbidge - 1981 - On Hegel's Logic"
HOULGATE_BODY = (f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n%% p. 443 (file p. 464) %%\n\n"
                 f"[[{BURBIDGE}|Burbidge, John. On Hegel's Logic. 1981.]]\n\n%% p. 444 (file p. 465) %%\n\n"
                 f"[[{STERN}|Stern, Robert. Understanding Hegel's Logic. 2023.]]\n")
STERN_BODY = (f"{LINK_LINE}\n\n# One\n\nProse.[^1]\n\n%% p. 12 (file p. 3) %%\n\n"
              f"[^1]: [[{BURBIDGE}|Burbidge, On Hegel's Logic, p. 4.]]\n")
BURBIDGE_BODY = f"{LINK_LINE}\n\n# One\n\nProse with no reference list.\n"
COLLECTED = "Moyar - 2017 - The Oxford Handbook of Hegel"
COLLECTED_BODY = (f"{LINK_LINE}\n\n# One\n\nProse.[^1]\n\n%% p. 5 (file p. 6) %%\n\n"
                  f"[^1]: [[{STERN}|Stern, Understanding Hegel's Logic, p. 2.]]\n\n"
                  f"## References\n\n%% p. 20 (file p. 21) %%\n\n"
                  f"[[{BURBIDGE}|Burbidge, John. On Hegel's Logic. 1981.]]\n\n"
                  f"# Two\n\nProse.\n\n## References\n\n%% p. 40 (file p. 41) %%\n\n"
                  f"[[{HOULGATE}|Houlgate, Stephen. The Opening of Hegel's Logic. 2006.]]\n\n"
                  f"# Notes\n\n%% p. 60 (file p. 61) %%\n\n1. [[{STERN}|Stern, Understanding Hegel's Logic, p. 9.]]\n")


class CitationGraphTestCase(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_titled_note(HOULGATE, HOULGATE_BODY)
        self.write_titled_note(STERN, STERN_BODY)
        self.write_titled_note(BURBIDGE, BURBIDGE_BODY)
        self.graph = CitationGraph()

    def write_titled_note(self, basename: str, body: str) -> None:
        self.write_note(basename, f"title: {basename}\n", body)


class TestCites(CitationGraphTestCase):
    def test_the_bibliography_links_are_the_works_cited_with_their_folios(self) -> None:
        expected = [{"basename": BURBIDGE, "folio": "443", "file_page": 464},
                    {"basename": STERN, "folio": "444", "file_page": 465}]
        self.assertEqual({"basename": HOULGATE, "cites": expected}, self.graph.cites(HOULGATE))

    def test_a_footnote_link_is_an_edge(self) -> None:
        self.assertEqual([{"basename": BURBIDGE, "folio": "12", "file_page": 3}], self.graph.cites(STERN)["cites"])

    def test_a_work_with_no_links_cites_nothing(self) -> None:
        self.assertEqual([], self.graph.cites(BURBIDGE)["cites"])

    def test_a_basename_without_a_corpus_file_is_refused(self) -> None:
        with self.assertRaises(LookupError):
            self.graph.cites("Nobody - 1999 - Nothing")


class TestEdgesAreReReadWhenACorpusFileChanges(CitationGraphTestCase):
    def test_a_rewritten_corpus_file_no_longer_reports_the_link_it_lost(self) -> None:
        self.graph.cited_by(BURBIDGE)
        self.write_titled_note(STERN, BURBIDGE_BODY)
        self.assertEqual([HOULGATE], [edge["basename"] for edge in self.graph.cited_by(BURBIDGE)["cited_by"]])

    def test_a_corpus_file_written_after_the_first_call_is_read(self) -> None:
        self.graph.cited_by(HOULGATE)
        self.write_titled_note("Later - 2025 - A Late Work", f"{LINK_LINE}\n\n[^1]: [[{HOULGATE}|Houlgate, p. 1.]]\n")
        self.assertEqual(["Later - 2025 - A Late Work"],
                         [edge["basename"] for edge in self.graph.cited_by(HOULGATE)["cited_by"]])

    def test_a_corpus_file_of_unchanged_size_and_mtime_is_not_read_again(self) -> None:
        self.graph.cited_by(BURBIDGE)
        self.retarget_stern_without_touching_its_stamp()
        self.assertEqual([HOULGATE, STERN], [edge["basename"] for edge in self.graph.cited_by(BURBIDGE)["cited_by"]])

    def retarget_stern_without_touching_its_stamp(self) -> None:
        path = self.vault.corpus / f"{STERN}.md"
        stamp = path.stat()
        path.write_text(path.read_text(encoding="utf-8").replace(f"[[{BURBIDGE}|", f"[[{BURBIDGE[:-1]}x|"),
                        encoding="utf-8")
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))


class TestCitedBy(CitationGraphTestCase):
    def test_every_linking_line_is_an_edge_toward_the_citing_work(self) -> None:
        expected = [{"basename": HOULGATE, "folio": "443", "file_page": 464},
                    {"basename": STERN, "folio": "12", "file_page": 3}]
        self.assertEqual({"basename": BURBIDGE, "cited_by": expected}, self.graph.cited_by(BURBIDGE))

    def test_a_work_nobody_links_to_is_cited_by_nothing(self) -> None:
        self.assertEqual([], self.graph.cited_by(HOULGATE)["cited_by"])


class TestEveryEntryListOfACollectedVolumeIsRead(CitationGraphTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_titled_note(COLLECTED, COLLECTED_BODY)

    def test_the_footnote_and_every_reference_list_and_the_endnotes_are_edges_in_line_order(self) -> None:
        expected = [{"basename": STERN, "folio": "5", "file_page": 6},
                    {"basename": BURBIDGE, "folio": "20", "file_page": 21},
                    {"basename": HOULGATE, "folio": "40", "file_page": 41},
                    {"basename": STERN, "folio": "60", "file_page": 61}]
        self.assertEqual(expected, self.graph.cites(COLLECTED)["cites"])

    def test_a_work_linked_only_from_a_second_reference_list_is_cited_by_the_volume(self) -> None:
        expected = [{"basename": COLLECTED, "folio": "40", "file_page": 41}]
        self.assertEqual(expected, self.graph.cited_by(HOULGATE)["cited_by"])

    def test_a_work_linked_from_an_endnotes_list_is_cited_by_the_volume_at_the_endnotes_folio(self) -> None:
        folios = [edge["folio"] for edge in self.graph.cited_by(STERN)["cited_by"] if edge["basename"] == COLLECTED]
        self.assertIn("60", folios)


MATH_NOTE = "Hlobil - 2025 - Reasons for Logic"
MATH_BODY = (f"{LINK_LINE}\n\n# One\n\nProse.[^1]\n\n%% p. 7 (file p. 9) %%\n\n"
             f"[^1]: The clause ❲[[A ∧ B]] = x❳ is discussed in "
             f"[[{BURBIDGE}|Burbidge, On Hegel's Logic, p. 4.]]\n")


class TestMathIsNotALink(CitationGraphTestCase):
    def test_brackets_inside_a_math_span_are_not_an_edge(self) -> None:
        self.write_titled_note(MATH_NOTE, MATH_BODY)
        targets = [edge["basename"] for edge in CitationGraph().cites(MATH_NOTE)["cites"]]
        self.assertEqual([BURBIDGE], targets)


if __name__ == "__main__":
    unittest.main()
