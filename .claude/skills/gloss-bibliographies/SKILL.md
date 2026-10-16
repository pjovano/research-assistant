---
name: gloss-bibliographies
description: "Stage 5 — once a batch has placed its works, copy each work's description onto its listing on every bibliography as the listing's gloss, then have the bibliography introducer write each touched bibliography's introduction, a note on each of its groups, and the group of each unsorted work; a batch introduces the bibliographies it touched, and the user's instruction introduces one again."
allowed-tools: Read, Glob, Grep, Agent, Write, Bash(~/.research-vault/venv/bin/python .claude/skills/classify-and-place/scripts/bibliographies.py:*), Bash(~/.research-vault/venv/bin/python ~/Developer/research-tools/.claude/skills/ingest/scripts/ingest.py:*)
---

# gloss-bibliographies (Stage 5; a script copies, one worker judges)

**Precondition:** every work of the batch has reached `placed`, or the user
names a bibliography. **Postcondition:** each listing of a work that carries
a `description:` carries that description as its gloss; each bibliography
the stage introduced lists the works it listed, in the same lists of works,
under the same `## Maps`, and opens with an introduction; `check` reports no
blocking group.

**Stage 5 runs in two steps, in order.** The `classify-and-place` skill
defines the gloss, the introduction, and the group note.

| # | Step | Run by | Does |
| --- | --- | --- | --- |
| 1 | Copy | `gloss-copy`, a script | on every bibliography, writes each listed work's `description:` after the work's wikilink as its gloss |
| 2 | Introduce | the `bibliography-introducer` worker, one dispatch per bibliography, then `gloss-write` | writes the bibliography's introduction, a group note under each `###` group the worker writes one for, and each unsorted work into the group the worker names |

**A gloss is derived, never written.** `gloss-copy` replaces a gloss that
differs from the work's `description:`, so a gloss changes only through its
work's `description:`. A listing whose work carries no `description:` keeps
the line it has. `gloss-copy` reads the lists of works alone and leaves
`## Maps` as it stands.

**The bibliography introducer judges what the listed works share, and nothing
else.** It reads one listing and writes one answers file. `gloss-write`
refuses the answers, and writes nothing, if a check of the table fails.

| Answer | Refused if |
| --- | --- |
| `introduction` | it is empty, runs over one paragraph or over 80 words, or names a listed work by a wikilink |
| a group note | its group is not a `###` group of its list of works once the works are sorted, its group is `### Unsorted`, or the note is empty, runs over one paragraph or over 50 words, or names a listed work by a wikilink |
| a sorted work | the work is not an unsorted work, or its group is empty or `Unsorted` |

**An unsorted work is a listing in no group, or in `### Unsorted`, of a list
of works that carries a group.** `gloss-write` moves each sorted work into
its group, opens a group no list carries before `### Unsorted`, and removes
`### Unsorted` once it holds no listing. Stage 5 NEVER opens a group in a
list of works that carries none: the reshaping's folds open the first.

## Commands

Every command is `~/.research-vault/venv/bin/python .claude/skills/classify-and-place/scripts/bibliographies.py <subcommand>`.

| Command | Does | Writes |
| --- | --- | --- |
| `gloss-copy [--apply]` | `changed`, each bibliography whose listings step 1 changes | each changed bibliography, with `--apply` |
| `gloss-plan --works <basename>... --bibliographies <name>...` | `bibliographies`, the names to introduce: each bibliography a named work sits on, each named bibliography, and each bibliography without an introduction; a bibliography that lists no work and no map is left out | nothing |
| `gloss-plan --all` | every bibliography that lists a work or a map | nothing |
| `gloss-listing "<name>" [--out <path>]` | the bibliography introducer's listing: the bibliography's `kind`, its `introduction`, its `maps` with their introductions, its `groups` with their notes, its `works` with their descriptions, and its `unsorted` works | the listing file, with `--out` |
| `gloss-write "<name>" --answers <path> [--check]` | `written` and `problems`, each check of the table above that failed; exits 1 on a problem. With `--check`, reports and writes nothing | the bibliography's body, without `--check` and without a problem |

## The ingest workflow

**The `ingest` workflow runs Stage 5 in the tail, after the reshaping and
the check-off and before Stage 6, through two `drive-*` steps of
`ingest.py`; each prints one JSON line and runs under the bibliographies
lock.** With the run's `args` carrying `gloss: "all"`, the plan is every
bibliography; otherwise it is the bibliographies the works the run placed
sit on, by their work keys, those the reshaping touched, and each
bibliography without an introduction.

| Step | Runs | `state` and next step |
| --- | --- | --- |
| `drive-gloss-plan <key>...`, or `drive-gloss-plan --all` | `gloss-copy --apply`, then `gloss-plan`, then `gloss-listing` for each planned bibliography into `ingest/glosses/<n>/listing.json` in the scratch directory | `gloss`, with `root`, the path of `ingest/glosses/`, and `count`, the bibliographies planned: dispatch the bibliography introducer per number `<n>` from 1 to `count`, on `<root>/<n>/listing.json` and its answers path `<root>/<n>/answers.json`, all at once, then `drive-gloss-finish <root>/<n>`. NEVER print the bibliographies' names or paths: the bibliographies of a batch overrun the JSON line, and a spilled list is no plan the workflow can read. `nothing`: no bibliography was planned. `halt`: a command failed |
| `bibliography-introducer` dispatch | reads the listing, writes the answers file | `drive-gloss-finish <dir>` |
| `drive-gloss-finish <dir>` | `gloss-write` on the answers file | `glossed`, with `bibliography`: done. `aside`: the worker wrote no answers file, or `gloss-write` refused the answers; the bibliography keeps the glosses step 1 copied and the introduction it had |

A bibliography set aside without an introduction is planned again by the
next batch. The batch's one report lists each bibliography introduced under
`glossed`, and each set aside under `questions`.

## Outside a batch

If the user asks for a bibliography to be introduced again, or introduced
otherwise, run the steps by hand on that bibliography alone: `gloss-copy`,
read its `changed`, then `gloss-copy --apply`; `gloss-listing` with `--out`;
one `bibliography-introducer` dispatch on the listing, with the user's
instruction in its prompt as a note; `gloss-write --check`; then
`gloss-write`. If `gloss-write --check` reports a problem, dispatch the
worker once more with the problems as a note; on a second refusal, stop and
ask the user. NEVER run `gloss-write` on answers its `--check` refused.

If the user asks for a gloss to read otherwise, change the work's
`description:` on the user's instruction, then run `gloss-copy --apply`.

## Guarantees

On completion every listing of a described work carries the work's
description as its gloss, every bibliography the stage introduced lists what
it listed and opens with an introduction, and `check` reports no blocking
group. A bibliography the stage set aside differs from what it was by its
copied glosses alone.
