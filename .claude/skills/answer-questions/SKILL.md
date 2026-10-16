---
name: answer-questions
description: "Answer questions — answer a research question from the corpus files, verify every direct quotation in the library PDF, and answer in chat; where the vault holds too little, say so and answer from the literature, cited."
allowed-tools: Read, Glob, Grep, Agent, Bash(~/.research-vault/venv/bin/python .claude/skills/answer-questions/scripts/verify.py verify:*), Bash(~/.research-vault/venv/bin/python .claude/skills/answer-questions/scripts/verify.py quality:*), Bash(~/.research-vault/venv/bin/python .claude/skills/answer-questions/scripts/verify.py locate:*), Bash(~/.research-vault/venv/bin/python .claude/skills/extract-corpus/scripts/extract.py record:*), Bash(~/.research-vault/venv/bin/python .claude/skills/search/scripts/search.py query:*), Bash(~/.research-vault/venv/bin/python .claude/skills/search/scripts/search.py outline:*), mcp__vault-rag__search_hybrid, mcp__vault-rag__outline, mcp__vault-rag__get_frontmatter, mcp__vault-rag__list_works, mcp__vault-rag__index_status, mcp__vault-rag__cites, mcp__vault-rag__cited_by, mcp__vault-rag__neighbours, mcp__vault-rag__contexts, Bash(~/.research-vault/venv/bin/python lib/vault.py:*), WebSearch, WebFetch, Write, SendUserFile
---

# answer-questions (Research Retrieval, run by the orchestrator; passage graders for the hits; the work reader for a whole work)

Answers a research question under the rules of `CLAUDE.md` §1. If the user asks for a document, write it to the session scratchpad and
deliver it with `SendUserFile`; if `SendUserFile` is unavailable, give the
scratchpad path in chat.

## Procedure

**Read `.claude/skills/answer-questions/reference/retrieval.md` before step 1.** Each
step that names one of its sections runs as that section states.

1. **Search**, per "Search".
2. **Choose the works**, per "Choose the works".
3. **Read**, per "Read".
4. **Judge the material.** If the corpus files settle the question, go to
   step 5. If they do not, say in the answer what the vault holds and what
   it lacks, then answer the remainder from training data and from the
   literature found through `WebSearch` and `WebFetch`, citing each work
   drawn on by author, year, and title; a claim from training data with no
   citable source is stated as such. NEVER present an answer as built from
   the vault when it was not.
5. **Verify every direct quotation**, per "Verify every direct quotation".
6. **Answer in chat.** Cite as `CLAUDE.md` §3 states. A claim
   cites the folio its corpus passage carries; a quotation cites the folio
   `verify` reported. Beside each verified quotation give the `link`
   `verify` reported. At the first citation of each work in the answer,
   give that work's `zotero://open-pdf/library/items/<KEY>?page=<file
   page>` link at the folio cited, the file page read from the page marker
   or from `outline`. One line of the answer names the queries that were
   run, and, where a worker was dispatched, which.

## Prohibitions

- NEVER deliver a quotation `verify` has not confirmed or that was not read
  on the page.
- NEVER deliver a quotation in the corpus file's wording where `verify`
  reported the page's.
- NEVER smooth disagreement between sources into a consensus. Report the
  disagreement and who holds which position.
- NEVER write any of it to the vault.
