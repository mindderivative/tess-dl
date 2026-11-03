"""The conformance corpus runner: one parametrised test per case in `tests/corpus/`.

`tdl` is imported inside each test so the corpus can be collected before the package exists.
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
    import tdl

    text = read(path).decode("utf-8")
    expected = json.loads(path.read_text("utf-8"))
    doc = tdl.loads(text, path=f"{area}/{case}.tdl")
    assert same(doc.canonical(), expected["canonical"])


@pytest.mark.parametrize(("area", "case", "path"), OK, ids=ids(OK))
def test_ok_case_round_trips_byte_for_byte(area, case, path):
    import tdl

    data = read(path)
    text = data.decode("utf-8")
    doc = tdl.loads(text, path=f"{area}/{case}.tdl")
    assert tdl.dumps(doc) == text
    assert tdl.dumps(tdl.load(io.BytesIO(data))) == text


@pytest.mark.parametrize(("area", "case", "path"), ERRORS, ids=ids(ERRORS))
def test_error_case_reports_the_listed_errors(area, case, path):
    import tdl

    data = read(path)
    expected = json.loads(path.read_text("utf-8"))["errors"]
    wanted = [(e["code"], e["line"], e["column"]) for e in expected]
    wanted_related = [[(r["line"], r["column"]) for r in e.get("related", [])] for e in expected]

    # `load` reads bytes, `loads` reads text; both must raise the first error.
    # `bad-encoding` has no text form, so only `load` applies.
    with pytest.raises(tdl.TDLSyntaxError) as raised:
        tdl.load(io.BytesIO(data))
    first = raised.value
    assert (first.code, first.origin.line, first.origin.column) == wanted[0]
    assert related(first) == wanted_related[0]
    if case == "bad-encoding":
        return

    text = data.decode("utf-8")
    with pytest.raises(tdl.TDLSyntaxError) as raised_text:
        tdl.loads(text)
    assert (
        raised_text.value.code,
        raised_text.value.origin.line,
        raised_text.value.origin.column,
    ) == wanted[0]
    result = tdl.parse(text)
    assert triples(result.errors) == wanted
    assert [related(e) for e in result.errors] == wanted_related


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
    raise AssertionError(f"unknown edit call {call}")


@pytest.mark.parametrize(("area", "case", "path"), EDITS, ids=ids(EDITS))
def test_edit_case_changes_only_what_it_must(area, case, path):
    import tdl

    text = read(path).decode("utf-8")
    expected = json.loads(path.read_text("utf-8"))
    doc = tdl.loads(text)
    if "raises" in expected:
        with pytest.raises(tdl.TDLError) as raised:
            apply(doc, expected["edit"])
        assert raised.value.code == expected["raises"]
        assert tdl.dumps(doc) == text
    else:
        result = apply(doc, expected["edit"])
        assert tdl.dumps(result) == read(path, ".result.tdl").decode("utf-8")
        assert tdl.dumps(doc) == text
