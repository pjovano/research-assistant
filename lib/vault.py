from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _vault.citations import (
    MAX_BIBLIOGRAPHY_HEADING_CHARS,
    MAX_BIBLIOGRAPHY_HEADING_WORDS,
    SOURCE_ROLES,
    SOURCE_TYPES,
    UNCITABLE_FIELD,
    UNCITABLE_TOKEN,
    commentary_target,
    field_topics,
    is_bibliography_heading,
    is_notes_heading,
    names_notes_section,
    section_content,
    section_pattern,
    wikilink_target,
    without_section,
)
from _vault.citekeys import citekey, citekey_year, unique_citekey
from _vault.frontmatter import (
    StoredNote,
    body_after_pdf_link,
    body_after_source_link,
    join_note,
    parse_note,
    pdf_link_of,
    read_frontmatter,
    read_frontmatter_only,
    split_note,
    upsert_pdf_link,
    write_frontmatter,
)
from _vault.footnotes import FootnoteCallSites
from _vault.listing import NOTE_SUFFIX, VaultDirectory, VaultTree
from _vault.locating import PDF_SUFFIX, PdfSearch
from _vault.markdown import (
    CITATION_LINK_MARK,
    FOOTNOTE_DEFINITION_RE,
    FOOTNOTE_MARK_RE,
    HEADING_RE,
    OBSIDIAN_COMMENT_RE,
    WIKILINK_RE,
)
from _vault.naming import (
    CreatorMissing,
    basename_of,
    creator_surnames,
    nfc,
    format_creator,
    library_filename,
    library_filename_verbatim,
    normalize_caps_name,
    parse_library_filename,
    sanitize_filename_part,
    strip_subtitle,
)
from _vault.replacement import GuardedNote, NoteChangedOnDisk, ReplacementFile
from _vault.reviewed import RECORDS_FILE_NAME, REVIEWED_KEY, ExtractionRecordsUnreadable, ReviewedBasenames
from _vault.scratch import (
    GLYPHS_DIRECTORY,
    OCCURRENCES_CACHE_NAME,
    PIXELS_CACHE_NAME,
    RENDER_NAME,
    ReviewedSweep,
    ScratchEntries,
    ScratchSweep,
)
from _vault.spans import BibliographySpan, EntryListSpans
from _vault.paths import (
    BIBLIOGRAPHIES_DIR,
    BIBLIOGRAPHIES_FOLDER,
    CHROMA_DIR,
    CORPUS_DIR,
    ATOMIC_NOTES_FOLDER,
    INBOX_DIR,
    LIBRARY_DIR,
    MACHINE,
    MACHINE_CONFIG_PATH,
    MACHINE_PATH_OVERRIDES,
    PROJECT_FILES_FOLDER,
    RAG_DIR,
    READING_LISTS_FOLDER,
    SCRATCH_DIR,
    TRANSCRIPTS_DIR,
    VAULT_ROOT,
    VOLUMES_DIR,
    WRITING_DIR,
    ensure_dirs,
)

__all__ = [
    "ARTICLE_PAGE_THRESHOLD", "BIBLIOGRAPHIES_DIR", "BIBLIOGRAPHIES_FOLDER", "BibliographySpan", "CHROMA_DIR", "CITATION_LINK_MARK",
    "CreatorMissing", "EntryListSpans", "ExtractionRecordsUnreadable", "GLYPHS_DIRECTORY", "OCCURRENCES_CACHE_NAME",
    "PIXELS_CACHE_NAME", "RECORDS_FILE_NAME", "RENDER_NAME", "REVIEWED_KEY", "ReviewedBasenames", "ReviewedSweep",
    "ScratchSweeps",
    "CORPUS_DIR", "FOOTNOTE_DEFINITION_RE", "ATOMIC_NOTES_FOLDER", "FOOTNOTE_MARK_RE", "FootnoteCallSites", "GuardedNote", "HEADING_RE", "INBOX_DIR", "LIBRARY_DIR", "LibraryPdf",
    "MACHINE", "MAX_BIBLIOGRAPHY_HEADING_CHARS", "MAX_BIBLIOGRAPHY_HEADING_WORDS", "NoteChangedOnDisk",
    "OBSIDIAN_COMMENT_RE", "PROJECT_FILES_FOLDER", "RAG_DIR", "READING_LISTS_FOLDER", "RESOLVED_PATH_NAMES", "ReplacementFile", "SCRATCH_DIR",
    "SOURCE_ROLES", "SOURCE_TYPES",
    "ScratchEntries", "StoredNote", "TRANSCRIPTS_DIR", "UNCITABLE_FIELD", "UNCITABLE_TOKEN", "VAULT_ROOT",
    "VOLUMES_DIR", "WIKILINK_RE", "WRITING_DIR", "basename_of", "bibliography_conflict_copies",
    "body_after_pdf_link", "body_after_source_link", "citekey", "citekey_year",
    "commentary_target", "conflict_copies", "corpus_path", "creator_surnames", "ensure_dirs", "field_topics",
    "format_creator", "held_note_exists", "held_note_path", "is_bibliography_heading", "is_notes_heading", "join_note",
    "library_conflict_copies",
    "library_filename", "library_filename_verbatim", "list_bibliographies", "list_corpus_files", "list_held_notes",
    "list_markdown", "list_placed_writing",
    "list_pdfs", "list_transcripts",
    "locate_pdf", "names_notes_section", "nfc", "normalize_caps_name", "note_path_for", "parse_library_filename",
    "parse_note", "pdf_link_of", "pdf_path",
    "read_frontmatter", "read_frontmatter_only", "sanitize_filename_part", "section_content", "section_pattern",
    "split_note", "strip_subtitle", "transcript_path", "unique_citekey", "upsert_pdf_link", "wikilink_target",
    "without_section", "write_frontmatter",
]

ARTICLE_PAGE_THRESHOLD = 40


class NotePaths:
    @staticmethod
    def corpus(basename: str) -> Path:
        return CORPUS_DIR / f"{nfc(basename)}{NOTE_SUFFIX}"

    @staticmethod
    def transcript(basename: str) -> Path:
        return TRANSCRIPTS_DIR / f"{nfc(basename)}{NOTE_SUFFIX}"

    @staticmethod
    def note_path_for(basename: str) -> Path:
        corpus = NotePaths.corpus(basename)
        return corpus if corpus.exists() else NotePaths.transcript(basename)

    @staticmethod
    def is_held(basename: str) -> bool:
        return NotePaths.corpus(basename).exists() or NotePaths.transcript(basename).exists()

    @staticmethod
    def pdf(basename: str) -> Path:
        return LIBRARY_DIR / f"{nfc(basename)}{PDF_SUFFIX}"

    @staticmethod
    def located_pdf(given: str, directories: tuple[Path, ...]) -> Path | None:
        return PdfSearch(given, directories).found()


class LibraryPdf:
    def __init__(self, given: str) -> None:
        self._given = given

    def path(self) -> Path:
        located = NotePaths.located_pdf(self._given, (LIBRARY_DIR,))
        if located is None:
            raise FileNotFoundError(f"no such PDF: {self._given}")
        return located


class VaultListing:
    @staticmethod
    def corpus_files() -> list[Path]:
        return VaultListing.markdown(CORPUS_DIR)

    @staticmethod
    def transcripts() -> list[Path]:
        return VaultListing.markdown(TRANSCRIPTS_DIR)

    @staticmethod
    def held_notes() -> list[Path]:
        return VaultListing.corpus_files() + VaultListing.transcripts()

    @staticmethod
    def placed_writing() -> list[Path]:
        folders = (WRITING_DIR / ATOMIC_NOTES_FOLDER, WRITING_DIR / PROJECT_FILES_FOLDER)
        return [path for folder in folders for path in VaultListing.markdown(folder)]

    @staticmethod
    def bibliographies() -> list[Path]:
        return VaultListing._bibliography_tree().markdown()

    @staticmethod
    def bibliography_conflict_copies() -> list[Path]:
        return VaultListing._bibliography_tree().conflict_copies()

    @staticmethod
    def _bibliography_tree() -> VaultTree:
        return VaultTree(BIBLIOGRAPHIES_DIR, folders_apart=(READING_LISTS_FOLDER,))

    @staticmethod
    def markdown(directory: Path) -> list[Path]:
        return VaultDirectory(directory).markdown()

    @staticmethod
    def pdfs(directory: Path) -> list[Path]:
        return VaultDirectory(directory, CORPUS_DIR).pdfs()

    @staticmethod
    def conflict_copies(directory: Path) -> list[Path]:
        return VaultDirectory(directory, CORPUS_DIR).conflict_copies()

    @staticmethod
    def library_conflict_copies() -> list[str]:
        directories = (CORPUS_DIR, TRANSCRIPTS_DIR, LIBRARY_DIR)
        return sorted(path.name for directory in directories for path in VaultListing.conflict_copies(directory))


corpus_path = NotePaths.corpus
transcript_path = NotePaths.transcript
note_path_for = NotePaths.note_path_for
held_note_path = NotePaths.note_path_for
held_note_exists = NotePaths.is_held
pdf_path = NotePaths.pdf
locate_pdf = NotePaths.located_pdf
list_corpus_files = VaultListing.corpus_files
list_transcripts = VaultListing.transcripts
list_held_notes = VaultListing.held_notes
list_bibliographies = VaultListing.bibliographies
list_placed_writing = VaultListing.placed_writing
bibliography_conflict_copies = VaultListing.bibliography_conflict_copies
list_markdown = VaultListing.markdown
list_pdfs = VaultListing.pdfs
conflict_copies = VaultListing.conflict_copies
library_conflict_copies = VaultListing.library_conflict_copies


class HeldBasenames:
    def __init__(self, directories: tuple[Path, ...]) -> None:
        self._directories = directories

    def keys(self) -> set[str]:
        return {basename_of(pdf) for directory in self._directories for pdf in VaultListing.pdfs(directory)}


class ScratchSweeps:
    @staticmethod
    def stale() -> ScratchSweep:
        return ScratchSweep(SCRATCH_DIR, HeldBasenames((LIBRARY_DIR, VOLUMES_DIR, INBOX_DIR)).keys())

    @staticmethod
    def reviewed() -> ReviewedSweep:
        return ReviewedSweep(SCRATCH_DIR, ReviewedBasenames(LIBRARY_DIR / RECORDS_FILE_NAME))


class VaultCommandLine:
    _DESCRIPTION = ("print the resolved vault paths; `sweep` lists the scratch entries keyed to no held or inbox PDF, "
                    "or with --reviewed the page renders and font repair caches of each reviewed work")

    def run(self, argv: list[str]) -> None:
        args = self._parser().parse_args(argv)
        args.handler(args)

    def _parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="vault.py", description=self._DESCRIPTION)
        parser.set_defaults(handler=self._print_paths)
        commands = parser.add_subparsers(dest="command")
        sweep = commands.add_parser("sweep", help="list every scratch entry whose key names no PDF in the library, "
                                                  "the volumes, or the inbox")
        sweep.add_argument("--reviewed", action="store_true",
                           help="list instead the page renders and font repair caches of each work whose extraction "
                                "record carries a reviewed date; its engine layouts are kept")
        sweep.add_argument("--apply", action="store_true", help="delete the listed entries; without it, delete nothing")
        sweep.set_defaults(handler=self._sweep)
        return parser

    def _sweep(self, args: argparse.Namespace) -> None:
        sweep = ScratchSweeps.reviewed() if args.reviewed else ScratchSweeps.stale()
        entries = sweep.entries()
        report = {"scratch_dir": str(SCRATCH_DIR), "applied": args.apply,
                  sweep.LABEL: [entry.as_dict() for entry in entries]}
        if args.apply:
            sweep.delete(entries)
        print(json.dumps(report, indent=2, ensure_ascii=False))

    def _print_paths(self, args: argparse.Namespace) -> None:
        for label, value in _RESOLVED_PATHS:
            print(f"{label:<18} = {value}")
        found = "found" if MACHINE else "absent or empty -- using synced defaults"
        print(f"{'MACHINE_CONFIG':<18} = {MACHINE_CONFIG_PATH} ({found})")
        for key in MACHINE_PATH_OVERRIDES:
            if MACHINE.get(key):
                print(f"  override: {key} = {MACHINE[key]}")


_RESOLVED_PATHS = (
    ("VAULT_ROOT", VAULT_ROOT),
    ("LIBRARY_DIR", LIBRARY_DIR),
    ("VOLUMES_DIR", VOLUMES_DIR),
    ("CORPUS_DIR", CORPUS_DIR),
    ("TRANSCRIPTS_DIR", TRANSCRIPTS_DIR),
    ("BIBLIOGRAPHIES_DIR", BIBLIOGRAPHIES_DIR),
    ("WRITING_DIR", WRITING_DIR),
    ("INBOX_DIR", INBOX_DIR),
    ("RAG_DIR", RAG_DIR),
    ("SCRATCH_DIR", SCRATCH_DIR),
)
RESOLVED_PATH_NAMES = tuple(name for name, _path in _RESOLVED_PATHS)


if __name__ == "__main__":
    VaultCommandLine().run(sys.argv[1:])
