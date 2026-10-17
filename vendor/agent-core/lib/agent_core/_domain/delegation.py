from __future__ import annotations

from dataclasses import dataclass

from agent_core._domain.fields import JsonFields

PRIVATE_DATA = "private_data"
UNTRUSTED_CONTENT = "untrusted_content"
SENDS_OUTWARD = "sends_outward"
RISKS = (PRIVATE_DATA, UNTRUSTED_CONTENT, SENDS_OUTWARD)
UNATTENDED_READ_ONLY = "read-only"
UNATTENDED_NONE = "none"
UNATTENDED_WRITE = "write"
DOMAIN_UNATTENDED_LEVELS = (UNATTENDED_READ_ONLY, UNATTENDED_NONE)
SKILL_UNATTENDED_LEVELS = (*DOMAIN_UNATTENDED_LEVELS, UNATTENDED_WRITE)
HANDLE_KEYS = ("kind", "examples")
UNATTENDED_KEYS = ("default", "skills")


@dataclass(frozen=True)
class RequestKind:
    kind: str
    examples: tuple[str, ...]

    @classmethod
    def parsed(cls, fields: JsonFields) -> RequestKind:
        fields.refuse_unknown(HANDLE_KEYS)
        return cls(fields.text("kind"), fields.texts("examples"))

    def as_dict(self) -> dict:
        return {"kind": self.kind, "examples": list(self.examples)}


@dataclass(frozen=True)
class EntrySkill:
    name: str
    exposure: tuple[str, ...]
    unattended: str

    def declares(self, risk: str) -> bool:
        return risk in self.exposure

    def declares_every_risk(self) -> bool:
        return all(self.declares(risk) for risk in RISKS)

    def as_dict(self) -> dict:
        return {"name": self.name, "exposure": list(self.exposure), "unattended": self.unattended}


@dataclass(frozen=True)
class UnattendedLevels:
    default: str
    per_skill: dict[str, str]

    @classmethod
    def parsed(cls, fields: JsonFields) -> UnattendedLevels:
        if isinstance(fields.value("unattended", UNATTENDED_READ_ONLY), str):
            return cls(fields.optional_choice("unattended", DOMAIN_UNATTENDED_LEVELS) or UNATTENDED_READ_ONLY, {})
        section = fields.section("unattended")
        section.refuse_unknown(UNATTENDED_KEYS)
        default = section.optional_choice("default", DOMAIN_UNATTENDED_LEVELS) or UNATTENDED_READ_ONLY
        return cls(default, PerSkillLevels(section.section("skills")).levels())

    def of(self, skill: str) -> str:
        return self.per_skill.get(skill, self.default)


class PerSkillLevels:
    def __init__(self, fields: JsonFields) -> None:
        self._fields = fields

    def levels(self) -> dict[str, str]:
        return {skill: self._fields.choice(skill, SKILL_UNATTENDED_LEVELS) for skill in self._fields.keys()}


@dataclass(frozen=True)
class DelegationFields:
    handles: tuple[RequestKind, ...]
    entry_skills: tuple[EntrySkill, ...]
    unattended: str

    @classmethod
    def parsed(cls, fields: JsonFields) -> DelegationFields:
        names = UniqueNames(fields).entry_skills()
        exposure = Exposure(fields.section("exposure"), names).by_skill()
        levels = UnattendedLevels.parsed(fields)
        StraySkills(fields, names).refuse(levels.per_skill, "`unattended.skills`")
        handles = tuple(RequestKind.parsed(record) for record in fields.records("handles"))
        skills = tuple(EntrySkill(name, exposure[name], levels.of(name)) for name in names)
        return cls(handles, skills, levels.default)

    def as_dict(self) -> dict:
        return {"handles": [handle.as_dict() for handle in self.handles],
                "entry_skills": [skill.as_dict() for skill in self.entry_skills], "unattended": self.unattended}


class UniqueNames:
    def __init__(self, fields: JsonFields) -> None:
        self._fields = fields

    def entry_skills(self) -> tuple[str, ...]:
        names = self._fields.texts("entry_skills")
        if len(set(names)) != len(names):
            raise self._fields.refuse("`entry_skills` names one skill twice")
        return names


class Exposure:
    def __init__(self, fields: JsonFields, entry_skills: tuple[str, ...]) -> None:
        self._fields = fields
        self._entry_skills = entry_skills

    def by_skill(self) -> dict[str, tuple[str, ...]]:
        StraySkills(self._fields, self._entry_skills).refuse(self._fields.keys(), "`exposure`")
        return {name: self._risks_of(name) for name in self._entry_skills}

    def _risks_of(self, skill: str) -> tuple[str, ...]:
        if skill not in self._fields.keys():
            raise self._fields.refuse(f"entry skill {skill!r} declares no exposure; declare `[]` if it carries "
                                      "no risk")
        risks = self._fields.texts(skill)
        unknown = sorted(set(risks) - set(RISKS))
        if unknown:
            raise self._fields.refuse(f"`{skill}` names unknown risks {unknown}; the risks are {list(RISKS)}")
        return risks


class StraySkills:
    def __init__(self, fields: JsonFields, entry_skills: tuple[str, ...]) -> None:
        self._fields = fields
        self._entry_skills = entry_skills

    def refuse(self, named: object, where: str) -> None:
        stray = sorted(set(named) - set(self._entry_skills))
        if stray:
            raise self._fields.refuse(f"{where} names {stray}, which `entry_skills` does not list")
