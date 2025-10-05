"""
Test what the parser produces for spread syntax
"""

import comp


def test_parse_spread_only():
    """Parse spread without assignment"""
    code = "{..$ctx.server}"
    
    result = comp.parse_expr(code)
    print(f"\nSpread only AST: {result}")
    print(f"Type: {type(result)}")
    if hasattr(result, 'fields'):
        print(f"Fields: {result.fields}")


def test_parse_assignment_only():
    """Parse assignment without spread"""
    code = "{port=100}"
    
    result = comp.parse_expr(code)
    print(f"\nAssignment only AST: {result}")
    print(f"Type: {type(result)}")
    if hasattr(result, 'fields'):
        print(f"Fields: {result.fields}")


def test_parse_spread_with_assignment():
    """Parse spread and assignment together"""
    code = "{..$ctx.server port=100}"
    
    result = comp.parse_expr(code)
    print(f"\nSpread + assignment AST: {result}")
    print(f"Type: {type(result)}")
    if hasattr(result, 'fields'):
        print(f"Fields: {result.fields}")


def test_parse_assignment_with_spread():
    """Parse assignment then spread"""
    code = "{port=100 ..$ctx.server}"
    
    result = comp.parse_expr(code)
    print(f"\nAssignment + spread AST: {result}")
    print(f"Type: {type(result)}")
    if hasattr(result, 'fields'):
        print(f"Fields: {result.fields}")
