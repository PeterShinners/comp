"""
Simple test to see if spread is in the AST
"""

import comp


def test_parse_spread_ast():
    code = "{..@}"
    result = comp.parse_expr(code)
    print(f"\nParsed: {result}")
    print(f"Type: {type(result).__name__}")
    if hasattr(result, 'kids'):
        print(f"Kids: {result.kids}")
        for i, kid in enumerate(result.kids):
            print(f"  Kid {i}: {type(kid).__name__}")
            if hasattr(kid, 'value'):
                print(f"    Has value attribute")
                val = getattr(kid, 'value', None)
                if val:
                    print(f"    Value type: {type(val).__name__}")
    
    # Check if we have a StructSpread
    assert hasattr(result, 'kids')
    assert len(result.kids) > 0
    print(f"\nFirst kid is StructSpread: {type(result.kids[0]).__name__ == 'StructSpread'}")
