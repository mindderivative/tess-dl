"""The errors TDL reports: one stable `code`, a plain message, a hint and where."""

from .origin import Origin

# code -> (message, hint). The wording follows docs/language.md ("Errors").
_WORDS: dict[str, tuple[str, str]] = {
    "tdl-no-metadata": (
        "The file does not start with a metadata block.",
        "Start the file with ---",
    ),
    "tdl-metadata-unclosed": ("The metadata block is never closed.", "Close the block with ---"),
    "tdl-no-version": ("The metadata has no TDL version.", "Add TDL: <version>"),
    "tdl-no-name": ("The metadata has no Name.", "Add Name: <identifier>"),
    "tdl-bad-name": (
        "This Name is not a valid identifier.",
        "Use letters, digits and _, starting with a letter",
    ),
    "tdl-no-root": ("The file has no root block.", "Add one root block, for example Shell { }"),
    "tdl-many-roots": ("The file has more than one root block.", "Keep one root block"),
    "tdl-unclosed-block": ("This block is never closed.", "Add the missing }"),
    "tdl-unexpected-close": ("This } closes nothing.", "Remove the extra }"),
    "tdl-unclosed-slot": ("This <| has no |> on its line.", "Close the slot on the same line"),
    "tdl-empty-slot": ("This slot is empty.", "Put an expression between <| and |>"),
    "tdl-unclosed-string": (
        "This string is not closed on its line.",
        "Close the string with the same quote",
    ),
    "tdl-bad-escape": (
        "This backslash does not start a valid escape.",
        "Use \\\\, \\\", \\', \\n, \\t or \\u and four hex digits",
    ),
    "tdl-duplicate-key": ("This key is already used in this block.", "Remove one of them"),
    "tdl-duplicate-variable": ("This name is already a loop variable.", "Use a different name"),
    "tdl-bare-hash": ("This colour needs quotes.", 'Quote the colour: "#ffffff"'),
    "tdl-unexpected-text": ("This text is not valid here.", "Write Key: value"),
    "tdl-reserved-name": ("This name is reserved.", "Choose another name"),
    "tdl-too-large": ("The file is larger than the limit.", "Split the file"),
    "tdl-too-deep": ("Blocks are nested deeper than the limit.", "Flatten the nesting"),
    "tdl-unsupported-version": (
        "This file needs a newer TDL than this library reads.",
        "Use a newer tesserae-dl",
    ),
    "tdl-bad-encoding": ("The bytes are not valid UTF-8.", "Save the file as UTF-8"),
}

CODES: frozenset[str] = frozenset(_WORDS)


class TDLError(Exception):
    """Base class: `code`, `message`, `hint`, `origin` and `related` origins."""

    def __init__(
        self, code: str, message: str, hint: str, origin: Origin, related: tuple[Origin, ...] = ()
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.origin = origin
        self.related = related

    def __str__(self) -> str:
        return f"{self.origin}: {self.message} ({self.hint})"


class TDLSyntaxError(TDLError):
    """The text is not valid TDL."""


def syntax_error(
    code: str,
    origin: Origin,
    related: tuple[Origin, ...] = (),
    *,
    message: str | None = None,
    hint: str | None = None,
) -> TDLSyntaxError:
    """Builds the error for `code`; `message` and `hint` replace the stock wording."""
    stock_message, stock_hint = _WORDS[code]
    return TDLSyntaxError(code, message or stock_message, hint or stock_hint, origin, related)


def too_large(path: str | None, limit: int) -> TDLSyntaxError:
    """The error for text over `limit` bytes; it points at the start of the file."""
    origin = Origin(path, 1, 1, 1, 1, 0)
    return syntax_error("tdl-too-large", origin, message=f"The file is larger than {limit} bytes.")
