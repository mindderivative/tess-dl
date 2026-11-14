---
name: conformance-corpus
description: 'Use when adding, changing or running cases in tests/corpus/ (plan step 2 and after): the .tdl + .expect.json case format, the areas, the 22 error codes, edit and limit cases, answering a shell TDL-REQ, and checking a new case fails for the right reason.'
---

# The conformance corpus

`tests/corpus/` is owned by `tess-dl`; the shell reads it and does not edit it. The shell proposes a case as a `TDL-REQ-###` with the input text and the expected result; `tess-dl` adds, changes or declines it (D92). It is built **before the parser** (step 2) and every case must fail for the right reason first.

## A case is two files

| File | Content |
|---|---|
| `<area>/<case>.tdl` | The input text, exactly (CRLF, BOM, tabs and a missing final newline are part of the case) |
| `<area>/<case>.expect.json` | `{"ok": true, "canonical": {...}}` (normalised content: no positions, no comments) or `{"errors": [{"code": "...", "line": N, "column": N}]}` |

Areas: `metadata`, `blocks`, `values`, `slots`, `strings`, `comments`, `structure` (`If`, `Else`, `For`), `errors`, `edits`, `limits`. Names say what the case shows (`errors/unclosed-block.tdl`), not a number.

Each case is as small as it can be and shows **one** thing. Lines and columns are 1-based, columns counted in characters (not bytes); the byte `offset` is not in the file.

## What the runner checks

One parametrised pytest module walks the folder, so a new case needs no test code:

- `ok`: `loads` succeeds and `canonical()` equals the expectation (step 3, `test_ok_case_reads_to_the_canonical_tree`); `dumps(loads(x)) == x` byte for byte and `dumps(load(BytesIO(data))) == x` (step 5, `test_ok_case_round_trips_byte_for_byte`). Every `ok` case is a round-trip case. See G26.
- `errors`: `loads` raises `TDLSyntaxError` with the first listed code, line and column; `parse` returns the whole list (up to 50), in source order.
- `edits`: three files per case (G23): `<case>.tdl`, `<case>.expect.json` with `{"edit": {"call": "with_metadata|without_metadata|with_property|replace|without_property|with_child|without_child|move_child|with_items|with_key|with_condition|with_variable", ...}}` (the block calls take `block`, a dotted `find` path; the `If` and `For` calls take `at`, an index path) (a refused edit adds `"raises": "<code>"` and has no result file) and `<case>.result.tdl`, the expected output bytes. The edit changes no other byte (`lossless-roundtrip`).
- A `.tdl` with no `.expect.json`, or the reverse, fails the run.
- `tdl-bad-encoding` and BOM/CRLF cases are raw bytes: never open `.tdl` in text mode.

## The error codes: one minimal file each (18 language codes and 4 limit/input codes)

`tdl-no-metadata`, `tdl-metadata-unclosed`, `tdl-no-version`, `tdl-no-name`, `tdl-bad-name`, `tdl-no-root`, `tdl-many-roots`, `tdl-unclosed-block`, `tdl-unexpected-close`, `tdl-unclosed-slot`, `tdl-empty-slot`, `tdl-unclosed-string`, `tdl-bad-escape`, `tdl-duplicate-key`, `tdl-duplicate-variable`, `tdl-bare-hash`, `tdl-unexpected-text` (G13; one case for each kind of mistake it covers), `tdl-reserved-name`. The "points at" column of the First Slice note is the proposal; fix the exact position when the case is written, and for `tdl-duplicate-key` put the first key in `related`. The four accepted extras (G18): `tdl-unsupported-version`, `tdl-too-large`, `tdl-too-deep`, `tdl-bad-encoding`.

Also one case per language-level line of `TDL Language#Acceptance Criteria` (for example `<| '|>' |>` ends at the second `|>`; `Color: "#fff"   # note` is a string and a comment) and per `TDL Library API` acceptance criterion; the six-mistake file for `parse`.

## Adding a case: the order

1. Write the `.tdl` and `.expect.json` from the **spec** (`docs/language.md`, or the vault note until it exists), not from what the parser does today.
2. Run it and see it fail **for the stated reason**: a missing feature (`ok` case), a wrong code or position (error case). A case that fails because the runner or the file is broken is not yet a case.
3. Once the parser passes it, break the rule on purpose and see this case (and not only some other) fail. Restore.
4. Never "fix" an expectation to match the parser without saying so: an expectation is a claim about the language.

## Other rules

- `Limits` cases (1 MiB, 50 errors, depth 64) build their big input in the test, not in a 1 MiB file in git.
- The corpus is test data that ships with a release (the shell installs it or copies a released version), so keep it free of local paths and secrets and keep names stable once released.
- A case the shell proposed and `tess-dl` declines gets a short reply naming the rule that decides it.
