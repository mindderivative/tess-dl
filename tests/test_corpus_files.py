"""The corpus files themselves: pairing, shape, codes and positions. Needs no `tess_dl`."""

import json
from pathlib import Path

import pytest

CORPUS = Path(__file__).parent / "corpus"
AREAS = {
    "metadata",
    "blocks",
    "values",
    "slots",
    "strings",
    "comments",
    "structure",
    "errors",
    "edits",
    "limits",
}
CODES = {
    "tdl-no-metadata",
    "tdl-metadata-unclosed",
    "tdl-no-version",
    "tdl-no-name",
    "tdl-bad-name",
    "tdl-no-root",
    "tdl-many-roots",
    "tdl-unclosed-block",
    "tdl-unexpected-close",
    "tdl-double-close",
    "tdl-unclosed-slot",
    "tdl-empty-slot",
    "tdl-unclosed-string",
    "tdl-bad-escape",
    "tdl-duplicate-key",
    "tdl-bare-hash",
    "tdl-unexpected-text",
    "tdl-reserved-name",
    "tdl-too-large",
    "tdl-too-deep",
    "tdl-unsupported-version",
    "tdl-bad-encoding",
}
BUILT_IN_CODE = {"tdl-too-large", "tdl-too-deep"}  # tests/test_limits.py
EDIT_CALLS = {
    "with_metadata": {"call", "key", "value"},
    "without_metadata": {"call", "key"},
    "with_property": {"call", "block", "key", "value"},
    "replace": {"call", "start", "end", "text"},
}
VALUE_KEYS = [
    {"word"},
    {"string"},
    {"number"},
    {"percent"},
    {"call", "args"},
    {"list"},
    {"slot"},
    {"template"},
]
ENTRY_KEYS = [
    {"block", "entries"},
    {"property", "value"},
    {"if", "body", "else"},
    {"for", "in", "key", "body"},
]


def sources():
    return sorted(p for p in CORPUS.rglob("*.tdl") if not p.name.endswith(".result.tdl"))


def expectation(path):
    return json.loads(path.with_name(path.name[: -len(".tdl")] + ".expect.json").read_text("utf-8"))


SOURCES = sources()
IDS = [f"{p.parent.name}/{p.stem}" for p in SOURCES]


def test_the_corpus_is_not_empty():
    assert len(SOURCES) > 50


def test_every_file_has_its_partner():
    tdl, expect, result = set(), set(), set()
    for p in CORPUS.rglob("*"):
        if p.is_dir():
            continue
        name = p.relative_to(CORPUS).as_posix()
        if name.endswith(".expect.json"):
            expect.add(name[: -len(".expect.json")])
        elif name.endswith(".result.tdl"):
            result.add(name[: -len(".result.tdl")])
        elif name.endswith(".tdl"):
            tdl.add(name[: -len(".tdl")])
        else:
            pytest.fail(f"stray file {name}")
    assert tdl == expect
    edits = set()
    for n in tdl:
        found = json.loads((CORPUS / f"{n}.expect.json").read_text("utf-8"))
        if "edit" in found and "raises" not in found:
            edits.add(n)
    assert result == edits


def test_every_code_has_a_case():
    used = {
        e["code"] for p in SOURCES if p.parent.name == "errors" for e in expectation(p)["errors"]
    }
    assert used | BUILT_IN_CODE == CODES
    assert not used & BUILT_IN_CODE


def check_value(node):
    assert isinstance(node, dict) and set(node) in VALUE_KEYS, node
    if "word" in node or "string" in node or "slot" in node:
        assert isinstance(next(iter(node.values())), str)
    elif "number" in node:
        assert type(node["number"]) in (int, float)
    elif "percent" in node:
        assert type(node["percent"]) is int
    elif "call" in node:
        assert isinstance(node["call"], str)
        for arg in node["args"]:
            check_value(arg)
    elif "list" in node:
        for item in node["list"]:
            check_value(item)
    else:
        for part in node["template"]:
            assert set(part) in ({"text"}, {"slot"}) and isinstance(next(iter(part.values())), str)


def check_entry(node):
    assert isinstance(node, dict) and set(node) in ENTRY_KEYS, node
    if "block" in node:
        assert isinstance(node["block"], str)
        for child in node["entries"]:
            check_entry(child)
    elif "property" in node:
        assert isinstance(node["property"], str)
        check_value(node["value"])
    elif "if" in node:
        assert set(node["if"]) == {"slot"}
        check_bodies(node["body"], node["else"] or [])
    else:
        assert isinstance(node["for"], str)
        assert set(node["in"]) == {"slot"} and set(node["key"]) == {"slot"}
        check_bodies(node["body"])


def check_bodies(*bodies):
    for body in bodies:
        for child in body:
            check_entry(child)


@pytest.mark.parametrize("path", SOURCES, ids=IDS)
def test_case_is_well_formed(path):
    assert path.parent.name in AREAS
    data = path.read_bytes()
    expected = expectation(path)
    kinds = [k for k in ("ok", "errors", "edit") if k in expected]
    assert len(kinds) == 1, kinds
    area = path.parent.name
    if "ok" in expected:
        assert set(expected) == {"ok", "canonical"} and expected["ok"] is True
        assert area != "errors" and area != "edits"
        canonical = expected["canonical"]
        assert set(canonical) == {"metadata", "root"}
        for value in canonical["metadata"].values():
            assert set(value) in ({"word"}, {"string"})
        assert "block" in canonical["root"]
        check_entry(canonical["root"])
    elif "errors" in expected:
        assert set(expected) == {"errors"} and area == "errors"
        assert expected["errors"]
        lines = data.count(b"\n") + 1
        for e in expected["errors"]:
            assert set(e) in ({"code", "line", "column"}, {"code", "line", "column", "related"})
            assert e["code"] in CODES
            for origin in [e, *e.get("related", [])]:
                assert isinstance(origin["line"], int) and origin["line"] >= 1
                assert isinstance(origin["column"], int) and origin["column"] >= 1
                assert origin["line"] <= lines
    else:
        assert area == "edits"
        edit = expected["edit"]
        assert set(expected) <= {"edit", "raises"}
        assert set(edit) == EDIT_CALLS[edit["call"]]
        if "raises" in expected:
            assert expected["raises"] in CODES
