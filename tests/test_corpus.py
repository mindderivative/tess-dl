"""The conformance corpus runner: one parametrised test per case in `tests/corpus/`.

`tess_dl` is imported inside each test so the corpus can be collected before the package exists.
Files are read as bytes: CRLF, BOM and invalid UTF-8 are part of the cases.
"""

import io
import json
from pathlib import Path

import pytest

CORPUS = Path(__file__).parent / "corpus"


def collect(area_filter):
    rows = []
    for path in sorted(CORPUS.rglob("*.expect.json")):
        area = path.parent.name
        if area_filter(area):
            rows.append((area, path.name[: -len(".expect.json")], path))
    return rows


def ids(rows):
    return [f"{area}/{case}" for area, case, _ in rows]


OK = collect(lambda a: a not in {"errors", "edits"})
ERRORS = collect(lambda a: a == "errors")
EDITS = collect(lambda a: a == "edits")


def read(path, suffix=".tdl"):
    return path.with_name(path.name[: -len(".expect.json")] + suffix).read_bytes()


def triples(errors):
    return [(e.code, e.origin.line, e.origin.column) for e in errors]


def related(error):
    return [(o.line, o.column) for o in error.related]


def same(actual, expected):
    return json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)


@pytest.mark.parametrize(("area", "case", "path"), OK, ids=ids(OK))
def test_ok_case_reads_to_the_canonical_tree(area, case, path):
    import tess_dl

    text = read(path).decode("utf-8")
    expected = json.loads(path.read_text("utf-8"))
    doc = tess_dl.loads(text, path=f"{area}/{case}.tdl")
    assert same(doc.canonical(), expected["canonical"])


@pytest.mark.parametrize(("area", "case", "path"), OK, ids=ids(OK))
def test_ok_case_round_trips_byte_for_byte(area, case, path):
    import tess_dl

    data = read(path)
    text = data.decode("utf-8")
    doc = tess_dl.loads(text, path=f"{area}/{case}.tdl")
    assert tess_dl.dumps(doc) == text
    assert tess_dl.dumps(tess_dl.load(io.BytesIO(data))) == text


def wanted(path):
    return json.loads(path.read_text("utf-8"))["errors"]


def first(error):
    return (error.code, error.origin.line, error.origin.column)


TEXT_ERRORS = [r for r in ERRORS if r[1] != "bad-encoding"]


@pytest.mark.parametrize(("area", "case", "path"), TEXT_ERRORS, ids=ids(TEXT_ERRORS))
def test_error_case_loads_raises_the_first_listed_error(area, case, path):
    """Step 4: `loads` stops at the first mistake with its code, position and related origins."""
    import tess_dl

    expected = wanted(path)[0]
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        tess_dl.loads(read(path).decode("utf-8"), path=f"{area}/{case}.tdl")
    error = raised.value
    assert first(error) == (expected["code"], expected["line"], expected["column"])
    assert related(error) == [(r["line"], r["column"]) for r in expected.get("related", [])]
    assert error.message and error.hint
    assert str(error) == (
        f"{area}/{case}.tdl:{error.origin.line}:{error.origin.column}: "
        f"{error.message} ({error.hint})"
    )


@pytest.mark.parametrize(("area", "case", "path"), ERRORS, ids=ids(ERRORS))
def test_error_case_load_raises_the_same_first_error(area, case, path):
    """Step 5: `load` reads bytes, so it also covers `bad-encoding`."""
    import tess_dl

    expected = wanted(path)[0]
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        tess_dl.load(io.BytesIO(read(path)))
    assert first(raised.value) == (expected["code"], expected["line"], expected["column"])
    assert related(raised.value) == [(r["line"], r["column"]) for r in expected.get("related", [])]


@pytest.mark.parametrize(("area", "case", "path"), TEXT_ERRORS, ids=ids(TEXT_ERRORS))
def test_error_case_parse_lists_every_listed_error(area, case, path):
    """Step 7: `parse` returns the whole list, in source order."""
    import tess_dl

    expected = wanted(path)
    errors = tess_dl.parse(read(path).decode("utf-8")).errors
    assert [first(e) for e in errors] == [(e["code"], e["line"], e["column"]) for e in expected]
    assert [related(e) for e in errors] == [
        [(r["line"], r["column"]) for r in e.get("related", [])] for e in expected
    ]


def apply(doc, edit):
    call = edit["call"]
    if call == "with_metadata":
        return doc.with_metadata(edit["key"], edit["value"])
    if call == "without_metadata":
        return doc.without_metadata(edit["key"])
    if call == "with_property":
        return doc.find(edit["block"]).with_property(edit["key"], edit["value"])
    if call == "replace":
        return doc.replace(edit["start"], edit["end"], edit["text"])
    if call == "without_property":
        return doc.find(edit["block"]).without_property(edit["key"])
    if call == "with_child":
        return doc.find(edit["block"]).with_child(edit["text"], edit["index"])[0]
    if call == "without_child":
        return doc.find(edit["block"]).without_child(edit["index"])
    if call == "move_child":
        return doc.find(edit["block"]).move_child(edit["index"], edit["to"])
    raise AssertionError(f"unknown edit call {call}")


@pytest.mark.parametrize(("area", "case", "path"), EDITS, ids=ids(EDITS))
def test_edit_case_changes_only_what_it_must(area, case, path):
    import tess_dl

    text = read(path).decode("utf-8")
    expected = json.loads(path.read_text("utf-8"))
    doc = tess_dl.loads(text)
    if "raises" in expected:
        with pytest.raises(tess_dl.TDLError) as raised:
            apply(doc, expected["edit"])
        assert raised.value.code == expected["raises"]
        assert tess_dl.dumps(doc) == text
    else:
        result = apply(doc, expected["edit"])
        assert tess_dl.dumps(result) == read(path, ".result.tdl").decode("utf-8")
        assert tess_dl.dumps(doc) == text
