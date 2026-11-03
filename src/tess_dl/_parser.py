"""The reader: TDL text to a tree. Private; `tess_dl.loads` is the way in.

One pass over the text with a cursor and compiled patterns, recursive descent for nesting.
Nesting is capped by `Limits.max_depth` (64), far below Python's recursion limit.
The first mistake raises `TDLSyntaxError`; where each one points is in docs/language.md.
"""

import re
from typing import NoReturn

from ._source import Source
from .errors import TDLSyntaxError, syntax_error, too_large
from .limits import Limits
from .tree import (
    Block,
    Call,
    Comment,
    Document,
    Entry,
    For,
    If,
    List,
    Metadata,
    Number,
    ParseResult,
    Percent,
    Property,
    Slot,
    String,
    Template,
    Value,
    Word,
)

LANGUAGE_VERSION = "0.1"
_MAJOR = int(LANGUAGE_VERSION.split(".")[0])

_RESERVED = frozenset({"If", "Else", "For", "In", "Key"})
_BOM = "\ufeff"

_FENCE = re.compile(r"---[ \t]*(?:\r?\n|\Z)")
_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_INLINE = re.compile(r"[ \t\r]*")  # whitespace that stays on the line (a lone \r is whitespace)
_SKIP = re.compile(r"[ \t\r\n,]*")  # whitespace, line ends and entry separators
_TRIVIA = re.compile(r"[ \t\r\n]*")
_CALL = re.compile(r"([A-Za-z][A-Za-z0-9_]*)\(")
_NUMBER = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")
_PERCENT = re.compile(r"[0-9]+%")
_HEX4 = re.compile(r"[0-9a-fA-F]{4}")
_ELSE = re.compile(r"Else(?![A-Za-z0-9_])")
_IN = re.compile(r"In(?![A-Za-z0-9_])")
_KEYWORD = re.compile(r"Key(?![A-Za-z0-9_])")
_TOKEN = re.compile(r"[^ \t\r\n,)]+")
_SLOT_SCAN = re.compile(r"""\}\}|['"\n]""")
_QUOTE_SCAN = {q: re.compile(rf"[\\\n{q}]") for q in "\"'"}
# What ends an unquoted value: a line end, `,`, `}`, a `{` (a slot or a mistake), ` #`.
_RUN_END = {
    False: re.compile(r"[\n{,}]|[ \t]#"),
    True: re.compile(r"[\n{,}\]]|[ \t]#"),  # inside a list `]` ends it too
}
_ESCAPES = {"\\": "\\", '"': '"', "'": "'", "n": "\n", "t": "\t"}
_SPACE_AFTER_HASH = frozenset({"", " ", "\t", "\r", "\n"})


class _Stop(Exception):
    """Reading ends here: the error cap was reached or a limit error stopped the file."""


_FATAL = frozenset({"tdl-too-large", "tdl-too-deep", "tdl-bad-encoding"})
_RESYNC = re.compile(r"[\n{}]")  # the characters that decide where reading carries on


def _skip(pattern: re.Pattern[str], text: str, pos: int) -> int:
    """The end of a match of a pattern that can match nothing (so it always matches)."""
    match = pattern.match(text, pos)
    assert match is not None
    return match.end()


class _Reader:
    def __init__(self, text: str, path: str | None, limits: Limits) -> None:
        self.text = text
        self.n = len(text)
        self.limits = limits
        self.source = Source(text, path)
        self.errors: list[TDLSyntaxError] | None = None  # a list when `parse` collects errors
        self.last_at = 0  # where the last error was raised: reading resumes after it
        self.pair_close = -1  # the second `}` of a `}}` that was already reported

    # errors

    def error(
        self,
        code: str,
        at: int,
        *related: int,
        message: str | None = None,
        hint: str | None = None,
    ) -> TDLSyntaxError:
        self.last_at = at
        origin = self.source.origin(at, min(at + 1, self.n))
        others = tuple(self.source.origin(r, min(r + 1, self.n)) for r in related)
        return syntax_error(code, origin, others, message=message, hint=hint)

    def fail(
        self,
        code: str,
        at: int,
        *related: int,
        message: str | None = None,
        hint: str | None = None,
    ) -> NoReturn:
        raise self.error(code, at, *related, message=message, hint=hint)

    def signal(
        self,
        code: str,
        at: int,
        *related: int,
        message: str | None = None,
        hint: str | None = None,
    ) -> None:
        """A mistake the reader can read past: `parse` records it, `loads` stops at it."""
        error = self.error(code, at, *related, message=message, hint=hint)
        if self.errors is None:
            raise error
        self.record(error)

    def record(self, error: TDLSyntaxError) -> None:
        """Keeps an error in source order. At the cap the last entry says so, and reading stops."""
        errors = self.errors
        assert errors is not None
        cap = max(1, self.limits.max_errors)
        if len(errors) >= cap:
            last = errors[-1]
            note = f"The list stops at {cap} errors."
            if not last.message.endswith(note):
                message = f"{last.message} {note}"
                errors[-1] = TDLSyntaxError(
                    last.code, message, last.hint, last.origin, last.related
                )
            raise _Stop
        index = len(errors)
        while index > 0 and errors[index - 1].origin.offset > error.origin.offset:
            index -= 1
        errors.insert(index, error)

    def absorb(self, error: TDLSyntaxError) -> None:
        """`parse` keeps the error; one that ends the file (a limit) also stops the reading."""
        self.record(error)
        if error.code in _FATAL:
            raise _Stop

    def resync(self, at: int) -> int:
        """Where reading carries on after a mistake: the end of the bad line, or the `}` that
        closes the block the bad entry is in. Braces opened on the bad line itself are skipped."""
        depth = 0
        for hit in _RESYNC.finditer(self.text, at):
            char = hit.group()
            if char == "\n":
                return hit.start()
            if char == "{":
                depth += 1
            elif depth == 0:
                return hit.start()
            else:
                depth -= 1
        return self.n

    def too_deep(self, at: int) -> NoReturn:
        self.fail(
            "tdl-too-deep",
            at,
            message=f"Blocks are nested more than {self.limits.max_depth} levels deep.",
        )

    def check_size(self) -> None:
        """`tdl-too-large` before any parsing; text that is not UTF-8 is `tdl-bad-encoding`."""
        text = self.text
        limit = self.limits.max_bytes
        if len(text) > limit:
            raise too_large(self.source.path, limit)
        if text.isascii():
            return
        try:
            size = len(text.encode("utf-8"))
        except UnicodeEncodeError as error:
            self.fail(
                "tdl-bad-encoding",
                error.start,
                message="This text has a character that cannot be written as UTF-8.",
            )
        if size > limit:
            raise too_large(self.source.path, limit)

    # the file

    def document(self) -> Document:
        text = self.text
        self.check_size()
        first = 1 if text.startswith(_BOM) else 0
        fence = _FENCE.match(text, first)
        if fence is None:
            self.fail("tdl-no-metadata", first)
        metadata, after_fence = self.metadata(first, fence.end())
        version = self.check_metadata(metadata, first)
        root, end = self.root(after_fence)
        self.after_root(end)
        return Document(metadata, root, self.source.path, text, version)

    def parse_all(self) -> Document | None:
        """Reads as far as it can, recording every error; the best tree, or `None`."""
        self.errors = []
        try:
            return self.read_all()
        except _Stop:
            return None

    def read_all(self) -> Document | None:
        try:
            self.check_size()
            text = self.text
            first = 1 if text.startswith(_BOM) else 0
            fence = _FENCE.match(text, first)
            if fence is None:
                self.fail("tdl-no-metadata", first)
            metadata, after_fence = self.metadata(first, fence.end())
            version = self.check_metadata(metadata, first)
            root, end = self.root(after_fence)
            self.after_root(end)
        except TDLSyntaxError as error:
            self.absorb(error)  # nothing more can be read: no tree
            return None
        return Document(metadata, root, self.source.path, text, version)

    # metadata

    def metadata(self, opening: int, pos: int) -> tuple[Metadata, int]:
        """Reads the lines up to the closing `---`; returns the metadata and where it ends."""
        text = self.text
        entries: list[Property | Comment] = []
        first_seen: dict[str, int] = {}
        while True:
            if pos >= self.n:
                self.fail("tdl-metadata-unclosed", opening)
            line_end = text.find("\n", pos)
            next_line = self.n if line_end < 0 else line_end + 1
            fence = _FENCE.match(text, pos)
            if fence is not None:
                end = fence.end()
                break
            try:
                self.metadata_line(pos, entries, first_seen)
            except TDLSyntaxError as error:
                if self.errors is None:
                    raise
                self.absorb(error)  # a bad line is skipped; the next line is read
            pos = next_line
        return Metadata(tuple(entries), start=opening, end=end, source=self.source), end

    def metadata_line(
        self, pos: int, entries: list[Property | Comment], first_seen: dict[str, int]
    ) -> None:
        text = self.text
        at = _skip(_INLINE, text, pos)
        char = text[at : at + 1]
        if char == "" or char == "\n":
            return
        if char == "#":
            entries.append(self.comment(at))
            return
        key = _KEY.match(text, at)
        if key is None:
            self.fail("tdl-unexpected-text", at)
        colon = _skip(_INLINE, text, key.end())
        if text[colon : colon + 1] != ":":
            self.fail(
                "tdl-unexpected-text",
                colon,
                message="A key needs a colon and a value.",
            )
        name = key.group()
        if name in first_seen:
            self.fail(
                "tdl-duplicate-key",
                at,
                first_seen[name],
                message=f"The key {name} is already used on line "
                f"{self.source.line_column(first_seen[name])[0]}.",
            )
        first_seen[name] = at
        value = self.metadata_value(colon + 1)
        entries.append(Property(name, value, start=at, end=value.end, source=self.source))

    def metadata_value(self, pos: int) -> Word | String:
        text = self.text
        at = _skip(_INLINE, text, pos)
        char = text[at : at + 1]
        if char == '"' or char == "'":
            string, end = self.string(at)
            self.check_value_end(end, "")
            return string
        if char == "" or char == "\n":
            self.missing_value(at)
        if char == "#":
            self.hash_in_value_position(at)
        line_end = text.find("\n", at)
        line = text[at : self.n if line_end < 0 else line_end]
        comment = re.search(r"[ \t]#", line)
        if comment is not None:
            line = line[: comment.start()]
        word = line.rstrip(" \t\r")
        return Word(word, start=at, end=at + len(word), source=self.source)

    def check_metadata(self, metadata: Metadata, opening: int) -> str:
        """The required keys and the version; returns the language version ("" if none)."""
        if "TDL" not in metadata:
            self.signal("tdl-no-version", opening)
        if "Name" not in metadata:
            self.signal("tdl-no-name", opening)
        else:
            name = metadata["Name"]
            name_text = name.text if isinstance(name, Word) else name.value
            if _KEY.fullmatch(name_text) is None:
                self.signal("tdl-bad-name", name.start)
            elif name_text in _RESERVED:
                self.signal("tdl-reserved-name", name.start)
        if "TDL" not in metadata:
            return ""
        version = metadata["TDL"]
        version_text = version.text if isinstance(version, Word) else version.value
        major = re.match(r"[0-9]+", version_text)
        if major is None:
            self.signal(
                "tdl-unsupported-version",
                version.start,
                message=f"The TDL version {version_text} does not start with a number.",
                hint=f"Write TDL: {LANGUAGE_VERSION}",
            )
        elif int(major.group()) > _MAJOR:
            self.signal(
                "tdl-unsupported-version",
                version.start,
                message=f"This file is written for TDL {version_text}; this library reads "
                f"{LANGUAGE_VERSION}.",
            )
        return version_text

    # the root block

    def root(self, pos: int) -> tuple[Block, int]:
        text = self.text
        after_fence = pos
        at = self.trivia(pos)
        if at >= self.n:
            self.fail("tdl-no-root", after_fence)
        if text[at] == "}":
            self.close_without_block(at)
        head = _KEY.match(text, at)
        if head is None:
            self.fail("tdl-unexpected-text", at)
        brace = _skip(_INLINE, text, head.end())
        if text[brace : brace + 1] != "{":
            self.fail("tdl-unexpected-text", brace)
        if head.group() in _RESERVED:
            self.fail("tdl-reserved-name", at)
        return self.block(at, head.group(), brace, 1)

    def after_root(self, pos: int) -> None:
        """Only comments and blank lines may follow the root block."""
        text = self.text
        while True:
            at = self.trivia(pos)
            if at >= self.n:
                return
            if at == self.pair_close:  # the second `}` of a `}}` that was already reported
                pos = at + 1
                continue
            if text[at] == "}":
                pair = text.startswith("}}", at)
                self.signal("tdl-double-close" if pair else "tdl-unexpected-close", at)
                self.pair_close = at + 1 if pair else -1
                pos = at + 1
                continue
            head = _KEY.match(text, at)
            if head is None:
                self.signal("tdl-unexpected-text", at)
                pos = self.resync(at)
                continue
            self.signal("tdl-many-roots", at)
            brace = _skip(_INLINE, text, head.end())
            if text[brace : brace + 1] == "{":
                _, pos = self.block(at, head.group(), brace, 1)  # read it: no second report
            else:
                pos = self.resync(at)

    def close_without_block(self, at: int) -> NoReturn:
        if self.text.startswith("}}", at):
            self.fail("tdl-double-close", at)
        self.fail("tdl-unexpected-close", at)

    def trivia(self, pos: int) -> int:
        """Skips whitespace, line ends and comments."""
        text = self.text
        while True:
            pos = _skip(_TRIVIA, text, pos)
            if text[pos : pos + 1] != "#":
                return pos
            line_end = text.find("\n", pos)
            pos = self.n if line_end < 0 else line_end

    # blocks and entries

    def block(self, start: int, type_: str, brace: int, level: int) -> tuple[Block, int]:
        if level > self.limits.max_depth:
            self.too_deep(brace)
        entries, end = self.entries(brace + 1, brace, level)
        return Block(type_, entries, start=start, end=end, source=self.source), end

    def entries(self, pos: int, opening: int, level: int) -> tuple[tuple[Entry, ...], int]:
        """Reads entries up to the closing `}`; `level` is the level of this body."""
        text = self.text
        out: list[Entry] = []
        first_seen: dict[str, int] = {}
        while True:
            pos = _skip(_SKIP, text, pos)
            if pos >= self.n:
                self.signal("tdl-unclosed-block", opening)
                return tuple(out), self.n
            if text[pos] == "}":
                if text.startswith("}}", pos):
                    self.signal("tdl-double-close", pos)
                    self.pair_close = pos + 1  # the pair closes this block and the next one
                return tuple(out), pos + 1
            start = pos
            try:
                pos = self.entry(pos, level, out, first_seen)
            except TDLSyntaxError as error:
                if self.errors is None:
                    raise
                self.absorb(error)  # a bad entry is skipped to the end of its line
                pos = max(self.resync(self.last_at), start + 1)

    def entry(self, pos: int, level: int, out: list[Entry], first_seen: dict[str, int]) -> int:
        """Reads one entry at `pos`, adds it to `out` and returns where it ends."""
        text = self.text
        if text[pos] == "#":
            comment = self.comment(pos)
            out.append(comment)
            return comment.end
        key = _KEY.match(text, pos)
        if key is None:
            self.fail("tdl-unexpected-text", pos)
        word = key.group()
        if word == "If":
            node, end = self.if_(pos, key.end(), level)
            out.append(node)
            return end
        if word == "For":
            loop, end = self.for_(pos, key.end(), level)
            out.append(loop)
            return end
        if word == "Else":
            self.fail(
                "tdl-unexpected-text",
                pos,
                message="This Else has no If before it.",
                hint="Write Else directly after the closing } of an If",
            )
        after = _skip(_INLINE, text, key.end())
        char = text[after : after + 1]
        if char == ":":
            if word in first_seen:
                self.fail(
                    "tdl-duplicate-key",
                    pos,
                    first_seen[word],
                    message=f"The key {word} is already used on line "
                    f"{self.source.line_column(first_seen[word])[0]}.",
                )
            first_seen[word] = pos
            value, end = self.value(after + 1, level, ",}")
            out.append(Property(word, value, start=pos, end=value.end, source=self.source))
            return end
        if char == "{":
            if word in _RESERVED:
                self.fail("tdl-reserved-name", pos)
            block, end = self.block(pos, word, after, level + 1)
            out.append(block)
            return end
        self.fail(
            "tdl-unexpected-text",
            after,
            message="A key needs a colon and a value, or a { to open a block.",
        )

    def comment(self, at: int) -> Comment:
        text = self.text
        line_end = text.find("\n", at)
        end = self.n if line_end < 0 else line_end
        if end > at and text[end - 1] == "\r" and end < self.n:
            end -= 1
        return Comment(text[at + 1 : end].strip(), start=at, end=end, source=self.source)

    def if_(self, start: int, after: int, level: int) -> tuple[If, int]:
        text = self.text
        at = _skip(_INLINE, text, after)
        if not text.startswith("{{", at):
            self.fail(
                "tdl-unexpected-text",
                at,
                message="An If needs a condition in {{ }}.",
                hint="Write If {{ condition }} { }",
            )
        condition, at = self.slot(at)
        brace = _skip(_INLINE, text, at)
        if text[brace : brace + 1] != "{":
            self.fail(
                "tdl-unexpected-text",
                brace,
                message="An If needs a { after its condition.",
                hint="Write If {{ condition }} { }",
            )
        if level + 1 > self.limits.max_depth:
            self.too_deep(brace)
        body, end = self.entries(brace + 1, brace, level + 1)
        else_body: tuple[Entry, ...] | None = None
        # Else follows the closing brace, on the same line or after newlines and comments.
        look = self.trivia(end)
        else_match = _ELSE.match(text, look)
        if else_match is not None:
            else_brace = _skip(_INLINE, text, else_match.end())
            if text[else_brace : else_brace + 1] != "{":
                self.fail(
                    "tdl-unexpected-text",
                    else_brace,
                    message="An Else needs a { after it.",
                    hint="There is no Else If: write Else { If {{ condition }} { } }",
                )
            if level + 1 > self.limits.max_depth:
                self.too_deep(else_brace)
            else_body, end = self.entries(else_brace + 1, else_brace, level + 1)
        return If(condition, body, else_body, start=start, end=end, source=self.source), end

    def for_(self, start: int, after: int, level: int) -> tuple[For, int]:
        text = self.text
        hint = "Write For item In {{ items }} Key {{ key }} { }"
        at = _skip(_INLINE, text, after)
        variable = _KEY.match(text, at)
        if variable is None:
            self.fail("tdl-unexpected-text", at, message="A For needs a variable name.", hint=hint)
        if variable.group() in _RESERVED:
            self.fail("tdl-reserved-name", at)
        at = _skip(_INLINE, text, variable.end())
        if _IN.match(text, at) is None:
            self.fail("tdl-unexpected-text", at, message="This For is missing In.", hint=hint)
        at = _skip(_INLINE, text, at + 2)
        if not text.startswith("{{", at):
            self.fail("tdl-unexpected-text", at, message="In needs a list in {{ }}.", hint=hint)
        items, at = self.slot(at)
        at = _skip(_INLINE, text, at)
        if _KEYWORD.match(text, at) is None:
            self.fail("tdl-unexpected-text", at, message="This For is missing Key.", hint=hint)
        at = _skip(_INLINE, text, at + 3)
        if not text.startswith("{{", at):
            self.fail("tdl-unexpected-text", at, message="Key needs a value in {{ }}.", hint=hint)
        key, at = self.slot(at)
        brace = _skip(_INLINE, text, at)
        if text[brace : brace + 1] != "{":
            self.fail("tdl-unexpected-text", brace, message="A For needs a { after Key.", hint=hint)
        if level + 1 > self.limits.max_depth:
            self.too_deep(brace)
        body, end = self.entries(brace + 1, brace, level + 1)
        node = For(variable.group(), items, key, body, start=start, end=end, source=self.source)
        return node, end

    # values

    def missing_value(self, at: int) -> NoReturn:
        self.fail(
            "tdl-unexpected-text",
            at,
            message="This property has no value.",
            hint="Write Key: value",
        )

    def hash_in_value_position(self, at: int) -> None:
        """A `#` where a value should start: a comment (no value) or a colour without quotes."""
        if self.text[at + 1 : at + 2] in _SPACE_AFTER_HASH:
            self.missing_value(at)
        self.fail("tdl-bare-hash", at)

    def value(self, pos: int, level: int, stops: str) -> tuple[Value, int]:
        """Reads one value; `stops` are the characters that end it besides a line end."""
        text = self.text
        at = _skip(_INLINE, text, pos)
        char = text[at : at + 1]
        if char == "" or char == "\n" or char in stops:
            self.missing_value(at)
        if char == "#":
            self.hash_in_value_position(at)
        if char == '"' or char == "'":
            string, end = self.string(at)
            self.check_value_end(end, stops)
            return string, end
        if char == "[":
            return self.list_(at, level + 1)
        return self.run(at, level, stops)

    def check_value_end(self, end: int, stops: str) -> None:
        """After a string or a call: only whitespace and a comment may follow on the line."""
        text = self.text
        at = _skip(_INLINE, text, end)
        char = text[at : at + 1]
        if char == "" or char == "\n" or (char != "" and char in stops):
            return
        if char == "#" and at > end:
            return
        self.fail(
            "tdl-unexpected-text",
            at,
            message="Only a comment may follow this value on its line.",
            hint="Remove the extra text or move it to a new line",
        )

    def run(self, at: int, level: int, stops: str) -> tuple[Value, int]:
        """An unquoted value: a word, number, percentage, call, slot or template."""
        text = self.text
        call = _CALL.match(text, at)
        if call is not None:
            node, end = self.call(call, level + 1)
            self.check_value_end(end, stops)
            return node, end
        pattern = _RUN_END["]" in stops]
        parts: list[str | Slot] = []
        seg = at  # where the current stretch of text starts
        while True:
            hit = pattern.search(text, seg)
            stop = self.n if hit is None else hit.start()
            if hit is not None and text[stop] == "{":
                if not text.startswith("{{", stop):
                    self.fail(
                        "tdl-unexpected-text",
                        stop,
                        message="A { cannot be part of an unquoted value.",
                        hint="Quote the text, or write a block",
                    )
                if stop > seg:
                    parts.append(text[seg:stop])
                slot, seg = self.slot(stop)
                parts.append(slot)
                continue
            break
        tail = text[seg:stop].rstrip(" \t\r")
        end = seg + len(tail)
        if tail:
            parts.append(tail)
        source = self.source
        if len(parts) == 1 and isinstance(parts[0], Slot):
            return parts[0], end
        if any(isinstance(part, Slot) for part in parts):
            return Template(tuple(parts), start=at, end=end, source=source), end
        return self.scalar(at, end), end

    def scalar(self, start: int, end: int) -> Number | Percent | Word:
        """A word, or the number or percentage its text spells."""
        text = self.text[start:end]
        source = self.source
        if _NUMBER.fullmatch(text):
            value = float(text) if "." in text else int(text)
            return Number(value, text, start=start, end=end, source=source)
        if _PERCENT.fullmatch(text):
            return Percent(int(text[:-1]), text, start=start, end=end, source=source)
        return Word(text, start=start, end=end, source=source)

    def call(self, head: re.Match[str], level: int) -> tuple[Call, int]:
        """`name(` then values separated by spaces, on one line, up to `)`."""
        if level > self.limits.max_depth:
            self.too_deep(head.start())
        text = self.text
        args: list[Value] = []
        pos = head.end()
        while True:
            pos = _skip(_INLINE, text, pos)
            char = text[pos : pos + 1]
            if char == ")":
                end = pos + 1
                break
            if char == "" or char == "\n":
                self.fail(
                    "tdl-unexpected-text",
                    pos,
                    message="This ( is never closed.",
                    hint="Close it with ) on the same line",
                )
            arg, pos = self.argument(pos, level)
            args.append(arg)
        node = Call(head.group(1), tuple(args), start=head.start(), end=end, source=self.source)
        return node, end

    def argument(self, at: int, level: int) -> tuple[Value, int]:
        text = self.text
        char = text[at]
        if char == '"' or char == "'":
            return self.string(at)
        if char == "[":
            return self.list_(at, level + 1)
        if text.startswith("{{", at):
            slot, end = self.slot(at)
            return slot, end
        if char == "#":
            if text[at + 1 : at + 2] not in _SPACE_AFTER_HASH:
                self.fail("tdl-bare-hash", at)
            self.fail(
                "tdl-unexpected-text",
                at,
                message="A comment cannot start inside a call.",
                hint="Close the call with ) before the comment",
            )
        if char == ",":
            self.fail("tdl-unexpected-text", at)
        call = _CALL.match(text, at)
        if call is not None:
            return self.call(call, level + 1)
        token = _TOKEN.match(text, at)
        assert token is not None  # `char` is not whitespace, `,` or `)`
        brace = token.group().find("{")
        if brace >= 0:
            self.fail(
                "tdl-unexpected-text",
                at + brace,
                message="A { cannot be part of an unquoted value.",
                hint="Quote the text, or write a block",
            )
        return self.scalar(at, token.end()), token.end()

    def list_(self, start: int, level: int) -> tuple[List, int]:
        if level > self.limits.max_depth:
            self.too_deep(start)
        text = self.text
        items: list[Value] = []
        pos = start + 1
        while True:
            pos = _skip(_SKIP, text, pos)
            char = text[pos : pos + 1]
            if char == "" or char == "}":
                self.fail(
                    "tdl-unexpected-text",
                    pos,
                    message="This [ is never closed.",
                    hint="Close the list with ]",
                )
            if char == "]":
                end = pos + 1
                break
            if char == "#" and text[pos + 1 : pos + 2] in _SPACE_AFTER_HASH:
                pos = self.comment(pos).end
                continue
            item, pos = self.value(pos, level, ",]}")
            items.append(item)
        return List(tuple(items), start=start, end=end, source=self.source), end

    def string(self, start: int) -> tuple[String, int]:
        text = self.text
        quote = text[start]
        pattern = _QUOTE_SCAN[quote]
        chunks: list[str] = []
        pos = start + 1
        while True:
            hit = pattern.search(text, pos)
            if hit is None or hit.group() == "\n":
                self.fail("tdl-unclosed-string", start)
            stop = hit.start()
            chunks.append(text[pos:stop])
            if hit.group() == quote:
                end = stop + 1
                break
            escape = text[stop + 1 : stop + 2]
            if escape in _ESCAPES and escape != "":
                chunks.append(_ESCAPES[escape])
                pos = stop + 2
            elif escape == "u" and _HEX4.match(text, stop + 2) is not None:
                chunks.append(chr(int(text[stop + 2 : stop + 6], 16)))
                pos = stop + 6
            else:
                self.fail("tdl-bad-escape", stop)
        node = String("".join(chunks), text[start:end], start=start, end=end, source=self.source)
        return node, end

    def slot(self, start: int) -> tuple[Slot, int]:
        """`{{ text }}` ends at the first `}}` that is not inside a quoted string."""
        text = self.text
        pos = start + 2
        while True:
            hit = _SLOT_SCAN.search(text, pos)
            if hit is None or hit.group() == "\n":
                self.fail("tdl-unclosed-slot", start)
            if hit.group() == "}}":
                close = hit.start()
                break
            quote = hit.group()
            pos = hit.end()
            while True:
                inner = _QUOTE_SCAN[quote].search(text, pos)
                if inner is None or inner.group() == "\n":
                    self.fail("tdl-unclosed-slot", start)
                pos = inner.end()
                if inner.group() == "\\":
                    if text[pos : pos + 1] == "\n":
                        self.fail("tdl-unclosed-slot", start)
                    pos += 1  # the escaped character
                    continue
                break
        inner_text = text[start + 2 : close]
        if not inner_text.strip():
            self.fail("tdl-empty-slot", start)
        end = close + 2
        node = Slot(inner_text, start=start, end=end, text_start=start + 2, source=self.source)
        return node, end


def loads(text: str, *, path: str | None = None, limits: Limits | None = None) -> Document:
    """Reads TDL text into a `Document`; raises `TDLSyntaxError` on the first mistake."""
    return _Reader(text, path, limits or Limits()).document()


def parse(text: str, *, path: str | None = None, limits: Limits | None = None) -> ParseResult:
    """Reads as much as it can: the best tree and every error found, in source order.

    Never raises for a syntax error. `document` is `None` when the metadata or the root block
    cannot be read, when a limit stops the file, or when the error cap is reached.
    """
    reader = _Reader(text, path, limits or Limits())
    document = reader.parse_all()
    return ParseResult(document, tuple(reader.errors or ()))
