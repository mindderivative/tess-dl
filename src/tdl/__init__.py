"""TDL, the Tesserae Data Language: reads a TDL file into a tree that keeps everything in it.

import tdl

doc = tdl.loads(text, path="Main_Shell.tdl")   # raises TDLSyntaxError on the first mistake
doc.root.type                                   # the root block's head word
"""

from ._parser import LANGUAGE_VERSION, loads
from .errors import TDLError, TDLSyntaxError
from .limits import Limits
from .origin import Origin
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
    Percent,
    Property,
    Slot,
    String,
    Template,
    Value,
    Word,
)

__version__ = "0.1.0.dev0"

__all__ = [
    "LANGUAGE_VERSION",
    "Block",
    "Call",
    "Comment",
    "Document",
    "Entry",
    "For",
    "If",
    "Limits",
    "List",
    "Metadata",
    "Number",
    "Origin",
    "Percent",
    "Property",
    "Slot",
    "String",
    "TDLError",
    "TDLSyntaxError",
    "Template",
    "Value",
    "Word",
    "__version__",
    "loads",
]
