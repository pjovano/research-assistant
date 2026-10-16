from __future__ import annotations

from pathlib import Path

from _vault.machine import MACHINE_CONFIG_PATH, load_machine_config
from _vault.root_errors import VaultRootNotFound

OBSIDIAN_VAULT_NAME = "research vault"
VAULT_DIR_KEY = "vault_dir"
DEFAULT_VAULT_ROOT = Path.home() / "Documents"
MACHINE_PATH_OVERRIDES = (VAULT_DIR_KEY, "rag_dir")


class ConfiguredVault:
    def __init__(self, machine: dict) -> None:
        self._machine = machine

    def resolved(self) -> Path:
        candidate = self._named()
        if not (candidate / OBSIDIAN_VAULT_NAME).is_dir():
            raise VaultRootNotFound(f"{candidate} holds no {OBSIDIAN_VAULT_NAME}/; "
                                    f"name the vault in {MACHINE_CONFIG_PATH} under {VAULT_DIR_KEY}")
        return candidate

    def _named(self) -> Path:
        value = self._machine.get(VAULT_DIR_KEY)
        return Path(value).expanduser() if value else DEFAULT_VAULT_ROOT


class OnDemandDirectories:
    def __init__(self, directories: tuple[Path, ...]) -> None:
        self._directories = directories

    def ensure(self) -> None:
        for directory in self._directories:
            directory.mkdir(parents=True, exist_ok=True)


MACHINE = load_machine_config()
VAULT_ROOT = ConfiguredVault(MACHINE).resolved()
OBSIDIAN_VAULT_DIR = VAULT_ROOT / OBSIDIAN_VAULT_NAME


def _machine_path(key: str, default: Path) -> Path:
    value = MACHINE.get(key)
    return Path(value).expanduser() if value else default


LIBRARY_DIR = VAULT_ROOT / "library"
VOLUMES_DIR = LIBRARY_DIR / "volumes"
CORPUS_DIR = OBSIDIAN_VAULT_DIR / "corpus"
TRANSCRIPTS_DIR = CORPUS_DIR / "talk transcripts"
BIBLIOGRAPHIES_FOLDER = "bibliographies"
BIBLIOGRAPHIES_DIR = OBSIDIAN_VAULT_DIR / BIBLIOGRAPHIES_FOLDER
READING_LISTS_FOLDER = "4 reading lists"
WRITING_DIR = OBSIDIAN_VAULT_DIR / "writing"
ATOMIC_NOTES_FOLDER = "1 notes"
PROJECT_FILES_FOLDER = "2 projects"
INBOX_DIR = Path.home() / "Desktop" / "inbox"
RAG_DIR = _machine_path("rag_dir", MACHINE_CONFIG_PATH.parent / "rag")
CHROMA_DIR = RAG_DIR / "chroma"
SCRATCH_DIR = MACHINE_CONFIG_PATH.parent / "cache"

_CREATED_ON_DEMAND = (BIBLIOGRAPHIES_DIR, CORPUS_DIR, TRANSCRIPTS_DIR, RAG_DIR, CHROMA_DIR)


def ensure_dirs() -> None:
    OnDemandDirectories(_CREATED_ON_DEMAND).ensure()
