from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from _vault.replacement import GuardedNote, NoteChangedOnDisk

_FM_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)

_PDF_LINK_RE = re.compile(
    r"\A\[[^\]]*\.pdf\]\(<?[^)]*>?\)[ \t]*\r?\n+", re.IGNORECASE)

_PDF_LINK_TARGET_RE = re.compile(r"\A\[[^\]]*\.pdf\]\(<?(?P<link>[^)>]*)>?\)", re.IGNORECASE)

_SOURCE_LINK_RE = re.compile(r"\A\[[^\]]*\]\(<?[^)]*>?\)[ \t]*\r?\n+")

_NOTE_PARTS_RE = re.compile(r"\A(---\n.*?\n---\n)(.*)\Z", re.DOTALL)
_YAML_LINE_WIDTH = 1000
_LINE_FEED = "\n"
_FRONTMATTER_FENCE = f"---{_LINE_FEED}"
_BYTE_ORDER_MARK = "﻿"
_ENCODING = "utf-8"
_STAGED_SUFFIX = ".staged"
EMPTY_SEQUENCE = "[]"
SEQUENCE_INDENT = "  "
_CONTINUATION_RE = re.compile(r"^\s|^- ")


class StoredNote:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._guarded = GuardedNote(path)
        self._was_read = False

    def read(self) -> tuple[dict, str]:
        parsed = parse_note(self._guarded.text())
        self._was_read = True
        return parsed

    def frontmatter(self) -> dict:
        meta, _body = self.read()
        return meta

    def write(self, meta: dict, body: str) -> None:
        self._guarded.replace(self._rendered(meta, body))

    def write_guarded(self, meta: dict, body: str) -> None:
        if self._was_read:
            self.write(meta, body)
        else:
            self._create(meta, body)

    def _create(self, meta: dict, body: str) -> None:
        AbsentNote(self._path).create(self._rendered(meta, body))
        self.read()

    def _rendered(self, meta: dict, body: str) -> str:
        return f"---\n{self._rendered_header(meta)}\n---\n\n{_to_lf(body).strip()}\n"

    @staticmethod
    def _rendered_header(meta: dict) -> str:
        dumped = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=_YAML_LINE_WIDTH)
        return _to_lf(dumped).strip()


class FrontmatterFields:
    def upserted(self, block: str, fields: dict) -> str:
        lines = block.rstrip("\n").split("\n")
        closing = lines[-1]
        kept = self._without(lines[:-1], fields)
        added = [line for key, value in fields.items() for line in _FieldLines(key, value).all()]
        return "\n".join(kept + added + [closing]) + "\n"

    def replaced_in_place(self, block: str, fields: dict) -> str:
        lines = block.rstrip("\n").split("\n")
        written = self._rewritten(lines[:-1], fields)
        absent = [key for key in fields if not any(self._names(line, key) for line in lines)]
        added = [line for key in absent for line in _FieldLines(key, fields[key]).all()]
        return "\n".join(written + added + [lines[-1]]) + "\n"

    def _rewritten(self, lines: list[str], fields: dict) -> list[str]:
        written: list[str] = []
        replacing = False
        for line in lines:
            key = next((key for key in fields if self._names(line, key)), None)
            continues = replacing and _CONTINUATION_RE.match(line) is not None
            if key is not None:
                written += _FieldLines(key, fields[key]).all()
            elif not continues:
                written.append(line)
            replacing = key is not None or continues
        return written

    def _without(self, lines: list[str], fields: dict) -> list[str]:
        kept: list[str] = []
        removing = False
        for line in lines:
            removing = self._names_any(line, fields) or (removing and _CONTINUATION_RE.match(line) is not None)
            if not removing:
                kept.append(line)
        return kept

    def _names_any(self, line: str, fields: dict) -> bool:
        return any(self._names(line, key) for key in fields)

    @staticmethod
    def _names(line: str, key: str) -> bool:
        return re.match(rf"^{re.escape(key)}:(\s|$)", line) is not None


class _FieldLines:
    def __init__(self, key: str, value: object) -> None:
        self._key = key
        self._value = value

    def all(self) -> list[str]:
        if self._value is None:
            return []
        if isinstance(self._value, list):
            return self._sequence(self._value)
        return [f"{self._key}: {self._value}"]

    def _sequence(self, items: list) -> list[str]:
        if not items:
            return [f"{self._key}: {EMPTY_SEQUENCE}"]
        return [f"{self._key}:"] + [f"{SEQUENCE_INDENT}- {item}" for item in items]


class AbsentNote:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._staged = path.with_name(path.name + _STAGED_SUFFIX)

    def create(self, text: str) -> None:
        self._staged.write_bytes(text.encode(_ENCODING))
        try:
            os.link(self._staged, self._path)
        except FileExistsError as error:
            raise NoteChangedOnDisk(self._path, "appeared on disk after it was found absent; nothing was written. "
                                                "Run the command again so it reads the current file.") from error
        finally:
            self._staged.unlink(missing_ok=True)


class NoteHeader:
    def __init__(self, path: Path) -> None:
        self._path = path

    def frontmatter(self) -> dict:
        with self._path.open(encoding=_ENCODING) as note:
            header = self._header_lines(note)
        return yaml.safe_load("".join(header)) or {} if header is not None else {}

    @staticmethod
    def _header_lines(note) -> list[str] | None:
        if note.readline().removeprefix(_BYTE_ORDER_MARK) != _FRONTMATTER_FENCE:
            return None
        header: list[str] = []
        for line in note:
            if line == _FRONTMATTER_FENCE:
                return header
            header.append(line)
        return None


def read_frontmatter(path: Path) -> tuple[dict, str]:
    return StoredNote(path).read()


def read_frontmatter_only(path: Path) -> dict:
    return NoteHeader(path).frontmatter()


def write_frontmatter(path: Path, meta: dict, body: str) -> None:
    StoredNote(path).write(meta, body)


def parse_note(text: str) -> tuple[dict, str]:
    unmarked = _to_lf(text).removeprefix(_BYTE_ORDER_MARK)
    match = _FM_RE.match(unmarked)
    if not match:
        return {}, unmarked
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def _to_lf(text: str) -> str:
    return text.replace("\r\n", _LINE_FEED).replace("\r", _LINE_FEED)


def split_note(text: str) -> tuple[str, str]:
    unmarked = _to_lf(text).removeprefix(_BYTE_ORDER_MARK)
    match = _NOTE_PARTS_RE.match(unmarked)
    if not match:
        return "", unmarked
    return match.group(1), match.group(2)


def join_note(frontmatter_block: str, body: str) -> str:
    return f"{frontmatter_block.rstrip(_LINE_FEED)}\n\n{_to_lf(body).strip()}\n"


def upsert_pdf_link(body: str, basename: str, link: str | None) -> str:
    unlinked = body_after_pdf_link(body)
    if not link:
        return unlinked
    return f"[{basename}.pdf]({_href(link)})\n\n{unlinked}"


def pdf_link_of(body: str) -> str | None:
    match = _PDF_LINK_TARGET_RE.match(body.lstrip())
    return match.group("link") if match else None


def body_after_pdf_link(body: str) -> str:
    return _PDF_LINK_RE.sub("", body.lstrip())


def body_after_source_link(body: str) -> str:
    return _SOURCE_LINK_RE.sub("", body.lstrip())


def _href(link: str) -> str:
    return f"<{link}>" if " " in link else link
