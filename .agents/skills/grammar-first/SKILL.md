---
name: grammar-first
description: 'Use when writing or changing the TDL grammar or the language reference (docs/language.md, plan step 1), settling one of the 12 grammar ambiguities, wording an error message or hint, or whenever the vault note and this repo disagree about the language.'
---

# Grammar first

The grammar is written before the parser (order of work, step 1) and `docs/language.md` is the source of truth from now on (D66). The parser implements it; a parser behaviour with no rule is a bug in one of the two.

## Writing a rule

- Every construct gets **a short example first, then the rule**, in the plain wording of the Familiar Names Audit (`41 TDL Reference/Familiar Names Audit.md`): the names a person from CSS, QML or Flutter expects; no compiler jargon in prose (`token`, `production`, `lexeme` stay private). Say where TDL differs from those.
- Lexical rules (characters, comments, strings, numbers, words, slots) and block rules (metadata, root, properties, `If`/`Else`/`For`) are separate sections. Each rule names the corpus cases that pin it (`conformance-corpus`).
- Every example in the doc is a corpus case, or is checked by a test, so the doc cannot drift from the parser.

## Settling an ambiguity

The 12 open questions are in the First Slice note ("Ambiguities to Settle in the Grammar"). Each has a recommendation, and **the `tess-dl` session decides** and records the answer (the note says so); every one needs an answer before the parser is written (acceptance criterion):

1. Take the recommendation unless there is a concrete reason not to. State the reason if you depart from it.
2. Record the answer in `docs/decisions.md` (a numbered row: decision, reason) and in `docs/language.md`, and add the corpus cases it makes possible.
3. Bring to the user only a **departure from the recommendation**, or anything that changes what an existing document means, with the options and your pick: new syntax is not settled silently.

## Error wording

An error says what happened in one plain sentence and the hint says what to write. It names what the author wrote, not the parser state: "This colour needs quotes. Write "#ffffff"." not "unexpected token HASH". `tdl-double-close`'s hint says `} }`. `str(error)` is `file:line:column: message (hint)`. No colour or symbol carries meaning (screen readers).

## When the vault and the repo disagree

Until `docs/language.md` exists the vault (`/home/phil/Projects/Obsidian/Tesserae Shell`) is right; after, this repo is. Either way, raise the difference as a `TDL-REQ-###` for the maintainer, who carries it; do not edit the vault and do not message the shell session unless asked.
