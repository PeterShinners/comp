#!/usr/bin/env python3
"""Test ExprIdentifier flattening fix"""

import comp

# Test cases
tests = [
    '(2+2).cat',
    '(2+2).cat.dog',
    '(2+2).cat.dog.mouse',
    '(x.y).a.b',
]

for expr in tests:
    print(f"\n{expr}")
    print("=" * 60)
    parsed = comp.parse_expr(expr)
    parsed.tree()
    
    # Verify it's flat
    root = parsed
    expr_ident = root.kids[0]
    if isinstance(expr_ident, comp.ast.ExprIdentifier):
        print(f"\n✓ ExprIdentifier with {len(expr_ident.kids)} kids")
        print(f"  - expr: {type(expr_ident.expr).__name__}")
        print(f"  - fields: {[type(f).__name__ for f in expr_ident.fields]}")
        
        # Check no nested ExprIdentifier
        for i, kid in enumerate(expr_ident.kids[1:], 1):
            if isinstance(kid, comp.ast.ExprIdentifier):
                print(f"  ✗ ERROR: Child {i} is ExprIdentifier (not flat!)")
            else:
                print(f"  ✓ Child {i}: {type(kid).__name__}")
    
    # Test round-trip
    unparsed = parsed.unparse()
    print(f"\nUnparse: {unparsed}")
