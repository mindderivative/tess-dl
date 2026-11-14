"""The edit calls (private): splice new text into the old, reparse, return a new `Document`.

An edit changes only the bytes it names. The result is always read again, so an edit that would
make the file invalid raises `TDLError` and the original `Document` is untouched. The rules for
where a new line goes are G24 and G32 in docs/decisions.md.
"""

import dataclasses
import re
import textwrap
from collections.abc import Sequence

from ._parser import _KEY, _RESERVED, loads
from .errors import TDLSyntaxError
from .origin import Origin
from .tree import Block, Comment, Document, Entry, For, If, Property, Slot

VERSION_KEYS = frozenset({"TDL", "Shell"})
_UNSAFE_WORD = re.compile(r"[\r\n]|[ \t]#")
_ESCAPED = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\u000d"}
_PROBE_HEAD = "---\nTDL: 0.1\nName: T\n---\nS {\nK: "


# Text helpers. Positions are character offsets into the document text.


def _next_line(text: str, pos: int) -> int:
    """Where the line that holds `pos` ends, after its line ending."""
    i = text.find("\n", pos)
    return len(text) if i < 0 else i + 1


def _line_start(text: str, pos: int) -> int:
    return text.rfind("\n", 0, pos) + 1


def _eol_before(text: str, at: int) -> str:
    """The line ending of the line that ends at `at`; a file with no line ending uses `\\n`."""
    return "\r\n" if text[at - 2 : at] == "\r\n" else "\n"


def _indent(text: str, pos: int) -> str:
    """The whitespace that starts the line holding `pos`."""
    start = _line_start(text, pos)
    return text[start : start + len(text[start:]) - len(text[start:].lstrip(" \t"))]


def _check_key(key: str) -> None:
    if _KEY.fullmatch(key) is None:
        raise ValueError(f"{key!r} is not a valid key: a letter, then letters, digits and _")


def _closing_fence_start(text: str, metadata_end: int) -> int:
    stop = metadata_end
    if text[stop - 1 : stop] == "\n":
        stop -= 1
    if text[stop - 1 : stop] == "\r":
        stop -= 1
    return text.rfind("\n", 0, stop) + 1


def _metadata_text(value: str) -> str:
    """`value` as TDL: a bare word when it reads back the same, else a quoted string."""
    bare = (
        value != ""
        and value == value.strip(" \t")
        and value[0] not in "\"'#"
        and _UNSAFE_WORD.search(value) is None
    )
    if bare:
        return value
    return '"' + "".join(_ESCAPED.get(ch, ch) for ch in value) + '"'


# The calls. Each returns the new text.


def with_metadata(doc: Document, key: str, value: str) -> str:
    _check_key(key)
    text = doc.text
    rendered = _metadata_text(value)
    entries = [e for e in doc.metadata.entries if isinstance(e, Property)]
    for entry in entries:
        if entry.key == key:
            return text[: entry.value.start] + rendered + text[entry.value.end :]
    versions = [e for e in entries if e.key in VERSION_KEYS]
    if key == "UID" and versions:
        at = _next_line(text, versions[-1].end)
    else:
        at = _closing_fence_start(text, doc.metadata.end)
    return text[:at] + f"{key}: {rendered}{_eol_before(text, at)}" + text[at:]


def without_metadata(doc: Document, key: str) -> str:
    text = doc.text
    for entry in doc.metadata.entries:
        if isinstance(entry, Property) and entry.key == key:
            return text[: _line_start(text, entry.start)] + text[_next_line(text, entry.end) :]
    return text


def replace(doc: Document, start: int, end: int, new: str) -> str:
    text = doc.text
    if not 0 <= start <= end <= len(text):
        raise ValueError(f"The span {start}:{end} is outside the text (0 to {len(text)})")
    return text[:start] + new + text[end:]


def with_property(block: Block, key: str, value: str) -> tuple[str, str | None]:
    """The new text and the path of the document, for a block read from text."""
    source = block.source
    if source is None:
        raise ValueError("A block built in code has no text to edit")
    _check_key(key)
    if key in _RESERVED:
        raise ValueError(f"{key!r} is reserved and cannot be a property key")
    value = value.strip(" \t")
    _check_value(value)
    text = source.text
    for entry in block.entries:
        if isinstance(entry, Property) and entry.key == key:
            return text[: entry.value.start] + value + text[entry.value.end :], source.path
    props = [e for e in block.entries if isinstance(e, Property)]
    line = f"{key}: {value}"
    if props:
        last = props[-1]
        rest = text[last.end : _next_line(text, last.end)].strip().removeprefix(",").strip()
        if rest == "" or rest.startswith("#"):
            at = _next_line(text, last.end)
            new = _indent(text, last.start) + line + _eol_before(text, at)
            return text[:at] + new + text[at:], source.path
        return text[: last.end] + ", " + line + text[last.end :], source.path
    brace = text.index("{", block.start + len(block.type))
    after = text[brace + 1 : _next_line(text, brace)].strip()
    if after == "" or after.startswith("#"):
        at = _next_line(text, brace)
        first = block.entries[0] if block.entries else None
        indent = _indent(text, first.start) if first else _indent(text, block.start) + "  "
        return text[:at] + indent + line + _eol_before(text, at) + text[at:], source.path
    tail = "," if block.entries else ""
    return text[: brace + 1] + " " + line + tail + text[brace + 1 :], source.path


def _check_value(value: str) -> None:
    """`value` must be exactly one TDL value on one line; anything else would change the file."""
    if value == "" or "\n" in value or "\r" in value:
        raise ValueError(f"{value!r} is not a single-line TDL value")
    try:
        probe = loads(_PROBE_HEAD + value + "\n}\n")
    except Exception:
        raise ValueError(f"{value!r} is not a valid TDL value") from None
    entries = probe.root.entries
    if len(entries) != 1 or not isinstance(entries[0], Property):
        raise ValueError(f"{value!r} is not a single TDL value")
    if entries[0].value.end != len(_PROBE_HEAD) + len(value):
        raise ValueError(f"{value!r} is not a single TDL value: it has text after the value")


# Block edits (T-011): without_property, with_child, without_child, move_child.
#
# Each one splices text at the entries' own positions, rereads the result, and then checks that
# the block holds exactly the entries it should: the old ones, minus or plus the one named. An edit
# that would change anything else (a text that reads differently in its new place) is refused.

_BLOCK_PROBE_HEAD = "---\nTDL: 0.1\nName: T\n---\n"
_PROBE_LINES = _BLOCK_PROBE_HEAD.count("\n")
_PROBE_BYTES = len(_BLOCK_PROBE_HEAD)


def _source_of(block: Block) -> tuple[str, str | None]:
    source = block.source
    if source is None:
        raise ValueError("A block built in code has no text to edit")
    return source.text, source.path


def _own_line(text: str, entry: Entry) -> tuple[bool, bool]:
    """Whether the entry starts its line (only space before it) and ends it (only a comma,
    space or comment after it)."""
    before = text[_line_start(text, entry.start) : entry.start]
    line_end = text.find("\n", entry.end)
    rest = text[entry.end : len(text) if line_end < 0 else line_end]
    after = rest.strip(" \t\r,")
    return before.strip(" \t\r") == "", after == "" or after.startswith("#")


def _removal_span(text: str, entry: Entry) -> tuple[int, int]:
    """The text to delete with an entry: its lines, or it and one separating comma."""
    starts, ends = _own_line(text, entry)
    if starts and ends:
        return _line_start(text, entry.start), _next_line(text, entry.end)
    if ends:  # it follows something on its first line: take the space before it
        start = entry.start
        while start > 0 and text[start - 1] in " \t":
            start -= 1
        return start, entry.end
    after = entry.end
    while after < len(text) and text[after] in " \t":
        after += 1
    if text[after : after + 1] == ",":  # `A: 1, B: 2`: take the comma and space after it
        after += 1
        while after < len(text) and text[after] in " \t":
            after += 1
        return entry.start, after
    before = entry.start
    while before > 0 and text[before - 1] in " \t":
        before -= 1
    if text[before - 1 : before] == ",":  # the last of `A: 1, B: 2 }`: take the comma before it
        return before - 1, entry.end
    return entry.start, after  # the only entry of `{ A: 1 }`: take the space after it


def _inside(entry: Entry, span: tuple[int, int]) -> bool:
    return span[0] <= entry.start and entry.end <= span[1]


def _apply(block: Block, new_text: str, expected: tuple[Entry, ...]) -> Document:
    """Reread `new_text`; the block must hold exactly `expected`, or the edit is refused."""
    from ._parser import loads

    source = block.source
    assert source is not None
    doc = loads(new_text, path=source.path)
    try:
        found = doc.at(block.index_path)
    except IndexError, ValueError:
        found = None
    if not isinstance(found, Block) or found.entries != expected:
        raise ValueError("This edit would change more than the entry it names, so it was refused")
    return doc


def _resolve(block: Block, child: Block | If | For | int) -> tuple[int, Entry]:
    entries = block.entries
    if isinstance(child, int) and not isinstance(child, bool):
        if not 0 <= child < len(entries):
            raise IndexError(f"index {child}: this block has {len(entries)} entries")
        index = child
    else:
        index = next((i for i, e in enumerate(entries) if e is child), -1)
        if index < 0:
            raise ValueError(
                "The child is not an entry of this block (is it from an older Document?)"
            )
    entry = entries[index]
    if not isinstance(entry, Block | If | For):
        raise ValueError(f"Entry {index} is a {type(entry).__name__}, not a block, If or For")
    return index, entry


def without_property(block: Block, key: str) -> Document:
    text, _ = _source_of(block)
    target = next((e for e in block.entries if isinstance(e, Property) and e.key == key), None)
    if target is None:
        raise KeyError(key)
    return _remove(block, text, target)


def _remove(block: Block, text: str, target: Entry) -> Document:
    span = _removal_span(text, target)
    expected = tuple(e for e in block.entries if not _inside(e, span))
    return _apply(block, text[: span[0]] + text[span[1] :], expected)


def without_child(block: Block, child: Block | If | For | int) -> Document:
    text, _ = _source_of(block)
    _, entry = _resolve(block, child)
    return _remove(block, text, entry)


def _dedent(text: str) -> list[str]:
    """The lines of `text` without their common indentation or blank lines at either end."""
    lines = text.replace("\r\n", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    return textwrap.dedent("\n".join(lines)).split("\n") if lines else []


def _shift(origin: Origin) -> Origin:
    """An origin in the probe file as an origin in the block text."""
    return Origin(
        "<block_text>",
        max(1, origin.line - _PROBE_LINES),
        origin.column,
        max(1, origin.end_line - _PROBE_LINES),
        origin.end_column,
        max(0, origin.offset - _PROBE_BYTES),
    )


def _probe(lines: list[str]) -> Block:
    """Read `lines` as the root block of a file; the errors point inside the lines."""
    from ._parser import loads

    try:
        return loads(_BLOCK_PROBE_HEAD + "\n".join(lines) + "\n").root
    except TDLSyntaxError as error:
        message = error.message
        if error.code == "tdl-duplicate-key":
            message = re.sub(
                r"line (\d+)", lambda m: f"line {int(m.group(1)) - _PROBE_LINES}", message
            )
        raise TDLSyntaxError(
            error.code,
            message,
            error.hint,
            _shift(error.origin),
            tuple(_shift(o) for o in error.related),
        ) from None


def _lines_text(lines: list[str], indent: str, eol: str) -> str:
    return "".join((indent + line if line else "") + eol for line in lines)


def _inline_text(lines: list[str], continuation: str, eol: str) -> str:
    return lines[0] + "".join(eol + continuation + line if line else eol for line in lines[1:])


def _plan_insert(
    text: str, block: Block, rest: Sequence[Entry], index: int, lines: list[str]
) -> tuple[int, int, str]:
    """The splice (start, end, new text) that puts `lines`, a dedented block, at `index` among
    the entries `rest` of `block`: on its own lines where the neighbours are, else inline."""
    head_indent = _indent(text, block.start)
    continuation = head_indent + "  "
    if index < len(rest):
        target = rest[index]
        starts, _ = _own_line(text, target)
        if starts:
            at = _line_start(text, target.start)
            return at, at, _lines_text(lines, _indent(text, target.start), _eol_before(text, at))
        # (an index never points at a comment at the end of a line: `_settle` moved it)
        eol = _eol_before(text, _next_line(text, target.start))
        return target.start, target.start, _inline_text(lines, continuation, eol) + ", "
    if rest:
        last = rest[-1]
        starts, ends = _own_line(text, last)
        if ends:
            at = _next_line(text, last.end)
            indent = _indent(text, last.start) if starts else continuation
            return at, at, _lines_text(lines, indent, _eol_before(text, at))
        eol = _eol_before(text, _next_line(text, last.end))
        return last.end, last.end, ", " + _inline_text(lines, continuation, eol)
    brace = text.index("{", block.start + len(block.type))
    after = text[brace + 1 : _next_line(text, brace)].strip(" \t\r\n")
    if after == "" or after.startswith("#"):
        at = _next_line(text, brace)
        return at, at, _lines_text(lines, continuation, _eol_before(text, at))
    eol = _eol_before(text, _next_line(text, brace))
    return brace + 1, brace + 1, " " + _inline_text(lines, continuation, eol)


def _settle(text: str, entries: Sequence[Entry], index: int) -> int:
    """Move an index that points at a comment at the end of a line past that comment, so a new
    entry never lands between an entry and its own trailing comment."""
    while (
        index < len(entries)
        and isinstance(entries[index], Comment)
        and not _own_line(text, entries[index])[0]
    ):
        index += 1
    return index


def with_child(block: Block, block_text: str, index: int | None) -> tuple[Document, Block]:
    text, _ = _source_of(block)
    entries = block.entries
    if index is None:
        index = len(entries)
    elif isinstance(index, bool) or not 0 <= index <= len(entries):
        raise IndexError(f"index {index}: this block has {len(entries)} entries")
    index = _settle(text, entries, index)
    lines = _dedent(block_text)
    child = _probe(lines)
    start, end, new = _plan_insert(text, block, entries, index, lines)
    doc = _apply(
        block, text[:start] + new + text[end:], entries[:index] + (child,) + entries[index:]
    )
    added = doc.at(block.index_path + (index,))
    assert isinstance(added, Block)
    return doc, added


def move_child(block: Block, child: Block | If | For | int, to: int) -> Document:
    from ._parser import loads

    text, path = _source_of(block)
    index, entry = _resolve(block, child)
    span = _removal_span(text, entry)
    moved = tuple(e for e in block.entries if _inside(e, span))
    rest = tuple(e for e in block.entries if not _inside(e, span))
    if isinstance(to, bool) or not 0 <= to <= len(rest):
        raise IndexError(f"to {to}: there are {len(rest)} other entries to place it among")
    to = _settle(text, rest, to)
    if to == index:
        return loads(text, path=path)
    starts, ends = _own_line(text, entry)
    if starts and ends:
        lines = _dedent(text[span[0] : span[1]])
    elif "\n" in text[entry.start : entry.end]:
        raise ValueError(
            "Only an entry on its own lines, or one on a single line, can be moved; use "
            "without_child and with_child for this one"
        )
    else:
        lines = [text[entry.start : entry.end]]
    start, end, new = _plan_insert(text, block, rest, to, lines)
    if start >= span[1]:
        new_text = text[: span[0]] + text[span[1] : start] + new + text[end:]
    elif end <= span[0]:
        new_text = text[:start] + new + text[end : span[0]] + text[span[1] :]
    else:
        raise ValueError("That entry cannot be moved there")
    return _apply(block, new_text, rest[:to] + moved + rest[to:])


# Slot and variable edits (T-040): For.with_items, For.with_key, If.with_condition,
# For.with_variable. Each replaces only the bytes of the slot or the variable it names.

_SLOT_PROBE_HEAD = _BLOCK_PROBE_HEAD + "S {\nK: "
_SLOT_LINE = _PROBE_LINES + 2  # the probe line that holds the slot text
_SLOT_COLUMN = len("K: ")  # what stands before the slot text on that line


def _shift_slot(origin: Origin) -> Origin:
    """An origin in the slot probe as an origin in the slot text."""

    def line(n: int) -> int:
        return max(1, n - _SLOT_LINE + 1)

    def column(n: int, at: int) -> int:
        return max(1, n - _SLOT_COLUMN) if at == _SLOT_LINE else n

    return Origin(
        "<slot_text>",
        line(origin.line),
        column(origin.column, origin.line),
        line(origin.end_line),
        column(origin.end_column, origin.end_line),
        max(0, origin.offset - len(_SLOT_PROBE_HEAD)),
    )


def _slot_probe(slot_text: str) -> str:
    """`slot_text` without the space around it, if it is exactly one slot (`{{ ... }}`)."""
    text = slot_text.strip(" \t\r\n")
    try:
        root = loads(_SLOT_PROBE_HEAD + text + "\n}\n").root
    except TDLSyntaxError as error:
        raise TDLSyntaxError(
            error.code,
            error.message,
            error.hint,
            _shift_slot(error.origin),
            tuple(_shift_slot(o) for o in error.related),
        ) from None
    entries = root.entries
    one = (
        len(entries) == 1
        and isinstance(entries[0], Property)
        and isinstance(entries[0].value, Slot)
        and entries[0].value.end == len(_SLOT_PROBE_HEAD) + len(text)
    )
    if not one:
        raise ValueError(f"{slot_text!r} is not exactly one slot, written {{{{ like this }}}}")
    return text


def _node_source(node: If | For) -> tuple[str, str | None]:
    source = node.source
    if source is None:
        raise ValueError("A node built in code has no text to edit")
    return source.text, source.path


def _apply_node[N: If | For](node: N, new_text: str, same: N) -> Document:
    """Reread `new_text`: the node at the same index path must be `same`, the node as it should
    now read, in full (its body and everything else it holds), or the edit is refused."""
    source = node.source
    assert source is not None
    doc = loads(new_text, path=source.path)
    try:
        found = doc.at(node.index_path)
    except IndexError, ValueError:
        found = None
    if type(found) is not type(node) or found != same:
        raise ValueError("This edit would change more than the slot it names, so it was refused")
    return doc


def _splice_slot(node: For | If, slot: Slot, slot_text: str) -> tuple[str, Slot]:
    """The text of `node`'s file with `slot` replaced by `slot_text`, and the slot as it reads."""
    text, _ = _node_source(node)
    new = _slot_probe(slot_text)
    return text[: slot.start] + new + text[slot.end :], dataclasses.replace(slot, text=new[2:-2])


def with_items(node: For, slot_text: str) -> Document:
    spliced, slot = _splice_slot(node, node.items, slot_text)
    return _apply_node(node, spliced, dataclasses.replace(node, items=slot))


def with_key(node: For, slot_text: str) -> Document:
    spliced, slot = _splice_slot(node, node.key, slot_text)
    return _apply_node(node, spliced, dataclasses.replace(node, key=slot))


def with_condition(node: If, slot_text: str) -> Document:
    spliced, slot = _splice_slot(node, node.condition, slot_text)
    return _apply_node(node, spliced, dataclasses.replace(node, condition=slot))


_FOR_HEAD = re.compile(r"For[ \t\r]+")


def with_variable(node: For, name: str) -> Document:
    text, _ = _node_source(node)
    if not isinstance(name, str) or _KEY.fullmatch(name) is None:
        raise ValueError(f"{name!r} is not a valid name: a letter, then letters, digits and _")
    if name in _RESERVED:
        raise ValueError(f"{name!r} is reserved and cannot be a loop variable")
    head = _FOR_HEAD.match(text, node.start)
    assert head is not None
    start = head.end()
    end = start + len(node.variable)
    assert text[start:end] == node.variable
    same = dataclasses.replace(node, variable=name)
    return _apply_node(node, text[:start] + name + text[end:], same)
