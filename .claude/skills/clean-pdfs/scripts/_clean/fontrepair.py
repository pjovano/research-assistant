from __future__ import annotations

from font_repair_record import FONT_REPAIR_RECORD_KEY

import json
from pathlib import Path

import pikepdf
import pymupdf
from vault import ReplacementFile

from .cmap import STREAM_ENCODING, ToUnicodeCMap
from .fonts import (
    DIFFERENCES_KEY,
    ENCODING_KEY,
    FIRST_GENERATION,
    TOUNICODE_KEY,
    FontRecord,
    glyph_name_char,
    parse_differences,
)
from .fontscan import FlaggedCode
from .glyphs import unicode_label
from .lines import Glyph
from .textlayer import Occurrences, SuspectOccurrence, TextLayerOccurrences

FONT_TEMPORARY_SUFFIX = ".fonts.tmp.pdf"
RECORD_KEY = f"/{FONT_REPAIR_RECORD_KEY}"
STATUS_WOULD_REPAIR = "would-repair"
STATUS_REPAIRED = "repaired"
STATUS_NOTHING_TO_REPAIR = "nothing-to-repair"
STATUS_UNRESOLVED = "unresolved-codes-remain"
STATUS_VERIFICATION_FAILED = "verification-failed"


class VerificationFailed(RuntimeError):
    pass


class RepairRecordCorrupt(RuntimeError):
    pass


class RepairPlan:
    def __init__(self, flagged: list[FlaggedCode]) -> None:
        self._patches = [code for code in flagged if code.is_resolved() and not code.is_confirmed()]
        self._unresolved = [code for code in flagged if not code.is_resolved()]

    def is_empty(self) -> bool:
        return not self._patches and not self._unresolved

    def has_patches(self) -> bool:
        return bool(self._patches)

    def is_partial(self) -> bool:
        return bool(self._unresolved)

    def overrides_for(self, record: FontRecord) -> dict[str, str]:
        return {patch.code: patch.identity.unicode for patch in self._patches if _applies_to(patch, record)}

    def overrides_by_xref(self, records: list[FontRecord]) -> dict[int, dict[str, str]]:
        return {record.xref: overrides for record in records if (overrides := self.overrides_for(record))}

    def records(self) -> list[dict]:
        unique = {_record_key(record): record for record in (patch.as_record() for patch in self._patches)}
        return list(unique.values())

    def retired_characters(self, records: list[FontRecord]) -> set[Glyph]:
        patched = {patch.text_layer_glyph for patch in self._patches}
        kept = {code.text_layer_glyph for code in self._unresolved}
        return patched - kept - self._still_emitted(records)

    def _still_emitted(self, records: list[FontRecord]) -> set[Glyph]:
        return {glyph for record in records
                for glyph in record.glyphs_emitted_beyond(set(self.overrides_for(record)))}

    def as_dict(self) -> dict:
        return {"partial": self.is_partial(),
                "patches": [_patch_row(patch) for patch in self._patches],
                "unresolved": [_unresolved_row(code) for code in self._unresolved]}


def _applies_to(patch: FlaggedCode, record: FontRecord) -> bool:
    same_font = patch.record.key == record.key
    emitted = record.emitted_at(patch.code)
    code_is_free_or_same = emitted is None or emitted == patch.char
    return same_font and code_is_free_or_same


def _record_key(record: dict) -> tuple:
    return tuple(sorted(record.items()))


def _patch_row(patch: FlaggedCode) -> dict:
    return {**patch.as_record(), "subset": patch.record.basefont, "xref": patch.record.xref}


def _unresolved_row(code: FlaggedCode) -> dict:
    return {**code.location(), "glyph_name": code.glyph_name, "unicode": unicode_label(code.char)}


class FontRepair:
    def __init__(self, pdf_path: Path, plan: RepairPlan, records: list[FontRecord]) -> None:
        self._path = pdf_path
        self._plan = plan
        self._records = records

    def run(self) -> None:
        with ReplacementFile(self._path, FONT_TEMPORARY_SUFFIX) as replacement:
            self._write_patched(replacement.path)
            RepairCheck(self._path, replacement.path, self._plan.retired_characters(self._records)).run()
            replacement.commit()

    def _write_patched(self, destination: Path) -> None:
        overrides_by_xref = self._plan.overrides_by_xref(self._records)
        with pikepdf.open(self._path) as pdf:
            for xref, overrides in overrides_by_xref.items():
                _ToUnicodeStream(pdf, xref).rewrite(overrides)
            RepairRecord(pdf).append(self._plan.records())
            pdf.save(destination)


class _ToUnicodeStream:
    def __init__(self, pdf: pikepdf.Pdf, xref: int) -> None:
        self._pdf = pdf
        self._font = pdf.get_object((xref, FIRST_GENERATION))

    def rewrite(self, overrides: dict[str, str]) -> None:
        original = self._stored()
        patched = (original or ToUnicodeCMap.from_mappings(self._glyph_name_mappings())).patched(overrides)
        if original is not None:
            KeptMappingsCheck(original, overrides).run(ToUnicodeCMap(patched))
        self._font[TOUNICODE_KEY] = self._pdf.make_stream(patched.encode(STREAM_ENCODING))

    def _stored(self) -> ToUnicodeCMap | None:
        stream = self._font.get(TOUNICODE_KEY)
        return ToUnicodeCMap.from_bytes(stream.read_bytes()) if isinstance(stream, pikepdf.Stream) else None

    def _glyph_name_mappings(self) -> dict[str, str]:
        encoding = self._font.get(ENCODING_KEY)
        if not isinstance(encoding, pikepdf.Dictionary) or DIFFERENCES_KEY not in encoding:
            return {}
        named = parse_differences(list(encoding[DIFFERENCES_KEY])).items()
        return {code: char for code, char in ((code, glyph_name_char(name)) for code, name in named) if char}


class RepairRecord:
    def __init__(self, pdf: pikepdf.Pdf) -> None:
        self._pdf = pdf

    def entries(self) -> list[dict]:
        stored = self._pdf.docinfo.get(RECORD_KEY)
        return [] if stored is None else _record_list(str(stored))

    def append(self, new_entries: list[dict]) -> None:
        self._pdf.docinfo[RECORD_KEY] = json.dumps(self.entries() + new_entries)


def _record_list(text: str) -> list[dict]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as failure:
        raise RepairRecordCorrupt(f"{RECORD_KEY} in the PDF's docinfo is not JSON: {failure}") from failure
    if not isinstance(parsed, list):
        raise RepairRecordCorrupt(f"{RECORD_KEY} in the PDF's docinfo is not a list")
    return parsed


class RepairCheck:
    def __init__(self, src_path: Path, dest_path: Path, retired: set[Glyph]) -> None:
        self._src = src_path
        self._dest = dest_path
        self._retired = retired

    def run(self) -> None:
        self._check_pages_kept()
        self._check_retired_characters_gone()

    def _check_pages_kept(self) -> None:
        with pymupdf.open(self._src) as src_doc, pymupdf.open(self._dest) as dest_doc:
            if dest_doc.page_count != src_doc.page_count:
                raise VerificationFailed(self._page_count_message(src_doc.page_count, dest_doc.page_count))

    def _page_count_message(self, expected: int, actual: int) -> str:
        return f"{self._dest.name} has {actual} pages; the original has {expected}."

    def _check_retired_characters_gone(self) -> None:
        occurrences = Occurrences(TextLayerOccurrences(self._dest, frozenset(self._retired)).collect())
        remaining = occurrences.matching(self._retired)
        if remaining:
            raise VerificationFailed(_remaining_message(remaining))


class KeptMappingsCheck:
    def __init__(self, original: ToUnicodeCMap, overrides: dict[str, str]) -> None:
        self._original = original
        self._overrides = overrides

    def run(self, patched: ToUnicodeCMap) -> None:
        changed = self._changed_codes(patched.mappings())
        if changed:
            raise VerificationFailed(f"the repaired ToUnicode table no longer maps the unpatched code(s) "
                                     f"{', '.join(changed)} to their old characters.")
        if patched.inherited_lines() != self._original.inherited_lines():
            raise VerificationFailed("the repaired ToUnicode table lost a usecmap line or a codespace range "
                                     "of the original.")

    def _changed_codes(self, kept: dict[str, str]) -> list[str]:
        unpatched = {code: char for code, char in self._original.mappings().items() if code not in self._overrides}
        return sorted(code for code, char in unpatched.items() if kept.get(code) != char)


def _remaining_message(remaining: list[SuspectOccurrence]) -> str:
    first = remaining[0]
    return (f"{len(remaining)} occurrence(s) of the repaired characters remain in the text layer, "
            f"the first on page {first.page_number}: {first.font} {unicode_label(first.char)}.")
