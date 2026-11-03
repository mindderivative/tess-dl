"""Positions in a TDL text."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Origin:
    """A place in a file: 1-based `line` and `column` (columns count characters).

    `end_line` and `end_column` are where the thing ends (exclusive) and `offset` is the
    byte offset of its start in the UTF-8 text. `file` is the label given as `path`.
    """

    file: str | None
    line: int
    column: int
    end_line: int
    end_column: int
    offset: int

    def __str__(self) -> str:
        return f"{self.file or '<text>'}:{self.line}:{self.column}"
