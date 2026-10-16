---
name: classify-and-place
description: "Stage 4 — when Stage 2 has written a corpus file's body and Stage 3 its citation links, read its opening and its neighbours in the citation graph, write its source_type, source_role, description, and field:, and add the work to each bibliography its field: names."
allowed-tools: Read, Write, Edit, Glob, Grep, Agent, Bash(~/.research-vault/venv/bin/python .claude/skills/classify-and-place/scripts/bibliographies.py:*)
---

# classify-and-place (Stage 4; the `work-classifier` worker judges)

**Precondition:** the corpus file carries a body, written by Stage 2, and
none of `source_type`, `source_role`, or `field:` has a value. `opening`
prints the three fields and exits 3 when any of them is set: Stage 4 has
already run on that corpus file.

**Postcondition:** the corpus file's frontmatter carries `source_type`,
`source_role`, and `field:`; every bibliography the `field:` names lists the
work; `check` reports no blocking group.

**Stage 4 runs once per corpus file, after Stage 3 on that corpus file and
before Stage 5.** Its two parts run in order: classify, then place.

**The citation graph is evidence, never the decision.** The work's
neighbours, as `graph.py neighbours "<basename>"` of the `cite-links` skill
lists them, show which bibliographies the works nearest it sit on. The
opening governs: a work whose opening settles its bibliographies is placed
there whatever its neighbours sit on. If the opening does not settle a
bibliography and the neighbours' tally names one, the neighbours and the
tally are evidence for the choice; if the two disagree, the disagreement is a
question for the user. A neighbour listing with no neighbours is no evidence.

**The orchestrator reads a corpus file's opening, never a whole work.** The
opening is what `opening` prints: the corpus file's headings and the text of
its prefatory sections — preface, foreword, introduction, or their
equivalents in German, French, Italian, Spanish, and Latin — or, when no
prefatory section holds text, the text of its sections from the first that
holds text, in order, cut at 4,000 words. NEVER open the PDF to
classify or place a work, and NEVER read the corpus file whole; if the
opening does not settle a decision, stop and ask the user.

## 1. Classify

1. Read the opening:

       ~/.research-vault/venv/bin/python .claude/skills/classify-and-place/scripts/bibliographies.py opening "<basename>"

   Its first lines are the basename and the current `source_type`,
   `source_role`, and `field`.

   | Exit | Means | Do |
   | --- | --- | --- |
   | 0 | the corpus file is unclassified | continue to step 2 |
   | 2 | the corpus file does not exist | run Stage 1 first |
   | 3 | one of the three fields already has a value | stop and ask the user; re-run with `--reclassify` only on their instruction |
   | any other value | unspecified | stop and ask the user |
2. Write `source_type` from the vocabulary below.
3. Write `source_role` from the vocabulary below.
4. If the work is a commentary, write `commentary_on: "[[<basename>]]"`
   naming the one primary work it runs through. The target MAY have no
   corpus file yet.
5. If the opening does not settle a value, stop and ask the user.
6. Write `description`: one or two sentences, in the orchestrator's words,
   of what the work says it does, ending with the folio the opening carries
   for it as `(<Author> <Year>, p. <N>)`; Stage 5 copies it whole onto each
   bibliography as the work's gloss. NEVER quote the work in it, and NEVER
   evaluate the work.
7. Write the fields into the corpus file's frontmatter with the Edit tool,
   changing no other line: the body below the frontmatter is Stage 2's and
   Stage 3's and is never edited by hand.

`source_type` and `source_role` take their values from these vocabularies.

| `source_type` | Is |
| --- | --- |
| `article` | a journal article, or a chapter filed as a book section |
| `monograph` | a book making one sustained argument |
| `historical` | a primary text in translation or in a critical edition |
| `textbook` | a textbook, handbook, companion, encyclopedia, or dictionary |
| `transcript` | a transcript, a note of `research vault/corpus/talk transcripts/`; a transcript takes `transcript` and no other value, and a corpus file never takes it |

| `source_role` | Is |
| --- | --- |
| `primary` | the text being commented on |
| `secondary` | interpretation or criticism of a primary text; if it runs through one primary work in that work's own order, it is a commentary and carries `commentary_on: "[[<basename>]]"` |
| `reference` | consulted for a fact or a definition, never argued with |

**A commentary is secondary literature that runs through one primary work in
that work's own order.** The test is form, never extent: a work carrying
`commentary_on:` is roled `secondary`, and `check` blocks on any other role.

**The classification is a judgment: the `work-classifier` worker's in the
ingest workflow and for a transcript, the orchestrator's by hand.** NEVER derive it by script, and
NEVER copy it from a filename or the Zotero record's `itemType`.

**Stage 4 runs on a transcript as on a corpus file.** `opening` finds a
transcript by its basename; its opening is the transcript's headings and
the text of its sections from the first, cut at 4,000 words. The `transcribe-talks` skill runs Stage 4 on each transcript
it files.

## 2. Place

**Membership is a judgment, and is NEVER mechanical.** NEVER derive `field:`
by matching bibliography names against a work's prose: a work that names a
subject in order to disclaim it matches exactly as one that argues for it.

**The reshaping creates and reshapes bibliographies, and nothing else
does.** The reshaping is the tail step of a batch in which the bibliography
shaper reads the citation graph's clusters and findings, the authors of five
or more works without a bibliography, the open nominations, the author maps,
the works on routing bibliographies, and the fold candidates, and `reshape`
carries out its answers: a creation, a bibliography under its parent's
`## Maps` with the works that gather on it; a move, a work from one
bibliography to another; an added placement, a work placed on one more
bibliography; a link, a bibliography added to one more parent's `## Maps`;
an unlink, a bibliography taken out of one parent's `## Maps`; or a fold, a
bibliography merged as a `###` group into the bibliography whose subject
holds its own. `reshape` also removes every stray placement, with no answer
naming it. A fold also rewrites the `field:` of each atomic note and
project file that names the folded bibliography, naming the target in its
place, and changes nothing else in it: the folded file is deleted, and a
`field:` naming it would name nothing. The user reads each creation, move, added placement, link,
unlink, and fold in the batch's one report, and reverses or changes it by
instruction. NEVER create, link, unlink, or fold a bibliography by hand.

**A bibliography gathers five works.** NEVER create a bibliography for fewer
than five works on it, on the creations beneath it, and on the
bibliographies linked beneath it: a bibliography of two or three works says
less than a `###` group on the bibliography above it. A subject of its own
that fewer than five works share is a `###` group on the most specific
bibliography whose subject holds it, and the reshaping folds a bibliography
that gathers fewer than five works into that bibliography.

**One subject, one bibliography.** A bibliography's subject is a discipline,
a period, a school, a thinker's or a scholar's body of work, a subject the
works name as their own (a problem, a doctrine, a work, a theory), or the
relation of two subjects. A narrower debate is a stretch of one subject: the
responses to it, its history, an approach to it, an aspect of it, a thesis
about it, or the subject in one field. A narrower debate is a `###` group on
the subject's bibliography, NEVER a bibliography of its own: NEVER create or
nominate one, and the reshaping folds an existing one into the subject's
bibliography.

**A primary work sits on its author's bibliography alone.** An author-only
work is a work roled `primary` one of whose creators carries an author
bibliography. An author-only work sits on its creators' author
bibliographies and on no other bibliography: a bibliography on a part of a
thinker's work, or on the thinker's relation to another subject, lists what
others wrote on it, NEVER the thinker's own works. A stray placement is an
author-only work's placement on any other bibliography; the reshaping
removes it. A stretch of one author's own writings, a period of the
authorship or a kind of writing, is a `###` group under `## Primary works` on
the author's bibliography, NEVER a bibliography of its own.

**The existing bibliographies are a guide to the tree's shape, never the
whole of it.** A nomination and a creation MAY name a root, a thinker, a
school, a subject, or a comparison bibliography the tree lacks, at any depth,
in the kinds of the table below; a root is a discipline or a period, NEVER an
author. A nomination and a creation name a subject distinct from every
existing bibliography's, NEVER a narrower debate of one.

1. Read the name and the `## Maps` listing of every bibliography (every
   note under `research vault/bibliographies/`, its subfolders included).
2. Choose every bibliography the work belongs to by descent: from each root
   whose subject holds a subject of the work, descend into every bibliography
   in `## Maps` whose subject holds one, and stop on a line of descent where
   none does. At each bibliography where a line of descent stopped, apply
   the relation test below.
3. If the relation test calls for a nomination, write it: the bibliography
   the work would sit on, its name, its kind, and its parent, which is a
   bibliography, a bibliography the tree lacks, or none for a new root. Write
   into `field:` the bibliographies the relation test names meanwhile, or
   nothing if no line of descent reached a bibliography. `drive-classify`
   records the nomination, with the bibliographies the work sits on
   meanwhile, for the reshaping, which looks for the other works that share
   its subject, creates the bibliography once five works share it, and moves
   the works there. A nomination stays open across batches until a
   reshaping moves its work. A work on no bibliography meanwhile is what
   `check` reports as unplaced, a backlog entry and not an error.
4. Write the chosen bibliographies into the corpus file's `field:` as
   wikilinks. If the work is an author-only work, write nothing into
   `field:` and no nomination: `drive-classify` writes the author
   bibliographies of its creators and nothing else. Otherwise
   `drive-classify` adds the author bibliography of every creator of the
   work, and drops from `field:` every bibliography that is an ancestor of
   another bibliography there. The author bibliographies of the work's
   creators stand outside this rule: none is dropped, and none makes a
   bibliography above it an ancestor to drop.
5. If a bibliography was created in this step, name to the user every placed
   work that now fits it, and change a placed work's `field:` only on the
   user's instruction: a corpus file is written once.
6. If the user instructs a change to a placed work's `source_role` or
   `field:`, run `place` again, then `check`: `place` adds the new listing,
   and `check` names the stale one, which is removed by hand.

| Rule | Is |
| --- | --- |
| most specific | a work sits on the most specific bibliography it belongs to, the one farthest from the root along a line of descent whose subject holds the work's subject, never also on an ancestor of it |
| plurality | a work MAY sit on several bibliographies, one per line of descent |
| catalogue | every work an author wrote sits on the author's bibliography, where §3 sorts it into `## Primary works`: the author bibliography is a catalogue, never a narrower subject. A work roled `secondary` sits there and on the bibliographies the relation test names, above or beneath it; an author-only work sits there alone |
| author | a bibliography carrying `author:` lists a work by another author by the relation test, as any bibliography does; §3 sorts it into `## Secondary literature` |

A line of descent is a chain of bibliographies, each listing the next under
`## Maps`. A routing bibliography is one whose `## Maps` lists a
bibliography other than a scholar's author bibliography, one no period
lists; its own list of works holds the works on the whole of its subject
and on its narrower debates. `check` reports a violation of the most-specific rule, other
than the catalogue rule's placement, as blocking, and a work on a routing
bibliography as advisory; it corrects neither. A work's `source_role` NEVER
bars it from a bibliography.

**A work stands in one of four relations to a bibliography's subject.**

| The work treats | Is | Sits |
| --- | --- | --- |
| the whole | the bibliography's subject in its full scope: a history, survey, introduction, companion, textbook, or bibliography of it; a reading of the whole of a thinker's work or of a whole movement; a primary work that spans its author's whole system | on the bibliography |
| a narrower debate | one stretch of the bibliography's subject: the responses to it, its history, an approach to it, an aspect of it, a thesis about it, or the subject in one field | on the bibliography, which Stage 5 groups by the debate; NEVER a nomination |
| a part | one work, doctrine, problem, period, or school within the bibliography's subject, a subject of its own | on the bibliography beneath that holds the part; if none does, on this bibliography, which Stage 5 groups by the part, with a nomination for the part |
| a relation | the bibliography's subject set beside another subject | on the comparison bibliography of the two subjects; if none exists, on the most specific bibliography of each subject, which Stage 5 groups by the relation, with a nomination for the comparison bibliography |

**A comparison bibliography is a bibliography on the relation between two
subjects, listed beneath the most specific bibliography of each.**

**An author of five or more works in the library gets an author
bibliography at the next reshaping.** The count is of the works one person
wrote, whatever their place in a work's creator list, read from the `author:`
of every corpus file. Where a surname covers more than one person, each
person is counted alone, and a surname no one person reaches five with gets
no bibliography. NEVER gather the works of two persons on one author
bibliography, and NEVER ask the user whether to: if the descriptions do not
settle which person wrote a work, the work counts for no person, and the
shaper writes nothing for it. `check` names every author the count has
reached whom no bibliography carries as its `author:`; the reshaping's
listing carries the same authors with their works.

**A bibliography's file sits in the subfolder of its kind, and NEVER in
`research vault/bibliographies/` itself.** Three folders hold the three
kinds, numbered so that they display in that order and not alphabetically:

| Folder | Holds |
| --- | --- |
| `1 historical periods/` | a bibliography naming a period or a movement in the history of philosophy |
| `2 authors/` | a bibliography carrying `author:` |
| `3 topics/` | a bibliography naming a subject or a discipline |

A subfolder NEVER enters a wikilink or a `field:`, which name a bibliography
by its basename alone: Obsidian resolves a wikilink by basename, and a path
in one resolves to nothing. NEVER give two bibliographies one basename, in one folder or in two:
a wikilink names only one, and `check` blocks on the pair. The subfolders
NEVER stand for the tree, which the `## Maps` listings alone carry: a root
sits in the folder of its kind like any other bibliography, and `3 topics/`
holds a discipline whether or not a bibliography lists it.

**A bibliography of more than twelve works whose works fall in two or more
clusters is split at the next reshaping:** the shaper creates one
bibliography per part of five or more works that share a subject of its own,
under the split bibliography, and moves the part's works to it. A part of
fewer than five works, and a part whose works share a narrower debate, stays
on the bibliography, as the group Stage 5 gives it.

**A bibliography's frontmatter is written by the user, or by the orchestrator
on the user's approval.** Two keys are read:

| Key | Is | Read by |
| --- | --- | --- |
| `aliases` | further phrases that name this bibliography | the work classifier or the orchestrator, placing a work |
| `author` | a surname, marking the bibliography as an author's own body of work | `place`, choosing the list of works |

**An author is a thinker or a scholar.** A thinker is an author whose works
the library holds as the texts a period or a discipline studies. A scholar is
an author whose works interpret a thinker or a subject.

| Bibliography | Is | Sits beneath | `kind` |
| --- | --- | --- | --- |
| root | an academic discipline, or a movement or period in the history of philosophy | nothing | `topic` for a discipline, `period` for a period |
| thinker | a thinker's author bibliography | each period the thinker belongs to, or the school within it | `author` |
| school | a school or narrower movement within a period | the period | `period` |
| subject | a subject of its own within a discipline, a period, a thinker's work, or another subject, which five or more works share, never a narrower debate of one and never a stretch of one author's own writings | each bibliography whose subject holds it; a part of a thinker's work also beneath the discipline its subject falls within | `topic` |
| comparison | the relation between two subjects, which five or more works treat | the most specific bibliography of each | `topic` |
| scholar | a scholar's author bibliography | each bibliography whose subject the scholar's works treat | `author` |

A bibliography MAY sit at any depth, and sits beneath the most specific
bibliography whose subject holds it. A period lists its thinkers, its
schools, and its subjects, NEVER a scholar. A bibliography's subject is named
as the works share it, NEVER as one work's thesis.

**The bibliographies are written in the bodies, and nowhere else.** A
bibliography lists the bibliographies one level beneath it under `## Maps`,
as a wikilink one to a line. NEVER write a `parent:` key, and NEVER read the
shape from the folders: `## Maps` is the one record of it. A bibliography
MAY sit beneath several parents; none lists itself through any chain, and
`check` blocks on a cycle. Nothing writes the inverse of a `## Maps` listing:
the bibliography beneath names nothing above it.

## 3. Add the work

Run the read-only form and read its output, then the writing form:

    ~/.research-vault/venv/bin/python .claude/skills/classify-and-place/scripts/bibliographies.py place "<basename>"
    ~/.research-vault/venv/bin/python .claude/skills/classify-and-place/scripts/bibliographies.py place "<basename>" --apply

`place` adds the line `- [[<basename>]]` to each bibliography the corpus
file's `field:` names, in its list of works, and changes nothing else: after
creation a bibliography changes only in its list of works, its glosses, its
introduction, and its group notes. The line goes before the first listed work later than the
new one, by `orig_year`, else `year`, else the basename's year, then by
basename; a list of works reads in the order the works were written. If the
list of works carries `###` groups, the line goes into the group
`### Unsorted`, added last if absent, until Stage 5 sorts the work into a
group.

**A work's group on a bibliography is recorded in the bibliography alone,**
as the `###` group its listing sits in; NEVER record it in `field:` or in
any other frontmatter field. `place` writes a new listing into
`### Unsorted`, Stage 5 sorts it into the group the bibliography introducer
names, and a fold writes each folded work into the group its answer names.

**A listing is a list item whose first wikilink names the work:**
`- [[<basename>]]`, with or without a gloss after it. A `###` heading, and a
line of prose, is never a listing, whatever wikilinks it carries, so an
introduction or a group note MAY link a bibliography.

| Bibliography | List of works |
| --- | --- |
| any, for a work whose `source_type` is `transcript` | `## Talk transcripts` |
| carries `author:` | `## Primary works` if the bibliography's `author:` is one of the work's creators, otherwise `## Secondary literature` |
| no `author:` | `## Primary works` for a work whose `source_role` is `primary`, otherwise `## Secondary literature` |

If the work is listed under another list of works of the same bibliography,
`place` moves the listing to the list the table names.

If the named section is absent, `place` adds it as the bibliography's last
`##` section. If `place` exits 4, a bibliography carries its list of works
twice: stop and ask the user to merge the two lists by hand. If `place`
exits 2, a bibliography named in `field:` has no file: stop and ask the user. If `place` exits with any other non-zero value,
stop and ask the user.

Nothing writes the inverse of `commentary_on:`. `check` reports a
`commentary_on:` whose target has no corpus file.

## The annotated bibliography

**An annotated bibliography is a bibliography carrying glosses, an
introduction, and group notes.** Stage 5 writes all three; the
`gloss-bibliographies` skill states how.

| Part | Is | Sits |
| --- | --- | --- |
| gloss | the listed work's `description:`, copied whole: what the work says it does, with its folio | after the work's wikilink, on the same line: `- [[<basename>]] — <gloss>` |
| introduction | one to three sentences, in the orchestrator's words, on what the bibliography is about and what its listed works share | the paragraph before the first `##` section |
| group note | one or two sentences, in the orchestrator's words, on what the works of one `###` group share | the paragraph beneath the group's heading, before its first listing |

**The introduction and a group note speak of the listed works together.**
NEVER state in either what one work argues, NEVER name a listed work in
either, and NEVER cite a folio in either: each listing's gloss carries its
own work's claim and folio. NEVER quote a work in either, and NEVER evaluate
one.

**The body reads in one order, whatever the bibliography's kind:** the
introduction; `## Maps`, each map listed bare; then each list of works the
bibliography carries, its listings in the order `place` keeps, under the
`###` groups a fold or Stage 5 opened.

A listing whose work carries no `description:` reads as `place` wrote it.

## `check` (read-only)

```bash
~/.research-vault/venv/bin/python .claude/skills/classify-and-place/scripts/bibliographies.py check
```

Reports, grouped by concern, and exits non-zero if a blocking group is
non-empty. An advisory group prints and never fails the gate.

| Group | Reports | Force |
| --- | --- | --- |
| Conflict copies | a sync conflict copy beside a corpus file or a bibliography; merge it by hand and delete it | blocking |
| Bibliographies | two bibliographies carrying one basename; a `## Maps` listing naming no bibliography; a bibliography beneath itself | blocking |
| Placement | a `field:` naming no bibliography, or naming a bibliography and its ancestor, unless either is the author bibliography of one of the work's creators | blocking |
| Listings | a bibliography listing a work whose corpus file's `field:` does not name it, or listing a work under both sections of an author bibliography; a bibliography carrying one list-of-works heading twice | blocking |
| Classification | a `source_type` or `source_role` outside its vocabulary; `commentary_on:` on a work not roled `secondary`; a transcript whose `source_type` is not `transcript`, or a corpus file whose `source_type` is `transcript` | blocking |
| Authors — five or more works and no author bibliography | an author of five or more works in the library whom no bibliography carries as its `author:`; the reshaping creates one | advisory |
| Authors — an author bibliography outside `2 authors/` | a bibliography carrying `author:` whose file sits in another folder | advisory |
| Backlog — unclassified | corpus files with no `source_type` or `source_role` yet | advisory |
| Reissues — a primary or historical work with no `orig_year` | a work roled `primary`, or typed `historical`, whose frontmatter carries no `orig_year`: the held edition MAY be a reissue, and the bibliographies order its author's works by `orig_year`; set it through Stage 1's `note` if the held edition is not the first | advisory |
| Backlog — unplaced | corpus files with no `field:` yet | advisory |
| Catalogue — an author's work missing from the author's bibliography | a work whose creator carries an author bibliography the work does not sit on; the reshaping adds it | advisory |
| Catalogue — a primary work off its author's bibliography | a stray placement: an author-only work on a bibliography other than its creators' author bibliographies; the reshaping removes it | advisory |
| Routing — a work on a routing bibliography | a work on a routing bibliography other than its author's own; the reshaping moves it, or leaves a work on the whole of the bibliography's subject or on a narrower debate of it | advisory |
| Commentaries — targets with no corpus file yet | `commentary_on:` naming a work with no corpus file | advisory |
| Writing — an atomic note or project file placed off the bibliographies | an atomic note's or a project file's `field:` naming no bibliography, or naming a bibliography and its ancestor; the `manage-projects` skill's `classify` corrects it on the user's instruction | advisory |

If `check` exits non-zero, fix the frontmatter it names and re-run it. If a
finding cannot be settled from the opening, stop and ask the user. Outside a
batch, run `check` after the last corpus file is placed, and before Stage 5.
In a batch, `ingest.py drive-check` runs `check --json` once, beside the citation sweep,
and each blocking group becomes a question in the batch's one report. An
advisory group NEVER becomes one.

## `tree` (read-only)

```bash
~/.research-vault/venv/bin/python .claude/skills/classify-and-place/scripts/bibliographies.py tree
```

Prints every bibliography as JSON: its `name`, its `folder`, its `author`,
its `aliases`, and `maps`, the bibliographies its `## Maps` lists.

## The ingest workflow

**The `ingest` workflow classifies and places each work of a batch through
the `work-classifier` worker and one `drive-classify` call, which carries no
judgment.** The worker instructions carry every rule of sections 1 and 2 the
worker obeys. The answers file lives in the work's batch work directory,
`ingest/<basename>/classify-answers.json` in the scratch directory, reached
as `ingest/by-key/<key>/classify-answers.json`. `<key>` is the work key the
`ingest` skill states; outside a batch, it is the basename.

| Step | Runs | `state` and next step |
| --- | --- | --- |
| `drive-classify <key>` | discards the work's answers file from an earlier run | `classify`, with `answers`: dispatch the `work-classifier` worker, naming the work file and `answers` |
| `work-classifier` dispatch | section 1 and section 2's choice: the worker reads `opening`, `tree`, and `graph.py neighbours`, and writes `source_type`, `source_role`, `commentary_on`, `description`, `field`, `nomination`, `questions`, and `notes` to the answers file: a question for a value the opening leaves open, a note for a caveat on a settled value | run `drive-classify` with `--answers` |
| `drive-classify <key> --answers "<answers file>"` | checks the answers, writes `source_type`, `source_role`, `field:`, `commentary_on:`, and `description:` into the frontmatter in place, changing no other line, then section 3: `place --json` and its `--apply` | `placed`, with the bibliographies changed and the answers' `notes`, which the batch's report carries on the work: Stage 4 is done for the work. `aside`: a question in the answers, a value outside its vocabulary, a bibliography that does not exist, a classification already written otherwise, or a `place` refusal. Answers with no bibliography and no question classify the work and place it nowhere: `placed`, with no bibliography. `unwritten`: the worker wrote no answers file; dispatch it again once, then run this step again; a second `unwritten` sets the PDF aside. `halt`: a conflict copy among the bibliographies |

**`drive-classify` leaves the frontmatter as it found it when it prints
`aside`.** If `place` refuses after the classification was written, it
restores the frontmatter, so a later batch lists the work at Stage 3 again,
which runs Stage 4 after it.
If a written classification equals the answers, it places the work again;
`place` adds only a missing listing.

**`drive-classify` runs one work at a time across the batch:** two works
placed on one bibliography at once lose a listing.

**`drive-classify` NEVER creates a bibliography.** A `nomination` in the
answers is recorded in `ingest/nominations.json` in the scratch directory,
with the work's basename, for the reshaping; a bibliography the answers name
in `field` that does not exist sets the work aside.

## The reshaping

**The reshaping runs once per batch, in the tail, after the bibliographies
check and the citation sweep and before Stage 5; the bibliography shaper
judges, and `reshape` writes.** Every command is `~/.research-vault/venv/bin/python .claude/skills/classify-and-place/scripts/bibliographies.py <subcommand>`.

| Command | Does | Writes |
| --- | --- | --- |
| `shape-listing [--nominations <file>] [--out <path>] [--parts <dir>]` | the shaper's listing: the tree, `graph.py clusters`' clusters and its `new`, `split`, and `misfit` findings, the authors of five or more works without a bibliography with their works, each nomination whose work still sits on the bibliographies it sat on when nominated, each author bibliography with its parents, its author's own works beneath it, and its count of works by others beneath it, each topic bibliography that only author bibliographies list, `routing_placements`, each work on a routing bibliography other than its author's own with the bibliography's maps and the work's nearest neighbours, `co_placed`, each pair of bibliographies on no common line of descent and with no map in common that share two or more works, `catalogue_gaps`, each work missing from an author bibliography of its creators, `stray_placements`, each author-only work with the bibliographies it sits `on` beside its creators' author bibliographies, `fold_candidates`, each pair of bibliographies whose `narrower` name holds every word of the `broader` name (`by` `name`), or names the head noun, the last word, of the `broader` bibliography that lists it (`by` `head`), neither an author bibliography, or whose `narrower` one, no author bibliography, gathers fewer than five works on it and beneath it, stray placements uncounted, and is listed by the `broader` one (`by` `size`, which a pair found both ways carries), with the narrower one's `works` and the works the two share, and a description of every work they name: its title, author, `source_role`, `description`, and bibliographies. The `missing` finding is Discover's, and the listing leaves it out. With `--parts`, cuts the listing into its parts and prints `parts`, their count, in place of the listing | the listing file, with `--out`; each part, `<dir>/<n>/listing.json`, with `--parts`, in place of the parts and the answers files `<dir>` held |
| `merge-answers --parts <dir> --out <file>` | merges the answers files the shaper wrote for the parts, `<dir>/<n>/answers.json`, into one: an answer two parts give alike stands once; the creations of one name are one creation, with the kind, parent, and author of the first and the works of each; a work's moves from one bibliography to two bibliographies are both dropped; a fold of one bibliography into two, and a fold of a bibliography another answer names, is dropped. Each dropped answer, each creation two parts shaped differently, and each part without an answers file is a question of the merged answers. Prints `parts` and `answered`, the counts of the parts and of the parts with an answers file | the merged answers file |
| `reshape --answers <file>` | checks the shaper's answers: each creation's name is new, its kind `author`, `period`, or `topic`, an author bibliography carries `author`, its parent is a bibliography, a creation in the same answers, or none for a root of kind `topic` or `period`, it sets no bibliography beneath itself, and five or more works with corpus files gather on it, on the creations beneath it, and on the bibliographies linked beneath it; each move names a work with a corpus file and a bibliography, and a source other than the author bibliography of one of the work's creators; each added placement names a work with a corpus file and a bibliography on no line of descent with one the work sits on, its author's own excepted; no creation, move, or added placement sets an author-only work on a bibliography other than its creators' author bibliographies; each link names two bibliographies or creations and sets neither beneath itself; each unlink's parent lists its bibliography, and leaves no author bibliography without a parent; each fold names two bibliographies, the folded one carrying neither `author:` nor `aliases`, the target neither the folded one nor beneath it nor folded itself, a group carrying no `#`, `[`, `]`, or `|`, and a folded bibliography no other answer names; prints the creations, the moves, each stray placement among them as a move to the work's author bibliography, the added placements, the links, the unlinks, the folds with their works and the atomic notes and project files whose `field:` they rewrite, under `writing`, the bibliographies touched, and the works moved, or exits 5 with the refusal | nothing |
| `reshape --answers <file> --apply` | the same check, then: each creation's file in the folder of its kind, with `author:` for an author bibliography and its empty lists of works, and the line `- [[<name>]]` in its parent's `## Maps` unless it is a root; each link's line `- [[<name>]]` in its parent's `## Maps`, and each work on or beneath the linked bibliography taken off every bibliography of its `field:` the link made an ancestor of another; each unlink's line removed from its parent's `## Maps`; each creation's works' `field:` with the creation in place of every ancestor of it the work sat on; each move's work's `field:` with the target in place of the source, its listing removed from the source, and `place` on it; each stray placement on a bibliography no fold names removed, from the work's `field:` and from the bibliography's list of works; each added placement's work's `field:` with the target beside the rest, and `place` on it; each fold's works, every work whose `field:` names the folded bibliography, each listed on the target with the gloss it carried, in the list `place` names, under the `###` group the answer names, a work the target already lists keeping that listing and joining the group if it sat in none or in `### Unsorted`, and its `field:` with the target in place of the folded one; a folded author-only work whose creator the target does not carry left on its creators' author bibliographies alone; each map of the folded bibliography linked beneath the target; the folded bibliography taken out of every `## Maps`, and its file deleted; then each folded work taken off every bibliography of its `field:` that has become an ancestor of another. No step takes a work off the author bibliography of one of its creators | the bibliographies, the corpus files' `field:`, and the deletion of each folded file |

**A listing larger than one dispatch reads is cut into parts.** The part
budget is 240,000 bytes of a part's JSON on one line. If the listing keeps
within the part budget, the listing is its one part. Otherwise each part
carries the whole `tree`, a run of the entries of the listing's other keys,
the `descriptions` and the `stray_placements` of the works those entries
name, and every other key, `clusters.clusters` among them, empty.

| Rule | Holds |
| --- | --- |
| Order | the parts take the entries key by key: `clusters.findings.new`, `clusters.findings.split`, `authors`, `author_maps`, `unlinked_subtopics`, `co_placed`, `catalogue_gaps`, `fold_candidates`, `nominations`, `clusters.findings.misfit`, `routing_placements`; within a key, in the listing's order |
| One key, one part | a key's entries that one part holds whole are never cut across two parts |
| Nominations | the listing orders `nominations` by `parent`, then by `name`: the nominations that name one subject fall together |
| A large entry | an entry larger than the part budget is a part of its own |

**Dispatch one bibliography shaper per part, each with its part's listing
and an answers file of its own; then run `merge-answers`, and `reshape` once,
on the merged answers file.** NEVER run `reshape` on one part's answers file:
the parts' answers conflict until they are merged.

| Step | Runs | `state` and next step |
| --- | --- | --- |
| `ingest.py drive-clusters` | `shape-listing` with the open nominations, into `ingest/reshape/listing.json`, and its parts into `ingest/reshape/parts/`; deletes the outcome file and the merged answers file of the reshaping before | `shape`, with `dir`, the parts' directory, `parts`, their `count` and the names of each part's `listing` and `answers` under `dir`, and `outcome`, the path the reshaping records its outcome at: dispatch one bibliography shaper per part, all at once, each with its part's two paths, then `drive-merge`. `nothing`: no finding, no author, no nomination, no topic bibliography that only author bibliographies list, no routing placement, no co-placement, no catalogue gap, no stray placement, and no fold candidate. `halt`: the listing failed |
| `bibliography-shaper` dispatch, one per part | writes the part's answers file: `create`, `move`, `add`, `link`, `unlink`, `fold`, and `questions` | `drive-merge`, once every dispatch has returned |
| `ingest.py drive-merge` | `merge-answers` over `ingest/reshape/parts/`, into `ingest/reshape/answers.json` | `merged`, with `answers`, the merged answers file: `drive-reshape <answers>`, under the bibliographies lock. `aside`: no part has an answers file, or the merge failed; the bibliographies are not reshaped, and the question goes into the batch's one report |
| `ingest.py drive-reshape <answers>` | `reshape --answers --apply`; records the bibliographies touched and the works moved or added in `ingest/reshape/touched.json`, which `drive-gloss-plan` reads, and its line, unspilled, in the outcome file | `reshaped`, with `created`, `moved`, `added`, `linked`, `unlinked`, `folded`, and the shaper's `questions`: carry the seven into the batch's one report. `aside`: no answers file, or refused answers, with the refusal |

The shaper's worker instructions carry every rule of the decisions: a
creation needs five works that share a subject the descriptions name, a move
or an added placement needs the work's description to fit the more specific
bibliography, a fold needs the folded bibliography to gather fewer than five
works, or its subject to be a narrower debate of the target's or a stretch
of the target author's own writings, and a decision the descriptions do not
settle is a question.

**A fold deletes the folded bibliography without asking the user.** The
tools wrote the folded file, `reshape` creating it and Stage 5 rewriting it,
and the batch's one report names every fold, which the user reverses by
instruction. A bibliography carrying `aliases` carries frontmatter the user
wrote: `reshape` refuses to fold it, and the shaper writes a question
instead.
