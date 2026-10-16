from __future__ import annotations

import json
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path

import vault

GRAPH_STORE_FILENAME = "citation-graph.sqlite"
HELD_KEY_PREFIX = "held:"
UNHELD_KEY_PREFIX = "unheld:"

_FLOAT_FORMAT = "f"
_FLOAT_BYTES = struct.calcsize(_FLOAT_FORMAT)

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS notes (basename TEXT PRIMARY KEY, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS citations (citing TEXT NOT NULL, cited TEXT NOT NULL, folio TEXT, file_page INTEGER, "
    "text TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS citations_citing ON citations (citing)",
    "CREATE INDEX IF NOT EXISTS citations_cited ON citations (cited)",
    "CREATE TABLE IF NOT EXISTS unheld (id INTEGER PRIMARY KEY, text TEXT NOT NULL, surnames TEXT NOT NULL, year TEXT)",
    "CREATE TABLE IF NOT EXISTS centroids (basename TEXT PRIMARY KEY, vector BLOB NOT NULL)",
)

_INSERT_CITATION = "INSERT INTO citations (citing, cited, folio, file_page, text) VALUES (?, ?, ?, ?, ?)"


def held_key(basename: str) -> str:
    return f"{HELD_KEY_PREFIX}{basename}"


def unheld_key(unheld_id: int) -> str:
    return f"{UNHELD_KEY_PREFIX}{unheld_id}"


@dataclass(frozen=True)
class CitationRow:
    citing: str
    cited: str
    folio: str | None
    file_page: int | None
    text: str

    @property
    def cites_held(self) -> bool:
        return self.cited.startswith(HELD_KEY_PREFIX)

    @property
    def cited_basename(self) -> str:
        return self.cited[len(HELD_KEY_PREFIX):]


@dataclass(frozen=True)
class UnheldRow:
    unheld_id: int
    text: str
    surnames: tuple[str, ...]
    year: str | None

    @property
    def key(self) -> str:
        return unheld_key(self.unheld_id)


class GraphStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or vault.RAG_DIR / GRAPH_STORE_FILENAME
        self._connection: sqlite3.Connection | None = None

    def stamps(self) -> dict[str, tuple[int, int]]:
        rows = self._open().execute("SELECT basename, size, mtime_ns FROM notes").fetchall()
        return {basename: (size, mtime_ns) for basename, size, mtime_ns in rows}

    def replace_note(self, basename: str, stamp: tuple[int, int], rows: list[CitationRow]) -> None:
        with self._open() as connection:
            connection.execute("DELETE FROM citations WHERE citing = ?", (basename,))
            connection.executemany(_INSERT_CITATION,
                                   [(row.citing, row.cited, row.folio, row.file_page, row.text) for row in rows])
            connection.execute("INSERT OR REPLACE INTO notes (basename, size, mtime_ns) VALUES (?, ?, ?)",
                               (basename, *stamp))

    def forget_note(self, basename: str) -> None:
        with self._open() as connection:
            connection.execute("DELETE FROM citations WHERE citing = ?", (basename,))
            connection.execute("DELETE FROM notes WHERE basename = ?", (basename,))
            connection.execute("DELETE FROM centroids WHERE basename = ?", (basename,))

    def citations(self) -> list[CitationRow]:
        rows = self._open().execute("SELECT citing, cited, folio, file_page, text FROM citations").fetchall()
        return [CitationRow(*row) for row in rows]

    def unheld_rows(self) -> list[UnheldRow]:
        rows = self._open().execute("SELECT id, text, surnames, year FROM unheld").fetchall()
        return [UnheldRow(unheld_id, text, tuple(json.loads(surnames)), year)
                for unheld_id, text, surnames, year in rows]

    def add_unheld(self, text: str, surnames: tuple[str, ...], year: str | None) -> UnheldRow:
        with self._open() as connection:
            cursor = connection.execute("INSERT INTO unheld (text, surnames, year) VALUES (?, ?, ?)",
                                        (text, json.dumps(list(surnames)), year))
        return UnheldRow(cursor.lastrowid, text, surnames, year)

    def set_centroid(self, basename: str, vector: list[float] | None) -> None:
        with self._open() as connection:
            connection.execute("DELETE FROM centroids WHERE basename = ?", (basename,))
            if vector:
                connection.execute("INSERT INTO centroids (basename, vector) VALUES (?, ?)",
                                   (basename, struct.pack(f"{len(vector)}{_FLOAT_FORMAT}", *vector)))

    def centroids(self) -> dict[str, list[float]]:
        rows = self._open().execute("SELECT basename, vector FROM centroids").fetchall()
        return {basename: self._unpacked(blob) for basename, blob in rows}

    def clear(self) -> None:
        self.close()
        if self._path.exists():
            self._path.unlink()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @staticmethod
    def _unpacked(blob: bytes) -> list[float]:
        return list(struct.unpack(f"{len(blob) // _FLOAT_BYTES}{_FLOAT_FORMAT}", blob))

    def _open(self) -> sqlite3.Connection:
        if self._connection is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self._path)
            for statement in _SCHEMA:
                self._connection.execute(statement)
        return self._connection
