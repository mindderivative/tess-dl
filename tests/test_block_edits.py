"""Block edits (T-011): without_property, with_child, without_child, move_child, index paths."""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

import tess_dl
from layouts import HEAD, files
from test_edits import changed_span

NAMED = HEAD.replace("Name: T", "Name: R")


def run(body, call, path="R"):
    """Apply `call` to the block at `path` of a file with `body`; the file's text after the head."""
    doc = tess_dl.loads(NAMED + body)
    result = call(doc.find(path))
    if isinstance(result, tuple):
        result = result[0]
    return tess_dl.dumps(result)[len(NAMED) :]


def all_blocks(node):
    """Every block below `node`, `node` first, through `If` and `For` bodies too."""
    found = [node] if isinstance(node, tess_dl.Block) else []
    kids = (
        node.entries
        if isinstance(node, tess_dl.Block)
        else node.body + (getattr(node, "else_body", None) or ())
    )
    for kid in kids:
        if isinstance(kid, tess_dl.Block | tess_dl.If | tess_dl.For):
            found += all_blocks(kid)
    return found


def all_nodes(node):
    """Every block, `If` and `For` below `node`, `node` first."""
    found = [node]
    kids = (
        node.entries
        if isinstance(node, tess_dl.Block)
        else node.body + (getattr(node, "else_body", None) or ())
    )
    for kid in kids:
        if isinstance(kid, tess_dl.Block | tess_dl.If | tess_dl.For):
            found += all_nodes(kid)
    return found


# with_child


@pytest.mark.parametrize(
    ("before", "index", "after"),
    [
        ("Shell { }\n", None, "Shell { A { } }\n"),
        ("Shell { A: 1, }\n", None, "Shell { A: 1, A { }, }\n"),
        ("Shell { X: 1 }\n", 0, "Shell { A { }, X: 1 }\n"),
        ("Shell { X: 1, Y: 2 }\n", 1, "Shell { X: 1, A { }, Y: 2 }\n"),
        ("Shell { # c\n}\n", None, "Shell { # c\n  A { }\n}\n"),
        ("Shell {\n  X: 1\n}\n", 0, "Shell {\n  A { }\n  X: 1\n}\n"),
        ("Shell {\n\tX: 1\n}\n", None, "Shell {\n\tX: 1\n\tA { }\n}\n"),
        ("Shell {\n  X: 1\n  # last\n}\n", None, "Shell {\n  X: 1\n  # last\n  A { }\n}\n"),
        ("Shell {\n  X: 1 # t\n  Y: 2\n}\n", 1, "Shell {\n  X: 1 # t\n  A { }\n  Y: 2\n}\n"),
    ],
)
def test_with_child_goes_where_the_neighbours_are(before, index, after):
    assert run(before, lambda b: b.with_child("A { }", index)) == after


def test_a_block_on_several_lines_goes_into_a_one_line_block_with_its_lines_indented():
    out = run("Shell { X: 1 }\n", lambda b: b.with_child("A {\n  Y: 2\n}"))
    assert out == "Shell { X: 1, A {\n    Y: 2\n  } }\n"
    assert tess_dl.loads(NAMED + out).root.entries[1].canonical()["entries"][0]["property"] == "Y"


def test_the_new_lines_take_the_line_ending_of_their_neighbours():
    crlf = (NAMED + "Shell {\n  X: 1\n  Y: 2\n}\n").replace("\n", "\r\n")
    doc = tess_dl.loads(crlf)
    for index in (0, 1, None):
        out = tess_dl.dumps(doc.root.with_child("A {\n  Z: 1\n}", index)[0])
        assert "\n" not in out.replace("\r\n", "")
        assert out.count("\r\n") == crlf.count("\r\n") + 3


def test_with_child_returns_the_new_block_and_a_path_that_finds_it_in_the_new_document():
    doc = tess_dl.loads(NAMED + "Shell {\n  X: 1\n  Y { }\n}\n")
    new_doc, child = doc.root.with_child("A { Name: a }", 1)
    assert child.type == "A" and child.name == "a" and child.index_path == (1,)
    assert new_doc.at(child.index_path) is child
    assert new_doc.at((2,)).type == "Y"  # what was at 1 is now at 2


def test_an_index_at_the_trailing_comment_of_a_line_moves_past_the_comment():
    doc = tess_dl.loads(NAMED + "Shell {\n  X: 1   # why\n  Y: 2\n}\n")
    new_doc, child = doc.root.with_child("A { }", 1)  # entry 1 is the comment after X
    assert child.index_path == (2,)
    assert tess_dl.dumps(new_doc)[len(NAMED) :] == "Shell {\n  X: 1   # why\n  A { }\n  Y: 2\n}\n"


@pytest.mark.parametrize(
    ("text", "code", "line"),
    [
        ("Width: 1", "tdl-unexpected-text", 1),
        ("Bar {\n  Width 1\n}", "tdl-unexpected-text", 2),
        ("Bar {\n  A: 1\n  A: 2\n}", "tdl-duplicate-key", 3),
        ("A { }\nB { }", "tdl-many-roots", 2),
        ("Bar {", "tdl-unclosed-block", 1),
        ("", "tdl-no-root", 1),
        ("If {{ c }} { }", "tdl-reserved-name", 1),
    ],
)
def test_a_text_that_is_not_one_block_is_refused_with_origins_inside_the_text(text, code, line):
    doc = tess_dl.loads(NAMED + "Shell { }\n")
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        doc.root.with_child(text)
    error = raised.value
    assert (error.code, error.origin.line) == (code, line)
    assert error.origin.file == "<block_text>" and str(error).startswith("<block_text>:")
    assert tess_dl.dumps(doc) == NAMED + "Shell { }\n"


def test_the_duplicate_key_message_names_the_line_in_the_text_not_in_the_probe():
    doc = tess_dl.loads(NAMED + "Shell { }\n")
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        doc.root.with_child("Bar {\n  A: 1\n  A: 2\n}")
    error = raised.value
    assert "line 2" in error.message and error.related[0].line == 2


@pytest.mark.parametrize("index", [-1, 3, True])
def test_an_index_outside_the_entries_is_an_index_error(index):
    doc = tess_dl.loads(NAMED + "Shell {\n  X: 1\n  Y: 2\n}\n")
    with pytest.raises(IndexError):
        doc.root.with_child("A { }", index)


def test_a_block_built_in_code_cannot_be_edited():
    built = tess_dl.Block("B", ())
    for call in (
        lambda: built.with_child("A { }"),
        lambda: built.without_property("A"),
        lambda: built.without_child(0),
        lambda: built.move_child(0, 0),
    ):
        with pytest.raises(ValueError):
            call()


# without_property


@pytest.mark.parametrize(
    ("before", "key", "after"),
    [
        ("Shell { A: 1, B: 2 }\n", "A", "Shell { B: 2 }\n"),
        ("Shell { A: 1, B: 2 }\n", "B", "Shell { A: 1 }\n"),
        ("Shell { A: 1 }\n", "A", "Shell { }\n"),
        ("Shell { A: 1\n}\n", "A", "Shell {\n}\n"),
        ("Shell {\n  A: 1,\n  B: 2\n}\n", "A", "Shell {\n  B: 2\n}\n"),
        ("Shell {\n  A: 1,\n  B: 2\n}\n", "B", "Shell {\n  A: 1,\n}\n"),
        ("Shell {\n  A: 1   # one\n  B: 2\n}\n", "A", "Shell {\n  B: 2\n}\n"),
        ("Shell {\n  # about\n  A: 1\n}\n", "A", "Shell {\n  # about\n}\n"),
        ("Shell {\r\n  A: 1\r\n  B: 2\r\n}\r\n", "A", "Shell {\r\n  B: 2\r\n}\r\n"),
    ],
)
def test_without_property_takes_the_line_or_one_comma(before, key, after):
    assert run(before, lambda b: b.without_property(key)) == after


def test_without_property_of_an_absent_key_is_a_key_error():
    doc = tess_dl.loads(NAMED + "Shell { A: 1 }\n")
    with pytest.raises(KeyError):
        doc.root.without_property("B")


# without_child


@pytest.mark.parametrize(
    ("before", "index", "after"),
    [
        ("Shell { A { }, B { } }\n", 0, "Shell { B { } }\n"),
        ("Shell { A { }, B { } }\n", 1, "Shell { A { } }\n"),
        ("Shell {\n  A { }\n}\n", 0, "Shell {\n}\n"),
        ("Shell {\n  A { }\n  B { }  # b\n  C { }\n}\n", 1, "Shell {\n  A { }\n  C { }\n}\n"),
        (
            "Shell {\n  If {{ c }} {\n    A { }\n  } Else {\n    B { }\n  }\n  C { }\n}\n",
            0,
            "Shell {\n  C { }\n}\n",
        ),
        (
            "Shell {\n  For x In {{ xs }} Key {{ x }} { A { } }\n  C { }\n}\n",
            0,
            "Shell {\n  C { }\n}\n",
        ),
    ],
)
def test_without_child_takes_the_entry_with_its_lines(before, index, after):
    assert run(before, lambda b: b.without_child(index)) == after


def test_without_child_takes_a_node_of_the_block_as_well_as_an_index():
    doc = tess_dl.loads(NAMED + "Shell {\n  A { }\n  B { }\n}\n")
    out = tess_dl.dumps(doc.root.without_child(doc.root.entries[1]))
    assert out == NAMED + "Shell {\n  A { }\n}\n"


def test_without_child_refuses_what_is_not_a_child_of_this_block():
    doc = tess_dl.loads(NAMED + "Shell {\n  X: 1\n  # c\n  A { B { } }\n}\n")
    block = doc.root
    for refused in (0, 1):  # a property, a comment
        with pytest.raises(ValueError):
            block.without_child(refused)
    with pytest.raises(IndexError):
        block.without_child(9)
    with pytest.raises(ValueError):
        block.without_child(block.entries[2].entries[0])  # a grandchild
    older = tess_dl.loads(NAMED + "Shell {\n  X: 1\n  # c\n  A { B { } }\n}\n")
    with pytest.raises(ValueError):  # a node of another Document, even with the same text
        block.without_child(older.root.entries[2])


# move_child


@pytest.mark.parametrize(
    ("before", "index", "to", "after"),
    [
        ("Shell { A { }, B { }, C { } }\n", 0, 2, "Shell { B { }, C { }, A { } }\n"),
        ("Shell { A { }, B { }, C { } }\n", 2, 0, "Shell { C { }, A { }, B { } }\n"),
        ("Shell { A { }, B { }, C { } }\n", 1, 0, "Shell { B { }, A { }, C { } }\n"),
        (
            "Shell {\n  A { }\n  B { }\n  C { }\n}\n",
            0,
            2,
            "Shell {\n  B { }\n  C { }\n  A { }\n}\n",
        ),
        (
            "Shell {\n  A { }\n  # about B\n  B {\n    Y: 1\n  }\n}\n",
            2,
            0,
            "Shell {\n  B {\n    Y: 1\n  }\n  A { }\n  # about B\n}\n",
        ),
        (
            "Shell {\n  X: 1\n  A { }\n}\n",
            1,
            0,
            "Shell {\n  A { }\n  X: 1\n}\n",
        ),
        (
            "Shell {\r\n  A { }\r\n  B { }\r\n}\r\n",
            0,
            1,
            "Shell {\r\n  B { }\r\n  A { }\r\n}\r\n",
        ),
    ],
)
def test_move_child_moves_the_text_and_nothing_else(before, index, to, after):
    assert run(before, lambda b: b.move_child(index, to)) == after


def test_moving_a_child_to_where_it_is_returns_an_equal_document():
    doc = tess_dl.loads(NAMED + "Shell {\n  A { }\n  B { }\n}\n")
    same = doc.root.move_child(1, 1)
    assert same == doc and tess_dl.dumps(same) == doc.text


def test_a_move_is_refused_for_the_wrong_arguments():
    doc = tess_dl.loads(NAMED + "Shell { A { }, B {\n  X: 1\n} }\n")
    block = doc.root
    with pytest.raises(IndexError):
        block.move_child(0, 2)  # only B is left to place it among: 0 or 1
    with pytest.raises(IndexError):
        block.move_child(0, -1)
    with pytest.raises(ValueError):  # B shares a line with A and spans lines
        block.move_child(1, 0)
    with pytest.raises(ValueError):
        tess_dl.loads(NAMED + "Shell { X: 1 }\n").root.move_child(0, 0)  # a property


# index paths


BODY = (
    "Shell {\n  A { Name: a }\n  If {{ c }} {\n    X { }\n    # n\n  } Else {\n    Y { }\n  }\n"
    "  For i In {{ xs }} Key {{ i }} {\n    Z { }\n  }\n}\n"
)


def test_index_paths_count_entries_and_step_through_if_and_for():
    doc = tess_dl.loads(NAMED + BODY)
    paths = {
        node.type if isinstance(node, tess_dl.Block) else type(node).__name__: node.index_path
        for node in all_nodes(doc.root)
    }
    assert paths == {
        "Shell": (),
        "A": (0,),
        "If": (1,),
        "X": (1, 0),
        "Y": (1, 2),  # the else body counts after the body, comment included
        "For": (2,),
        "Z": (2, 0),
    }
    assert doc.at(()) is doc.root and doc.at((1, 2)).type == "Y" and doc.at((2,)).variable == "i"


@pytest.mark.parametrize(
    ("path", "error"),
    [((0, 0), ValueError), ((1, 1), ValueError), ((9,), IndexError), ((-1,), IndexError)],
)
def test_at_refuses_a_path_that_ends_at_or_goes_through_a_property_or_comment(path, error):
    doc = tess_dl.loads(NAMED + BODY)
    with pytest.raises(error):
        doc.at(path)


def test_a_path_survives_an_edit_to_the_text_around_it():
    doc = tess_dl.loads(NAMED + BODY)
    path = doc.root.entries[2].index_path
    doc2 = doc.with_metadata("UID", "x").root.with_child("W { }")[0]  # appended: nothing shifts
    assert doc2.at(path).variable == "i"
    doc3 = doc.root.with_child("W { }", 0)[0]  # inserted first: everything shifts by one
    assert isinstance(doc3.at(path), tess_dl.If)  # the For moved to 3; the If is at 2 now


@settings(max_examples=200, deadline=None)
@given(files())
def test_every_node_is_found_again_by_its_own_path(text):
    doc = tess_dl.loads(text)
    for node in all_nodes(doc.root):
        assert doc.at(node.index_path) is node


# the guarantees, over generated files and every block in them


def pick_block(doc, data):
    return data.draw(st.sampled_from(all_blocks(doc.root)))


@settings(max_examples=300, deadline=None)
@given(files(), st.data())
def test_with_child_is_a_pure_insertion_and_changes_no_other_entry(text, data):
    doc = tess_dl.loads(text)
    block = pick_block(doc, data)
    index = data.draw(st.integers(0, len(block.entries)))
    new_doc, child = block.with_child("Icon {\n  Name: Ok\n}", index)
    new = tess_dl.dumps(new_doc)
    removed, _ = changed_span(text, new)
    assert removed == "" and new.count("Icon {") == text.count("Icon {") + 1
    assert new_doc.at(child.index_path) is child
    assert child.canonical() == {
        "block": "Icon",
        "entries": [{"property": "Name", "value": {"word": "Ok"}}],
    }
    parent = new_doc.at(child.index_path[:-1])
    k = child.index_path[-1]
    assert k >= index and parent.entries[:k] + parent.entries[k + 1 :] == block.entries


@settings(max_examples=300, deadline=None)
@given(files(), st.data())
def test_without_child_is_a_pure_deletion_of_that_entry_and_its_line_comment(text, data):
    doc = tess_dl.loads(text)
    candidates = [
        (b, i)
        for b in all_blocks(doc.root)
        for i, e in enumerate(b.entries)
        if isinstance(e, tess_dl.Block | tess_dl.If | tess_dl.For)
    ]
    assume(candidates)
    block, index = data.draw(st.sampled_from(candidates))
    new_doc = block.without_child(index)
    removed, added = changed_span(text, tess_dl.dumps(new_doc))
    assert added == "" and removed.strip()
    after = new_doc.at(block.index_path)
    assert len(after.entries) in (len(block.entries) - 1, len(block.entries) - 2)
    assert tess_dl.loads(tess_dl.dumps(new_doc), path=new_doc.path) == new_doc


@settings(max_examples=300, deadline=None)
@given(files(), st.data())
def test_without_property_is_a_pure_deletion_of_that_property(text, data):
    doc = tess_dl.loads(text)
    candidates = [
        (b, e.key)
        for b in all_blocks(doc.root)
        for e in b.entries
        if isinstance(e, tess_dl.Property)
    ]
    assume(candidates)
    block, key = data.draw(st.sampled_from(candidates))
    new_doc = block.without_property(key)
    new = tess_dl.dumps(new_doc)
    _, added = changed_span(text, new)
    assert added == "" and len(new) < len(text)
    assert all(
        not (isinstance(e, tess_dl.Property) and e.key == key)
        for e in new_doc.at(block.index_path).entries
    )


@settings(max_examples=300, deadline=None)
@given(files(), st.data())
def test_move_child_only_reorders_and_changes_no_other_line(text, data):
    doc = tess_dl.loads(text)
    candidates = [
        (b, i)
        for b in all_blocks(doc.root)
        for i, e in enumerate(b.entries)
        if isinstance(e, tess_dl.Block | tess_dl.If | tess_dl.For)
    ]
    assume(candidates)
    block, index = data.draw(st.sampled_from(candidates))
    to = data.draw(st.integers(0, len(block.entries) - 1))
    try:
        new_doc = block.move_child(index, to)
    except IndexError:
        assume(False)
    except ValueError:
        return  # an entry sharing a line and spanning lines: refused, and that is the contract
    new = tess_dl.dumps(new_doc)
    old_lines = sorted(line.strip() for line in text.split("\n"))
    assert sorted(line.strip() for line in new.split("\n")) == old_lines
    entries = new_doc.at(block.index_path).entries
    assert sorted(map(repr, entries)) == sorted(map(repr, block.entries))
