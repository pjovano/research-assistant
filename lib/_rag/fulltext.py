from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import vault as vault_lib

from .chunking import HEADING_PATH_KEY, Child, ChunkedDocument, Parent
from .documents import UNSTAMPED, FileStamp

FULLTEXT_FILENAME = "fulltext.sqlite"
FTS_TOKENIZER = "unicode61 remove_diacritics 0"
SCHEMA_VERSION = 2
CONTEXT_WEIGHT = 0.25
EMPTY_STORE = ":memory:"
PARENTS_TABLE = "parents"
CHILDREN_TABLE = "children"
MANIFEST_TABLE = "manifest"
CHUNK_ID_COLUMN = "chunk_id"
PARENT_ID_COLUMN = "parent_id"
BASENAME_COLUMN = "basename"
CHUNK_ID = CHUNK_ID_COLUMN
PARENT_ID = PARENT_ID_COLUMN
BASENAME = BASENAME_COLUMN
TEXT = "text"
CONTEXT = "context"
METADATA = "metadata"
HEADING_PATH = HEADING_PATH_KEY
_QUERY_TERM_RE = re.compile(r"[^\W_]+", re.UNICODE)
_ANY_TERM = " OR "
_PLACEHOLDER_JOIN = ", "

_CHILDREN_FTS = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS children_fts
    USING fts5(text, context, content='children', content_rowid='rowid', tokenize='{FTS_TOKENIZER}');
"""
_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS parents(
    parent_id TEXT PRIMARY KEY, basename TEXT NOT NULL, text TEXT NOT NULL, metadata TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS children(
    chunk_id TEXT PRIMARY KEY, parent_id TEXT NOT NULL, basename TEXT NOT NULL,
    text TEXT NOT NULL, context TEXT NOT NULL, metadata TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS parents_by_basename ON parents(basename);
CREATE INDEX IF NOT EXISTS children_by_basename ON children(basename);
{_CHILDREN_FTS}
CREATE TABLE IF NOT EXISTS manifest(
    basename TEXT PRIMARY KEY, chunk_ids TEXT NOT NULL, document_hash TEXT NOT NULL,
    embedding_model TEXT NOT NULL DEFAULT '',
    size INTEGER NOT NULL DEFAULT {UNSTAMPED}, mtime_ns INTEGER NOT NULL DEFAULT {UNSTAMPED});
"""
_UPGRADES = {
    1: f"""
ALTER TABLE children ADD COLUMN context TEXT NOT NULL DEFAULT '';
DROP TABLE children_fts;
{_CHILDREN_FTS}
INSERT INTO children_fts(children_fts) VALUES ('rebuild');
""",
    2: f"""
ALTER TABLE manifest ADD COLUMN embedding_model TEXT NOT NULL DEFAULT '';
ALTER TABLE manifest ADD COLUMN size INTEGER NOT NULL DEFAULT {UNSTAMPED};
ALTER TABLE manifest ADD COLUMN mtime_ns INTEGER NOT NULL DEFAULT {UNSTAMPED};
""",
}
_UNINDEX_CHILDREN = ("INSERT INTO children_fts(children_fts, rowid, text, context) "
                     f"SELECT 'delete', rowid, text, context FROM {CHILDREN_TABLE} WHERE {BASENAME_COLUMN} = ?")
_INDEX_CHILDREN = ("INSERT INTO children_fts(rowid, text, context) "
                   f"SELECT rowid, text, context FROM {CHILDREN_TABLE} WHERE {BASENAME_COLUMN} = ?")
_UNINDEX_ALL = "INSERT INTO children_fts(children_fts) VALUES ('delete-all')"
_INSERT_PARENT = f"INSERT INTO {PARENTS_TABLE}(parent_id, basename, text, metadata) VALUES (?, ?, ?, ?)"
_INSERT_CHILD = (f"INSERT INTO {CHILDREN_TABLE}(chunk_id, parent_id, basename, text, context, metadata) "
                 "VALUES (?, ?, ?, ?, ?, ?)")
_INSERT_MANIFEST = (f"INSERT INTO {MANIFEST_TABLE}"
                    "(basename, chunk_ids, document_hash, embedding_model, size, mtime_ns) VALUES (?, ?, ?, ?, ?, ?)")
_RESTAMP_MANIFEST = f"UPDATE {MANIFEST_TABLE} SET embedding_model = ?, size = ?, mtime_ns = ? WHERE basename = ?"
_MANIFEST_COLUMNS = f"SELECT basename, chunk_ids, document_hash, embedding_model, size, mtime_ns FROM {MANIFEST_TABLE}"
_MANIFEST_ROWS = f"{_MANIFEST_COLUMNS} ORDER BY {BASENAME_COLUMN}"
_MANIFEST_ROW = f"{_MANIFEST_COLUMNS} WHERE {BASENAME_COLUMN} = ?"
_BM25 = (f"SELECT children.chunk_id, bm25(children_fts, 1.0, {CONTEXT_WEIGHT}) AS rank FROM children_fts "
         "JOIN children ON children.rowid = children_fts.rowid "
         "WHERE children_fts MATCH ? ORDER BY rank LIMIT ?")
_CHILD_IDS = f"SELECT {CHUNK_ID_COLUMN} FROM {CHILDREN_TABLE}"
_ROW_COUNT_COLUMN = "row_count"
_COUNT_ROWS = f"SELECT count(*) AS {_ROW_COUNT_COLUMN} FROM {{table}}"
_ROWS_IN = "SELECT * FROM {table} WHERE {column} IN ({placeholders})"
_DELETE_ROWS = "DELETE FROM {table}"
_DELETE_DOCUMENT_ROWS = f"DELETE FROM {{table}} WHERE {BASENAME_COLUMN} = ?"
_ROW_TABLES = (PARENTS_TABLE, CHILDREN_TABLE, MANIFEST_TABLE)
_CHUNK_TABLES = (PARENTS_TABLE, CHILDREN_TABLE)


def fts_query(text: str) -> str:
    return _ANY_TERM.join(f'"{term}"' for term in _QUERY_TERM_RE.findall(text))


@dataclass(frozen=True)
class ManifestRecord:
    document_hash: str
    embedding_model: str
    stamp: FileStamp

    @staticmethod
    def unstamped(document_hash: str) -> "ManifestRecord":
        return ManifestRecord(document_hash, "", FileStamp.unstamped())

    def is_stamped(self, stamp: FileStamp, prefix: str) -> bool:
        return self.stamp == stamp and self.document_hash.startswith(prefix)


@dataclass(frozen=True)
class ManifestRow:
    basename: str
    chunk_ids: list[str]
    record: ManifestRecord

    @staticmethod
    def of(row: sqlite3.Row) -> "ManifestRow":
        stamp = FileStamp(row["size"], row["mtime_ns"])
        record = ManifestRecord(row["document_hash"], row["embedding_model"], stamp)
        return ManifestRow(row[BASENAME_COLUMN], json.loads(row["chunk_ids"]), record)


class FullTextStore:
    def __init__(self, directory: Path | None = None) -> None:
        self._path = (directory or vault_lib.RAG_DIR) / FULLTEXT_FILENAME
        self._connection: sqlite3.Connection | None = None
        self._empty_connection: sqlite3.Connection | None = None

    def present(self) -> bool:
        return self._path.exists()

    def manifest_row(self, basename: str) -> ManifestRow | None:
        row = self._one(_MANIFEST_ROW, basename)
        return None if row is None else ManifestRow.of(row)

    def manifest_rows(self) -> list[ManifestRow]:
        return [ManifestRow.of(row) for row in self._reader().execute(_MANIFEST_ROWS)]

    def document_hash(self, basename: str) -> str | None:
        row = self.manifest_row(basename)
        return None if row is None else row.record.document_hash

    def chunk_ids_of(self, basename: str) -> list[str]:
        row = self.manifest_row(basename)
        return [] if row is None else row.chunk_ids

    def manifest_basenames(self) -> list[str]:
        return [row.basename for row in self.manifest_rows()]

    def manifest_chunk_ids(self) -> set[str]:
        return {chunk_id for row in self.manifest_rows() for chunk_id in row.chunk_ids}

    def child_ids(self) -> set[str]:
        return {row[CHUNK_ID_COLUMN] for row in self._reader().execute(_CHILD_IDS)}

    def counts(self) -> dict[str, int]:
        return {table: self._one(_COUNT_ROWS.format(table=table))[_ROW_COUNT_COLUMN] for table in _ROW_TABLES}

    def replace_document(self, basename: str, chunked: ChunkedDocument, record: ManifestRecord) -> None:
        with self._writer() as db:
            self._delete_rows(db, basename)
            db.executemany(_INSERT_PARENT, [_parent_row(parent) for parent in chunked.parents])
            db.executemany(_INSERT_CHILD, [_child_row(child) for child in chunked.children])
            db.execute(_INDEX_CHILDREN, (basename,))
            db.execute(_INSERT_MANIFEST, _manifest_row(basename, chunked.chunk_ids, record))

    def restamp_document(self, basename: str, record: ManifestRecord) -> None:
        with self._writer() as db:
            db.execute(_RESTAMP_MANIFEST, (record.embedding_model, record.stamp.size, record.stamp.mtime_ns, basename))

    def remove_document(self, basename: str) -> None:
        with self._writer() as db:
            self._delete_rows(db, basename)

    def clear(self) -> None:
        with self._writer() as db:
            db.execute(_UNINDEX_ALL)
            for table in _ROW_TABLES:
                db.execute(_DELETE_ROWS.format(table=table))

    def bm25_ranked(self, query: str, limit: int) -> list[str]:
        match = fts_query(query)
        if not match:
            return []
        return [row[CHUNK_ID_COLUMN] for row in self._reader().execute(_BM25, (match, limit))]

    def children(self, chunk_ids: list[str]) -> list[dict]:
        return self._rows(CHILDREN_TABLE, CHUNK_ID_COLUMN, chunk_ids)

    def children_by_id(self, chunk_ids: list[str]) -> dict[str, dict]:
        return {child[CHUNK_ID]: child for child in self.children(chunk_ids)}

    def parents(self, parent_ids: list[str]) -> list[dict]:
        return self._rows(PARENTS_TABLE, PARENT_ID_COLUMN, parent_ids)

    def stored_of(self, basename: str) -> dict[str, list[dict]]:
        return {table: self._rows(table, BASENAME_COLUMN, [basename]) for table in _CHUNK_TABLES}

    def _rows(self, table: str, column: str, values: list[str]) -> list[dict]:
        if not values:
            return []
        placeholders = _PLACEHOLDER_JOIN.join("?" * len(values))
        statement = _ROWS_IN.format(table=table, column=column, placeholders=placeholders)
        return [_with_parsed_metadata(row) for row in self._reader().execute(statement, values)]

    def _one(self, sql: str, *parameters: str) -> sqlite3.Row | None:
        return self._reader().execute(sql, parameters).fetchone()

    @staticmethod
    def _delete_rows(db: sqlite3.Connection, basename: str) -> None:
        db.execute(_UNINDEX_CHILDREN, (basename,))
        for table in _ROW_TABLES:
            db.execute(_DELETE_DOCUMENT_ROWS.format(table=table), (basename,))

    def _reader(self) -> sqlite3.Connection:
        if self._connection is not None or self.present():
            return self._writer()
        return self._empty()

    def _empty(self) -> sqlite3.Connection:
        if self._empty_connection is None:
            self._empty_connection = _opened(EMPTY_STORE)
        return self._empty_connection

    def _writer(self) -> sqlite3.Connection:
        if self._connection is None:
            self._open_store()
        return self._connection

    def _open_store(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = _opened(str(self._path))


def _opened(location: str) -> sqlite3.Connection:
    connection = sqlite3.connect(location)
    connection.row_factory = sqlite3.Row
    _StoreSchema(connection).ensure()
    return connection


class _StoreSchema:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def ensure(self) -> None:
        if self._is_empty():
            self._create()
        else:
            self._upgrade()

    def _is_empty(self) -> bool:
        return self._connection.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] == 0

    def _create(self) -> None:
        self._connection.executescript(_SCHEMA)
        self._stamp(SCHEMA_VERSION)

    def _upgrade(self) -> None:
        for version in range(self._version() + 1, SCHEMA_VERSION + 1):
            self._connection.executescript(_UPGRADES[version])
            self._stamp(version)

    def _version(self) -> int:
        return self._connection.execute("PRAGMA user_version").fetchone()[0]

    def _stamp(self, version: int) -> None:
        self._connection.execute(f"PRAGMA user_version = {version}")


def _manifest_row(basename: str, chunk_ids: list[str], record: ManifestRecord) -> tuple:
    return (basename, json.dumps(chunk_ids), record.document_hash,
            record.embedding_model, record.stamp.size, record.stamp.mtime_ns)


def _parent_row(parent: Parent) -> tuple:
    return parent.parent_id, parent.basename, parent.text, _dumped(parent.metadata)


def _child_row(child: Child) -> tuple:
    return child.chunk_id, child.parent_id, child.basename, child.text, child.context, _dumped(child.metadata)


def _dumped(metadata: dict) -> str:
    return json.dumps(metadata, ensure_ascii=False)


def _with_parsed_metadata(row: sqlite3.Row) -> dict:
    record = dict(row)
    record[METADATA] = json.loads(record[METADATA])
    return record
