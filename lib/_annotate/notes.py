from __future__ import annotations

import re
from dataclasses import dataclass

ENTRY_SEPARATOR = "\n\n"
TAG_SEPARATOR = "\n"
TOKEN_SEPARATOR = " "
LINK_SEPARATOR = " — "
OMISSION = " […] "
NON_SLUG = re.compile(r"[^a-z0-9]+")
TAG_IN_TEXT = re.compile(r"#\[\[([^\]]+)\]\]")


@dataclass(frozen=True)
class Tag:
    label: str

    @property
    def is_empty(self) -> bool:
        return not self.label.strip()

    @property
    def slug(self) -> str:
        return NON_SLUG.sub("-", self.label.strip().lower()).strip("-")

    @property
    def token(self) -> str:
        if self.is_empty:
            return ""
        return f"#[[{self.label.strip()}]]"

    def matches(self, wanted: str) -> bool:
        return self.slug == Tag(wanted).slug

    @staticmethod
    def found_in(text: str) -> list["Tag"]:
        return [Tag(label) for label in TAG_IN_TEXT.findall(text or "")]


@dataclass(frozen=True)
class Note:
    link: str
    body: str
    tag: Tag = Tag("")
    further_tags: tuple[Tag, ...] = ()
    inline_tags: tuple[Tag, ...] = ()
    rewrites: bool = False

    @property
    def rendered(self) -> str:
        body = InlinedBody(self.body, self.inline_tags)
        return TAG_SEPARATOR.join(part for part in (self._stem(body.text), self._tokens(body)) if part)

    def _tokens(self, body: "InlinedBody") -> str:
        return TOKEN_SEPARATOR.join(tag.token for tag in (self.tag, *self.further_tags)
                                    if not tag.is_empty and not body.carries(tag))

    def _stem(self, body: str) -> str:
        if not self.link:
            return body
        separator = TAG_SEPARATOR if TAG_SEPARATOR in body.strip() else LINK_SEPARATOR
        return separator.join(part for part in (f"[[{self.link}]]", body.strip()) if part)


class InlinedBody:
    def __init__(self, body: str, tags: tuple[Tag, ...]) -> None:
        self._text = body
        self._carried: list[str] = []
        for tag in tags:
            self._inline(tag)

    @property
    def text(self) -> str:
        return self._text

    def carries(self, tag: Tag) -> bool:
        return tag.slug in self._carried

    def _inline(self, tag: Tag) -> None:
        named = None if tag.is_empty else self._first_naming(tag)
        if named is not None:
            self._text = self._text[:named.start()] + tag.token + self._text[named.end():]
            self._carried.append(tag.slug)

    def _first_naming(self, tag: Tag) -> re.Match | None:
        pattern = re.compile(rf"\[\[[^\]]*\]\]|(?P<label>(?<!\w){re.escape(tag.label)}(?!\w))", re.IGNORECASE)
        return next((match for match in pattern.finditer(self._text) if match.group("label")), None)


class NoteLedger:
    def __init__(self, content: str) -> None:
        self._entries = self._split(content)

    @staticmethod
    def of(annotation) -> "NoteLedger":
        return NoteLedger(annotation.info.get("content", ""))

    @property
    def entries(self) -> list[str]:
        return list(self._entries)

    def mentions(self, link: str) -> bool:
        return any(f"[[{link}]]" in entry for entry in self._entries)

    def appended(self, note: Note) -> str:
        if not self._carries_already(note):
            return self.extended(note.rendered)
        return self._rewritten(note) if note.rewrites else self.rendered()

    def _rewritten(self, note: Note) -> str:
        return ENTRY_SEPARATOR.join(note.rendered if entry.startswith(f"[[{note.link}]]") else entry
                                    for entry in self._entries)

    def extended(self, entry: str) -> str:
        return ENTRY_SEPARATOR.join(self._entries + [entry])

    def _carries_already(self, note: Note) -> bool:
        if note.link:
            return self.mentions(note.link)
        return note.rendered in self._entries

    def rendered(self) -> str:
        return ENTRY_SEPARATOR.join(self._entries)

    def _split(self, content: str) -> list[str]:
        if not content:
            return []
        return [entry.strip() for entry in content.split(ENTRY_SEPARATOR) if entry.strip()]
