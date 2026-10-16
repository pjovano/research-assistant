from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

import identifiers
import titlecase
import vault
import zotero

from _file.records import CslName, CslRecord
from _file.resolvers import ARXIV_ARCHIVE

SHORT_TITLE_LIMIT = 60
_SHORT_TITLE_TROUBLE = ('?', '/', ':', '"')
_HTML_TAG = re.compile(r"<[^>]+>")
_DASH_SUBTITLE = re.compile(r"(?<=\S)\s+[—–]\s+(?=\S)")
_DOUBLED_SPACE = re.compile(r"\s{2,}")
_IMPRINT_SEPARATOR = re.compile(r"\s*[;/]\s*")
_SUBTITLE_JOIN = ": "
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
_SUFFIXES = ("Jr.", "Jr", "Sr.", "Sr", "II", "III", "IV")
_MASSACHUSETTS_PUBLISHERS = ("harvard university press", "mit press", "belknap")
_CAMBRIDGE_MASSACHUSETTS = "Cambridge, Massachusetts"
_CAMBRIDGE_FORMS = ("cambridge", "cambridge, ma", "cambridge, mass.", "cambridge, mass", "cambridge ma")
_PRINT_ISSN = "print"

_CREATOR_TYPES_BY_CSL_ROLE = {
    "author": "author",
    "editor": "editor",
    "translator": "translator",
    "container-author": "bookAuthor",
    "collection-editor": "seriesEditor",
}

_ARTICLE_DATE_FIELDS = ("published-print", "issued", "published-online")
_OTHER_DATE_FIELDS = ("issued", "published-print", "published-online")


@dataclass
class Proposal:
    fields: dict = field(default_factory=dict)
    orig_year: str | None = None
    normalizations: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    def set(self, name: str, value: object) -> None:
        if value not in zotero.EMPTY_FIELD_VALUES:
            self.fields[name] = value

    def note(self, text: str) -> None:
        self.normalizations.append(text)

    def flag(self, text: str) -> None:
        self.flags.append(text)


class TitleNormalizer:
    def __init__(self, csl: dict) -> None:
        self._csl = csl

    def into(self, proposal: Proposal) -> None:
        title = self._cased(self._cleaned(str(self._csl.get("title") or ""), proposal), proposal)
        title = self._with_subtitle(title, proposal)
        proposal.set("title", title)
        self._flag_short_title(title, proposal)

    def _cased(self, text: str, proposal: Proposal) -> str:
        cased = titlecase.title_case(text)
        if cased.changed:
            proposal.note(f"recased to Title Case ({cased.language or 'language unknown'}): {cased.text}")
        if cased.language_unknown:
            proposal.flag(f"language not detected; English Title Case applied: {cased.text}")
        return cased.text

    def _cleaned(self, raw: str, proposal: Proposal) -> str:
        unmarked = html.unescape(_HTML_TAG.sub("", raw))
        if unmarked != raw:
            proposal.note("markup stripped from title")
        dashless = _DASH_SUBTITLE.sub(_SUBTITLE_JOIN, unmarked)
        if dashless != unmarked:
            proposal.flag("spaced dash converted to a colon: check that it opened a subtitle")
        return _DOUBLED_SPACE.sub(" ", dashless).strip().rstrip(".").strip()

    def _with_subtitle(self, title: str, proposal: Proposal) -> str:
        subtitles = [self._cased_subtitle(str(part), proposal) for part in self._csl.get("subtitle") or []]
        unjoined = [part for part in subtitles if part and part.lower() not in title.lower()]
        if not unjoined:
            return title
        proposal.note("subtitle joined to the title with a colon")
        return _SUBTITLE_JOIN.join([title] + unjoined)

    def _cased_subtitle(self, part: str, proposal: Proposal) -> str:
        cleaning_notes_discarded = Proposal()
        return self._cased(self._cleaned(part, cleaning_notes_discarded), proposal)

    def _flag_short_title(self, title: str, proposal: Proposal) -> None:
        main = vault.strip_subtitle(title)
        if len(main) > SHORT_TITLE_LIMIT:
            proposal.flag(f"main title exceeds {SHORT_TITLE_LIMIT} characters; hand-set shortTitle")
        if any(character in main for character in _SHORT_TITLE_TROUBLE):
            proposal.flag(f"main title carries one of {''.join(_SHORT_TITLE_TROUBLE)}; hand-set shortTitle")


class CreatorNormalizer:
    def __init__(self, csl: dict) -> None:
        self._csl = csl

    def into(self, proposal: Proposal) -> None:
        creators = [self._creator(name, creator_type, proposal)
                    for role, creator_type in _CREATOR_TYPES_BY_CSL_ROLE.items()
                    for name in self._csl.get(role) or []]
        proposal.set("creators", creators)

    def _creator(self, name: dict, creator_type: str, proposal: Proposal) -> dict:
        if name.get("literal"):
            proposal.flag(f"organization as {creator_type}: {name['literal']}")
            return {"creatorType": creator_type, "name": name["literal"]}
        person = CslName(name).as_creator()
        self._move_suffix(person, name)
        self._recase(person, proposal)
        if name.get("split-on-whitespace"):
            proposal.flag(f"name split on its last space: check the surname of {person['lastName']}")
        return {"creatorType": creator_type, **person}

    def _move_suffix(self, person: dict, name: dict) -> None:
        suffix = str(name.get("suffix") or "").strip()
        last = person["lastName"]
        for known in _SUFFIXES:
            if last.endswith(f" {known}") or last.endswith(f", {known}"):
                suffix, last = known, last[: -len(known)].rstrip(", ")
        person["lastName"] = last
        if suffix:
            person["firstName"] = f"{person['firstName']}, {suffix}".strip(", ")

    def _recase(self, person: dict, proposal: Proposal) -> None:
        for part in ("firstName", "lastName"):
            recased = vault.normalize_caps_name(person[part])
            if recased != person[part]:
                proposal.note(f"creator name de-shouted: {person[part]} -> {recased}")
            person[part] = recased
        if person["lastName"] and person["lastName"].islower():
            proposal.flag(f"all-lowercase surname left as given: {person['lastName']}")


class DateNormalizer:
    def __init__(self, csl: dict, item_type: str) -> None:
        self._csl = csl
        self._item_type = item_type

    def into(self, proposal: Proposal) -> None:
        order = _ARTICLE_DATE_FIELDS if self._item_type == "journalArticle" else _OTHER_DATE_FIELDS
        year = next((self._year(name) for name in order if self._year(name)), None)
        proposal.set("date", year)
        original = self._year("original-date")
        if original and original != year:
            proposal.orig_year = original

    def _year(self, name: str) -> str | None:
        return CslRecord(self._csl).year(name)


class PlaceNormalizer:
    def __init__(self, csl: dict) -> None:
        self._csl = csl

    def into(self, proposal: Proposal) -> None:
        place = str(self._csl.get("publisher-place") or "").strip()
        if not place:
            proposal.flag("place not supplied by the lookup")
            return
        primary = _IMPRINT_SEPARATOR.split(place)[0]
        if primary != place:
            proposal.note(f"place cut to the primary imprint: {primary}")
        proposal.set("place", self._massachusetts(primary, proposal))

    def _massachusetts(self, place: str, proposal: Proposal) -> str:
        if not self._is_cambridge_massachusetts(place):
            return place
        if place != _CAMBRIDGE_MASSACHUSETTS:
            proposal.note(f"place written as {_CAMBRIDGE_MASSACHUSETTS}")
        return _CAMBRIDGE_MASSACHUSETTS

    def _is_cambridge_massachusetts(self, place: str) -> bool:
        publisher = str(self._csl.get("publisher") or "").lower()
        return place.lower() in _CAMBRIDGE_FORMS and any(name in publisher for name in _MASSACHUSETTS_PUBLISHERS)


class ContainerNormalizer:
    def __init__(self, csl: dict, item_type: str) -> None:
        self._csl = csl
        self._item_type = item_type

    def into(self, proposal: Proposal) -> None:
        handler = {
            "journalArticle": self._article, "bookSection": self._chapter, "book": self._book,
            "preprint": self._preprint, "conferencePaper": self._conference,
            "thesis": self._thesis, "report": self._report,
        }.get(self._item_type)
        if handler:
            handler(proposal)

    def _article(self, proposal: Proposal) -> None:
        proposal.set("publicationTitle", self._csl.get("container-title"))
        proposal.set("volume", self._arabic_volume(proposal))
        proposal.set("issue", self._csl.get("issue"))
        self._pages(proposal)
        self._issn(proposal)

    def _chapter(self, proposal: Proposal) -> None:
        proposal.set("bookTitle", self._csl.get("container-title"))
        proposal.set("publisher", self._csl.get("publisher"))
        proposal.set("pages", self._csl.get("page"))
        PlaceNormalizer(self._csl).into(proposal)

    def _book(self, proposal: Proposal) -> None:
        proposal.set("publisher", self._csl.get("publisher"))
        proposal.set("series", self._csl.get("container-title"))
        PlaceNormalizer(self._csl).into(proposal)

    def _preprint(self, proposal: Proposal) -> None:
        proposal.set("repository", self._csl.get("archive") or ARXIV_ARCHIVE)
        proposal.set("archiveID", self._csl.get("archive_location"))
        proposal.set("url", self._csl.get("URL"))

    def _conference(self, proposal: Proposal) -> None:
        proposal.set("proceedingsTitle", self._csl.get("container-title"))
        proposal.set("publisher", self._csl.get("publisher"))
        proposal.set("pages", self._csl.get("page"))

    def _thesis(self, proposal: Proposal) -> None:
        proposal.set("university", self._csl.get("publisher"))
        PlaceNormalizer(self._csl).into(proposal)

    def _report(self, proposal: Proposal) -> None:
        proposal.set("institution", self._csl.get("publisher"))
        PlaceNormalizer(self._csl).into(proposal)

    def _arabic_volume(self, proposal: Proposal) -> str:
        volume = str(self._csl.get("volume") or "").strip()
        if volume and titlecase.ROMAN_NUMERAL.match(volume.upper()):
            proposal.note(f"Roman volume {volume} written as Arabic")
            return str(_roman_to_int(volume.upper()))
        return volume

    def _pages(self, proposal: Proposal) -> None:
        pages = str(self._csl.get("page") or "").strip()
        if pages:
            proposal.set("pages", pages)
            return
        article_number = str(self._csl.get("article-number") or "").strip()
        if article_number:
            proposal.set("pages", article_number)
            proposal.flag("article-number journal: the file's own folios belong in extra")

    def _issn(self, proposal: Proposal) -> None:
        by_type = self._csl.get("issn-by-type") or {}
        issn = by_type.get(_PRINT_ISSN) or next(iter(by_type.values()), None)
        if issn:
            proposal.set("ISSN", issn)
            proposal.flag("print ISSN written; a publisher-platform URL on the title page means the e-ISSN")


class IdentifierNormalizer:
    def __init__(self, csl: dict, pdf_isbns: list[str]) -> None:
        self._csl = csl
        self._pdf_isbns = pdf_isbns

    def into(self, proposal: Proposal) -> None:
        doi = str(self._csl.get("DOI") or "").strip()
        if doi:
            self._doi(doi, proposal)
        self._isbn(proposal)

    def _doi(self, doi: str, proposal: Proposal) -> None:
        cleaned = identifiers.clean_doi(doi)
        if cleaned != doi:
            proposal.note("DOI lowercased and stripped of its URL prefix")
        proposal.set("DOI", cleaned)

    def _isbn(self, proposal: Proposal) -> None:
        if len(self._pdf_isbns) == 1:
            proposal.set("ISBN", identifiers.canonical_isbn(self._pdf_isbns[0]))
            proposal.note("ISBN written as ISBN-13 without hyphens")
            return
        supplied = [isbn for isbn in (identifiers.canonical_isbn(str(raw)) for raw in self._csl.get("ISBN") or [])
                    if isbn]
        if self._pdf_isbns or supplied:
            proposal.flag(f"ISBN left for the worker to choose: PDF {self._pdf_isbns}, lookup {supplied}")


class RecordNormalizer:
    def __init__(self, csl: dict, pdf_isbns: list[str]) -> None:
        self._csl = csl
        self._pdf_isbns = pdf_isbns

    def proposal(self) -> Proposal:
        proposal = Proposal()
        item_type = self._item_type(proposal)
        TitleNormalizer(self._csl).into(proposal)
        CreatorNormalizer(self._csl).into(proposal)
        DateNormalizer(self._csl, item_type).into(proposal)
        ContainerNormalizer(self._csl, item_type).into(proposal)
        IdentifierNormalizer(self._csl, self._pdf_isbns).into(proposal)
        return proposal

    def _item_type(self, proposal: Proposal) -> str:
        record = CslRecord(self._csl)
        if record.item_type is None:
            proposal.flag(f"CSL type {record.csl_type!r} maps to no item type; set itemType by hand")
            return ""
        proposal.set("itemType", record.item_type)
        return record.item_type


def _roman_to_int(numeral: str) -> int:
    total = 0
    for position, character in enumerate(numeral):
        value = _ROMAN_VALUES[character]
        next_position = position + 1
        following = _ROMAN_VALUES.get(numeral[next_position:next_position + 1], 0)
        total += -value if value < following else value
    return total
