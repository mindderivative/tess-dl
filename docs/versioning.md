# Versioning

Two version numbers, kept apart:

- **Package version** (`tdl.__version__`, `pyproject.toml`): [Semantic Versioning](https://semver.org).
  Below 1.0, a minor bump may break the API; the changelog says how.
- **Language version** (`tdl.LANGUAGE_VERSION`, `"0.1"`): what a file declares in its metadata
  (`TDL: 0.1`) so later language changes do not break old files. A file declares a major and a
  minor; a file whose major is newer than the library's is `tdl-unsupported-version`. The package
  patch number never changes the language. Until 1.0 a minor bump may change the language.

The two numbers are independent: package `0.1.0` and language `0.1` are both correct today.

The PyPI name is `tesserae-dl`; the import name is `tdl` and the repository is `tess-dl`. Every
release is described in `CHANGELOG.md`; the steps to make one are in the `release-checklist` skill,
and everything in it that publishes waits for the maintainer.

Releases are git tags `vX.Y.Z`. Consumers such as the Tesserae Shell pin an exact `tdl` version.
The conformance corpus (`tests/corpus/`) is versioned with the package: it ships in the source
distribution, and a consumer that wants it reads the released one for its pinned version.

## Setting up PyPI

`.github/workflows/release.yml` publishes with PyPI's Trusted Publishing, so no token is stored. The
one-time setup, by the maintainer:

1. **PyPI:** sign in, then *Your account → Publishing → Add a new pending publisher* (a "pending"
   publisher creates the project `tesserae-dl` on its first upload). Owner `mindderivative`,
   repository `tess-dl`, workflow `release.yml`, environment `pypi`.
2. **TestPyPI** (optional, for a rehearsal): the same on test.pypi.org with environment `testpypi`.
3. **GitHub:** *Settings → Environments*: create `pypi` and `testpypi`. For `pypi`, add yourself as a
   required reviewer so that a tag never publishes without a click.
4. **Rehearse:** *Actions → Release → Run workflow* on `main` builds, tests and uploads to TestPyPI.
   Install it in a clean environment with
   `uv pip install --index-url https://test.pypi.org/simple/ tesserae-dl`.
5. **Release:** with `pyproject.toml`, `tdl.__version__` and a `CHANGELOG.md` section agreeing, push
   the tag: `git tag v0.1.0 && git push origin v0.1.0`. The workflow checks that the three agree and
   that the tag is `v` plus the version, runs the checks, builds, publishes to PyPI after the `pypi`
   environment is approved, and then creates the GitHub release from the changelog section.

A version cannot be uploaded to PyPI twice: a mistake means the next version number.
