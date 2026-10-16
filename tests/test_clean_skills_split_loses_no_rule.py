from __future__ import annotations

import re
import unittest
from pathlib import Path

from _support import FIXTURES_DIR, PROJECT_ROOT

PRE_SPLIT_DIR = FIXTURES_DIR / "pre-split-skills"
PRE_SPLIT_FILES = (PRE_SPLIT_DIR / "clean-code.txt", PRE_SPLIT_DIR / "clean-prose.txt")
VENDORED_SKILLS_DIR = PROJECT_ROOT / "vendor" / "agent-core" / "skills"
VENDORED_SOUL_FILE = PROJECT_ROOT / "vendor" / "agent-core" / "SOUL.md"
SPLIT_FILES = (VENDORED_SKILLS_DIR / "clean-code" / "SKILL.md", VENDORED_SKILLS_DIR / "clean-prose" / "SKILL.md",
               PROJECT_ROOT / ".claude" / "code-overlay.md", PROJECT_ROOT / ".claude" / "glossary.md",
               VENDORED_SOUL_FILE)
PRE_A6_CONTRACT_FILE = FIXTURES_DIR / "pre-a6-contract" / "rewritten-sentences.txt"
CONTRACT_FILES = (PROJECT_ROOT / "AGENTS.md", VENDORED_SOUL_FILE)
WHITESPACE_RUN = re.compile(r"\s+")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
TABLE_CELL_SEPARATOR = "|"
TABLE_RULE = re.compile(r"^\|(\s*-+\s*\|)+$")
HEADING_MARK = "#"
FENCE = "---"
FRONTMATTER_KEY = re.compile(r"^[a-z]+: ")
DOMAIN_CONTENT_IS_RESEARCH_CONTENT = ("**The vault's domain content is research content:** derived research notes, "
                                     "the substance of a research answer, or the user's own drafts.")
NARRATION_NEEDS_ITS_REASON = ("NEVER narrate an action without its reason: a sentence that announces a step and cites "
                              "no rule or fact withholds why the step is taken.")
INPUT_IS_A_PDF = "**In the vault, `clean-prose` §12's input is a PDF and the work it holds, and its run is a batch.**"
REWORDED = {
    "description: Enforces the vault's prose standard on instruction text, which is AGENTS.md, SKILL.md files, "
    "worker instructions, and any reference file a skill loads. Use this skill before adding or editing any "
    "instruction prose, including a one-sentence change; it also governs how the orchestrator explains its own "
    "work in chat. Not for research content.":
        ("description: Enforces the prose standard on instruction text, which is AGENTS.md, SOUL.md, SKILL.md files, "
         "worker instructions, and any reference file a skill loads. Use this skill before adding or editing any "
         "instruction prose, including a one-sentence change; it also governs how the orchestrator explains its own "
         "work in chat. Not for domain content.",
         DOMAIN_CONTENT_IS_RESEARCH_CONTENT),
    "(The Research Vault section below overrides this for the vault.)":
        ("**The domain's code overlay.** If `.claude/code-overlay.md` exists, read it whole after this file.",
         "In the vault, **Fix what you find** overrides `clean-code`'s **Scope of a change**."),
    "The control plane is the repository this skill lives in.":
        ("The control plane is the repository this code overlay lives in.",),
    "Everything above is the standard for all code in the control plane, and it binds a one-line fix as much as a "
    "new module.":
        ("Everything `clean-code` states is the standard for all code in the control plane, and it binds a one-line "
         "fix as much as a new module.",),
    "This skill is the standard for the vault's instruction layer, the counterpart to `clean-code` with the same "
    "force.":
        ("This skill is the standard for instruction text, the counterpart to `clean-code` with the same force.",),
    "Applies to the vault contract, every `SKILL.md`, every set of worker instructions, and every reference file a "
    "skill loads.":
        ("Applies to the repository's contract, the soul file, every `SKILL.md`, every set of worker instructions, "
         "and every reference file a skill loads.",),
    "| symlink | a relative symbolic link under `.claude/` that resolves to a core unit inside the vendored core | "
    "link (for a symlink), alias, shortcut |":
        ("| symlink | a relative symbolic link under `.claude/` that resolves to a core unit inside the vendored core, "
         "or inside `core/` in `agent-core` itself | link (for a symlink), alias, shortcut |",),
    "Three exceptions bind: `subagent_type` is the Agent tool's literal parameter name and stays as written; a code "
    "or configuration identifier (`vault-rag`, `rag.py`, `RAG_DIR`, `rag_dir`, `itemType`) stays as written; "
    "quoting a banned term to state its ban is not a use.":
        ("Three exceptions bind: `subagent_type` is the Agent tool's literal parameter name and stays as written; a "
         "code or configuration identifier stays as written; quoting a banned term to state its ban is not a use.",
         "The code and configuration identifiers `vault-rag`, `rag.py`, `RAG_DIR`, `rag_dir`, and `itemType` stay "
         "as written."),
    "Length alone NEVER forces a break, and NEVER merge two units to balance length.":
        ("Unless §14's paragraph limit binds the paragraph, length alone NEVER forces a break.",
         "NEVER merge two units to balance length."),
    "An enumeration breaks between its items and NEVER inside one; if its items run about a line each, the list "
    "stays one paragraph at any length.":
        ("**An enumeration breaks between its items and NEVER inside one.**",
         "If its items run about a line each, the list stays one paragraph at any length."),
    "Per Scope, this rule binds research content as well.":
        ("Per Scope, §6's paragraph rules bind domain content as well.", DOMAIN_CONTENT_IS_RESEARCH_CONTENT),
    "Does not apply to research content: derived research notes, the substance of a research answer, or the user's "
    "own drafts.":
        ("Does not apply to domain content.", DOMAIN_CONTENT_IS_RESEARCH_CONTENT),
    "One exception binds: §6's paragraph rule applies to research content too.":
        ("One exception binds: §6's paragraph rule applies to domain content too.",
         DOMAIN_CONTENT_IS_RESEARCH_CONTENT),
    "**Extend this table whenever the vault fixes a new term.** A build step that names a new artifact, role, or "
    "layer MUST add it here in the same session, with its banned synonyms.":
        ("**Extend the Vocabulary whenever a repository fixes a new term.** A build step that names a new artifact, "
         "role, or layer MUST add it in the same session, with its banned synonyms: a term of the core to this table, "
         "a term of one domain to the domain's glossary.",),
    "**Repetition across a delegation boundary.** A worker inherits no vault contract, so a rule restated in a "
    "worker's instructions is doing necessary work.":
        ("**Repetition across a delegation boundary.** A worker inherits no contract, so a rule restated in a "
         "worker's instructions is doing necessary work.",),
    "It does NOT govern the substance of a research answer.":
        ("It does NOT govern the substance of an answer.", DOMAIN_CONTENT_IS_RESEARCH_CONTENT),
    "- NEVER name a work in a rule, and NEVER describe one so closely that only that work fits.":
        ("- NEVER name one input in a rule, and NEVER describe one so closely that only that input fits.",
         INPUT_IS_A_PDF),
    "- If a worker or the orchestrator misjudged one PDF, find the sentence that permitted the misjudgment: an "
    "uncovered case, an undefined force, or an undefined term.":
        ("- If a worker or the orchestrator misjudged one input, find the sentence that permitted the misjudgment: an "
         "uncovered case, an undefined force, or an undefined term.", INPUT_IS_A_PDF),
    "NEVER append a sentence for the PDF.":
        ("NEVER append a sentence for the input.", INPUT_IS_A_PDF),
    "**When an action fails, name the failure branch the instruction specifies.** NEVER improvise a recovery silently.":
        ("**If an action fails, name the failure branch the instruction specifies.** NEVER improvise a recovery "
         "silently.",),
    "**Mark judgment as judgment.** If no rule governs a choice, say so: \"No rule covers this; choosing X because Y.\" "
    "NEVER present a preference as a requirement, and NEVER present a requirement as a preference.":
        ("**Mark judgment as judgment.** If no rule governs a choice, say so: \"No rule covers this; choosing X because "
         "Y.\"", "NEVER present a preference as a requirement.", "NEVER present a requirement as a preference."),
    "**When reversing a recommendation, name what changed:** the rule, the measurement, or the fact.":
        ("If you reverse a recommendation, name what changed: the rule, the measurement, or the fact.",),
    "**Banned: narration that cites nothing.** *Let me go ahead and…*, *I'll just…*, *Now I'll…*.":
        (NARRATION_NEEDS_ITS_REASON,),
    "Each announces an action while withholding its reason.":
        (NARRATION_NEEDS_ITS_REASON,),
    "- If a rule carries more than two exceptions, restate the rule so that it covers them: a list of exceptions "
    "grows by one per batch.":
        ("- If a rule carries more than two exceptions, restate the rule so that it covers them: a list of exceptions "
         "grows by one per run.", INPUT_IS_A_PDF),
}

CONTRACT_REWORDED = {
    "Every worker but `pdf-filer` runs with `omitClaudeMd`, so it never loads this contract; `pdf-filer` still loads "
    "it, through the import `CLAUDE.md` holds.":
        ("Every worker runs with `omitClaudeMd`, so it never loads this contract, the soul file, or the user file.",),
    "**Never.** NEVER write to the session memory store; anything durable belongs in this contract or a skill.":
        ("**Never.** NEVER write to the session memory store; a rule belongs in this contract or a skill, and what is "
         "true of the user now belongs in `USER.md`, which the `remember` skill keeps.",),
    "**ALWAYS invoke the `clean-prose` skill BEFORE writing or editing instruction text** — this contract, a skill, "
    "worker instructions, a reference file a skill loads — including a one-sentence change.":
        ("**ALWAYS invoke the `clean-prose` skill BEFORE writing or editing instruction text** — this contract, the "
         "soul file, a skill, worker instructions, a reference file a skill loads — including a one-sentence change.",),
}


class RuleUnits:
    def __init__(self, text: str) -> None:
        self._lines = text.splitlines()

    def units(self) -> list[str]:
        return [unit for block in self._blocks() for unit in self._split(block)]

    def _blocks(self) -> list[str]:
        blocks, paragraph = [], []
        for line in self._lines:
            if self._stands_alone(line) or not line.strip():
                blocks += [" ".join(paragraph), line]
                paragraph = []
            else:
                paragraph.append(line)
        return [block for block in blocks + [" ".join(paragraph)] if block.strip()]

    @staticmethod
    def _stands_alone(line: str) -> bool:
        return line.startswith((TABLE_CELL_SEPARATOR, HEADING_MARK, FENCE)) or FRONTMATTER_KEY.match(line) is not None

    @staticmethod
    def _split(block: str) -> list[str]:
        normalized = WHITESPACE_RUN.sub(" ", block).strip()
        if normalized.startswith((HEADING_MARK, FENCE)) or TABLE_RULE.match(normalized):
            return []
        if normalized.startswith(TABLE_CELL_SEPARATOR) or FRONTMATTER_KEY.match(normalized):
            return [normalized]
        return SENTENCE_END.split(normalized)


class SplitText:
    def __init__(self, paths: tuple[Path, ...]) -> None:
        self._text = WHITESPACE_RUN.sub(" ", " ".join(path.read_text(encoding="utf-8") for path in paths))

    def holds(self, unit: str) -> bool:
        return unit in self._text


class RuleLedger:
    def __init__(self, old_units: list[str], new_text: SplitText, reworded: dict[str, tuple[str, ...]]) -> None:
        self._old_units = old_units
        self._new_text = new_text
        self._reworded = reworded

    def lost(self) -> list[str]:
        return [unit for unit in self._old_units if not self._kept(unit)]

    def stale_rewordings(self) -> list[str]:
        return [old for old in self._reworded if old not in self._old_units or self._new_text.holds(old)]

    def _kept(self, unit: str) -> bool:
        if self._new_text.holds(unit):
            return True
        return unit in self._reworded and all(self._new_text.holds(part) for part in self._reworded[unit])


def pre_split_units() -> list[str]:
    return [unit for path in PRE_SPLIT_FILES for unit in RuleUnits(path.read_text(encoding="utf-8")).units()]


LEDGER = RuleLedger(pre_split_units(), SplitText(SPLIT_FILES), REWORDED)
CONTRACT_LEDGER = RuleLedger(RuleUnits(PRE_A6_CONTRACT_FILE.read_text(encoding="utf-8")).units(),
                             SplitText(CONTRACT_FILES), CONTRACT_REWORDED)


class TheSplitSkillsHoldEveryRuleTheOldSkillsHeld(unittest.TestCase):
    def test_every_old_sentence_and_row_is_in_the_new_files_verbatim_or_by_its_reviewed_rewording(self) -> None:
        self.assertEqual([], LEDGER.lost())

    def test_every_rewording_names_an_old_unit_the_new_files_no_longer_hold_verbatim(self) -> None:
        self.assertEqual([], LEDGER.stale_rewordings())


class TheContractAndTheSoulFileHoldEveryContractRuleA6Rewrote(unittest.TestCase):
    def test_every_rewritten_contract_sentence_is_in_the_contract_or_the_soul_file_by_its_rewording(self) -> None:
        self.assertEqual([], CONTRACT_LEDGER.lost())

    def test_every_contract_rewording_names_a_sentence_the_contract_no_longer_holds_verbatim(self) -> None:
        self.assertEqual([], CONTRACT_LEDGER.stale_rewordings())


class TheLedgerReportsADroppedRule(unittest.TestCase):
    def test_a_sentence_missing_from_the_new_text_is_lost(self) -> None:
        ledger = RuleLedger(RuleUnits("Keep this rule. Drop that rule.").units(), FakeSplitText("Keep this rule."), {})
        self.assertEqual(["Drop that rule."], ledger.lost())

    def test_a_table_row_missing_from_the_new_text_is_lost(self) -> None:
        old = "| Term | Means |\n| --- | --- |\n| kept | one |\n| dropped | two |\n"
        ledger = RuleLedger(RuleUnits(old).units(), FakeSplitText("| Term | Means | | kept | one |"), {})
        self.assertEqual(["| dropped | two |"], ledger.lost())

    def test_a_rewording_absent_from_the_new_text_does_not_keep_its_rule(self) -> None:
        ledger = RuleLedger(["Old rule."], FakeSplitText("Other rule."), {"Old rule.": ("New rule.",)})
        self.assertEqual(["Old rule."], ledger.lost())


class FakeSplitText(SplitText):
    def __init__(self, text: str) -> None:
        self._text = text


if __name__ == "__main__":
    unittest.main()
