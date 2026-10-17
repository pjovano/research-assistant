from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from agent_core._domain.delegation import RISKS, UNTRUSTED_CONTENT, EntrySkill
from agent_core._domain.fields import ManifestError
from agent_core._domain.home import HomeRelative
from agent_core._domain.schema import ValidManifest

SKILLS_DIR = Path(".claude") / "skills"
SKILL_FILE = "SKILL.md"
FRONTMATTER_FENCE = "---"
ALLOWED_TOOLS_KEY = "allowed-tools:"
LIST_ITEM = "- "
TOOL_SEPARATOR = re.compile(r",(?![^()]*\))")
WEB = "web"
CAPABILITY_OF_TOOL = {"WebSearch": WEB, "WebFetch": WEB}
LISTED = "domains"
REFUSED = "refused"


class SkillFile:
    def __init__(self, domain_directory: Path, skill: str) -> None:
        self.path = domain_directory / SKILLS_DIR / skill / SKILL_FILE

    def capabilities(self) -> list[str]:
        tools = (self._tool_name(entry) for entry in self._allowed_tools())
        return sorted({CAPABILITY_OF_TOOL[tool] for tool in tools if tool in CAPABILITY_OF_TOOL})

    def _allowed_tools(self) -> list[str]:
        lines = self._frontmatter()
        start = next((index for index, line in enumerate(lines) if line.startswith(ALLOWED_TOOLS_KEY)), None)
        if start is None:
            return []
        inline = lines[start].removeprefix(ALLOWED_TOOLS_KEY).strip()
        if inline:
            return TOOL_SEPARATOR.split(inline)
        return [line.strip().removeprefix(LIST_ITEM) for line in self._list_after(lines, start)]

    @staticmethod
    def _list_after(lines: list[str], start: int) -> list[str]:
        following = lines[start + 1:]
        end = next((index for index, line in enumerate(following) if not line.strip().startswith(LIST_ITEM)),
                   len(following))
        return following[:end]

    @staticmethod
    def _tool_name(entry: str) -> str:
        return entry.strip().strip("\"'").split("(", 1)[0].strip()

    def _frontmatter(self) -> list[str]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise ManifestError(f"{self.path}: the entry skill's file cannot be read: {error.strerror}") from error
        if not lines or lines[0] != FRONTMATTER_FENCE or FRONTMATTER_FENCE not in lines[1:]:
            return []
        return lines[1:lines.index(FRONTMATTER_FENCE, 1)]


class ExposureCheck:
    def __init__(self, manifest: ValidManifest) -> None:
        self._manifest = manifest

    def listed_skills(self) -> list[dict]:
        return [self._listed(skill) for skill in self._manifest.delegation.entry_skills]

    def _listed(self, skill: EntrySkill) -> dict:
        capabilities = SkillFile(self._manifest.directory, skill.name).capabilities()
        self._refuse_every_risk(skill)
        self._refuse_undeclared_untrusted_content(skill, capabilities)
        return {**skill.as_dict(), "capabilities": capabilities}

    def _refuse_every_risk(self, skill: EntrySkill) -> None:
        if skill.declares_every_risk():
            raise self._refusal(skill, f"declares all three risks, {list(RISKS)}: no session may hold private "
                                       "data, untrusted content, and a way to send outward at once")

    def _refuse_undeclared_untrusted_content(self, skill: EntrySkill, capabilities: list[str]) -> None:
        if WEB in capabilities and not skill.declares(UNTRUSTED_CONTENT):
            raise self._refusal(skill, f"has the `{WEB}` capability and does not declare `{UNTRUSTED_CONTENT}`")

    def _refusal(self, skill: EntrySkill, problem: str) -> ManifestError:
        return ManifestError(f"{self._manifest.manifest.path}: entry skill {skill.name!r} {problem}")


class Registry:
    def __init__(self, manifest_paths: Sequence[Path]) -> None:
        self._manifest_paths = manifest_paths

    def as_dict(self) -> dict:
        outcomes = [self._outcome(path) for path in self._manifest_paths]
        return {key: [outcome[key] for outcome in outcomes if key in outcome] for key in (LISTED, REFUSED)}

    def _outcome(self, path: Path) -> dict:
        try:
            return {LISTED: self._entry(ValidManifest.read(path))}
        except ManifestError as error:
            return {REFUSED: {"manifest": HomeRelative(path).text(), "error": str(error)}}

    @staticmethod
    def _entry(manifest: ValidManifest) -> dict:
        delegation = manifest.delegation.as_dict()
        return {"name": manifest.manifest.name, "summary": manifest.manifest.summary,
                "directory": HomeRelative(manifest.directory).text(), **delegation,
                "entry_skills": ExposureCheck(manifest).listed_skills()}
