from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

Device = Literal["mps", "cuda", "cpu"]


class Accelerator(Protocol):
    def device(self) -> Device: ...

    def reachable(self) -> str | None: ...


class Trash(Protocol):
    def discard(self, path: Path) -> None: ...


class SyncedFolder(Protocol):
    def conflict_copies(self, directory: Path) -> list[Path]: ...

    def not_downloaded(self, path: Path) -> bool: ...


class Locations(Protocol):
    @property
    def vault_root(self) -> Path: ...

    @property
    def inbox(self) -> Path: ...

    @property
    def state_dir(self) -> Path: ...

    @property
    def rag_dir(self) -> Path: ...
