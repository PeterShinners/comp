"""Test tag definitions and hierarchy construction."""

import runtest

import comp


def test_tag_redefinition_union():
    """Test that tag definitions union together (last value wins)."""
    code = """
    !tag #status = 0
    !tag #status = "unknown"
    !tag #status.active = 1
    !tag #status.active = 100
    """
    module = runtest.module_from_code(code)

    # Root tag: last definition wins
    assert "status" in module.tags
    status_value = module.tags["status"].value.to_python()
    assert status_value == "unknown", f"Expected 'unknown', got {status_value}"

    # Child tag: last definition wins
    assert "status.active" in module.tags
    active_value = module.tags["status.active"].value.to_python()
    assert active_value == 100, f"Expected 100, got {active_value}"


def test_tag_hierarchy_implicit_parents():
    """Test that parent tags are created implicitly."""
    code = """
    !tag #a.b.c.d = 42
    """
    module = runtest.module_from_code(code)

    # All parents should exist
    assert "a" in module.tags
    assert "a.b" in module.tags
    assert "a.b.c" in module.tags
    assert "a.b.c.d" in module.tags

    # Only leaf has value
    assert module.tags["a"].value is None
    assert module.tags["a.b"].value is None
    assert module.tags["a.b.c"].value is None
    assert module.tags["a.b.c.d"].value.to_python() == 42


def test_tag_with_expressions():
    """Test tags with simple expression values (currently limited by grammar)."""
    code = """
    !tag #computed = 2 + 3
    !tag #neg = -10
    !tag #paren = (42)
    """
    module = runtest.module_from_code(code)

    # Simple expressions should work
    assert module.tags["computed"].value.to_python() == 5
    assert module.tags["neg"].value.to_python() == -10
    assert module.tags["paren"].value.to_python() == 42


def test_comprehensive_tag_definition():
    """Test a realistic comprehensive tag definition combining all styles."""
    code = """
    !tag #status = "unknown" {
        #active = 1
        #inactive = 0
    }

    !tag #status.pending = 2
    !tag #status.error = -1 {
        #timeout = -100
        #network
    }

    !tag #priority = {
        #low = 1
        #medium = 2
        #high = 3
    }
    !tag #priority.critical = 99
    """
    module = runtest.module_from_code(code)
    expected = {
        "status": "unknown",
        "status.active": 1,
        "status.inactive": 0,
        "status.pending": 2,
        "status.error": -1,
        "status.error.timeout": -100,
        "status.error.network": None,
        "priority": None,
        "priority.low": 1,
        "priority.medium": 2,
        "priority.high": 3,
        "priority.critical": 99,
    }

    assert len(module.tags) == len(expected)
    for tag_name, expected_value in expected.items():
        assert tag_name in module.tags, f"Missing #{tag_name}"
        if expected_value is None:
            assert module.tags[tag_name].value is None
        else:
            actual = module.tags[tag_name].value.to_python()
            assert actual == expected_value, f"#{tag_name}: expected {expected_value}, got {actual}"



@runtest.params(
    "code, expr, result",
    # Basic is-a checks
    equal=(
        "!tag #status",
        "[#status |is-a parent=#status]",
        True
    ),
    direct_child=(
        "!tag #status = {#error}",
        "[#error.status |is-a parent=#status]",
        True
    ),
    grandchild=(
        "!tag #status = {#error = {#timeout}}",
        "[#timeout.error.status |is-a parent=#status]",
        True
    ),
    sibling=(
        "!tag #status = {#error #warning}",
        "[#error.status |is-a parent=#warning.status]",
        False
    ),
    not_related=(
        "!tag #status\n!tag #color",
        "[#status |is-a parent=#color]",
        False
    ),
    # Partial name matching
    partial_child=(
        "!tag #http.status = {#error}",
        "[#error |is-a parent=#status]",
        True
    ),
)
def test_is_a_hierarchy(key, code, expr, result, scopes):
    """Test is-a function for tag hierarchy checking."""
    module_ast = comp.parse_module(code)
    mod = comp.run.Module("test")
    mod.process_builtins()
    mod.process_ast(module_ast)
    mod.resolve_all()
    
    expr_ast = comp.parse_expr(expr)
    
    value = comp.run.evaluate(expr_ast.kids[0], mod, scopes)
    expected = comp.run.Value(result)
    assert value == expected
