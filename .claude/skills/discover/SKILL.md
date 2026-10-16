---
name: discover
description: "Discover — on a research question, build a reading list from what the held works cite and from a literature search outside the vault, and deliver it as a document through SendUserFile."
allowed-tools: Read, Glob, Grep, Write, Agent, SendUserFile, WebSearch, Bash(~/.research-vault/venv/bin/python .claude/skills/discover/scripts/discover.py:*), mcp__vault-rag__search_hybrid, mcp__vault-rag__get_frontmatter, mcp__vault-rag__list_works, mcp__vault-rag__index_status, Bash(~/.research-vault/venv/bin/python lib/vault.py:*)
---

# discover (Discover, run by the orchestrator; scouts for the searches; a grader before delivery)

**Discover reads the held works' citations, then runs a parallel literature
search.** It takes the research question and the held works on it, reads
their reference lists for the works they cite that the library lacks, and
looks those works up outside the vault. It harvests from the held works the
term list, the vocabulary of the debate, combines the terms into queries, and
runs every query concurrently through scouts, one per query cluster. The
reading list it delivers is built under the rules of `AGENTS.md` §1: every
comment reports and never evaluates, the list lives outside the vault, and
nothing is claimed that no page showed.

## Vocabulary

| Term | Is |
| --- | --- |
| seed work | a held work the vault search, or the corpus read, names as bearing on the question |
| outer ring | the works `list_works` returns for the bibliographies a seed work's `field:` names |
| citing set | the seed works plus the outer ring: the held works whose reference lists `unheld` reads |
| shortlist | the entries `unheld --min-citing <N>` prints over the citing set |
| known item | a shortlist entry the orchestrator chooses because the work it names bears on the question |
| known-item query | one query naming one known item: its first author's surname, then its main title in quotation marks |
| term list | the concepts, technical terms, position labels, and names harvested from the seed works and the shortlist |
| query cluster | the queries assigned to one scout, grouped by source |
| scout | the `literature-scout` worker, one dispatch per query cluster |
| candidate | a work a scout saw a page for, returned in the scout's JSON shape |
| sighting | the page a candidate was seen at: a record page or a search listing |
| obtain link | the one link an entry carries to where the work is obtained: `publisher`, `open copy`, or `internet archive` |
| grader | the `reading-list-grader` worker, one dispatch per reading list |
| reading list | the delivered document |
| neighbouring subject | a subject the question's subject draws on, applies, or runs parallel to, or one of two subjects the question relates, taken without the other |
| left-out work | a search hit, a shortlist entry, or a candidate that "Scope" keeps off the reading list |
| discover task | `- [ ] #discover · Discover “<Subject>”: <how the subject bears on the question>`, a line naming one neighbouring subject to run Discover on |

## Scope

**A reading list holds only the works that bear on the question.** A work
bears on the question if it is wholly on the question's subject, or if it
holds a passage, a chapter, a section, or a note, that discusses the
question's subject. If the question relates two subjects, the passage
discusses the two together. A work on a neighbouring subject that holds no
such passage does not bear on the question: NEVER choose it as a seed work or
a known item, compose a query from its terms alone, or list it.

**The question sets the length of the reading list.** A narrow question
yields a short reading list, and a broad one a long reading list. NEVER list
a work to lengthen the reading list, and NEVER list a work for what it shares
with the question's subject short of a passage on it.

**A neighbouring subject is a discover task, never a listing.** The user asks
for a neighbouring subject by choosing its discover task or naming it, and
that request is a question of its own.

## Discover tasks

**A discover task names one neighbouring subject the left-out works share.**
The task reads `- [ ] #discover · Discover “<Subject>”: <clause>`: the subject as a
title of at most eight words, then one clause stating how the subject bears
on the question, as the left-out works state it. The clause reports and
NEVER evaluates.

1. Write one discover task for each neighbouring subject at least two
   left-out works share, at most five, the subject the most left-out works
   share first. NEVER write a discover task for a subject no left-out work
   names. A reading list MAY carry no discover task.
2. If `research vault/bibliographies/4 reading lists/` holds a reading list
   whose name or `question:` names the subject, write no discover task for
   it.

**The user chooses a discover task by checking it, `- [x]`, or by naming it
in chat.** NEVER run Discover on a discover task the user has not chosen.
To resolve a chosen discover task:

1. Run "Procedure" with the task's subject as the question.
2. Delete the task's line from the reading list or the project reading list
   it stands in.
3. Keep the new reading list per step 9.

## Parts

| Part | Is | Run by |
| --- | --- | --- |
| `scripts/discover.py unheld <basename>... [--min-citing <N>]` | the entry-list entries and footnotes of the named held works that name no held work, deduplicated across works and across the editions of one work, each with the year of every edition it is cited in, its citing works and the folio and file page of each citing entry, ordered by the count of citing works, `cited_by_count`; two citing works that print one reference list in common, at least 5 entries in the same words, count once, and the later one's `cited_by` item names the earlier in `same_list_as`; with `--min-citing`, only the entries whose count is at least N | the orchestrator, inline |
| `scripts/discover.py merge --unheld <path> [--known <path>]` | the scouts' reports from stdin, deduplicated, each candidate marked held or unheld, with its local citation count attached, counted as `unheld` counts it, ordered by impact; a candidate with no sighting URL is dropped here; `known_unseen` lists the known items no candidate names | the orchestrator, inline |
| `.claude/agents/literature-scout.md` | one source, one query cluster, its report written to the session scratchpad | scouts, concurrently |
| `.claude/agents/reading-list-grader.md` | the rubric over the written reading list | the grader |

The script writes nothing and never calls the network. Every command is
`~/.research-vault/venv/bin/python .claude/skills/discover/scripts/discover.py <command>`.

## The sources

| Source | Reached by the scout through | Gives | Lacks |
| --- | --- | --- | --- |
| PhilPapers | `WebSearch` on `site:philpapers.org` | record URL, title, authors, snippet | citation counts; the record page cannot be opened |
| PhilArchive | `WebSearch` on `site:philarchive.org` | the open copy's URL, title, authors | citation counts |
| Google Scholar | the browser tools | titles, `Cited by` counts, publisher links | stable ordering |
| Internet Archive | `WebFetch` on its search | scanned books | recent works |
| publisher catalogues and authors' pages | `WebSearch`, then `WebFetch` | the publisher's page; open copies | coverage |

`philpapers.org` and `philarchive.org` sit behind a bot check: a scout NEVER
fetches them directly and NEVER attempts the check. A PhilPapers API key, or
a bot check the user clears in the browser, would open the record pages; the
skill runs without either.

## Procedure

1. **Search the vault.** Run `answer-questions`'s steps 1 and 2: one `search_hybrid`
   call carrying the question and every key term as its list of queries, then `get_frontmatter` on each
   promising hit and `list_works` on each hit's `field:`. The hits are the
   seed works; the works `list_works` adds are the outer ring; together they
   are the citing set. If `index_status` reports nothing indexed, or
   `search_hybrid` is unavailable, read the frontmatter and the headings of
   every corpus file instead (`Grep "^#" "<CORPUS_DIR>/*.md"`, where `CORPUS_DIR`
   is the path `~/.research-vault/venv/bin/python lib/vault.py` prints under
   that name),
   choose the seed works by title and headings, and say in the reading list
   that the search stores were not used. If the vault holds no work on the
   question, the seed set and the citing set are empty: say so, skip step 2,
   harvest the term list from the question alone, and continue.
2. **Read the citing set's reference lists.**
   1. Run `unheld` over the citing set and write its output to the session
      scratchpad as `unheld.json`. If `unheld` refuses a basename as not
      held, drop that basename from the citing set and run again. If
      `unheld` fails for any other reason, report the error in chat, take no
      known items, say so in the reading list's header, and continue at
      step 3.
   2. Run `unheld --min-citing <N>` over the citing set, starting at N = 1.
      While the shortlist holds more than 150 entries, raise N by one and run
      again; if a raised N empties the shortlist, keep the shortlist of the N
      before it. Read the shortlist.
   3. Choose the known items: every shortlist entry that names a work bearing
      on the question, per "Scope", judged from the entry's title, at most 16, in the
      shortlist's order. NEVER drop an entry for the orchestrator's opinion
      of the work's quality. If two entries name one work under different
      titles, as an original and its translation do, choose the entry more
      works cite, and count the work once toward the 16: `unheld` joins
      editions only under one title. If no entry bears on the question,
      there are no known items: say so in the reading list's header.
   4. Write the known items, each entry copied whole from the shortlist, to
      the session scratchpad as `known.json`, in the shape
      `{"entries": [...]}`.
3. **Harvest the term list.** Read the seed works' frontmatter and the
   sections the hits fall in, under the 4,000-word limit of "Read" in `answer-questions`'s `reference/retrieval.md`
   per section. Write the term list: concepts, technical terms, position
   labels, the names of authors the shortlist names on the question, and the
   titles of the known items. If a seed is in German or French, carry each
   term's English form beside it.
4. **Compose the queries.**
   1. Compose one known-item query per known item, the surname and the main
      title read from the entry. Assign the known-item queries to publisher
      catalogues and authors' pages, eight per query cluster, in
      `known.json`'s order: that route opens the work's own page, which
      carries the obtain link.
   2. Combine the terms into two- and three-term topic queries, each term
      with its variants, and add one query per author name. Every topic
      query carries a term of each subject the question relates, and every
      author-name query a term of the question's subject beside the name: a
      query on one of the subjects alone returns works on a neighbouring
      subject. Every source
      takes the concept queries; PhilPapers and Google Scholar also take the
      author-name queries. A topic query cluster holds at most eight queries;
      if more are composed for one source, keep the eight whose terms the
      seed works use most.
   3. Assign one scout per query cluster. State the count of known items, of
      queries, and of scouts before dispatching.
5. **Dispatch the scouts** in one message so they run concurrently, one
   `Agent` call per query cluster with `subagent_type: literature-scout` and
   `model: claude-sonnet-5`. The prompt carries the question, the
   term list, the cluster's queries, the mode (`known items` for a cluster of
   known-item queries, `topic` otherwise), the source, the held titles the
   scout skips, and the path under the session scratchpad the scout
   writes its report to. A scout
   whose report file is absent or is not JSON, or whose output is marked
   partial, is a failed dispatch:
   dispatch it once more; if it fails again, treat its source as
   unreachable.
6. **Merge.** Pipe the report files as one JSON array into
   `merge --unheld <scratchpad>/unheld.json --known <scratchpad>/known.json`;
   if there are no known items, omit `--known`; if step 2 did not run, omit
   both. If `merge` exits non-zero, stop and tell the user its error: no
   reading list is written from unmerged reports. Read the ordered list and `known_unseen`. Choose every candidate a
   known-item query surfaced. Choose each other candidate whose own comment
   states that the work bears on the question, per "Scope"; leave out a
   candidate whose comment states a neighbouring subject alone, or states
   nothing of the work's subject. Keep the script's order. NEVER drop a candidate
   for the orchestrator's opinion of its quality. If a `known_unseen` entry names the same work as a chosen
   candidate under another year or title, list the work once, as the
   candidate. Write the discover tasks from the left-out works, per
   "Discover tasks".
7. **Write the reading list** to the session scratchpad as
   `Reading list - <Topic>.md`, where `<Topic>` is the question's subject
   in Title Case, at most eight words. The file opens with a frontmatter
   block of two fields, `type: reading-list` and `question:`, both carrying
   the question word for word as the user asked it, then, in this order:
   1. a header of three items: the question, word for word as the user
      asked it, first; the seed works; the term list.
      If the search stores were not used, if the citing set was empty, or if
      step 2 yielded no known item, say so in the seed works item. If a
      source was unreachable, add one line naming it and the queries that
      therefore did not run;
   2. an "Already held" section: every seed work and every candidate
      `merge` marked held, each as one list item with its
      `zotero://open-pdf/library/items/<key>` link read from the corpus
      file's PDF link;
   3. a "Cited by the held works" section: every chosen candidate whose
      `cited_by_count` is at least 1, in the script's order, each as a
      candidate item;
   4. a "Cited, not found outside the vault" section: every `known_unseen`
      entry, in `known.json`'s order, each as a cited item;
   5. a "Found by search" section: every other chosen candidate, in the
      script's order, each as a candidate item;
   6. a "Neighbouring subjects" section: each discover task, per "Discover
      tasks".

   If a section holds no item, the section states "None." Items are
   separated by a blank line. **Only a discover task carries a box:** a
   task is a step the orchestrator carries out, and a work to obtain is the
   user's step, so a held, cited, or candidate item is a plain list item.

   **A candidate item** is `- <reference>. <comment>. <link>`: the
   reference as `<Author> (<Year>). <Title>, <container>`, then one comment,
   then the obtain link with its kind named. A field the page did not show
   is left out, never marked. If the candidate has no obtain link, the item
   ends with the page it was seen at, named as such. The comment reports
   what the work is and where it discusses the question, as the candidate's
   own description states it; it NEVER evaluates, ranks by quality, or
   recommends. The item carries no impact
   numbers and no locator: `merge` keeps both, and the orchestrator gives
   them in chat on request.

   **A cited item** is `- <entry>. Cited in <citing works>. seen at:
   <link>`: the entry text as the first citing work prints it; each citing
   work as `<Author> <Year>, p. <folio>`, the author and year read from its
   basename, or `<Author> <Year>` where its locator carries no folio; the
   link `zotero://open-pdf/library/items/<key>?page=<file_page>` for the
   first citing work, the key read from its corpus file's PDF link, without
   `?page=` where the locator carries no file page. The citing works are the
   cited item's only sighting, so the cited item carries them.
8. **Grade and deliver.** Dispatch the grader with the document's path,
   `subagent_type: reading-list-grader`, `model: claude-sonnet-5`. Output marked
   partial is a failed dispatch: dispatch the grader once more, and if the
   second output is partial too, deliver without a grade and say so. Fix every
   flag it returns, then dispatch it once more; if flags remain after the
   second pass, fix them and deliver. Deliver with `SendUserFile`; if
   `SendUserFile` is unavailable, give the scratchpad path in chat.
9. **Keep the reading list.** If the user asks to keep the reading list for
   a project, follow "Carrying a reading list into a project" of the
   `manage-projects` skill, and write no copy of the document: the
   project reading list holds its entries, and a batch checks each off once
   its work is placed. If the user asks to keep the reading list and names
   no project, copy it into `research vault/bibliographies/4 reading lists/`
   under its scratchpad filename, and say in chat that no batch checks a
   kept document off. If a file of that name exists there, stop and ask the
   user. Otherwise, keep nothing.

## Prohibitions

- NEVER write to the vault except by step 9, the kept reading list or the
  entries carried into a project reading list, and by the deletion of a
  resolved discover task's line: the
  reports, `unheld.json`, and `known.json` live in the session scratchpad.
- NEVER present a work as held unless `merge` marked it held or it is a seed
  work.
- NEVER list a work no page showed: every suggestion is a candidate a scout
  saw a page for, or a `known_unseen` entry, whose page is the citing work's.
- NEVER deliver an obtain link a scout did not return.
- NEVER omit an unreachable source: the header names it and the queries that
  did not run.
