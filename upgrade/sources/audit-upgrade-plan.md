# Audit upgrade plan

**This plan is the detail reference for `unified-upgrade-plan.md`.** The
unified plan governs: where the two differ, the unified plan wins. This plan
gives the worker who builds each item what the unified plan leaves out.

| Item | Content | Wave | Depends on |
| --- | --- | --- | --- |
| U2 | STE writing rules in the core's `clean-prose` | W2, lane a | A1 |
| U1 | audit test bench | W3, lane a | A2 |
| U3 | the lint layer | W3, lane a | U1 |
| U4 | unit scoping and baseline v2 | W3, lane a | U3 |
| U5 | the `audit` workflow and its workers | W4, lane a | U4 |
| U6 | loop and fix mode, in a worktree | W4, lane a | U5 |
| U7 | Check 8: throughput and token economy, with stage timings in `ingest.py` | W4, lane a | U6 |
| U8 | Check 9: current practice | W4, lane a | U7 |
| U2b | the > 40-word sentence cleanup | W5, lane c | U3; runs before G21 |

The fast post-edit hook is not an item of this plan: it is X1, the first item
of W1. G17 extends U3's `xref` check to tiers. The upgraded audit is the
programme's final quality gate (X7.1).

In the core the audit skill is `control-plane-audit`. The research domain keeps
`vault-audit` as a thin skill that invokes it, adding the research checks.

Upgrade the audit so that it is (1) as thorough as today or more, measured
rather than assumed; (2) mechanical wherever a rule can be counted; (3) run as a
structured workflow whose workers read small scopes in full, so the
orchestrator's context stays small; (4) cheap enough per iteration to loop;
(5) an optimization pass as well as a correctness pass; and (6) current with
first-party practice on skills, subagents, and model instructions.

## 1. Where we start

Snapshot of `research-tools`, 2026-10-15.

| Measure | Value |
| --- | --- |
| Commits since the baseline commit `3f15cc2` | 547; 692 files, +55,663/−3,232 lines |
| `audit.py changed` audit set | 682 changed + 373 related of 1,130 files: `changed` ≈ `all` |
| Instruction text | 741 KB (~180k tokens); 3,087 prose sentences |
| Code (`lib/`, skills, workflows) | ~2.0 MB |
| Tests | 583 `.py` files, ~2.7 MB; 553 test modules, about 4,940 tests, single-process |
| A full read under today's step 4 | ~700k tokens before tests, in one context |
| Sentences > 20 / > 25 / > 40 words | 42% / 29% / 9% (CLAUDE.md: median 21, 34% > 25) |
| `audit.py lint` today | 35 `code` rows (33 too-many-arguments, 1 long function, 1 long file); 1 `pointers` row (`file-pdfs/SKILL.md:364` names `library/.refiling/`); 0 `works` rows |
| `audit.py` subcommands | `lint`, `changed`, `accept`, `residue` |
| `vault-audit` reference files | none: the skill has no `reference/` directory |
| Ruff rules selected | `E4, E7, E9, F` only |
| Post-edit hook | runs the full suite after every Python edit; its run time is not measured |
| `CLAUDE.md` (always loaded) | 39 KB |
| Largest worker instructions | `bibliography-shaper` 23 KB, `pdf-filer` 18 KB, `work-classifier` 15 KB |

The diagnosis: the unit of audit is the file, a file counts as related by
naming another file's path, and every check rests on one long read. At this
churn, that read is the whole plane, and attention degrades long before it
ends, so thoroughness today is assumed, not measured.

## 2. Target architecture

```
                 audit.py drive-plan        (script, seconds)
   lint · STE · xref · ruff · clones · costs · units · closure · rotation
                              │ partitions + hints
          ┌──────────┬────────┴──────┬─────────────┬────────────┬──────────────────┐
     prose-reader code-reader  failure-tracer special-case  optimizer  practices-reader   Phase 1: judgment, parallel, Sonnet
          │          │               │             │            │      ▲ digest (practices-scout, when stale)
          └──────────┴────────┬──────┴─────────────┴────────────┴──────┘
                drift-checker · redundancy-checker                         Phase 2: cross-cutting, on indexes
                              │ findings (answers files)
                        audit-verifier                                     Phase 3: adversarial, per file
                              │ confirmed
                 audit.py drive-assemble    (script)                        Phase 4: merge, dedupe, rank, report
                              │
                 audit-fixer (worktree) → re-plan on delta                 Phase 5: loop mode only
```

Four layers, each with one job:

| Layer | Job | Guarantee |
| --- | --- | --- |
| Lint | every countable rule, every unit, every run | complete recall on its classes; no attention decay |
| Judgment | what a script cannot count, on bounded partitions read in full | each worker reads ≤ budget tokens, with each unit's dependencies |
| Verify | disprove each finding against the source | false positives never reach the report or the loop |
| Bench | seeded defects, recall per check and per layer | "did we lose power" is a number every item must hold |

Lint hits are hints to judgment, never its boundary: no worker skips a unit
because lint found it clean.

### Where the audit lives

A2 moves today's engine to `agent-core` (public) as is. U1 to U8 then build the
upgrade there. Each domain carries the core as a git subtree at
`vendor/agent-core/`, with the core's skills, agents, and workflows symlinked
into `.claude/skills/`, `.claude/agents/`, and `.claude/workflows/`.

| Piece | Home | Notes |
| --- | --- | --- |
| generic engine: `audit.py`, `_audit/`, the lint rows of U3, units and closure of U4 | `agent-core` | runs against the domain root it is given |
| bench | `agent-core` tests, `tests/audit_bench/` | a domain-neutral synthetic plane |
| `audit.js` and its workers, `relay` included | `agent-core` | symlinked into each domain |
| domain checks | each domain's `audit/checks.py` | registered with the engine; tested in the domain's suite |
| `control-plane-audit` | `agent-core` | the core's audit skill |
| `vault-audit` | research domain | a thin research skill that invokes `control-plane-audit` with the research checks |
| baseline | each domain's repo, `audit/baseline.json` | each domain keeps its own `accepted`, units, and `acknowledged` |
| practices digest | `agent-core`, `audit/practices-digest.md` | committed; refreshed through a reviewed PR (U8) |

The research domain's `audit/checks.py` holds:

| Check | Runs | Content |
| --- | --- | --- |
| `works` | anywhere | today's `works` check, unchanged |
| `special`, PDF-keyed signs | anywhere | conditions comparing with a literal file page or an exact font name; the core's `special` row carries the generic signs |
| `residue` | primary only | today's `residue`; needs the real vault |
| `staleness`, counts against disk | primary only | numerals beside works, PDFs, or corpus files against the vault's counts; needs the real vault |
| folders | anywhere, in CI | `domain.json` `folders`, the research `Locations` defaults (P7), and the generated sandbox name the same folders |

A primary-only check reports itself skipped when no real vault is present, as
in the cloud and in CI.

## 3. Items, in order

Each item: invoke `clean-prose` before instruction text and `clean-code` before
code; the suite, ruff, and the audit linter pass; every commit carries a
`Defect-class:` trailer for a fix, or `Change-class: refactor|feature — <what>`
otherwise (X2).

### U1 — Audit test bench (measure first)

The bar every later item must clear. It lives in `agent-core`'s tests.

| Piece | Content |
| --- | --- |
| `tests/audit_bench/seeds.json` | one seed per defect class: `{id, check, class, target, mutation}`; mutations are applied to a synthetic control plane, never to a work |
| `tests/audit_bench/plane/` | a small synthetic control plane: a contract, a glossary, two skills, two workers, a `lib/` module, a script, a settings file; clean at rest |
| `audit.py bench build <dir>` | copies the synthetic plane into `<dir>` and applies every seed; prints the seed manifest |
| `audit.py bench score <dir> <findings.json>` | matches findings to seeds by check and `file:line` window; prints recall per check, per layer, and the unmatched findings (false-positive candidates) |
| `tests/test_audit_bench.py` | the lint layer's recall on the seeds, in CI, deterministic |

Seed classes (initial set, ~30): banned force word; banned synonym; bare
`should`; long sentence; compound obligation; action with no failure branch;
branch with no default; unbound antecedent; duplicate rule that drifted; stale
count; dead path; worker `model:` contradicting the stage table; subcommand
named in prose but absent from argparse, and the reverse; allow-list entry with
no subcommand; hook named in the contract but absent from the hook module;
reimplemented filename rule; swallowed write error; non-atomic note write;
flag argument; magic number; special case on a literal file page; special case
on an exact font name; threshold changed with no pinning test; commit with
neither a `Defect-class:` nor a `Change-class:` trailer; worker instructions
missing a rule they need (delegation boundary); missing handling for an
external service offline; a recast-rationale tail and a cross-boundary
repetition as **negative seeds** (a finding on them is a false positive). U8
adds its seeds (§3, U8).

**Root threading.** The bench runs every check against `<dir>`, so every check
takes a root. Today only `ControlPlaneFiles` (`scope.py:26`) takes one. These
must take it too:

| Code | Today |
| --- | --- |
| `Baseline._present` | `baseline.py:54` |
| `FileMeasures._finding` | `measures.py:75` |
| `Residue` | reads the repository it runs from |
| `AuditSet` | defaults to `BASELINE_PATH` |
| `audit.py` | `audit.py:9` finds the repository by `lib/vault.py` |
| `scope.py` | `scope.py:7` derives the root from `vault.__file__` |

In the core, `audit.py` and `scope.py` take the domain root, from an argument
that defaults to the git top level of the working directory. No check reads
the repository it is installed in.

**Baseline measurement:** run today's skill procedure once against the seeded
plane (one agent, as the skill runs now) and record recall per check. That
number is the floor.

### U2 — STE writing rules in `clean-prose`

New sections in the core's general `clean-prose`, restating ASD-STE100's
writing rules in house form. No text comes from the specification, and there
is no general dictionary: the domain's `.claude/glossary.md` (moved there by
A1) is the technical-names list.

| Rule | Threshold | Lintable |
| --- | --- | --- |
| Sentence length by form | Command, Prohibition, Conditional ≤ 20 words; Definition, Invariant ≤ 25 | yes |
| One instruction per sentence | one imperative or force word per main clause | yes (heuristic) |
| Active voice for actions | no passive in a Command or Conditional | heuristic |
| Noun clusters | ≤ 3 nouns in a row, technical names exempt | heuristic |
| Paragraph length | ≤ 6 sentences; a sequence of actions is numbered steps | yes |
| One topic per paragraph | — | judgment |
| Condition before action | already in `clean-prose`; STE confirms | heuristic |

Scope rules: code spans, technical names from the domain's glossary, and table
cells count as one word each; a table cell's limit is the row's form.

**Ratchet:** the rules bind text written or changed after adoption. Existing
text keeps its findings as acknowledged (U3). The > 40-word tail (~280
sentences) is a separate cleanup, U2b. It runs in W5 lane c, once U3 has
measured the tail, and before G21: both rewrite instruction prose.

The chat register stays out of scope: STE governs instruction text.

### U3 — The lint layer

`audit.py lint` gains row types; each row is `{rule, file, line, detail,
fingerprint}`.

| Row | Rules | Replaces judgment in |
| --- | --- | --- |
| `prose` | banned force words; bare `should`; banned synonyms parsed from the domain's `.claude/glossary.md` (a synonym marked `(for the X)` flagged only in the X sense, low confidence); "agent" alone; the STE rules of U2 | 2b measures 3–6, part of 4 |
| `xref` | subcommands in prose vs argparse, both ways; workers in prose vs `.claude/agents/`; each worker's `model:` vs the stage table's Model column; allow-list vs subcommands, both ways; the contract's hook list vs the hook module; skills in the contract's operation tables vs `.claude/skills/` | 1 (reverse half), 3, 4 (allow-list) |
| `redundancy` | sentence shingles shared across instruction files, pair and overlap; flagged drifted when the copies differ | 2 (candidates) |
| `staleness` | *currently/now/still/empty* with `git blame` age; the research domain adds numerals against disk counts (§2) | 6 |
| `special` | sign 3: AST conditions comparing with string literals, plus the domain's PDF-keyed signs (§2); sign 4: constants whose value changed since the baseline, with or without a test naming them; sign 5: enumerations that grew in two or more commits; sign 6: commits with neither a `Defect-class:` trailer for a fix nor a `Change-class: refactor\|feature — <what>` trailer otherwise | 7 |
| `code` | ruff with `PLR0913, PLR0915, PLR2004, C901, FBT, BLE, S110, ERA, ARG` added; `CodeMeasures` keeps only what ruff cannot count (file length, comments, docstrings); an AST-normalized clone detector for functions that reimplement a `lib/` helper | 4b, part of 4 |

`xref` reads `model:` and the Model column only. G17 later extends the same
check to tiers, so the two never disagree. The domain's `audit/checks.py`
names where its contract keeps the stage table, the hook list, and the
operation tables.

Supporting changes:

* **Ruff inside the lint.** The extra ruff rules run inside `audit.py lint`,
  ratcheted by fingerprint. `pyproject.toml` keeps `E4, E7, E9, F`; otherwise
  CI fails on the 33 existing too-many-arguments rows.
* **Ratchet.** The baseline gains `acknowledged: {fingerprint: reason}`. A
  fingerprint is the rule plus the file plus a hash of the normalized line,
  never the line number, so it survives edits elsewhere in the file. `lint
  --new` prints only unacknowledged rows. The first run acknowledges today's
  rows in bulk, on the user's word.
* **New subcommands.** The baseline-writing subcommands (acknowledge,
  dismiss) each need an `excludedCommands` entry, as `accept` has. They ship
  as a settings patch in `upgrade/settings-patches/`.
* **No new dependency.** Voice and noun clusters use regex heuristics. The
  bench measures their recall and precision; adding a tagger (a lock change)
  is a later decision, made on those numbers.
* **Hooks and CI.** The post-edit Markdown hook adds `prose --new` for the
  edited file. CI fails on new `xref` and `special` rows; `prose` and
  `redundancy` rows report without failing until their precision is measured.
* **Contract.** U3 does not edit the contract for the trailers: X2 puts them
  there.

### U4 — Unit scoping and baseline v2

| Piece | Content |
| --- | --- |
| Units | a Markdown section (heading to next heading of the same or higher level), a top-level Python function, class, or method, a workflow function |
| Baseline v2 | per unit: digest, last-judgment-read date; per file: digest (migration keeps `accepted`); one baseline per domain, at `audit/baseline.json` in its repo |
| Closure | a unit's dependencies: the glossary terms and bolded rule heads it defines, then the units using them; the Python symbols it defines, then the units importing or calling them. Replaces the filename-mention rule in `related.py` |
| Rotation | each run adds the units with the oldest last-read date until the rotation budget (default 15% of the run's budget) is spent |
| `audit.py changed` | prints units, closure, rotation slice, and token counts (tiktoken, already pinned) |
| Skill step 4 | "read the unit in full, with its closure" replaces "read every file of the audit set in full"; the report states coverage by unit and by age |

### U5 — The `audit` workflow and its workers

`audit.js` ships from the core, on the `ingest.js` pattern: script steps
through `relay` (Haiku, low effort, already so), workers through `agent()` with
a schema, answers files in the scratch directory under `audit/<run>/`. The
workers, `relay` included, ship from the core. Ports PR 22, which would delete
`relay`, is deferred (W6); if it is ever done, `audit.js` moves to the same
`WorkerRunner`.

Arguments: `{scope: "changed" | "all" | <path>, budget, partition_tokens,
loop, fix, practices_max_age}`.

| Phase | Step | Run by | Model |
| --- | --- | --- | --- |
| Plan | `audit.py drive-plan`: lint, units, closure, rotation, partitions (≤ `partition_tokens`, default 60k), hints per partition, costs, the practices digest's age | relay | Haiku |
| Digest | Check 9 only, when the committed digest is older than `practices_max_age` (U8): the scout writes a fresh digest for a reviewed PR to `agent-core`; the run reads the committed copy | `audit-practices-scout` | Sonnet |
| Judge | one dispatch per check family × partition | workers below | Sonnet |
| Cross-cut | Check 1 on the rule-to-enforcement index; Check 2 on the shingle pairs | workers below | Sonnet |
| Verify | one dispatch per file with findings: confirm or reject each, quoting the source | `audit-verifier` | Sonnet; the session's for findings ranked A or C |
| Assemble | `audit.py drive-assemble`: merge, dedupe, drop acknowledged, rank, write last-read dates to the run's working baseline, print the report | relay | Haiku |
| Fix | loop mode only, U6 | `audit-fixer` | the session's |

New worker instructions (each carries its check text in full and the two
false-positive guards, since a worker inherits nothing; each names its model
as G17 sets it, `tier:` once G17 has merged):

| Worker | Checks | Reads |
| --- | --- | --- |
| `audit-prose-reader` | 2b, 3, STE judgment rules | an instruction partition and its hints |
| `audit-code-reader` | 4, 4b | a code partition, `lib/` units first |
| `audit-failure-tracer` | 5 | one failure scenario, along its code path |
| `audit-special-case-reader` | 7 | the changed units and the log |
| `audit-drift-checker` | 1 | the rule-to-enforcement index; opens a file only to confirm a pair |
| `audit-redundancy-checker` | 2 | the shingle pairs; names the single home of each |
| `audit-optimizer` | 8 (U7) | the cost measurements and the units they name |
| `audit-practices-scout` | 9 (U8) | the fixed allowlist of first-party sources; writes the dated digest for a reviewed PR |
| `audit-practices-reader` | 9 (U8) | the committed digest and a partition of units |
| `audit-verifier` | — | one file's findings and the file; for a Check 9 finding, the cited source page on an allowlisted host |

Finding schema: `{check, file, line, claim, evidence, consequence, fix_kind:
settings|docs|code, rank: A-F, mechanizable: bool}`. A Check 9 finding adds
`practice` and `url`. `mechanizable` feeds the promotion log, `audit.py
promotions`, which lists the recurring mechanical shapes that should become
lint rules.

The orchestrator reads the plan's counts and the assembled report: a few
thousand tokens per run. The core's audit skill is rewritten around the
workflow: the procedure becomes "run the workflow, read the report, accept on
the user's word"; the check texts move into the worker instructions, and the
skill keeps only what the orchestrator does. `vault-audit` stays a thin
research skill that invokes it.

**Size.** A full `all` run is ~20–40 dispatches. That exceeds the session's
default workflow size guideline (under 10 agents). The default is to cap a run
with `budget` and let rotation cover the rest across runs. Raising the
guideline under "Dynamic workflow size" in `/config` is the user's choice.

**Concurrency.** A cloud VM has about 4 vCPU, so the workflow's concurrency
there is below 16. X0.4 measures the real figure; size partitions and `budget`
on it.

### U6 — Loop and fix mode

| Piece | Content |
| --- | --- |
| Working baseline | each iteration writes last-read dates and digests to `audit/<run>/baseline.json` in the scratch directory, so the next iteration audits only the delta; the committed baseline, `audit/baseline.json` in the domain's repo, changes only on `accept`, on the user's word |
| Worktree | the fixer works in a git worktree, never in the main checkout: ingest preflight requires the main checkout on a clean `main` (`_ingest/checkout.py:36-64`) |
| `audit-fixer` | applies confirmed `docs` and `code` findings on the fix branch `audit-fixes/<date>` in its worktree, one commit per finding, each with its trailer; the suite, ruff, and the audit linter after each; reverts a fix that fails them and reports it unfixed |
| Stop | an iteration with no new confirmed finding, or `loop` iterations |
| End | the orchestrator opens or updates the pull request, titled by what the fixes change; the user reviews and merges, then instructs `accept` |
| Dismissals | dismissed findings go to the domain baseline's `acknowledged` with the reason, so the tools still write one control-plane file per domain |
| Contract | the domain contract's §4 or §5 gains the audit fixer beside the extraction fixer: the worktree, the fix branch, the PR, never `main`; `vault-audit` replaces "writes only the audit baseline" with "writes the audit baseline, and in fix mode commits on the fix branch" |

`[settings]` fixes stay with the user: the sandbox denies the workers writes to
`.claude/settings.json`, and policy changes are the user's call.

### U7 — Check 8: throughput and token economy

`audit.py costs` measures; `audit-optimizer` proposes. Each finding carries a
measure, a change, an expected gain, and a risk.

| Measure | Source |
| --- | --- |
| Always-loaded tokens | `CLAUDE.md`, every skill and worker `description` |
| Load cost per skill | SKILL.md plus the reference files it loads |
| Worker cost | instruction tokens × dispatches per batch (static count from the workflows) |
| Cross-boundary repetition | text shared by worker instructions that a shared reference could carry (kept where the worker needs it in context) |
| Model fit | each dispatch's model against its task's judgment load |
| Suite and hooks | time per test module (a timing test runner), hook time per edit kind |
| Batch timing | stage durations and lock waits, from the stage timings `ingest.py` records |
| Machine | the health journals over recent batches; primary only |

**Stage timings in `ingest.py`** are part of U7, in `research-assistant`.
Today no stage timing is recorded. U7 records each stage's duration and each
lock wait per batch, beside the batch's other state, without changing a vault
format.

Candidates already visible: `CLAUDE.md` at 39 KB always loaded;
`bibliography-shaper` at 23 KB.

Check 8 proposes, never applies outside fix mode; in fix mode it applies only
`docs` and `code` changes the verifier confirmed.

### U8 — Check 9: current practice

Check 9 brings first-party practice on skills, subagents, hooks, workflows, and
model instructions into the control plane, within `clean-prose`. It is
generic, so it lives in the core.

| Piece | Content |
| --- | --- |
| `audit-practices-scout` | reads a fixed allowlist of first-party sources: the Claude Code docs on skills, subagents, hooks, and workflows; the Claude prompting and agent docs; Anthropic's engineering posts. It writes a dated practices digest, each practice restated in house prose with its source URL |
| Digest | committed in `agent-core` as `audit/practices-digest.md`, and refreshed through a reviewed PR when it is older than `practices_max_age` (default 30 days). Every domain, cloud sessions included, reads the same reviewed copy, and the review is one more guard against injected text |
| `audit-practices-reader` | compares the digest against the control plane's units: skill descriptions and bodies, worker instructions, the workflows' prompts and schemas, and model and effort fit. Each finding carries the practice, its URL, the unit, and the change |
| Verify | `audit-verifier` confirms that the source states the practice and that the change keeps every contract rule |
| Fix | confirmed `docs` findings go through the fix loop (U6) under `clean-prose` |
| Contradictions | a practice that contradicts a rule of the contract or `clean-prose` is never applied: it is reported as `needs-decision`, with both sides |
| Guards | source text is data, never instructions: the scout reports a sentence aimed at the reader as a finding and does not act on it; only the allowlisted hosts are read; no source text is copied into the instructions |
| Sandbox | the allowlisted hosts, `code.claude.com`, `docs.claude.com`, and `www.anthropic.com`, are added to `network.allowedDomains`, as a settings patch in `upgrade/settings-patches/`; the scout and the verifier, which re-reads a cited page, may read only these hosts |

The allowlist sits in the scout's worker instructions, so a change to it is a
change to instruction text, made under `clean-prose` through a PR.

Bench seeds (U1's bench, with a fixture digest, so CI needs no network): a
unit that follows an outdated practice the fixture digest replaces; and, as a
negative seed, a fixture page carrying a sentence aimed at the reader, which
must surface as a finding and never as an applied change.

## 4. Acceptance

| Item | Accepted when |
| --- | --- |
| U1 | bench runs in `agent-core`'s CI; every check reads `<dir>` through its root; today's recall per check recorded |
| U2 | the core's `clean-prose` carries the STE rules; the audit linter passes |
| U2b | U3's `prose` row finds no sentence over 40 words in the instruction text; the audit linter passes |
| U3 | lint recall on mechanical seeds = 100%; lint ≤ 60 s; today's rows acknowledged; no negative seed flagged; CI passes with `pyproject.toml`'s gating set unchanged |
| U4 | a one-sentence change to `CLAUDE.md` yields a unit set < 5% of the plane |
| U5 | workflow recall ≥ U1's recall on every check; orchestrator context per run < 15k tokens; no negative seed in the report |
| U6 | two iterations on the seeded plane converge; fixes land on the fix branch only, in a worktree; the main checkout is untouched |
| U7 | each Check 8 finding carries a measure and a change; the suite-time and batch-timing measures reported |
| U8 | each finding cites a source URL the verifier confirmed; no finding that contradicts the contract or `clean-prose` is applied; the seeded outdated-practice unit is found on the bench; the negative injection seed is never applied |

A row that needs the real vault or the Mac becomes a line in
`upgrade/rehearsal.md`, run in W8: `residue` and the count-against-disk
`staleness` against the staging vault; U7's batch timings and health-journal
measures on a real backfill run.

## 5. Decisions settled

1. **Fix mode in the loop:** yes, for `docs` and `code`, on a fix branch in a
   worktree, with the PR as the user's review point.
2. **Check 8's reach:** the control plane and the health journals. Session
   transcripts (last 7 days) are opt-in.
3. **CI gating:** `xref` and `special` gate at once; `prose` and `redundancy`
   gate once their precision is measured.
4. **Workflow size:** cap runs with `budget` and rely on rotation.
5. **Partition budget:** 60k tokens per worker to start; the bench tunes it.

## 6. Risks

| Risk | Guard |
| --- | --- |
| Lint precision too low; noise trains everyone to ignore it | bench negative seeds; report-only until precision is measured |
| Unit closure misses a dependency | rotation re-reads every unit on a cycle; periodic `all` |
| Workers lose context the single reader had | closure in-partition; cross-cut workers on indexes; bench recall gate |
| Fix loop churns or fights itself | one commit per finding, revert on failure, stop on no new finding, PR review |
| STE ratchet leaves old text unreadable for long | the > 40-word cleanup (U2b), sized by lint |
| Contract drift from the audit's own changes | the audit's own skill and workers sit in its audit set |
| A fetched page injects instructions into the practices scout | allowlisted first-party hosts only; source text is data; a sentence aimed at the reader is reported, never acted on; the digest reaches `agent-core` only through a reviewed PR; the verifier re-reads the source; fixes go through the PR |
| Check 9 churns the instructions after fashion | first-party sources only; a practice contradicting the contract or `clean-prose` goes to `needs-decision`; fixes pass the verifier and the PR review; the digest refreshes at most every `practices_max_age` |
