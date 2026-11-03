# Skills

Project skills for agents. `.claude/skills` is a symlink to this directory.

| Skill | Use for | Source |
|---|---|---|
| `issue-workflow` | Working a board issue from Ready to In review | Written for this project (loop from `tess-el`). |
| `grammar-first` | The grammar, `docs/language.md`, the 12 ambiguities, error wording | Written for this project. |
| `conformance-corpus` | `tests/corpus/` cases, the 17 error codes, shell `TDL-REQ`s | Written for this project. |
| `lossless-roundtrip` | Spans, `dumps`, edit calls, round-trip and edit properties | Written for this project. |
| `perf-baseline` | The budget, limits and benchmarks (step 8) | Written for this project. |
| `release-checklist` | `tesserae-dl` 0.1.0 and later releases (step 9) | Written for this project (steps from `tess-el`). |
| `property-based-testing` | Hypothesis properties (round trip, idempotence, no-crash) | [trailofbits/skills](https://github.com/trailofbits/skills) `plugins/property-based-testing` (commit `196a9073`, 2026-10-25), copied from `tess-el`: unchanged except that `README.md`, `assets/` and `agents/` were dropped. CC-BY-SA-4.0; the licence text is in `LICENSE-trailofbits`. |
| `sharp-edges` | API misuse review of each new public name | Same repository and commit, `plugins/sharp-edges`, copied from `tess-el` the same way. Same licence. Only `references/lang-python.md` and `references/config-patterns.md` matter here. |
| `python-testing-patterns` | pytest fixtures and parametrisation | Installed globally in `~/.agents/skills/`. |

The third-party skills were read in full before they were added to `tess-el`; they are plain Markdown with no scripts. The `.graphifyignore` leaves their text out of the code graph.
