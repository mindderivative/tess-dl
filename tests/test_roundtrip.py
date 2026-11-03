"""`dumps`, `dump` and `load` (step 5): the exact round trip and what `load` refuses."""

import io

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import tess_dl
from layouts import HEAD, files


@settings(max_examples=300, deadline=None)
@given(files())
def test_any_valid_file_round_trips_through_text_and_bytes(text):
    doc = tess_dl.loads(text)
    assert tess_dl.dumps(doc) == text
    data = text.encode("utf-8")
    assert tess_dl.dumps(tess_dl.load(io.BytesIO(data))) == text
    out = io.BytesIO()
    tess_dl.dump(doc, out)
    assert out.getvalue() == data


@settings(max_examples=200, deadline=None)
@given(files())
def test_reading_what_was_dumped_gives_an_equal_document(text):
    doc = tess_dl.loads(text, path="a.tdl")
    out = io.BytesIO()
    tess_dl.dump(doc, out)
    again = tess_dl.load(io.BytesIO(out.getvalue()), path="a.tdl")
    assert again == doc
    assert again.canonical() == doc.canonical()


def walk(node, text, outer):
    """Every entry's span lies inside its parent's, the entries do not overlap, and the span
    slices back to text that starts with the entry's own word."""
    kids = {
        tess_dl.Block: lambda n: n.entries,
        tess_dl.If: lambda n: n.body + (n.else_body or ()),
        tess_dl.For: lambda n: n.body,
    }.get(type(node), lambda n: ())(node)
    assert outer[0] <= node.start <= node.end <= outer[1]
    if isinstance(node, tess_dl.Block):
        assert text[node.start : node.end].startswith(node.type)
    previous = node.start
    for kid in kids:
        assert previous <= kid.start
        walk(kid, text, (node.start, node.end))
        previous = kid.end


@settings(max_examples=200, deadline=None)
@given(files())
def test_spans_nest_and_do_not_overlap(text):
    doc = tess_dl.loads(text)
    walk(doc.root, text, (0, len(text)))
    assert doc.metadata.start >= (1 if text.startswith("\ufeff") else 0)


@settings(max_examples=300, deadline=None)
@given(st.binary(max_size=200), st.booleans())
def test_load_on_arbitrary_bytes_raises_only_tdl_errors(data, with_head):
    payload = (HEAD.encode() + b"Shell {\n" + data) if with_head else data
    try:
        tess_dl.load(io.BytesIO(payload))
    except tess_dl.TDLError:
        pass


def test_dump_keeps_the_byte_order_mark_and_each_line_ending():
    text = "\ufeff" + HEAD.replace("\n", "\r\n") + "Shell {\r\n  Width: 1\n}"
    out = io.BytesIO()
    tess_dl.dump(tess_dl.loads(text), out)
    assert out.getvalue() == text.encode("utf-8")
    assert out.getvalue().startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize(
    ("text", "line", "column"),
    [
        ("\ud800" + HEAD + "Shell { }\n", 1, 1),
        (HEAD + "Shell { Text: a\udfffb }\n", 5, 16),
    ],
)
def test_text_that_cannot_be_utf8_is_a_bad_encoding_error_not_a_python_one(text, line, column):
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        tess_dl.loads(text)
    error = raised.value
    assert (error.code, error.origin.line, error.origin.column) == (
        "tdl-bad-encoding",
        line,
        column,
    )
    assert error.message.endswith(".")


class CountingReader(io.BytesIO):
    """A binary stream that remembers how many bytes were asked for."""

    asked = 0

    def read(self, size=-1):
        data = super().read(size)
        self.asked += len(data)
        return data


def test_load_refuses_a_file_over_the_limit_without_reading_it_whole():
    limit = 1000
    reader = CountingReader(b"x" * 50_000)
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        tess_dl.load(reader, limits=tess_dl.Limits(max_bytes=limit))
    assert (raised.value.code, raised.value.origin.line, raised.value.origin.column) == (
        "tdl-too-large",
        1,
        1,
    )
    assert reader.asked == limit + 1


def test_load_reads_a_stream_that_returns_short_reads():
    data = (HEAD + "Shell { }\n").encode()

    class Trickle(io.RawIOBase):
        def __init__(self):
            self.rest = memoryview(data)

        def readable(self):
            return True

        def read(self, size=-1):
            chunk, self.rest = bytes(self.rest[:3]), self.rest[3:]
            return chunk

    assert tess_dl.dumps(tess_dl.load(Trickle())) == data.decode()
