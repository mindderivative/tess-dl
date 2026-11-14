# The Tesserae Data Language (TDL), version 0.1

TDL is a structure-only data language: blocks, properties and values. It does not know what a bar, a monitor or a colour is. The program that reads a file (the Tesserae Shell, Tesserae UI) decides which blocks and keys it accepts and what a value means. Expressions belong to TEL: TDL only marks where one starts and ends.

This page is the reference for what the `tess_dl` library reads. Each section shows an example first, then the rule. Where TDL behaves differently from CSS, QML or Flutter, a note says so. The reasons for the choices are in [decisions.md](decisions.md) (rows G1 to G37).

Status: draft for the first slice. Every example here becomes a case in `tests/corpus/`.

## A file

A file is a metadata block, then exactly one root block.

```
---
TDL: 0.1
Name: Shell_Root
---

# The root block names the kind of file.
Shell {
  Monitor {
    Name: Main
    Connector: DP-1
    Bar {
      Name: Top_Bar
      Edge: TOP
      Height: 32
      Label { Text: Battery {{ battery.percent }}% }
    }
  }
}
```

The keys inside the root block (`Monitor`, `Edge`, `Label`) belong to the shell's schema, not to TDL.

## Text, lines and whitespace

```
# one file, written on Windows: every line ends with \r\n
```

- A file is UTF-8 text. A leading byte-order mark is accepted and kept.
- A line ends with `\n` or `\r\n`. Both are accepted; each line keeps the ending it had. A lone `\r` is ordinary whitespace. (G6)
- A space or a tab is whitespace. Indentation never matters.
- The last line may or may not end with a line ending.

## Comments

```
Width: 32   # pixels
# a whole line
Color: "#1e1e1e"   # the # inside the quotes is part of the string
```

A `#` starts a comment when it is the first thing on a line or follows whitespace. The comment runs to the end of the line. A `#` inside a quoted string or inside a slot is not a comment. A `#` with no whitespace before it (`a#b`) is part of the word.

One case needs care: where a value is expected, a `#` followed directly by a non-space character (`Color: #fff`) is not a comment but the error `tdl-bare-hash`; a `#` followed by whitespace or the end of the line (`Color: # note`) is a comment. (G14)

*Differs from CSS:* there is no `/* */` and no `//`.

## Names and keys

```
Bar
Exclusive_Zone
Level_1
```

A key, a block head, a `For` variable and a `Name:` value all follow one rule: a letter, then any letters, digits and `_`. There are no numeric keys (`1` is not a key). (G10)

`If`, `Else`, `For`, `In` and `Key` are reserved words. They cannot be a block head, and a `Name:` cannot be one of them (`tdl-reserved-name`).

TDL never changes case. The shell's schema decides which spellings it accepts.

## The metadata block

```
---
TDL: 0.1          # the language version
Name: Shell_Root
Shell: 0.1
UID: 0192d3c4-7a1e-7c2f-9b1a-3f5e2d8a6c10
---
```

- The file starts with a line that holds only `---` (trailing spaces and tabs are allowed). Nothing may come before it except a byte-order mark. (G6)
- Each line until the next `---` is `Key: value` or a comment or blank. No blocks, no lists.
- Every bare value here is a **word**, never a number: `0.1` is the text `0.1`. A quoted value is a string. (G2)
- `TDL:` is required (`tdl-no-version`). `Name:` is required and must be letters, digits and `_`, starting with a letter (`tdl-no-name`, `tdl-bad-name`).
- Other keys are allowed and kept. A key may appear once (`tdl-duplicate-key`).
- A `---` line with no second `---` after it is `tdl-metadata-unclosed`. A file whose first line is not `---` is `tdl-no-metadata`.

## Blocks and properties

```
Panel { Name: p1, Width: 200 }     # one line
Spacer { }                          # empty
Border {
  Color: "#1e1e1e"
  Width: [2, 2, 2, 2]
}
```

- A **block** is a word, then `{`, then entries, then `}`. The word before the brace is the block's type (`Panel`, `Border`).
- A **property** is `Key: value`. The space after `:` is optional.
- Entries in a block (properties, blocks, `If`, `For`, comments) are separated by a newline or a `,`. A trailing `,` is allowed and never required.
- The same block word may appear many times in one block. A property key may appear once (`tdl-duplicate-key`; the error names both places).
- `Children` and `Import` are ordinary words: `Children` is a block, `Import: File.tdl` is a property. Their meaning is the shell's. (G9)
- Nested blocks close with a space or a newline between the braces: `} }`, never `}}`. An adjacent `}}` outside a slot or a string is `tdl-double-close`, whether or not two blocks are open. A block directly inside a block opens as `{ {` for the same reason: `{{` always opens a slot.
- A `{` with no `}` before the end of the file is `tdl-unclosed-block`; a `}` with nothing open is `tdl-unexpected-close`.
- Nesting is limited to 64 levels (the root block is level 1; blocks, `If`/`For` bodies, lists and calls each count). (G11, G27)

## The root block

```
Module {
  ...
}
```

After the metadata there is exactly one block, the **root block**. Its head word says what kind of file it is; TDL does not look at the word or at the file name. No root block is `tdl-no-root`; a second one is `tdl-many-roots`. Comments and blank lines may surround it.

## Values

| Kind | Written as | Notes |
|---|---|---|
| Word | `TOP`, `true`, `Top_Bar`, `Hello world` | Unquoted text |
| String | `"a b"`, `'a b'` | Quoted, with escapes |
| Number | `16`, `-4`, `0.9` | |
| Percent | `50%` | A whole number and `%` |
| Call | `rgba(0 0 0 0.5)` | A name, then values in parentheses |
| List | `[a, b, c]` | |
| Slot | `{{ expression }}` | TEL's |
| Template | `Battery {{ battery.percent }}%` | Text with a slot in it |

TDL reads the **form** of a value, not its meaning. `true`, `false`, `null` and `TOP` are words; the shell's schema turns them into a boolean, a null or an enum. A colour, a length and four-sided values are the shell's too.

### Words

```
Edge: TOP
Text: Hello world        # one word with a space in it
Connector: DP-1
```

An unquoted value runs to the end of the line, the next `,`, a closing `}` (or `]` inside a list) or a comment, whichever comes first. Surrounding whitespace is dropped; inside, it is kept. A word may not contain `,`, `{`, `}` or start with `#`: quote it. A word whose text is a number is a number (below), so `Name: 1st` is a word and `Width: 16` is a number. (G1)

### Strings

```
Text: "Say \"hi\""
Path: 'C:\\Users'
Mark: "\u00e9"
```

`"…"` and `'…'` are the same. A string must close on the line it opens (`tdl-unclosed-string`). A `{{` inside quotes is plain text, not a slot. (G15) These escapes are valid: `\\` `\"` `\'` `\n` `\t` and `\u` followed by four hex digits. Any other `\x` is `tdl-bad-escape`. (G5) The value of the string has the escapes resolved; its text is kept as written.

A colour with `#` needs quotes: `Color: "#ffffff"`. `Color: #fff` is `tdl-bare-hash` (hint: write `"#ffffff"`).

*Differs from CSS:* an unquoted colour with `#` is an error, not a colour.

### Numbers and percentages

```
Opacity: 0.9
Offset: -4
Width: 50%
```

A number is an optional `-`, digits, and optionally `.` and more digits. No exponent (`1e3`), no hex (`0x10`), no separators (`1_000`), no leading `+`, no `.5` or `5.`. (G3) A percentage is a whole number followed by `%`. A word that merely starts with digits (`16px`) is a word.

### Calls

```
Color: rgba(0 0 0 0.5)
```

Any word written directly against `(` starts a call (`rgba(`, `url(`). The arguments are values separated by spaces, up to the `)`, on one line. TDL does not know which call names exist; the shell rejects the ones it does not. (G4)

### Lists

```
Width: [2, 2, 2, 2]
Items: [a, b, c]
Names: [
  First
  Second,
]
Empty: []
```

A list holds values (not blocks). Items are separated by `,` or a newline, a trailing `,` is allowed, and a list may span lines. (G8) A group of `Key: value` pairs is a block, never a list.

### Slots

```
Text: {{ max(a, b) }}
Color: {{ hovered ? "#1e1e2e" : "#313244" }}
Text: {{ '}}' }}
```

A slot starts at `{{` and ends at the first `}}` that is not inside a quoted string (`'…'` or `"…"`, with `\` escapes). Everything in between is opaque to TDL: a `,`, `#`, `:` or a single brace in a slot does not end a value or start a comment. The slot's **text** is what lies between the braces, nothing trimmed (` max(a, b) `), and its **text origin** is the position of the first character after `{{`; both are for TEL.

- A slot is on one line. A line end before `}}` is `tdl-unclosed-slot`. (G7)
- `{{ }}` with nothing but whitespace is `tdl-empty-slot`.
- A slot ends at its first `}}`: in `{{ {'a': {'b': 1}} }}` the slot is ` {'a': {'b': 1` and the trailing `}}` is `tdl-double-close`. (G19)

A value that is exactly one slot is a slot. A value that has text around a slot is a **template**: `Battery {{ battery.percent }}%` is the parts `Battery `, the slot, and `%`, in order.

## If, Else and For

```
If {{ battery.low }} {
  Icon { Name: Warning }
} Else {
  Icon { Name: Ok }
}

For item In {{ items }} Key {{ item.id }} {
  Label { Text: {{ item.title }} }
}
```

- `If {{ condition }} { … }` may be followed by `Else { … }`. There is no `Else If`: nest an `If` inside the `Else`. `Else` follows the closing brace of the `If` body, on the same line or after newlines and comments. (G17) An `Else` with no `If` is `tdl-unexpected-text`.
- `For variable In {{ items }} Key {{ key }} { … }`. The variable follows the names rule. `In` and `Key` are required (`Key` gives each entry its identity); leaving either out is `tdl-unexpected-text`.
- Their bodies hold entries like any block.
- `If`, `Else`, `For`, `In` and `Key` are special only where a key or entry is expected (they are fine inside an unquoted word or a string).

## Errors

Every error has a stable `code`, a one-sentence message in plain words, a hint that says what to write, an origin (`file:line:column`, 1-based, columns counted in characters) and related origins. `str(error)` is `file:line:column: message (hint)`.

| Code | When | Hint | Points at |
|---|---|---|---|
| `tdl-no-metadata` | The file does not start with a `---` block | Start the file with `---` | Line 1, column 1 |
| `tdl-metadata-unclosed` | The metadata block has no closing `---` | Close the block with `---` | The opening `---` |
| `tdl-no-version` | No `TDL:` in the metadata | Add `TDL: <version>` | The opening `---` |
| `tdl-no-name` | No `Name:` in the metadata | Add `Name: <identifier>` | The opening `---` |
| `tdl-bad-name` | A `Name:` with a character other than a letter, digit or `_`, or starting with a digit | Use letters, digits and `_` | The value |
| `tdl-no-root` | No root block after the metadata | Add one root block, for example `Shell { }` | The end of the metadata block |
| `tdl-many-roots` | More than one root block | Keep one root block | The head word of the second |
| `tdl-unclosed-block` | A `{` has no `}` before the end of the file | Add the missing `}` | The opening `{` |
| `tdl-unexpected-close` | A `}` with no open block | Remove the extra `}` | That `}` |
| `tdl-double-close` | A `}}` outside a slot or string | Write `} }` | The first `}` of the `}}` |
| `tdl-unclosed-slot` | A `{{` with no `}}` on the same line | Close the slot on the same line | The `{{` |
| `tdl-empty-slot` | A `{{ }}` with nothing in it | Put an expression in the slot | The `{{` |
| `tdl-unclosed-string` | A quote with no closing quote on the line | Close the string | The opening quote |
| `tdl-bad-escape` | A `\` followed by something that is not an escape | Use a valid escape or write `\\` | The backslash |
| `tdl-duplicate-key` | A property key twice in one block (or metadata) | Remove one; the message names both places | The second key; the first is a related origin |
| `tdl-bare-hash` | A value that starts with `#` outside quotes | Quote the colour: `"#ffffff"` | The `#` |
| `tdl-unexpected-text` | Text that is not valid where it stands. Kinds: a key with no `:` (or a block head with no `{`); a property with no value; an `Else` with no `If`; an `If` or `For` missing a part (the condition, `In`, the list, `Key`, the key, or the `{` of its body); an unclosed `(` or `[`; a stray `{` in an unquoted value or a call; text after a string or call on the same line; a `,` or a comment inside a call; anything else that cannot start a metadata line, the root block, an entry or a value | The hint says what that spot needs, for example `Write Key: value` | The first character that does not fit (see below) |
| `tdl-reserved-name` | A block head or `Name:` that is `If`, `Else`, `For`, `In` or `Key` | Choose another name | The word |

Those are the 18 language errors. Checking the root block against the file name is not TDL's job: the program that reads the file does that.

Where it points, in detail (G20, G28): `tdl-no-root` at the first character after the closing `---` line, including its line ending. `tdl-unexpected-text` at: the first non-whitespace character after the `:` for a missing value (a `#` that starts a comment, or the line end); the first character after the key and its whitespace for a missing `:` or `{`; the `Else` for an `Else` with no `If`; the character where the missing part of an `If` or `For` should start (for a `For` with no `Key`, the `{` that opens the body; with no `In`, the first `{{` after the variable; with no `{` at all, the line end); the line end for an unclosed `(`; for an unclosed `[`, the `}` or the end of the file that reaches it; the `{` for a stray `{` in an unquoted value or a call argument; the first non-whitespace character after a string or a call; the `,` or the `#` inside a call; otherwise the first character that cannot start the line, root block, entry or value. `tdl-bad-encoding` is placed by counting the valid UTF-8 prefix before the first bad byte (G21). A `TDL:` value that does not start with a number is `tdl-unsupported-version` too.

Four more codes report what the library will not read at all. Each stops the file with one error:

| Code | When | Hint |
|---|---|---|
| `tdl-too-large` | The text is longer than 1 MiB (checked before any parsing) | Split the file |
| `tdl-too-deep` | Blocks, bodies, lists and calls nest deeper than 64 levels | Flatten the nesting |
| `tdl-unsupported-version` | The `TDL:` version is newer than this library's | Use a newer `tesserae-dl` |
| `tdl-bad-encoding` | The bytes are not valid UTF-8 (`load`; the message gives the byte offset), or the text holds a character UTF-8 cannot write, such as a lone surrogate (`loads`, G30) | Save the file as UTF-8 |

The error list stops at 50 errors; the last entry says so (`The list stops at 50 errors.`). `tess_dl.parse` lists every mistake it finds, in source order (G31):

- A bad entry is recorded and skipped to the end of its line, or to the `}` that closes its block; braces opened on the bad line itself are skipped with it.
- A bad metadata line is recorded and the next line is read; each missing or wrong required key (`TDL`, `Name`) is reported and reading goes on.
- `}}` is reported once and closes up to two open blocks; the second `}` is not reported again.
- A `{` that is never closed is reported at each unclosed `{` when the file ends.
- A second root block is reported and then read, so its inside is not reported twice; text after the root block is reported line by line.
- `tdl-too-large`, `tdl-too-deep` and `tdl-bad-encoding` stop the file with that one error.
- The tree it returns leaves out the entries that had a mistake; there is none when the metadata or root block cannot be read.

## Where TDL differs

| If you know | Know that in TDL |
|---|---|
| CSS | `#fff` unquoted is an error; no `/* */`; a value ends at the line end or a `,`, not at `;` |
| JSON, YAML | Keys are not quoted; `:` is required; `,` or a newline separates entries; there is no indentation rule |
| QML, Flutter | A block's head word is its type, and a name is a `Name:` property |
| Any template language | `{{ }}` marks a slot on one line; TDL does not run it |
