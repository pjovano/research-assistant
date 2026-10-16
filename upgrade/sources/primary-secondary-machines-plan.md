# Plan: one primary machine, and secondaries that reach it remotely

This plan is the detail reference for `unified-upgrade-plan.md`. That plan governs: where the two differ, it wins. Each section maps to one unified item:

| Section | Unified item | Wave |
| --- | --- | --- |
| §1 Contract | X2 | W1 |
| §2 README | P16, as the "Two machines: primary and secondaries" and "Retire a former full install" sections beside the per-OS "Install" sections | W5 |
| §3 Remote Control job | P5+M3 | W2 |
| §4 iCloud check | P6+M4 | W2 |
| §5 Retiring the laptop's install | the switch, step 6 | W8 |
| uninstall (§3, §5) | P5+M3, through `Scheduler.remove` | W2 |

## The model

- **Primary** (the always-on Mac): the only machine with the control plane. It has the repos (`~/Developer/assistant`, the dispatcher and front door; `~/Developer/research-assistant`, the research domain; `~/Developer/personal-assistant` and any later domain), the venv, the search stores, the models, Zotero, the health watcher, the extraction engine and the batches. The dispatcher's state lives on its own disk, in `~/.assistant/state/`. Every operation runs here.
- **Secondary** (the laptop, or any other machine): it holds the vault only through iCloud. You read and write notes in Obsidian, and drop PDFs into `~/Desktop/inbox/`, which syncs over. Sessions are started from the Claude app or claude.ai/code and run on the primary. It needs no repo, no Python, no Homebrew tools and no `machine.json`.

## How the secondary reaches the primary

Chosen: **Remote Control server mode**, `claude remote-control --spawn same-dir`, run in `~/Developer/assistant` on the primary.

- It starts sessions on demand, each in the dispatcher repo. The laptop needs nothing beyond a browser or the Claude app, and the docs confirm the session uses the primary's files, hooks, `.mcp.json` and project settings (https://code.claude.com/docs/en/remote-control).
- The dispatcher hands a batch to a background session in the research repo's main checkout (`delegate`, A3). A session spawned in a worktree can't run a batch: ingest preflight refuses a worktree (`.claude/skills/ingest/scripts/_ingest/checkout.py:56-59`).

Two alternatives come out worse:

- **The desktop app's SSH connection:** the docs don't confirm it loads the project's `.claude/settings.json` and `.mcp.json`, or how the sandbox behaves. A silent loss of the permission hooks is too risky.
- **Plain `ssh` + `tmux` + `claude`:** this works; document it as the fallback.

## Changes

### 1. Contract (`CLAUDE.md`), X2

- §2: replace "Two machines share the vault through iCloud and the control plane through git" with the primary/secondary roles above. Add NEVER run an operation, or clone the control plane, on a secondary.
- Narrow every "on each machine", "either machine" and "both machines" rule to the primary (plus CI and the cloud setup script where it applies):
  - the `vault_dir` rule in §1
  - the `~/.claude/settings.json` keys
  - pandoc and typst
  - the lock rule ("rebuild both environments")
  - the health watcher
- Keep "never name a machine, paths only under `~`". It keeps the vault portable, and a secondary can be promoted to primary later.
- Add one rule: on the primary, iCloud's **Optimize Mac Storage stays off**, so every library PDF is on disk when a stage reads it. A secondary may keep it on, which is part of what keeps it light.
- Add the folders model: `~/Documents` holds folders side by side (`library`, `research vault`, later others). Any of them can be an Obsidian vault. Each is assigned to the assistants that work on it. iCloud syncs all of them.

### 2. README, P16

The README has one "Install" section per OS, for anyone. Beside them, two sections from this plan:

- **Two machines: primary and secondaries.**
  - **The primary:** the macOS "Install" section, plus:
    - sign in to Claude Code with `/login`, with a claude.ai account; Remote Control doesn't accept an API key
    - run `claude remote-control` once by hand in `~/Developer/assistant`, to answer the "Enable Remote Control?" and folder-trust prompts
    - install the Remote Control job (§3)
    - keep the machine awake (Energy settings, set by hand)
    - turn Optimize Mac Storage off
  - **A secondary:** sign in to iCloud with Desktop & Documents on, open `~/Documents/research vault` in Obsidian, and use the Claude app or claude.ai/code to start sessions on the primary. Also list what *not* to install: the repos, Python and the venv, Homebrew tools, Ollama and the model caches, Zotero, `machine.json`.
  - **Why iCloud:** the contract, `domain.json`'s `folders`, and the sandbox paths the settings generator writes all name folders under `~/Documents`, which iCloud's Desktop & Documents syncs. A vault on Dropbox or similar would need all of them changed.
- **Retire a former full install:** the steps in §5.

### 3. Remote Control job on the primary, P5+M3

Codify and fix the existing service.

- **Today:** a hand-written `~/Library/LaunchAgents/local.claude-remote-control.plist` is loaded and runs under launchd, so `claude remote-control` runs without a TTY. It has `--spawn worktree`, `KeepAlive`, `RunAtLoad`, `ThrottleInterval` 30, `--no-create-session-in-dir`, a `PATH` that reaches `claude` and Homebrew, and a log under `~/Library/Logs/`. It has no `caffeinate`, and its working directory is the research repo. Its worktree mode is why remote sessions can't run a batch.
- **The port:** the job is a second job on the `Scheduler` port (P5), beside the health job. The launchd adapter takes a label and plist contents, which today are hard-coded (`lib/_health/installer.py:40`, `lib/_health/launch_agent.py:32-42`), and implements `remove`.
- **The job:**
  - runs `caffeinate -i claude remote-control --spawn same-dir`, with `KeepAlive`; the machine stays awake while the server runs
  - working directory `~/Developer/assistant`
  - keeps the hand-written plist's other keys and flags, and resolves `claude` at install time rather than naming its path
  - passes no `--name`: the hand-written plist names the machine, which the contract forbids in the control plane
  - uses a label other than `local.claude-remote-control`, so the hand-written plist stays untouched for rollback: the switch unloads it (step 4.1), and the rollback reloads it
  - has `install [--apply]` and `uninstall [--apply]`, read-only form first
  - its code is built in `research-assistant`, where the `Scheduler` port lives, though the job serves the dispatcher
- **Docs facts:**
  - The first run must be interactive: it asks "Enable Remote Control?" and for folder trust. Without a terminal the trust prompt exits with "Workspace not trusted".
  - It needs a claude.ai login, not an API key.
  - Server mode exits after about 10 minutes offline; `KeepAlive` restarts it.
- **When:** built in the cloud; installed at the switch (W8 step 4.6), after the first interactive run in `~/Developer/assistant` (step 4.5). `doctor` (P15) reports whether the job is installed and current.
- **Tests:** build the plist, and the install/stale/loaded states, the way the health installer's tests do; plus `remove`, for a loaded job and for an absent one.
- **Mac-only checks** (to `upgrade/rehearsal.md`; the staging home can't rehearse Remote Control, so they run after the switch, in step 4.7, and a failure rolls back): the job loads under launchd; a session started from the laptop or the phone opens in `~/Developer/assistant`; one research question is answered through it; a dry-run batch it hands off runs in the research repo's main checkout.

### 4. iCloud check in ingest preflight, P6+M4

- If a PDF in the library or the inbox is still a placeholder iCloud hasn't downloaded, the batch would fail midway. Preflight halts with a question instead, like the other machine checks.
- Defect class: "a synced file whose bytes are not on disk."
- Built on the `SyncedFolder` port: `not_downloaded(path)` for this check, beside `conflict_copies()` for the ports plan's conflict pattern. Preflight halts on either.
- `doctor` (P15) also reports placeholders. No documented way to read the Optimize Mac Storage setting is known, so on the primary `doctor` infers it from placeholders in the library and the inbox.
- Tests: a fake `SyncedFolder` that reports a placeholder, and one that reports a conflict copy; preflight halts on each.

### 5. Retiring the laptop's current install

Done by hand after the switch (W8 step 6), following the README's "Retire a former full install":

- unload the health watcher's launch agent with `launchctl bootout` and delete its plist; the laptop's old checkout predates `uninstall`, and a secondary gets no new checkout
- delete `~/.research-vault`
- delete the Ollama model and the HF/torch/datalab caches
- delete the repo clone
- optionally remove Zotero (the records live on the primary's Zotero)

`health.py` has no uninstall today, only `sample`, `report` and `install [--apply]`. P5 adds `uninstall [--apply]` through `Scheduler.remove`, for any install that runs the new code.

### 6. Leave as is

- The `vault-audit` concern about two machines editing the same note through iCloud at once still applies: the user editing in Obsidian on the laptop while the primary writes.
- The `conflict copy` term in `clean-prose` still applies too.

## Settled decisions

1. **How Remote Control starts sessions:** `same-dir`, in the dispatcher repo. Worktree mode blocks batches, because preflight refuses a worktree.
2. **The iCloud check (§4):** included.
3. **Other cloud services:** keep iCloud, and say why in the README (§2).
