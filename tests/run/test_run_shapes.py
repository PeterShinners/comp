"""Test shape definitions."""

import runtest

import comp


@runtest.params(
    "code, expected_shapes",
    # Simple shape with named fields
    basic=(
        "!shape ~point = {x ~num y ~num}",
        {
            "point": {
                "name": "point",
                "field_count": 2,
            }
        },
    ),
    # Shape with defaults
    with_defaults=(
        "!shape ~config = {port ~num = 8080 host ~str = localhost}",
        {
            "config": {
                "name": "config",
                "field_count": 2,
            }
        },
    ),
    # Shape with mixed named and typed fields
    mixed=(
        "!shape ~data = {name ~str count ~num active ~bool}",
        {
            "data": {
                "name": "data",
                "field_count": 3,
            }
        },
    ),
    # Positional shape (fields without names)
    positional=(
        "!shape ~pair = {~num ~num}",
        {
            "pair": {
                "name": "pair",
                "field_count": 2,
            }
        },
    ),
    # Mixed positional and named
    mixed_pos=(
        "!shape ~labeled = {~str name ~str}",
        {
            "labeled": {
                "name": "labeled",
                "field_count": 2,
            }
        },
    ),
)
def test_shape_definitions(code, expected_shapes):
    """Test basic shape definitions with various field types."""
    module = runtest.module_from_code(code)
    for shape_name, expected in expected_shapes.items():
        assert shape_name in module.shapes
        shape = module.shapes[shape_name]
        assert shape.name == expected["name"]
        assert len(shape.fields) == expected["field_count"]


@runtest.params(
    "code, shape_name, expected_field_count",
    # Shape inheritance with spread
    inherited=(
        """
        !shape ~point-2d = {x ~num y ~num}
        !shape ~point-3d = {..~point-2d z ~num}
        """,
        "point-3d",
        3,
    ),
    # Multiple inheritance
    multiple=(
        """
        !shape ~timestamped = {created ~str updated ~str}
        !shape ~identified = {id ~str}
        !shape ~entity = {..~timestamped ..~identified name ~str}
        """,
        "entity",
        4,
    ),
)
def test_shape_spread(code, shape_name, expected_field_count):
    """Test shape spreading and inheritance."""
    module = runtest.module_from_code(code)
    assert shape_name in module.shapes
    shape = module.shapes[shape_name]
    assert len(shape.fields) == expected_field_count


@runtest.params(
    "code, shape_name, verify_union",
    # Simple union
    simple_union=(
        """
        !shape ~success = {value ~any}
        !shape ~error = {message ~str}
        !shape ~result = ~success | ~error
        """,
        "result",
        lambda shape: shape.shape is not None,
    ),
    # Union with primitives
    primitive_union=(
        "!shape ~flexible = ~num | ~str",
        "flexible",
        lambda shape: shape.shape is not None,
    ),
    # Three-way union
    triple_union=(
        """
        !shape ~a = {x ~num}
        !shape ~b = {y ~num}
        !shape ~c = {z ~num}
        !shape ~abc = ~a | ~b | ~c
        """,
        "abc",
        lambda shape: shape.shape is not None,
    ),
)
def test_shape_unions(code, shape_name, verify_union):
    """Test shape union definitions."""
    module = runtest.module_from_code(code)
    assert shape_name in module.shapes
    shape = module.shapes[shape_name]
    assert verify_union(shape)


@runtest.params(
    "code, shape_name",
    # Tag field constraint
    tag_field=(
        """
        !tag #status = {#active #inactive}
        !shape ~user = {name ~str status #status}
        """,
        "user",
    ),
    # Tag array field
    tag_array=(
        """
        !tag #permission = {#read #write #admin}
        !shape ~role = {name ~str perms #permission[]}
        """,
        "role",
    ),
)
def test_shape_tag_fields(code, shape_name):
    """Test shapes with tag-typed fields."""
    module = runtest.module_from_code(code)

    assert shape_name in module.shapes
    shape = module.shapes[shape_name]
    assert shape._resolved
