"""The edit calls (private): splice new text into the old, reparse, return a new `Document`.

An edit changes only the bytes it names. The result is always read again, so an edit that would
make the file invalid raises `TDLError` and the original `Document` is untouched. The rules for
where a new line goes are G24 and G32 in docs/decisions.md.
"""

import re

from ._parser import _KEY, _RESERVED, loads
from .tree import Block, Document, Property

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
