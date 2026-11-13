# TDL

TDL, the Tesserae Data Language, is a small structure-only language for the files the Tesserae
Shell reads: blocks, properties and values. `tess_dl` is the Python library that reads it into a tree
that keeps everything in the file (comments, layout, positions), reports every mistake with
`file:line:column`, and writes the text back unchanged except for an edit you ask for.

> **Status:** alpha, package 0.1.1, language version 0.1. The import name changed from
> `tdl` to `tess_dl` in 0.1.1 (see [`CHANGELOG.md`](CHANGELOG.md)). The API may change
> before 1.0 (a minor version may break it; see [`docs/versioning.md`](docs/versioning.md)).
> Documentation site: <https://mindderivative.github.io/tess-dl/>. The language is in [`docs/language.md`](docs/language.md), the API in [`docs/api.md`](docs/api.md),
> the reasons for the choices in [`docs/decisions.md`](docs/decisions.md).

`tess_dl` needs Python 3.14 or later and has no dependencies:

```sh
pip install tesserae-dl
```

```python
import tess_dl

text = """\
---
TDL: 0.1
Name: Shell_Root
---
Shell {
  Bar { Name: Top_Bar, Height: 32 }   # pixels
}
"""

doc = tess_dl.loads(text, path="Main_Shell.tdl")  # raises TDLSyntaxError on the first mistake
doc.root.type  # 'Shell'
doc.find("Shell_Root.Top_Bar").name  # 'Top_Bar'
assert tess_dl.dumps(doc) == text  # the exact text back, byte for byte

broken = text.replace("Height: 32", "Height 32")
result = tess_dl.parse(broken)  # never raises for a syntax error
[str(e) for e in result.errors]  # every error, in source order, up to 50

doc2 = doc.with_metadata("UID", "0192d3c4")  # one edit: every other byte is unchanged
doc3 = doc.find("Shell_Root.Top_Bar").with_property("Height", "40")
```

- `loads`, `load` (a binary file object), `parse`, `dumps`, `dump`.
- A tree of `Document`, `Metadata`, `Block`, `Property`, `If`, `For` and `Comment`, with `Word`,
  `String`, `Number`, `Percent`, `Call`, `List`, `Slot` and `Template` for values. Nodes are
  immutable, keep where they came from (`node.origin`), and are safe to share between threads.
- Edits return a new `Document` and change only the bytes they name: `with_metadata`,
  `without_metadata`, `replace`, and on a block `with_property`, `without_property`, `with_child`,
  `without_child`, `move_child`. An edit that would break the file raises. `Block.index_path` and
  `Document.at` address a block by position, `format_block` and `format` write the canonical layout.
- 22 error codes, each with a plain message, a hint and a position (`tdl-bare-hash`:
  "This colour needs quotes. Quote the colour: "#ffffff""). The list is in
  [`docs/language.md`](docs/language.md#errors).
- Limits (`tess_dl.Limits`): 1 MiB of text, 50 errors, 64 levels of nesting.
- Not in 0.1: checking keys or types (that is the program's, such as the shell), building a tree
  in code and formatting it, `to_data()`, a command line. See [`docs/api.md`](docs/api.md).

A 100 KB file reads in about 13 ms and a file at the 1 MiB limit in about 140 ms
([`docs/benchmarks.md`](docs/benchmarks.md)).

PyPI name: `tesserae-dl`. Import name: `tess_dl`.

## The conformance corpus

`tests/corpus/` holds the files and expected results that define the language: valid files with
their normalised content, files with each error and its position, and edits with their result. It
ships in the source distribution (not in the wheel) as test data, and the Tesserae Shell reads it.
New cases come from a `TDL-REQ-###` through the maintainer; see
[`.agents/skills/conformance-corpus/SKILL.md`](.agents/skills/conformance-corpus/SKILL.md).

## Development

```sh
uv pip install -e . --group dev   # into the active venv (Python 3.14+)
python tools/check.py             # ruff, format check, mypy (strict), pytest: what CI runs
python benchmarks/bench.py        # timing against the budget (docs/benchmarks.md)
mkdocs serve                      # the docs site locally (uv pip install --group docs)
```

Work is tracked on the [Tesserae Data Language board](https://github.com/users/mindderivative/projects/5)
(`python tools/board.py status`). Agent instructions are in [`AGENTS.md`](AGENTS.md); project skills
are in `.agents/skills/`.

## Versioning

See [`docs/versioning.md`](docs/versioning.md).

## Licence

[MIT](LICENSE)
