"""What the reader will not read."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Limits:
    """`max_bytes` of text, `max_errors` reported by `parse`, `max_depth` of nesting.

    The root block is level 1; blocks, `If` and `For` bodies, lists and calls each add one.
    """

    max_bytes: int = 1_048_576
    max_errors: int = 50
    max_depth: int = 64
