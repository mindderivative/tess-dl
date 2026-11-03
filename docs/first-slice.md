# tess-dl First Slice

> Moved here from the Tesserae Shell design vault on 2026-11-02. This file is now the source of truth; the vault keeps a short pointer. Names of vault notes and decisions (D1 to D94, the ADR-0014 file layout and so on) refer to that vault and are not links.

> [!NOTE]
> The brief for the first piece of work in the `tess-dl` project (PyPI `tesserae-dl`, import `tess_dl`): a parser that reads a TDL file into a lossless tree, reports the 22 error codes with positions, writes the file back byte for byte, and is checked by a shared test corpus. The brief collects what the vault already decided so the `tess-dl` session does not have to dig. It is written for the maintainer to hand over; the vault sends nothing to another project (AGENTS > 6. Requests Between Projects). Where the vault is silent, the brief says so and gives a recommendation.

## Goal

By the end of the first slice, this works:

```python
import tess_dl

doc = tess_dl.loads(text, path="Main_Shell.tdl")  # raises TDLError on the first mistake
result = tess_dl.parse(text, path="Main_Shell.tdl")  # never raises; result.errors lists up to 50
assert tess_dl.dumps(doc) == text  # exact round trip
doc2 = doc.with_metadata("UID", "0192...")  # one edit, every other byte unchanged
```

Nothing else is in the first slice (see [Not in the First Slice](#not-in-the-first-slice)).

## Where This Brief Lives

This note in the Tesserae Shell vault is the current version: `~/Projects/Obsidian/Tesserae Shell/41 TDL Reference/tess-dl First Slice.md`. A copy in another place (for example the exported `docs/` of the `tess-shell` repository, or a `tess-dl` docs folder) can be older. Until the TDL documentation moves into `tess-dl/docs/` (the maintainer's plan, 2026-11-02, D92), read the notes this brief links in the vault, and when the two disagree the vault is right.

## What to Read

| Source | For |
|---|---|
| [TDL Library API](api.md) | The public API: entry points, classes, errors, limits, edit calls, acceptance criteria |
| [TDL Language](language.md) | The language as it stands: metadata block, root block, punctuation, values, structure words, the 22 error codes |
| ADR-0014 Shell File Language | Why it is as it is: D1 to D91 (see especially D2, D8, D9, D28, D31, D36, D52, D54, D66 to D70, D74, D91) |
| Familiar Names Audit | The wording rules for the docs and the error messages |
| tess-dl Handover | Which language text moves into `tess-dl` and in what order |
| Expression Language Requirements | How TEL uses a slot's text and origin (T17) |

If a vault note and the `tess-dl` text disagree, the `tess-dl` text is the source of truth from now on (D66). Raise the difference as a `TDL-REQ-###` so the maintainer can record it.

## Project Basics (Decided, D67)

MIT licence; Python 3.14 or later; no runtime dependencies; pytest; the language version `0.1` is separate from the package version; fully typed with `py.typed`; every public name in `tess_dl.__all__`. Build tooling and CI follow the TEL project's choices unless there is a reason not to ([TDL Library API > Open Questions](api.md#open-questions) 7).

## Order of Work

| # | Task | Done when |
|---|---|---|
| 1 | Write the grammar (lexical rules and block rules) in `docs/language.md`, with an example before each rule, in the plain wording the Familiar Names Audit asks for | Every construct in [TDL Language](language.md) has a rule, and the ambiguities in [Ambiguities to Settle in the Grammar](#ambiguities-to-settle-in-the-grammar) each have an answer |
| 2 | Build the conformance corpus ([The Conformance Corpus](#the-conformance-corpus)) from the acceptance criteria and the 22 error codes, before the parser | The corpus runs and every case fails for the right reason |
| 3 | Lexer and parser, producing the tree of [TDL Library API > The Tree](api.md#the-tree) with spans on every node and comments kept | The `ok` cases parse |
| 4 | Errors: the 22 codes with message, hint, origin and related origins | The `error` cases pass with the stated positions |
| 5 | `dumps` and the round trip | `dumps(loads(x)) == x` for every `ok` case |
| 6 | `with_metadata`, `without_metadata`, `with_property`, `replace` | The edit cases in the corpus pass; no other byte changes |
| 7 | `parse` with recovery and the 50-error cap | A file with six mistakes returns six errors |
| 8 | Limits (1 MiB, 50 errors, depth 64) and the timing check | The budget in [TDL Library API > Performance Budget](api.md#performance-budget) is measured and recorded |
| 9 | Publish `tesserae-dl` 0.1.0 | The install works on a clean Python 3.14 |

Rule of thumb: tests and the grammar come before the parser. The shell will start by reading the corpus.

## The Conformance Corpus

A folder `tests/corpus/` in `tess-dl`. `tess-dl` owns the corpus; the shell does not edit it. When the shell finds a case it needs (a file the parser should accept or refuse, an error position, an edit result), it proposes it to `tess-dl` as a `TDL-REQ-###` with the input text and the expected result, and `tess-dl` adds, changes or declines it (maintainer, 2026-11-02, D92). The shell gets the corpus by installing the package's test data or by copying a released version. One case is two files:

| File | Content |
|---|---|
| `<area>/<case>.tdl` | The input text |
| `<area>/<case>.expect.json` | Either `{"ok": true, "canonical": { ... }}` (the normalised content, no positions or comments) or `{"errors": [{"code": "...", "line": N, "column": N}]}` |

Every `ok` case is also checked for the exact round trip. Areas: `metadata`, `blocks`, `values`, `slots`, `strings`, `comments`, `structure` (`If`, `Else`, `For`), `errors`, `edits`, `limits`.

### Cases for the Error Codes

One minimal file per code (22). The "points at" column is the proposal for where the origin lands; the exact line and column are fixed when the cases are written.

| Code | The file has | Points at |
|---|---|---|
| `tdl-no-metadata` | A root block and no `---` | Line 1, column 1 |
| `tdl-metadata-unclosed` | `---` and keys, no second `---` | The opening `---` |
| `tdl-no-version` | A metadata block without `TDL:` | The opening `---` |
| `tdl-no-name` | A metadata block without `Name:` | The opening `---` |
| `tdl-bad-name` | `Name: DP-1` or `Name: 1st` | The value |
| `tdl-no-root` | A metadata block and nothing after it | The end of the metadata block |
| `tdl-many-roots` | Two root blocks | The head word of the second |
| `tdl-unclosed-block` | `Bar {` with no `}` | The opening `{` |
| `tdl-unexpected-close` | A stray `}` | That `}` |
| `tdl-double-close` | `}}` closing two blocks | The `}}` |
| `tdl-unclosed-slot` | `Text: {{ a` | The `{{` |
| `tdl-empty-slot` | `Text: {{ }}` | The `{{` |
| `tdl-unclosed-string` | `Text: "abc` | The opening quote |
| `tdl-bad-escape` | `Text: "a\q"` | The backslash |
| `tdl-duplicate-key` | `Width: 1` twice in one block | The second key; the first is in `related` |
| `tdl-bare-hash` | `Color: #fff` | The `#` |
| `tdl-reserved-name` | A block headed `If` used as a name, or `Name: For` | The word |
| `tdl-unexpected-text` | `Width 32`, a key with no value, an `Else` with no `If`, a `For` without `In` or `Key`, an unclosed `(`, a stray `{` in an unquoted value | The first character that does not fit |
| `tdl-too-large` | A file over 1 MiB | Line 1, column 1 (checked before parsing) |
| `tdl-too-deep` | 65 levels of nesting | The opening brace that passes the limit |
| `tdl-unsupported-version` | `TDL: 9.0` | The version value |
| `tdl-bad-encoding` | Bytes that are not valid UTF-8, through `load` | The byte offset of the first bad byte |

### Cases from the Acceptance Criteria

Take every language-level line in [TDL Language > Acceptance Criteria](language.md) as a case. Among them: `TDL: 0.1   # note` is the value `0.1` and a comment; `Color: "#fff"   # note` is a string and a comment; `Text: {{ max(a, b) }}` is one slot whose `,` does not end the value; `{{ '}}' }}` ends at the second `}}`; `{{ {'a': {'b': 1}} }}` ends at the first `}}`; a one-line block `Params { format { Type: string } }` and an empty block `Spacer { }` both load; a list of four, one number and a named-sides block are all valid values; repeated block names are allowed and a repeated property key is not.

Cases with no vault answer are listed next; write them once the grammar settles them.

## Ambiguities to Settle in the Grammar

The vault's prose does not fully decide these. Each has a recommendation; the `tess-dl` session decides and records the answer in `docs/language.md`.

| # | Question | Recommendation |
|---|---|---|
| 1 | Is an unquoted value with spaces (`Text: Hello world`) one `Word` or a separate kind? | One kind, `Word`, whose `text` is the whole run, as the rule "an unquoted value runs to the end of the line, the next `,`, a closing brace or a comment" implies |
| 2 | Is `0.1` in the metadata block a `Number`? | No: versions are strings (ADR-0014 Shell File Language > Layout Rules item 3); in the metadata block every bare value is a `Word` |
| 3 | What numbers exist? | `16`, `-4`, `0.9`; no exponent, no hex, no digit separators in 0.1 |
| 4 | Where does `Call` begin: `rgba(` only, or any `word(`? | Any `word(`, so the shell can reject unknown names; the parser keeps the arguments as values separated by spaces |
| 5 | Escapes in a string | `\\`, `\"`, `\'`, `\n`, `\t`, `\u` followed by four hex digits; anything else is `tdl-bad-escape` |
| 6 | Line endings, tabs, BOM | `\n` and `\r\n` both accepted and preserved; a tab is whitespace; a leading BOM is accepted and preserved |
| 7 | Can a slot contain a newline? | No: a slot is on one line (D54); a newline before `}}` is `tdl-unclosed-slot` |
| 8 | Is the end of a value the end of the line even inside a list? | A list may span lines; its items are separated by `,` or a newline |
| 9 | Is `Children` special for the parser? | No: an ordinary block; only `If`, `Else`, `For`, `In` and `Key` are reserved ([TDL Language > Structure Words](language.md)) |
| 10 | Key characters | A letter, then letters, digits and `_` (D4 forbids numeric keys) |
| 11 | Maximum nesting depth | 64 (decided, G11) |
| 12 | Where trivia attaches | Comments are entries in their block, in source order; blank lines and indentation are kept in the source spans and not modelled |

## The Shell's Expectations

What the shell relies on, so the first slice does not have to guess:

- Positions are 1-based `line` and `column` counted in characters, plus a byte `offset` ([TDL Library API > Errors](api.md#errors)).
- A `Slot` carries `text` and `text_origin`, where `text_origin` is the first character after `{{`, and nothing is trimmed (Expression Language Requirements T17).
- The shell converts an `Origin` to TEL's `Origin`; `tess_dl` imports nothing from TEL or tre.
- The shell writes `UID` through `with_metadata` and expects only that line to change (Risk Register R-06).
- `tess_dl` parses on any thread and returns immutable data.

## Not in the First Slice

The formatter and `canonical()` for the Python builder (OQ 3), a `tdl` command line (OQ 6), the TextMate grammar, a language server, `to_data()` beyond a simple shape, and anything that knows a block's meaning (lengths, colours, enums, the schema, `Import`). The shell's schema, the building blocks and the module list are not the library's concern.

## How to Report Back

- A needed change to the vault's language text or API: a `TDL-REQ-###` with the reason (AGENTS > 6. Requests Between Projects); the maintainer carries it here.
- A question about the shell's use: ask through the maintainer.
- When a task above finishes: say which rows of tess-dl Handover can be handed over.

## Open Questions

1. [x] The brief goes to `tess-dl` as written; the maintainer gives the session the vault location of this note (2026-11-02).
2. [x] `tess-dl` owns the corpus and the shell proposes cases by `TDL-REQ-###` (maintainer, 2026-11-02, D92).
3. [x] The 12 grammar ambiguities are answered: G1 to G12 in `tess-dl` `docs/decisions.md` (commit `5e44072`), with G13 to G18 from the maintainer's answers (2026-11-02). The table above is the brief as written; the answers are in [TDL Language](language.md).

## Acceptance Criteria

- [ ] The `tess-dl` session can start from this note and the notes it links, with no other conversation.
- [ ] Every item under [Goal](#goal) and in the order-of-work table has a test in the corpus.
- [ ] Every ambiguity has a recorded answer before the parser is written.

## Links

- [TDL Library API](api.md) · tess-dl Handover · [TDL Language](language.md) · ADR-0014 Shell File Language · 41 TDL Reference
