"""Test shape definition parsing."""

import pytest

import comp
from tests import comptest


@comptest.params(
    "code",
    simple=("!shape ~point = {x ~num y ~num}",),
    dotted_name=("!shape ~geo.point = {x ~num y ~num}",),
    with_defaults=("!shape ~point = {x ~num = 0 y ~num = 0}",),
    predicate_field=("!shape ~user = {name ~str active? ~bool}",),  # ? for boolean predicate
    tag_as_type=("!shape ~status = {value #active}",),
    shape_spread=("!shape ~point3d = {..~point z ~num}",),
    nested_inline=("!shape ~circle = {pos ~{x ~num y ~num} radius ~num}",),
    deep_nested=("!shape ~transform = {translate ~{x ~num y ~num z ~num}}",),
    alias=("!shape ~number = ~num",),
    union=("!shape ~result = ~success | ~error",),
    optional_via_union=("!shape ~config = {email ~str | ~nil = {}}",),  # Optional via union
    positional=("!shape ~pair = {~num ~num}",),  # Positional fields (no names)
    positional_three=("!shape ~triple = {~num ~num ~num}",),
    mixed_positional=("!shape ~labeled = {~str name ~str}",),  # Mix positional and named
    complex=(
        "!shape ~entity = {id ~str pos ~{x ~num y ~num} found? ~bool}",
    ),
)
def test_valid_shape_definitions(key, code):
    """Test valid shape definitions parse and roundtrip correctly."""
    result = comp.parse_module(code)
    assert isinstance(result, comp.Module)
    assert len(result.statements) == 1
    assert isinstance(result.statements[0], comp.ShapeDefinition)
    comptest.roundtrip(result)


@comptest.params(
    "code,expected_tokens",
    simple=("!shape ~point = {x ~num}", ["point"]),
    dotted=("!shape ~geo.point = {x ~num}", ["geo", "point"]),
    deep=("!shape ~a.b.c = {x ~num}", ["a", "b", "c"]),
)
def test_shape_name_tokens(key, code, expected_tokens):
    """Test that shape names are parsed into correct token lists."""
    result = comp.parse_module(code)
    shape_def = result.statements[0]
    assert shape_def.tokens == expected_tokens
    comptest.roundtrip(result)


@comptest.params(
    "code,expected_fields",
    two_fields=("!shape ~point = {x ~num y ~num}", 2),
    three_fields=("!shape ~point3d = {x ~num y ~num z ~num}", 3),
    with_spread=("!shape ~point3d = {..~point z ~num}", 2),  # spread + field
    nested=("!shape ~circle = {pos ~{x ~num y ~num} radius ~num}", 2),
)
def test_shape_field_count(key, code, expected_fields):
    """Test that shape fields are counted correctly."""
    result = comp.parse_module(code)
    shape_def = result.statements[0]
    assert len(shape_def.kids) == expected_fields
    comptest.roundtrip(result)


@comptest.params(
    "code",
    predicate_simple=("!shape ~user = {active? ~bool}",),
    predicate_mixed=("!shape ~user = {name ~str verified? ~bool id ~num}",),
)
def test_predicate_field_names(key, code):
    """Test field names with ? suffix (Ruby idiom for boolean predicates).

    The ? is part of the field name, not special optional syntax.
    """
    result = comp.parse_module(code)
    shape_def = result.statements[0]

    # Find fields with ? in the name
    predicate_fields = [
        f for f in shape_def.kids
        if isinstance(f, comp.ShapeField) and '?' in f.name
    ]
    assert len(predicate_fields) > 0, "Should have at least one predicate field"

    # Check that the field name includes the ?
    for field in predicate_fields:
        assert field.name.endswith('?'), f"Predicate field name should end with ?: {field.name}"

    comptest.roundtrip(result)


@comptest.params(
    "code",
    simple_default=("!shape ~point = {x ~num = 0}",),
    multiple_defaults=("!shape ~point = {x ~num = 0 y ~num = 0}",),
    string_default=("!shape ~config = {host ~str = \"localhost\"}",),
)
def test_default_values(key, code):
    """Test fields with default values."""
    result = comp.parse_module(code)
    shape_def = result.statements[0]

    # Check that fields have defaults
    fields_with_defaults = [
        f for f in shape_def.kids
        if isinstance(f, comp.ShapeField) and f.default is not None
    ]
    assert len(fields_with_defaults) > 0, "Should have fields with defaults"

    comptest.roundtrip(result)


@comptest.params(
    "code",
    simple_spread=("!shape ~point3d = {..~point z ~num}",),
    multiple_spreads=("!shape ~combined = {..~base ..~extra id ~num}",),
    spread_with_defaults=("!shape ~data = {name ~str ..~defaults}",),  # Spread shape with defaults
)
def test_shape_spread(key, code):
    """Test shape spreading."""
    result = comp.parse_module(code)
    shape_def = result.statements[0]

    # Check that there's at least one spread
    spreads = [k for k in shape_def.kids if isinstance(k, comp.ShapeSpread)]
    assert len(spreads) > 0, "Should have at least one spread"

    comptest.roundtrip(result)


@comptest.params(
    "code",
    simple_nested=("!shape ~circle = {pos ~{x ~num y ~num}}",),
    deep_nested=("!shape ~a = {b ~{c ~{d ~num}}}",),
    nested_with_fields=("!shape ~entity = {pos ~{x ~num y ~num} name ~str}",),
)
def test_nested_inline_shapes(key, code):
    """Test nested inline shape definitions."""
    result = comp.parse_module(code)
    shape_def = result.statements[0]

    # The nested inline shape fields should be present as children of the field
    assert len(shape_def.kids) > 0

    comptest.roundtrip(result)


@comptest.params(
    "code",
    two_positional=("!shape ~pair = {~num ~num}",),
    three_positional=("!shape ~triple = {~str ~num ~bool}",),
    mixed=("!shape ~mixed = {~str name ~str id ~num}",),
    positional_with_default=("!shape ~pair = {~num ~num = 0}",),
)
def test_positional_fields(key, code):
    """Test positional (unnamed) fields in shapes.

    Positional fields have no name and are matched by position during morphing.
    """
    result = comp.parse_module(code)
    shape_def = result.statements[0]

    # Find positional fields (fields with no name)
    positional_fields = [
        f for f in shape_def.kids
        if isinstance(f, comp.ShapeField) and f.name is None
    ]
    assert len(positional_fields) > 0, "Should have at least one positional field"

    comptest.roundtrip(result)


@comptest.params(
    "code",
    simple_alias=("!shape ~number = ~num",),
    alias_to_custom=("!shape ~coordinate = ~point",),
    tag_alias=("!shape ~status-type = #status",),
    alias_with_default=("!shape ~one = ~num=1",),
    tag_alias_with_default=("!shape ~active = #bool=#true",),
    string_alias_with_default=("!shape ~empty = ~str=\"\"",),
)
def test_shape_aliases(key, code):
    """Test simple shape aliases and aliases with defaults."""
    result = comp.parse_module(code)
    shape_def = result.statements[0]

    assert isinstance(shape_def, comp.ShapeDefinition)
    comptest.roundtrip(result)


@comptest.params(
    "code",
    simple_union=("!shape ~result = ~success | ~error",),
    multi_union=("!shape ~value = ~num | ~str | ~bool",),
)
def test_shape_unions(key, code):
    """Test union shapes."""
    result = comp.parse_module(code)
    shape_def = result.statements[0]

    # Union creates a tree structure - should have children
    assert len(shape_def.kids) > 0

    comptest.roundtrip(result)


def test_complex_shape_definition():
    """Test a complex shape with multiple features."""
    code = """!shape ~entity = {
        id ~str
        name ~str = "unnamed"
        pos ~{x ~num y ~num z ~num}
        found? ~bool
        ..~timestamped
    }"""

    # Normalize whitespace for roundtrip comparison
    normalized = " ".join(code.split())

    result = comp.parse_module(normalized)
    shape_def = result.statements[0]

    assert isinstance(shape_def, comp.ShapeDefinition)
    assert shape_def.tokens == ["entity"]
    assert len(shape_def.kids) == 5  # 4 fields + 1 spread

    # Find different field types
    all_fields = [k for k in shape_def.kids if isinstance(k, comp.ShapeField)]
    predicate_fields = [f for f in all_fields if '?' in f.name]
    spreads = [k for k in shape_def.kids if isinstance(k, comp.ShapeSpread)]

    assert len(all_fields) == 4  # id, name, pos, found?
    assert len(predicate_fields) == 1  # found?
    assert len(spreads) == 1  # ..~timestamped

    comptest.roundtrip(result)
