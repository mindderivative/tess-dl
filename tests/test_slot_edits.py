"""T-040: For.with_items, For.with_key, If.with_condition, For.with_variable; edits in an Else."""

import re

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

import tess_dl
from layouts import HEAD, files
from test_block_edits import all_nodes

NAMED = HEAD.replace("Name: T", "Name: R")

BODY = (
    "Shell {\n  A: 1\n  If {{ c }} {   # warn\n    X { Name: x }\n  } Else {\n"
    "    Y { Name: y }\n    If {{ b }} { Z { } }\n"
    "    For i In {{ zs }} Key {{ i }} { V { } }\n  }\n"
    "  For x In {{ xs }}   Key {{ x.id }} {\n    L { T: {{ x.t }} }\n  }\n}\n"
)


def doc():
    return tess_dl.loads(NAMED + BODY)


# the signatures: what each call changes, and nothing else


@pytest.mark.parametrize(
    ("path", "call", "arg", "old", "new"),
    [
        ((1,), "with_condition", "{{ battery.low }}", "If {{ c }} {", "If {{ battery.low }} {"),
        ((2,), "with_items", "{{ items }}", "In {{ xs }}", "In {{ items }}"),
        ((2,), "with_key", "{{ x.uid }}", "Key {{ x.id }}", "Key {{ x.uid }}"),
        ((2,), "with_variable", "item", "For x In", "For item In"),
        ((1, 3), "with_condition", "{{ not b }}", "If {{ b }}", "If {{ not b }}"),
        ((1, 4), "with_items", "{{ ws }}", "In {{ zs }}", "In {{ ws }}"),
        ((1, 4), "with_variable", "k", "For i In", "For k In"),
    ],
)
def test_each_call_replaces_only_the_bytes_it_names(path, call, arg, old, new):
    before = doc()
    after = getattr(before.at(path), call)(arg)
    assert tess_dl.dumps(after) == before.text.replace(old, new, 1)
    assert before.text.count(old) == 1


def test_spacing_around_the_new_slot_is_dropped_and_the_inside_is_kept_byte_for_byte():
    out = doc().at((1,)).with_condition("  \t{{   a  and   b }}\n ")
    assert "If {{   a  and   b }} {   # warn" in tess_dl.dumps(out)


def test_a_slot_with_a_closing_pair_in_a_string_is_one_slot():
    out = doc().at((2,)).with_key("{{ '}}' }}")
    assert out.at((2,)).key.text == " '}}' "


def test_the_variable_is_renamed_in_its_declaration_only_and_references_stay():
    out = doc().at((2,)).with_variable("item")
    new = tess_dl.dumps(out)
    assert "For item In {{ xs }}   Key {{ x.id }}" in new and "{{ x.t }}" in new
    assert out.at((2,)).variable == "item"


def test_with_variable_to_the_same_name_changes_nothing():
    before = doc()
    assert before.at((2,)).with_variable("x") == before


def test_the_text_whitespace_and_crlf_of_everything_else_stay():
    text = (NAMED + BODY).replace("\n", "\r\n")
    out = tess_dl.loads(text).at((2,)).with_items("{{ q }}")
    assert tess_dl.dumps(out) == text.replace("{{ xs }}", "{{ q }}")


# every index path stays valid, and the nodes keep their places


def test_every_index_path_is_valid_after_every_call():
    before = doc()
    calls = [
        ((1,), "with_condition", "{{ a }}"),
        ((2,), "with_items", "{{ a }}"),
        ((2,), "with_key", "{{ a }}"),
        ((2,), "with_variable", "item"),
        ((1, 3), "with_condition", "{{ a }}"),
    ]
    for path, call, arg in calls:
        after = getattr(before.at(path), call)(arg)
        assert [(type(n).__name__, n.index_path) for n in all_nodes(after.root)] == [
            (type(n).__name__, n.index_path) for n in all_nodes(before.root)
        ]


# errors


@pytest.mark.parametrize(
    ("text", "code", "line", "column"),
    [
        ("{{ a", "tdl-unclosed-slot", 1, 1),
        ("  {{ }}", "tdl-empty-slot", 1, 1),
        ("{{ a\n}}", "tdl-unclosed-slot", 1, 1),
        ("", "tdl-unexpected-text", 1, 1),
        ("#x", "tdl-bare-hash", 1, 1),
        ('"abc', "tdl-unclosed-string", 1, 1),
    ],
)
def test_invalid_slot_text_is_a_syntax_error_with_origins_inside_the_text(text, code, line, column):
    node = doc().at((1,))
    with pytest.raises(tess_dl.TDLSyntaxError) as raised:
        node.with_condition(text)
    error = raised.value
    assert (error.code, error.origin.line, error.origin.column) == (code, line, column)
    assert error.origin.file == "<slot_text>" and str(error).startswith("<slot_text>:")


@pytest.mark.parametrize(
    "text",
    [
        "word",
        "12",
        "{{ a }} b",
        "b {{ a }}",
        "{{ a }}, B: 1",
        "{{ a }} # c",
        '"{{ a }}"',
        "[{{ a }}]",
    ],
)
def test_valid_tdl_that_is_not_exactly_one_slot_is_a_value_error(text):
    before = doc()
    with pytest.raises(ValueError):
        before.at((1,)).with_condition(text)
    with pytest.raises(ValueError):
        before.at((2,)).with_items(text)
    assert before == doc()


@pytest.mark.parametrize("name", ["", "1x", "a b", "a-b", "x.y", "If", "Else", "For", "In", "Key"])
def test_a_variable_that_is_not_a_key_or_is_reserved_is_a_value_error(name):
    with pytest.raises(ValueError):
        doc().at((2,)).with_variable(name)


def test_a_node_built_in_code_cannot_be_edited():
    slot = tess_dl.Slot(" a ")
    built_for = tess_dl.For("x", slot, slot, ())
    built_if = tess_dl.If(slot, (), None)
    for call in (
        lambda: built_for.with_items("{{ b }}"),
        lambda: built_for.with_key("{{ b }}"),
        lambda: built_for.with_variable("y"),
        lambda: built_if.with_condition("{{ b }}"),
    ):
        with pytest.raises(ValueError):
            call()


def test_an_error_leaves_the_document_unchanged():
    before = doc()
    for call in (
        lambda: before.at((1,)).with_condition("{{ a"),
        lambda: before.at((2,)).with_variable("If"),
    ):
        with pytest.raises((tess_dl.TDLSyntaxError, ValueError)):
            call()
    assert before == doc() and before.text == NAMED + BODY


# an Else body stays addressable: every edit works inside it


def test_an_else_body_is_addressed_by_index_path_after_the_body():
    d = doc()
    assert d.at((1,)).body[0].text == "warn"  # the comment at the end of the `If` line is entry 0
    assert d.at((1, 1)).name == "x"  # the body of the If
    assert d.at((1, 2)).name == "y" and d.at((1, 3)).condition.text == " b "  # the else body
    assert d.at((1, 4)).variable == "i"
    assert d.at((1, 2)).index_path == (1, 2)


def test_block_edits_work_on_a_block_inside_an_else():
    d = doc()
    y = d.at((1, 2))
    out = y.with_property("Width", "10")
    assert "Y { Name: y, Width: 10 }" in tess_dl.dumps(out)
    out, child = y.with_child("Icon { }")
    assert child.index_path == (1, 2, 1) and out.at(child.index_path) is child
    out = d.at((1, 3)).body[0].with_property("K", "1")  # Z, inside an If inside the Else
    assert "Z { K: 1 }" in tess_dl.dumps(out)
    out = y.without_property("Name")
    assert "Y { }" in tess_dl.dumps(out)
    out, _ = d.at((1, 4)).body[0].with_child("Q { }")  # a block inside a For inside the Else
    assert "V { Q { } }" in tess_dl.dumps(out)


def test_an_if_inside_an_else_can_be_edited_and_the_else_is_untouched_around_it():
    d = doc()
    out = d.at((1, 3)).with_condition("{{ b and c }}")
    assert tess_dl.dumps(out) == d.text.replace("If {{ b }} { Z", "If {{ b and c }} { Z")
    assert out.at((1, 2)).name == "y"


def test_a_formatted_document_keeps_every_else_edit_path():
    d = tess_dl.format(doc())
    assert d.at((1, 3)).with_condition("{{ q }}").at((1, 3)).condition.text == " q "


# the guarantees over generated files, for every If and For in them


def nodes_of(document, kind):
    return [n for n in all_nodes(document.root) if isinstance(n, kind)]


SLOTS = st.sampled_from(
    ["{{ a }}", "{{ a.b + 1 }}", "{{ '}}' }}", "  {{   spaced  }}  ", "{{ x ? y : z }}"]
)


@settings(max_examples=300, deadline=None)
@given(files(), st.data(), SLOTS)
def test_with_condition_changes_one_span_and_nothing_else(text, data, slot):
    document = tess_dl.loads(text)
    ifs = nodes_of(document, tess_dl.If)
    assume(ifs)
    node = data.draw(st.sampled_from(ifs))
    out = node.with_condition(slot)
    new_text = tess_dl.dumps(out)
    old = node.condition
    assert new_text == text[: old.start] + slot.strip() + text[old.end :]
    assert [n.index_path for n in all_nodes(out.root)] == [
        n.index_path for n in all_nodes(document.root)
    ]
    assert out.at(node.index_path).condition.text == slot.strip()[2:-2]
    assert (
        out.at(node.index_path).body == node.body
        and out.at(node.index_path).else_body == node.else_body
    )


@settings(max_examples=300, deadline=None)
@given(files(), st.data(), SLOTS, st.sampled_from(["with_items", "with_key"]))
def test_with_items_and_with_key_change_one_span_and_nothing_else(text, data, slot, call):
    document = tess_dl.loads(text)
    fors = nodes_of(document, tess_dl.For)
    assume(fors)
    node = data.draw(st.sampled_from(fors))
    old = node.items if call == "with_items" else node.key
    out = getattr(node, call)(slot)
    new_text = tess_dl.dumps(out)
    assert new_text == text[: old.start] + slot.strip() + text[old.end :]
    assert [n.index_path for n in all_nodes(out.root)] == [
        n.index_path for n in all_nodes(document.root)
    ]
    new = out.at(node.index_path)
    assert new.variable == node.variable and new.body == node.body
    assert (new.key if call == "with_items" else new.items) == (
        node.key if call == "with_items" else node.items
    )


@settings(max_examples=300, deadline=None)
@given(files(), st.data(), st.sampled_from(["item", "k", "Row_2", "x"]))
def test_with_variable_changes_the_declaration_only(text, data, name):
    document = tess_dl.loads(text)
    fors = nodes_of(document, tess_dl.For)
    assume(fors)
    node = data.draw(st.sampled_from(fors))
    out = node.with_variable(name)
    new_text = tess_dl.dumps(out)
    start = re.compile(r"For[ \t\r]+").match(text, node.start).end()  # type: ignore[union-attr]
    assert new_text == text[:start] + name + text[start + len(node.variable) :]
    assert out.at(node.index_path).variable == name
    assert out.at(node.index_path).items == node.items and out.at(node.index_path).key == node.key
    assert tess_dl.loads(new_text, path=out.path) == out


@settings(max_examples=200, deadline=None)
@given(files(), st.data())
def test_a_slot_edit_followed_by_the_inverse_gives_back_the_original_text(text, data):
    document = tess_dl.loads(text)
    ifs = nodes_of(document, tess_dl.If)
    assume(ifs)
    node = data.draw(st.sampled_from(ifs))
    original = text[node.condition.start : node.condition.end]
    edited = node.with_condition("{{ zzz }}")
    back = edited.at(node.index_path).with_condition(original)
    assert tess_dl.dumps(back) == text


def test_the_reread_check_refuses_a_result_that_is_not_the_expected_node():
    """The guard behind every call: the node at the same path must read exactly as expected."""
    import dataclasses

    from tess_dl import _edit

    node = doc().at((2,))
    wrong = dataclasses.replace(node, variable="somethingelse")
    with pytest.raises(ValueError, match="more than the slot"):
        _edit._apply_node(node, doc().text, wrong)  # the text is unchanged: not `wrong`
    with pytest.raises(ValueError):  # a result where the node is no longer at its path
        _edit._apply_node(node, doc().text.replace("For x In", "Spacer { }\n  For x In"), node)
