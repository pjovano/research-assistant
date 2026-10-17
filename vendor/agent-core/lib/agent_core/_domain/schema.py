from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_core._domain.delegation import DelegationFields
from agent_core._domain.fields import JsonFields
from agent_core._domain.manifest import DomainManifest, JsonFile

MANIFEST_KEYS = ("name", "summary", "handles", "entry_skills", "exposure", "folders", "vault", "policy",
                 "unattended")


@dataclass(frozen=True)
class ValidManifest:
    manifest: DomainManifest
    delegation: DelegationFields

    @classmethod
    def read(cls, path: Path) -> ValidManifest:
        fields = JsonFields(JsonFile(path).values(), str(path))
        fields.refuse_unknown(MANIFEST_KEYS)
        return cls(DomainManifest.parsed(path, fields), DelegationFields.parsed(fields))

    @property
    def directory(self) -> Path:
        return self.manifest.path.expanduser().resolve().parent
