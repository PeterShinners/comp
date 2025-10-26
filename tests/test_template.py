"""Test template operator functionality."""

import comp
import comptest


def test_template_basic():
    """Test basic template with named field."""
    # {name="Alice"} % "Hello, %{name}!"
    expr = comp.ast.TemplateOp(
        left=comp.ast.Structure([
            comp.ast.FieldOp(
                value=comp.ast.String("Alice"),
                key=comp.ast.String("name")
            )
        ]),
        right=comp.ast.String("Hello, %{name}!")
    )
    result = comptest.run_ast(expr)
    comptest.assert_value(result, "Hello, Alice!")


def test_template_positional():
    """Test template with positional fields."""
    # {10 20} % "Values: %{#0}, %{#1}"
    expr = comp.ast.TemplateOp(
        left=comp.ast.Structure([
            comp.ast.FieldOp(comp.ast.Number(10)),
            comp.ast.FieldOp(comp.ast.Number(20))
        ]),
        right=comp.ast.String("Values: %{#0}, %{#1}")
    )
    result = comptest.run_ast(expr)
    comptest.assert_value(result, "Values: 10, 20")


def test_template_empty_placeholder():
    """Test template with empty placeholder."""
    # 42 % "Answer: %{}"
    expr = comp.ast.TemplateOp(
        left=comp.ast.Number(42),
        right=comp.ast.String("Answer: %{}")
    )
    result = comptest.run_ast(expr)
    comptest.assert_value(result, "Answer: 42")


def test_template_multiple_placeholders():
    """Test template with multiple placeholders."""
    # {name="Alice" age=30} % "%{name} is %{age} years old"
    expr = comp.ast.TemplateOp(
        left=comp.ast.Structure([
            comp.ast.FieldOp(
                value=comp.ast.String("Alice"),
                key=comp.ast.String("name")
            ),
            comp.ast.FieldOp(
                value=comp.ast.Number(30),
                key=comp.ast.String("age")
            )
        ]),
        right=comp.ast.String("%{name} is %{age} years old")
    )
    result = comptest.run_ast(expr)
    comptest.assert_value(result, "Alice is 30 years old")


def test_template_nested_field():
    """Test template with nested field access."""
    # {user={name="Bob"}} % "User: %{user.name}"
    expr = comp.ast.TemplateOp(
        left=comp.ast.Structure([
            comp.ast.FieldOp(
                value=comp.ast.Structure([
                    comp.ast.FieldOp(
                        value=comp.ast.String("Bob"),
                        key=comp.ast.String("name")
                    )
                ]),
                key=comp.ast.String("user")
            )
        ]),
        right=comp.ast.String("User: %{user.name}")
    )
    result = comptest.run_ast(expr)
    comptest.assert_value(result, "User: Bob")


def test_template_from_source():
    """Test template operator parsing from source code."""
    module_ast = comp.parse_module('''
        !func |format-greeting ~{name ~str} = {
            {name=$in.name} % "Hello, %{name}!"
        }
    ''')
    
    engine = comp.Engine()
    module = comp.Module()
    module.prepare(module_ast, engine)
    engine.run(module_ast, module=module)
    
    # Look up and run the function
    funcs = module.lookup_function(['format-greeting'])
    assert funcs, "Function not found"
    func = funcs[0]
    
    # Run with input
    input_value = comp.Value({"name": "World"})
    result = engine.run_function(func, in_=input_value)
    
    comptest.assert_value(result, "Hello, World!")
