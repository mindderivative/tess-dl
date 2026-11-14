# Changelog

All notable changes to the package. Versions follow [Semantic Versioning](https://semver.org); below
1.0 a minor version may break the API. The language version is separate and is 0.1 up to package 0.1.1 and 0.2 after it
here (`docs/versioning.md`).

## Unreleased

### Breaking: language 0.2 (G38)

- A slot is written `<| expression |>`; `{{ }}` is no longer a slot. `{{` in an unquoted value is
  `tdl-unexpected-text` with a hint. Files declare `TDL: 0.2`; `tess_dl.LANGUAGE_VERSION` is `"0.2"`.
  `tools/migrate_slots.py` rewrites 0.1 files (run it with `uv run --no-project --with
  tesserae-dl==0.1.1`). `If.with_condition`, `For.with_items` and `For.with_key` take the new form.
- `tdl-double-close` is removed: `}}` is two closing braces, and a slot may hold braces, so
  `<| {'a': {'b': 1}} |>` is one slot. 22 error codes still: `tdl-duplicate-variable` is new.
- `For` takes several loop variables, `For i, item In <| enumerate(items) |> Key <| item.id |> { }`:
  `For.variables` (a tuple; `For.variable` is the first), `with_variable("i, item")` or a sequence;
  `canonical()` writes a list for two or more names.

### Added

- Block edits: `Block.without_property(key)`, `Block.with_child(block_text, index=None)` (returns the
  new document and the new block), `Block.without_child(child)` and `Block.move_child(child, to)`.
  Comments, order and layout of everything untouched stay byte for byte; the reread result is
  checked. Errors in `block_text` carry origins inside the text.
- `Block.index_path` (also on `If` and `For`) and `Document.at(index_path)`: an address by position
  that survives edits, for blocks without a `Name:`.
- 12 new edit cases in the corpus (`without_property`, `with_child`, `without_child`, `move_child`;
  G35).
- `If.with_condition(slot_text)`, `For.with_items(slot_text)`, `For.with_key(slot_text)` and
  `For.with_variable(name)`: replace a slot or the loop variable in place (G37). The slot is given with
  its braces; errors in it carry origins inside the text. `with_variable` does not rename references
  in slots. Only the named bytes change and every `index_path` stays valid. 9 new corpus edit cases;
  edits inside an `Else` are tested.
- The formatter: `format_block(text)` (one block, as a string) and `format(document)` (a new
  `Document`), writing the canonical layout of `docs/api.md` (G36): two spaces a level, one entry per
  line, comments and blank lines kept, values written as they were. Idempotent; the result is
  reread and must hold the same content and comments.

## 0.1.1

### Breaking: the import name is `tess_dl`

The package is now imported as `tess_dl`, to avoid a clash with another project's top-level `tdl`.
The PyPI name is unchanged (`pip install tesserae-dl`). To migrate, change `import tdl` to
`import tess_dl` and `tdl.` to `tess_dl.` (or `import tess_dl as tdl`). There is no `tdl` alias.

Unchanged: the error codes (`tdl-unclosed-block` and the rest), the `.tdl` file extension and the
language itself. The hint of `tdl-unsupported-version` now says to use a newer `tesserae-dl`.

## 0.1.0

The first release: everything in the first-slice plan, steps 1 to 8.

### The language

- A file is a metadata block (`TDL:`, `Name:` and other keys) and exactly one root block. Blocks,
  properties, `If`/`Else`/`For`, comments, and the values word, string, number, percentage, call,
  list, `{{ slot }}` and template. The reference is `docs/language.md`; the 32 decisions behind it
  are in `docs/decisions.md`.
- 22 error codes with a plain message, a hint and a position (18 language codes and four for
  what the library will not read: `tdl-too-large`, `tdl-too-deep`, `tdl-unsupported-version`,
  `tdl-bad-encoding`).

### The library

- `loads`, `load`, `parse`, `dumps`, `dump`. `parse` never raises for a syntax error: it returns the
  best tree it could build and every error found, in source order, up to 50.
- A lossless tree: `Document`, `Metadata`, `Block`, `Property`, `If`, `For`, `Comment` and the value
  classes, immutable and carrying where they came from. `dumps(loads(text)) == text`, byte for byte:
  comments, blank lines, indentation, `\n` and `\r\n` per line, a byte-order mark and a missing
  final newline are all kept.
- Edits that change only the bytes they name: `Document.with_metadata`, `without_metadata`,
  `replace` and `Block.with_property`, and `Document.find` for a dotted path of `Name:` values. An
  edit that would break the file raises and returns nothing.
- `Limits`: 1 MiB of text, 50 errors, 64 levels of nesting.
- Python 3.14 or later, no dependencies, typed (`py.typed`).

### The conformance corpus

- `tests/corpus/`: 54 valid files with their normalised content, 57 files with errors and their
  positions, 13 edits with their results. It ships in the source distribution.

### Measured

- A 100 KB file reads in 13 ms and a file at the 1 MiB limit in 140 ms; time grows linearly, and no
  input built to be slow (`benchmarks/bench.py`) is super-linear. See `docs/benchmarks.md`.

### Not in this release

- Checking keys or types against a schema, and anything that knows what a block means: that is the
  program that reads the file.
- Building a tree in code and formatting it, `canonical()` on such a tree, `to_data()`, a command
  line, a TextMate grammar and a language server (`docs/api.md`, open questions).
- `Block.properties`, `Block.blocks`, `Block.get`, `Block.walk` and `Document.imports`, listed in
  `docs/api.md` but in no step of the first slice.
