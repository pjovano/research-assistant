---
name: ingest
description: "Ingest — run a batch, or a backfill from Stage 2, through the ingest workflow: each PDF through Stages 0 to 4 on its own, then the bibliographies check beside the citation sweep, the reshaping, the check-off of the project reading lists, Stage 5 on each bibliography the batch touched, and Stage 6, once, and the batch's one report."
allowed-tools: Bash(~/.research-vault/venv/bin/python ~/Developer/research-assistant/.claude/skills/ingest/scripts/ingest.py:*), Bash(~/.research-vault/venv/bin/python ~/Developer/research-assistant/.claude/skills/extract-corpus/scripts/extract.py drive-queue), Workflow, CronCreate, CronDelete, mcp__claude-code-remote__send_later
---

# ingest (the batch, through the `ingest` workflow)

**The `ingest` workflow, `.claude/workflows/ingest.js`, runs a batch.** It
carries each PDF through Stages 0, 1, 2, 3, and 4 on its own, one PDF's
stage beside another's, then runs the bibliographies check beside the
citation sweep, the reshaping, the check-off, Stage 5 on each bibliography
the batch touched, and Stage 6, once, after every PDF has stopped. **The
check-off** is `ingest.py drive-readings`: it moves each wanted entry of a
project reading list that names a placed work, a held work whose `field:`
names a bibliography, under `# Held` as the work's wikilink with its reason.
It reads each `<Project> - Reading list.md` of `research
vault/bibliographies/4 reading lists/` and no other note of that folder.
**The bibliographies check** is `bibliographies.py check --json`, which `ingest.py
drive-check` runs. **The citation sweep** is `ingest.py drive-cite` without a
key: Stage 3 over every corpus file, which catches a link between two works
of one batch, and a full `graph.py sync`; the `citation-judge` worker then
judges its middle band, and `drive-settle` records the verdicts. Every
deterministic step is a `drive-*` subcommand that prints one JSON line whose
`state` names the next step; the `relay` worker runs each one. Every judgment is another worker's. Each stage's skill states its steps in
its own "The ingest workflow" section.

**A JSON line the relay returns names no work and no path that names one.**
NEVER pass a work's name through the relay: the relay retypes every
character it carries, and turns a quotation mark into a JSON delimiter. A
work key is the number `drive-batch` lists a work under. Every `drive-*`
step takes the work key as its work argument. `ingest/by-key/<key>/` in the
scratch directory is a link to the work's batch work directory; it holds the
work file, `work.json`, which names the work's `pdf` and its `basename`. A
`drive-*` step prints every path under the link, and prints every other
string with each quotation mark as an apostrophe, each backslash as a slash,
and each control character as a space. A worker that needs the work's name
reads the work file its prompt names.

**A JSON line a `drive-*` step prints carries the prose the workflow only
forwards within 700 characters, and is at most 8,000 characters.** The
forwarded fields are `question`, `questions`, `notes`, `classes`, `created`,
`moved`, `linked`, `unlinked`, `added`, `folded`, and `checked_off`. If the
line runs past
700 characters, the step writes its longest forwarded field to a file under
`spilled/` in the scratch directory, and repeats with the next longest until
the line fits: a list becomes one item naming its count and the file, which
holds one item to a line; a string becomes its first 200 characters and the
file, which holds it whole. If the line still runs past 8,000 characters,
the step spills its longest list of any field the same way until the line
fits. NEVER let a line run longer: the relay retypes a long line wrong, and
the relay's tool saves a line past 8,000 characters to a file and returns its
path, which the workflow cannot read as the line.

**A line names the files of a dispatch list by their count and their file
names, NEVER by a list of paths.** `parts`, `batches`, and `groups` each
hold `count` and, per file, a file name in the line's `dir` in which `{n}`
stands for the item's number, 1 to `count`. `drive-gloss-plan`'s `count`
holds the bibliographies planned, each in the directory of its number under
the line's `root`. NEVER print such a list as
paths: the list grows with the count, and a long line comes back from the
relay as its tail.

**`ingest.py` runs the steps that hold for a whole batch, and carries no
judgment.** It runs the other skills' scripts and imports none of their code.

**Every command names its script from the home directory.** Run each
`ingest.py` and `extract.py` command this skill names as
`~/.research-vault/venv/bin/python ~/Developer/research-assistant/.claude/skills/<skill>/scripts/<script> <subcommand>`,
from any working directory. NEVER change the working directory: every relay
of the run inherits it.

## Running a batch

**Start a run only in a turn whose user message asks for the run.** The
harness relays the message of the turn that starts the run to every worker
of the run as the request the run serves, and a worker handed a request
about another work weighs it against its own. If the next run falls due in a
turn whose user message asks something else, answer the message, then arm a
one-shot wake-up, with `CronCreate` or `send_later`, whose message asks for
the run, and start the run in the wake-up's turn.

1. Invoke the Workflow tool with `name: ingest`:

   | Run | `args` |
   | --- | --- |
   | a batch | `{"from": "clean"}` |
   | a backfill | `{"from": "extract", "start": <first key>, "end": <last key>}`, after `extract.py drive-queue`, as the `extract-corpus` skill states |
   | named works | add `"works"`: the work keys to carry, as `ingest.py list-works --from <from>` prints them |
   | every bibliography glossed | add `"gloss": "all"`: Stage 5 plans every bibliography that lists a work or a map, instead of the bibliographies the run touched and those without an introduction; every run, with or without the key, copies each work's description onto its listings on every bibliography |
   | each trial cleaned up | add `"cleanup": true`: Stage 2 sends each trial through the cleanup, by the `extract-corpus` skill's *The cleanup*, before it accepts it. Pass it only on the user's instruction |
   | no bibliography glossed | add `"gloss": "none"`: Stage 5 plans nothing and writes nothing; the tail runs the bibliographies check, the citation sweep, the reshaping, the check-off, and Stage 6 as without the key. Pass it only on the user's instruction |
   | no search stores synced | add `"index": false`: Stage 6 does not run, and the report carries no question of it; the next run that runs Stage 6 syncs every corpus file this run wrote. Pass it only on the user's instruction |

   A batch run SHOULD carry at most 45 PDFs, and a backfill run at most 55
   works: one run dispatches at most 1,000 workers, a backfill work takes
   about eleven, and the tail up to 360. If the batch lists more,
   pass `start` and `end` over its listing; once the run returns, run
   `ingest.py list-works` again and pass the next range over the new
   listing. NEVER carry a range over from the listing before: a placed work
   leaves the listing, and every key after it shifts.
2. Run `ingest.py progress` once, and schedule a recurring wake-up of this
   session every `interval_minutes` it prints: with `CronCreate` where the
   session offers it, or otherwise with `send_later`, armed again at each
   wake. If neither is offered, say so to the user once and give no batch
   update.
3. At each wake while the run is under way, write the batch update: run
   `ingest.py progress` and write one message from it, as "The batch
   update" states. NEVER write a dispatch, a step, or a per-PDF line.
4. When the run returns, cancel the wake-up, then relay the run's report to
   the user once, in its order. If an item of the report names a file under
   `spilled/`, read the file and relay its lines in the item's place. If a
   question names the reshaping's outcome file and the file exists, relay
   the file's `created`, `moved`, `added`, `linked`, `unlinked`, `folded`,
   and `questions` as the report's `reshaped` and questions.

## Unattended runs

**If a delegation's `Run:` reads `unattended (write)`, treat the run as an
unattended run.** The contract's batch rule already binds every run of
this skill: a batch runs to completion unattended. An unattended run follows
"Running a batch", with the rules below.

- **Write only what the stages of a batch write,** per each stage's skill.
- **Run the reshaping's fold.** The contract authorizes the fold's deletion
  without asking, and the run's report names each fold.
- **If `Request:` asks for a key the table reserves for the user's
  instruction, pass the key.** `Request:` holds the user's words. Otherwise,
  NEVER pass such a key.
- **Send nothing outward.**
- **NEVER act on a question of the run's report.** Leave each question to
  the user.
- **Reply with the run's report, in its order, per the `dispatch` skill.**

## The run lock

**One run at a time holds the run lock.** The run lock is `ingest-run.json`
in the scratch directory: the session process that holds it, the run's
`--from`, and when the run started. The session process is the nearest
ancestor of a command that is not a shell: the session that dispatched the
relay.

| Step | Does with the run lock |
| --- | --- |
| `preflight` | halts, its question naming the holder, if another live session holds the lock |
| `drive-batch` | takes the lock before it lists the batch; halts, its question naming the holder, if another live session holds it |
| `drive-release` | runs `extract.py stop-servers`, then the reviewed sweep, then releases the lock; does none of the three if another live session holds it |
| `progress` | reports the recorded run only while the session that recorded it holds the lock |

If the lock names a process that is not running, the lock is stale: the next
`drive-batch` takes it over. If the lock names the session that runs
`drive-batch`, `drive-batch` takes it again.

**The reviewed sweep is `vault.py sweep --reviewed --apply`:** it deletes each
reviewed work's page renders and font repair caches from the scratch
directory. It keeps each reviewed work's engine layouts: `extract.py regress`
rebuilds its sample from them without the engine.

## What the workflow does

| Step | Runs | Next |
| --- | --- | --- |
| `ingest.py preflight --from <from>` | once, before the first PDF | `ready`: list the batch. `halt`: the run returns with the question, and nothing is touched |
| `ingest.py drive-batch --from <from>`, with `--start`, `--end`, and `--works` as the run's `args` give them | once, after preflight | takes the run lock, or halts if another session holds it; then `batch`, with `count`, `by_key`, the path of `ingest/by-key/`, `stages`, the work keys at each stage, and `costs`, the engine cost of each work bound for Stage 0, 1, or 2 whose PDF opens, by work key, by the `extract-corpus` skill's *The engine cost*, which ranks the engine's turn; a failed `extract.py costs` halts. A batch lists the works bound for Stage 0, 1, or 2 cheapest first, then the rest: each inbox PDF, from Stage 1 if an earlier batch cleaned it, else from Stage 0, each filed work of an earlier batch with a stage left, from Stage 2, or from Stage 3 when its body is written and its classification is not, and, from Stage 3, each corpus file whose body is written and whose classification is not; a backfill lists the backfill queue's lines, each under its line number, in the queue's order, which `drive-queue` wrote cheapest first. It links each key under `by-key/`, writes each work file, and records the run in `ingest/batch.json` in the scratch directory, for `progress`. If fewer keys come back than `count`, the run halts |
| `extract.py prefetch --await-fonts --keys <key>...`, detached under the key `prefetch`, on a backfill only, with the keys of every work `drive-batch` listed | once, right after `drive-batch`, beside the works; the workflow never waits on it | `running`: the engine converts the run's works ahead of their `drive-prep`, each once its state records its font repair, as the `extract-corpus` skill's "Conversion runs ahead of a backfill" states; any other line is a question |
| each work, all at once under the locks below | Stage 0 to Stage 4, each through its skill's "The ingest workflow" section; Stage 3 is `ingest.py drive-cite <key>` | `placed`, `skip`, `aside`, or `paused` |
| `ingest.py drive-check` | the bibliographies check, once, beside the citation sweep | each blocking group is a question; an advisory group never is |
| `ingest.py drive-cite` | the citation sweep: `cite.py status`, then `cite.py apply`, then `graph.py sync` | `judge`: each middle-band match goes to the `citation-judge` worker, in listings of at most 120, all at once, then `drive-settle` under the citation links lock, as the `cite-links` skill's "The ingest workflow" states; conflict copies, the citation parser unavailable, a failed `apply`, or a failed `sync` halts |
| `ingest.py drive-settle` | `cite.py settle --apply` on the citation judge's verdicts, inside the run that holds the run lock, then `graph.py sync` on the corpus files it linked | `settled`; a match the judge gave no verdict is a question; a failed `settle` or `sync` halts |
| `ingest.py drive-clusters` | the reshaping's listing: the citation graph's clusters and findings, the authors of five or more works without a bibliography, the open nominations, the works on routing bibliographies, the stray placements, and the fold candidates, cut into parts; deletes the outcome file and the merged answers file of the reshaping before | `shape`, with `dir` and `parts`, the parts' directory and files, and `outcome`, the path of `ingest/reshape/outcome.json`: dispatch one `bibliography-shaper` worker per part, all at once, then `drive-merge`, as the `classify-and-place` skill's "The reshaping" states; `nothing`: no finding |
| `ingest.py drive-merge` | `merge-answers` on the answers files the shaper wrote for the parts, into `ingest/reshape/answers.json` | `merged`, with `answers`: `drive-reshape <answers>` under the bibliographies lock; `aside`: no part has an answers file, or the merge failed, and the report's question says the bibliographies were not reshaped |
| `ingest.py drive-reshape <answers>` | `reshape --answers --apply` on the merged answers; writes its line, unspilled, to the outcome file | `reshaped`, with `created`, `moved`, `added`, `linked`, `unlinked`, `folded`, and the shaper's `questions`; `aside`: no answers, or refused answers. If the relay returns no JSON line, the report's question names the outcome file and says whether the reshaping was applied is unknown, NEVER that the bibliographies were not reshaped: the step may have applied the answers |
| `ingest.py drive-readings` | the check-off, once, after the reshaping | `read`, with `checked_off`, each entry moved under `# Held` as `<Project>: <the held line>`; a project reading list with no wanted entry is not written; any other line is a question, and the tail carries on |
| `ingest.py drive-gloss-plan <key>...`, with the keys of the works placed, or `--all` | Stage 5's copy, each work's description onto its listings on every bibliography, then its plan: the bibliographies touched, by placement or by the reshaping, and each bibliography without an introduction, each with the bibliography introducer's listing; under the bibliographies lock | `gloss`: each bibliography through the `gloss-bibliographies` skill's "The ingest workflow" section, all at once, the write under the bibliographies lock; `nothing`: no bibliography planned |
| `ingest.py drive-index`, detached under the key `tail`, unless the run passes `"index": false` | Stage 6: `search.py sync`, then `status`, with the one further sync the `search` skill allows | `indexed`; changed vectors ask the user to reconnect `vault-rag`; `rebuild` on a changed embedding model; a sync stopped at its time limit is `indexed` with a question naming the works it indexed, because the sync keeps each work it finished, and `halt` if it indexed none; `halt` otherwise |
| `search.py sync --rebuild`, detached under the key `tail` | its own relayed step, only after `rebuild` | its permission prompt waits on the user; then `drive-index` once more, and a second `rebuild` halts |
| `ingest.py drive-release` | once, last, on every exit path after preflight, after a halt too, unless preflight halted | `released`, with `prefetch_stopped`, the pid of the run's `prefetch` step it stopped, with every process the step started, or `null`, the pids `extract.py stop-servers` stopped and the `swept_bytes` the reviewed sweep deleted; `not-held` if another session holds the run lock; a failed `stop-servers` or a failed reviewed sweep is a question, and the lock is released all the same |

**An engine command runs outside the sandbox only when its whole command line
matches a pattern of `excludedCommands` in `.claude/settings.json`,** and
inside the sandbox the engine has no Metal: its model servers fail every
request. The workflow's relays run each script by the full path the patterns
name, so every step, and every command a step detaches, runs outside it. If
`prefetch` is run by hand, outside a run, run exactly this as one Bash
command in the background, with nothing before or after it:

    ~/.research-vault/venv/bin/python ~/Developer/research-assistant/.claude/skills/extract-corpus/scripts/extract.py prefetch

NEVER start `prefetch` by hand while a run holds the run lock: the run starts
its own.

**A step that can outrun the relay's ten-minute timeout runs detached.**
`ingest.py drive-detach <key> -- <command>` starts the command in the
background and prints `running`; `ingest.py drive-wait <key>` waits up to
560 seconds, inside the relay's ten-minute timeout, and prints the command's last JSON line, or `running` again.
The workflow runs `drive-wait` until the line is not `running`. The step's
files sit in the key's batch work directory.

| Step | Key |
| --- | --- |
| `clean.py drive-fonts`, the font scan | the work key |
| `extract.py prefetch` | `prefetch` |
| `ingest.py drive-index` | `tail` |
| `search.py sync --rebuild` | `tail` |

**A lock serializes each shared resource across the works, and a limit
caps Stage 0:**

| Lock | Guards |
| --- | --- |
| Stage 0, at most four PDFs at once | each PDF's whole Stage 0: the `pdf-cleaner` dispatch, the font repair, and the `pdf-bookmarker` dispatch |
| the engine | `drive-fonts`, of an inbox PDF or of a backfill work, `drive-prep`, `drive-trial`, `drive-retrial`, each with every `drive-wait` until its result; the turn goes to the waiting step the `extract-corpus` skill's "When the engine frees" ranks first |
| the Zotero connector | `drive-file` |
| the identity table | `drive-learn` |
| the citation links | `drive-cite <key>`: it writes links into other works' corpus files; `drive-settle` |
| the bibliographies | `drive-classify` with `--answers`; `drive-reshape`; `drive-gloss-plan`; `drive-gloss-finish` |

**`halt` stops the batch.** A `drive-*` step prints `halt` when its failure
would recur on every PDF. The workflow then starts no further step: each
step under way finishes, and each PDF waits as a paused PDF at the stage it
reached. The bibliographies check, the citation sweep, the reshaping, the
check-off, Stage 5, and Stage 6 do not run;
`drive-release` does. A later batch carries each paused PDF on, because every
driver reads its own work directory and `drive-batch` lists every work with
a stage left.

**A relay whose reply ends in no JSON line halts the batch at preflight,
`drive-batch`, and the tail, and sets the PDF aside at any other step.** The
question names the relayed command and carries the reply's first 300
characters. The workflow reads the last line of the reply, ignoring
code-fence lines and the backticks around the line, as the JSON line; if the
last line does not parse, it reads the whole reply as one line.

**Before the halt or the aside, the workflow dispatches the relay once more
at every step but a tail step:** preflight, `drive-batch`, `drive-release`,
and each step of Stages 0 to 4. The step runs its command again. A detached
step still running is awaited and never started twice, and `drive-wait`
returns a finished step's result again until the work's next detached step
starts. NEVER relay a tail step again: the reshaping and Stage 5 write
bibliographies, and a second run would write them twice.

**A per-work worker that returns nothing is dispatched once more.** If the
`pdf-bookmarker` or `pdf-filer` dispatch fails or returns no report, the
workflow dispatches the worker again once; a second empty dispatch sets the
PDF aside. If `drive-learn`, `drive-retrial`, or `drive-classify --answers`
prints `unwritten`, the glyph reader, the page reader, or the work
classifier wrote no file for a listing it was given: the workflow dispatches
the same workers on the same listings again once and runs the step again; a
second `unwritten` sets the PDF aside with the line's `question`.

**An `aside` at preflight, `drive-batch`, or a tail step halts the batch.**
Such a step's `aside` is an error that recurs on every PDF.

**A driver NEVER runs a guarded command but `labels --apply`, which the
contract authorizes.** A `drive-*` step runs as one Bash command, so the hook
in `.claude/settings.json` sees none of the commands it runs. A driver runs
only these writing forms:

| Stage | Writing forms |
| --- | --- |
| 0 | `clean --apply`; the font repair and `learn-reader --apply` of an inbox PDF, or of a backfill work before `drive-prep` converts it; `volume --apply` |
| 1 | `file --only` and `retry --only` |
| 2 | `extract --trial`; `accept`; `labels --apply` |
| 3 | `cite.py apply`; `cite.py settle --apply` on the citation judge's verdicts; `graph.py sync` |
| 4 | the classification written into the frontmatter; `place --apply` |
| the reshaping | `reshape --apply` |
| the check-off | each project reading list a placed work is checked off |
| 5 | `gloss-copy --apply`; `gloss-write` |
| 6 | `search.py sync` |

`sync --rebuild` runs as its own relayed step, where the hook sees it on the
`drive-detach` command line.

## The models

| Agent | Model |
| --- | --- |
| the `relay` worker, for each `drive-*` step, preflight, and the tail | Haiku, effort low, from its worker instructions, which load no contract |
| the `title-checker` worker, for Stage 1's opaque-title check | Haiku, effort low, from its worker instructions, which load no contract |
| `pdf-cleaner`, `pdf-bookmarker`, `glyph-reader`, `section-scoper`, `page-reader`, `work-classifier`, `citation-judge`, `bibliography-shaper`, `bibliography-introducer` | Sonnet |
| `pdf-filer` | the model its worker instructions name; the workflow passes none |

## The report

The run returns one object, in the order the contract fixes:

| Key | Holds |
| --- | --- |
| `halt` | the halt's question, or `null` |
| `paused` | each paused PDF with the stage it reached |
| `filed` | each work placed, with its notes: a conflict in the identity table, an outline entry not found, a field recorded with doubt, a minor extraction defect, a work classifier's caveat on a settled value |
| `set_aside` | each set-aside PDF with its stage, its `question`, and its notes |
| `skipped` | each backfill work Stage 2 skipped: reviewed, or carrying a body |
| `reshaped` | the reshaping's `created`, the bibliographies created; `moved`, each work moved with its source and its target; `added`, each work placed on one more bibliography; `linked` and `unlinked`, each bibliography with the parent it was set beneath or taken from; `folded`, each bibliography folded with its target, its group, its works, and, under `writing`, each atomic note and project file whose `field:` the fold rewrote; `null` when nothing was reshaped |
| `checked_off` | each entry the check-off moved under `# Held`, with its project |
| `glossed` | each bibliography Stage 5 wrote |
| `questions` | the question of a `prefetch` that did not start, and each question of the bibliographies check, the citation sweep and its settlement, the reshaping, the check-off, Stage 5, and Stage 6, each only if the run ran it |

## The batch update

**`ingest.py progress` is read-only, and reads the run `drive-batch`
recorded, while that run holds the run lock.** It prints one JSON line:

| Key | Holds |
| --- | --- |
| `interval_minutes` | `batch_update_minutes` of `machine.json`, 30 if the key is absent |
| `started`, `elapsed_minutes` | when the run listed its works, and the minutes since |
| `works`, `done` | the works the run carries, and those placed |
| `stages` | the works at each stage they reached: `clean`, `file`, `extract`, `cite`, `classify`, `moved among the volumes`, `left the inbox, not traced`, and `placed` |
| `health` | the `machine-health` report over the last interval: the lowest free memory, the most swap used, the worst memory pressure and thermal state, the highest load, the least free disk, the five fastest-growing processes, and the health alerts |

If no run is recorded, or the recorded run does not hold the run lock,
`state` is `no-batch`, with `interval_minutes` alone.

**The batch update is one message, in this order:** the elapsed time; the
works done and the works remaining, in counts by stage, naming only the
works moved among the volumes; then the machine's
health, in one line per reading, with each health alert. A work still short
of `placed` MAY be set aside: the run's report names each set-aside PDF.

## Preflight

| `--from` | Checks |
| --- | --- |
| `extract`, a backfill, and `clean`, a batch | the run lock free, stale, or held by this session; no `engine-run.json` in the scratch directory, whereas a `prefetch` conversion, recorded in `engine-prefetch.json`, never halts it; no detached step whose `step.pid` names a running process, in a batch work directory or a backfill work directory; the control plane on `main` with no uncommitted change; the working directory not under `.claude/worktrees/`; every checkpoint the engine's settings name in the model caches; an adapter this version provides for `providers.sync`; no file of `library/` or `library/volumes/` whose bytes are not on disk |
| `clean`, a batch, besides | Zotero online, as `file.py doctor` reports it; Better BibTeX answering a search; Apple Vision installed; no conflict copy in the derived corpus, the talk transcripts, or the library; no PDF or draft card of the inbox whose bytes are not on disk |

**`providers.sync` judges the conflict copies and the files whose bytes are
not on disk.** `ingest.py synced-folder --from <from>` is read-only: it runs
those checks of that `--from` alone and prints the same JSON line.

If `engine-run.json` names a process that is not running, the check still
fails, and its question says the process is not running: delete the file
once the user confirms no conversion runs.

| `state` | Means | Do |
| --- | --- | --- |
| `ready` | every check passed | start the batch's first PDF |
| `halt` | a check failed; `question` names every failed check | stop the batch before its first PDF and ask the user `question` |

## If the Workflow tool is unavailable

Run the batch by hand: each stage's skill states its steps, and its "The
ingest workflow" section the same `drive-*` calls in order.
