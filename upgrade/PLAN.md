# The upgrade programme: one plan from four

**This plan governs.** The four source plans beside it hold the detail for
each item: what to build, the file references, and the acceptance. Each one
opens with a map from its sections to this plan's item IDs. Where a source
plan and this plan differ, this plan wins.

## Context

Four upgrade plans were written separately and sit in `~/Desktop/upgrade plans/`:

| Plan | Aims to |
| --- | --- |
| `assistant-architecture-plan.md` | split the setup into a shared core (`agent-core`), a dispatcher, and one repo per domain (research, personal, …) |
| `audit-upgrade-plan.md` | turn `vault-audit` into a measured, linted, multi-worker workflow with a test bench and a fix loop |
| `hexagonal-ports-plan.md` | refactor the code into ports and adapters: other OSes, hosted APIs in place of local models, and a port for the agent host |
| `primary-secondary-machines-plan.md` | keep the control plane on one always-on Mac and let other machines reach it through Remote Control |

You want them merged into one plan, improved where needed, and built in the
cloud while the current setup keeps running on your Mac. At the end you pull
the new setup down, and it replaces the old one under the new name
`research-assistant`. Your answers set the scope:

- **This round builds for your own use, never for users who don't exist
  yet.** From the ports plan it builds only what the primary Mac uses: the
  host ports for the health and Remote Control jobs, and the iCloud
  placeholder halt. Support for other OSes, hosted APIs, and other agent
  hosts waits for a real need (§3, "Deferred").
- **The personal assistant is a skeleton only**: an empty domain repo, made
  from the domain template, where you add skills soon after the switch. Its
  first skills are plain skills of its own; the dispatcher waits until they
  show what the domains share (§3, "Deferred").
- **The audit upgrade is in full, and it makes the instructions lighter.** On
  top of the measured, multi-worker audit, the instruction text only shrinks:
  a word ratchet in CI, cuts as the audit's first output, and a cut target
  for the closing audit run (§1, "New: the instruction text only shrinks").
- **No answer-quality benchmark.** An answer surfaces passages, and every
  quotation is already verified in the PDF.
- **One switch at the end** to the new multi-repo setup, with the rename part
  of that switch.
- **The audit also learns from current best practice.** On top of finding and
  applying optimizations, it reads up on how skills, subagents, and model
  instructions are best written, and brings those practices into your
  instructions within your prose standards (U8).
- **The new repos are public.** GitHub doesn't charge Actions minutes for
  public repos (standard runners, macOS included), and your account is at 90%
  of its quota.

## The shape of the solution

**Build beside the old setup, never inside it.** The new setup lives in new
GitHub repos. `research-tools` is frozen: during the build, the Mac only keeps
running the backfill ingest with it, and its code doesn't change.

| Repo | Role during the build | After the switch |
| --- | --- | --- |
| `research-tools` | frozen; runs the backfill on the Mac | archived, read-only, kept for rollback |
| `research-assistant` | new; starts as a snapshot of `research-tools` taken in W0; every research-side upgrade lands here | the research domain |
| `agent-core` | new; `core/`: the shared standards, the audit engine, the host ports, the domain template; its root: the Remote Control job, and later the dispatcher | `core/` is what every domain carries; the root holds the Remote Control job, and becomes the front door when the dispatcher is built |
| `personal-assistant` | new; made from the domain template; no skills yet | the place for your personal skills |
| `assistant` | created in X0.1 with only a README, then superseded by `agent-core`'s root (§1) | deleted or archived |

**The cloud builds; the primary runs.** The research operations exist to
work on your library on the primary Mac, and they run nowhere else. The cloud
sessions write and test the code: they read fixtures only, never a library
PDF, a corpus file, or a note, and every fixture carries no work's text (the
publish-guard checks it). That an operation runs in the cloud is never an aim.
A cloud check counts only as the build's own tooling (the item workflow, the
audit, the environment the build sessions run in). The acceptance that
matters for your use is the rehearsal on the primary (§6).

**The backfill and the build don't meet.** The backfill writes only vault
data: corpus files, the extraction records, the identity table, and the
verdicts record. The new setup reads the same vault, so everything the backfill
produces carries over at the switch. That makes the vault invariant (§2.2)
binding. The switch happens between backfill runs: a paused or set-aside PDF
is simply picked up by the new setup's next batch.

**One switch, rehearsed first.** On the Mac, the new setup first runs beside
the old one in a staging home against copies of your data. Every check that
needs the Mac runs there, side by side with the old setup. Only once all of
them pass does the switch happen. Rollback means reloading the old launch
agents, restoring the old venv, and working from the old checkout.

**Your part:** approve this plan; do one setup sitting (GitHub, cloud
environments, a token); answer the `needs-decision` questions that come up as
PR comments; and do the rehearsal and the switch. You don't review every PR.
Nothing runs from the new repos before the switch, so the gates in §5 merge
them.

## 1. What the review of the four plans changed

The code survey checked every factual claim in the plans: line references,
counts, and paths. Most hold. The changes below fix the claims that don't
hold, the places where two plans collide, and assumptions that fail in the
cloud.

### Across all four plans

| Problem | Resolution |
| --- | --- |
| Three plans assume two full machines ("both machines", "clone on both", "rebuild both environments") | The primary/secondary plan replaces that assumption everywhere. Only the primary has the control plane, so every "both machines" becomes "the primary", and the dispatcher's state lives on the primary's own disk (`~/.agent-core/state/`), not in iCloud or git. That settles the assistant plan's open decisions 4 and 5. |
| The rename moves the checkout and the launch agents, and would break the running setup mid-build | No GitHub rename. `research-assistant` is a new repo, and the switch is the rename. |
| Two generators for the same `settings.json` sandbox block (ports PR 20 `policy.json`; assistant 3.4 `domain.json`) | One generator in `agent-core`. `domain.json` carries a `policy` section; `domain.py settings` reads it. |
| "Capabilities" means two things: tool classes (ports) and the three risks of private data, untrusted content, and sending out (assistant) | The ports plan keeps **capabilities** for tool classes. The three risks become **exposure**, and `registry` checks each skill's declared exposure against its generated tool capabilities: a skill with `web` must declare untrusted content. Both wait with the dispatcher and the worker generator (§3, "Deferred"); the terms stand for that later round. |
| Commit trailers: the audit wants `Defect-class:` on every commit, but a refactor has no defect class | `Defect-class:` for a fix, `Change-class: refactor\|feature — <what>` for everything else. The audit's sign 6 accepts either. This is settled in W1, because every upgrade commit needs it. |
| The Vocabulary table is both moved (assistant 1.3) and parsed in place (audit PR 3), and it is the most-churned text in the repo (75 commits in two weeks) | The move happens first (A1). The audit lint then parses the domain's `.claude/glossary.md`. |
| Ports PR 22 deletes `relay`, which the audit's `audit.js` is built on | PR 22 is deferred (§3, W6). If it is ever done, `audit.js` moves to the same `WorkerRunner`. |
| The README is restructured two ways at once: per OS (ports) and per role (machines) | Per role only, for the primary: "Install" on macOS; "Two machines: primary and secondaries"; "Retire a former full install". The per-OS install waits with the other OSes (§3, "Deferred"). |
| `lib/_health/launch_agent.py` and `installer.py` are edited by three plans; the health job's label and plist contents are hard-coded (`installer.py:40`, `launch_agent.py:32-42`), and there is no uninstall | One item (P5+M3) builds the `Scheduler` port, in the core. Its launchd adapter takes a label and contents and has `remove`. The health job and the Remote Control job are two jobs on it. |
| The iCloud placeholder check (machines 4) and the iCloud conflict pattern (ports PR 6) both touch `_ingest/preflight.py` | One port, `SyncedFolder`: `conflict_copies()` and `not_downloaded(path)`. Preflight halts on either. |

### New: folders in `~/Documents`, assigned to domains

`~/Documents` holds your folders side by side: `library`, `research vault`,
later perhaps `taxes` or `medical`. Any folder can be made an Obsidian vault of
its own. Each domain is told which of these folders it works on. The two
choices are independent:

- a folder is a vault or not, whichever domain uses it;
- a domain can work on several folders, and two domains can share one.

| Piece | Content |
| --- | --- |
| `domain.json` | `folders`: the folders under `~/Documents` the domain works on, each with `read` or `write` access. A folder can carry `sensitive: true`, which keeps every domain that doesn't list it from reading it. |
| research domain | lists today's `library` (write) and `research vault` (write). Nothing moves: invariant 2 holds, and the contract's `vault_dir` rule is unchanged. A CI check confirms `domain.json`, the vault paths `_vault/paths.py` names, and the generated sandbox all name the same folders. |
| settings generator (G20) | gives each domain write access to exactly the folders it lists as `write`. G20 ships its own manifest reader, `domain.py manifests`, which reads every `~/Developer/*/domain.json` on the primary, or the manifests named on the command line. From those manifests the generator denies reads of any `sensitive` folder the domain doesn't list, so a research session never sees `taxes` or `medical`. The sandbox's `denyRead` blocks a sandboxed Bash read and not the Read tool (`spikes.md` item 7), so for each such folder the generator writes both a `sandbox.filesystem.denyRead` entry and a `Read(...)` rule in `permissions.deny`. A cloud session enforces no sandbox (`spikes.md` item 1), so the rehearsal checks the guard on the primary, against Bash, Read, Grep, and Glob (R-G20-2, R-G20-3). The dispatcher's `registry`, when it is built, reads the same manifests. Tests of the reader and the generator use fixture manifests, since `~/Developer` exists only on the primary. |
| template and `new-domain` (A5) | asks which folders in `~/Documents` the new domain works on, existing or new, and with what access. For a new folder, it offers to make it an Obsidian vault by copying a default `.obsidian/` config (today's `graph.json` pattern, made general). Folders are created on the Mac at the switch, not in the cloud. |
| `personal-assistant` (A4) | lists no folders yet. You add them with `new-domain`'s folder step when you build it out. |

### New: one repo for the core and the dispatcher; contracts in `AGENTS.md`

Settled after W0. It replaces the assistant architecture plan's separate
`assistant` repo, and wherever a source plan names `assistant`, read
`agent-core`'s root.

| Piece | Content |
| --- | --- |
| `agent-core` | one repo, two parts. `core/` holds what every domain shares: `skills/`, `agents/`, `workflows/`, `audit/`, `lib/` (the host ports for jobs and alerts), `templates/domain/`, `domain.py`. The root holds the Remote Control job and the root contract; the dispatcher's `domain.json`, its `.claude/settings.json`, and the skills `route`, `delegate`, `compose`, and `registry` join it when the dispatcher is built (§3, "Deferred"). The tests sit at the root, outside `core/`. |
| The front door | Until the dispatcher is built, Remote Control runs in `~/Developer/research-assistant`, the only domain with skills, and a remote session is a research session. When the dispatcher is built, Remote Control moves to `~/Developer/agent-core`, and the dispatcher hands each request to a session started in the owning domain's repo, so that domain's settings, sandbox, hooks, and MCP servers apply from its first turn. The dispatcher never loads a domain's contract into its own session: an instruction file cannot change a session's sandbox or permissions, and one session holding every domain's permissions is the combination §5 of the assistant plan forbids. |
| What a domain carries | `core/` alone, vendored at `vendor/agent-core/` with `git subtree` from the branch `core`, which `agent-core`'s CI writes with `git subtree split --prefix core` after every merge to `main`. The dispatcher's contract and skills never enter a domain. A domain symlinks the core skills, workers, and workflows it uses into `.claude/`; the dispatcher symlinks them from `core/` the same way. |
| Why a copy | the copy needs no setup in the build's cloud sessions or in CI, and a domain moves to a newer core only when it pulls on purpose. A checkout of `agent-core` beside each domain would also work, at the cost of setup in every environment and of the pinning. |
| Contracts | every repo's contract is `AGENTS.md`, a name other agent hosts read; `CLAUDE.md` holds the one line `@AGENTS.md`. The research contract moves in X2. |
| Host ports in the core | `Scheduler`, `Notifier`, and `SystemReadings`, with `Job`, `Notice`, and `Level`, and their macOS adapters, live in the core, because every domain runs jobs and raises alerts on the primary. The ports plan put them in `research-assistant`, and P1 declared them there; P5+M3 moves them. The research domain keeps the health job: its detectors, its workloads, and its journals. `SyncedFolder` stays in `research-assistant` with its iCloud adapter (P6+M4). The Linux adapters, `Accelerator`, `Trash`, and `Locations` wait with the other OSes (§3, "Deferred"). |
| Core code | the core's Python is one package, `core/lib/agent_core/`, so that no core module shadows a domain module of the same name. A domain reaches it by adding `vendor/agent-core/lib` to its module path; the dispatcher adds `core/lib`. NEVER re-export a core name from a domain module: a re-export is a copy that drifts. |
| State | `~/.agent-core/state/` on the primary: the dispatcher's ledger and preferences file, made when the dispatcher is built. |
| `assistant` | created in X0.1, holding one commit with a README, and not used: you delete it, or archive it to keep the name reserved. |

### Assistant architecture plan

- **The core is vendored, not installed as a plugin.** The docs say cloud
  sessions don't install plugins from `enabledPlugins`, and a local-directory
  marketplace path doesn't exist in the cloud or in CI. So `agent-core`'s
  `core/` enters each domain as a git subtree at `vendor/agent-core/`. Its skills, agents, and
  workflows are symlinked into `.claude/skills/`, `.claude/agents/`, and
  `.claude/workflows/`. The W0 spike found that relative symlinks load
  skills, agents, and workflows (`spikes.md` item 3), so no generated copy is
  needed; macOS was not tested, and the rehearsal checks it (R-A0-1). This
  gives four things:
  - skill names stay `clean-code` and `clean-prose`, so references and habits
    don't change;
  - workers keep reading `.claude/skills/clean-code/SKILL.md`;
  - CI needs no token to fetch the core;
  - a domain moves to a newer core on purpose, with `git subtree pull` (the
    plan's "pinned ref" option). The spike's round trip of `add`, `pull
    --squash`, and `split` worked (`spikes.md` item 6).
  A plugin packaging of the core can be added later for other people.
- **Fact fixes:**
  - the repo name sits on 26 lines in 12 files, including
    `gloss-bibliographies/SKILL.md:4`, plus two plists outside git;
  - the audit path is named in 11 places, including three test modules and
    `CLAUDE.md:450`;
  - only `extraction-fixer` names the audit script.
- **The research-only audit checks split by machine.** `works` and `special`
  run anywhere. `residue` and the count-against-disk `staleness` need the real
  vault, so they run only on the primary.
- **Remote Control already runs.** A hand-written
  `local.claude-remote-control.plist` with `--spawn worktree` and no
  `caffeinate` is loaded. In worktree mode no remote session can run a batch,
  because preflight refuses a worktree (`_ingest/checkout.py:56-59`). Fix: the
  Remote Control job runs in `~/Developer/research-assistant`, the main
  checkout, in `same-dir` mode, so a remote session can run a batch.
- **The personal domain is a skeleton.** This round builds the domain
  template, `new-domain`, and `personal-assistant` from them (A5, A4). The
  dispatcher (A3) and its `inbox` and `schedule` skills wait until the
  personal domain's own skills show what the two domains share.

### Audit upgrade plan

- **The audit engine moves to the core first, as is (A2). The upgrade PRs
  then build it there.**
  - In the core the skill is `control-plane-audit`. The research domain keeps
    `vault-audit` as a thin skill that invokes it, adding the research checks.
  - Each domain keeps its own baseline at `audit/baseline.json` in its repo.
- **The > 40-word sentence cleanup (the audit plan's PR 2b) is U2b.** It runs
  in W5, once U3 has measured the long tail, and grows no file's word count.
- **The bench needs `root` threaded through more code.** Only
  `ControlPlaneFiles` takes a `root` today. `Baseline._present`,
  `FileMeasures._finding`, `Residue`, and `AuditSet`'s `BASELINE_PATH` default
  must take it too.
- **The extra ruff rules run inside `audit.py lint`**, ratcheted by
  fingerprint. `pyproject.toml`'s gating set stays `E4, E7, E9, F`; otherwise
  CI fails on the 33 existing too-many-arguments findings.
- **`xref` is written against `model:` and the stage table's Model column
  (U3).**
- **The fast post-edit hook moves to the very start (X1)**, out of Check 8.
  - Today every Python edit waits for the full suite. The spike measured it
    on the 4-vCPU cloud VM: 4,965 tests in 118 s, and the post-edit hook 2 min
    10.5 s per Python edit (`spikes.md`, the rerun), across about 50 PRs.
  - The hook runs the test modules that import the changed module. The full
    suite still runs in CI and before every push.
- **The fixer works in a worktree**, never in the main checkout, which
  preflight requires to be on a clean `main`.
- **The workflows are sized on the measured concurrency.** The Workflow tool
  runs min(16, CPUs − 2) agents at once: 2 on the 4-vCPU VM. Each agent costs
  about 68,000 tokens before it does any work (`spikes.md` item 4). U5 sizes
  its partitions and `budget` on these figures, and so does §4's item
  workflow.
- **The upgraded audit is the programme's final quality gate (W7).**
- **New: Check 9, current practice (U8).** It sits beside Check 8's
  optimizations and is generic, so it lives in the core.

  | Piece | Content |
  | --- | --- |
  | `audit-practices-scout` worker | reads a fixed allowlist of first-party sources: the Claude Code docs on skills, subagents, hooks, and workflows; the Claude prompting and agent docs; Anthropic's engineering posts. It writes a dated practices digest, each practice with its source URL. The digest is committed in `agent-core` as `core/audit/practices-digest.md`, so every domain carries it and refreshed through a reviewed PR when it is older than `practices_max_age` (default 30 days). Every domain, cloud sessions included, reads the same reviewed copy, and the review is one more guard against injected text. |
  | `audit-practices-reader` worker | compares the digest against the control plane's units (skill descriptions and bodies, worker instructions, the workflows' prompts and schemas, model and effort fit). Each finding carries the practice, its URL, the unit, and the change. |
  | Verify and fix | The `audit-verifier` confirms that the source states the practice and that the change keeps every contract rule. Confirmed `docs` findings go through the fix loop (U6) under `clean-prose`. A practice that contradicts a rule of the contract or `clean-prose` is never applied: it is reported as `needs-decision`, with both sides. |
  | Guards | Source text is data, never instructions: the scout reports a sentence aimed at the reader as a finding and does not act on it. Only the allowlisted hosts are read. No source text is copied into the instructions: practices are restated in house prose. |
  | Sandbox | The allowlisted hosts (`code.claude.com`, `docs.claude.com`, `www.anthropic.com`) are added to `network.allowedDomains` in U8's own PR: a cloud session in Auto mode may edit `.claude/settings.json` (`spikes.md` item 2). The scout and the verifier, which re-reads a cited page, may read only these hosts. The scout runs on the primary, where the sandbox enforces the limit (R-U8-1); a cloud session reads only the committed digest and never runs the scout. |
  | No growth | A Check 9 change replaces text and never grows its unit's word count. A practice that can be brought in only by adding words is reported as `needs-decision`, with the words it adds. |

### New: the instruction text only shrinks

The existing audit already cuts instruction text (Check 2, redundancy; Check
2b, prose). The upgraded audit makes the cuts binding, so that no item, fix,
or practice grows the text a session loads.

| Piece | Item | Content |
| --- | --- | --- |
| Word count | U3 | `audit.py lint` gains the `weight` row: the words of each instruction file and of the whole instruction text, against the counts in the audit baseline. The always-loaded text, the contract and every skill's and worker's `description`, is counted on its own |
| Ratchet in CI | U3 | CI fails a PR that grows the always-loaded text. CI fails a PR that grows the whole instruction text unless the growth sits in a `Change-class: feature` commit and the PR body states the words added and the rule each serves. A fix or a refactor never grows the text. A merged PR that cuts the text lowers the baseline's counts |
| Cuts first | U5 | Every run's report opens with the cuts: each as replacement text with the words it saves, ranked by how often the text is loaded (`clean-prose` §10), and the run's total saved. The prose reader judges each unit against `clean-prose` §7–8; the redundancy checker names each duplicate's single home |
| Redundancy gates | U3, U5 | `redundancy` rows fail CI once the bench measures their precision at 0.9 or higher |
| No rule lost | U6 | The fix loop applies a cut only with A1's diff check: every rule of the old text maps to a sentence of the new. A cut that drops a rule is reverted and reported |
| No growth | U2b, U8 | U2b's splits and Check 9's practices grow no file's word count |
| Cut target | X7.1 | The closing audit run cuts the whole instruction text by at least 20% of its words, the contract first. If the target cannot be met without dropping a rule, the run reports the shortfall and drops no rule |

### Hexagonal ports plan

- **This round builds only what the primary uses.** P1 (merged) declared the
  ports and the `mac-local` profile. P5+M3 builds the host ports' macOS
  adapters and the two jobs; P6+M4 builds `SyncedFolder` with its iCloud
  adapter and the placeholder halt. Every other item of the ports plan serves
  another OS, a hosted API, or another agent host, and waits (§3,
  "Deferred").
- **Counts, for the deferred `Vault` refactor (P7).**
  - 65 modules use the path constants, not 58, plus 92 test files that patch
    them.
  - 12 modules read `machine.json`, not 9.
  - There are no `sys.platform` skips: only typst, the HF model cache, and
    node.
- **CI runs on Linux; the rehearsal runs the suite on macOS.** P2 is dropped:
  every CI job runs on Linux, so that PRs stay fast, and the rehearsal runs
  the full suite on the primary's macOS (R-P2-1).
- **PR 22, the Python batch driver, is deferred.** It is the largest change,
  and it pays off only when a second agent host is actually wanted.

### Primary/secondary plan

- Its item 3 becomes "codify and fix the existing service": a `Scheduler` job,
  `caffeinate -i`, `KeepAlive`, `~/Developer/research-assistant` as its
  working directory until the dispatcher is built, and `same-dir` spawning.
  - The new jobs take labels of their own, so the old hand-written plists stay
    untouched and the rollback can reload them.
  - The job passes no `--name`, because the contract forbids naming a machine
    in the control plane.
  - The job's code is built at `agent-core`'s root, on the core's `Scheduler`
    port, because the job serves the machine, never one domain. No domain
    carries it. Its working directory is an argument, so the dispatcher
    moves it to `~/Developer/agent-core` with no code change.
- Item 4 (the iCloud placeholder check) is included, through `SyncedFolder`.
  No documented way to read the Optimize Mac Storage setting is known, so
  preflight infers it from placeholders in the library and the inbox, and
  the rehearsal checks for none (R-P6+M4-1).
- Item 5 (retiring the laptop install) is the last step of the switch. It is
  done by hand: `launchctl bootout` and deleting the plists. The laptop keeps
  only the frozen checkout, which has no `uninstall`; `Scheduler.remove`
  serves installs that run the new code.

## 2. Invariants every item obeys

1. **Nothing touches the running setup before the switch.** No item writes to
   `~/.research-vault`, the launch agents, `~/.claude/settings.json`, or the
   `research-tools` checkout on the Mac.
2. **The vault stays readable by both editions.** No item changes a vault
   format: corpus frontmatter, bibliographies, notes, the extraction records,
   or `machine.json`. Only additive keys are allowed.
3. **`mac-local` behaves exactly as today.** Each ports item states how this is
   checked: by a test in CI, or by a rehearsal step on the Mac (§6).
4. **The contract's rules hold in the new repos.**
   - `clean-code` is invoked before code, and `clean-prose` before
     instruction text.
   - The suite, ruff, and the audit linter pass.
   - Work goes on a branch cut from `main`, reaches `main` through a PR, and
     the PR is titled by the rule it leaves in place.
   - Every commit carries a `Defect-class:` or `Change-class:` trailer.
5. **Each item adds its Mac-only acceptance checks to
   `upgrade/rehearsal.md`.** Nothing is lost between a cloud PR and the
   rehearsal. An item edits only the section headed by its own ID, so lanes
   running in parallel do not conflict there.

## 3. Waves and items

The IDs name the source: **X** programme, **M** machines, **A** assistant,
**U** audit, **P** ports, **G** the ports plan's agent-host track (Track G),
which lands in the core. Each item is one PR in its source plan's sense, and
its content and acceptance are the source plan's, as amended in §1. Items in
the same wave and different lanes run in parallel. A lane is a set of items
that touch disjoint files.

| Wave | Lane | Item(s) | Repo | Depends on |
| --- | --- | --- | --- | --- |
| **W0 setup** | — | X0.0–X0.5 (§4; there is no X0.3) | all | plan approved |
| **W1 foundations** | a | **X1** fast post-edit hook (affected modules; full suite in CI and pre-push; §5 text) → **X2** contract: trailers, primary/secondary roles (M §1), "both machines" narrowed, the contract moved to `AGENTS.md` with `CLAUDE.md` importing it (§1) → **X3** the repo's own name: the 26 lines in 12 files that name `research-tools` now name `research-assistant` (the two plists outside git change at the switch) | research-assistant | W0 |
| | b | **P1** ports, `providers.py`, profiles; P2 is dropped (§1, "Hexagonal ports plan") | research-assistant | W0 |
| | c | **A0** `agent-core` skeleton: `core/` and the root dispatcher's layout (§1), CI (suite and ruff; A2 adds the audit linter), the branch `core` written by CI, the `vendor` subtree of `core/` into research-assistant, the symlink layout | agent-core + research-assistant | W0 spike |
| **W2** | a | **A1** `clean-code`/`clean-prose` split into the core's general text plus the research overlay `.claude/code-overlay.md` and `.claude/glossary.md` (diff check: no rule lost) → **U2** STE rules in the core's `clean-prose` | both | A0 |
| | b | **P5+M3** `Scheduler`/`SystemReadings`/`Notifier` moved into the core, with the launchd adapter and its `remove` and the macOS readings and notifiers; the health job on the core's ports; the Remote Control job at `agent-core`'s root, working in `~/Developer/research-assistant` (code only, installed at the switch) → **P6+M4** `SyncedFolder` with its iCloud adapter, and the preflight halt on a placeholder | agent-core, then research-assistant | A0, P1 |
| **W3** | a | **A2** audit engine to the core, as is; research checks in `audit/checks.py`; a thin `vault-audit` skill; hook, CI, tests, `extraction-fixer` repointed → **U1** bench → **U3** lint layer, with the `weight` row and the word ratchet → **U4** units, closure, baseline v2 | both | A1, U2 |
| | b | **G20** research `domain.json` created with its `folders` and `policy`, the manifest reader, and one settings generator, with the sensitive-folder read guard | agent-core + research-assistant | A1 |
| **W4** | a | **U5** audit workflow and workers, its report opening with the cuts → **U6** loop and fix (worktree), no rule lost → **U7** Check 8 (plus stage timings in `ingest.py`) → **U8** Check 9, current practice, with no growth | agent-core (+ research for timings) | U4 |
| | b | **A5** domain template + `new-domain`, with the folder step (folders in `~/Documents`, access, optional Obsidian vault) → **A4** `personal-assistant` made by `new-domain`, no skills and no folders yet | agent-core, personal-assistant | G20 |
| **W5** | a | **U2b** the > 40-word sentence cleanup, with no file's word count grown | research-assistant | U3, U8 |
| | b | **P16** the README per role, for the primary: install on macOS; "Two machines: primary and secondaries"; "Retire a former full install" | research-assistant | X2, P5+M3 |
| **W6** | — | **Deferred: not in this round** (below) | — | — |
| **W7 hardening** | — | **X7.1** the upgraded audit in `all` mode with the fix loop, on every repo, toward the 20% cut target → **X7.2** a completeness critic: every acceptance row of the items this round builds has a CI test or a line in `rehearsal.md` → **X7.3** `cutover.py rehearse \| switch \| rollback` (read-only form first) and the switch runbook | all | W5 |
| **W8** | — | rehearsal and switch on the Mac, with you (§6) | — | W7 |

**Deferred.** Each item below has the status `deferred` in its item file,
and the item workflow stops on it. Each waits for the need its row names;
until you name that need, nothing of it is built.

| Item(s) | Builds | Waits for |
| --- | --- | --- |
| P3, P4 | search ports; API embedder and reranker | a hosted search provider you want to use |
| P9, P10 | transcriber and diarizer ports; hosted transcription | a hosted transcription provider you want to use |
| P7a–P7h | the `Vault` object and `Locations` over 65 modules; test vaults | a second OS, or a vault outside `~/Documents` |
| P11, P12, P13 | `LayoutEngine` port; Marker API and `calibrate`; `LineRecognizer`, Tesseract, and `calibrate-ocr` | a second layout engine or OCR engine you want to use |
| P8, P14, P15 | the contract per OS; requirement extras and locks; `bootstrap` and `doctor` | a second OS, or a second user's install |
| P5+M3's and P6+M4's other-OS parts | systemd, the Linux readings, `notify-send`, ntfy; `Accelerator`; `Trash` | a second OS |
| G17, G18, G19, G21 | model tiers; `HookIo` and the git pre-commit fallback; worker specs and the generator; capability names in the prose | a second agent host |
| A3 | the dispatcher at `agent-core`'s root: `route`, `delegate`, `compose`, `registry`, `approvals`, `dispatch`; `handles`, `entry_skills`, `exposure`, `unattended` | the personal domain's own skills, which show what the domains share |
| P22 | the Python batch driver | a second agent host |

**Why this order:**

- **X1 goes first** because it makes every later edit cheap.
- **The contract trailers and roles go next**, because every later commit and
  item cites them.
- **The core split (A1) comes before the audit (A2, U*) and before G20**,
  because the audit parses the glossary and lives in the core, and G20's
  `domain.py` lives in the core.
- **The domain template (A5) comes after the single settings generator
  (G20)**, because `new-domain` prints the settings block G20 generates.
- **A settings change after G20 goes through `domain.json`.** Once G20 has
  merged, an item that changes `.claude/settings.json` (U3's
  `excludedCommands`, U8's hosts) edits the `policy` of `domain.json` and
  writes the settings the generator prints. If G20 merges while such an item
  is open, the item moves its settings change into `policy` when it merges
  `main`.
- **U2b comes after the audit track (W4-a)**, because U5 and U6 rewrite the
  audit skills that U2b's sentence cleanup also edits.
- **A Vocabulary row added on a branch while A1 runs moves on merge.** A1
  moves `clean-prose`'s Vocabulary to `.claude/glossary.md`; a W2 item of
  another lane that adds a row resolves the merge conflict by adding the row
  to the glossary.

**A core pull.** An item that changes the core opens the core's PR first; its
domain PR runs `git subtree pull --prefix vendor/agent-core` after the core's
PR merges, and names that PR.

- A domain PR's pull MAY carry another lane's merged core change. The change
  stays inert until that lane's own domain PR links or imports it.
- If another lane's pull merges into the domain's `main` first, and the PR
  then conflicts under `vendor/agent-core/`, rerun the pull on the new `main`
  and drop the earlier pull commit. NEVER resolve a conflict under
  `vendor/agent-core/` by hand: the vendored core changes only by
  `git subtree pull`.

## 4. Running it in the cloud

### W0: one setup sitting with you

| Step | What |
| --- | --- |
| X0.0 | **Seed `research-assistant`, private** (this local session, after your yes): copy `research-tools` `main` as one squashed snapshot into a new **private** GitHub repo, `research-assistant`. Add `upgrade/` (the unified plan as `PLAN.md` and the four source plans in `sources/`) and `bin/cloud-setup.sh`. The `research-tools` checkout is only read; it is never changed. Every later W0 step runs in a cloud session on this repo, because a cloud session can open only what is on GitHub. |
| X0.1 | **Pre-publish scan, then go public** (cloud, on the private `research-assistant`; only the snapshot is ever published, so the old history needs no scan): secrets (gitleaks over the snapshot); absolute personal paths; work titles and source text in `tests/fixtures/` (copyright); anything personal in the instruction text. Fix the findings in a PR. Then create `agent-core` and `assistant` as **public** repos and `personal-assistant` as **private**, and make `research-assistant` public. Install the Claude GitHub App on all four. Protect `main`: a PR and green CI required. Require approval before workflows run on PRs from forks. Every public repo gets a **publish-guard** CI job: gitleaks plus the audit's `works` check, so no PR can make a secret or a work's text public. **Done**; since then the dispatcher's place is `agent-core`'s root (§1), so you delete or archive `assistant`. **Still yours:** in each repo, allow auto-merge (Settings → General) and add the `decision-gate` check to `main`'s required checks (§5). |
| X0.2 | Cloud environment `research`, network Limited with the package-manager defaults, plus the hosts the spike's rerun lists: `download.pytorch.org`, `download-r2.pytorch.org`, `openaipublic.blob.core.windows.net`, `github.com`, `objects.githubusercontent.com`, `release-assets.githubusercontent.com`, `models.datalab.to`, and `astral.sh` only if the image lacks uv. The environment's setup script runs outside the repository and without network (`spikes.md` item 8), so it is an `echo`. The SessionStart hook in `.claude/settings.json` runs `bin/cloud-session-start.sh`, which runs `bin/cloud-setup.sh` until `~/.research-vault/cloud-setup.done` exists, so a PR changes the setup and nothing is updated by hand. `bin/cloud-setup.sh` mirrors CI: uv; `~/.research-vault/venv` built from `requirements.lock` with `UV_TORCH_BACKEND=cpu`; the empty-vault `machine.json` (the contract allows this in a test container); pandoc 3.12; node; tiktoken prefetched into `~/.research-vault/tiktoken`; the CI env vars. Its steps that need no PyPI run before the sync (PR #3), and it sends each `NO_PROXY` host the container cannot resolve through the gateway (PR #4). **Without a venv at that path, every hook exits 2 and blocks all Bash and Write. With a venv that holds no packages, Bash works, every Write is blocked, and every Edit reports a hook error.** Environment `core`: Python, uv, ruff, pyyaml, tiktoken. |
| X0.4 | Spike session (cloud, about an hour), results in `upgrade/spikes.md`: (1) hooks and suite run, and their timing; (2) whether Auto mode may edit `.claude/settings.json`; if not, settings changes ship as patches in `upgrade/settings-patches/` and you apply them at the switch; (3) whether symlinked skills, agents, and workflows load; (4) whether the Workflow tool runs, and its real concurrency on 4 vCPU; (5) push and PR creation; (6) `git subtree` round trip; (7) on the Mac, whether the sandbox's read-deny setting blocks reads of a folder, which the cross-domain read guard relies on; (8) whether the environment's setup script sees the cloned repo. **Done:** `spikes.md` holds the results, and this plan carries their consequences. |
| X0.5 | Complete `upgrade/` in `research-assistant` (cloud): `items/<id>.md`, `rehearsal.md`, and the item workflow `upgrade-item.js`, beside the plans X0.0 put there. `vault-audit` excludes `upgrade/`: its scope patterns name no path under it. `upgrade/` is deleted at the switch. The `decision-gate` CI job of §5 ships with it. |

### The orchestration

```
conductor (a desktop-app session; touches nothing local)
  │ per wave: ready items → lanes with disjoint files
  ├── cloud session, lane a ── runs upgrade-item.js on each item in turn ──► PRs
  ├── cloud session, lane b ── …                                         ──► PRs
  └── cloud session, lane c ── …                                         ──► PRs
  │ merge gate (§5), then the next wave
```

- **One cloud session per lane**, so each lane has its own VM: 4 vCPU and 16
  GB. Lanes in one VM would fight over the test suite.
- **Inside a lane, the saved workflow `upgrade/upgrade-item.js` runs each
  item**, with six agents per item and at most eight with two fix rounds,
  under the 10-agent guideline. The lane's session runs it with the Workflow
  tool's `scriptPath` and `args: {item: "<id>"}`:

  | Phase | Agent(s) | Does |
  | --- | --- | --- |
  | Scope | 1 reader | reads the item, `PLAN.md` §1–5, and the code areas; stops the item if it is deferred, if a dependency has no `Upgrade-item:` commit on `main`, or if a repo it names is not attached; returns files, tests to add, risks, and the rehearsal checks needed |
  | Build | 1 implementer (worktree) | implements under the repo's contract on the branch `upgrade/<item>`: `clean-code`/`clean-prose`, a test that builds the defect class or pins the behaviour, the trailers |
  | Verify | 3 refuters, two at a time | lenses: **behaviour** (does `mac-local` change?), **contract** (`clean-prose`, special cases, cross-references, readers of every new field), **acceptance** (each row met in CI, or listed for the rehearsal) |
  | Fix | the implementer | a new agent per round, in a worktree on the same branch; fixes the confirmed findings and reruns the checks; at most two rounds, then the item goes to `needs-decision` |
  | Publish | 1 | pushes, opens the PR with the GitHub MCP tools (title by rule; body: acceptance table, rehearsal lines, open questions); auto-merge when nothing is left for you, otherwise a draft labelled `needs-decision` |

- **What the spike measured binds the lanes** (`spikes.md` items 4 and 5).
  The Workflow tool runs two agents at once on the 4-vCPU VM, so the three
  refuters take two rounds of agent time. Each agent costs about 68,000 tokens
  before it does any work, about 0.4 to 0.55 million tokens per item. A cloud
  session pushes its branch and opens its PR against `main` without you.
- **Every upgrade commit carries `Upgrade-item: <id>`** beside its
  `Defect-class:` or `Change-class:` trailer. The Scope reader finds an item's
  dependencies on `main` by that trailer.
- **The lane's session prompt authorizes the `upgrade/<item>` branches.** A
  cloud session pushes only to the branches its prompt names.
- **Each agent that edits runs the checks itself.** The post-edit hook checks
  the checkout `$CLAUDE_PROJECT_DIR` names, never the agent's worktree, until
  X1 makes it check the worktree that holds the edited file.
- **A lane runs its items one after another, each after the one before has
  merged.** Each item depends on its predecessor being on `main`, and
  auto-merge (§5) merges a PR that clears the gate without waiting for you.
  The lane's session subscribes to each PR it opens, drives it to green, and
  starts the next item when the PR merges.
- **Cloud sessions can't message back.** The conductor reads their results
  from GitHub: PRs, CI, and labels.

### Starting a lane

Start one cloud session per lane, in the environment `research`, with every
repo the lane's items name attached. A lane whose items touch only
`agent-core` MAY use the environment `core`. Give it this prompt, with the
lane and its items filled in:

```
Run lane <wave>-<lane> of upgrade/PLAN.md §3: items <id>, <id>, … in that order.
You may push to the branch upgrade/<item> of each item, in every repo the item names.
For each item:
1. Run the saved workflow upgrade/upgrade-item.js with the Workflow tool's
   scriptPath and args {item: "<id>"}, and read its result.
2. If the result's status is "stopped", or needs_decision is true, stop the lane
   and report the item, its reasons, and its PR links.
3. Otherwise subscribe to each PR it opened and drive each to green. When every
   PR of the item has merged, start the next item.
When the last item has merged, report the PRs and the rehearsal lines added.
```

W1 starts three lanes: a (X1, X2, X3), b (P1), and c (A0, with
`agent-core` attached).

## 5. Merge gate in the new repos

A PR merges into a new repo's `main` when all of these hold:

- CI is green: the suite, ruff, the audit linter, and the repo's own jobs;
- the three refuters found nothing they could not refute, or the fix rounds
  cleared it;
- the PR merges without conflict onto the current `main`;
- no `needs-decision` label is open.

**Auto-merge enforces the gate.** The item workflow's publisher turns on
auto-merge, with merge commits, only for a PR that has no reason for your
decision; otherwise it opens a draft labelled `needs-decision`, and GitHub
merges no draft. The `decision-gate` CI job fails while the PR carries the
label, and `main`'s required checks name it, so a label added later also
holds the PR. GitHub merges no PR with a conflict.

Anything else waits for you. A PR comment states the question; you answer,
remove the label, and mark the PR ready. The conductor lists open decisions at
each wave's end.

## 6. Rehearsal and switch (W8, on the Mac, with you)

1. **Pick a gap between backfill runs**, with no batch running. Clone the new
   repos into `~/Developer/` beside the old checkout.
2. **Rehearse in a staging home.** `cutover.py rehearse` sets `HOME` to
   `~/.staging-home`, so every `~` path is staged, and builds:
   - a venv from `requirements.lock`;
   - a staging vault: copies of a sample of reviewed works, their PDFs, and the
     bibliographies.

   Ollama and Zotero are shared read-only. No Stage 1 runs, so nothing touches
   Zotero.
3. **Run `rehearsal.md`, old against new.** It holds every Mac-only acceptance
   row the items collected, including:
   - the full suite on macOS;
   - a health sample;
   - no iCloud placeholder in the library or the inbox;
   - an `ingest` dry run;
   - a Stage 2 → 6 backfill of three works in the staging vault;
   - one research question answered from a local session in the research
     checkout; Remote Control is checked after the switch, in step 4.7;
   - the symlinked core skills, workers, and workflows loading on macOS
     (A0; the spike tested Linux only);
   - the sandbox's write limits and the sensitive-folder read guard against
     Bash, Read, Grep, and Glob (G20): a cloud session enforces no sandbox,
     so no cloud PR can verify them.
4. **Switch** (`cutover.py switch`, read-only form first):
   1. Unload the old health and Remote Control jobs.
   2. Move the old venv aside.
   3. Apply `~/.claude/settings.json`. No settings patches exist: the item
      PRs edit `.claude/settings.json` themselves (`spikes.md` item 2).
   4. Build the venv from `requirements.lock` with the contract's `uv pip
      sync` command, and set `core.hooksPath` to `.githooks` in each new
      checkout. The jobs wait for step 6.
   5. Run `claude remote-control` once by hand in
      `~/Developer/research-assistant`, to answer its enable and folder-trust
      prompts. A job can't answer them.
   6. Install the health and Remote Control jobs through the core's
      `Scheduler`, under their new labels: the health job with `health.py
      install --apply` in `~/Developer/research-assistant`, the Remote Control
      job with `bin/remote_control.py install --apply` in
      `~/Developer/agent-core`, its working directory
      `~/Developer/research-assistant`.
   7. **Check what the staging home can't rehearse:** from the laptop or the
      phone, open a session through Remote Control, ask one research question,
      and start a dry-run batch in that session. If any of these fails, roll
      back.
5. **Rollback** (`cutover.py rollback`): reload the old jobs, restore the old
   venv, and work from `~/Developer/research-tools`. Keep the rollback ready for
   two weeks, then archive `research-tools` on GitHub.
6. **Retire the laptop's install by hand**, following the README's "Retire a
   former full install."

## 7. Defaults I chose (say so before W0 if you disagree)

1. The dispatcher, when it is built, lives at `agent-core`'s root (§1);
   `assistant` is deleted or archived.
2. `research-assistant` and `agent-core` are public from W0, after the
   pre-publish scan; `personal-assistant` is private. The old
   `research-tools` stays private, and its CI keeps using your quota until the
   switch.
3. PRs in the new repos merge on the gate in §5, through auto-merge, without
   asking for each one.
4. Until the dispatcher is built, Remote Control works in
   `~/Developer/research-assistant`.
5. The closing audit run's cut target is 20% of the instruction text's words
   (§1, "New: the instruction text only shrinks").
6. The items §3 lists as deferred are not in this round.

## 8. Verification

- **Per PR, in the cloud:** CI (suite, ruff, audit linter), the three
  refuters, and the item's acceptance rows.
- **Per wave:** the conductor checks that each merged item's acceptance rows
  are met or listed in `rehearsal.md`. From W4 on, it also runs the upgraded
  audit on the wave's changed units.
- **Before the switch:** X7.1, the full audit with the fix loop, and X7.2, the
  completeness critic, close the build. §6's rehearsal is the last gate. The
  switch happens only when every line of `rehearsal.md` passes old against new.

## Critical files (research side)

- `AGENTS.md` (after X2; `CLAUDE.md` imports it), `README.md`, `.claude/settings.json`, `lib/harness_hooks.py`
- `.github/workflows/ci.yml`, `.github/actions/empty-vault/action.yml`
- `lib/_vault/paths.py`, `lib/_vault/machine.py`, `lib/_health/{installer,launch_agent,hook}.py`
- `.claude/skills/{clean-code,clean-prose,vault-audit}/`
- `.claude/skills/ingest/scripts/_ingest/{preflight,checkout}.py`, `.claude/workflows/{ingest,resolve-tasks}.js`
- `.claude/agents/*.md`, `requirements.{txt,lock}`, `pyproject.toml`
