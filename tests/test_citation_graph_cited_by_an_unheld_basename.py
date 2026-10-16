from __future__ import annotations

import importlib.util
import sys
import unittest

from _support import SKILLS_DIR, LiveTree

LiveTree.activate()

from references import CitationGraph
from _references_fixtures import LINK_LINE, VaultTestCase

UNHELD = "Nobody - 1999 - Nothing"
HELD = "Holder - 2001 - A Held Work"
CITING = "Citer - 2010 - A Citing Work"
CITING_BODY = f"{LINK_LINE}\n\n# Bibliography\n\n%% p. 9 (file p. 10) %%\n\n[[{UNHELD}|Nobody. Nothing. 1999.]]\n"
SERVER_PATH = SKILLS_DIR / "search" / "server.py"


class SearchServer:
    @staticmethod
    def over(graph: CitationGraph):
        spec = importlib.util.spec_from_file_location("entry_search_server", SERVER_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        server = module.VaultRagServer.__new__(module.VaultRagServer)
        server._graph = graph
        return server


class TestCitedByAnUnheldBasename(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_note(HELD, "title: held\n")
        self.write_note(CITING, "title: citing\n", CITING_BODY)
        self.graph = CitationGraph()

    def test_an_unheld_basename_is_refused_even_when_a_note_links_to_it(self) -> None:
        with self.assertRaises(LookupError):
            self.graph.cited_by(UNHELD)

    def test_a_held_basename_nobody_links_to_is_cited_by_nothing(self) -> None:
        self.assertEqual([], self.graph.cited_by(HELD)["cited_by"])

    def test_the_search_server_reports_an_unheld_basename_as_an_error(self) -> None:
        self.assertIn("error", SearchServer.over(self.graph).cited_by(UNHELD))

    def test_the_search_server_reports_an_unheld_basename_as_cites_does(self) -> None:
        server = SearchServer.over(self.graph)
        self.assertEqual(set(server.cites(UNHELD)), set(server.cited_by(UNHELD)))


if __name__ == "__main__":
    unittest.main()
