"""Bytes to text for `load` (private)."""

from .errors import TDLSyntaxError, syntax_error
from .origin import Origin


def decode(data: bytes, path: str | None) -> str:
    """UTF-8 text from bytes, keeping a leading byte-order mark.

    An invalid byte raises `tdl-bad-encoding`. Its line and column come from the valid text
    before it (G21), and its `offset` is the byte offset of the bad byte.
    """
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _bad_encoding(data, error.start, path) from None


def _bad_encoding(data: bytes, offset: int, path: str | None) -> TDLSyntaxError:
    prefix = data[:offset].decode("utf-8")
    line = 1 + prefix.count("\n")
    start = prefix.rfind("\n") + 1
    column = 1 + len(prefix) - start
    if line == 1 and prefix.startswith("\ufeff"):
        column -= 1  # the byte-order mark is not counted, as in every other position
    origin = Origin(path, line, column, line, column, offset)
    return syntax_error(
        "tdl-bad-encoding",
        origin,
        message=f"The bytes are not valid UTF-8: the byte at offset {offset} is not.",
    )
