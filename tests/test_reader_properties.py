"""Properties of the reader that hold for any input (step 3): it fails only in the stated way."""

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import tdl
from layouts import OK_TEXTS, SOUP

CORPUS = Path(__file__).parent / "corpus"
CODES = {
    e["code"]
    for p in CORPUS.glob("errors/*.expect.json")
    for e in json.loads(p.read_text("utf-8"))["errors"]
}


def read_or_syntax_error(text: str) -> tdl.Document | None:
    try:
        return tdl.loads(text)
    except tdl.TDLSyntaxError as error:
        assert error.code in CODES | {"tdl-too-large", "tdl-too-deep"}
        assert error.origin.line >= 1 and error.origin.column >= 1
        return None


@settings(max_examples=300, deadline=None)
@given(SOUP)
def test_arbitrary_text_after_metadata_never_fails_any_other_way(body):
    read_or_syntax_error("---\nTDL: 0.1\nName: T\n---\n" + body)


@settings(max_examples=300, deadline=None)
@given(st.sampled_from(OK_TEXTS), st.data())
def test_a_valid_file_with_a_piece_cut_out_never_fails_any_other_way(text, data):
    start = data.draw(st.integers(0, len(text)))
    end = data.draw(st.integers(start, min(len(text), start + 12)))
    read_or_syntax_error(text[:start] + text[end:])


BUILDERS = {
    "blocks": lambda n: "B {\n" * n + "}\n" * n,
    "lists": lambda n: "A: " + "[" * n,
    "calls": lambda n: "A: " + "f(" * n,
}


@pytest.mark.parametrize("kind", sorted(BUILDERS))
@pytest.mark.parametrize("levels", [62, 63, 64, 65])
def test_nesting_limit_is_exact_at_the_boundary(levels, kind):
    check_nesting(levels, kind)


@settings(max_examples=100, deadline=None)
@given(st.integers(1, 200), st.sampled_from(sorted(BUILDERS)))
def test_nesting_stops_at_the_limit_and_never_overflows_the_stack(levels, kind):
    check_nesting(levels, kind)


def check_nesting(levels, kind):
    body = BUILDERS[kind](levels)
    text = "---\nTDL: 0.1\nName: T\n---\nShell {\n" + body
    code = None
    try:
        tdl.loads(text)
    except tdl.TDLSyntaxError as error:
        code = error.code
    # the root block is level 1, so `levels` more make 1 + levels
    assert (code == "tdl-too-deep") == (levels + 1 > 64)


JARGON = ("token", "lexeme", "production", "parser", "parse error", "syntax error", "EOF")


def check_error_shape(text: str, error: tdl.TDLSyntaxError) -> None:
    lines = text.split("\n")
    for origin in (error.origin, *error.related):
        assert 1 <= origin.line <= len(lines)
        assert 1 <= origin.column <= len(lines[origin.line - 1]) + 1
        assert (origin.end_line, origin.end_column) >= (origin.line, origin.column)
        assert origin.offset <= len(text.encode("utf-8"))
    assert error.message.endswith(".") and error.hint
    assert not any(word in (error.message + error.hint).lower() for word in JARGON)
    assert str(error) == f"{error.origin}: {error.message} ({error.hint})"


@settings(max_examples=300, deadline=None)
@given(SOUP)
def test_every_error_has_a_real_position_and_plain_words(body):
    text = "---\nTDL: 0.1\nName: T\n---\n" + body
    try:
        tdl.loads(text)
    except tdl.TDLSyntaxError as error:
        check_error_shape(text, error)


def test_every_corpus_error_has_a_real_position_and_plain_words():
    for path in sorted(CORPUS.glob("errors/*.tdl")):
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        try:
            tdl.loads(text)
        except tdl.TDLSyntaxError as error:
            check_error_shape(text, error)
