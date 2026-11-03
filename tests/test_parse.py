"""`parse` (step 7): it never raises, lists every error in source order, and stops at the cap."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import tess_dl
from layouts import HEAD, OK_TEXTS, SOUP, files


def triples(errors):
    return [(e.code, e.origin.line, e.origin.column) for e in errors]


def offsets(errors):
    return [e.origin.offset for e in errors]


ANY_TEXT = st.one_of(
    SOUP.map(lambda body: HEAD + body),
    st.text(max_size=120),  # includes lone surrogates and every other code point
    st.builds(
        lambda text, a, b: text[:a] + text[a + b :],
        st.sampled_from(OK_TEXTS),
        st.integers(0, 400),
        st.integers(0, 12),
    ),
)


@settings(max_examples=500, deadline=None)
@given(ANY_TEXT)
def test_parse_never_raises_and_lists_errors_in_source_order_within_the_cap(text):
    result = tess_dl.parse(text)
    assert len(result.errors) <= 50
    assert offsets(result.errors) == sorted(offsets(result.errors))
    assert all(isinstance(e, tess_dl.TDLSyntaxError) for e in result.errors)


@settings(max_examples=500, deadline=None)
@given(ANY_TEXT)
def test_parse_agrees_with_loads(text):
    result = tess_dl.parse(text)
    try:
        doc = tess_dl.loads(text)
    except tess_dl.TDLSyntaxError as error:
        # loads stops at the first mistake it meets; parse lists that mistake too
        assert (error.code, error.origin.line, error.origin.column) in triples(result.errors)
    else:
        assert result.errors == ()
        assert result.document == doc


@settings(max_examples=200, deadline=None)
@given(files())
def test_a_valid_file_parses_to_the_same_document_with_no_errors(text):
    result = tess_dl.parse(text, path="a.tdl")
    assert result.errors == ()
    assert result.document == tess_dl.loads(text, path="a.tdl")


@settings(max_examples=200, deadline=None)
@given(ANY_TEXT, st.integers(1, 6))
def test_the_cap_is_honoured_and_the_last_entry_says_so(text, cap):
    full = tess_dl.parse(text).errors
    capped = tess_dl.parse(text, limits=tess_dl.Limits(max_errors=cap)).errors
    assert len(capped) <= cap
    if len(full) > cap:
        assert len(capped) == cap
        assert capped[-1].message.endswith(f"The list stops at {cap} errors.")
        assert all(not e.message.endswith("errors.") for e in capped[:-1])
    else:
        assert triples(capped) == triples(full)
        assert not any("The list stops" in e.message for e in capped)


def mistakes(n: int) -> str:
    return HEAD + "Shell {\n" + "  Bad\n" * n + "}\n"


def test_sixty_mistakes_give_fifty_errors_and_the_last_says_so():
    errors = tess_dl.parse(mistakes(60)).errors
    assert len(errors) == 50
    assert "50" in errors[-1].message
    assert [e.origin.line for e in errors] == list(range(6, 56))


def test_exactly_fifty_mistakes_are_listed_without_a_cap_note():
    errors = tess_dl.parse(mistakes(50)).errors
    assert len(errors) == 50
    assert "The list stops" not in errors[-1].message


def test_no_work_is_done_after_the_cap(monkeypatch):
    from tess_dl import _parser

    calls = []
    original = _parser._Reader.error

    def counting(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(_parser._Reader, "error", counting)
    tess_dl.parse(mistakes(5000))
    assert len(calls) == 51  # fifty kept and the one that showed there were more


def test_the_best_tree_leaves_out_only_the_entries_with_mistakes():
    text = (
        HEAD
        + 'Shell {\n  Width 32\n  Height: 1\n  Color: #fff\n  Text: "abc\n  Label { Name: ok }\n}\n'
    )
    result = tess_dl.parse(text)
    assert [e.code for e in result.errors] == [
        "tdl-unexpected-text",
        "tdl-bare-hash",
        "tdl-unclosed-string",
    ]
    assert result.document is not None
    assert result.document.canonical()["root"] == {
        "block": "Shell",
        "entries": [
            {"property": "Height", "value": {"number": 1}},
            {"block": "Label", "entries": [{"property": "Name", "value": {"word": "ok"}}]},
        ],
    }


def test_a_bad_entry_on_the_closing_line_does_not_swallow_the_closing_brace():
    result = tess_dl.parse(HEAD + "Shell { Color: #fff }\n")
    assert triples(result.errors) == [("tdl-bare-hash", 5, 16)]
    assert result.document is not None and result.document.root.entries == ()


def test_metadata_mistakes_are_all_listed_and_the_body_is_still_read():
    text = "---\nName: 1st\nName: x\nTitle\n---\nShell {\n  Width 32\n}\n"
    result = tess_dl.parse(text)
    assert triples(result.errors) == [
        ("tdl-no-version", 1, 1),
        ("tdl-bad-name", 2, 7),
        ("tdl-duplicate-key", 3, 1),
        ("tdl-unexpected-text", 4, 6),
        ("tdl-unexpected-text", 7, 9),
    ]
    assert result.document is not None


@pytest.mark.parametrize(
    ("text", "codes", "has_document"),
    [
        ("Shell { }", ["tdl-no-metadata"], False),
        ("---\nTDL: 0.1\nName: T\n", ["tdl-metadata-unclosed"], False),
        (HEAD, ["tdl-no-root"], False),
        (HEAD + "{ }\n", ["tdl-unexpected-text"], False),
        (
            HEAD + "Shell { }\nOther {\n  Width 1\n}\n",
            ["tdl-many-roots", "tdl-unexpected-text"],
            True,
        ),
        (HEAD + "Shell { }\n} ]\n", ["tdl-unexpected-close", "tdl-unexpected-text"], True),
        (HEAD + "Shell {\n  Bar {\n", ["tdl-unclosed-block"] * 2, True),
    ],
)
def test_errors_outside_a_block_are_recovered_where_a_tree_can_still_be_built(
    text, codes, has_document
):
    result = tess_dl.parse(text)
    assert [e.code for e in result.errors] == codes
    assert (result.document is not None) == has_document


def test_a_double_close_is_reported_once_and_closes_both_blocks():
    result = tess_dl.parse(HEAD + "Shell {\n  Bar {\n    Width: 1\n  }}\n")
    assert triples(result.errors) == [("tdl-double-close", 8, 3)]
    assert result.document is not None
    assert result.document.canonical()["root"]["entries"][0]["block"] == "Bar"


def test_limit_errors_stop_the_file_with_one_error_and_no_tree():
    big = tess_dl.parse(
        HEAD + "Shell {\n" + "# x\n" * 100 + "}\n", limits=tess_dl.Limits(max_bytes=100)
    )
    assert triples(big.errors) == [("tdl-too-large", 1, 1)] and big.document is None
    deep = tess_dl.parse(HEAD + "B {\n" * 70 + "}\n" * 70)
    assert triples(deep.errors) == [("tdl-too-deep", 69, 3)] and deep.document is None
    bad = tess_dl.parse(HEAD + "Shell { Text: a\ud800 }\n")
    assert [e.code for e in bad.errors] == ["tdl-bad-encoding"] and bad.document is None


def test_a_text_that_is_not_utf8_is_one_error_and_still_never_raises():
    assert tess_dl.parse("\ud800").errors[0].code == "tdl-bad-encoding"
