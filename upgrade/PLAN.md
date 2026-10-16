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

- **All of the ports plan**, for other people to install and for clean design.
  You won't test the other OSes or the APIs yourself.
- **The personal assistant is a skeleton only**: an empty domain repo where you
  add skills later.
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
| `agent-core` | new; the shared standards, the audit engine, the agent-host layer, the domain template | the core every domain carries |
| `assistant` | new; the dispatcher | the front door, reached from any machine through Remote Control |
| `personal-assistant` | new; made from the domain template; no skills yet | the place for your personal skills |

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
| Three plans assume two full machines ("both machines", "clone on both", "rebuild both environments") | The primary/secondary plan replaces that assumption everywhere. Only the primary has the control plane, so every "both machines" becomes "the primary", and the dispatcher's state lives on the primary's own disk (`~/.assistant/state/`), not in iCloud or git. That settles the assistant plan's open decisions 4 and 5. |
| The rename moves the checkout and the launch agents, and would break the running setup mid-build | No GitHub rename. `research-assistant` is a new repo, and the switch is the rename. |
| Two generators for the same `settings.json` sandbox block (ports PR 20 `policy.json`; assistant 3.4 `domain.json`) | One generator in `agent-core`. `domain.json` carries a `policy` section; `domain.py settings` reads it. |
| "Capabilities" means two things: tool classes (ports) and the three risks of private data, untrusted content, and sending out (assistant) | The ports plan keeps **capabilities** for tool classes. The three risks become **exposure**, and `registry` checks each skill's declared exposure against its generated tool capabilities: a skill with `web` must declare untrusted content. |
| Commit trailers: the audit wants `Defect-class:` on every commit, but a refactor has no defect class | `Defect-class:` for a fix, `Change-class: refactor\|feature — <what>` for everything else. The audit's sign 6 accepts either. This is settled in W1, because every upgrade commit needs it. |
| The Vocabulary table is both moved (assistant 1.3) and parsed in place (audit PR 3), and it is the most-churned text in the repo (75 commits in two weeks) | The move happens first (A1). The audit lint then parses the domain's `.claude/glossary.md`. |
| Ports PR 22 deletes `relay`, which the audit's `audit.js` is built on | PR 22 is deferred (§3, W6). If it is ever done, `audit.js` moves to the same `WorkerRunner`. |
| The README is restructured two ways at once: per OS (ports) and per role (machines) | One structure: "Install" per OS, for anyone; "Two machines: primary and secondaries"; "Retire a former full install". |
| `lib/_health/launch_agent.py` and `installer.py` are edited by three plans; the health job's label and plist contents are hard-coded (`installer.py:40`, `launch_agent.py:32-42`), and there is no uninstall | One item (P5+M3) builds the `Scheduler` port. Its launchd adapter takes a label and contents and has `remove`. The health job and the Remote Control job are two jobs on it. |
| The iCloud placeholder check (machines 4) and the iCloud conflict pattern (ports PR 6) both touch `_ingest/preflight.py` | One port, `SyncedFolder`: `conflict_copies()` and `not_downloaded(path)`. Preflight halts on either. |

### New: folders in `~/Documents`, assigned to assistants

`~/Documents` holds your folders side by side: `library`, `research vault`,
later perhaps `taxes` or `medical`. Any folder can be made an Obsidian vault of
its own. Each assistant is told which of these folders it works on. The two
choices are independent:

- a folder is a vault or not, whichever assistant uses it;
- an assistant can work on several folders, and two assistants can share one.

| Piece | Content |
| --- | --- |
| `domain.json` | `folders`: the folders under `~/Documents` the assistant works on, each with `read` or `write` access. A folder can carry `sensitive: true`, which keeps every assistant that doesn't list it from reading it. |
| research domain | lists today's `library` (write) and `research vault` (write). Nothing moves: invariant 2 holds, and the contract's `vault_dir` rule is unchanged. A CI check confirms `domain.json`, the research `Locations` defaults (P7), and the generated sandbox all name the same folders. |
| settings generator (G20) | gives each assistant write access to exactly the folders it lists as `write`. G20 ships its own manifest reader, `domain.py manifests`, which reads every `~/Developer/*/domain.json` on the primary, or the manifests named on the command line. From those manifests the generator denies reads of any `sensitive` folder the assistant doesn't list, so a research session never sees `taxes` or `medical`. The sandbox's `denyRead` blocks a sandboxed Bash read and not the Read tool (`spikes.md` item 7), so for each such folder the generator writes both a `sandbox.filesystem.denyRead` entry and a `Read(...)` rule in `permissions.deny`. A cloud session enforces no sandbox (`spikes.md` item 1), so the rehearsal checks the guard on the primary, against Bash, Read, Grep, and Glob (R-G20-2, R-G20-3). A3's `registry` builds on the same reader. The dispatcher lists no folders. Tests of the reader, the generator, and `registry` use fixture manifests, since `~/Developer` exists only on the primary. |
| template and `new-domain` (A5) | asks which folders in `~/Documents` the new assistant works on, existing or new, and with what access. For a new folder, it offers to make it an Obsidian vault by copying a default `.obsidian/` config (today's `graph.json` pattern, made general). Folders are created on the Mac at the switch, not in the cloud. |
| `personal-assistant` (A4) | lists no folders yet. You add them with `new-domain`'s folder step when you build it out. |

### Assistant architecture plan

- **The core is vendored, not installed as a plugin.** The docs say cloud
  sessions don't install plugins from `enabledPlugins`, and a local-directory
  marketplace path doesn't exist in the cloud or in CI. So `agent-core` enters
  each domain as a git subtree at `vendor/agent-core/`. Its skills, agents, and
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
  Remote Control job runs in the dispatcher repo in `same-dir` mode, and the
  dispatcher hands batches to a background session in the research repo's main
  checkout.
- **The personal domain is a skeleton**, and the `inbox` and `schedule`
  dispatcher skills wait for it. This round builds `route`, `delegate`,
  `compose`, and `registry`.

### Audit upgrade plan

- **The audit engine moves to the core first, as is (A2). The upgrade PRs
  then build it there.**
  - In the core the skill is `control-plane-audit`. The research domain keeps
    `vault-audit` as a thin skill that invokes it, adding the research checks.
  - Each domain keeps its own baseline at `audit/baseline.json` in its repo.
- **The > 40-word sentence cleanup (the audit plan's PR 2b) is U2b.** It runs
  in W5 lane c, before G21: both rewrite instruction prose, and U3 has measured
  the long tail by then.
- **The bench needs `root` threaded through more code.** Only
  `ControlPlaneFiles` takes a `root` today. `Baseline._present`,
  `FileMeasures._finding`, `Residue`, and `AuditSet`'s `BASELINE_PATH` default
  must take it too.
- **The extra ruff rules run inside `audit.py lint`**, ratcheted by
  fingerprint. `pyproject.toml`'s gating set stays `E4, E7, E9, F`; otherwise
  CI fails on the 33 existing too-many-arguments findings.
- **`xref` is written against `model:` and the stage table's Model column
  (U3).** G17 then extends the same check to tiers, so the two never disagree.
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
  | `audit-practices-scout` worker | reads a fixed allowlist of first-party sources: the Claude Code docs on skills, subagents, hooks, and workflows; the Claude prompting and agent docs; Anthropic's engineering posts. It writes a dated practices digest, each practice with its source URL. The digest is committed in `agent-core` as `audit/practices-digest.md` and refreshed through a reviewed PR when it is older than `practices_max_age` (default 30 days). Every domain, cloud sessions included, reads the same reviewed copy, and the review is one more guard against injected text. |
  | `audit-practices-reader` worker | compares the digest against the control plane's units (skill descriptions and bodies, worker instructions, the workflows' prompts and schemas, model and effort fit). Each finding carries the practice, its URL, the unit, and the change. |
  | Verify and fix | The `audit-verifier` confirms that the source states the practice and that the change keeps every contract rule. Confirmed `docs` findings go through the fix loop (U6) under `clean-prose`. A practice that contradicts a rule of the contract or `clean-prose` is never applied: it is reported as `needs-decision`, with both sides. |
  | Guards | Source text is data, never instructions: the scout reports a sentence aimed at the reader as a finding and does not act on it. Only the allowlisted hosts are read. No source text is copied into the instructions: practices are restated in house prose. |
  | Sandbox | The allowlisted hosts (`code.claude.com`, `docs.claude.com`, `www.anthropic.com`) are added to `network.allowedDomains` in U8's own PR: a cloud session in Auto mode may edit `.claude/settings.json` (`spikes.md` item 2). The scout and the verifier, which re-reads a cited page, may read only these hosts. A cloud session enforces no sandbox (`spikes.md` item 1), so there the limit rests on the worker instructions and the environment's network setting; the rehearsal checks the sandbox's limit on the primary (R-U8-1). |

### Hexagonal ports plan

- **Counts.**
  - 65 modules use the path constants, not 58, plus 92 test files that patch
    them.
  - 12 modules read `machine.json`, not 9.
  - There are no `sys.platform` skips: only typst, the HF model cache, and
    node.
  - PR 7 is bigger than planned. Each slice merges promptly, so the other
    lanes rebase onto it quickly.
- **Testing you won't do yourself moves to CI and the cloud.**
  - **Linux:** the cloud VM is Ubuntu 24.04, and a CI job installs `api-light`
    on a clean runner.
  - **WSL2:** documented in the README; an optional Windows CI job.
  - **macOS:** a `macos-latest` job on every PR, free on a public repo.
- **API adapters are built against the providers' documented APIs, with
  hand-built fixtures**, and the README and `doctor` mark them experimental.
  `calibrate` and `calibrate-ocr` ship without numbers. Recording live
  fixtures needs keys and is optional.
- **PR 8's "the two Macs" becomes "the primary."**
- **PR 22, the Python batch driver, is deferred.** It is the largest change,
  and it pays off only when a second agent host is actually wanted.

### Primary/secondary plan

- Its item 3 becomes "codify and fix the existing service": a `Scheduler` job,
  `caffeinate -i`, `KeepAlive`, the dispatcher repo as its working directory,
  and `same-dir` spawning.
  - The new jobs take labels of their own, so the old hand-written plists stay
    untouched and the rollback can reload them.
  - The job passes no `--name`, because the contract forbids naming a machine
    in the control plane.
  - The job's code is built in `research-assistant`, where the `Scheduler` port
    lives, even though the job serves the dispatcher. Moving the host ports
    into the core is a candidate for a later round.
- Item 4 (the iCloud placeholder check) is included, through `SyncedFolder`.
  No documented way to read the Optimize Mac Storage setting is known, so
  `doctor` infers it from placeholders in the library and the inbox.
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
   or `machine.json`. Only additive keys are allowed; for example, PR 12's
   `engine:` appears only on works a non-reference engine wrote.
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
| **W1 foundations** | a | **X1** fast post-edit hook (affected modules; full suite in CI and pre-push; §5 text) → **X2** contract: trailers, primary/secondary roles (M §1), "both machines" narrowed → **X3** the repo's own name: the 26 lines in 12 files that name `research-tools` now name `research-assistant` (the two plists outside git change at the switch) | research-assistant | W0 |
| | b | **P1** ports, `providers.py`, profiles → **P2** macOS CI job on every PR, `requires_platform` | research-assistant | W0 |
| | c | **A0** `agent-core` skeleton: layout, CI, `vendor` subtree into research-assistant, the symlink layout | agent-core + research-assistant | W0 spike |
| **W2** | a | **A1** `clean-code`/`clean-prose` split into the core's general text plus the research overlay `.claude/code-overlay.md` and `.claude/glossary.md` (diff check: no rule lost) → **U2** STE rules in the core's `clean-prose` | both | A0 |
| | b | **P5+M3** `Scheduler`/`SystemReadings`/`Notifier`; launchd adapter with `remove`; health on the ports; the Remote Control job (code only, installed at the switch) → **P6+M4** `Accelerator`, `Trash` (send2trash, lock regenerated), `SyncedFolder` with the placeholder halt | research-assistant | P1 |
| | c | **P3** search ports → **P4** API embedder and reranker | research-assistant | P1 |
| | d | **P9** transcriber and diarizer ports → **P10** hosted transcription | research-assistant | P1 |
| **W3** | a | **A2** audit engine to the core, as is; research checks in `audit/checks.py`; a thin `vault-audit` skill; hook, CI, tests, `extraction-fixer` repointed → **U1** bench → **U3** lint layer → **U4** units, closure, baseline v2 | both | A1, U2 |
| | b | **P7a–f** `Vault` object, one slice per skill group → **P7h** test vaults | research-assistant | W2-b,c,d merged |
| **W4** | a | **U5** audit workflow and workers → **U6** loop and fix (worktree) → **U7** Check 8 (plus stage timings in `ingest.py`) → **U8** Check 9, current practice | agent-core (+ research for timings) | U4 |
| | b | **P7g** shim deleted, plus the path-constant lint rule → **P11** `LayoutEngine` port → **P12** Marker API + `calibrate` → **P13** `LineRecognizer` + Tesseract + `calibrate-ocr` | research-assistant | P7f, U3 |
| | c | **G17** tiers → **G18** `HookIo` + git pre-commit (the X1 affected-module checks; the full suite runs pre-push and in CI) → **G19** worker specs + generator (the agent-host port at `lib/_ports/agent.py` and its adapters in `lib/_adapters/agent/`, in `agent-core`). Each repo commits the agent files the generator renders from its specs, and CI fails if they differ from a fresh render. A domain symlinks the core's rendered files, never its specs → **G20** research `domain.json` created with its `folders` and `policy`, the manifest reader, and one settings generator | agent-core + research-assistant | U3 |
| **W5** | a | **P14** requirement extras and locks (the in-repo setup script `bin/cloud-setup.sh` is updated in the same PR) → **P15** `bootstrap`/`doctor`, with primary checks (Remote Control job; no iCloud placeholders in the library or the inbox, which stands in for Optimize Mac Storage off). Where the host has no scheduler (a cloud VM or container without systemd `--user`), `bootstrap` skips the jobs and `doctor` reports them as `unavailable`, not `failing`. `bootstrap --no-jobs` skips them on purpose; the switch uses it → **P8**, **P16** contract and README per OS; a clean-runner Linux install job; optional WSL job. The end-to-end Linux check: in the cloud VM under `linux-local` (Marker on CPU, Ollama installed in the VM), a small fixture PDF goes from Stage 2 to Stage 6. Stages 0 and 1 need Zotero and stay untested off the Mac | research-assistant | W4-b |
| | b | **A5** domain template + `new-domain`, with the folder step (folders in `~/Documents`, access, optional Obsidian vault) → **A3** dispatcher: contract, registry, `route`, `delegate`, `compose`, `registry`; the core skills `approvals` and `dispatch` (plain names: vendored skills have no plugin namespace); research `domain.json` completed with `handles`, `entry_skills`, `exposure`, and `unattended` → **A4** `personal-assistant` made by `new-domain`, no skills and no folders yet | agent-core, assistant, personal-assistant | G20 |
| | c | **U2b** the > 40-word sentence cleanup → **G21** capability names in the prose (about 25 instruction files, in slices by skill); the capability names are core terms, defined in the core's `clean-prose`, not in a domain glossary | research-assistant | U3, G19 |
| **W6** | — | **P22** Python batch driver: **not in this round** unless you say so | — | — |
| **W7 hardening** | — | **X7.1** the upgraded audit in `all` mode with the fix loop, on every repo → **X7.2** a completeness critic: every acceptance row of the four plans has a CI test or a line in `rehearsal.md` → **X7.3** `cutover.py rehearse \| switch \| rollback` (read-only form first) and the switch runbook | all | W5 |
| **W8** | — | rehearsal and switch on the Mac, with you (§6) | — | W7 |

**Why this order:**

- **X1 goes first** because it makes every later edit cheap.
- **The contract trailers and roles go next**, because every later commit and
  item cites them.
- **The core split (A1) comes before the audit (A2, U*)**, because the audit
  parses the glossary and lives in the core.
- **The audit comes before the agent-host track (G*)**, because G17 extends
  the `xref` check that U3 writes.
- **The quiet ports (search, health, talks) come before the `Vault` refactor
  (P7)**, which touches 65 modules and would collide with them.
- **The extraction ports (P11–13) come after P7**: both touch
  `extract-corpus`.
- **The locks and `bootstrap` (P14–15) come after every port that adds a
  dependency.**
- **The dispatcher comes after the single settings generator (G20).**
- **The capability prose pass (G21) comes last**, because it rewrites the most
  instruction files, and every earlier item edits some of them.

## 4. Running it in the cloud

### W0: one setup sitting with you

| Step | What |
| --- | --- |
| X0.0 | **Seed `research-assistant`, private** (this local session, after your yes): copy `research-tools` `main` as one squashed snapshot into a new **private** GitHub repo, `research-assistant`. Add `upgrade/` (the unified plan as `PLAN.md` and the four source plans in `sources/`) and `bin/cloud-setup.sh`. The `research-tools` checkout is only read; it is never changed. Every later W0 step runs in a cloud session on this repo, because a cloud session can open only what is on GitHub. |
| X0.1 | **Pre-publish scan, then go public** (cloud, on the private `research-assistant`; only the snapshot is ever published, so the old history needs no scan): secrets (gitleaks over the snapshot); absolute personal paths; work titles and source text in `tests/fixtures/` (copyright); anything personal in the instruction text. Fix the findings in a PR. Then create `agent-core` and `assistant` as **public** repos and `personal-assistant` as **private**, and make `research-assistant` public. Install the Claude GitHub App on all four. Protect `main`: a PR and green CI required. Require approval before workflows run on PRs from forks. Every public repo gets a **publish-guard** CI job: gitleaks plus the audit's `works` check, so no PR can make a secret or a work's text public. |
| X0.2 | Cloud environment `research`, network Limited with the package-manager defaults, plus the hosts the spike's rerun lists: `download.pytorch.org`, `download-r2.pytorch.org`, `openaipublic.blob.core.windows.net`, `github.com`, `objects.githubusercontent.com`, `release-assets.githubusercontent.com`, `models.datalab.to`, and `astral.sh` only if the image lacks uv. The environment's setup script runs outside the repository and without network (`spikes.md` item 8), so it is an `echo`. The SessionStart hook in `.claude/settings.json` runs `bin/cloud-session-start.sh`, which runs `bin/cloud-setup.sh` until `~/.research-vault/cloud-setup.done` exists, so a PR changes the setup (P14 does) and nothing is updated by hand. `bin/cloud-setup.sh` mirrors CI: uv; `~/.research-vault/venv` built from `requirements.lock` with `UV_TORCH_BACKEND=cpu`; the empty-vault `machine.json` (the contract allows this in a test container); pandoc 3.12; node; tiktoken prefetched into `~/.research-vault/tiktoken`; the CI env vars. Its steps that need no PyPI run before the sync (PR #3), and it sends each `NO_PROXY` host the container cannot resolve through the gateway (PR #4). **Without a venv at that path, every hook exits 2 and blocks all Bash and Write. With a venv that holds no packages, Bash works, every Write is blocked, and every Edit reports a hook error.** Environment `core`: Python, uv, ruff, pyyaml, tiktoken. |
| X0.4 | Spike session (cloud, about an hour), results in `upgrade/spikes.md`: (1) hooks and suite run, and their timing; (2) whether Auto mode may edit `.claude/settings.json`; if not, settings changes ship as patches in `upgrade/settings-patches/` and you apply them at the switch; (3) whether symlinked skills, agents, and workflows load; (4) whether the Workflow tool runs, and its real concurrency on 4 vCPU; (5) push and PR creation; (6) `git subtree` round trip; (7) on the Mac, whether the sandbox's read-deny setting blocks reads of a folder, which the cross-domain read guard relies on; (8) whether the environment's setup script sees the cloned repo. **Done:** `spikes.md` holds the results, and this plan carries their consequences. |
| X0.5 | Complete `upgrade/` in `research-assistant` (cloud): `items/<id>.md`, `rehearsal.md`, and the item workflow `upgrade-item.js`, beside the plans X0.0 put there. `vault-audit` excludes `upgrade/`: its scope patterns name no path under it. `upgrade/` is deleted at the switch. |

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
  | Build | 1 implementer (worktree) | implements under the repo's `CLAUDE.md` on the branch `upgrade/<item>`: `clean-code`/`clean-prose`, a test that builds the defect class or pins the behaviour, the trailers |
  | Verify | 3 refuters, two at a time | lenses: **behaviour** (does `mac-local` change?), **contract** (`clean-prose`, special cases, cross-references, readers of every new field), **acceptance** (each row met in CI, or listed for the rehearsal) |
  | Fix | the implementer | a new agent per round, in a worktree on the same branch; fixes the confirmed findings and reruns the checks; at most two rounds, then the item goes to `needs-decision` |
  | Publish | 1 | pushes, opens the PR with the GitHub MCP tools (title by rule; body: acceptance table, rehearsal lines, open questions); a draft labelled `needs-decision` when anything is left for you |

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
- **Cloud sessions can't message back.** The conductor reads their results
  from GitHub: PRs, CI, and labels.

## 5. Merge gate in the new repos

The conductor merges a PR into a new repo's `main` when all of these hold:

- CI is green: the suite, ruff, the audit linter, and the repo's own jobs;
- the three refuters found nothing they could not refute, or the fix rounds
  cleared it;
- the PR merges without conflict onto the current `main`;
- no `needs-decision` label is open.

Anything else waits for you. A PR comment states the question, and the
conductor lists open decisions at each wave's end.

## 6. Rehearsal and switch (W8, on the Mac, with you)

1. **Pick a gap between backfill runs**, with no batch running. Clone the new
   repos into `~/Developer/` beside the old checkout.
2. **Rehearse in a staging home.** `cutover.py rehearse` sets `HOME` to
   `~/.staging-home`, so every `~` path is staged, and builds:
   - a venv from the new locks;
   - a staging vault: copies of a sample of reviewed works, their PDFs, and the
     bibliographies.

   Ollama and Zotero are shared read-only. No Stage 1 runs, so nothing touches
   Zotero.
3. **Run `rehearsal.md`, old against new.** It holds every Mac-only acceptance
   row the items collected, including:
   - the full suite on macOS;
   - `regress` records byte-identical (P11);
   - search answers identical on a fixed query set (P3);
   - generated `.claude/` files identical apart from ordering (G17–21);
   - a health sample;
   - `doctor` green;
   - an `ingest` dry run;
   - a Stage 2 → 6 backfill of three works in the staging vault;
   - one research question answered through the dispatcher, from a local
     session; Remote Control is checked after the switch, in step 4.7;
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
   4. Bootstrap for real, with `bootstrap --no-jobs`: the jobs wait for step 6.
   5. Run `claude remote-control` once by hand in `~/Developer/assistant`, to
      answer its enable and folder-trust prompts. A job can't answer them.
   6. Install the health and Remote Control jobs through `Scheduler`, under
      their new labels, with Remote Control working in
      `~/Developer/assistant`.
   7. **Check what the staging home can't rehearse:** from the laptop or the
      phone, open a session through Remote Control, ask one research question,
      and start a dry-run batch through the dispatcher. If any of these fails,
      roll back.
5. **Rollback** (`cutover.py rollback`): reload the old jobs, restore the old
   venv, and work from `~/Developer/research-tools`. Keep the rollback ready for
   two weeks, then archive `research-tools` on GitHub.
6. **Retire the laptop's install by hand**, following the README's "Retire a
   former full install."

## 7. Defaults I chose (say so before W0 if you disagree)

1. The dispatcher repo is named `assistant`.
2. `research-assistant`, `agent-core`, and `assistant` are public from W0,
   after the pre-publish scan; `personal-assistant` is private. The old
   `research-tools` stays private, and its CI keeps using your quota until the
   switch.
3. The conductor merges PRs in the new repos on the gate in §5, without asking
   for each one.
4. API adapters ship untested against live providers and marked
   experimental.
5. Ports PR 22 is not in this round.

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

- `CLAUDE.md`, `README.md`, `.claude/settings.json`, `lib/harness_hooks.py`
- `.github/workflows/ci.yml`, `.github/actions/empty-vault/action.yml`
- `lib/_vault/paths.py`, `lib/_vault/machine.py`, `lib/_health/{installer,launch_agent,hook}.py`
- `.claude/skills/{clean-code,clean-prose,vault-audit}/`
- `.claude/skills/ingest/scripts/_ingest/{preflight,checkout}.py`, `.claude/workflows/{ingest,resolve-tasks}.js`
- `.claude/agents/*.md`, `requirements.{txt,lock}`, `pyproject.toml`
