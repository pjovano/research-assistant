from __future__ import annotations

import dataclasses
import itertools
import re
from collections.abc import Iterator
from dataclasses import dataclass

from _extract.carriednotes import CarriedNote, OpenMarks, UnansweredMarks
from _extract.formulamarks import FormulaMarks
from _extract.notemarks import (
    KEYED_NOTE_OPENING_RE, RAISED_KEY_RE, RAISED_RUN_RE as MARK_RE, SPACED_WRITTEN_MARK_RE as _MARK_RE, note_key,
    raised_mark, written_mark,
)
from _extract.notenumbers import MARKDOWN_NOTE_OPENING_RE as _LEADING_NUMBER_RE, NOTE_SYMBOLS
from _extract.sentences import closes_a_sentence
from _extract.superscriptmarks import SuperscriptMarks

_MARK_SEPARATOR_RE = re.compile(r"\s*,\s*")
_PRINTED_NUMERAL_TEMPLATE = "{number}. "
_PRINTED_SYMBOL_TEMPLATE = "{number} "
_PRINTED_NUMERAL_OPENING_RE = re.compile(r"^(?P<digits>\d{1,3})\.\s+")
_RAISED_DIGITS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_RAISED_TO_DIGITS = str.maketrans(_RAISED_DIGITS, "0123456789")
_RAISED_NUMERAL_OPENING_RE = re.compile(rf"^\s*(?P<raised>[{_RAISED_DIGITS}]{{1,3}})(?![{_RAISED_DIGITS}])")
_OPENING_WORDS_MATCHED = 3
MAX_CONTINUATION_LABEL_WORDS = 3
_LAYER_NUMERAL_TEMPLATE = r"(?<!\d)(?:<sup>)?(?P<number>\d{1,3})(?:</sup>)?\s+"

_NEXT_NOTE_TEMPLATE = (r"(?<=[.;:!?)\]”’*])\s+(?=(\*{{0,2}})(?:<sup>)?{number}(?:</sup>)?\1\s+\S)"
                       r"|(?<=[.;:!?)\]”’*])(?=<sup>{number}</sup>\s*\S)"
                       r"|\s+(?={number}\s+[A-ZÀ-ÖØ-Þ])")
_REFERENCE_ABBREVIATIONS = frozenset({"p.", "pp.", "vol.", "vols.", "no.", "nos.", "n.", "nn.", "ch.", "chap.",
                                      "sec.", "fig.", "cf.", "ed.", "s.", "bd.", "anm.", "art.", "l.", "ll."})


@dataclass(frozen=True)
class FootnoteDefinition:
    label: int
    number: str | None
    text: str
    marked: bool = True

    def rendered(self) -> str:
        return f"{written_mark(self.label)}: {self.text}"

    def extended(self, more: str) -> FootnoteDefinition:
        return FootnoteDefinition(self.label, self.number, f"{self.text} {more}".strip(), self.marked)

    def relabelled(self, label: int) -> FootnoteDefinition:
        return dataclasses.replace(self, label=label)

    def printed_numeral(self) -> int | None:
        opening = _PRINTED_NUMERAL_OPENING_RE.match(self.text)
        if opening is None:
            return None
        return int(opening.group("digits"))

    def is_continued_as(self, continued: FootnoteDefinition) -> bool:
        return self.marked and self.label == continued.label

    def repeats_the_opening_of(self, other: FootnoteDefinition) -> bool:
        opening = self.text.removeprefix(printed_opening(self.number))
        is_an_unmarked_twin = not self.marked and other.marked and self.number == other.number
        return is_an_unmarked_twin and other.text.startswith(opening)


@dataclass(frozen=True)
class FootnoteLabels:
    marked: int = 0
    unmarked: int = 0

    def after_marked(self, printed_sign: str) -> FootnoteLabels:
        following = self.marked + 1
        numeral = int(printed_sign) if printed_sign.isdigit() else following
        return dataclasses.replace(self, marked=max(numeral, following))

    def after_unmarked(self) -> FootnoteLabels:
        return dataclasses.replace(self, unmarked=self.unmarked + 1)


def labelled_after_the_marked(definitions: list[FootnoteDefinition],
                              unpaired_marks: set[int]) -> list[FootnoteDefinition]:
    taken = {definition.label for definition in definitions if definition.marked} | unpaired_marks
    filling_gaps = _unmarked_filling_gaps(definitions, taken)
    past_the_marked = itertools.count(max(taken, default=0) + 1)
    return [_labelled(definition, index in filling_gaps, past_the_marked)
            for index, definition in enumerate(definitions)]


def _unmarked_filling_gaps(definitions: list[FootnoteDefinition], taken: set[int]) -> set[int]:
    gaps = set(range(1, max(taken, default=0) + 1)) - taken
    filling = set()
    for index, definition in enumerate(definitions):
        numeral = definition.printed_numeral()
        if not definition.marked and numeral in gaps:
            gaps.discard(numeral)
            filling.add(index)
    return filling


def _labelled(definition: FootnoteDefinition, fills_a_gap: bool, past_the_marked: Iterator[int]) -> FootnoteDefinition:
    if definition.marked:
        return definition
    if fills_a_gap:
        return definition.relabelled(definition.printed_numeral())
    return definition.relabelled(next(past_the_marked))


@dataclass(frozen=True)
class _LogEntry:
    file_page: int
    number: str | None
    is_mark: bool

    def rendered(self) -> str:
        if self.is_mark:
            return f"file p. {self.file_page}: mark {self.number} has no footnote on the page"
        return f"file p. {self.file_page}: footnote {self.number or '(unnumbered)'} has no mark on the page"

    def is_endnote(self, sections) -> bool:
        if self.is_mark:
            return sections.lists_mark(self.file_page, self.number)
        return sections.holds_page(self.file_page)


class FootnoteLog:
    def __init__(self) -> None:
        self._entries: list[_LogEntry] = []

    def unpaired_mark(self, file_page: int, number: str) -> None:
        self._entries.append(_LogEntry(file_page, number, True))

    def withdraw_unpaired_mark(self, file_page: int, number: str) -> None:
        self._entries.remove(_LogEntry(file_page, number, True))

    def orphan_definition(self, file_page: int, number: str | None) -> None:
        self._entries.append(_LogEntry(file_page, number, False))

    def entries(self) -> list[str]:
        return [entry.rendered() for entry in self._entries]

    def entries_outside(self, endnote_sections) -> list[str]:
        return [entry.rendered() for entry in self._entries if not entry.is_endnote(endnote_sections)]


@dataclass
class PairedPage:
    body_texts: list[str]
    definitions: list[FootnoteDefinition]
    continued_texts: list[str]

    def footnote_texts(self) -> list[str]:
        return [definition.text for definition in self.definitions] + self.continued_texts


class FootnotePairer:
    def __init__(self, labels: FootnoteLabels, log: FootnoteLog) -> None:
        self._labels = labels
        self._log = log
        self._open: FootnoteDefinition | None = None
        self._open_page = 0
        self._continuations: list[FootnoteDefinition] = []
        self._left_open = OpenMarks(0, frozenset())
        self._unanswered = UnansweredMarks()
        self._carried: list[CarriedNote] = []

    def continuations(self) -> list[FootnoteDefinition]:
        return list(self._continuations)

    def clear_continuations(self) -> None:
        self._continuations.clear()

    def carried_notes(self) -> list[CarriedNote]:
        return list(self._carried)

    def paired(self, file_page: int, body_htmls: list[str], footnote_texts: list[str]) -> PairedPage:
        note_texts = [_with_its_raised_numeral_lowered(text) for text in footnote_texts]
        htmls = _answered_marks_raised(body_htmls, note_texts)
        marks = {number for html in htmls for number in mark_numbers(html)}
        notes = self._note_texts(file_page, note_texts, marks)
        continued = [] if self._open is None else notes.leading
        self._extend_open(continued)
        carried = self._carried_over(notes.keyed, marks)
        numbered = [(number, text) for number, text in notes.keyed if number not in carried]
        candidates = [(None, text) for text in notes.leading if not continued] + numbered
        pairing = _PagePairing(self, file_page, dict(numbered))
        bodies = [pairing.marked(html) for html in htmls]
        paired_here = pairing.definitions(candidates)
        definitions = list(carried.values()) + paired_here
        unmarked = [self._unmarked(file_page, number, text) for number, text in pairing.unpaired(candidates)]
        self._keep_left_open(pairing.marks_left_open(), paired_here)
        self._keep_open(file_page, definitions, continued)
        return PairedPage(bodies, definitions + unmarked, continued)

    def _note_texts(self, file_page: int, note_texts: list[str], marks: set[str]) -> _NoteTexts:
        open_number = self._open.number if self._open else None
        sequence = _NoteSequence(open_number, self._raised_on(file_page, marks))
        unlabelled = _ContinuationLabel(open_number).dropped(note_texts)
        run_on = _RunOnNotes(marks)
        return _NoteTexts([note for text in _joined_continuations(unlabelled) for note in run_on.split(text)], sequence)

    def leaves_a_note_unfinished_before(self, file_page: int) -> bool:
        is_open_on_the_page_before = self._open is not None and self._open_page == file_page - 1
        return is_open_on_the_page_before and not closes_a_sentence(self._open.text)

    def _keep_left_open(self, left_open: OpenMarks, paired_here: list[FootnoteDefinition]) -> None:
        if paired_here:
            self._unanswered.forget_all()
        self._unanswered.keep(left_open)
        self._left_open = left_open

    def _keep_open(self, file_page: int, definitions: list[FootnoteDefinition], continued: list[str]) -> None:
        if definitions:
            self._open = definitions[-1]
        if definitions or continued:
            self._open_page = file_page

    def define(self, number: str, text: str) -> FootnoteDefinition:
        self._labels = self._labels.after_marked(number)
        return FootnoteDefinition(self._labels.marked, number, text)

    def note_unpaired_mark(self, file_page: int, number: str) -> None:
        self._log.unpaired_mark(file_page, number)

    def close_marks(self, numbers: set[str]) -> None:
        self._left_open = self._left_open.without(numbers)
        self._unanswered.withdraw(self._left_open.file_page, numbers)

    def open_marks_before(self, file_page: int) -> frozenset[str]:
        return frozenset(number for number in self._left_open.numbers if self._left_open.holds(number, file_page))

    def _raised_on(self, file_page: int, marks: set[str]) -> frozenset[str]:
        return frozenset(marks) | self.open_marks_before(file_page)

    def _carried_over(self, numbered: list[tuple[str, str]], marks: set[str]) -> dict[str, FootnoteDefinition]:
        return {number: self._carry(number, text) for number, text in numbered
                if number not in marks and self._unanswered.page_of(number) is not None}

    def _carry(self, number: str, text: str) -> FootnoteDefinition:
        mark_page = self._unanswered.page_of(number)
        self._unanswered.answer(number)
        definition = self.define(number, text)
        self._carried.append(CarriedNote(mark_page, number, definition.label))
        self._log.withdraw_unpaired_mark(mark_page, number)
        return definition

    def _extend_open(self, texts: list[str]) -> None:
        for text in texts:
            self._open = self._open.extended(text)
            self._continuations.append(self._open)

    def _unmarked(self, file_page: int, number: str | None, text: str) -> FootnoteDefinition:
        self._log.orphan_definition(file_page, number)
        printed = printed_opening(number) + text
        self._labels = self._labels.after_unmarked()
        return FootnoteDefinition(self._labels.unmarked, number, printed, marked=False)


@dataclass(frozen=True)
class _NoteSequence:
    open_number: str | None
    raised: frozenset[str]

    def opens_a_note(self, number: str, keyed: list[str]) -> bool:
        numerals = [sign for sign in [self.open_number] + keyed if sign is not None and sign.isdigit()]
        follows = numerals[-1] if numerals else None
        if follows is None or int(number) > int(follows):
            return True
        return number in self.raised and number not in keyed


class _NoteTexts:
    def __init__(self, texts: list[str], sequence: _NoteSequence) -> None:
        self._sequence = sequence
        self._leading: list[str] = []
        self._keyed: list[tuple[str, str]] = []
        for text in texts:
            if text.strip():
                self._add(text)

    @property
    def leading(self) -> list[str]:
        return list(self._leading)

    @property
    def keyed(self) -> list[tuple[str, str]]:
        return list(self._keyed)

    def _add(self, text: str) -> None:
        numbered = _LEADING_NUMBER_RE.match(text)
        keyed = KEYED_NOTE_OPENING_RE.match(text)
        if keyed is not None:
            self._keyed.append((note_key(keyed), text[keyed.end():].strip()))
        elif numbered is None:
            self._continue(text.strip())
        else:
            self._add_numbered(numbered.group("number"), text[numbered.end():].strip(), text.strip())

    def _add_numbered(self, number: str, body: str, printed: str) -> None:
        if (number, body) in self._keyed:
            return
        if self._keyed and self._keyed[-1][0] == number and closes_a_sentence(self._keyed[-1][1]):
            self._fold_the_last_note_back()
        if self._sequence.opens_a_note(number, [held for held, _ in self._keyed]):
            self._keyed.append((number, body))
        else:
            self._continue(printed)

    def _fold_the_last_note_back(self) -> None:
        number, body = self._keyed.pop()
        self._continue(f"{number} {body}")

    def _continue(self, text: str) -> None:
        if self._keyed:
            number, previous = self._keyed[-1]
            self._keyed[-1] = (number, f"{previous} {text}")
        else:
            self._leading.append(text)


@dataclass(frozen=True)
class _ContinuationLabel:
    open_number: str | None

    def dropped(self, footnote_texts: list[str]) -> list[str]:
        texts = [text.strip() for text in footnote_texts if text.strip()]
        if len(texts) < 2 or not self._labels(texts[0]) or _LEADING_NUMBER_RE.match(texts[1]) is not None:
            return footnote_texts
        return texts[1:]

    def _labels(self, text: str) -> bool:
        words = text.split()
        is_short = len(words) <= MAX_CONTINUATION_LABEL_WORDS
        is_a_heading = _LEADING_NUMBER_RE.match(text) is None and not closes_a_sentence(text)
        names_the_open_note = self.open_number is not None and self.open_number.isdigit() and self.open_number in words
        return names_the_open_note and is_short and is_a_heading


class _PagePairing:
    def __init__(self, pairer: FootnotePairer, file_page: int, by_number: dict[str, str]) -> None:
        self._pairer = pairer
        self._file_page = file_page
        self._by_number = by_number
        self._taken: dict[str, FootnoteDefinition] = {}
        self._left_open: set[str] = set()

    def marked(self, html: str) -> str:
        return RAISED_KEY_RE.sub(self._keyed, MARK_RE.sub(self._replaced, html))

    def marks_left_open(self) -> OpenMarks:
        return OpenMarks(self._file_page, frozenset(self._left_open))

    def definitions(self, candidates: list[tuple[str | None, str]]) -> list[FootnoteDefinition]:
        return [self._taken[number] for number, _text in candidates if number in self._taken]

    def unpaired(self, candidates: list[tuple[str | None, str]]) -> list[tuple[str | None, str]]:
        return [(number, text) for number, text in candidates if number not in self._taken]

    def _replaced(self, match: re.Match) -> str:
        return "".join(self._reference(number) for number in _MARK_SEPARATOR_RE.split(match.group(1)))

    def _reference(self, number: str) -> str:
        if not self._answers(number):
            self._pairer.note_unpaired_mark(self._file_page, number)
            self._left_open.add(number)
            return f"<sup>{number}</sup>"
        return self._defined(number)

    def _keyed(self, match: re.Match) -> str:
        key = match.group(1)
        return self._defined(key) if self._answers(key) else match.group(0)

    def _answers(self, sign: str) -> bool:
        return sign in self._by_number and sign not in self._taken

    def _defined(self, sign: str) -> str:
        self._taken[sign] = self._pairer.define(sign, self._by_number[sign])
        return written_mark(self._taken[sign].label)


class _RunOnNotes:
    def __init__(self, marks: set[str]) -> None:
        self._marks = marks

    def split(self, text: str) -> list[str]:
        notes, rest = [], text
        boundary = self._next_boundary(rest)
        while boundary is not None:
            notes.append(rest[:boundary.start()].strip())
            rest = rest[boundary.end():]
            boundary = self._next_boundary(rest)
        return notes + [rest]

    def _next_boundary(self, text: str) -> re.Match | None:
        leading = _LEADING_NUMBER_RE.match(text)
        if leading is None:
            return None
        next_number = int(leading.group("number")) + 1
        if str(next_number) not in self._marks:
            return None
        pattern = _NEXT_NOTE_TEMPLATE.format(number=next_number)
        return next((found for found in re.finditer(pattern, text) if not _ends_in_abbreviation(text[:found.start()])),
                    None)


def _answered_marks_raised(body_htmls: list[str], footnote_texts: list[str]) -> list[str]:
    printed = {leading_note_number(text) for text in footnote_texts} - {None}
    htmls = body_htmls
    for raised_form in (FormulaMarks, SuperscriptMarks):
        marked = {number for html in htmls for number in mark_numbers(html)}
        answered = raised_form(printed, marked)
        htmls = [answered.raised(html) for html in htmls]
    return htmls


def _with_its_raised_numeral_lowered(note_text: str) -> str:
    return _RAISED_NUMERAL_OPENING_RE.sub(_lowered_numeral, note_text, count=1)


def _lowered_numeral(opening: re.Match) -> str:
    return raised_mark(opening.group("raised").translate(_RAISED_TO_DIGITS))


def _joined_continuations(texts: list[str]) -> list[str]:
    joined: list[str] = []
    for text in (text.strip() for text in texts if text.strip()):
        if joined and not _opens_a_keyed_note(text):
            joined[-1] = f"{joined[-1]} {text}"
        else:
            joined.append(text)
    return joined


def _opens_a_keyed_note(text: str) -> bool:
    return _LEADING_NUMBER_RE.match(text) is not None or KEYED_NOTE_OPENING_RE.match(text) is not None


def _ends_in_abbreviation(text: str) -> bool:
    words = text.split()
    return bool(words) and words[-1].lower() in _REFERENCE_ABBREVIATIONS


def printed_opening(sign: str | None) -> str:
    if sign is None:
        return ""
    template = _PRINTED_SYMBOL_TEMPLATE if sign[0] in NOTE_SYMBOLS else _PRINTED_NUMERAL_TEMPLATE
    return template.format(number=sign)


def mark_numbers(html: str) -> list[str]:
    return [number for run in MARK_RE.findall(html) for number in _MARK_SEPARATOR_RE.split(run)]


def leading_note_number(text: str) -> str | None:
    match = _LEADING_NUMBER_RE.match(text)
    return match.group("number") if match else None


def with_the_layers_numeral(read_text: str, layer_text: str) -> str:
    read = _LEADING_NUMBER_RE.match(read_text)
    opening_words = read_text[read.end():].split()[:_OPENING_WORDS_MATCHED] if read else []
    if not opening_words:
        return read_text
    printed = _numerals_printed_before(opening_words, layer_text)
    if not printed:
        return read_text[read.end():] if _opens_on(layer_text, opening_words) else read_text
    if read.group("number") in printed:
        return read_text
    return read_text[:read.start("number")] + printed[0] + read_text[read.end("number"):]


def _opens_on(layer_text: str, opening_words: list[str]) -> bool:
    return layer_text.split()[:len(opening_words)] == opening_words


def _numerals_printed_before(opening_words: list[str], layer_text: str) -> list[str]:
    pattern = _LAYER_NUMERAL_TEMPLATE + r"\s+".join(map(re.escape, opening_words))
    return [printed.group("number") for printed in re.finditer(pattern, layer_text)]


def without_marks(text: str) -> tuple[str, list[str]]:
    marks = [mark.strip() for mark in _MARK_RE.findall(text)]
    return _MARK_RE.sub("", text).strip(), marks
