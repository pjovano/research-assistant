from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .glyphs import METHOD_WORKER, UNICODE_FIELD, Identity, IdentityTable, char_of_label, normalize_glyph
from .textkey import ENCODING

SHORTHAND_UNCHANGED = "="
UNRESOLVED = "unresolved"
RE_ENCODED_FAMILY_STEMS = ("times", "symbol", "arial", "helvetica", "palatino", "garamond", "minion", "cambria",
                           "courier")
TEX_FAMILY_PREFIXES = ("CM", "EU", "MSAM", "MSBM", "LASY", "rsfs", "LINE")
STYLE_SUFFIX_RE = re.compile(r"[.\-][A-Za-z]+$")
TRAILING_HEX_RUN_RE = re.compile(r"[0-9A-Fa-f]{6,}$")
MAX_UNRESOLVED_CODES = 30
REASON_FIELD = "reason"
REASON_TOO_MANY_CODES = f"the PDF carries more than {MAX_UNRESOLVED_CODES} unresolved codes"
REASON_RE_ENCODED = ("a code with no glyph name, in a family publishers re-encode per document, named as another "
                     "character")
REASON_OUTSIDE_SELF_ENCODED = "a code with no glyph name outside a TeX family or a subset-hashed family"


class LearnRefused(RuntimeError):
    pass


def literal_unicode(unicode: str, equals_sign: bool) -> str:
    if unicode == SHORTHAND_UNCHANGED and not equals_sign:
        raise LearnRefused('--unicode "=" is the glyph reader\'s shorthand for the character the text layer emits '
                           "today, which this command cannot see: learn the reader's answers with "
                           "`fonts learn-reader`, or pass --equals-sign if the glyph is an equals sign")
    return unicode


@dataclass(frozen=True)
class ReaderAnswer:
    pdf: str
    font: str
    glyph: str
    unicode: str

    def is_unresolved(self) -> bool:
        return self.unicode == UNRESOLVED

    def is_unchanged(self) -> bool:
        return self.unicode == SHORTHAND_UNCHANGED

    def is_in_family_re_encoded_per_document(self) -> bool:
        family = self.font.lower()
        return any(stem in family for stem in RE_ENCODED_FAMILY_STEMS)

    def is_in_family_fixing_its_own_encoding(self) -> bool:
        return self.font.startswith(TEX_FAMILY_PREFIXES) or self._carries_subset_hash()

    def _carries_subset_hash(self) -> bool:
        run = TRAILING_HEX_RUN_RE.search(STYLE_SUFFIX_RE.sub("", self.font))
        return run is not None and any(character.isdigit() for character in run.group())

    def row(self) -> dict:
        return {"pdf": self.pdf, "font": self.font, "glyph": self.glyph, "unicode": self.unicode}


class IdentifyReports:
    def __init__(self, paths: list[Path]) -> None:
        self._reports = {report["pdf"]: report["codes"]
                         for report in (json.loads(path.read_text(encoding=ENCODING)) for path in paths)}

    def only_pdf(self) -> str:
        if len(self._reports) != 1:
            raise LearnRefused("answers given as a plain list need exactly one --identify report")
        return next(iter(self._reports))

    def code_count(self, pdf: str) -> int:
        return len(self._codes_of(pdf))

    def current_character(self, answer: ReaderAnswer) -> str:
        return char_of_label(self._entry_of(answer)[UNICODE_FIELD])

    def names_no_glyph(self, answer: ReaderAnswer) -> bool:
        return not self._entry_of(answer)["glyph_name"]

    def glyph_name_of(self, answer: ReaderAnswer) -> str | None:
        return self._entry_of(answer)["glyph_name"] or None

    def code_of(self, answer: ReaderAnswer) -> str:
        return self._entry_of(answer)["code"]

    def _entry_of(self, answer: ReaderAnswer) -> dict:
        entry = next((code for code in self._codes_of(answer.pdf) if _names_glyph(code, answer)), None)
        if entry is None:
            raise LearnRefused(f"no identify entry for {answer.font} {answer.glyph} in {answer.pdf}")
        return entry

    def _codes_of(self, pdf: str) -> list[dict]:
        try:
            return self._reports[pdf]
        except KeyError as missing:
            raise LearnRefused(f"no --identify report for {pdf}") from missing


def _names_glyph(code: dict, answer: ReaderAnswer) -> bool:
    named = answer.glyph == code["glyph_name"] or normalize_glyph(answer.glyph) == normalize_glyph(code["code"])
    return code["font"] == answer.font and named


class ReaderAnswers:
    def __init__(self, answers_path: Path, reports: IdentifyReports) -> None:
        self._path = answers_path
        self._reports = reports

    def answers(self) -> list[ReaderAnswer]:
        return [ReaderAnswer(pdf, answer["font"], answer["glyph"], answer["unicode"])
                for pdf, listed in self._keyed_by_pdf().items() for answer in listed]

    def _keyed_by_pdf(self) -> dict[str, list[dict]]:
        payload = json.loads(self._path.read_text(encoding=ENCODING))
        return payload if isinstance(payload, dict) else {self._reports.only_pdf(): payload}


class ReaderLearning:
    def __init__(self, table: IdentityTable, answers: list[ReaderAnswer], reports: IdentifyReports) -> None:
        self._table = table
        self._answers = answers
        self._reports = reports

    def plan(self) -> dict:
        resolved = [answer for answer in self._answers if not answer.is_unresolved()]
        set_aside = {answer: reason for answer in resolved if (reason := self._reason_to_set_aside(answer))}
        no_repair = [answer for answer in resolved if answer not in set_aside and self._needs_no_repair(answer)]
        entries = [(answer, *self._entry_for(answer)) for answer in resolved
                   if answer not in set_aside and answer not in no_repair]
        disputed = _disputed_keys(entries)
        return {"learn": _unique([self._learn_row(key, entry) for _, key, entry in entries
                                  if self._is_new(key) and key not in disputed]),
                "conflicts": [self._conflict_row(answer, key) for answer, key, entry in entries
                              if self._conflicts(key, entry) or key in disputed],
                "unresolved": [answer.row() for answer in self._answers if answer.is_unresolved()],
                "set_aside": [{**answer.row(), REASON_FIELD: reason} for answer, reason in set_aside.items()],
                "needs_no_repair": [answer.row() for answer in no_repair]}

    def _reason_to_set_aside(self, answer: ReaderAnswer) -> str | None:
        if self._reports.code_count(answer.pdf) > MAX_UNRESOLVED_CODES:
            return REASON_TOO_MANY_CODES
        if not self._is_keyed_by_a_bare_code(answer) or answer.is_unchanged():
            return None
        if answer.is_in_family_re_encoded_per_document():
            return REASON_RE_ENCODED
        return REASON_OUTSIDE_SELF_ENCODED

    def _needs_no_repair(self, answer: ReaderAnswer) -> bool:
        return self._is_keyed_by_a_bare_code(answer) and answer.is_unchanged()

    def _is_keyed_by_a_bare_code(self, answer: ReaderAnswer) -> bool:
        return self._reports.names_no_glyph(answer) and not answer.is_in_family_fixing_its_own_encoding()

    def apply(self) -> None:
        for row in self.plan()["learn"]:
            self._table.write(row["key"], row["entry"])

    def _entry_for(self, answer: ReaderAnswer) -> tuple[str, dict]:
        identity = Identity(self._character_of(answer), METHOD_WORKER)
        glyph_name = self._reports.glyph_name_of(answer)
        if glyph_name is None:
            return self._table.entry_for_code(answer.font, self._reports.code_of(answer), identity)
        return self._table.entry_for(answer.font, glyph_name, identity)

    def _character_of(self, answer: ReaderAnswer) -> str:
        if answer.is_unchanged():
            return self._reports.current_character(answer)
        return answer.unicode

    def _is_new(self, key: str) -> bool:
        return self._table.existing(key) is None

    def _conflicts(self, key: str, entry: dict) -> bool:
        return self._table.conflicting(key, entry) is not None

    def _learn_row(self, key: str, entry: dict) -> dict:
        return {"key": key, "entry": entry}

    def _conflict_row(self, answer: ReaderAnswer, key: str) -> dict:
        return {**answer.row(), "key": key, "table": self._table.existing(key)}


def _disputed_keys(entries: list[tuple[ReaderAnswer, str, dict]]) -> set[str]:
    characters: dict[str, set[str]] = {}
    for _, key, entry in entries:
        characters.setdefault(key, set()).add(entry[UNICODE_FIELD])
    return {key for key, found in characters.items() if len(found) > 1}


def _unique(rows: list[dict]) -> list[dict]:
    return list({row["key"]: row for row in rows}.values())
