"""Test function definitions."""

import runtest

import comp


@runtest.params(
    "code, expected_funcs",
    # Simple function without args or shape
    simple=(
        "!func |greet ~nil = {hello}",
        {
            "greet": {"name": "greet", "impls": 1}
        },
    ),
    # Function with inline shape, no args
    with_shape=(
        "!func |double ~{x ~num} = {x * 2}",
        {
            "double": {"name": "double", "impls": 1}
        },
    ),
    # Function with args, no shape
    with_args=(
        "!func |repeat ~nil ^{count ~num} = {$in * ^count}",
        {
            "repeat": {"name": "repeat", "impls": 1}
        },
    ),
    # Function with both shape and args
    full=(
        "!func |add ~{x ~num} ^{n ~num} = {x + ^n}",
        {
            "add": {"name": "add", "impls": 1}
        },
    ),
    # Multiple implementations (overloads)
    overloaded=(
        """
        !func |process ~{x ~num} = {number}
        !func |process ~{s ~str} = {string}
        """,
        {
            "process": {"name": "process", "impls": 2}
        },
    ),
)
def test_function_definitions(key, code, expected_funcs):
    """Test parsing and storing function definitions."""
    module = runtest.module_from_code(code)

    for func_name, expected in expected_funcs.items():
        assert func_name in module.funcs
        func = module.funcs[func_name]
        assert func.name == expected["name"]
        assert len(func.implementations) == expected["impls"]


@runtest.params(
    "code, func_name",
    # Inline shape definition
    inline=(
        "!func |process ~{x ~num y ~num} = {x + y}",
        "process",
    ),
    # Referenced shape definition
    referenced=(
        """
        !shape ~point = {x ~num y ~num}
        !func |move ~point = {x + 1}
        """,
        "move",
    ),
    # No shape
    no_shape=(
        "!func |identity ~nil = {$in}",
        "identity",
    ),
)
def test_function_shape_definitions(key, code, func_name):
    """Test function shape definitions (inline vs referenced)."""
    module = runtest.module_from_code(code)
    assert func_name in module.funcs
    func = module.funcs[func_name]
    assert len(func.implementations) >= 1


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
        "!func |simple ~nil = {data}",
        "simple",
        1,
    ),
)
def test_function_overloads(key, code, func_name, expected_impl_count):
    """Test function overloading with multiple implementations."""
    module = runtest.module_from_code(code)
    assert func_name in module.funcs
    func = module.funcs[func_name]
    assert len(func.implementations) == expected_impl_count
