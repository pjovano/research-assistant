---
name: annotate-pdfs
description: "Annotate — on a research request, write real, editable highlights with contextual notes into a library PDF, and revise annotations already written there."
allowed-tools: Read, Write, Glob, Grep, Bash(~/.research-vault/venv/bin/python lib/annotate.py:*), Bash(~/.research-vault/venv/bin/python .claude/skills/answer-questions/scripts/verify.py locate:*), Agent
---

# annotate-pdfs (Annotate, run by the orchestrator; a worker for a whole work)

**Boundaries:**

- NEVER touch the derived corpus, the bibliographies, or the search stores.
  NEVER write an answer or a note into the vault. The search stores and the
  corpus files are used only to find passages.
- **The annotations are the user's, not yours.** No authorship namespace, no
  per-pass marker, no colour outside the Colour table: they MUST be
  indistinguishable from hand-made highlights. The author name comes from
  `annotation_author` in `machine.json`; if absent, leave the field unset.
- A tag names the subtopic a passage belongs to, for later filtering — never
  a provenance stamp. A generic request writes the annotations untagged.
  Otherwise, if no tag was given, ask for one; if the user declines, write
  the annotations untagged. NEVER invent a taxonomy.

**Colour follows the kind of request.**

| Request | Colour |
| --- | --- |
| generic: the main claims or the steps of the argument, the work's own core claims, its note a claim comment | `yellow`, the reader's default |
| a contested passage, its note a dispute comment: held works read it, or the concept it states, in contrary ways, in a primary or a secondary work; NEVER a passage commentators read in one way | `orange` |
| a note that only points elsewhere, a pointer comment: parallel passages, or works that discuss the passage | `gray` |
| a topic, or a source the user did not write, its note a claim comment | the topic's group: `blue` for theoretical philosophy (logic, language, mathematics, science, metaphysics, causality), `green` for practical philosophy (ethics, politics, aesthetics, religion) |
| for one of the user's own papers, or a case the user marks out | the colour the user names; `red`, `purple`, and `magenta` are reserved for such cases, NEVER a default, since each reads poorly through the page |
| the references of an atomic note | the `take-notes` skill's `highlight` writes them, and its "Colour" states their colour |

**A book keeps few colours, each with one meaning:** a book read with many
commentaries shows mostly yellow, orange, and its group's colour, with gray
for pointers. If a request fits none of the rows, ask the user for the
colour.

## First: which mode?

Four modes run: whole work, trace, cites trace, revision. If the prompt
fits more than one, ask which. NEVER guess, and NEVER silently run two: the
sets differ and the run is expensive to redo. If the prompt fits none, stop
and ask the user. Say which mode is running before starting.

## The mechanism, in every mode

1. Resolve the request to one PDF in `library/` by basename. If no PDF
   matches, or more than one does, stop and ask the user.
2. Locate the page: by `locate --ref` where `anchors` reports inline
   markers; by `verify.py locate "<basename>" "<phrase>"` for the file pages
   whose text layer carries a quoted phrase; or by reading, in whole-work
   mode.
3. Read that page — the page, not the surrounding extract.
4. Judge the span: a clause, a sentence, or at most four sentences; never a
   whole paragraph when one sentence carries the claim.
5. Emit `(file page, start_word_index, end_word_index, note)`.
6. Write through `annotate.py`.

- A span NEVER starts or ends on an inline pagination marker.
- If the sentence runs over a page break, the entry is a cross-page span:
  see Writing.

Word indices come from the page's own word list. NEVER locate a highlight by
string matching: ligatures, soft hyphens, hyphenation, and two-column flow
defeat it.

### Check anchoring before planning a trace

```bash
~/.research-vault/venv/bin/python lib/annotate.py anchors "<pdf>"
```

Anchoring is a per-PDF capability — detected, never assumed:

| Strategy | Gives |
| --- | --- |
| `inline-marker` | bracketed edition pagination: a bracket holding one or more references joined by `/`, each an edition siglum (one or more capital letters) and a page, or a volume, a colon, and a page; word-level precision. A bracket holding a bare number, a year, or prose is not edition pagination |
| `marginal-number` | bare margin numbers; page-level plus height |
| `quote-match` | the file pages whose text layer carries a quoted phrase, from `~/.research-vault/venv/bin/python .claude/skills/answer-questions/scripts/verify.py locate "<basename>" "<phrase>"`; always available, least reliable |

Resolve one reference, writing nothing:

```bash
~/.research-vault/venv/bin/python lib/annotate.py locate "<pdf>" --ref A137
```

If a reference has no marker, `locate` reports the nearest markers below and
above: read between them to close the gap. NEVER guess. If `anchors` or
`locate` exits non-zero, stop and tell the user its message.

## The modes

### Whole work — "find all the passages in X dealing with Y"

Dispatch the `pdf-annotator` worker: invoke the Agent tool with
`subagent_type: pdf-annotator` and no `model`; the prompt carries the PDF
path, the mode, the question, the tag, and any page restriction. The worker
proposes and reports misses; the orchestrator validates and writes. The worker
never touches the PDF. If the worker returns `{"error": …}` or no JSON object,
dispatch it once more; if it fails again, stop and tell the user.

### Trace — "highlight every passage of X that paper Y comments on"

Dispatch the `pdf-annotator` worker on the citing work, as under Whole work,
in trace mode with the cited work's basename; it returns, per cited passage,
what the citing work says about it: every whole-work read goes to a worker
(`AGENTS.md` §4). Land those passages in the cited work's PDF. If the
worker returns no citable passage, report that and stop.

- **If the citing paper quotes a different translation or edition**, the
  `quote-match` strategy fails or matches weakly. Track the passage down in the
  library's edition by judgment: the surrounding argument, the section, the
  canonical reference (A/B, Bekker, Stephanus, Akademie), names and terms
  that survive translation.
- If a note records a translation difference, say so in the note.
- If a passage that plainly exists cannot be located, report the miss.
  NEVER guess: a wrong highlight is worse than an absent one, because the
  user prunes by relevance and never re-verifies placement.

### Cites trace — "annotate this book to reflect what it cites"

Read the wikilinks Stage 3 placed in the book's corpus file, on its
bibliography entries or its footnotes; each names a held work the book
cites. For each, land the passages where the book engages that work, with
the engaged work's wikilink and what the book says about it as the note.
If the corpus has no corpus file for the book, the corpus file has no
body, or it carries no wikilink, there are no entries: say so; NEVER return
an empty result silently.

### Revision — editing annotations that already exist

```bash
~/.research-vault/venv/bin/python lib/annotate.py list "<pdf>"
```

Prints every annotation with its note, tag, and covered text. Selection is
semantic: identify "the ones about X" by reading what they cover, never from
a manifest — the PDF is the only record. `--tag` narrows the field first:

```bash
~/.research-vault/venv/bin/python lib/annotate.py list "<pdf>" --tag "<tag>"
```

NEVER treat a tag filter as the full set: untagged and hand-made
highlights carry no tag and never appear in a filtered listing.

**A cross-page span lists as one record**, `p318–319 #0/#0`, with its
covered text joined across the page break. The pairing is inferred, never
stamped: two highlights on adjacent pages are one unit when their notes are
identical and non-empty, the earlier ends on the last body line of its
page, and the later begins on the first body line of the next. A hand-made
pair that meets the rule lists the same way.

NEVER modify or delete an annotation outside the described set: the
user's own highlights are indistinguishable by design, and there is no
rollback. ALWAYS list the annotations a delete would remove and get the
user's yes before running `revise --apply` with a `delete`
(`AGENTS.md` §5). If the described set is unclear, list the
candidates and ask. Report what was changed and what was left alone.

## Writing

Spec file, then dry run, then apply:

```json
{"annotations": [
  {"page": 318, "start": 26, "end": 58,
   "link": "<citing basename>",
   "body": "what this passage is doing, and why it is marked",
   "tag": "<subtopic>"},
  {"page": 318, "start": 446, "end_page": 319, "end": 20,
   "link": "<citing basename>",
   "body": "a sentence that runs over the page break",
   "tag": "<subtopic>"}
]}
```

```bash
~/.research-vault/venv/bin/python lib/annotate.py plan  "<pdf>" --spec spans.json
~/.research-vault/venv/bin/python lib/annotate.py apply "<pdf>" --spec spans.json --apply
```

- `plan` writes nothing and prints, per proposal, the exact text to be
  highlighted and the note. ALWAYS run `plan` and read its output before
  `apply` (`AGENTS.md` §5).
- `page` is the file page.
- `further` marks a joint highlight: a list of `[start, end]` word spans of
  `page`, written with the entry's own span as one highlight. An entry with
  `further` NEVER carries `end_page` or `rect`: the spec is rejected
  otherwise.
- `inline_tags` lists the tags that stand in `body` where `body` carries
  their name, in place of those words.
- `end_page` marks a cross-page span. The first segment runs from `start`
  to the last body line of `page`; the second segment runs from the first
  body line of `end_page`, after its running head and folio, to `end`. A
  body line is a line of the page that is not a running head, a folio
  line, a footnote, or a banner. `end_page` MUST be `page + 1`, and a
  cross-page entry NEVER carries `rect`: the spec is rejected otherwise.
  A cross-page span NEVER crosses a two-up gutter: the writer rejects it.
  If `start` or `end` lies outside its page's body lines, the writer skips
  the entry and names the segment that fell short. The writer writes two
  highlights, one per page, with one note, one tag, one colour, and one
  author; `plan` reports the pair as one line, `p318–319 [446:477 | 0:19]`,
  with the text joined across the break. If one segment merges into an
  existing highlight, the other is still written on its own page, and the
  line reads `MERGED+ADDED`.
- `tag` is optional, and `tags` MAY list further tags after it; the first is
  written to `/Subj`, and each as a
  `#[[Wikilink]]` token on the line directly after the note (not after a
  blank line — a blank line reads as a separate commentator). The note token
  is the channel that matters: `/Subj` does not survive into Zotero.
- `colour` is a Zotero palette name (`yellow`, `red`, `green`, `blue`,
  `purple`, `magenta`, `orange`, `gray`) or an `[r, g, b]` triple. PREFER
  the names OVER triples — they are Zotero's own hex values. Assign the
  colour the Colour table gives.

Revision is the same shape:

```json
{"changes": [{"page": 318, "index": 0, "colour": "green"},
             {"page": 284, "index": 1, "append": "a further note"},
             {"page": 173, "index": 0, "delete": true}]}
```

```bash
~/.research-vault/venv/bin/python lib/annotate.py revise "<pdf>" --spec changes.json
~/.research-vault/venv/bin/python lib/annotate.py revise "<pdf>" --spec changes.json --apply
```

Without `--apply` both forms are dry runs.

If `plan`, `apply`, `list`, or `revise` exits non-zero, stop and tell the user
its message.

A change addressed at either segment of a cross-page span applies to both
highlights: colour, note, append, delete. The dry run names both segments,
`p319 #0 + p318 #0 DELETE`. A highlight that is not the span's other
segment is never touched.

A rejected span is skipped and the others are written; `apply` names each
rejected span with its reason. Correct the rejected spans in the spec and
re-run `apply` on them alone: a written span re-run merges and never
stacks.

### Overlap and saving — invariants

- **Overlapping passes merge; they never stack.** A proposed span
  substantially overlapping an existing highlight appends its note to that
  highlight, keeping the existing author. The highlight keeps its extent
  where the span lies within it, and grows to cover the span's words where
  the span runs past it; it NEVER shrinks. Re-running a pass is safe: a
  note whose wikilink is present is not added twice.
- **The writer always saves incrementally**, leaving the existing object
  graph — including the Stage 0 outline — untouched. There is no
  non-incremental path, and there must not be: a full rewrite puts the
  outline at risk.

## The note

```
[[<basename>]] — <what the citing work says about this passage>
```

- No fixed format, no citation stamp: NEVER put `Author Year, p. N` in the
  note.
- Length follows the difficulty of the idea; NEVER pad, NEVER compress a
  hard idea into a fragment. Front-load the claim.
- Report the argument, never judge it (`AGENTS.md` §1); attribute
  every claim.
- The note MUST evoke the context and the argument: a reader meeting the
  highlight months later must know why it is marked.

## Every run ends with a report in chat

- The mode, and the anchoring strategy used.
- What was highlighted; what was merged into an existing highlight.
- Every miss, with its reason.

The user's confirmation is not required before `apply`; the `plan` run before
it is. Highlight, report, and the user prunes in their reader.

## Awkward material

| Material | Rule |
| --- | --- |
| Two-up spread scans | two printed pages per file page; a span MUST NOT cross the gutter — the writer rejects it. Read visually, then place word indices on the correct half. |
| PDFs with no usable text layer | no word boxes: read the pages as images and place a rectangle — `{"page": 3, "rect": [x0, y0, x1, y1], ...}`. In whole-work mode read every page visually; in trace mode read only the pages needed. |
