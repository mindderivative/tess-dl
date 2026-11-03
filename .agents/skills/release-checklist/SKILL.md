---
name: release-checklist
description: 'Use only when the user asks for a tess-dl release or a PyPI publish (plan step 9, tesserae-dl 0.1.0): version, changelog, build, clean-install smoke test, TestPyPI, tag, PyPI.'
---

# Release checklist

**Every step that publishes (push, tag, TestPyPI/PyPI upload, GitHub release) waits for the user.** Never approve the `pypi` environment; the user does. Build tooling and CI follow the `tess-el` project (`../tess-el/.github/workflows/ci.yml` and `release.yml`, Trusted Publishing on a `vX.Y.Z` tag) unless there is a reason not to; the language version (`0.1`) is separate from the package version.

1. **Ready?** `python3 tools/board.py status`: nothing In progress or In review for this release.
2. **Version:** `version` in `pyproject.toml` and `__version__` in `src/tess_dl/__init__.py` must match; `tess_dl.LANGUAGE_VERSION` stays `"0.1"` unless the language changed. SemVer; before 1.0 a minor may change the API and the changelog says how.
3. **Changelog and docs:** a `CHANGELOG.md` section, `README.md` and `docs/` current (language reference, error codes, versioning), the corpus listed as shipped test data.
4. **Checks:** `ruff check .`, `ruff format --check .`, `mypy` (strict), `pytest -q` pass on Python 3.14; CI is green on `main` (`gh run list -R mindderivative/tess-dl`). The acceptance criteria of `TDL Library API` each have a passing test.
5. **Build:** `uv build --out-dir /tmp/tess-dl-dist`; inspect wheel and sdist (`unzip -l`, `tar tf`): `src/tess_dl`, `py.typed`, `LICENSE` (MIT, "Mind Derivative"), the corpus if it ships; nothing from `.agents`, `.claude`, `.omp`, `tools` or notes that should not ship.
6. **Clean-install smoke test:** a new venv on 3.14, install the wheel, `python -I -c "import tess_dl; print(tess_dl.__version__, tess_dl.LANGUAGE_VERSION)"`, run the round trip on a corpus file, and confirm importing `tess_dl` imports no third-party package and none of TEL, tre (`tess_re`, formerly `tre`) or the shell.
7. **TestPyPI** first (user runs or approves), then install from it into a clean venv.
8. **Tag** `vX.Y.Z` (annotated; user approves), push the tag, **PyPI** upload (user approves), GitHub release notes.
9. **After:** tell the user the version to pin and which `tess-dl Handover` rows can move; move the cards to Done with `--approved`; update the memory entity.
