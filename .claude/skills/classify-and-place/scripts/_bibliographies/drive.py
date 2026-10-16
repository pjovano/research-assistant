from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

import vault
from synced_folder import ConfiguredSyncedFolder, SyncedFolderUnavailable

from _drive.script import ScriptRun, SkillScript
from _drive.steps import StepGuard
from _drive.work import CLASSIFY_ANSWERS_NAME, Halt, IngestWorks, SetAside, Unwritten, WorkDirectory
from _ports.host import SyncedFolder
from _vault.frontmatter import FrontmatterFields
from _vault.scratch import INGEST_ENTRY

from .catalogue import AuthorCatalogue, MostSpecificField
from .tree import BibliographyTree
from .notes import Bibliographies, Corpus, CorpusNote
from .opening import CLASSIFICATION_FIELDS, Classification
from .placement import TRANSCRIPT_SOURCE_TYPE

BIBLIOGRAPHIES_SCRIPT = Path(__file__).resolve().parents[1] / "bibliographies.py"
SECONDARY_ROLE = "secondary"
COMMENTARY_FIELD = "commentary_on"
DESCRIPTION_FIELD = "description"
NOMINATION_FIELD = "nomination"
NOMINATIONS_NAME = "nominations.json"
NOTES_FIELD = "notes"
PLACED_ON_FIELD = "placed_on"
EXIT_UNRESOLVED = 2
EXIT_REPEATED_WORK_LIST = 4


class BibliographiesScript(SkillScript):
    def __init__(self, interpreter: str = sys.executable) -> None:
        super().__init__(BIBLIOGRAPHIES_SCRIPT, interpreter)


def wikilink(target: str) -> str:
    return json.dumps(f"[[{target}]]", ensure_ascii=False)


def bare_name(given: str) -> str:
    return vault.nfc(given.strip().removeprefix("[[").removesuffix("]]"))


class ClassifierAnswers:
    def __init__(self, answers: dict, note: CorpusNote, field: MostSpecificField) -> None:
        self._answers = answers
        self._note = note
        self._field = field

    @classmethod
    def read(cls, path: Path, note: CorpusNote, field: MostSpecificField) -> ClassifierAnswers:
        try:
            return cls(json.loads(path.read_text(encoding="utf-8")), note, field)
        except FileNotFoundError:
            raise Unwritten(f"the work classifier wrote no answers file: {path}") from None
        except (OSError, ValueError):
            raise SetAside(f"the work classifier wrote no readable answers file: {path}") from None

    @property
    def bibliographies(self) -> list[str]:
        return self._field.of([bare_name(name) for name in self._answers.get("field") or []], self._source_role)

    @property
    def _source_role(self) -> str | None:
        return self._answers.get("source_role")

    @property
    def nomination(self) -> dict | None:
        given = self._answers.get(NOMINATION_FIELD)
        if not (isinstance(given, dict) and given.get("name")) or self._field.keeps_to_the_catalogue(self._source_role):
            return None
        return {**given, "works": [self._note.basename], PLACED_ON_FIELD: self.bibliographies}

    @property
    def notes(self) -> list[str]:
        return [str(note) for note in self._answers.get(NOTES_FIELD) or []]

    def require_settled(self, held: set[str]) -> None:
        questions = self._answers.get("questions") or []
        if questions:
            raise SetAside("the work classifier asks: " + " | ".join(str(question) for question in questions))
        self._require_vocabularies()
        unknown = [name for name in self.bibliographies if name not in held]
        if unknown:
            raise SetAside(f"field: names bibliographies that do not exist yet: {unknown}; the shaper creates one "
                           "from a nomination, never field:")

    def _require_vocabularies(self) -> None:
        source_type, source_role = self._answers.get("source_type"), self._answers.get("source_role")
        if source_type not in vault.SOURCE_TYPES or source_role not in vault.SOURCE_ROLES:
            raise SetAside(f"a value outside the vocabularies: source_type {source_type!r}, "
                           f"source_role {source_role!r}")
        if (source_type == TRANSCRIPT_SOURCE_TYPE) != self._note.is_transcript:
            raise SetAside(f"source_type {source_type!r} on a {self._kind_of_note()}: a transcript, and only a "
                           "transcript, takes transcript")
        if self._answers.get(COMMENTARY_FIELD) and source_role != SECONDARY_ROLE:
            raise SetAside(f"a commentary roled {source_role!r}: a commentary is secondary")

    def _kind_of_note(self) -> str:
        return "transcript" if self._note.is_transcript else "corpus file"

    def fields_beside(self, placed: list[str]) -> dict:
        names = self._field.of([*placed, *self.bibliographies], self._source_role)
        fields = {"source_type": self._answers["source_type"], "source_role": self._answers["source_role"],
                  "field": [wikilink(name) for name in names]}
        return {**fields, **self._commentary_field(), **self._description_field()}

    def _commentary_field(self) -> dict:
        commentary = self._answers.get(COMMENTARY_FIELD)
        return {COMMENTARY_FIELD: wikilink(bare_name(commentary))} if commentary else {}

    def _description_field(self) -> dict:
        description = str(self._answers.get(DESCRIPTION_FIELD) or "").strip()
        return {DESCRIPTION_FIELD: json.dumps(description, ensure_ascii=False)} if description else {}

    def matches(self, meta: dict) -> bool:
        written_values = (meta.get("source_type"), meta.get("source_role"))
        placed = {vault.nfc(topic) for topic in vault.field_topics(meta)}
        same_values = written_values == (self._answers["source_type"], self._answers["source_role"])
        return same_values and set(self.bibliographies) <= placed


class ClassificationWrite:
    def __init__(self, basename: str) -> None:
        self._stored = vault.GuardedNote(vault.held_note_path(basename))
        self._before: str | None = None

    def meta(self) -> dict:
        meta, _body = vault.parse_note(self._stored.text())
        return meta

    def write(self, fields: dict) -> None:
        self._before = self._stored.text()
        block, body = vault.split_note(self._before)
        self._stored.replace(vault.join_note(FrontmatterFields().replaced_in_place(block, fields), body))

    def undo(self) -> None:
        if self._before is not None:
            self._stored.replace(self._before)


class Placing:
    def __init__(self, basename: str, script: SkillScript) -> None:
        self._basename = basename
        self._script = script

    def placed(self, bibliographies: list[str]) -> list[str]:
        if not bibliographies:
            return []
        self._run("place", self._basename, "--json")
        return self._run("place", self._basename, "--json", "--apply")["bibliographies"]

    def _run(self, *args: str) -> dict:
        run = self._script.run(*args)
        if run.ok:
            return run.payload()
        raise SetAside(self._refusal(run))

    @staticmethod
    def _refusal(run: ScriptRun) -> str:
        if run.returncode == EXIT_REPEATED_WORK_LIST:
            return f"a bibliography carries its list of works twice; merge the two lists by hand: {run.tail}"
        if run.returncode == EXIT_UNRESOLVED:
            return f"`place` names a bibliography or a corpus file that does not exist: {run.tail}"
        return f"`place` failed: {run.tail}"


class NominationLedger:
    def __init__(self, path: Path) -> None:
        self._path = path

    def record(self, nomination: dict) -> None:
        kept = [item for item in self._read() if item.get("works") != nomination["works"]]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"nominations": [*kept, nomination]}
        self._path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _read(self) -> list[dict]:
        try:
            return list(json.loads(self._path.read_text(encoding="utf-8")).get("nominations", []))
        except (OSError, ValueError):
            return []


class BibliographyConflicts:
    def __init__(self, folder: Callable[[], SyncedFolder]) -> None:
        self._folder = folder

    def halt_on_any(self) -> None:
        copies = self._copies()
        if copies:
            raise Halt(f"iCloud left conflict copies among the bibliographies; merge and delete each: {copies}")

    def _copies(self) -> list[str]:
        try:
            folder = self._folder()
        except SyncedFolderUnavailable as unavailable:
            raise Halt(str(unavailable)) from unavailable
        return [path.name for directory in vault.bibliography_folders() for path in folder.conflict_copies(directory)]


class ClassifyStep:
    def __init__(self, basename: str, answers_path: Path, script: SkillScript, ledger: NominationLedger) -> None:
        self._basename = basename
        self._answers_path = answers_path
        self._script = script
        self._ledger = ledger

    def run(self) -> dict:
        bibliographies = Bibliographies()
        work = Corpus().note(self._basename)
        field = MostSpecificField(AuthorCatalogue(bibliographies).maps_of(work), BibliographyTree(bibliographies.entries()))
        answers = ClassifierAnswers.read(self._answers_path, work, field)
        answers.require_settled(bibliographies.names())
        note = ClassificationWrite(self._basename)
        self._write(note, answers)
        placed = self._placed(note, answers)
        return {"state": "placed", "bibliographies": placed, "nominated": self._recorded(answers),
                "notes": answers.notes}

    def _recorded(self, answers: ClassifierAnswers) -> bool:
        if answers.nomination is None:
            return False
        self._ledger.record(answers.nomination)
        return True

    def _placed(self, note: ClassificationWrite, answers: ClassifierAnswers) -> list[str]:
        try:
            return Placing(self._basename, self._script).placed(answers.bibliographies)
        except SetAside:
            note.undo()
            raise

    @staticmethod
    def _write(note: ClassificationWrite, answers: ClassifierAnswers) -> None:
        meta = note.meta()
        if not Classification(meta).is_written:
            note.write(answers.fields_beside(vault.field_topics(meta)))
        elif not answers.matches(meta):
            written = {field: meta.get(field) for field in CLASSIFICATION_FIELDS}
            raise SetAside(f"the corpus file is already classified otherwise: {written}")


class ClassifyDriver:
    def __init__(self, script: SkillScript | None = None, works_dir: Path | None = None,
                 synced_folder: Callable[[], SyncedFolder] | None = None) -> None:
        self._script = script or BibliographiesScript()
        self._works_dir = works_dir or vault.SCRATCH_DIR / INGEST_ENTRY
        self._works = IngestWorks(self._works_dir)
        self._conflicts = BibliographyConflicts(synced_folder or ConfiguredSyncedFolder.of_machine().built)

    def prepare(self, key: str) -> dict:
        return StepGuard("drive-classify").on_work(lambda: self._works.work(key), self._prepared)

    @staticmethod
    def _prepared(work: WorkDirectory) -> dict:
        work.discard(CLASSIFY_ANSWERS_NAME)
        return {"state": "classify", "answers": str(work.path(CLASSIFY_ANSWERS_NAME))}

    def classify(self, key: str, answers_path: Path) -> dict:
        ledger = NominationLedger(self._works_dir / NOMINATIONS_NAME)
        return StepGuard("drive-classify").on_work(
            lambda: self._works.work(key),
            lambda work: self._classified(work, answers_path, ledger))

    def _classified(self, work: WorkDirectory, answers_path: Path, ledger: NominationLedger) -> dict:
        self._conflicts.halt_on_any()
        return ClassifyStep(vault.basename_of(Path(work.pdf)), answers_path, self._script, ledger).run()
