from __future__ import annotations

import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

from _support import PROJECT_ROOT, SKILLS_DIR

LIB_DIR = PROJECT_ROOT / "lib"

LIBRARY_FACADES = ("annotate", "citation_graph", "machine_health", "identifiers", "pagetext", "providers", "rag",
                   "references", "titlecase", "vault", "zotero")

LIBRARY_PACKAGES = ("_annotate", "_drive", "_graph", "_health", "_pagetext", "_ports", "_rag", "_references", "_vault",
                    "_writing")

ENTRY_SCRIPTS = (
    "cite-links/scripts/cite.py",
    "cite-links/scripts/graph.py",
    "classify-and-place/scripts/bibliographies.py",
    "clean-pdfs/scripts/clean.py",
    "discover/scripts/discover.py",
    "edit-drafts/scripts/drafts.py",
    "extract-chapters/scripts/volumes.py",
    "extract-corpus/scripts/extract.py",
    "file-pdfs/scripts/file.py",
    "ingest/scripts/ingest.py",
    "machine-health/scripts/health.py",
    "manage-projects/scripts/projects.py",
    "answer-questions/scripts/verify.py",
    "search/scripts/search.py",
    "search/server.py",
    "take-notes/scripts/notes.py",
    "transcribe-talks/scripts/transcribe.py",
    "vault-audit/scripts/audit.py",
)

VAULT_PUBLIC_NAMES = (
    "ARTICLE_PAGE_THRESHOLD", "BIBLIOGRAPHIES_DIR", "BIBLIOGRAPHIES_FOLDER", "BibliographySpan", "CHROMA_DIR", "CITATION_LINK_MARK",
    "CORPUS_DIR", "CreatorMissing", "EntryListSpans", "ExtractionRecordsUnreadable", "FOOTNOTE_DEFINITION_RE",
    "FOOTNOTE_MARK_RE", "GLYPHS_DIRECTORY", "OCCURRENCES_CACHE_NAME", "PIXELS_CACHE_NAME", "RECORDS_FILE_NAME",
    "RENDER_NAME", "REVIEWED_KEY", "ReviewedBasenames", "ReviewedSweep", "ScratchSweeps",
    "FootnoteCallSites", "GuardedNote", "HEADING_RE", "ATOMIC_NOTES_FOLDER", "PROJECT_FILES_FOLDER",
    "INBOX_DIR", "LIBRARY_DIR", "LibraryPdf", "MACHINE", "MAX_BIBLIOGRAPHY_HEADING_CHARS",
    "MAX_BIBLIOGRAPHY_HEADING_WORDS", "NoteChangedOnDisk", "OBSIDIAN_COMMENT_RE", "RAG_DIR", "READING_LISTS_FOLDER",
    "RESOLVED_PATH_NAMES", "ReplacementFile",
    "SCRATCH_DIR", "SOURCE_ROLES", "SOURCE_TYPES", "TRANSCRIPTS_DIR", "UNCITABLE_FIELD", "UNCITABLE_TOKEN",
    "ScratchEntries", "StoredNote", "VAULT_ROOT", "VOLUMES_DIR", "WIKILINK_RE", "WRITING_DIR", "basename_of",
    "bibliography_conflict_copies", "bibliography_folders", "body_after_pdf_link", "body_after_source_link",
    "citekey", "citekey_year", "commentary_target", "conflict_copies", "creator_surnames", "ensure_dirs",
    "field_topics", "format_creator", "held_note_exists", "held_note_path", "is_bibliography_heading",
    "is_notes_heading", "join_note",
    "library_conflict_copies",
    "library_filename", "library_filename_verbatim",
    "list_bibliographies", "list_corpus_files", "list_held_notes", "list_markdown", "list_pdfs", "list_transcripts",
    "list_placed_writing",
    "locate_pdf", "names_notes_section", "nfc", "note_path_for", "split_note",
    "normalize_caps_name", "parse_library_filename", "parse_note",
    "corpus_path", "pdf_link_of", "pdf_path", "read_frontmatter", "read_frontmatter_only", "sanitize_filename_part",
    "section_content",
    "section_pattern", "strip_subtitle", "transcript_path", "unique_citekey", "upsert_pdf_link", "wikilink_target",
    "without_section", "write_frontmatter",
)


class EntryScript:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def relative_path(self) -> str:
        return self._path.relative_to(SKILLS_DIR).as_posix()

    @property
    def directory(self) -> Path:
        return self._path.parent

    def imported(self):
        name = f"entry_{self._path.stem}"
        spec = importlib.util.spec_from_file_location(name, self._path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def discovered() -> list["EntryScript"]:
        paths = sorted(SKILLS_DIR.glob("*/scripts/*.py")) + sorted(SKILLS_DIR.glob("*/server.py"))
        return [EntryScript(path) for path in paths]


class ImportPath:
    @staticmethod
    def activate(directories: list[Path]) -> None:
        for directory in directories:
            entry = str(directory)
            if entry not in sys.path:
                sys.path.insert(0, entry)


ImportPath.activate([LIB_DIR] + [script.directory for script in EntryScript.discovered()])


class TestLibraryModulesImport(unittest.TestCase):
    def test_every_facade_imports(self) -> None:
        for name in LIBRARY_FACADES:
            with self.subTest(facade=name):
                self.assertIsNotNone(importlib.import_module(name))

    def test_every_private_package_imports(self) -> None:
        for name in LIBRARY_PACKAGES:
            with self.subTest(package=name):
                self.assertIsNotNone(importlib.import_module(name))


class TestEntryScriptsImport(unittest.TestCase):
    def test_the_discovered_scripts_are_the_pinned_ones(self) -> None:
        discovered = [script.relative_path for script in EntryScript.discovered()]
        self.assertEqual(sorted(ENTRY_SCRIPTS), sorted(discovered))

    def test_every_entry_script_imports(self) -> None:
        for script in EntryScript.discovered():
            with self.subTest(script=script.relative_path):
                self.assertIsNotNone(script.imported())


class TestVaultFacade(unittest.TestCase):
    def test_the_public_surface_is_exactly_the_pinned_names(self) -> None:
        import vault
        self.assertEqual(set(VAULT_PUBLIC_NAMES), set(vault.__all__))

    def test_every_exported_name_is_reachable_on_the_facade(self) -> None:
        import vault
        unreachable = [name for name in vault.__all__ if not hasattr(vault, name)]
        self.assertEqual([], unreachable)


if __name__ == "__main__":
    unittest.main()
