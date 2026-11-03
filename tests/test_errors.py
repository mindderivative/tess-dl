"""The error object and the bytes error (step 4); the corpus checks each code's first position."""

import json
from pathlib import Path

import pytest

CORPUS = Path(__file__).parent / "corpus" / "errors"


def test_bad_encoding_corpus_case_points_at_the_character_before_the_bad_byte():
    import tdl
    from tdl._decode import decode

    data = (CORPUS / "bad-encoding.tdl").read_bytes()
    expected = json.loads((CORPUS / "bad-encoding.expect.json").read_text("utf-8"))["errors"][0]
    with pytest.raises(tdl.TDLSyntaxError) as raised:
        decode(data, "bad-encoding.tdl")
    error = raised.value
    assert (error.code, error.origin.line, error.origin.column) == (
        expected["code"],
        expected["line"],
        expected["column"],
    )
    assert error.origin.offset == data.index(b"\xff")
    assert str(error.origin.offset) in error.message


@pytest.mark.parametrize(
    ("data", "line", "column", "offset"),
    [
        (b"\xff", 1, 1, 0),
        (b"\xef\xbb\xbf\xff", 1, 1, 3),  # a byte-order mark is not a column
        ("é😀".encode() + b"\xff", 1, 3, 6),  # columns count characters, offsets bytes
        (b"a\nbb\n\xc3", 3, 1, 5),  # a cut-off multi-byte character at the end
        (b"a\r\nb\x80", 2, 2, 4),  # \r\n is one line break
    ],
)
def test_bad_encoding_position_comes_from_the_valid_text_before_it(data, line, column, offset):
    import tdl
    from tdl._decode import decode

    with pytest.raises(tdl.TDLSyntaxError) as raised:
        decode(data, None)
    origin = raised.value.origin
    assert (origin.line, origin.column, origin.offset) == (line, column, offset)


def test_valid_bytes_decode_and_keep_the_byte_order_mark():
    from tdl._decode import decode

    assert decode("\ufeffé\r\n".encode(), None) == "\ufeffé\r\n"
