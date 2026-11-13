"""The formatter (T-011b): `format_block` and `format`: the canonical layout, kept content."""

import pytest
from hypothesis import given, settings

import tess_dl
from layouts import HEAD, OK_TEXTS, files
from tess_dl._format import _comments
from test_block_edits import all_nodes

NAMED = HEAD.replace("Name: T", "Name: R")


# format_block


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("Panel { Name: p1,   Width:200 }", "Panel {\n  Name: p1\n  Width: 200\n}"),
        ("Spacer {}", "Spacer { }"),
        ("A {\n\tB { }\n}", "A {\n  B { }\n}"),
        ("    A { X: 1 }", "A {\n  X: 1\n}"),
        ("A { X: 1 } # c", "A {\n  X: 1\n}  # c"),
        ("A {\n  X: 1\n\n\n\n  Y: 2\n}", "A {\n  X: 1\n\n  Y: 2\n}"),
        ("A {\n\n  X: 1\n\n}", "A {\n  X: 1\n}"),
        (
            "# top\nA { # c\n X: 1 # t\n}",
            "# top\nA {\n  # c\n  X: 1  # t\n}",
        ),
        (
            "A { If {{ c }} { X { } } Else { Y { } } }",
            "A {\n  If {{ c }} {\n    X { }\n  } Else {\n    Y { }\n  }\n}",
        ),
        (
            "A {\n If {{ c }} { X { } }\n # why\n Else { Y { } }\n}",
            "A {\n  If {{ c }} {\n    X { }\n  }\n  # why\n  Else {\n    Y { }\n  }\n}",
        ),
        ("A { If {{ c }} { } }", "A {\n  If {{ c }} { }\n}"),
        (
            "A { For  x  In  {{ xs }}  Key  {{ x }} { Z { } } }",
            "A {\n  For x In {{ xs }} Key {{ x }} {\n    Z { }\n  }\n}",
        ),
        ("A {\n  L: [\n    1,\n    2\n  ]\n}", "A {\n  L: [\n    1,\n    2\n  ]\n}"),
        ("A {\r\n X: 1\r\n}", "A {\r\n  X: 1\r\n}"),
        ("A { # c\n}", "A {\n  # c\n}"),
        (
            "A { T: Battery {{ b.percent }}%, C: rgba(0 0 0 0.5), S: 'a b' }",
            "A {\n  T: Battery {{ b.percent }}%\n  C: rgba(0 0 0 0.5)\n  S: 'a b'\n}",
        ),
    ],
)
def test_format_block_writes_the_canonical_layout(before, after):
    assert tess_dl.format_block(before) == after
    assert tess_dl.format_block(after) == after  # and that is a fixed point


def test_format_block_keeps_comment_lines_above_and_below_the_block():
    out = tess_dl.format_block("\n\n# above\n\nA { }\n\n# below\n\n")
    assert out == "# above\n\nA { }\n\n# below"


@pytest.mark.parametrize(
    ("text", "code", "line"),
    [("Width: 1", "tdl-unexpected-text", 1), ("A {\n  B 1\n}", "tdl-unexpected-text", 2)],
)
def test_format_block_refuses_what_is_not_one_block_with_origins_inside_the_text(text, code, line):
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        tess_dl.format_block(text)
    assert (raised.value.code, raised.value.origin.line) == (code, line)
    assert raised.value.origin.file == "<block_text>"


def test_a_formatted_block_goes_into_with_child_unchanged():
    doc = tess_dl.loads(NAMED + "Shell {\n  X: 1\n}\n")
    new_doc, child = doc.root.with_child(tess_dl.format_block("Bar { Name: b,  Width: 2 }"))
    assert tess_dl.dumps(new_doc)[len(NAMED) :] == (
        "Shell {\n  X: 1\n  Bar {\n    Name: b\n    Width: 2\n  }\n}\n"
    )
    assert child.name == "b"


# format


def test_format_writes_a_whole_file_in_the_canonical_layout():
    head = "---\nTDL:   0.1   #   v\nName: R   # n\n# own line\n\n\nUID: x\n---\n"
    text = (
        "\ufeff"
        + head
        + "\n\n# top\nShell { Panel { A: 1, B: 2 }\n\tLabel { } , T: Hi {{ b }}\n"
        + "}   # end\n\n\n# last"
    )
    doc = tess_dl.format(tess_dl.loads(text))
    assert doc.text == (
        "\ufeff---\nTDL: 0.1  #   v\nName: R  # n\n# own line\n\nUID: x\n---\n\n# top\n"
        "Shell {\n  Panel {\n    A: 1\n    B: 2\n  }\n  Label { }\n  T: Hi {{ b }}\n"
        "}  # end\n\n# last\n"
    )


def test_format_uses_the_line_ending_of_the_first_line_throughout_and_ends_with_one():
    crlf = (NAMED + "Shell { A: 1\n, B: 2 }").replace("\n", "\r\n")
    out = tess_dl.format(tess_dl.loads(crlf)).text
    assert out.endswith("}\r\n") and "\n" not in out.replace("\r\n", "")
    mixed = tess_dl.format(tess_dl.loads(NAMED + "Shell { A: 1\r\n}\r\n")).text
    assert "\r" not in mixed and mixed.endswith("}\n")


def test_format_refuses_a_document_that_has_errors():
    result = tess_dl.parse(NAMED + "Shell {\n  Width 32\n}\n")
    assert result.document is not None
    with pytest.raises(tess_dl.TDLSyntaxError):
        tess_dl.format(result.document)


def test_the_formatted_document_keeps_the_path_label():
    assert tess_dl.format(tess_dl.loads(NAMED + "Shell { }\n", path="a.tdl")).path == "a.tdl"


@pytest.mark.parametrize("text", OK_TEXTS)
def test_every_ok_corpus_file_formats_to_the_same_content_and_is_a_fixed_point(text):
    doc = tess_dl.loads(text)
    once = tess_dl.format(doc)
    assert once.canonical() == doc.canonical() and _comments(once) == _comments(doc)
    assert tess_dl.format(once).text == once.text


def layout_problems(text):
    """Things a canonical document never has."""
    problems = []
    eol = "\r\n" if "\r\n" in text else "\n"
    body = text.removeprefix("\ufeff")
    if not body.endswith(eol) or body.endswith(eol * 2):
        problems.append("must end with exactly one line ending")
    if eol == "\n" and "\r" in text or eol == "\r\n" and "\n" in text.replace("\r\n", ""):
        problems.append("mixed line endings")
    for number, line in enumerate(body.split(eol)[:-1], 1):
        if line != line.rstrip():
            problems.append(f"line {number} has trailing space")
        if line.startswith("\t") or len(line) - len(line.lstrip(" ")) & 1:
            problems.append(f"line {number} is not indented by two spaces a level")
    return problems


@settings(max_examples=300, deadline=None)
@given(files())
def test_format_keeps_content_and_comments_is_idempotent_and_canonical(text):
    doc = tess_dl.loads(text)
    once = tess_dl.format(doc)
    assert once.canonical() == doc.canonical() and _comments(once) == _comments(doc)
    assert layout_problems(once.text) == []
    assert tess_dl.format(once).text == once.text
    paths = [n.index_path for n in all_nodes(doc.root)]
    assert paths == [
        n.index_path for n in all_nodes(once.root)
    ]  # the same nodes in the same places


@settings(max_examples=200, deadline=None)
@given(files())
def test_format_block_of_the_root_keeps_content_and_is_a_fixed_point(text):
    doc = tess_dl.loads(text)
    snippet = doc.text[doc.root.start : doc.root.end]
    once = tess_dl.format_block(snippet)
    again = tess_dl.format_block(once)
    assert again == once
    probe = tess_dl.loads(HEAD + once + "\n").root
    assert probe.canonical() == doc.root.canonical()
