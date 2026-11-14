# TDL

TDL, the Tesserae Data Language, is a small structure-only language for the files the Tesserae
Shell reads: blocks, properties and values. `tess_dl` is the Python library that reads it into a
tree that keeps everything in the file (comments, layout, positions), reports every mistake with
`file:line:column`, and writes the text back unchanged except for an edit you ask for.

!!! note "Status"
    Alpha: package 0.1.1 (language 0.1; `main` reads language 0.2, which writes slots `<| |>`, unreleased). The API may change before 1.0 (a minor version may
    break it; see [Versioning](versioning.md)). The import name is `tess_dl`; the 0.1.0 release
    imported as `tdl`.

`tess_dl` needs Python 3.14 or later and has no dependencies:

```sh
pip install tesserae-dl
```

```python
import tess_dl

text = """\
---
TDL: 0.2
Name: Shell_Root
---
Shell {
  Bar { Name: Top_Bar, Height: 32 }   # pixels
}
"""

doc = tess_dl.loads(text, path="Main_Shell.tdl")  # raises TDLSyntaxError on the first mistake
doc.find("Shell_Root.Top_Bar").name  # 'Top_Bar'
assert tess_dl.dumps(doc) == text  # the exact text back, byte for byte

result = tess_dl.parse(text.replace("Height: 32", "Height 32"))  # never raises
[str(e) for e in result.errors]  # every error, in source order, up to 50

doc2 = doc.with_metadata("UID", "0192d3c4")  # one edit: every other byte is unchanged
```

## Where to read next

| If you want | Read |
|---|---|
| The language: files, blocks, values, slots, `If`/`For`, comments, the 22 error codes | [Language](language.md) |
| The Python API: functions, the tree, edits, errors, limits | [API](api.md) |
| Why a rule is the way it is | [Decisions](decisions.md) |
| How fast it is, and how that was measured | [Benchmarks](benchmarks.md) |
| Package and language versions, and how a release is made | [Versioning](versioning.md) |
| The brief the first release was built from | [First slice](first-slice.md) |

## The conformance corpus

The files and expected results that define the language live in `tests/corpus/` in the
[repository](https://github.com/mindderivative/tess-dl/tree/main/tests/corpus): valid files with their
normalised content, files with each error and its position, and edits with their result. It ships in
the source distribution (not the wheel) as test data.

## Licence

[MIT](https://github.com/mindderivative/tess-dl/blob/main/LICENSE)
