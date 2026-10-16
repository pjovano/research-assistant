from __future__ import annotations

from _corpus import FrozenCorpus

SHOUTED_NAMES = [
    "PAUL K. FEYERABEND", "MacFarlane", "van Fraassen", "IBM", "MCDOWELL",
    "O'NEILL", "JEAN-PIERRE DUPUY", "de Finetti", "", "McDOWELL", "ANSCOMBE",
]

SUBTITLED_TITLES = [
    "Naming and Necessity",
    "Structure and Categoricity: Determinacy of Reference and Truth-Value",
    "Special Sciences (Or: The Disunity of Science as a Working Hypothesis)",
    "Either-Or",
    "Truth-Value Gaps",
    "Kind-Crossing — A Study",
    "The Logic of Scientific Discovery – Second Edition",
    "Mathematics as a Science of Quantity - An Essay",
    "Being and Time",
    "A Very Long Title With No Subtitle Separator Anywhere In It At All Really",
]

CITEKEY_SURNAMES = [
    "Cantù", "Schrödinger", "Bermúdez", "Gödel", "Poincaré", "Cavaillès",
    "Grattan-Guinness", "Hettig-Rolfe", "Dutilh Novaes", "Łukasiewicz",
    "Kierkegaard", "Ørsted", "Weiß",
]

FILENAME_PARTS = ['A/B: C?', 'Plain', 'x<y>z|w*v"u']

LIBRARY_FILENAMES = [
    "Kripke - 1980 - Naming and Necessity.pdf",
    "A and B - 1999 - Title.pdf",
    "not a library name.pdf",
    "Smith - 12 - Short Year.pdf",
]

WIKILINK_VALUES = ["[[Being]]", "[[A|B]]", "bare", "", "[[X#h]]"]


class NamingSnapshot:
    name = "vault_naming"

    def build(self) -> dict:
        import vault
        return {p.basename: self._row(vault, p) for p in FrozenCorpus.pairs()}

    def _row(self, vault, pair) -> dict:
        sidecar = pair.sidecar
        surnames = self._surnames(sidecar)
        year = str(sidecar.get("year") or "")
        title = str(sidecar.get("title") or "")
        return {
            "creator": vault.format_creator(surnames),
            "citekey_year": vault.citekey_year(sidecar),
            "citekey": vault.citekey(surnames[0] if surnames else "", vault.citekey_year(sidecar)),
            "stripped_title": vault.strip_subtitle(title),
            "library_filename_verbatim": vault.library_filename_verbatim(surnames, year, title),
        }

    def _surnames(self, sidecar: dict) -> list[str]:
        return [a.get("lastName", "") for a in (sidecar.get("authors") or [])]


class NamingEdgeCaseSnapshot:
    name = "vault_naming_edge_cases"

    def build(self) -> dict:
        import vault
        return {name: self._applied(vault, name) for name in self._COVERED}

    def _applied(self, vault, name: str) -> dict:
        function = getattr(vault, name)
        return {case: function(*self._arguments(name, case)) for case in self._CASES[name]}

    def _arguments(self, name: str, case: str) -> tuple:
        return (case, "2010") if name == "citekey" else (case,)

    _CASES = {
        "normalize_caps_name": SHOUTED_NAMES,
        "strip_subtitle": SUBTITLED_TITLES,
        "citekey": CITEKEY_SURNAMES,
        "sanitize_filename_part": FILENAME_PARTS,
        "parse_library_filename": LIBRARY_FILENAMES,
        "wikilink_target": WIKILINK_VALUES,
    }
    _COVERED = tuple(_CASES)


class BuildItemSnapshot:
    name = "zotero_build_item"

    def build(self) -> dict:
        import zotero
        return {p.basename: zotero.build_item(self._meta(p)) for p in FrozenCorpus.pairs()}

    def _meta(self, pair) -> dict:
        sidecar, bib = pair.sidecar, pair.bib
        fields = dict(bib)
        fields.pop("orig_year", None)
        return {
            "title": sidecar.get("title", ""),
            "authors": sidecar.get("authors") or [],
            "year": sidecar.get("year", ""),
            "orig_year": sidecar.get("orig_year"),
            "type": sidecar.get("type"),
            "bib": fields,
        }


ALL_SNAPSHOTS = (
    NamingSnapshot(),
    NamingEdgeCaseSnapshot(),
    BuildItemSnapshot(),
)
