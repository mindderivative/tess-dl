"""The tree a TDL file is read into. Nodes are immutable and keep where they came from."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field

from ._source import Source
from .origin import Origin

type Data = dict[str, object]


@dataclass(frozen=True, slots=True)
class _Node:
    """Where a node came from: character offsets into the text, and the text's line index.

    These never take part in `==`, so a tree read from text equals the same tree built in code.
    """

    start: int = field(default=-1, compare=False, repr=False, kw_only=True)
    end: int = field(default=-1, compare=False, repr=False, kw_only=True)
    source: Source | None = field(default=None, compare=False, repr=False, kw_only=True)

    @property
    def origin(self) -> Origin | None:
        """Where the node starts and ends, or `None` for a node built in code."""
        if self.source is None:
            return None
        return self.source.origin(self.start, self.end)


# Values


@dataclass(frozen=True, slots=True)
class Word(_Node):
    """Unquoted text: `TOP`, `true`, `Hello world`."""

    text: str

    def canonical(self) -> Data:
        return {"word": self.text}


@dataclass(frozen=True, slots=True)
class String(_Node):
    """`"..."` or `'...'`: `value` has the escapes resolved, `text` is as written."""

    value: str
    text: str

    def canonical(self) -> Data:
        return {"string": self.value}


@dataclass(frozen=True, slots=True)
class Number(_Node):
    """`16`, `-4`, `0.9`: an `int` or a `float`."""

    value: int | float
    text: str

    def canonical(self) -> Data:
        return {"number": self.value}


@dataclass(frozen=True, slots=True)
class Percent(_Node):
    """`50%`."""

    value: int
    text: str

    def canonical(self) -> Data:
        return {"percent": self.value}


@dataclass(frozen=True, slots=True)
class Slot(_Node):
    """`{{ expression }}`: `text` is exactly what lies between the braces, nothing trimmed."""

    text: str
    text_start: int = field(default=-1, compare=False, repr=False, kw_only=True)

    @property
    def text_origin(self) -> Origin | None:
        """Where `text` starts: the first character after `{{`. For TEL."""
        if self.source is None:
            return None
        return self.source.origin(self.text_start, self.text_start)

    def canonical(self) -> Data:
        return {"slot": self.text}


@dataclass(frozen=True, slots=True)
class Template(_Node):
    """Text with a slot in it, `Battery {{ battery.percent }}%`: strings and slots in order."""

    parts: tuple[str | Slot, ...]

    def canonical(self) -> Data:
        return {
            "template": [
                {"text": part} if isinstance(part, str) else part.canonical() for part in self.parts
            ]
        }


@dataclass(frozen=True, slots=True)
class Call(_Node):
    """`rgba(0 0 0 0.5)`: a name and the values written in the parentheses."""

    name: str
    args: tuple[Value, ...]

    def canonical(self) -> Data:
        return {"call": self.name, "args": [arg.canonical() for arg in self.args]}


@dataclass(frozen=True, slots=True)
class List(_Node):
    """`[a, b, c]`."""

    items: tuple[Value, ...]

    def canonical(self) -> Data:
        return {"list": [item.canonical() for item in self.items]}


type Value = Word | String | Number | Percent | Call | List | Slot | Template


# Entries


@dataclass(frozen=True, slots=True)
class Comment(_Node):
    """A `#` comment kept where it stands. `text` is what follows the `#`, trimmed."""

    text: str


@dataclass(frozen=True, slots=True)
class Property(_Node):
    """`Key: value`."""

    key: str
    value: Value

    @property
    def key_origin(self) -> Origin | None:
        if self.source is None:
            return None
        return self.source.origin(self.start, self.start + len(self.key))

    @property
    def value_origin(self) -> Origin | None:
        return self.value.origin

    def canonical(self) -> Data:
        return {"property": self.key, "value": self.value.canonical()}


@dataclass(frozen=True, slots=True)
class Block(_Node):
    """`Type { entries }`. `type` is the word before the brace."""

    type: str
    entries: tuple[Entry, ...]

    @property
    def name(self) -> str | None:
        """The value of `Name:` in this block, or `None`."""
        for entry in self.entries:
            if isinstance(entry, Property) and entry.key == "Name":
                match entry.value:
                    case Word(text=text):
                        return text
                    case String(value=value):
                        return value
                    case _:
                        return None
        return None

    def canonical(self) -> Data:
        return {"block": self.type, "entries": _canonical_entries(self.entries)}


@dataclass(frozen=True, slots=True)
class If(_Node):
    """`If {{ c }} { ... }` and an optional `Else { ... }` (`else_body` is `None` without one)."""

    condition: Slot
    body: tuple[Entry, ...]
    else_body: tuple[Entry, ...] | None

    def canonical(self) -> Data:
        return {
            "if": self.condition.canonical(),
            "body": _canonical_entries(self.body),
            "else": None if self.else_body is None else _canonical_entries(self.else_body),
        }


@dataclass(frozen=True, slots=True)
class For(_Node):
    """`For variable In {{ items }} Key {{ key }} { ... }`."""

    variable: str
    items: Slot
    key: Slot
    body: tuple[Entry, ...]

    def canonical(self) -> Data:
        return {
            "for": self.variable,
            "in": self.items.canonical(),
            "key": self.key.canonical(),
            "body": _canonical_entries(self.body),
        }


type Entry = Block | Property | If | For | Comment


def _canonical_entries(entries: tuple[Entry, ...]) -> list[Data]:
    return [entry.canonical() for entry in entries if not isinstance(entry, Comment)]


# The document


@dataclass(frozen=True, slots=True)
class Metadata(_Node, Mapping[str, Word | String]):
    """The block between the two `---` lines: a mapping from key to value.

    `entries` also holds the comments, in source order.
    """

    entries: tuple[Property | Comment, ...]

    def __getitem__(self, key: str) -> Word | String:
        for entry in self.entries:
            if isinstance(entry, Property) and entry.key == key:
                value = entry.value
                assert isinstance(value, Word | String)
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (entry.key for entry in self.entries if isinstance(entry, Property))

    def __len__(self) -> int:
        return sum(1 for entry in self.entries if isinstance(entry, Property))


@dataclass(frozen=True, slots=True)
class Document:
    """A TDL file: its metadata, its root block and the source `text`."""

    metadata: Metadata
    root: Block
    path: str | None
    text: str
    language_version: str

    def canonical(self) -> Data:
        """The content with no positions and no comments (G22), for tests and tools."""
        return {
            "metadata": {key: value.canonical() for key, value in self.metadata.items()},
            "root": self.root.canonical(),
        }
