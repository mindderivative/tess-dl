"""Turns character offsets into line, column and byte positions (private)."""

import re
from bisect import bisect_right

from .origin import Origin

_NEWLINE = re.compile("\n")


class Source:
    """The text of one file and its line index. Built once, then only read."""

    __slots__ = ("_ascii", "_starts", "path", "text")

    def __init__(self, text: str, path: str | None) -> None:
        self.text = text
        self.path = path
        self._ascii = text.isascii()
        # A leading byte-order mark is not counted: the first line starts after it.
        starts = [1 if text.startswith("\ufeff") else 0]
        starts.extend(m.end() for m in _NEWLINE.finditer(text))
        self._starts = starts

    def line_column(self, offset: int) -> tuple[int, int]:
        line = max(1, bisect_right(self._starts, offset))
        return line, max(1, offset - self._starts[line - 1] + 1)

    def byte_offset(self, offset: int) -> int:
        return offset if self._ascii else len(self.text[:offset].encode("utf-8"))

    def origin(self, start: int, end: int) -> Origin:
        line, column = self.line_column(start)
        end_line, end_column = self.line_column(end)
        return Origin(self.path, line, column, end_line, end_column, self.byte_offset(start))
