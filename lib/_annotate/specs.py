from __future__ import annotations

import json
from pathlib import Path

from .notes import Note, Tag
from .palette import TagPalette
from .reader import RevisionChange
from .requests import AnnotationRequest


class SpecError(ValueError):
    pass


class SpecColour:
    def __init__(self, given) -> None:
        self._given = given

    def rgb(self) -> tuple | None:
        if self._given is None:
            return None
        if isinstance(self._given, str):
            return self._named()
        return tuple(float(value) for value in self._given)

    def _named(self) -> tuple:
        colour = TagPalette().named(self._given)
        if colour is None:
            raise SpecError(f"unknown colour {self._given!r}; use one of {TagPalette().names}")
        return colour.rgb


class AnnotationSpec:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    @staticmethod
    def loaded(path: Path) -> "AnnotationSpec":
        return AnnotationSpec(JsonSpec(path).payload())

    def requests(self) -> list[AnnotationRequest]:
        entries = self._payload.get("annotations")
        if not isinstance(entries, list):
            raise SpecError("spec needs an 'annotations' list")
        return [self._request(entry, position) for position, entry in enumerate(entries)]

    def _request(self, entry: dict, position: int) -> AnnotationRequest:
        self._require(entry, position, "page")
        page = int(entry["page"])
        return AnnotationRequest(page, int(entry.get("start", 0)),
                                 int(entry.get("end", 0)), self._note(entry),
                                 self._rect(entry), SpecColour(entry.get("colour")).rgb(),
                                 self._end_page(entry, position, page), self._further(entry, position))

    def _end_page(self, entry: dict, position: int, page: int) -> int | None:
        if "end_page" not in entry:
            return None
        if "rect" in entry:
            raise SpecError(f"annotation {position} carries both 'end_page' and 'rect'; "
                            "a cross-page span is a word span")
        end_page = int(entry["end_page"])
        if end_page != page + 1:
            raise SpecError(f"annotation {position}: 'end_page' must be {page + 1}, "
                            f"the page after 'page' {page}; got {end_page}")
        return end_page

    def _further(self, entry: dict, position: int) -> tuple:
        further = tuple((int(start), int(end)) for start, end in entry.get("further", []))
        if further and ("end_page" in entry or "rect" in entry):
            raise SpecError(f"annotation {position} carries 'further' beside 'end_page' or 'rect'; "
                            "a joint highlight is word spans of one page")
        return further

    def _note(self, entry: dict) -> Note:
        first, *further = [*([entry["tag"]] if entry.get("tag") else []), *entry.get("tags", [])] or [""]
        return Note(entry.get("link", ""), entry.get("body", ""), Tag(first), tuple(Tag(label) for label in further),
                    tuple(Tag(label) for label in entry.get("inline_tags", [])), bool(entry.get("rewrite", False)))

    def _rect(self, entry: dict) -> tuple | None:
        rect = entry.get("rect")
        return tuple(float(v) for v in rect) if rect else None

    def _require(self, entry: dict, position: int, key: str) -> None:
        if key not in entry:
            raise SpecError(f"annotation {position} is missing '{key}'")


class RevisionSpec:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    @staticmethod
    def loaded(path: Path) -> "RevisionSpec":
        return RevisionSpec(JsonSpec(path).payload())

    def changes(self) -> list[RevisionChange]:
        entries = self._payload.get("changes")
        if not isinstance(entries, list):
            raise SpecError("spec needs a 'changes' list")
        return [self._change(entry, position) for position, entry in enumerate(entries)]

    def _change(self, entry: dict, position: int) -> RevisionChange:
        self._require(entry, position)
        return RevisionChange(int(entry["page"]), int(entry["index"]),
                              SpecColour(entry.get("colour")).rgb(), entry.get("note"),
                              entry.get("append"), bool(entry.get("delete", False)))

    def _require(self, entry: dict, position: int) -> None:
        for key in ("page", "index"):
            if key not in entry:
                raise SpecError(f"change {position} is missing '{key}'")


class JsonSpec:
    def __init__(self, path: Path) -> None:
        self._path = path

    def payload(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except OSError as error:
            raise SpecError(f"cannot read spec {self._path}: {error}") from error
        except json.JSONDecodeError as error:
            raise SpecError(f"spec {self._path} is not valid JSON: {error}") from error
