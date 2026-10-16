---
name: cite-links
description: "Stage 3 — once Stage 2 accepts a work, place a wikilink on every entry-list entry, or footnote, that names a held work published no later than the citing work, in the work's corpus file and in every corpus file naming its author, and bring the citation graph up to date; after every batch, the same over every corpus file; a corpus file is touched only when it gains a link."
allowed-tools: Bash(~/.research-vault/venv/bin/python .claude/skills/cite-links/scripts/cite.py:*), Bash(~/.research-vault/venv/bin/python .claude/skills/cite-links/scripts/graph.py:*)
---

# cite-links (Stage 3, run inline)

**Stage 3 is a deterministic script.** Outside a batch, the orchestrator
runs it inline. In a batch, the `relay` worker runs it through
`ingest.py drive-cite <key>` once Stage 2 accepts a work, and through
`ingest.py drive-cite` once per batch as the citation sweep. NEVER dispatch
it to any other worker.

**Stage 3 runs on a work before Stage 4 classifies it: the work classifier
reads the work's neighbours in the citation graph, which its citation links
and the links naming it build.** The per-work run links the work's own
entries, then every corpus file that names one of the work's authors, then
runs `graph.py sync` on each corpus file written. The citation sweep runs
`status` and `apply` over every corpus file, then `graph.py sync` whole, so
that a link between two works of one batch, whichever Stage 2 accepted
first, is written before Stage 6.

**A held work is a PDF in the library.** Its corpus file supplies its aliases
and its original year when the corpus file exists; its filename supplies its
creator, year, and title otherwise.

**A bibliography entry names a held work** when its score against the work
reaches the automatic threshold. The citation parser `references.py` names
splits the entry into authors, title, container, year, and pages. The score
is the similarity of the entry's main title, or of its container when the
container's own main title is two words or more, to the work's main title
and aliases, plus ten for an agreeing year and minus ten for a disagreeing
year. Where the parser names no title, the entry's whole text stands in for
it: a footnote citing a work by a short title and a section number parses
into no title at all. The score
counts the authors and the title alone: NEVER score an entry by the form of
what it cites, because a held work is cited as a piece of a volume as
readily as on its own. The score is zero unless one of the work's authors'
surnames is among the parsed authors, or, when none was parsed, in the entry
text; a surname found only in the entry's title caps the score below the
automatic threshold. The work's original year — its edition year when it has
none — MUST be no later than the citing work's. A work NEVER names itself.

**An entry that opens with a run of dashes, or with its year, is scored
under the author above it.** A reference list drops the author's name from
an entry repeating the author of the entry before it, printing a run of
dashes in its place or nothing at all. An entry opens with its year when its
first words are the year, bare or in parentheses, after `ed.` or `eds.` or
alone, followed by a period, a comma, or a colon. The entry is scored as
though the author's name stood before the year or where the dashes stand,
and the entry text is written unchanged.

**The score falls in one of three bands.** At or above the automatic
threshold, the entry names the work and `apply` links it. Between the
confirmation threshold and the automatic threshold, the entry is in the
middle band: it is reported in `to_confirm` and links only once a verdict
confirms it. Below the confirmation threshold, the entry names nothing. Both
thresholds are constants in `references.py`.

**The verdicts record settles a scored match.** The verdicts record is
`library/citation-verdicts.json` in the vault: under each citing basename,
under each entry text exactly as `to_confirm` reports it, the matched
basename and the verdict, `confirm` or `reject`, the citation judge's or
the user's. `settle --apply` alone writes it. A recorded verdict binds only
the citing work, entry, and matched work it names; a verdict on another match of the entry settles
nothing.

| Verdict | `status` and the citation sweep | `apply` |
| --- | --- | --- |
| `confirm` | never reports the match in `to_confirm`, nor its link in `stale` | links the entry as it links an automatic match |
| `reject` | never reports the match in `to_confirm` | NEVER links the entry to the work, at any score; NEVER links it to its second-best match |
| none | reports a middle-band match in `to_confirm` | links an automatic match alone |

NEVER move the verdicts record into the control plane: it changes with use,
and iCloud carries it to both machines.

**A work is matched by its longest title form.** Where one of a work's
titles is the opening of another — its main title beside its whole title —
only the longer is scored: a short form matches every entry whose title
opens with it, and a work named by one common word would name them all.

**A link whose entry names nothing is reported in `stale`.** `apply` NEVER
removes a link: a link a later rule no longer supports is listed for the
user, who decides whether it goes.

**A link targets a held work with a corpus file.** If the entry's best match
has no corpus file, the entry gains no link and is not reported: Obsidian
resolves a wikilink only to a note, and a link to a work with no corpus file
opens an empty note. The entry gains its link at the first Stage 3 after the
work's corpus file is written. NEVER link the entry to its second-best match
instead.

**The link follows the entry.** A link surface is an entry list — a section
headed references, bibliography, works cited, notes, endnotes, or one of the
equivalents `lib/_vault/citations.py` lists — and every footnote definition. Every
entry of an entry list that names a held work becomes
`<entry text> [[<basename>|↗]]`, and every footnote definition that names one
becomes `[^k]: <footnote text> [[<basename>|↗]]`. The entry text stays exactly as
Stage 2 wrote it: NEVER put it inside the link, because Obsidian renders a
link's shown text without its Markdown. A line already carrying a link is
rescored by its entry text and left as it is when the link names its best
match; one line carries one link, so a footnote naming a second held work
surfaces in `to_confirm`.

## The citation parser

**The citation parser is a token classifier `references.py` loads from the
Hugging Face cache**: `SIRIS-Lab/citation-parser-ENTITY`, or the model
`machine.json` names under `citation_parser_model`. Installing it is the
user's step, once per machine: the harness sets `HF_HUB_OFFLINE=1`, so the
download runs in a terminal with that variable unset:

    ~/.research-vault/venv/bin/python -c "from transformers import pipeline; pipeline('token-classification', model='SIRIS-Lab/citation-parser-ENTITY')"

Parsed entries are cached in `citation-parser-cache.sqlite` under `rag_dir`;
the cache is derived, and deleting it costs one re-parse.

## Procedure

Every command is `~/.research-vault/venv/bin/python .claude/skills/cite-links/scripts/cite.py <subcommand>`.
With no basename, a command covers every corpus file;
with basenames, only those.

1. **Status.** Run `cite.py status` and read what it prints: an object
   carrying `conflict_copies` and `rows`. If `conflict_copies` is non-empty,
   a sync left a copy beside a corpus file or a library PDF: stop and ask the
   user to merge and delete it before any link is written. If `status` exits
   non-zero naming the citation parser, the model is not available on this
   machine: stop and ask the user.
2. **Apply.** Run `cite.py apply`. It rewrites the linked lines of every
   corpus file whose row read `changed`, and nothing else in the file. It
   NEVER links a `to_confirm` entry. If `apply` exits non-zero, run `status`:
   a corpus file `apply` wrote before the failure reads `unchanged`, one it
   did not reads `changed`; stop and tell the user the error.
3. **Settle.** The citation judge gives the verdicts. Write the
   `to_confirm` items to listings in the shape the `citation-judge` worker
   reads, at most 120 matches to a listing, each with `n`, `citing`, `entry`,
   `candidate`, and `score`. Dispatch the `citation-judge` worker once per
   listing, all at once: invoke the Agent tool with `subagent_type:
   citation-judge` and the prompt `Listing: <listing>` and `Write your
   answers file to: <answers>`. Write each answer's verdict to a verdicts
   file; if the user gives a verdict, singly or by score band, the user's
   verdict replaces the judge's. Run `settle` without `--apply` and read
   every row. If a row reads `not-offered`, the pair is not the entry's
   current middle-band match: leave the pair out. Then run `settle --apply`.
   If `settle --apply` exits non-zero naming the run lock, an ingest run
   holds it: wait until the run returns, then run it again. If the judge
   wrote no verdict on a match, the match stays unlinked: list it in the
   report. NEVER ask the user for a verdict the judge gave.

| `status` | Meaning | Do |
| --- | --- | --- |
| `unchanged` | every entry naming a held work already carries its link | nothing |
| `changed` | `links_to_add` entries would gain a link, on the works in `linked_works` | run `apply` |
| `to_confirm` | a list, on every row: each item is an entry text, the candidate `basename`, and the `score`; empty when no middle-band match is unsettled by the verdicts record | send each item to the citation judge, as step 3 states; settle it only through `settle` |
| `rewritten` | `apply` wrote the links | proceed to Stage 4 |
| `no-body` | the corpus file has no body yet | run Stage 2 on the work, then Stage 3 again |
| `no-pdf` | the corpus file's PDF is not in the library | stop and ask the user |
| any other value | unspecified | stop and ask the user |

## Commands

| Command | Does | Writes |
| --- | --- | --- |
| `cite.py status [<basename>...]` | `conflict_copies`, the sync conflict copies beside the corpus files and in the library, and `rows`, one row per corpus file: its `status`, `links_to_add`, `linked_works`, `to_confirm`, and `stale` | nothing |
| `cite.py apply [<basename>...]` | the rows of `status`, and the exact and automatic links written; `status` reads `rewritten` where a file was written | the linked lines |
| `cite.py status --cited "<basename>"`, `cite.py apply --cited "<basename>"` | the same, over every corpus file but the work's own whose text names one of the work's authors, or over the work alone when none does; exits non-zero for a work not in the library, or beside basenames | as `status` and `apply` |
| `cite.py settle --verdicts <file>` | `planned`, `not-offered`, and `verdicts`, one row per verdict of the file with its `score` and its `status`: `planned` when the pair is the entry's middle-band match or a match the verdicts record settles, `not-offered` otherwise | nothing |
| `cite.py settle --scores <low> <high> --verdict confirm\|reject [<basename>...]` | the same, over every unsettled middle-band match whose reported score is at least `low` and below `high`, in the named corpus files or in every one | nothing |
| either `settle` form with `--apply` | the same rows with `status` `recorded` in place of `planned`, then `rows`, the rows of `apply` over each citing work a `confirm` names; exits non-zero, recording nothing, while an ingest run holds the run lock, unless `--in-run <pid>` names the session process that holds it | the verdicts record, then the linked lines |

A verdicts file is a JSON list; each item carries `citing`, `entry`, `work`,
and `verdict`, the `entry` exactly as `to_confirm` reported it. `settle`
records a `planned` row alone and NEVER a `not-offered` one. ALWAYS run
`settle` without `--apply` first and read every row.

## The citation graph

**The citation graph is every reference the corpus files make, held and
unheld, with the signals that relate two held works.** `graph.py` builds it
into the graph store, `citation-graph.sqlite` under `rag_dir`, which is
derived: deleting it costs one `sync`. A held reference is a citation link; an
unheld reference is an entry of an entry list, or a footnote, that names no
held work, merged with the entries of other corpus files that name the same
work by the rule `discover.py unheld` merges by. A work's centroid is the mean
of its vectors in the embedding store, absent until Stage 6 has indexed it.

Four signals relate two held works, each between 0 and 1, combined by the
weights `lib/_graph/signals.py` names: direct citation, in either direction,
halved when the works share an author; bibliographic coupling, the Salton
cosine of their reference sets; co-citation, the Salton cosine of the sets of
works citing each; and the cosine of their centroids.

Every command is `~/.research-vault/venv/bin/python .claude/skills/cite-links/scripts/graph.py <subcommand>`.

| Command | Does | Writes |
| --- | --- | --- |
| `graph.py sync [<basename>...]` | reads every corpus file whose size or modification time the graph store does not hold, or the named ones alone, and forgets every corpus file no longer in the derived corpus; prints `synced`, `removed`, and `notes` | the graph store |
| `graph.py sync --rebuild` | discards the graph store and builds it again | the graph store |
| `graph.py neighbours "<basename>" [--k <N>]` | the `N` works nearest the work, 10 absent `--k`, each with its `score`, its `signals`, the references the two share, and the bibliographies its `field:` names; then `bibliographies`, each bibliography the neighbours sit on weighted by the scores of the neighbours on it | nothing |
| `graph.py clusters` | `clusters`, the communities of three or more works Louvain finds over the combined signals, each with its works, its bibliographies by count, and its most-cited references; and `findings`, tabled below | nothing |
| `graph.py contexts "<citing>" "<cited>"` | `passages`, every passage of the citing corpus file that speaks of the cited work, in body order, each with its `kind`, its folio, and its text cut to 800 characters around the citation | nothing |

A cluster finding is one of four kinds, each keyed on a constant
`lib/_graph/clusters.py` names.

| Finding | Is |
| --- | --- |
| `new` | a cluster of three or more works of which no bibliography holds half |
| `split` | a bibliography of more than twelve works whose works fall in two or more clusters, each holding three or more of them |
| `misfit` | a placed work none of whose five nearest neighbours sits on any bibliography it sits on |
| `missing` | an unheld work three or more works of one cluster cite |

A passage's `kind` is `footnote`, the sentence calling a footnote whose
definition carries the cited work's citation link; `author-date`, the cited
author's surname within sixty characters before one of the cited work's
years; or `mention`, the cited work's main title or an alias beside the
author's surname, the surname with or without a possessive or genitive
ending. An entry of an entry list is never a passage.

If `sync` exits non-zero naming the citation parser, the model is not
available on this machine: stop and ask the user. `neighbours` and
`contexts` exit non-zero for a basename with no corpus file.

## Guarantees

On completion every entry of an entry list, and every footnote, that names a held work
carries that work's wikilink, and every middle-band entry is either settled
by the verdicts record or listed in the report. The frontmatter and every unlinked line
of the corpus file are byte for byte as they were.

## The ingest workflow

**The `ingest` workflow runs Stage 3 on each work through `ingest.py
drive-cite <key>`, under the citation links lock, and once per batch through
`ingest.py drive-cite`, the citation sweep; neither carries judgment.** The
`citation-judge` worker judges each middle-band match the sweep finds, and
`ingest.py drive-settle` records its verdicts. Each step prints one JSON
line.

| Step | Runs | `state` and next step |
| --- | --- | --- |
| `drive-cite <key>` | `cite.py apply "<basename>"`, then `cite.py apply --cited "<basename>"`, then `graph.py sync` on the work and on every corpus file the two wrote | `linked`, with `linked`, the corpus files written: Stage 4. `halt`: the citation parser unavailable, a failed `apply`, or a failed `sync` |
| `drive-cite` | steps 1 and 2 over every corpus file, then `graph.py sync` | `linked`, with `linked`: no middle-band match. `judge`, with `root` and `count`: the middle band written to `count` listings, `<root>/<n>/listing.json`, at most 120 matches each; dispatch the `citation-judge` worker on each listing, all at once, with its answers path `<root>/<n>/answers.json`, then `drive-settle`. `halt`: a conflict copy, the citation parser unavailable, a failed `apply`, or a failed `sync`: stop the batch with the line's `question` |
| `drive-settle` | the judge's verdicts written to `<root>/verdicts.json`, then `cite.py settle --verdicts <file> --apply --in-run <session process>`, then `graph.py sync` on the corpus files it linked, under the citation links lock | `settled`, with `confirmed`, `rejected`, and `linked`; a match the judge gave no verdict is a question, and stays unlinked until the next sweep. `halt`: a failed `settle` or a failed `sync` |
