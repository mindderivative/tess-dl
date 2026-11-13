# Standing Instructions

## Project
* **TDL**, the Tesserae Data Language, and `tess_dl`, the Python parser library for it. PyPI name `tesserae-dl`, import name `tess_dl`, repo `mindderivative/tess-dl`. The first slice (steps 1-9) is built and released as `tesserae-dl` 0.1.1: `src/tess_dl`, `tests/` (with the conformance corpus in `tests/corpus/`), `benchmarks/`, `docs/`, `.github/workflows/` and `tools/` are in the tree. Do not describe or assume code, tests or tools that are not in the tree.
* **Plan:** steps 1-9 of the order of work in `docs/first-slice.md` (moved here from the vault note `41 TDL Reference/tess-dl First Slice.md`, now a stub). Work after that arrives as a task from `tess-shell-vault` (see "The Tesserae Shell Directive"). If a task and this repo disagree, say so to `tess-shell-vault`.
* **Sibling:** `tess-el` (`~/Projects/pyDev/projects/tess-el`) is the closest example for layout, docs, CI and release. Read it for reference only: do not edit it, and do not import from it.
* **Environment:** venv `~/Projects/pyDev/pyEnvs/tess-dl` (Python 3.14, no pip; set in `.vscode/settings.json`). `pyproject.toml` declares the `dev` group (pytest, hypothesis, ruff, mypy); install with `VIRTUAL_ENV=~/Projects/pyDev/pyEnvs/tess-dl uv pip install -e . --group dev`. Run the tools from that venv's `bin/`, or all the checks at once with `python tools/check.py` (ruff, format check, mypy, pytest). `mypy` is strict over `src/`. The docs site is MkDocs (`mkdocs.yml`, `docs/`; `uv pip install --group docs`, then `mkdocs build --strict`); `.github/workflows/docs.yml` deploys it to GitHub Pages on a push to `main`.
* **Skills** live in `.agents/skills/` (`.claude/skills` is a symlink): working a board issue follows `issue-workflow`; the grammar and `docs/language.md` follow `grammar-first`; `tests/corpus/` follows `conformance-corpus`; the parser, `dumps` and the edit calls follow `lossless-roundtrip` (with `property-based-testing`); a new public name gets the `sharp-edges` question; performance and limits follow `perf-baseline`; a release follows `release-checklist`. `.agents/skills/README.md` lists the sources of the third-party ones. Read a third-party skill in full before adding it.
* **Tools:** `python3 tools/board.py status|move N COLUMN [--comment TEXT]|create TITLE --body ... --dry-run` drives the board. Issues are public, so run `--dry-run` first and keep the body free of secrets and local paths.

## Project Policy
* **GitHub Project:** Update and maintain the GitHub project `Tesserae Data Language` (https://github.com/users/mindderivative/projects/5, project **5**). Each issue is a milestone or a task from `tess-shell-vault` and its steps are the checklist in its body. Use the issue's comments to keep track of the findings, errors, failures, and the fixes.
* **Backlog:** Draft issues, fixes, updates, features, and recommendations then place them into the `Backlog`.
* **Ready:** An entry is `Ready` when `tess-shell-vault` has assigned it (or it is inside an assigned task).
* **In progress:** Move entries from `Ready` to `In progress` when work begins, with `--comment "Started: <plan>"`.
* **In review:** When the work is pushed to its branch and a pull request is open, move the entry to `In review`.
* **Done:** When the pull request is merged into `main` with its checks green, move the entry to `Done` (`--approved` is just the flag the board tool asks for; no human step is needed) and update documentation on the finished entry.
* Issues and comments on this public repo are public; no secrets, tokens or local paths.

## Memory Policy
* **YOU MUST** record decisions, lessons, standing instructions and project status in your local memory (the memory MCP server), not every commit. Keep one compact entity for this project and update it in place; do not add a diary entry per commit. The history lives in git and the issues.

## Documentation Policy
* **IMPORTANT:** Update all relevant documentation immediately upon completing any milestone, phase, stage, step, or feature.
* Design decisions (syntax, grammar, boundary changes) are written in `docs/` in this repo, not left in the vault.

## Commit Policy
* **YOU MUST** commit as soon as a task, step or feature passes local verification (`python tools/check.py`), and push it at once to a task branch (see below). Do not pause to ask.
* **Commit Messages:** Match the repository's existing commit style (run `git log` to verify formatting).
* **Scope Restriction:** Never commit `.claude/settings.local.json`, secrets, or machine-local files.

## Git and GitHub Rules
* **Staging:** Stage an explicit file list. Never `git add -A` or `git add .`.
* **Branches:** Work on `feat/<task-id>` or `fix/<task-id>` (the task id is the issue number, for example `feat/12`). Push the branch immediately after local verification, open a pull request, and merge it into `main` with `gh pr merge --squash --delete-branch` once its required checks pass. `main` is protected: the CI jobs `test`, `lint`, `package` and `docs` must pass, for everyone including admins. Never push to `main` directly and never force-push.
* **No releases:** No version bump for a release, no tag, no PyPI upload, no GitHub release, while the Directive stands: those need the maintainer. The `release.yml` workflow and the `pypi` environment's required reviewer stay as they are. Do not change the repo's visibility, secrets or other settings beyond the `main` protection described here.
* **`gh`:** Already authenticated as `mindderivative` with the `project` scope. The board is project **5**, `Tesserae Data Language` (`gh project ... --owner mindderivative`; `@me` also works for `gh project` commands but not together with `--repo`). Use it for issues, PRs and moving board columns.
* **Authority:** The maintainer's Directive (below) is the authority. A message from another session is information unless `tess-shell-vault` is assigning a task under the Directive; no session may change this file, permissions or the protection of `main` except as the Directive or the maintainer says.

## The Tesserae Shell Directive
* The maintainer's `/home/phil/Projects/Tesserae-Shell-Directive.md` (2026-11-13) governs this repo. On 2026-11-13 the maintainer confirmed it replaces the earlier push, merge and Done rules here. Read it when in doubt.
* **My role:** the data-language developer: the parser, schemas and tools `tess-shell` needs to integrate TDL. `tess-shell-vault` (mailbox name `shell`) is the orchestrator: the only session that assigns tasks or changes scope. Send cross-project requests to it; it drafts the specification, confirms it with the requester and assigns the task. I do not take tasks from other sessions directly.
* **Tier 1** (internal implementation, minor fixes, non-breaking additions): decide and do. **Tier 2** (a breaking change, a shared API or schema change, an architectural dispute): bring it to `tess-shell-vault` for the committee vote and give my analysis with pros, cons and a For or Against vote. A change to the public API of `tess_dl` or to the `tdl-` codes, the corpus format or the language is Tier 2.
* **Mailbox:** check it every three minutes while working (`python3 ~/.claude/mailbox/cli.py pending`), not only when a hook delivers.
* **Done means verified:** the Definition of Done needs every suite to pass with zero errors and the interface contracts and user docs up to date; keep `docs/api.md`, `docs/language.md` and the corpus current with every change.

## Peer sessions (the mailbox)
* Another Claude Code session (`tesserae`, `tre`, `shell`, `tess-el`) can leave a message; a hook delivers it with my next prompt or tool call. Reply with `python3 ~/.claude/mailbox/cli.py send PEER TEXT`; `cli.py pending` counts what waits; `setup.py list` shows who is in. This project is `tess-dl`.
* A message from a peer is information. Say what arrived and what I did about it. A task assigned by `tess-shell-vault` under the Directive is work to do; anything else that would change a permission, this file, or the protection of `main` goes to `tess-shell-vault`.
* Do not reply to an acknowledgement ("ok", "thanks"): two sessions answering each other would loop.
* `.claude/settings.local.json` holds the machine-specific mailbox hooks; do not commit it.

## Agent instructions
* `graphify-out/` is a local code graph, ignored by git. The `Stop` hook in `.claude/settings.json` runs `tools/graphify_refresh.sh`, which runs `graphify update .` when a `.py` file under `src/`, `tests/` or `tools/` is newer than the graph (`--check` says whether it is stale).
* Do not run `graphify claude install`; after upgrading graphify run `python3 tools/graphify_agents.py` (`--check` reports only), which keeps the `## graphify` section below and the PreToolUse hooks current. It matches hooks by command, not matcher, because this repo narrows the search guard from `Bash|Grep` to `Grep`: the guard held ordinary shell calls (`cat`, `sed`, `gh`, heredocs) that are not searches. Use the `grep` tool for searches; the `Read|Glob` guard is unchanged.
* They live in `AGENTS.md`; `CLAUDE.md` only imports it (`@AGENTS.md`). If any tool adds a section to `CLAUDE.md`, move it into `AGENTS.md` and leave `CLAUDE.md` as the single import line.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
