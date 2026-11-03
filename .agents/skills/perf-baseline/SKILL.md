---
name: perf-baseline
description: 'Use for TDL performance work (plan step 8): measuring parse time against the budget, the 1 MiB / 50 errors / depth 64 limits, memory per tree, and recording results. Not for tuning before the behaviour tests pass.'
---

# Performance and limits

The budget (TDL Library API, "Performance Budget", proposed, to be measured on the first slice): a 100 KB file parses in under 20 ms; a file at the 1 MiB limit in under 250 ms; one pass over the text, no copy beyond the tree; no thread, no timer. `loads` of the same text twice gives equal documents (caching is the shell's business). Until a number is measured on this machine the budget is a target, not a result: **do not claim a speed-up or a pass without a number.**

## Limits (`tdl.Limits(max_bytes=1_048_576, max_errors=50, max_depth=64)`)

- Over `max_bytes`: `tdl-too-large`, **before** any parsing work (check the length first). One byte under parses; one byte over raises. Build the input in the test.
- Over `max_errors`: the list stops at 50 and the last entry says so; recovery stops doing work after the cap.
- Over `max_depth` (proposed): `tdl-too-deep`. The parser must not use Python recursion proportional to depth that can hit the interpreter limit before 64, and a test with 10,000 nested braces must raise `tdl-too-deep`, never `RecursionError`.
- Adversarial inputs: many `{{`, a very long line, a long run of `}`, a huge list, deeply nested lists. None may take super-linear time.

## Measure

- A script under `benchmarks/` (not shipped; nothing under `src/` imports it), stdlib `timeit` and `tracemalloc`, no dependency. Inputs: a generated 100 KB and 1 MiB file with realistic mix (metadata, nested blocks, slots, comments), plus the worst cases above.
- Report parse time (best of N after warm-up, say N), tree memory, and time for `dumps` and for one `with_metadata`. Run on an idle machine; two runs can differ by 10%.
- Check scaling: time for 1x, 2x, 4x input should grow about linearly.

## Record

Results go in `docs/benchmarks.md` with the date, Python version, machine, commit and the exact command; update the "Performance Budgets" ledger by raising a `TDL-REQ-###` (the vault is the maintainer's). A change that speeds one case and slows another is reported with both.

## Rules

- No tuning before the behaviour tests and the round trip pass (steps 3 to 7 before 8).
- A guard that protects memory or time can look redundant for results; pin it with a `tracemalloc` or wall-clock test instead of deleting it.
- Importing `tdl` imports no third-party package, and nothing in a benchmark may be needed to import it.
