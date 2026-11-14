"""The formatter (private): the canonical layout of a block or a document (G36).

It writes the tree back out from the source text of each node, so a value, a slot, a string or a
comment is never changed, only where it stands: two spaces per level, one entry per line, a blank
line kept where the source had one or more. The result is read again and must hold the same content
and the same comments as the input, or the format is refused.
"""

import re
from typing import Any

from ._edit import _BLOCK_PROBE_HEAD, _dedent, _indent, _line_start, _probe
from .tree import Block, Comment, Document, Entry, For, If, Property

_STEP = "  "
_SPACE = re.compile(r"[ \t\r\n]*")


def _eol_of(text: str) -> str:
    """The line ending of the first line, which the whole output uses."""
    first = text.find("\n")
    return "\r\n" if first > 0 and text[first - 1] == "\r" else "\n"


def _line_comment(text: str, after: int) -> str | None:
    """A comment on the same line after `after`, exactly as written (it starts with `#`)."""
    end = text.find("\n", after)
    rest = text[after : len(text) if end < 0 else end].strip()
    return rest if rest.startswith("#") else None


def _comments(node: Any) -> list[str]:
    """The text of every comment in a document or block, in source order. A comment at the end of
    a metadata line is not an entry of the tree, so it is read from the text."""
    if isinstance(node, Comment):
        return [node.text]
    if isinstance(node, Document):
        found: list[str] = []
        for entry in node.metadata.entries:
            found += _comments(entry)
            if isinstance(entry, Property):
                trailing = _line_comment(node.text, entry.value.end)
                found += [] if trailing is None else [trailing[1:].strip()]
        return found + _comments(node.root)
    if isinstance(node, Block):
        return _comments_of(node.entries)
    if isinstance(node, If):
        return _comments_of(node.body) + _comments_of(node.else_body or ())
    if isinstance(node, For):
        return _comments_of(node.body)
    return []


def _comments_of(entries: tuple[Entry, ...] | tuple[Property | Comment, ...]) -> list[str]:
    return [c for entry in entries for c in _comments(entry)]


def _trivia(region: str, *, lead: bool, trail: bool) -> list[str]:
    """The comment lines and blank lines of a stretch of text between nodes: one blank line where
    there were several, and none at the start unless `lead` or at the end unless `trail`."""
    out: list[str] = []
    for raw in region.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if line:
            out.append(line)
        elif not out or out[-1] != "":
            out.append("")
    if not lead:
        while out and out[0] == "":
            out.pop(0)
    if not trail:
        while out and out[-1] == "":
            out.pop()
    return out


class _Renderer:
    """Writes entries as lines (without line endings) from the source text they came from."""

    def __init__(self, text: str, *, metadata: bool = False) -> None:
        self.text = text
        self.metadata = metadata  # a comment at the end of a metadata line is not an entry

    def entries(self, entries: tuple[Any, ...], depth: int) -> list[str]:
        text = self.text
        indent = _STEP * depth
        out: list[str] = []
        previous_end: int | None = None
        for entry in entries:
            if isinstance(entry, Comment):
                body = text[entry.start : entry.end].rstrip()
                shares_line = text[_line_start(text, entry.start) : entry.start].strip(" \t\r")
                if out and shares_line:  # a comment at the end of a line stays at its end
                    out[-1] += "  " + body
                    previous_end = entry.end
                    continue
                lines = [indent + body]
            else:
                lines = self.entry(entry, depth)
                if self.metadata and isinstance(entry, Property):
                    trailing = _line_comment(text, entry.value.end)
                    if trailing is not None:
                        lines[-1] += "  " + trailing
            if previous_end is not None and text.count("\n", previous_end, entry.start) >= 2:
                out.append("")
            out.extend(lines)
            previous_end = entry.end
        return out

    def entry(self, entry: Entry, depth: int) -> list[str]:
        indent = _STEP * depth
        text = self.text
        if isinstance(entry, Property):
            return self.property(entry, indent)
        if isinstance(entry, Block):
            return self.body(f"{indent}{entry.type} {{", entry.entries, depth)
        if isinstance(entry, If):
            return self.if_(entry, depth)
        assert isinstance(entry, For)
        head = (
            f"{indent}For {', '.join(entry.variables)} In"
            f" {text[entry.items.start : entry.items.end]}"
            f" Key {text[entry.key.start : entry.key.end]} {{"
        )
        return self.body(head, entry.body, depth)

    def body(self, head: str, entries: tuple[Entry, ...], depth: int) -> list[str]:
        if not entries:
            return [head + " }"]
        return [head, *self.entries(entries, depth + 1), _STEP * depth + "}"]

    def property(self, entry: Property, indent: str) -> list[str]:
        """`Key: value`; a value on several lines (a list) keeps its inner layout, re-based."""
        text = self.text
        first, *rest = text[entry.value.start : entry.value.end].replace("\r\n", "\n").split("\n")
        lines = [f"{indent}{entry.key}: {first}"]
        original = _indent(text, entry.start)
        for line in rest:
            kept = line[len(original) :] if line.startswith(original) else line.lstrip()
            lines.append(indent + kept)
        return lines

    def if_(self, entry: If, depth: int) -> list[str]:
        indent = _STEP * depth
        text = self.text
        head = f"{indent}If {text[entry.condition.start : entry.condition.end]} {{"
        if entry.else_body is None:
            return self.body(head, entry.body, depth)
        lines = [head, *self.entries(entry.body, depth + 1)]
        between = self.between_if_and_else(entry)
        if between:  # Else may follow comments on later lines (G17); they stay where they were
            lines += [indent + "}", *[indent + c for c in between], indent + "Else {"]
        else:
            lines.append(indent + "} Else {")
        return [*lines, *self.entries(entry.else_body, depth + 1), indent + "}"]

    def between_if_and_else(self, entry: If) -> list[str]:
        """The comments between the closing brace of an `If` body and its `Else`."""
        text = self.text
        start = entry.body[-1].end if entry.body else entry.condition.end
        pos = text.index("}", start) + 1
        found: list[str] = []
        while True:
            match = _SPACE.match(text, pos)
            assert match is not None
            pos = match.end()
            if text[pos : pos + 1] != "#":
                return found
            end = text.find("\n", pos)
            end = len(text) if end < 0 else end
            found.append(text[pos:end].rstrip())
            pos = end


def _before(text: str, start: int, end: int, *, lead: bool) -> list[str]:
    """The comment and blank lines between `start` and the head of a root block at `end`. The
    piece after the last line ending is the root's own line and is not one of them."""
    head, separator, _ = text[start:end].rpartition("\n")
    return _trivia(head, lead=lead, trail=True) if separator else []


def _after(text: str, end: int) -> tuple[str | None, list[str]]:
    """What follows a root block: a comment at the end of its line, then comment lines."""
    line_end = text.find("\n", end)
    line_end = len(text) if line_end < 0 else line_end
    rest = text[end:line_end].strip()
    lines = _trivia(text[line_end + 1 :], lead=True, trail=False)
    return (rest if rest.startswith("#") else None), lines


def _with_comments(lines: list[str]) -> list[str]:
    """`lines` if any of them is a comment: a blank line only separates a block from a comment."""
    return lines if any(lines) else []


def _check(old: Document | Block, new: Document | Block) -> None:
    if old.canonical() != new.canonical() or _comments(old) != _comments(new):
        raise ValueError("Formatting would change the content or the comments, so it was refused")


def format_block(text: str) -> str:
    """The canonical layout of one block, without a trailing line ending.

    `text` is the TDL of exactly one block, as for `Block.with_child`; a comment line above it or
    after it is kept. Errors are `TDLSyntaxError`s with origins inside `text`. Formatting the
    result again changes nothing.
    """
    root = _probe(_dedent(text))
    source = root.source
    assert source is not None
    src = source.text
    lines = _with_comments(_before(src, len(_BLOCK_PROBE_HEAD), root.start, lead=False))
    lines += _Renderer(src).entry(root, 0)
    trailing, after = _after(src, root.end)
    if trailing:
        lines[-1] += "  " + trailing
    lines += _with_comments(after)
    out = _eol_of(text).join(lines)
    _check(root, _probe(_dedent(out)))
    return out


def format_document(document: Document) -> Document:
    """The canonical layout of a whole document, as a new `Document` (G36).

    Two spaces per level, one entry per line (no `,` between entries), `Type { }` for an empty
    block, `} Else {` on one line, a comment at the end of a line kept there, one blank line where
    the source had one or more, and the line ending of the first line throughout. The text always
    ends with one line ending. Values, slots and strings are written as they were. Raises
    `TDLSyntaxError` if the text is not valid, and formatting the result changes nothing.
    """
    from ._parser import loads

    old = loads(document.text, path=document.path)  # a document with errors cannot be formatted
    text = old.text
    renderer = _Renderer(text)
    lines = ["---", *_Renderer(text, metadata=True).entries(old.metadata.entries, 0), "---"]
    lines += _before(text, old.metadata.end, old.root.start, lead=True)
    lines += renderer.entry(old.root, 0)
    trailing, after = _after(text, old.root.end)
    if trailing:
        lines[-1] += "  " + trailing
    lines += after
    while lines and lines[-1] == "":
        lines.pop()
    eol = _eol_of(text)
    out = ("\ufeff" if text.startswith("\ufeff") else "") + eol.join(lines) + eol
    new = loads(out, path=document.path)
    _check(old, new)
    return new
