from __future__ import annotations

from references import CitationParser, CitedEntry, EditionIdentity, Locator, UnheldWork, WorksBySurname

from _graph.store import GraphStore, UnheldRow


class UnheldRegistry:
    def __init__(self, store: GraphStore, parser: CitationParser) -> None:
        self._store = store
        self._parser = parser
        self._works = WorksBySurname()
        for row in store.unheld_rows():
            self._works.add(row.unheld_id, self._work_of(row))

    def row_for(self, entry: CitedEntry) -> UnheldRow:
        identity = self._identity_of(entry.text)
        unheld_id = self._works.key_of(entry, identity)
        if unheld_id is None:
            return self._added(entry, identity)
        return self._known(unheld_id, entry)

    def _known(self, unheld_id: int, entry: CitedEntry) -> UnheldRow:
        self._works.work(unheld_id).add(entry)
        return UnheldRow(unheld_id, entry.text, entry.surnames, entry.year)

    def _added(self, entry: CitedEntry, identity: EditionIdentity) -> UnheldRow:
        row = self._store.add_unheld(entry.text, entry.surnames, entry.year)
        self._works.add(row.unheld_id, UnheldWork(entry, identity))
        return row

    def _work_of(self, row: UnheldRow) -> UnheldWork:
        first = CitedEntry(row.surnames, row.year, Locator("", None, None, row.text))
        return UnheldWork(first, self._identity_of(row.text))

    def _identity_of(self, text: str) -> EditionIdentity:
        return EditionIdentity.of(self._parser.parse(text))
