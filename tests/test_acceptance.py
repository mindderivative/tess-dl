"""The acceptance criteria of docs/api.md that no corpus case or other test states in words.

The rest are covered where they live: the round trip, the 22 codes, `Width 32`, the six-mistakes
file and `with_metadata("UID", x)` by the corpus runner; the 1 MiB limit by `test_limits.py`.
"""

import subprocess
import sys
import types

import pytest

import tess_dl

HEAD = "---\nTDL: 0.2\nName: T\n---\n"


def read(body: str) -> tess_dl.Block:
    return tess_dl.loads(HEAD + "Shell {\n" + body + "\n}\n").root


def test_a_quoted_hash_is_a_string_and_the_comment_after_it_is_kept():
    root = read('  Color: "#fff"   # note')
    prop, comment = root.entries
    assert isinstance(prop, tess_dl.Property) and isinstance(prop.value, tess_dl.String)
    assert prop.value.value == "#fff"
    assert isinstance(comment, tess_dl.Comment) and comment.text == "note"


def test_a_bare_hash_is_refused_and_the_hint_says_to_quote_it():
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        read("  Color: #fff")
    assert raised.value.code == "tdl-bare-hash" and '"#ffffff"' in raised.value.hint


def test_a_slot_keeps_its_text_untrimmed_and_the_comma_does_not_end_the_value():
    (prop,) = read("  Text: <| max(a, b) |>").entries
    assert isinstance(prop, tess_dl.Property) and isinstance(prop.value, tess_dl.Slot)
    assert prop.value.text == " max(a, b) "
    origin = prop.value.text_origin
    assert origin is not None and (origin.line, origin.column) == (6, 11)


def test_a_slot_ends_at_the_first_close_outside_quotes_and_holds_braces():
    (prop,) = read("  Text: <| '|>' |>").entries
    assert isinstance(prop.value, tess_dl.Slot) and prop.value.text == " '|>' "
    (prop,) = read("  Text: <| {'a': {'b': 1}} |>").entries
    assert isinstance(prop.value, tess_dl.Slot) and prop.value.text == " {'a': {'b': 1}} "


def test_two_closing_braces_together_close_two_blocks():
    doc = tess_dl.loads(HEAD + "Shell {\n  Bar {\n  }}\n")
    assert doc.root.entries[0].type == "Bar"


def test_the_old_slot_form_is_refused_with_a_hint_to_the_new_one():
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        read("  Text: {{ a }}")
    assert raised.value.code == "tdl-unexpected-text" and "<|" in raised.value.message
    assert (raised.value.origin.line, raised.value.origin.column) == (6, 9)


def test_width_without_a_colon_points_at_the_first_character_that_does_not_fit():
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        read("  Width 32")
    error = raised.value
    assert (error.code, error.origin.line, error.origin.column) == ("tdl-unexpected-text", 6, 9)


def test_importing_tdl_loads_only_the_standard_library():
    """Run in a clean interpreter: no third-party package, and none of TEL, tre or the shell.

    (tre is imported as `tess_re` from its 0.6.0; any non-standard-library name fails this test.)

    Only what `import tess_dl` adds is counted: a runner may pre-load modules of its own at start-up
    (a `sitecustomize`), and those are not the library's.
    """
    code = (
        "import sys; before = set(sys.modules); import tess_dl; "
        "own = set(sys.stdlib_module_names) | {'tess_dl'}; "
        "print(sorted({m.split('.')[0] for m in set(sys.modules) - before} - own))"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True
    )
    assert done.stdout.strip() == "[]", done.stdout


def test_every_public_name_is_in_all_and_every_name_in_all_exists():
    public = {
        name
        for name, value in vars(tess_dl).items()
        if not name.startswith("_") and not isinstance(value, types.ModuleType)
    }
    assert public == set(tess_dl.__all__) - {"__version__"}
    assert tess_dl.__version__ in vars(tess_dl).values()
    assert all(hasattr(tess_dl, name) for name in tess_dl.__all__)
    assert len(tess_dl.__all__) == len(set(tess_dl.__all__))


def test_the_language_and_package_versions_are_separate_strings():
    assert tess_dl.LANGUAGE_VERSION == "0.2"
    assert tess_dl.__version__ != tess_dl.LANGUAGE_VERSION
    assert tess_dl.loads(HEAD + "Shell { }\n").language_version == "0.2"
