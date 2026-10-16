---
name: machine-health
description: "Machine health — a launchd job samples memory, swap, memory pressure, the thermal state, and the workload processes every minute, raises a health alert on critical memory pressure or a serious or critical thermal state, and notifies on the desktop and, through a reminder iCloud syncs, on the phone; report on demand."
allowed-tools: Bash(~/.research-vault/venv/bin/python .claude/skills/machine-health/scripts/health.py:*)
---

# machine-health (run inline)

**The health watcher is a deterministic script.** launchd runs it once a
minute on the primary; the orchestrator runs its other commands inline.
NEVER dispatch it to a worker.

## Parts

| Part | Is | Run by |
| --- | --- | --- |
| `scripts/health.py` | the CLI, whose commands are tabled below | launchd for `sample`; the orchestrator for the rest |
| `lib/machine_health.py` | the facade over `lib/_health/` | `health.py` |
| health journals | `~/.research-vault/cache/health/samples/` and `alerts/`, one JSON-lines file per day; on the primary, never synced | written by `sample` |
| launch agent | `~/Library/LaunchAgents/com.research-vault.machine-health.plist`, naming `health.py` in `~/Developer/research-assistant`, never in a worktree | launchd |
| `ensure-health-watcher` | the `lib/harness_hooks.py` subcommand a PreToolUse hook runs before every Bash command | the harness |

**The health watcher NEVER imports `vault`.** Resolving the vault reads
`~/Documents`, which macOS guards per program, and a launchd job cannot
answer the prompt. `health.py` reads `machine.json` through
`_vault/machine.py` and matches the model servers through
`server_command_line.py`, neither of which resolves the vault.

## Commands

| Command | Does | Writes |
| --- | --- | --- |
| `sample` | take one sample, append it to the health journals, prune journal days past the retention, run the detectors on the sample, journal and notify each health alert not raised within the cooldown | the health journals; a desktop notification; a reminder |
| `report [--hours N]` | the system's worst readings, each process's first, last, and peak memory and its growth per hour, and the health alerts of the last `N` hours, 24 by default | nothing |
| `install [--apply]` | print the launch agent, whether it needs installing, and the `launchctl` command that loads it by hand; with `--apply`, write the launch agent if it is missing or stale and load it if it is not loaded | the launch agent |

## Samples

**A sample holds the system reading and the workload processes.** The system
reading is available memory, swap used, the memory pressure level, the load
average, the free disk under `~`, and the thermal state macOS reports:
`nominal`, `fair`, `serious`, or `critical`. macOS gives a process no
temperature in degrees without administrator rights, so the thermal state
stands for it. If the machine refuses a reading, the reading is `null`. A workload process is one whose command line names a
model server, `extract.py`, `transcribe.py`, the search skill's `server.py`
(labelled `vault-rag`), `ollama`, `llama-server`, or `whisper-cli`. The
sample also keeps the largest other processes by memory, each labelled
`other:<name>`, so the report sees memory growth outside the workload.

## Detectors

**A health alert is one detector's finding on the sample just taken, keyed so
the cooldown can suppress its repeat.** Each threshold is the level at which
macOS itself acts: at `critical` memory pressure it runs out of memory for
applications and quits them, and at `serious` thermal state it throttles the
machine to cool it.

| Detector | Raises when | Key |
| --- | --- | --- |
| pressure | the memory pressure is `critical` | `pressure:critical` |
| thermal | the thermal state is `serious` or `critical` | `thermal:<state>` |

NEVER add a detector on a trend in a process's memory or in swap: model loads
and the session's own growth raise one every hour, and `report` shows each
process's growth on demand.

## Settings

**Every setting has a default; `machine.json` MAY override one under the key
`health`.**

| Key | Default |
| --- | --- |
| `alert_cooldown_minutes` | 60 |
| `retention_days` | 14 |
| `other_processes_kept` | 5 |

## Install

**A pipeline command installs the health watcher.** Before every Bash
command, the `ensure-health-watcher` hook reads the command. If the command
runs a script of `clean-pdfs`, `file-pdfs`, `extract-corpus`,
`classify-and-place`, `cite-links`, `search`, `extract-chapters`, or
`transcribe-talks`, on macOS, and the control plane holds `health.py`, the
hook writes the launch agent if it is missing or stale and loads it if
launchd has not. The hook runs outside the sandbox. NEVER start the health
watcher from a pipeline script: a process the sandbox confines reads neither
swap nor memory pressure and cannot notify.

* If the hook loads the launch agent, it shows `Started the health watcher`
  once.
* If launchd refuses the launch agent, the hook shows `The health watcher
  did not start` with launchd's error, and the command runs. Run `install`,
  and give the user its `manual` command to run themselves.
* If the user asks whether the health watcher runs, run `report --hours 1`.
  If it reports no samples, read `~/.research-vault/cache/health/launchd.log`
  and report its last lines to the user.

## Reporting

* If the user asks how the machine holds up, run `report` over the hours the
  user names, 24 by default, and answer from it in counts and the processes
  that grew.
* During a batch, `ingest.py progress` carries `report` over the update
  interval into each batch update, as the `ingest` skill states.

## Phone delivery

**`sample` files each health alert it notifies as a reminder in the
Reminders list `Machine health`, due one minute after it is raised.** iCloud
carries the reminder to the user's phone, and the phone notifies when it
falls due. The minute lets the sync arrive before the reminder falls due.
NEVER deliver a health alert to the phone through a scheduled task or a
Claude session: a run costs a session and waits for the schedule, where the
reminder costs nothing and arrives in seconds.

* The first reminder on a machine makes macOS ask the user to let the health
  watcher control Reminders. If the user asks why no reminder arrived, tell
  the user to allow it under System Settings, Privacy & Security,
  Automation.
* If `osascript` fails or times out, the alert stays in the health journals
  and `report` lists it; the next alert of its key waits out the cooldown.
