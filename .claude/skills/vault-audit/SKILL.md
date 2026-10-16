---
name: vault-audit
description: "Vault Maintenance — audit the vault's control plane (the contract, the skills, the worker instructions, the code) for contract drift, staleness, redundancy, special cases, and code quality, reading what changed since the last audit and what depends on it. Reports in chat and writes only the audit baseline. Use when asked to audit, review, or trim the vault's own control plane — never research content."
allowed-tools: Read, Glob, Grep, Bash(~/.research-vault/venv/bin/python .claude/skills/vault-audit/scripts/audit.py:*), Bash(~/.research-vault/venv/bin/python -m unittest discover:*), Bash(git log:*), Bash(ls:*), Bash(find:*), Bash(du:*), Bash(wc:*)
---

# vault-audit (Vault Maintenance, run inline by the orchestrator)

Audits the control plane — `AGENTS.md`, the `CLAUDE.md` that imports it, `.claude/settings.json`,
`.mcp.json`, `pyproject.toml`, the CI workflow and composite action under
`.github/`, the skills, the worker instructions, the reference files, the
code, and the test fixtures — against itself and against the disk. The audit changes nothing but the
audit baseline, so it MAY run at any time, including mid-batch.

Two definitions fix the scale of a run:

* **Audit baseline.** `.claude/skills/vault-audit/baseline.json` holds one
  digest per control-plane file, as of the last accepted audit.
* **Audit set.** The audit set is the files this run reads whole: every file
  changed since the last accepted audit, plus every control-plane file whose
  text names one of them.

## Arguments

Optional; default `changed`.

| Arg | The audit set is |
| --- | --- |
| `changed` | what `audit.py changed` prints |
| `all` | every control-plane file |
| `<path>` | the named file, plus every file that names it |

**Run `all` when the contract or a skill's procedure changed, before scaling
over a new batch, and whenever the user asks for a full audit.** A change
inside one file can break a rule in a file that never mentions it, and only a
full read finds that.

## Commands

Every command is `~/.research-vault/venv/bin/python
.claude/skills/vault-audit/scripts/audit.py <subcommand>`.

| Command | Prints | Writes |
| --- | --- | --- |
| `audit.py changed` | `accepted`, the audit set as `changed` and `related`, the `removed` files, and `counts` | nothing |
| `audit.py lint` | `code`, one row per Clean Code measure; `pointers`, one row per dead path or future date; and `works`, one row per basename of a work in instruction text or in code outside `tests/`; each with `file` and `line` | nothing |
| `audit.py residue` | the scratch directory's size and age, the conflict copies, the corpus files with no PDF, the bytecode directories, the orphans, and the inbox's contents | nothing |
| `audit.py accept` | the date recorded and the number of files | the audit baseline |

If the audit baseline is not valid JSON, every command prints `{"error": …}`
and exits 1: restore the baseline from git and run the command again.

`audit.py lint` reads every control-plane file whatever the audit set, because
a script's coverage costs no judgment; `--changed` narrows it. `audit.py
changed --all` prints every file as the audit set.

## Procedure

1. Run `audit.py changed`. If `accepted` is null, no audit has been accepted:
   the audit set is every file, and the report says so.
2. Run `audit.py lint` and `audit.py residue`. Read both outputs before
   reading any file: they place the findings a file read would have to search
   for.
3. Run the test suite:
   `~/.research-vault/venv/bin/python -m unittest discover -s tests`.
4. Read every file of the audit set in full. NEVER conclude anything from a
   partial read: a partial read produces confident wrong findings. If a file
   cannot be read, report it as unaudited and continue.
5. Run checks 1, 2, 2b, 3, and 6 inline. Checks 4, 5, and 7 read code, and the
   orchestrator MAY dispatch each to a worker whose prompt carries the check's
   text in full, names the files in scope, and asks for findings as
   `file:line` rows; the orchestrator assembles the report.
6. Report in chat, in the six sections under Output.
7. Run `audit.py accept` ONLY on the user's instruction, after the findings are
   fixed or dismissed: accepting records every file as audited, and a finding
   left unfixed then goes unread until that file changes again.

**NEVER report a file outside the audit set as correct.** The report states
the audit set and the counts, so the user reads coverage rather than assuming
it.

## Check 1 — Contract drift

- For each rule in `AGENTS.md`, locate the code or config that
  enforces it, or mark it UNENFORCED — a missing guardrail or dead prose,
  each a finding with a different fix. Priority: the filename convention and
  the join key (§3), the classification vocabularies (§3), the citation
  format and the `uncitable:` field (§3), the no-answers-on-disk rule
  (§1), the model column and the run-by column of the stage tables (§4), the
  page checks (§4), the write-once rule for notes (§4), and the standards
  (§5): the dry run before the writing form, and the test suite around every
  code change.
- Check the reverse: a `deny` entry, permission, or script behaviour the
  contract never mentions is undocumented policy.
- Check §2's architecture table against the disk, both directions. Flag
  anything generated inside the vault that §2 places outside it or marks
  unsynced — search stores, caches, scratch renders, bytecode.

## Check 2 — Redundancy

Find text duplicated between the contract and SKILL.md files, between
SKILL.md files and their scripts' `--help`, and between skills sharing a
handoff. For each duplicate, name the single home:

| Home | Holds |
| --- | --- |
| `AGENTS.md` | what is true across all stages and needed in every session |
| a SKILL.md | what is true only while that stage runs |
| a script's `--help` | its own invocation detail |

A duplicate whose copies have drifted apart outranks one that still agrees.

## Check 2b — Prose quality

The standard is `.claude/skills/clean-prose/SKILL.md` with its overlay
`.claude/glossary.md`; the contract's §5 gates authoring against it, and this
check audits conformance after the fact. Read the skill, then the overlay,
before running the check.

Apply to every instruction file in the audit set. Report the measures as
numbers, ranked by consequence — measures 1 and 2 change what a reader does;
measure 6 costs tokens:

1. Actions with no stated failure branch.
2. Branches with an uncovered case and no named default.
3. Undefined force: *consider*, *try to*, *generally*, *where appropriate*,
   *as needed*, and bare `should` where MUST or PREFER was meant.
4. Sentences with none of the five forms; compound obligations; action before
   condition; unbound antecedents.
5. One concept under two or more terms across the file set — the canonical
   terms are the Vocabulary tables of `clean-prose` and `.claude/glossary.md`.
6. Economy and format: decoration, narrative, examples, throat-clearing,
   over-long qualification, always-loaded bytes, and enumerable rules left as
   flowing paragraphs where a table or numbered steps would serve.

Guard against two silent false positives: **recast rationale** (a why-tail
bound to the rule it guards) and **repetition across a delegation boundary**
(a worker inherits nothing). Cutting either is a regression. In Check 2b and
Check 4b alike, the highest-value finding is text or code written since the
last audit that never met the standard, worker instructions first.

## Check 3 — Skill definition quality

For each SKILL.md in the audit set:

- Is the `description` specific enough to trigger on the right requests and
  narrow enough not to fire on adjacent ones?
- Does it state preconditions and postconditions so the stages compose?
- Is directory ownership unambiguous — one writer per directory? Trace the
  handoff from the inbox on the Desktop through Zotero to the
  library and the derived corpus, and confirm the prose matches what the
  scripts do.
- Where a skill dispatches a worker, is the contract exact: verbatim prompt,
  pinned model, explicit return shape?

## Check 4 — Code quality

Read `lib/*.py` and their `_packages` first, then the stage scripts,
looking for logic that reimplements a shared helper — path resolution,
filename parsing, frontmatter read/write, the `<FirstCreator>` rule, text
extraction, quote finding. A divergent copy of the filename rule is a
silent-corruption bug: the basename is the join key.

Also check: hardcoded paths, machine names, or binaries (§2 forbids them);
bare `except`/`pass` swallowing a failed write; UTF-8 handling; a note written
without the atomic replace and the staleness guard `vault.GuardedNote` gives;
overwriting a corpus file's frontmatter without reading it; a script rewriting
a hand-written field (`field:`, `commentary_on:`, the classification);
non-idempotent re-runs; and the `.claude/settings.json` allow-list against the
real subcommand surface, both directions.

**Where code was added since the last audit, check what it made possible
elsewhere:** a helper the new code introduced that older code reimplements, and
a pass the new code makes redundant.

## Check 4b — Clean Code conformance

`audit.py lint` counts the mechanical measures: functions over 20 lines, files
over 500, more than three arguments, comments, and docstrings. Read its `code`
rows as the measure; the judgment this check adds is what a script cannot
count — duplicated knowledge, flag arguments, command-query mixing, magic
numbers, free functions outside the three places `.claude/code-overlay.md`
permits, and
names that mislead.

The standard has no standing exemptions: a comment recounting an incident is
a finding like any other comment, and a bug found while refactoring is fixed,
not deferred.

A suite absent, failing, or with goldens regenerated in bulk to pass is itself
a Check 4b finding.

## Check 5 — Failure modes

Trace in code what happens for each; the finding is handling that is wrong,
silent, or undefined:

- Zotero offline partway through Stage 1
- a PDF with no text layer, or a page that fails the page checks
- a duplicate work, or a second edition of one already held
- a Stage 6 sync interrupted midway
- a corpus file hand-edited after embedding
- two machines editing the same corpus file through iCloud at once
- a stage re-run on input already processed
- a volume in `library/volumes/` with no outline
- a chapter cut from a volume without the user naming it
- Stage 4 re-run on a corpus file that already carries `source_type` or `field:`

## Check 6 — Staleness and residue

This check tests truth, not consistency: a rule can be well-formed, enforced,
and describe a world that has moved. Version control dates the edit that
wrote a claim, never the world the claim describes.

`audit.py lint` reports the dead paths and the future dates as `pointers`.
Two questions remain for the reader:

| Question | Against |
| --- | --- |
| Counts — every corpus figure quoted anywhere | what is on disk |
| Standing claims about mutable state (*currently*, *now*, *still*, *empty*) | whether they hold today; else re-date or reformulate |

Rank by blast radius, not age. No consequence, no finding.

### Residue

`audit.py residue` reports each site. Two distinctions decide whether a pile is
a finding: **derived?** (regenerable is deletable; unique work product is not)
and **owned?** (a directory no stage is contracted to clear is the actual
defect).

| Site | Note |
| --- | --- |
| the scratch directory | page renders, engine and pixel caches, normalized page texts; on the primary, persistent; `sweep --apply` clears the entries keyed to no held or inbox PDF, and the reviewed sweep clears each reviewed work's page renders and font repair caches |
| `conflict_copies` | iCloud conflict copies beside the corpus files and the library; report each, and delete one only on the user's word, after any merge by hand the skill that owns the file states |
| `corpus_without_pdf` | a corpus file with no PDF of the same basename; its frontmatter and classification are hand-set work product, its body is derived |
| `bytecode_directories` | their reappearance is the finding: something ran Python without `PYTHONDONTWRITEBYTECODE=1` |
| `inbox_files` | report the count; NEVER propose deleting — the user clears the inbox |
| `orphans` | `*.tmp`, `*.bak`, `*~`, `*.part`, `*.partial` left behind by an interrupted write |

Report and propose the clearing; NEVER run it — deleting a stranded render or
handoff can destroy the only cleaned copy, and that judgment is the user's.

## Check 7 — Special cases

The contract's §5 defines the defect class and the special case;
`.claude/code-overlay.md` and `clean-prose` §12 with `.claude/glossary.md`
state the rule for code and for instruction text. Read all three before
running the check. The check asks one question of every rule,
branch, constant, and table entry in the audit set: **can a PDF not yet
ingested meet it?** No second PDF, no rule.

Run `git log --since=<accepted> --stat`, `<accepted>` being the date
`audit.py changed` prints; if `accepted` is null, run `git log --stat`. If the
command fails, report sign 6 as unaudited and continue.

| # | Sign | Read from |
| --- | --- | --- |
| 1 | a work's basename in instruction text or in code outside `tests/` | `lint`'s `works` rows |
| 2 | a work named any other way — a creator, a title, a Zotero key — in a rule, a condition, a constant, or an identifier | the audit set |
| 3 | a condition only one PDF could meet: a literal file page, page count, exact string, or exact font name, alone or conjoined | the code in the audit set |
| 4 | a threshold changed since the last accepted audit with no test pinning a built PDF on each side of the new value | the log, then `tests/` |
| 5 | a rule carrying more than two exceptions; an enumeration or a chain of branches that gained an entry in each of two or more commits | the audit set, then the log |
| 6 | a commit other than a merge commit, changing code or instruction text, whose message carries neither a `Defect-class:` trailer nor a `Change-class:` trailer, or whose `Defect-class:` trailer names only a work | the log |
| 7 | a test added since the last accepted audit that pins a fix and either reads a library PDF or is named for a work, where the contract requires the defect class built in a PDF of its own | the log, then `tests/` |

Three things are not special cases. Data that parameterizes a rule (a list of
producers, font families, heading words, languages) is specification: each
entry names a class of PDFs. A test that reads a library PDF as a fixture,
under `tests/README.md`, names a work as data, unless sign 7 applies. An entry of the identity table
lives in the library and is keyed on a font family.

For each finding, name the defect class the text or code should have stated,
and propose one of two fixes: restate the rule so that it covers the defect
class, or delete the special case. If no defect class can be named, the fix is
deletion.

Report the lines each file of the audit set gained since the last accepted
audit, from the log's `--stat`. Growth is not a finding; it ranks which file
to read first.

## Output

In chat only; write nothing to disk but the audit baseline, and only on the
user's instruction.

Open with the coverage: the audit set's counts, the date the baseline was
accepted, and the files reported unaudited. Then six sections, `file:line`
throughout; where you infer intent rather than read it, say so:

- **A. Contradictions** — rule versus reality, each with the concrete
  consequence. No consequence, no finding.
- **B. Redundancies and prose** — duplicates with their single home, then
  prose cuts as specific replacement text, never verdicts.
- **C. Code issues** — ranked by likelihood of silent data corruption.
- **D. Special cases** — by sign, each with the defect class it should have
  stated and marked restate-it or delete-it; then the lines each file gained.
- **E. Staleness and residue** — ranked by blast radius, each marked
  correct-it or re-date-it; then the residue sites, each marked
  derived-or-not and owner-or-none.
- **F. Fix list** — prioritized, each `[settings]` / `[docs]` / `[code]`,
  each with the smallest change that resolves it.

Close by naming the next step: the user fixes or dismisses the findings, and
then instructs `audit.py accept`.
