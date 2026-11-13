# Versioning

Two version numbers, kept apart:

- **Package version** (`tess_dl.__version__`, `pyproject.toml`): [Semantic Versioning](https://semver.org).
  Below 1.0, a minor bump may break the API; the changelog says how.
- **Language version** (`tess_dl.LANGUAGE_VERSION`, `"0.1"`): what a file declares in its metadata
  (`TDL: 0.1`) so later language changes do not break old files. A file declares a major and a
  minor; a file whose major is newer than the library's is `tdl-unsupported-version`. The package
  patch number never changes the language. Until 1.0 a minor bump may change the language.

The two numbers are independent: package `0.1.0` and language `0.1` are both correct today.

The PyPI name is `tesserae-dl`; the import name is `tess_dl` and the repository is `tess-dl`. Every
release is described in `CHANGELOG.md`; the steps to make one are in the `release-checklist` skill,
and everything in it that publishes waits for the maintainer.

Releases are git tags `vX.Y.Z`. Consumers such as the Tesserae Shell pin an exact `tesserae-dl` version.
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
5. **Release:** with `pyproject.toml`, `tess_dl.__version__` and a `CHANGELOG.md` section agreeing, push
   the tag: `git tag v0.1.0 && git push origin v0.1.0`. The workflow checks that the three agree and
   that the tag is `v` plus the version, runs the checks, builds, publishes to PyPI after the `pypi`
   environment is approved, and then creates the GitHub release from the changelog section.

A version cannot be uploaded to PyPI twice: a mistake means the next version number.

## The documentation site

`docs/` is published with MkDocs (Material theme) to <https://mindderivative.github.io/tess-dl/> by
`.github/workflows/docs.yml` on every push to `main` that changes `docs/`, `mkdocs.yml` or
`pyproject.toml`. It is not a release: nothing is uploaded to PyPI. GitHub Pages is set to deploy
from that workflow (*Settings → Pages → Source: GitHub Actions*). Build it locally with
`uv pip install --group docs` and `mkdocs serve`; CI builds it with `--strict`, so a broken link
fails the build.

## Releases under the Tesserae Shell Directive

While the maintainer's Tesserae Shell Directive (2026-11-13) stands, no version tag, PyPI upload or
GitHub release is made without the maintainer. Work goes to `feat/<id>` or `fix/<id>` branches and is
merged into `main` by pull request once the CI jobs `test`, `lint`, `package` and `docs` pass; `main`
is protected so that this holds for everyone. The Release workflow and the `pypi` environment's
required reviewer are unchanged.
