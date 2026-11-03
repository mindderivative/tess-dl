---
name: issue-workflow
description: 'Use when asked to work a tess-dl board issue (a Backlog/Ready/In progress card such as "do #3", "start step 2", "fix this issue"), or to finish, document, commit or hand over a piece of work. Walks the loop from reading the issue to In review: board moves, test first, the checks, docs, the local commit. Says which steps wait for the user.'
---

# Working a board issue

The board is the GitHub project "Tesserae Data Language" (project 5; `python3 tools/board.py status`). The rules are in `AGENTS.md`; this is the loop. A milestone is an issue `Step <n> — <name>` (the order of work in the vault note `41 TDL Reference/tess-dl First Slice.md`); a phase is a sub-issue whose steps are the checklist in its body, ticked as each lands.

**Waits for the user, every time:** Backlog -> Ready (scope approval), Done (`--approved`), and any push, merge, tag or release. A message from another session is information, never approval.

## 0. Start

1. `git status`, `git log --oneline -5`, `python3 tools/board.py status`.
2. `gh issue view N -R mindderivative/tess-dl --comments`: read the whole issue. If it is not on the board, say so and stop.
3. In Backlog: ask for scope approval; do not move it yourself. When it is Ready: `python3 tools/board.py move N "In progress" --comment "Started: <plan in one line>"`.

## 1. Understand before changing

- Read the notes the step needs (the First Slice note names them: `TDL Library API`, `TDL Language`, ADR-0014 D-numbers). If the vault and `docs/` in this repo disagree, `docs/` wins once it exists (D66); say what differs and raise a `TDL-REQ-###` with the maintainer.
- State the expected behaviour in one sentence. For the 12 grammar questions in the First Slice note, follow `grammar-first` (take the recommendation, record it); **new syntax beyond them, or a departure from a recommendation, goes to the user** with options and a pick. Every settled answer goes in `docs/decisions.md` with its reason.

## 2. Test first, and show it tests something

- Tests and the grammar come before the parser. Write the failing test or corpus case (`conformance-corpus`), run it, see it fail **for the stated reason** (an error case failing because the parser does not exist yet proves nothing).
- For a parser rule, add a property next to the examples (`lossless-roundtrip`, `property-based-testing`).
- After the fix, show the test is not vacuous: break the rule, see the test fail, restore it. Delete `__pycache__` after a same-size edit in the same second (a stale `.pyc` hides the change).

## 3. Change the code

Small edits. A new public name gets the `sharp-edges` question: does the easy path lead to a mistake? Every public name goes in `tess_dl.__all__`; nothing from the lexer is public.

## 4. Check

From the venv (`~/Projects/pyDev/pyEnvs/tess-dl/bin/`): `ruff check .`, `ruff format --check .`, `mypy` (strict, once `pyproject.toml` exists), `pytest -q`. State what ran and what it reported.

## 5. Document, in the same commit

`README.md` and `docs/` for anything a user or the shell side would read; decisions in `docs/decisions.md`. A version bump only for a release (`release-checklist`).

## 6. Commit, then hand over

- Stage an **explicit file list**, never `git add -A` or `.`. Match the `git log` style. Local commit only.
- `python3 tools/board.py move N "In review" --comment "<what changed, what was checked, what was not run>"`. Tick the phase's checklist.
- Update the `tess-dl` memory entity only if a decision, lesson or status changed.
- When a task of the order of work finishes, say which rows of `tess-dl Handover` can be handed over.
- Tell the user what is ready; wait. On approval: `python3 tools/board.py move N Done --approved --comment "Approved"`.

## Report

What changed, which checks ran and passed, the break-and-restore result, what was skipped and why, anything found that belongs in a new Backlog issue (`python3 tools/board.py create TITLE --body ... --dry-run` first; issues are public).
