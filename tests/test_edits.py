"""The edit calls beyond the corpus (step 6): only the edit changes, and refusals touch nothing."""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

import tess_dl
from layouts import HEAD, files

TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),  # lone surrogates are not UTF-8
    max_size=40,
)
KEYS = st.sampled_from(["UID", "Title", "Author", "Shell", "Extra_1"])  # not TDL or Name: see below


def changed_span(old: str, new: str) -> tuple[str, str]:
    """What was removed from `old` and what was put in its place: the one changed span."""
    k = 0
    while k < min(len(old), len(new)) and old[k] == new[k]:
        k += 1
    m = 0
    while m < min(len(old), len(new)) - k and old[-1 - m] == new[-1 - m]:
        m += 1
    return old[k : len(old) - m], new[k : len(new) - m]


def word_or_string(value) -> str:
    return value.text if isinstance(value, tess_dl.Word) else value.value


# with_metadata and without_metadata


@settings(max_examples=300, deadline=None)
@given(files(), KEYS, TEXT)
def test_with_metadata_reads_back_what_was_given_and_changes_one_span(text, key, value):
    doc = tess_dl.loads(text)
    new = doc.with_metadata(key, value)
    assert word_or_string(new.metadata[key]) == value
    removed, added = changed_span(text, tess_dl.dumps(new))
    if key in doc.metadata:
        assert removed == doc.text[doc.metadata[key].start : doc.metadata[key].end]
    else:
        assert removed == "" and added.endswith("\n") and added.count("\n") == 1
    # every other key and the whole root are as they were
    assert {k: v for k, v in new.metadata.items() if k != key} == {
        k: v for k, v in doc.metadata.items() if k != key
    }
    assert new.root == doc.root


@settings(max_examples=200, deadline=None)
@given(files(), KEYS, TEXT)
def test_the_same_edit_twice_changes_nothing_the_second_time(text, key, value):
    once = tess_dl.loads(text).with_metadata(key, value)
    assert tess_dl.dumps(once.with_metadata(key, value)) == tess_dl.dumps(once)


@settings(max_examples=200, deadline=None)
@given(files(), st.sampled_from(["UID", "Title", "Author"]), TEXT)
def test_adding_then_removing_a_key_gives_back_the_original_text(text, key, value):
    doc = tess_dl.loads(text)
    assume(key not in doc.metadata)
    assert tess_dl.dumps(doc.with_metadata(key, value).without_metadata(key)) == text


@settings(max_examples=200, deadline=None)
@given(files(), TEXT)
def test_an_edited_document_reads_back_equal_and_keeps_its_line_endings(text, value):
    new = tess_dl.loads(text).with_metadata("UID", value)
    assert tess_dl.loads(tess_dl.dumps(new), path=new.path) == new
    out = tess_dl.dumps(new)
    assert out.count("\r\n") >= text.count("\r\n")  # a CRLF line is never turned into LF


def test_the_new_uid_line_takes_the_line_ending_of_the_line_before_it():
    text = "---\r\nTDL: 0.1\r\nName: T\nShell: 0.1\n---\nShell { }\n"
    out = tess_dl.dumps(tess_dl.loads(text).with_metadata("UID", "x"))
    assert out == "---\r\nTDL: 0.1\r\nName: T\nShell: 0.1\nUID: x\n---\nShell { }\n"


def test_a_value_that_would_not_read_back_as_a_word_is_quoted():
    doc = tess_dl.loads(HEAD + "Shell { }\n")
    for value, written in [
        ("a b", "a b"),
        ("", '""'),
        (" x", '" x"'),
        ('"q"', '"\\"q\\""'),
        ("a # b", '"a # b"'),
        ("two\nlines", '"two\\nlines"'),
    ]:
        assert f"Title: {written}\n" in tess_dl.dumps(doc.with_metadata("Title", value))


def test_removing_an_absent_key_returns_the_same_document():
    doc = tess_dl.loads(HEAD + "Shell { }\n")
    assert doc.without_metadata("Nope") is doc


@pytest.mark.parametrize("key", ["", "a b", "1x", "A:B", "A\nB"])
def test_a_key_that_is_not_a_name_is_refused(key):
    doc = tess_dl.loads(HEAD + "Shell { }\n")
    with pytest.raises(ValueError):
        doc.with_metadata(key, "x")
    with pytest.raises(ValueError):
        doc.root.with_property(key, "1")


@pytest.mark.parametrize(("call", "code"), [("TDL", "tdl-no-version"), ("Name", "tdl-no-name")])
def test_removing_a_required_key_is_refused_and_the_original_is_untouched(call, code):
    doc = tess_dl.loads(HEAD + "Shell { }\n")
    with pytest.raises(tess_dl.TDLError) as raised:
        doc.without_metadata(call)
    assert raised.value.code == code
    assert tess_dl.dumps(doc) == HEAD + "Shell { }\n"


def test_setting_name_to_something_that_is_not_a_name_is_refused():
    doc = tess_dl.loads(HEAD + "Shell { }\n")
    with pytest.raises(tess_dl.TDLError) as raised:
        doc.with_metadata("Name", "DP-1")
    assert raised.value.code == "tdl-bad-name"


# replace


def test_replace_takes_character_offsets_and_refuses_a_span_outside_the_text():
    doc = tess_dl.loads("\ufeff" + HEAD + "Shell { }\n")
    at = doc.text.index("Shell")
    assert tess_dl.dumps(doc.replace(at, at + 5, "Other")).endswith("Other { }\n")
    for bad in [(-1, 2), (5, 2), (0, len(doc.text) + 1)]:
        with pytest.raises(ValueError):
            doc.replace(*bad, "x")


# with_property


def prop(text: str, path: str, key: str, value: str) -> str:
    doc = tess_dl.loads(HEAD.replace("Name: T", "Name: R") + text)
    return tess_dl.dumps(doc.find(path).with_property(key, value))[len(HEAD) :]


@pytest.mark.parametrize(
    ("before", "after"),
    [
        # a new property after the last one, same indentation and line ending
        ("Shell {\n  A: 1\n}\n", "Shell {\n  A: 1\n  H: 40\n}\n"),
        ("Shell {\r\n\tA: 1  # note\r\n}\r\n", "Shell {\r\n\tA: 1  # note\r\n\tH: 40\r\n}\r\n"),
        ("Shell {\n  A: 1,\n  B: 2,\n}\n", "Shell {\n  A: 1,\n  B: 2,\n  H: 40\n}\n"),
        # the property is on the line of the closing brace: add it inline
        ("Shell { A: 1 }\n", "Shell { A: 1, H: 40 }\n"),
        ("Shell { A: 1, }\n", "Shell { A: 1, H: 40, }\n"),
        # no property yet
        ("Shell { }\n", "Shell { H: 40 }\n"),
        ("Shell { Label { } }\n", "Shell { H: 40, Label { } }\n"),
        ("Shell {\n  Label { }\n}\n", "Shell {\n  H: 40\n  Label { }\n}\n"),
        ("Shell {\n}\n", "Shell {\n  H: 40\n}\n"),
        # an existing property changes only its value
        ("Shell {\n  H: 1   # px\n}\n", "Shell {\n  H: 40   # px\n}\n"),
        ('Shell { H: "a" }\n', "Shell { H: 40 }\n"),
    ],
)
def test_with_property_places_the_line_where_the_neighbours_are(before, after):
    assert prop(before, "R", "H", "40") == after


def test_find_follows_name_values_and_reports_what_is_missing():
    doc = tess_dl.loads(
        HEAD.replace("Name: T", "Name: R")
        + 'Shell {\n  M { Name: Main\n  Bar { Name: "Top" } }\n  M { Name: Other }\n}\n'
    )
    assert doc.find("R") is doc.root
    assert doc.find("R.Main").name == "Main"
    assert doc.find("R.Main.Top").type == "Bar"
    for path in ["Main", "R.Nope", "R.Top", "R.Main.Main", ""]:
        with pytest.raises(KeyError):
            doc.find(path)


@pytest.mark.parametrize("value", ["", "1 }", "1\nOther: 2", "1 # c", "a, b", "{{", '"abc', "a }"])
def test_a_value_that_is_not_exactly_one_value_is_refused(value):
    doc = tess_dl.loads(HEAD + "Shell { A: 1 }\n")
    with pytest.raises(ValueError):
        doc.root.with_property("H", value)


def test_reserved_words_and_blocks_built_in_code_are_refused():
    doc = tess_dl.loads(HEAD + "Shell { }\n")
    with pytest.raises(ValueError):
        doc.root.with_property("If", "1")
    with pytest.raises(ValueError):
        tess_dl.Block("B", ()).with_property("H", "1")


@settings(max_examples=300, deadline=None)
@given(
    files(), st.sampled_from(["Added", "Width", "Text"]), st.sampled_from(["1", "x y", "[1, 2]"])
)
def test_with_property_changes_one_span_and_one_property(text, key, value):
    doc = tess_dl.loads(text)
    new = doc.root.with_property(key, value)
    removed, added = changed_span(text, tess_dl.dumps(new))
    mine = [e for e in new.root.entries if isinstance(e, tess_dl.Property) and e.key == key]
    assert len(mine) == 1
    old = [e for e in doc.root.entries if isinstance(e, tess_dl.Property) and e.key == key]
    if old:
        assert removed == text[old[0].value.start : old[0].value.end] and added == value
    else:
        assert removed == "" and key in added and value in added
    others_before = [e for e in doc.root.entries if e not in old]
    others_after = [e for e in new.root.entries if e not in mine]
    assert others_before == others_after
    assert tess_dl.loads(tess_dl.dumps(new), path=new.path) == new


def test_setting_the_language_version_to_one_this_library_cannot_read_is_refused():
    doc = tess_dl.loads(HEAD + "Shell { }\n")
    assert tess_dl.dumps(doc.with_metadata("TDL", "0.2")).startswith("---\nTDL: 0.2\n")
    with pytest.raises(tess_dl.TDLError) as raised:
        doc.with_metadata("TDL", "9.0")
    assert raised.value.code == "tdl-unsupported-version"
