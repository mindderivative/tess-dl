# Design decisions

Decisions made for the language and the library, newest last. The reason is kept with each one. Syntax, grammar and boundary changes are recorded here, in this repo, not left in the vault.

`G` rows answer the 12 grammar ambiguities of the First Slice note (vault: `41 TDL Reference/tess-dl First Slice.md`). The note leaves them to the `tess-dl` session: each takes the note's recommendation unless the Notes column says otherwise. `Q` rows are open questions for the maintainer.

## 2026-11-02 (grammar, plan step 1)

| # | Decision | Notes |
|---|---|---|
| G1 | **An unquoted value is one kind, `Word`**, whose text is the whole run (spaces inside kept, outer whitespace dropped). A word whose text is a number is a `Number`. | The rule "an unquoted value runs to the end of the line, the next `,`, a closing brace or a comment" implies one run. `Hello world` is one word; `1st` is a word; `16` is a number. |
| G2 | **In the metadata block every bare value is a `Word`**, never a number. `0.1` is the text `0.1`. | Versions are strings (ADR-0014 layout rule 3): `0.10` and `0.1` must not be the same value. |
| G3 | **Numbers are `16`, `-4`, `0.9`**: an optional `-`, digits, optionally `.` and digits. No exponent, hex, digit separators, leading `+`, `.5` or `5.`. A word that only starts with digits (`16px`) is a word. | Smallest set the shell's lengths and opacities need. More can be added later without breaking a file. |
| G4 | **`Call` starts at any word written directly against `(`**; the arguments are values separated by spaces, to the `)`, on one line. | The shell, not the parser, knows which call names exist, so it can say "unknown colour function". |
| G5 | **String escapes:** `\\`, `\"`, `\'`, `\n`, `\t`, `\u` plus four hex digits. Anything else is `tdl-bad-escape`. | As recommended. |
| G6 | **Line endings, tabs, BOM:** `\n` and `\r\n` are both accepted and each line keeps its own; a tab is whitespace; a leading BOM is accepted and kept; a lone `\r` is plain whitespace; a `---` line may have trailing spaces or tabs. | A lossless tree must keep all of them. The lone `\r` and trailing-space details go beyond the recommendation; they are the least surprising reading. |
| G7 | **A slot is on one line.** A line end before `}}` is `tdl-unclosed-slot`. | D54 of the vault's ADR-0014. |
| G8 | **A list may span lines;** items are separated by `,` or a newline, with an optional trailing `,`. | As recommended; matches how entries are separated in a block. |
| G9 | **`Children` is an ordinary block** and `Import` an ordinary property. Only `If`, `Else`, `For`, `In` and `Key` are reserved. | The parser stays free of the shell's meaning. |
| G10 | **Key characters:** a letter, then letters, digits and `_`. The same rule serves block heads, `For` variables and `Name:` values. | D4 forbids numeric keys. One rule for every name keeps `tdl-bad-name` simple. |
| G11 | **Maximum nesting depth is 64**, counting the root block as 1; blocks, `If`/`For` bodies and lists each add a level. | Proposed by the note. A stack-safe parser must reach it without a `RecursionError`. |
| G12 | **Trivia is kept in source spans, not modelled.** Comments are entries in their block in source order; blank lines and indentation live in the spans between nodes. | Keeps the tree small and makes the exact round trip a property of the spans (`lossless-roundtrip`). |

## Open

| # | Question | Recommendation |
|---|---|---|
| Q1 | **The 17 codes do not cover every syntax mistake.** Nothing names `Width 32` (no colon), a key with no value, an `Else` with no `If`, a `For` with no `In` or `Key`, an unclosed `(` in a call, or a stray `{` in an unquoted value. What does the library report for these? | One more code for "this is not valid here" (working name `tdl-unexpected-text`), with a per-case message and hint. It is new language surface, so the code is the maintainer's to approve. Until then `parse` cannot recover from these cases with a code. |
| Q2 | **`Color: #fff` versus `Key: # note`.** A `#` after whitespace starts a comment, yet `Color: #fff` must be `tdl-bare-hash`. | In value position, a `#` followed directly by a non-space character is `tdl-bare-hash`; a `#` followed by whitespace or the end of the line is a comment. |
| Q3 | **Is `{{ }}` a slot inside a quoted string** (`"Battery {{ x }}%"`), or plain text? | Plain text: a quoted string never holds a slot, so quotes are a way to switch slots off. A template is written unquoted. |
| Q4 | **Is a property with no value (`Key:` then a line end) valid?** | An error covered by Q1's new code. |
| Q5 | **Where may `Else` sit?** | After the `If` body's closing brace, on the same line or after newlines and comments. |
| Q6 | **The extra codes** `tdl-unsupported-version`, `tdl-too-large`, `tdl-too-deep`, `tdl-bad-encoding` (TDL Library API, open question 5). | Accept all four: each is a limit or input the library must report somehow. |
