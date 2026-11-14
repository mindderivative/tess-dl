"""The limits that need big inputs: built here so no large file lives in git (G11, G18, G25)."""

import pytest

META = "---\nTDL: 0.2\nName: T\n---\n"
MAX_BYTES = 1_048_576
MAX_DEPTH = 64


def sized(total):
    head, tail = META + "Shell {\n", "}\n"
    fill = total - len(head) - len(tail)
    return head + "# " + "x" * (fill - 3) + "\n" + tail


def nested(levels):
    return META + "B {\n" * levels + "}\n" * levels


def test_a_file_of_exactly_one_mebibyte_loads():
    import tess_dl

    text = sized(MAX_BYTES)
    assert len(text.encode()) == MAX_BYTES
    assert tess_dl.dumps(tess_dl.loads(text)) == text


def test_one_byte_more_is_too_large_and_nothing_else():
    import tess_dl

    text = sized(MAX_BYTES + 1)
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        tess_dl.loads(text)
    assert (raised.value.code, raised.value.origin.line, raised.value.origin.column) == (
        "tdl-too-large",
        1,
        1,
    )
    errors = tess_dl.parse(text).errors
    assert [(e.code, e.origin.line, e.origin.column) for e in errors] == [("tdl-too-large", 1, 1)]


def test_sixty_four_levels_load():
    import tess_dl

    text = nested(MAX_DEPTH)
    assert tess_dl.dumps(tess_dl.loads(text)) == text


def test_sixty_five_levels_are_too_deep_at_the_65th_brace():
    import tess_dl

    text = nested(MAX_DEPTH + 1)
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        tess_dl.loads(text)
    assert (raised.value.code, raised.value.origin.line, raised.value.origin.column) == (
        "tdl-too-deep",
        69,
        3,
    )
    assert [e.code for e in tess_dl.parse(text).errors] == ["tdl-too-deep"]


def test_sixty_mistakes_give_fifty_errors_and_the_last_says_so():
    import tess_dl

    text = META + "Shell {\n" + "  Bad\n" * 60 + "}\n"
    errors = tess_dl.parse(text).errors
    assert len(errors) == 50
    assert "50" in errors[-1].message


NESTINGS = {
    "blocks": lambda n: "B {\n" * n,
    "lists": lambda n: "A: " + "[" * n,
    "calls": lambda n: "A: " + "f(" * n,
}


@pytest.mark.parametrize("kind", sorted(NESTINGS))
def test_ten_thousand_levels_are_too_deep_and_never_a_recursion_error(kind):
    import tess_dl

    text = META + "Shell {\n" + NESTINGS[kind](10_000)
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        tess_dl.loads(text)
    assert raised.value.code == "tdl-too-deep"
    result = tess_dl.parse(text)
    assert [e.code for e in result.errors] == ["tdl-too-deep"] and result.document is None


def test_a_file_over_the_limit_is_refused_before_anything_is_read():
    import tess_dl

    garbage = "x" * (MAX_BYTES + 1)  # would be tdl-no-metadata if it were read
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        tess_dl.loads(garbage)
    assert raised.value.code == "tdl-too-large"
    assert [e.code for e in tess_dl.parse(garbage).errors] == ["tdl-too-large"]
    wide = "\u00e9" * (MAX_BYTES // 2 + 1)  # under the limit in characters, over it in bytes
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        tess_dl.loads(wide)
    assert raised.value.code == "tdl-too-large"


def realistic(size):
    block = (
        "  Bar {\n    Name: Bar\n    Text: Battery <| b.percent |>%\n    Items: [1, 2, 3]\n  }\n"
    )
    body = block * ((size - len(META) - 10) // len(block))
    return META + "Shell {\n" + body + "}\n"


def fastest(read, text, runs=5):
    import time

    times = []
    for _ in range(runs):
        start = time.perf_counter()
        read(text)
        times.append(time.perf_counter() - start)
    return min(times)


@pytest.mark.parametrize("call", ["loads", "parse"])
def test_reading_time_grows_linearly_with_the_size_of_the_file(call):
    """A guard against a quadratic step. Four times the text costs about four times as long
    (benchmarks/bench.py measures x4.1); a quadratic step would cost sixteen. The bound of x9
    leaves room for a noisy machine."""
    import tess_dl

    read = getattr(tess_dl, call)
    small = fastest(read, realistic(MAX_BYTES // 4))
    big = fastest(read, realistic(MAX_BYTES))
    assert big / small < 9, f"{call}: x{big / small:.1f} for four times the text"


def test_a_file_at_the_limit_reads_inside_a_generous_ceiling():
    """The measured time is about 0.14 s; this only fails if it grows to seconds."""
    import tess_dl

    assert fastest(tess_dl.loads, realistic(MAX_BYTES), runs=2) < 3.0


def test_a_long_line_of_mistakes_reads_in_time_and_reports_the_first_one():
    """The rest of a bad line is skipped with it (G31), so one line gives one error."""
    import time

    import tess_dl

    text = META + "Shell { " + "a: #x, " * 100_000 + "}\n"
    start = time.perf_counter()
    result = tess_dl.parse(text)
    assert time.perf_counter() - start < 3.0
    assert [e.code for e in result.errors] == ["tdl-bare-hash"]
