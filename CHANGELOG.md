# Changelog

All notable changes to the package. Versions follow [Semantic Versioning](https://semver.org); below
1.0 a minor version may break the API. The language version is separate and is 0.1 for every release
here (`docs/versioning.md`).

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
