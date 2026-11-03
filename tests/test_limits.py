"""The limits that need big inputs: built here so no large file lives in git (G11, G18, G25)."""

import pytest

META = "---\nTDL: 0.1\nName: T\n---\n"
MAX_BYTES = 1_048_576
MAX_DEPTH = 64


def sized(total):
    head, tail = META + "Shell {\n", "}\n"
    fill = total - len(head) - len(tail)
    return head + "# " + "x" * (fill - 3) + "\n" + tail


def nested(levels):
    return META + "B {\n" * levels + "}\n" * levels


def test_a_file_of_exactly_one_mebibyte_loads():
    import tdl

    text = sized(MAX_BYTES)
    assert len(text.encode()) == MAX_BYTES
    assert tdl.dumps(tdl.loads(text)) == text


def test_one_byte_more_is_too_large_and_nothing_else():
    import tdl

    text = sized(MAX_BYTES + 1)
    with pytest.raises(tdl.TDLSyntaxError) as raised:
        tdl.loads(text)
    assert (raised.value.code, raised.value.origin.line, raised.value.origin.column) == (
        "tdl-too-large",
        1,
        1,
    )
    errors = tdl.parse(text).errors
    assert [(e.code, e.origin.line, e.origin.column) for e in errors] == [("tdl-too-large", 1, 1)]


def test_sixty_four_levels_load():
    import tdl

    text = nested(MAX_DEPTH)
    assert tdl.dumps(tdl.loads(text)) == text


def test_sixty_five_levels_are_too_deep_at_the_65th_brace():
    import tdl

    text = nested(MAX_DEPTH + 1)
    with pytest.raises(tdl.TDLSyntaxError) as raised:
        tdl.loads(text)
    assert (raised.value.code, raised.value.origin.line, raised.value.origin.column) == (
        "tdl-too-deep",
        69,
        3,
    )
    assert [e.code for e in tdl.parse(text).errors] == ["tdl-too-deep"]


def test_sixty_mistakes_give_fifty_errors_and_the_last_says_so():
    import tdl

    text = META + "Shell {\n" + "  Bad\n" * 60 + "}\n"
    errors = tdl.parse(text).errors
    assert len(errors) == 50
    assert "50" in errors[-1].message
