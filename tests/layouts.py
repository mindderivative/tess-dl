"""Generators shared by the property tests: valid TDL files with random layout."""

from pathlib import Path

from hypothesis import strategies as st

CORPUS = Path(__file__).parent / "corpus"
OK_TEXTS = [
    p.read_bytes().decode("utf-8")
    for p in sorted(CORPUS.rglob("*.tdl"))
    if p.parent.name not in {"errors", "edits"} and not p.name.endswith(".result.tdl")
]

# Characters that steer the reader: braces, quotes, hashes, slots, newlines and names.
SOUP = st.text(alphabet="{}[]()\"'#:,\\ \t\r\nabAB09-%.=\u00e9", max_size=200)

HEAD = "---\nTDL: 0.1\nName: T\n---\n"
ENTRIES = [
    "Width: 32",
    "Text: Hello world",
    "Color: rgba(0 0 0 0.5)",
    'Mark: "a \\u00e9 b"',
    "Items: [1, 2, 3]",
    "Text: Battery {{ battery.percent }}%",
    "Spacer { }",
    "Panel { Name: p1, Width: 200 }",
    "If {{ c }} { Label { } }",
    "For x In {{ xs }} Key {{ x }} { Label { } }",
    "# a comment",
    "",
    "Name: caf\u00e9_\U0001f600",
]
SPACE = st.text(alphabet=" \t", max_size=3)
EOL = st.sampled_from(["\n", "\r\n"])


@st.composite
def files(draw):
    """A valid file with random layout: comments, blanks, indentation, line endings, BOM."""
    lines = draw(st.lists(st.sampled_from(ENTRIES), max_size=12))
    # a property key may appear once: keep the first of each, drop repeats
    seen, kept = set(), []
    for line in lines:
        key = line.split(":", 1)[0] if ":" in line and "{" not in line.split(":", 1)[0] else None
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        kept.append(line)
    out = [draw(SPACE) + "Shell {"]
    for line in kept:
        out.append(
            draw(SPACE) + line + (draw(SPACE) + "  # note" if line and draw(st.booleans()) else "")
        )
    out.append("}")
    body = "".join(line + draw(EOL) for line in out)
    if draw(st.booleans()):
        body = body.rstrip("\r\n")  # no final newline
    head = HEAD.replace("\n", draw(EOL))
    return ("\ufeff" if draw(st.booleans()) else "") + head + body
