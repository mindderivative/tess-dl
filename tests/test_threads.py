"""`tess_dl` parses on any thread and returns immutable data (docs/api.md, "Python Contract")."""

import dataclasses
from concurrent.futures import ThreadPoolExecutor

import pytest

import tess_dl
from layouts import OK_TEXTS

HEAD = "---\nTDL: 0.1\nName: T\n---\n"
BAD_TEXTS = [HEAD + 'Shell {\n  Width 32\n  Color: #fff\n  Text: "abc\n}\n', "Shell { }", HEAD]


def snapshot(text):
    result = tess_dl.parse(text)
    return (
        result.document.canonical() if result.document else None,
        [(e.code, e.origin.line, e.origin.column) for e in result.errors],
    )


def test_many_threads_reading_the_same_texts_get_the_same_results_as_one():
    texts = OK_TEXTS + BAD_TEXTS
    expected = [snapshot(t) for t in texts]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for _ in range(4):
            assert list(pool.map(snapshot, texts)) == expected


def test_one_document_can_be_edited_and_written_from_many_threads():
    doc = tess_dl.loads(HEAD + "Shell {\n  Bar { Name: B }\n}\n")
    expected = tess_dl.dumps(doc.with_metadata("UID", "x"))

    def work(i):
        edited = doc.with_metadata("UID", "x")
        again = doc.find("T.B").with_property("Height", str(i))
        return tess_dl.dumps(edited), tess_dl.dumps(again), tess_dl.dumps(doc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(work, range(200)))
    assert all(r[0] == expected and r[2] == doc.text for r in results)
    assert [r[1].count("Height") for r in results] == [1] * 200


def test_nodes_cannot_be_changed_in_place():
    doc = tess_dl.loads(HEAD + "Shell { Width: 1 }\n")
    prop = doc.root.entries[0]
    for node, field in [(doc, "text"), (doc.root, "type"), (prop, "key"), (prop.value, "value")]:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(node, field, "x")
    assert isinstance(doc.root.entries, tuple)
    with pytest.raises(TypeError):
        doc.metadata["TDL"] = "x"
