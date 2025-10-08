"""Test function definitions."""

import runtest

import comp


@runtest.params(
    "code, expected_funcs",
    # Simple function without args or shape
    simple=(
        "!func |greet = {hello}",
        {
            "greet": {
                "name": "greet",
                "impls": 1,
                "has_shape": False,
            }
        },
    ),
    # Function with inline shape, no args
    with_shape=(
        "!func |double ~{x ~num} = {x * 2}",
        {
            "double": {
                "name": "double",
                "impls": 1,
                "has_shape": True,
            }
        },
    ),
    # Function with args, no shape
    with_args=(
        "!func |repeat ^{count ~num} = {$in * ^count}",
        {
            "repeat": {
                "name": "repeat",
                "impls": 1,
                "has_shape": False,
            }
        },
    ),
    # Function with both shape and args
    full=(
        "!func |add ~{x ~num} ^{n ~num} = {x + ^n}",
        {
            "add": {
                "name": "add",
                "impls": 1,
                "has_shape": True,
            }
        },
    ),
    # Multiple implementations (overloads)
    overloaded=(
        """
        !func |process ~{x ~num} = {number}
        !func |process ~{s ~str} = {string}
        """,
        {
            "process": {
                "name": "process",
                "impls": 2,
                "has_shape": True,
            }
        },
    ),
)
def test_function_definitions(code, expected_funcs):
    """Test parsing and storing function definitions."""
    module = runtest.module_from_code(code)

    for func_name, expected in expected_funcs.items():
        assert func_name in module.funcs
        func = module.funcs[func_name]
        assert func.name == expected["name"]
        assert len(func.implementations) == expected["impls"]

        # Check if implementations have shapes
        if expected["has_shape"]:
            assert any(impl.shape for impl in func.implementations)


@runtest.params(
    "code, func_name, shape_check",
    # Inline shape definition
    inline=(
        "!func |process ~{x ~num y ~num} = {x + y}",
        "process",
        lambda impl: impl.shape is not None,
    ),
    # Referenced shape definition
    referenced=(
        """
        !shape ~point = {x ~num y ~num}
        !func |move ~point = {x + 1}
        """,
        "move",
        lambda impl: impl.shape is not None,
    ),
    # No shape
    no_shape=(
        "!func |identity = {$in}",
        "identity",
        lambda impl: impl.shape is None,
    ),
)
def test_function_shape_definitions(code, func_name, shape_check):
    """Test function shape definitions (inline vs referenced)."""
    module = runtest.module_from_code(code)
    assert func_name in module.funcs
    func = module.funcs[func_name]
    assert len(func.implementations) >= 1
    assert shape_check(func.implementations[0])


@runtest.params(
    "code, func_name, expected_impl_count",
    # Two distinct shapes
    distinct=(
        """
        !func |handle ~{x ~num} = {number}
        !func |handle ~{s ~str} = {string}
        """,
        "handle",
        2,
    ),
    # Three implementations
    triple=(
        """
        !func |format ~{n ~num} = {number}
        !func |format ~{s ~str} = {string}
        !func |format ~{b ~bool} = {boolean}
        """,
        "format",
        3,
    ),
    # Single implementation
    single=(
        "!func |simple = {data}",
        "simple",
        1,
    ),
)
def test_function_overloads(code, func_name, expected_impl_count):
    """Test function overloading with multiple implementations."""
    module = runtest.module_from_code(code)
    assert func_name in module.funcs
    func = module.funcs[func_name]
    assert len(func.implementations) == expected_impl_count
