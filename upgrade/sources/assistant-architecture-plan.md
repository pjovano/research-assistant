# Assistant architecture plan

**This plan is the detail reference for `unified-upgrade-plan.md`.** The
unified plan governs: it sets the items, the waves, the order, and the gates.
Where the two differ, the unified plan wins. This plan gives the cloud session
building each item the detail the unified plan leaves out.

| This plan | Unified item(s) | Wave |
| --- | --- | --- |
| §1 What we learned from similar systems | rationale for A0–A5 | — |
| §2 Target architecture | A0–A5 | W1–W5 |
| §3 The domain interface | A0, A1, A2, A5; G20 for `folders`, `policy`, the manifest reader, and the settings generator; A3 for the rest of the manifest | W1–W5 |
| §4 The dispatcher | A3 | W5-b, after A5 and G20 |
| §5 Security model | A3 (`registry`, `approvals`); G20 (the sensitive-folder read guard) | W4-c, W5-b |
| §6 W0 — Setup | X0.0–X0.5; the name inside the snapshot for X3 | W0; X3 in W1-a |
| §6 A0 — The core skeleton | A0 | W1-c |
| §6 A1 — The split | A1, then U2 | W2-a |
| §6 A2 — The audit engine moved to the core | A2, then U1, U3, U4 (W3-a) and U5–U8 (W4-a) | W3-a |
| §6 A5 — The template | A5 | W5-b, before A3 |
| §6 A3 — The dispatcher | A3 | W5-b, after A5 and G20 |
| §6 A4 — The personal skeleton | A4 | W5-b, after A3 |
| §7 Versioning and the machines | A0 | W1-c |
| §8 Decisions | settled | W0 |
| §9 Risks | — | — |
| §10 Later: building out the personal domain | outside this round | — |

Build one front door for every assistant: a **dispatcher** session you always
start in, which routes each request to a **domain** (research, personal, and
later accounting, legal, …) and runs it there under that domain's own contract,
sandbox, hooks, and tools. A shared **core** carries the rules every domain
obeys: `clean-code`, `clean-prose`, the control-plane audit, the approval
rules, and the security rules.

Goals, in order: (1) the running setup (`research-tools`, frozen during the
build, running only the backfill) is untouched until the switch, and the new
setup reads the same vault unchanged; (2) a new domain is added without
changing the dispatcher or the core; (3) no session ever holds private data,
untrusted content, and a way to send things out at once; (4) the dispatcher
stays thin: it routes, it does not hold domain data.

## 1. What we learned from similar systems

| Source | Finding | What it changes here |
| --- | --- | --- |
| [Claude Code agent view](https://code.claude.com/docs/en/agent-view) | background sessions (`claude --bg`), dispatch to a child repo with `@<repo>`, a supervisor that restarts crashed sessions and stops idle ones after ~1 h unless pinned; each session spends quota on its own; a research preview | the dispatcher builds no daemon: it is a contract, a registry, and skills over these primitives |
| [Cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging) | `ListAgents` / `SendMessage` between local sessions over a per-user socket; `notify_when_idle` sends one notice when a session finishes (12 h limit); an incoming message never approves anything, never changes configuration, and the receiver's permission prompts still apply; `crossSessionInbound` controls delivery | delegation and completion notices use this; a domain session treats the dispatcher's message as a request, never as your consent |
| [Plugins](https://code.claude.com/docs/en/plugins/components), [marketplaces](https://code.claude.com/docs/en/plugin-marketplaces) | a plugin carries skills, agents, hooks, MCP servers, output styles; **not** a `CLAUDE.md`, and of settings only `agent` and `subagentStatusLine`; skills are namespaced `/<plugin>:<skill>`; a local-directory marketplace reads the files from the checkout; cloud sessions do not install plugins from `enabledPlugins`, and a local-directory marketplace path exists neither in the cloud nor in CI | the core is vendored as a git subtree, not installed as a plugin (§3, §7); the shared contract text ships as a skill each domain contract invokes; sandbox and permissions stay in each domain's own `settings.json` |
| [15 repos with Claude Code](https://dev.to/neil_agentic/how-i-manage-15-repos-with-claude-code-without-losing-my-mind-2ood) | persistent managers that never touch code, short-lived workers per repo; a TOML registry generates each repo's sandbox; failures: monorepo, submodules, one session orchestrating across repos; rule: read broadly, write to one repo at a time | each domain's `domain.json` feeds the one settings generator (G20); read-only questions go to a cheap model |
| [Anthropic, multi-agent research](https://www.anthropic.com/engineering/multi-agent-research-system) | a delegated task needs objective, output format, tools, and a boundary; explicit effort-scaling rules, or the lead over-spawns; save the plan externally; ~15× the tokens of chat | a delegation template; the dispatcher answers simple requests itself; a ledger file |
| [Lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) | private data + untrusted content + external communication in one agent makes prompt injection a data leak; no model-level fix | a core rule and a per-skill exposure table (§5) |
| OpenClaw ([malicious skills](https://thehackernews.com/2026/02/researchers-find-341-malicious-clawhub.html), [architecture](https://medium.com/@nimritakoul01/openclaw-architecture-simply-explained-fca2e9f15f27)) | same shape as this plan (gateway, channels, `SKILL.md`, file memory, heartbeat); ~12% of audited registry skills malicious; injections stored in memory and assembled later; gateway exposed by default | skills only from your own repos; state files written only from your words |
| [Meta Muse](https://abcnews.com/Technology/wireStory/meta-launches-personal-ai-agent-muse-emphasizes-safety-136284133), [OpenAI dots](https://techcrunch.com/2026/09/29/openai-launches-dots-its-bubbly-agentic-avatar/), [Zapier review](https://zapier.com/blog/chatgpt-dots/) | a dedicated VM per user; dots' read-only mode while the user is away; dots missed urgent, high-judgment items and surfaced routine ones | unattended runs are read-only by default; a later brief leads with what needs you (§10) |

The OpenClaw and community figures come from secondary write-ups: patterns, not
exact numbers.

## 2. Target architecture

Every path below is on the primary: only the primary has the control plane. A
secondary reaches the dispatcher through Remote Control.

```
                         you (any machine, through Remote Control)
                                               │
   ~/Developer/assistant ───────────── dispatcher session ──────── ~/.assistant/state/ (ledger, preferences)
     registry ← domain.json of each domain     │  routes · delegates · composes
                                               │  ListAgents / SendMessage / claude --bg
             ┌─────────────────────────────────┼──────────────────────────────┐
   ~/Developer/research-assistant   ~/Developer/personal-assistant   ~/Developer/accounting   …
     contract, sandbox, hooks       contract, sandbox                (later, from the template)
     vault-rag, ingest, …           skeleton: no skills, no folders
     folders: library, research vault
             └─────────────────────────────────┼──────────────────────────────┘
                                               │ vendored: git subtree at vendor/agent-core/,
                                               │ skills, agents, and workflows symlinked into .claude/
   agent-core (GitHub)
     skills: clean-code · clean-prose · control-plane-audit · dispatch · approvals · new-domain
     audit engine · domain.py · templates/domain/
```

| Layer | Repo | Visibility | Holds | Never holds |
| --- | --- | --- | --- | --- |
| Core | `agent-core` | public | the general standards, the audit engine, the approval and security rules, `domain.py`, the domain template | any domain's terms, data, or paths |
| Dispatcher | `assistant` | public | its contract, the registry, the routing and composing skills | any domain's data; it reads what a domain returns, never its files; it lists no folders; its ledger and preferences live outside git, in `~/.assistant/state/` |
| Domain | `research-assistant` (public), `personal-assistant` (private), one repo each later | per domain | its contract, skills, workers, scripts, sandbox, hooks, MCP servers, its overlays on the core, the vendored core | another domain's data; a direct call to another domain |

Every flow between domains passes through the dispatcher, so one place sees and
records it.

## 3. The domain interface

Every domain fills the same slots. The core's skills and the dispatcher read
only these.

| Slot | Path in the domain repo | Is | Read by |
| --- | --- | --- | --- |
| Contract | `CLAUDE.md` | §1 Mandate, §2 Architecture, §3 Conventions, §4 Operation, §5 Standards; §5 invokes `clean-code`, `clean-prose`, `approvals` | the domain's sessions |
| Manifest | `domain.json` | the fields in the table below | `domain.py manifests`, which `domain.py settings` and the dispatcher's `registry` build on |
| Core | `vendor/agent-core/` (git subtree); `.claude/skills/<skill>`, `.claude/agents/<worker>`, and `.claude/workflows/<workflow>` symlinks into it | the core's skills, workers, and workflows, at the version this domain pulled | Claude Code; workers, by the `.claude/` path |
| Glossary | `.claude/glossary.md` | the domain's terms, in the Vocabulary-table shape `clean-prose` uses today | `clean-prose`; the audit lint |
| Code overlay | `.claude/code-overlay.md` | stricter code rules, overriding the general ones | `clean-code` |
| Audit checks | `audit/checks.py` | domain checks registered with the core audit engine | `control-plane-audit` |
| Audit baseline | `audit/baseline.json` | the domain's own audit baseline | `control-plane-audit` |
| Settings | `.claude/settings.json` | sandbox, permissions, hooks; its `permissions` and `sandbox` blocks generated by `domain.py settings` from `domain.json` | Claude Code |

### The manifest, `domain.json`

| Field | Is |
| --- | --- |
| `name` | the domain's name, the repo's name |
| `summary` | one sentence on what the domain does |
| `handles` | the request kinds the domain owns, each with examples |
| `entry_skills` | the skills the dispatcher may name in a delegation |
| `exposure` | per skill, which of the three risks it carries: `private_data`, `untrusted_content`, `sends_outward` (§5) |
| `folders` | the folders under `~/Documents` the domain works on, each with `read` or `write` access, and optionally `sensitive: true` |
| `policy` | the network hosts, the allowed commands, the commands excluded from the sandbox, the prompt-on patterns |
| `unattended` | what a scheduled or background run may do: `read-only` by default, `none` for a sensitive domain; an entry skill MAY carry its own value |

G20 creates the research `domain.json` with its `folders` and `policy`. A3
completes it with `handles`, `entry_skills`, `exposure`, and `unattended`.

"Capabilities" names the tool classes of the ports plan (G19), never these
three risks.

### Folders in `~/Documents`

`~/Documents` holds your folders side by side: `library`, `research vault`,
later perhaps `taxes` or `medical`. Two choices are independent:

- a folder is an Obsidian vault or not, whichever assistant uses it;
- an assistant works on several folders, and two assistants MAY share one.

| Domain | `folders` |
| --- | --- |
| research | `library` (write), `research vault` (write); nothing moves, and the contract's `vault_dir` rule is unchanged |
| dispatcher | none |
| personal (A4) | none yet; added with `new-domain`'s folder step at the build-out |

A CI check in `research-assistant` confirms that `domain.json`, the research
`Locations` defaults (P7), and the generated sandbox name the same folders.

### The settings block

One generator, in the core: `domain.py settings` (G20). It reads
`domain.json`'s `folders` and `policy` and prints the `permissions` and
`sandbox` blocks of `.claude/settings.json`:

- write access to exactly the folders the domain lists as `write`;
- a read-deny on every `sensitive` folder another domain lists and this one
  does not, taken from the manifests `domain.py manifests` reads;
- the network hosts, the allowed and excluded commands, and the prompt-on
  patterns of `policy`.

G20 ships the manifest reader, `domain.py manifests`, beside the generator. It
reads every `~/Developer/*/domain.json` on the primary, or the manifests named
on the command line. A3's `registry` builds on the same reader. `~/Developer`
exists only on the primary, so the tests of the reader, the generator, and
`registry` use fixture manifests.

Each domain keeps its sandbox and permissions in its own `settings.json`. The
sandbox denies Bash every write to it. Whether Auto
mode MAY edit it in the cloud is the W0 spike's question (2): if it may, a
settings change ships in its PR; if not, it ships as a patch in
`upgrade/settings-patches/`, which you apply at the switch.

## 4. The dispatcher

This round builds `route`, `delegate`, `compose`, and `registry`. The `inbox`
and `schedule` skills wait for the personal domain (§10).

### Contract outline (`assistant/CLAUDE.md`)

1. **Mandate.** Route every request to the domain that owns it; answer simple
   requests yourself; compose requests that span domains; never hold domain
   data.
2. **Routing.** Read the registry. One domain matches → delegate. Several or
   none → ask. A request inside a domain's `handles` that needs long
   back-and-forth (taking notes, editing a draft, changing a domain's code) →
   open that domain session for you in split view and step out.
3. **Effort rules.** A request the registry or the ledger answers (which domain
   handles X, what is running) → answer it, no delegation. One domain, one
   result → one delegated session. Several domains → one per domain, in
   parallel, then compose. NEVER delegate to more domains than the request
   names.
4. **Delegation template.** Each message to a domain carries: your request word
   for word; the dispatcher's reading of it, marked as such; the output wanted
   (form, length); done when; what not to do. The domain's contract governs;
   the template never overrides it.
5. **Long jobs.** Start in the background (`claude --bg` in the domain's
   directory), record in the ledger, subscribe with `notify_when_idle`,
   report once at completion. A research batch keeps its own rules (runs
   unattended, reports once) and starts in the research repo's main checkout,
   `~/Developer/research-assistant`, never in a worktree: ingest preflight
   refuses a worktree (`_ingest/checkout.py:56-59`).
6. **State.** `~/.assistant/state/ledger.md` (open delegations and their
   results), `~/.assistant/state/preferences.md` (your standing preferences),
   on the primary's own disk, neither in iCloud nor in git. Written only from
   your own words or a domain's returned result, never from mail, web, or file
   content. Session transcripts expire after 7 days; nothing durable lives in
   them.
7. **Approvals and security.** Invoke `approvals`. The dispatcher sends
   nothing outward itself; it presents a domain's draft and waits for your yes.

### Skills

| Skill | Does |
| --- | --- |
| `route` | read the registry, pick the domain, or ask |
| `delegate` | start or resume the domain session, send the templated message, record it in the ledger |
| `compose` | combine results from several domains into one answer |
| `registry` | rebuild the registry from the manifests `domain.py manifests` reads; validate each manifest; check each skill's exposure (§5) |

### The front door

Remote Control already runs on the primary: a hand-written
`local.claude-remote-control.plist` with `--spawn worktree` and no
`caffeinate`. In worktree mode no remote session can run a batch, because
preflight refuses a worktree.

| Piece | Content |
| --- | --- |
| The job | `claude remote-control` under `caffeinate -i`, `KeepAlive`, in `~/Developer/assistant`, `same-dir` spawning; no `--name`, because the contract forbids naming a machine; a label of its own, so the old plist stays untouched for rollback; a `Scheduler` job (P5+M3), code only in the build, built in `research-assistant`, where `Scheduler` lives |
| Batches | the dispatcher hands each batch to a background session in the research repo's main checkout |
| Install | at the switch (W8): step 4.1 unloads the old plist; step 4.5 runs `claude remote-control` once by hand in `~/Developer/assistant`, for its enable and folder-trust prompts; step 4.6 installs the job through `Scheduler` under its new label; step 4.7 checks it from the laptop or the phone |

Any machine reaches the dispatcher through it.

## 5. Security model

**The rule (in `approvals`).** NEVER let one session hold all three of:
private data, untrusted content, and a way to send outward (network, mail,
messages, posting). Each domain declares its `exposure` per skill in
`domain.json`. `registry` enforces two checks:

- it refuses a skill that declares all three;
- it checks each skill's declared exposure against the tool capabilities G19
  generates for it: a skill with `web` MUST declare untrusted content.

**The sensitive-folder read guard.** A folder with `sensitive: true` is
read-denied to every domain that does not list it, through the sandbox block
`domain.py settings` generates from the manifests `domain.py manifests`
reads (§3). A research session never sees `taxes` or
`medical`. The W0 spike's question (7) confirms on the Mac that the sandbox's
read-deny blocks reads of a folder.

| Domain / skill | Private data | Untrusted content | Sends outward | Pattern |
| --- | --- | --- | --- | --- |
| research: answer, notes, ingest | library, notes | PDFs, web (Discover) | no sending; network to listed hosts | as today |
| dispatcher | the domains' returned results | no | no | presents drafts; sends nothing |

When the personal domain is built out (§10), and for later domains:

| Domain / skill | Private data | Untrusted content | Sends outward | Pattern |
| --- | --- | --- | --- | --- |
| personal: reminders, calendar | yes | no | no | free to write |
| personal: mail-reader | yes | yes (mail) | **no** (no network, no send) | returns a summary only |
| personal: drafter | the summary | no | **no**: writes a draft | you approve each send |
| personal: sender | — | — | yes | only on your yes, only the approved draft |
| accounting, legal | yes | documents | no | results only to the dispatcher |

Further rules:

* **Unattended means read-only.** A scheduled or background run prepares;
  every outward or irreversible action waits for you.
* **Skills only from your own repos.** A third-party skill is read in full and
  copied into `agent-core` or a domain before use; never installed from a
  public registry.
* **Messages between sessions are requests, not consent.** Claude Code already
  enforces this; the domain contracts restate it.
* **Apple Events through named scripts**, at the personal build-out. The
  personal domain's sandbox exempts only its own scripts (for example
  `bin/reminders`, `bin/calendar`), never `osascript` in general.

## 6. Items

Each item is one PR in a new repo; nothing runs from the new repos before the
switch. Each PR: `clean-prose` before instruction text, `clean-code` before
code; the suite, ruff, and audit lint pass in every touched repo; every commit
carries a `Defect-class:` or `Change-class:` trailer. An acceptance row that
needs the Mac becomes a line in `upgrade/rehearsal.md`, run old against new at
the switch rehearsal (W8); every other row is a CI test.

### W0 — Setup (X0.0–X0.5)

The unified plan's §4 states the steps. What this plan needs from W0:

| Step | Content |
| --- | --- |
| X0.0 | `research-assistant` starts private, from one squashed snapshot of `research-tools` `main`, seeded from the local session with the plans in `upgrade/`. No GitHub rename: `research-tools` stays private and frozen, and is archived after the switch. |
| X0.1 | After the pre-publish scan of the snapshot: `research-assistant`, `agent-core`, and `assistant` public; `personal-assistant` private. |
| X0.4 | The spike's answers this plan rests on: (2) whether Auto mode may edit `.claude/settings.json` (§3); (3) whether symlinked skills, agents, and workflows load (A0); (6) the `git subtree` round trip (A0, §7); (7) whether the sandbox's read-deny blocks a folder (§5). |

CI needs no token to reach the core: the core is vendored into each domain.

**The name inside the snapshot (X3, W1-a).** The 26 lines in 12 files that
name `research-tools` name `research-assistant`:

| File | Lines | What changes |
| --- | --- | --- |
| `.claude/settings.json` | 10 | the allow and prompt rules naming `~/Developer/research-tools/…` (a settings patch if the spike says so) |
| `.claude/skills/ingest/SKILL.md` | 3 | `allowed-tools` and two command lines |
| `README.md` | 3 | title and setup steps |
| `tests/test_ingest_preflight_checking_the_machine_state.py` | 2 | the path |
| `tests/test_ingest_workflow_settling_relay_replies.py` | 1 | the path |
| `CLAUDE.md` | 1 | §2's control-plane path |
| `.claude/skills/clean-prose/SKILL.md` | 1 | the Vocabulary row for the control plane |
| `.claude/skills/gloss-bibliographies/SKILL.md` | 1 | line 4 |
| `.claude/skills/machine-health/SKILL.md` | 1 | the launch agent's path |
| `.claude/workflows/ingest.js`, `resolve-tasks.js` | 1 each | the `REPOSITORY` and `NOTES` constants |
| `lib/_health/launch_agent.py` | 1 | `CONTROL_PLANE` |

The two plists outside git, the health watcher's and
`local.claude-remote-control.plist`, are replaced at the switch: step 4.1
unloads them, step 4.6 installs the new health and Remote Control jobs under
labels of their own, and the old plists stay on disk for the rollback. Claude
Code keys session history by directory, so sessions from before the switch
stay under the old key and expire within 7 days.

**Accepted when:** `git grep research-tools` finds nothing outside `upgrade/`
(CI). On the Mac
(rehearsal): an `ingest` dry run resolves every script path; the health
watcher samples from the new path.

### A0 — The core skeleton (W1-c)

| Step | Content |
| --- | --- |
| A0.1 | `agent-core`'s layout: `skills/`, `agents/`, `workflows/`, `audit/`, `templates/domain/`, `domain.py`, its CI (suite, ruff, audit lint) |
| A0.2 | `vendor/agent-core/` in `research-assistant`, added with `git subtree add` |
| A0.3 | The symlink layout: each core skill at `.claude/skills/<skill>`, each core worker at `.claude/agents/<worker>.md` (after G19, the core's rendered agent file, never its spec), and each core workflow at `.claude/workflows/<workflow>.js`, a relative symlink into `vendor/agent-core/` |
| A0.4 | The fallback, if the W0 spike finds symlinks do not load: a generated copy in place of each symlink, and a CI check that fails when a copy differs from `vendor/agent-core/` |

**Accepted when:** a cloud session in `research-assistant` lists a core skill
through the symlink; `git subtree pull` brings a core change in as one PR
(CI).

### A1 — Split `clean-code` and `clean-prose` into the core (W2-a)

Low risk: two Markdown skills, no code. U2 then adds the STE rules to the
core's `clean-prose`.

| Step | Content |
| --- | --- |
| A1.1 | `agent-core/skills/clean-code/` and `agent-core/skills/clean-prose/`: the general text only |
| A1.2 | The general skills load the domain's overlay when present: `clean-code` reads `.claude/code-overlay.md`, `clean-prose` reads `.claude/glossary.md`; an overlay rule overrides the general one |
| A1.3 | In `research-assistant`: move `clean-code`'s `## Research Vault` section (lines 190–212, ~3.3 KB of 17.4 KB) to `.claude/code-overlay.md`; move `clean-prose`'s §5 Vocabulary (lines 82–364, ~48.5 KB, ~260 rows) and the about six vault mentions elsewhere in it to `.claude/glossary.md`; replace the two skill directories with the symlinks of A0 |
| A1.4 | The skill names stay `clean-code` and `clean-prose`: `CLAUDE.md` §5 and `settings.json` do not change |
| A1.5 | The six workers that read `clean-code` keep reading `.claude/skills/clean-code/SKILL.md`, then read `.claude/code-overlay.md`: `extraction-fixer`, `page-reader`, `pdf-bookmarker`, `pdf-cleaner`, `pdf-filer` (it names the directory, at `:351`), `work-classifier`. `extraction-fixer` alone also reads `clean-prose`; it then reads `.claude/glossary.md`. `README.md` names the overlays |
| A1.6 | `audit.py lint`'s pointer check follows the symlinks, so a path through `.claude/skills/` into `vendor/agent-core/` resolves |

**Accepted when:** the suite, ruff, and audit lint pass; a session in
`research-assistant` lists `clean-code` and `clean-prose`; a worker dispatched
in a test reads both the general text and the overlay; the overlays and the
general text together hold every rule the old skills held (a diff check: no
rule lost). All in CI.

### A2 — The audit engine moved to the core (W3-a)

`vault-audit` is the hard one: its scripts import `lib/vault.py`, and its path
is named in 11 places. A2 moves the engine as is; U1 and U3–U8 then build the
audit upgrade in the core (`audit-upgrade-plan.md`): U1 bench → U3 lint layer
→ U4 units, closure, baseline v2 in W3-a, and U5–U8 in W4-a. U2 precedes A2
in W2-a, and U2b follows in W5-c. The bench's synthetic
control plane is domain-free, so it becomes the core's own test plane.

| Step | Content |
| --- | --- |
| A2.1 | The engine moves to `agent-core` as the `control-plane-audit` skill, unchanged in behaviour |
| A2.2 | `research-assistant/audit/checks.py` holds the research checks: `works` (works named in the control plane) and `special` (the signs keyed to PDFs: page, font-name literals) run anywhere; `residue` (inbox, corpus files with no PDF, conflict copies) and the count-against-disk `staleness` need the real vault and run only on the primary |
| A2.3 | The audit lint parses the domain's `.claude/glossary.md`, which A1 made |
| A2.4 | `vault-audit` stays as a thin skill that invokes the core audit with the research checks, so `CLAUDE.md` and your habits keep one name |
| A2.5 | Re-point the 11 places that name the audit path (table below) |
| A2.6 | Baseline per domain: each domain keeps its own baseline at `audit/baseline.json` in its repo, so the tools still write one control-plane file per domain |

| Place | What names the path |
| --- | --- |
| `.claude/settings.json:25` | the allow rule |
| `.claude/settings.json:165` | the prompt rule on `accept` |
| `lib/harness_hooks.py:18-19` | `AUDIT_SCRIPT` |
| `.github/workflows/ci.yml:45` | the CI audit lint step |
| `tests/test_imports.py:36` | the import list |
| `tests/test_harness_hooks_checks_after_edit.py:77` | the test that the script exists at `AUDIT_SCRIPT` |
| `tests/test_vault_audit.py:344` | the usage line |
| `CLAUDE.md:450` | §5's audit linter command |
| `.claude/agents/extraction-fixer.md:50` | the only worker naming the script |
| `.claude/skills/vault-audit/SKILL.md:4,41` | `allowed-tools` and the command line |
| `.claude/skills/clean-prose/SKILL.md:244` | the Vocabulary row for the audit baseline's path; after A1 it sits in `.claude/glossary.md` |

**Accepted when:** the post-edit hook and CI give the same verdicts as before
on an unchanged tree (CI); after U4, the audit upgrade plan's acceptance table
holds, run from the core against `research-assistant` (CI). On the Mac
(rehearsal): `residue` and the count-against-disk `staleness` run on the real
vault.

### A5 — The template and `new-domain` (W5-b, before A3)

| Step | Content |
| --- | --- |
| A5.1 | `templates/domain/` carries an empty contract in the five-section shape, a glossary, an `audit/checks.py` stub, a test runner, CI calling the core audit, the `vendor/agent-core/` subtree and its symlinks, and a default `.obsidian/` config (today's `obsidian/graph.json` pattern, made general) |
| A5.2 | `new-domain`: copies the template, asks the domain's mandate, `handles`, `exposure`, `policy`, and `unattended`, writes `domain.json`, prints the settings block from `domain.py settings` |
| A5.3 | The folder step: which folders in `~/Documents` the domain works on, existing or new, and with what access; for a new folder, it offers to make it an Obsidian vault by copying the default `.obsidian/` config. Folders are created on the Mac at the switch, never in the cloud |
| A5.4 | A domain with sensitive data (accounting, legal) runs with `unattended: none`, no network hosts in `policy`, and its folders `sensitive: true` by default |

**Accepted when:** a domain made from the template in CI passes the core audit
and its own CI. On the Mac (rehearsal): `new-domain`'s folder step creates a
folder under `~/Documents` and, when asked, makes it an Obsidian vault.

### A3 — The dispatcher (W5-b, after A5 and G20)

| Step | Content |
| --- | --- |
| A3.1 | `research-assistant/domain.json`, which G20 created with `folders` and `policy`, completed with: `handles` research questions, discover, notes, drafts, projects, ingest; `entry_skills`; `exposure` per entry skill; `unattended: read-only` except `ingest` |
| A3.2 | `assistant/CLAUDE.md` per §4; the skills `route`, `delegate`, `compose`, `registry` |
| A3.3 | The core skills `approvals` (the rules of §5) and `dispatch` (the delegation template, shared so domains can read what they will receive); plain names, because vendored skills have no plugin namespace |
| A3.4 | `domain.py` in the core: `manifests` and `settings` (from G20), `validate` (a manifest against the schema), `registry` (builds the registry on `manifests` and runs §5's two checks) |
| A3.5 | The state directory `~/.assistant/state/`, with the ledger and the preferences file, made on the primary on first use |
| A3.6 | The front door of §4: the dispatcher's side of the Remote Control job and the hand-off of batches to the research main checkout |

**Accepted when** (CI): `registry` validates the research manifest; it refuses
a fixture manifest whose skill declares all three exposures, and one whose
skill has `web` and does not declare untrusted content. On the Mac (rehearsal):
from `assistant`, "what does my library say about X?" runs in a
`research-assistant` session and returns the verified answer; "start a batch"
starts it in the background in the research main checkout, and the dispatcher
reports once at the end; a request matching no domain is asked about, not
guessed.

### A4 — The personal skeleton (W5-b, after A3)

| Step | Content |
| --- | --- |
| A4.1 | `personal-assistant`, private, made by `new-domain` from the template: contract, `domain.json`, glossary, the vendored core |
| A4.2 | No skills and no folders: `entry_skills` and `folders` empty |

**Accepted when** (CI): the repo passes the core audit and its own CI;
`registry` lists it with no entry skills, without a change to `assistant` or
`agent-core`, so the dispatcher routes nothing to it.

## 7. Versioning and the machines

* Every repo syncs through git. Only the primary has checkouts, under
  `~/Developer/`; a secondary reaches them through Remote Control.
* Each domain carries the core as a git subtree at `vendor/agent-core/`. A
  domain moves to a newer core on purpose, with `git subtree pull` in a PR to
  that domain; a domain that stays on an older core simply does not pull.
* Workers read the core by its `.claude/` path, which stays the same across
  core versions.
* Core changes reach `main` through a pull request, on the same rule as
  `research-assistant` §5, and run the core's test plane. A domain's subtree
  pull runs that domain's CI and audit before merge.
* A core change that alters a rule a domain overlay overrides is reported by
  the core audit as an overlay conflict.
* A plugin packaging of the core MAY be added later, for other people.

## 8. Decisions

All settled.

| # | Decision | Resolution |
| --- | --- | --- |
| 1 | Dispatcher repo name | `assistant` |
| 2 | Core distribution | a vendored git subtree at `vendor/agent-core/`, skills, agents, and workflows symlinked into `.claude/`; a domain upgrades with `git subtree pull`. Cloud sessions do not install plugins, and a local-directory marketplace path exists neither in the cloud nor in CI |
| 3 | Audit sequencing | A2 moves the engine to the core as is; U1 and U3–U8 then build the upgrade in the core |
| 4 | Dispatcher state location | the primary's own disk, `~/.assistant/state/`; neither iCloud nor git |
| 5 | Which machine runs the dispatcher | the primary, which alone has the control plane |
| 6 | Mail source | deferred to the personal build-out (§10) |

The repos: `agent-core`, `assistant`, and `research-assistant` are public;
`personal-assistant` is private. `research-assistant` is a new repo made from
a squashed snapshot of `research-tools`.

## 9. Risks

| Risk | Guard |
| --- | --- |
| The switch leaves a stale path (a launch agent, a plist, a settings rule) | the switch rehearsal (W8): every `rehearsal.md` line passes old against new in a staging home, including an `ingest` dry run and a health sample, before the switch; `cutover.py rollback` stays ready for two weeks |
| A1 loses a vault rule in the split | the diff check in A1's acceptance; the audit's `xref` |
| Workers or CI cannot find the core | the core is vendored: workers read `.claude/skills/…`, and CI checks out one repo; A1's test dispatches a worker |
| The architecture and audit plans collide over `vault-audit` | one sequence: A2 moves it as is, then U1 and U3–U8 build it in the core, with the bench as the shared gate |
| The dispatcher becomes a second, bloated contract | its mandate is routing; domain rules stay in domains; Check 8 of the audit measures its always-loaded tokens |
| Prompt injection through mail or web | §5's exposure split, enforced by `registry`; unattended read-only; state written only from your words |
| One domain reads another's sensitive folder | the sensitive-folder read guard (§5), confirmed by the W0 spike |
| Cost: every delegation is a session | effort rules; simple requests answered in place; cheap model for read-only questions |
| Agent view and messaging are previews and change | the dispatcher's `delegate` skill is the one place that calls them |

## 10. Later: building out the personal domain

Outside this round. A4 leaves `personal-assistant` a skeleton; this section is
the reference for building it out. The dispatcher's `inbox` and `schedule`
skills come with it.

| Step | Content |
| --- | --- |
| L.1 | Folders: `new-domain`'s folder step, for any folder the personal skills work on |
| L.2 | `reminders` and `calendar` skills over two named scripts (EventKit or AppleScript), exempted from the sandbox by exact command pattern; a one-time macOS permission grant on the primary |
| L.3 | `brief`: today's events, due reminders, open tasks from the research notes (through the dispatcher), new works placed; leads with "needs you"; weekday mornings as a scheduled task |
| L.4 | The Reminders inbox: a "Claude" list; a scheduled sweep turns each item into a request to the dispatcher and writes the result into the reminder's notes |
| L.5 | Mail, last: `mail-reader` read-only, no network, summary only; `drafter` writes drafts; `sender` only on your yes (§5) |

| Dispatcher skill | Does |
| --- | --- |
| `inbox` | read the "Claude" Reminders list (through the personal domain), turn each item into a request |
| `schedule` | the scheduled runs: morning brief, inbox sweep, weekly checks |

Only the primary runs the schedules and the inbox sweep, so no two machines
sweep one inbox. The mail source is open: Apple Mail through a script, or a
mail MCP server; the default is Apple Mail, read-only.

**Accepted when:** a reminder added from the phone comes back answered; the
brief arrives on schedule, read-only; the registry refuses a mail skill that
declares sending and reading together.
