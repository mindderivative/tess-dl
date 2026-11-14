#!/usr/bin/env python3
"""Migrate TDL 0.1 files to 0.2: the slot delimiters `{{ }}` become `<| |>`.

Run it with the release that still reads `{{ }}`, so the old reader finds the slots:

    uv run --no-project --with tesserae-dl==0.1.1 python tools/migrate_slots.py FILE_OR_DIR...
    uv run --no-project --with tesserae-dl==0.1.1 python tools/migrate_slots.py --check DIR

Each `.tdl` file is read with that release. The two delimiters of every slot are rewritten and a
`TDL: 0.1` becomes `TDL: 0.2`; no other byte changes (comments, layout, line endings, a byte-order
mark, and text in quoted strings that merely looks like a slot all stay). A file already in 0.2
is left alone. `--check` changes nothing and exits 1 if any file would change.

A slot whose text holds `|>` outside a quote cannot be migrated by rewriting the delimiters, because
the new slot would end there: the file is reported and left as it is.

Exit status: 0 all done (or nothing to do), 1 `--check` found work, 2 a file could not be migrated.
"""

import argparse
import sys
from pathlib import Path

import tess_dl

OLD_OPEN, OLD_CLOSE = "{{", "}}"
NEW_OPEN, NEW_CLOSE = "<|", "|>"


def holds_new_close(text: str) -> bool:
    """Whether `|>` stands in `text` outside a quoted string (the scan the new reader makes)."""
    quote = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif text.startswith(NEW_CLOSE, i):
            return True
        i += 1
    return False


def slots_of(node: object) -> list[tess_dl.Slot]:
    """Every slot below `node`, found through the tree of the old reader."""
    found: list[tess_dl.Slot] = []
    if isinstance(node, tess_dl.Slot):
        found.append(node)
    elif isinstance(node, tess_dl.Template):
        for part in node.parts:
            found += slots_of(part)
    elif isinstance(node, tess_dl.Call):
        for arg in node.args:
            found += slots_of(arg)
    elif isinstance(node, tess_dl.List):
        for item in node.items:
            found += slots_of(item)
    elif isinstance(node, tess_dl.Property):
        found += slots_of(node.value)
    elif isinstance(node, tess_dl.Block):
        for entry in node.entries:
            found += slots_of(entry)
    elif isinstance(node, tess_dl.If):
        found += slots_of(node.condition)
        for entry in node.body + (node.else_body or ()):
            found += slots_of(entry)
    elif isinstance(node, tess_dl.For):
        found += slots_of(node.items) + slots_of(node.key)
        for entry in node.body:
            found += slots_of(entry)
    return found


def migrate(text: str) -> str:
    """The text of a 0.1 file as 0.2. Raises `ValueError` if it cannot be done by rewriting."""
    doc = tess_dl.loads(text)
    edits: list[tuple[int, int, str]] = []  # start, end, replacement
    for slot in slots_of(doc.root):
        if (
            text[slot.start : slot.start + 2] != OLD_OPEN
            or text[slot.end - 2 : slot.end] != OLD_CLOSE
        ):
            raise ValueError(f"offset {slot.start}: not a {OLD_OPEN} {OLD_CLOSE} slot as expected")
        if holds_new_close(slot.text):
            origin = slot.origin
            where = f"{origin.line}:{origin.column}" if origin else str(slot.start)
            raise ValueError(f"{where}: the slot text holds {NEW_CLOSE} outside a quote")
        edits.append((slot.start, slot.start + 2, NEW_OPEN))
        edits.append((slot.end - 2, slot.end, NEW_CLOSE))
    version = doc.metadata.get("TDL")
    if version is not None and version.start >= 0:
        if isinstance(version, tess_dl.Word) and version.text == "0.1":
            edits.append((version.start, version.end, "0.2"))
        elif isinstance(version, tess_dl.String) and version.value == "0.1":
            edits.append((version.start + 1, version.end - 1, "0.2"))
    for start, end, new in sorted(edits, reverse=True):
        text = text[:start] + new + text[end:]
    return text


def tdl_files(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        found += sorted(path.rglob("*.tdl")) if path.is_dir() else [path]
    return found


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("paths", nargs="+", help=".tdl files, or folders searched for them")
    parser.add_argument(
        "--check", action="store_true", help="change nothing; exit 1 if work is due"
    )
    args = parser.parse_args(argv)
    if not tess_dl.__version__.startswith("0.1."):
        print(
            f"This tool reads the old syntax: run it with tesserae-dl==0.1.1 "
            f"(found tess_dl {tess_dl.__version__}).",
            file=sys.stderr,
        )
        return 2
    changed = failed = 0
    for path in tdl_files(args.paths):
        data = path.read_bytes()
        try:
            old = data.decode("utf-8")
            new = migrate(old)
        except (UnicodeDecodeError, ValueError, tess_dl.TDLError) as error:
            print(f"{path}: not migrated: {error}", file=sys.stderr)
            failed += 1
            continue
        if new != old:
            changed += 1
            print(f"{path}: {'would change' if args.check else 'migrated'}")
            if not args.check:
                path.write_bytes(new.encode("utf-8"))
    print(f"{changed} file(s) {'to change' if args.check else 'migrated'}, {failed} not migrated")
    if failed:
        return 2
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
