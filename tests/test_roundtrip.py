"""`dumps`, `dump` and `load` (step 5): the exact round trip and what `load` refuses."""

import io

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import tdl

HEAD = "---\nTDL: 0.1\nName: T\n---\n"
ENTRIES = [
    "Width: 32",
    "Text: Hello world",
    "Color: rgba(0 0 0 0.5)",
    'Mark: "a \\u00e9 b"',
    "Items: [1, 2, 3]",
    "Text: Battery {{ battery.percent }}%",
    "Spacer { }",
    "Panel { Name: p1, Width: 200 }",
    "If {{ c }} { Label { } }",
    "For x In {{ xs }} Key {{ x }} { Label { } }",
    "# a comment",
    "",
    "Name: caf\u00e9_\U0001f600",
]
SPACE = st.text(alphabet=" \t", max_size=3)
EOL = st.sampled_from(["\n", "\r\n"])


@st.composite
def files(draw):
    """A valid file with random layout: comments, blanks, indentation, line endings, BOM."""
    lines = draw(st.lists(st.sampled_from(ENTRIES), max_size=12))
    # a property key may appear once: keep the first of each, drop repeats
    seen, kept = set(), []
    for line in lines:
        key = line.split(":", 1)[0] if ":" in line and "{" not in line.split(":", 1)[0] else None
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        kept.append(line)
    out = [draw(SPACE) + "Shell {"]
    for line in kept:
        out.append(
            draw(SPACE) + line + (draw(SPACE) + "  # note" if line and draw(st.booleans()) else "")
        )
    out.append("}")
    body = "".join(line + draw(EOL) for line in out)
    if draw(st.booleans()):
        body = body.rstrip("\r\n")  # no final newline
    head = HEAD.replace("\n", draw(EOL))
    return ("\ufeff" if draw(st.booleans()) else "") + head + body


@settings(max_examples=300, deadline=None)
@given(files())
def test_any_valid_file_round_trips_through_text_and_bytes(text):
    doc = tdl.loads(text)
    assert tdl.dumps(doc) == text
    data = text.encode("utf-8")
    assert tdl.dumps(tdl.load(io.BytesIO(data))) == text
    out = io.BytesIO()
    tdl.dump(doc, out)
    assert out.getvalue() == data


@settings(max_examples=200, deadline=None)
@given(files())
def test_reading_what_was_dumped_gives_an_equal_document(text):
    doc = tdl.loads(text, path="a.tdl")
    out = io.BytesIO()
    tdl.dump(doc, out)
    again = tdl.load(io.BytesIO(out.getvalue()), path="a.tdl")
    assert again == doc
    assert again.canonical() == doc.canonical()


def walk(node, text, outer):
    """Every entry's span lies inside its parent's, the entries do not overlap, and the span
    slices back to text that starts with the entry's own word."""
    kids = {
        tdl.Block: lambda n: n.entries,
        tdl.If: lambda n: n.body + (n.else_body or ()),
        tdl.For: lambda n: n.body,
    }.get(type(node), lambda n: ())(node)
    assert outer[0] <= node.start <= node.end <= outer[1]
    if isinstance(node, tdl.Block):
        assert text[node.start : node.end].startswith(node.type)
    previous = node.start
    for kid in kids:
        assert previous <= kid.start
        walk(kid, text, (node.start, node.end))
        previous = kid.end


@settings(max_examples=200, deadline=None)
@given(files())
def test_spans_nest_and_do_not_overlap(text):
    doc = tdl.loads(text)
    walk(doc.root, text, (0, len(text)))
    assert doc.metadata.start >= (1 if text.startswith("\ufeff") else 0)


@settings(max_examples=300, deadline=None)
@given(st.binary(max_size=200), st.booleans())
def test_load_on_arbitrary_bytes_raises_only_tdl_errors(data, with_head):
    payload = (HEAD.encode() + b"Shell {\n" + data) if with_head else data
    try:
        tdl.load(io.BytesIO(payload))
    except tdl.TDLError:
        pass


def test_dump_keeps_the_byte_order_mark_and_each_line_ending():
    text = "\ufeff" + HEAD.replace("\n", "\r\n") + "Shell {\r\n  Width: 1\n}"
    out = io.BytesIO()
    tdl.dump(tdl.loads(text), out)
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
    with pytest.raises(tdl.TDLSyntaxError) as raised:
        tdl.loads(text)
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
    with pytest.raises(tdl.TDLSyntaxError) as raised:
        tdl.load(reader, limits=tdl.Limits(max_bytes=limit))
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

    assert tdl.dumps(tdl.load(Trickle())) == data.decode()
