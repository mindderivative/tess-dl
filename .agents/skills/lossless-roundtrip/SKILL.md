---
name: lossless-roundtrip
description: 'Use when writing or reviewing the TDL lexer, parser, tree, dumps or any edit call (with_metadata, without_metadata, with_property, replace), or when a round-trip, span, position or edit test fails: the byte-exact and "only the edit changes" guarantees and how to test them.'
---

# Lossless round trip

The library's promise: `tdl.dumps(tdl.loads(text)) == text` for any file it accepts, and an edit changes **only** the bytes the edit names (the shell writes `UID` through `with_metadata` and relies on this: Risk Register R-06). Everything below protects those two lines.

## Design rules

- **Spans are the truth.** Every node keeps the source span it came from (`origin`: 1-based `line` and `column` in characters, plus a byte `offset`, and end positions). `dumps` of an unedited document returns `Document.text`; it does not re-render the tree.
- **Trivia is kept, not modelled** (grammar question 12): comments are entries in their block in source order; blank lines, indentation, line endings (`\n` or `\r\n`, per line), a leading BOM, tabs and a missing final newline live in the source spans.
- **An edit splices text, then reparses** to check the result is valid, and returns a new immutable `Document`. If the edit would break the file it raises `TDLError` and returns nothing; the original is untouched.
- `with_metadata("UID", x)` puts `UID` directly after the last version field (D10); any other new key goes at the end of the block; an existing key's value is replaced in place. The new line copies the indentation and line ending of its neighbour.
- Positions count characters but spans index bytes or code points consistently; convert in one place, and test a non-ASCII input (`"é"`, an emoji) so a column never drifts.
- Constructed nodes (the Python builder) have no span; `dumps` formats them with the standard layout (two-space indent). A parsed node never takes that path.
- Nodes are immutable and the functions pure: safe on any thread, no global state.

## Tests that catch the real bugs

1. **Every `ok` corpus case round-trips** (`conformance-corpus`).
2. **Property: round trip on generated files.** Generate valid documents (Hypothesis; see `property-based-testing`, "round trip" and "idempotence"), with random comments, blank lines, indentation, `\r\n`, a BOM and no final newline, and assert `dumps(loads(t)) == t`. Also assert `loads(dumps(d)) == d` for an edited document.
3. **Property: an edit changes only the edit.** For a random valid file and a random metadata key and value, compare `dumps(edited)` with the original using a diff: exactly the expected line differs. Also edit twice with the same value: the second edit changes nothing.
4. **Property: spans.** For every node, `text[span]` re-parses to an equal node; children's spans nest inside their parent's and do not overlap.
5. **Property: no crash.** `parse` on arbitrary text (and on valid files with a random byte or line deleted) never raises anything but returns a `ParseResult`; `loads` raises only `TDLError`. The error list is in source order and capped at 50.
6. **Recovery.** A file with six deliberate mistakes returns six errors with the right positions (resync points: a newline, `}`, the end of a block).

## Review checklist

- Does any code path build the output from the tree for a parsed document? It should not.
- Is every character of the input covered by a span or by trivia between spans? A gap is a byte `dumps` can lose.
- `}}` versus `} }`, `{{ '}}' }}`, a `#` inside a string or a slot, and `\r\n` inside an edit: each has a case.
- A property test that cannot fail is not a test: shrink a known bug in (drop a space in `dumps`) and see the property catch it, then restore.
