# Rehearsal: the Mac-only checks, run old against new

This file holds every acceptance check that needs the primary Mac. §6 of
`PLAN.md` runs it in W8. The switch happens only when every line passes.

## How to run it

| Rule | Content |
| --- | --- |
| Where | the primary, in a gap between backfill runs, with no batch running |
| Staging home | `cutover.py rehearse` sets `HOME` to `~/.staging-home`; every `~` path is staged; Ollama and Zotero are shared read-only; no Stage 1 runs |
| Old against new | where a line has an "Old" column entry, run the same check with the frozen `research-tools` setup and with the new setup, and compare |
| Phase | **S**: in the staging home, before the switch (§6 step 3). **W**: after the switch, from the laptop or the phone (§6 step 4.7); a failure rolls back. **R**: at the laptop's retirement (§6 step 6) |
| Result | the rehearsal fills the Result column: `pass`, or `fail` with what was seen |

## How an item adds to it

| Rule | Content |
| --- | --- |
| Own section | an item's PR edits only the section headed by its own ID; sections stay in `PLAN.md` §3's order |
| Line IDs | `R-<item>-<n>`, numbered from 1 within the section; a removed line keeps its number retired |
| Columns | every line states the check, the command or action, what passes, and its phase |
| No duplicate | a check another line already covers is named in the item file, never repeated here |

## Lines every item shares

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-all-1 | S | The full suite on macOS | `~/.research-vault/venv/bin/python -m unittest discover -s tests` in `~/Developer/research-assistant` | every test passes or skips for a named absent tool | |
| R-all-2 | S | ruff and the audit linter on macOS | `~/.research-vault/venv/bin/ruff check .`; `… audit.py lint` (the core's path after A2) | no finding; `works` 0 | |

## W1

### X1

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-X1-1 | S | A desktop session's `.py` edit runs the affected test modules | edit one `lib/` module in a session in the staging checkout; read the hook's report | only the importing test modules run; the hook time is recorded | |
| R-X1-2 | S | The pre-push hook runs the full suite | `git push --dry-run` from the staging checkout with `core.hooksPath` set | the full suite, ruff, and the audit linter run before the push | |

### X2

No Mac-only check.

### X3

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-X3-1 | S | An `ingest` dry run resolves every script path | the `ingest` skill's dry run from `~/Developer/research-assistant` | every script path resolves under the new checkout; no path names `research-tools` | |
| R-X3-2 | S | The health watcher samples from the new path | `health.py sample` from the new checkout | a journal line is written; its command names the new checkout | |

### P1

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-P1-1 | S | The primary's real `machine.json` resolves to today's classes | `~/.research-vault/venv/bin/python lib/providers.py --machine <copy of the primary's machine.json>` in the staging checkout | every port but `sync` and `locations` names the class the old setup constructs; `sync` and `locations` read `unconfigured`, naming `icloud` and `macos` | |
| R-P1-2 | S | The old setup still reads a `machine.json` carrying `profile` and `providers` | run the frozen setup's `health.py report` with the two keys added to the staged `machine.json` | it runs as without the keys | |

### P2

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-P2-1 | S | The suite passes on the primary's own macOS, beside the `macos-latest` job | R-all-1 | R-all-1 passes | |

### A0

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-A0-1 | S | Symlinked core skills, workers, and workflows load on macOS (spike item 3 ran on Linux only) | in a session in the staging checkout, list the skills, the agent types, and the saved workflows | every core skill, worker, and workflow symlinked under `.claude/` is listed | |

## W2

### A1

No Mac-only check: R-A0-1 covers the symlinked `clean-code` and `clean-prose`.

### U2

No Mac-only check.

### P5+M3

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-P5+M3-1 | S | A health sample on the ports | `health.py sample`, then `health.py report` | the sample's readings match the old setup's sample taken within the same minute, level by level | |
| R-P5+M3-2 | S | The new health plist matches the installed one | `health.py install` (read-only form); diff its plist with `~/Library/LaunchAgents/<old health label>.plist` | they differ only in the label and the repository path | |
| R-P5+M3-3 | S | `uninstall` names the new jobs only | `health.py uninstall` and the Remote Control job's `uninstall`, read-only forms | neither names an old plist | |
| R-P5+M3-4 | W | The Remote Control job loads under launchd | `launchctl print gui/$(id -u)/<new label>` | state running; working directory `~/Developer/agent-core`; `caffeinate -i` in the command; no `--name` | |
| R-P5+M3-5 | W | A session from a secondary opens in the dispatcher repo | open a session from the laptop or the phone | its working directory is `~/Developer/agent-core` | |
| R-P5+M3-6 | W | One research question is answered through it | ask one library question in that session | the answer comes back with verified quotations | |
| R-P5+M3-7 | W | A handed-off dry-run batch runs in the research main checkout | ask that session for a dry-run batch | the batch runs in `~/Developer/research-assistant`, not a worktree | |

### P6+M4

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-P6+M4-1 | S | No placeholder in the library or the inbox | the preflight's `SyncedFolder` check over the real library and inbox, read-only | no placeholder; if one is found, Optimize Mac Storage is on and the switch waits | |
| R-P6+M4-2 | S | The accelerator is Metal | print `Accelerator.device()` and `reachable()` | `mps`; `reachable()` returns no cause | |
| R-P6+M4-3 | S | `Trash.discard` uses the macOS Trash | discard a scratch file through the port | the file is in the Trash and recoverable | |

### P3

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-P3-1 | S | Search answers identically | a fixed query set through `search.py` under the old and the new setup, on the same search stores | the hits, their order, and their scores are identical | |

### P4

No Mac-only check: R-P3-1 covers `mac-local` search.

### P9

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-P9-1 | S | A talk's raw transcript is unchanged | transcribe one short recording to its raw transcript under the old and the new setup; first run the old setup twice to see whether its output varies | the new raw transcript equals the old; if the old varies between its own runs, the speakers and the utterance order agree | |

### P10

No Mac-only check.

## W3

### A2

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-A2-1 | S | `residue` runs on a real vault | `vault-audit`'s `residue` against the staging vault, old and new | the same report | |
| R-A2-2 | S | The count-against-disk `staleness` runs on a real vault | the research `staleness` check against the staging vault | it runs and is not reported skipped | |

### U1, U3, U4

No Mac-only check.

### P7a

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-P7a-1 | S | Every path resolves as before | print every path the old `vault` constants name and every field of the new `Vault`, from the same `machine.json` | identical | |

### P7b–P7f, P7h

No Mac-only check: R-X3-1 and R-P11-2 run the moved code.

## W4

### U5, U6

No Mac-only check.

### U7

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-U7-1 | S | Stage timings are recorded on a real backfill | the backfill of R-P11-2, then `audit.py costs` | each stage's duration and each lock wait appear; no vault file changed format | |
| R-U7-2 | S | The health-journal measures are read | `audit.py costs` on the primary | the machine measures report from the health journals | |

### U8

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-U8-1 | S | The scout reads only the allowlisted hosts | dispatch the scout with a fixture source list naming one host outside the allowlist | the outside host is refused; the three allowlisted hosts are read | |

### P7g

No Mac-only check: R-X3-1 runs after the shim is gone.

### P11

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-P11-1 | S | `regress` records are byte-identical | `extract.py regress` under the old and the new setup, on the same sample | every extraction record byte-identical | |
| R-P11-2 | S | A Stage 2 → 6 backfill of three works runs as before | the `ingest` workflow from Stage 2 over three works in the staging vault, old and new | the same corpus file bodies, classifications, and bibliography listings | |

### P12

No Mac-only check.

### P13

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-P13-1 | S | The pixel check's verdicts are unchanged under Vision | `fonts scan` over a sample of filed PDFs, old and new | the same verdicts | |

### G17

No Mac-only check.

### G18

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-G18-1 | S | The git pre-commit hook runs on macOS | stage a file that fails ruff; `git commit` | the commit is refused with ruff's finding | |

### G19

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-G19-1 | S | The rendered worker files equal today's | `agents.py generate --host claude-code`; diff with the old checkout's `.claude/agents/` | equal apart from ordering | |

### G20

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-G20-1 | S | The generated settings blocks equal today's | `domain.py settings` over the real `~/Developer/*/domain.json`; diff with the old checkout's `.claude/settings.json` | equal apart from ordering and the folder rules G20 adds | |
| R-G20-2 | S | The sandbox refuses a Bash write outside the `write` folders (the cloud's sandbox is inert, spike item 1) | in a research session, a Bash `touch` in a folder outside `library` and `research vault` | refused by the sandbox | |
| R-G20-3 | S | A sensitive folder of another manifest is unreadable (spike item 7) | a fixture manifest listing a `sensitive: true` folder holding a canary file; regenerate the research settings; in a research session, read the canary with Bash `cat`, the Read tool, Grep, and Glob | all four refused; a control file beside the folder stays readable | |
| R-G20-4 | S | The manifest reader reads every domain on the primary | `domain.py manifests` | every `~/Developer/*/domain.json` listed | |

## W5

### P14

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-P14-1 | S | The venv builds from the new locks on macOS | the `mac-local` locks synced into the staging venv | the build succeeds; R-all-1 passes on it | |

### P15

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-P15-1 | S | `doctor` is green on the primary | `setup.py doctor` | every line `ok`, the primary checks included; R-P5+M3's jobs report as not yet installed until §6 step 4.6 | |
| R-P15-2 | S | `bootstrap --no-jobs` installs no job | `setup.py bootstrap --profile mac-local --no-jobs` in the staging home | no launch agent added | |

### P8

No Mac-only check.

### P16

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-P16-1 | R | The laptop's former install retires by the README | follow "Retire a former full install" on the laptop | no launch agent of the old setup loaded; `~/.research-vault` gone; the vault still opens in Obsidian | |

### A5

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-A5-1 | S | The folder step creates a folder and an Obsidian vault | `new-domain`'s folder step in the staging home, with a new folder and the vault offer accepted | the folder exists under the staged `~/Documents` with the default `.obsidian/` config | |

### A3

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-A3-1 | S | A library question routes to research | from a local session in `~/Developer/agent-core`: "what does my library say about X?" | a `research-assistant` session answers with verified quotations | |
| R-A3-2 | S | A batch starts in the background in the research main checkout | "start a batch" (dry run) from the dispatcher | the batch runs in `~/Developer/research-assistant`; the dispatcher reports once, at the end | |
| R-A3-3 | S | A request matching no domain is asked about | a request no `handles` entry covers | the dispatcher asks; it delegates nothing | |
| R-A3-4 | S | A delegated session applies the project's allow rules (spike item 2) | inspect the delegated session's startup for "Ignoring … permissions.allow entries" | no such line; the research checkout is a trusted workspace | |

### A4, U2b, G21

No Mac-only check.

## W7

### X7.1, X7.2

No Mac-only check.

### X7.3

| ID | Phase | Check | Command or action | Passes when | Result |
| --- | --- | --- | --- | --- | --- |
| R-X7.3-1 | S | `rehearse` builds the staging home | `cutover.py rehearse`, read-only form, then `--apply` | the read-only form changes nothing; the writing form builds the venv and the staging vault | |
| R-X7.3-2 | S | `switch` lists §6 step 4 in order | `cutover.py switch`, read-only form | every step of §6 step 4, in order, and nothing else | |
| R-X7.3-3 | S | `rollback` lists the old jobs, the old venv, and the old checkout | `cutover.py rollback`, read-only form | each old plist, the moved venv, and `~/Developer/research-tools` named | |
