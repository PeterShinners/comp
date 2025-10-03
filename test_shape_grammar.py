#!/usr/bin/env python3
"""Quick validation of shape definition grammar."""

import comp

# Test cases for shape definitions
test_cases = [
    # Simple shape
    "!shape ~point = {x ~num y ~num}",
    
    # With defaults
    "!shape ~point = {x ~num = 0 y ~num = 0}",
    
    # Optional fields
    "!shape ~user = {name ~str email? ~str}",
    
    # Tag as type
    "!shape ~status = {value #active}",
    
    # Spread
    "!shape ~point3d = {..~point z ~num}",
    
    # Nested inline shape
    "!shape ~circle = {pos ~{x ~num y ~num} radius ~num}",
    
    # Union
    "!shape ~result = ~success | ~error",
    
    # Alias
    "!shape ~number = ~num",
]

print("Testing shape definition grammar...\n")

for i, code in enumerate(test_cases, 1):
    print(f"Test {i}: {code}")
    try:
        result = comp.parse_module(code)
        print(f"  ✓ Parsed successfully")
        print(f"  Tree: {result.tree}")
        print()
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        print()

print("Done!")
