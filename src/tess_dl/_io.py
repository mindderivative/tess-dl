"""`dumps`, `dump` and `load` (private module; the names are public through `tess_dl`)."""

from typing import BinaryIO

from ._decode import decode
from ._parser import loads
from .errors import too_large
from .limits import Limits
from .tree import Document


def dumps(document: Document) -> str:
    """The text of a document. For a document read from text it is that text, byte for byte."""
    return document.text


def dump(document: Document, fp: BinaryIO) -> None:
    """Writes the text of a document to a binary file object as UTF-8, byte-order mark kept."""
    fp.write(document.text.encode("utf-8"))


def load(fp: BinaryIO, *, path: str | None = None, limits: Limits | None = None) -> Document:
    """Reads a document from a binary file object the caller opened (UTF-8, BOM accepted).

    The library never opens a path itself. At most `limits.max_bytes` plus one byte is read, so
    a huge file is refused without being read whole. Raises `TDLSyntaxError`, including
    `tdl-bad-encoding` for bytes that are not valid UTF-8.
    """
    limits = limits or Limits()
    wanted = limits.max_bytes + 1
    chunks: list[bytes] = []
    size = 0
    while size < wanted:
        chunk = fp.read(wanted - size)
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
    if size > limits.max_bytes:
        raise too_large(path, limits.max_bytes)
    return loads(decode(b"".join(chunks), path), path=path, limits=limits)
