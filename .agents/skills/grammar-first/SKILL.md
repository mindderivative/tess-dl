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

The 12 open questions are in the First Slice note ("Ambiguities to Settle in the Grammar"). Each has a recommendation, but **the answer is the maintainer's call**:

1. State the question, the options, and the recommendation with its reason.
2. Ask. Do not write the parser to a guess.
3. Record the answer in `docs/decisions.md` (a numbered row: decision, reason) and in `docs/language.md`; add the corpus cases it makes possible.

Settled by the vault already (do not reopen): values are lexical, the schema types them (D74); the suffix check belongs to the shell (D91, so 17 language errors); `{{ }}` is a slot and its text is TEL's; a slot is on one line (D54).

## Error wording

An error says what happened in one plain sentence and the hint says what to write. It names what the author wrote, not the parser state: "This colour needs quotes. Write "#ffffff"." not "unexpected token HASH". `tdl-double-close`'s hint says `} }`. `str(error)` is `file:line:column: message (hint)`. No colour or symbol carries meaning (screen readers).

## When the vault and the repo disagree

Until `docs/language.md` exists the vault (`/home/phil/Projects/Obsidian/Tesserae Shell`) is right; after, this repo is. Either way, raise the difference as a `TDL-REQ-###` for the maintainer, who carries it; do not edit the vault and do not message the shell session unless asked.
