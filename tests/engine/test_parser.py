#!/usr/bin/env python
"""Comprehensive parser tests for engine."""

import comp.engine as comp

def test(label, expr):
    """Test parsing an expression."""
    try:
        result = comp.parse_expr(expr)
        print(f"✓ {label}: {result}")
        return True
    except Exception as e:
        print(f"✗ {label}: {e}")
        return False

print("Engine Parser Tests")
print("=" * 60)

# Literals
test("Number", "42")
test("Decimal", "3.14")
test("String", '"hello world"')
test("True", "true")
test("False", "false")

# Arithmetic
test("Addition", "1 + 2")
test("Subtraction", "10 - 3")
test("Multiplication", "4 * 5")
test("Division", "20 / 4")
test("Modulo", "17 % 5")
test("Power", "2 ^ 8")

# Comparison
test("Equality", "x == 5")
test("Not Equal", "x != 5")
test("Less Than", "x < 10")
test("Greater Than", "x > 0")

# Logical (using proper syntax)
test("And", "x > 0 && x < 10")
test("Or", "x == 5 || x == 10")
test("Not", "!!x")

# Structures
test("Empty Structure", "{}")
test("Single Value", "{5}")
test("Named Field", "{x = 5}")
test("Multiple Fields", "{x = 5 y = 10}")
test("Spread", "{x = 5 ..base}")

# Identifiers
test("Simple Identifier", "foo")
test("Field Access", "foo.bar")
test("Nested Field", "foo.bar.baz")
test("Local Scope", "@local")
test("Local Field", "@local.field")
test("Mod Scope", "$mod")
test("Mod Field", "$mod.value")

# Pipelines
test("Seeded Pipeline", "[5 |double]")
test("Unseeded Pipeline", "[|double]")
test("Pipeline Chain", "[5 |double |triple]")

# References
test("Tag Reference", "#tag")
test("Tag Path", "#tag.subtag")

# Note: Shape and function references are NOT valid as standalone expressions
# They can only be used in specific contexts (morphing, pipelines, etc.)

# Morphing (shape references are valid here)
test("Weak Morph", "x ~num")

print("=" * 60)
print("Parser tests complete!")
