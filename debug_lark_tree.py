#!/usr/bin/env python3
"""
Debug utility to show Lark parse trees for Comp expressions.

This helps visualize what's happening at the grammar level before AST transformation.
"""

import sys
from pathlib import Path

# Add the src directory to the path so we can import comp
sys.path.insert(0, str(Path(__file__).parent / "src"))

from lark import Lark
from lark.tree import pydot__tree_to_png  # For generating tree images if needed


def get_comp_parser():
    """Get the raw Lark parser for Comp grammar."""
    # Read the grammar files
    grammar_dir = Path(__file__).parent / "src" / "comp" / "lark"
    
    # Read main grammar
    with open(grammar_dir / "comp.lark") as f:
        comp_grammar = f.read()
    
    # Read literals grammar  
    with open(grammar_dir / "literals.lark") as f:
        literals_grammar = f.read()
    
    # Combine the grammars
    full_grammar = literals_grammar + "\n\n" + comp_grammar
    
    # Create parser with keep_all_tokens to see more detail
    parser = Lark(
        full_grammar,
        parser='lalr',
        start='expression',
        keep_all_tokens=True,
        maybe_placeholders=False
    )
    
    return parser


def pretty_print_tree(tree, indent=0):
    """Pretty print a Lark tree in a readable format."""
    spaces = "  " * indent
    
    if hasattr(tree, 'data'):
        # This is a Tree node
        print(f"{spaces}{tree.data}")
        for child in tree.children:
            pretty_print_tree(child, indent + 1)
    else:
        # This is a Token
        if hasattr(tree, 'type'):
            print(f"{spaces}[{tree.type}] '{tree.value}'")
        else:
            print(f"{spaces}'{tree}'")


def debug_parse(expression):
    """Parse an expression and show the Lark tree."""
    parser = get_comp_parser()
    
    print(f"Parsing: {expression}")
    print("=" * 50)
    
    try:
        tree = parser.parse(expression)
        pretty_print_tree(tree)
        return tree
    except Exception as e:
        print(f"Parse error: {e}")
        return None


def debug_multiple(expressions):
    """Debug multiple expressions at once."""
    parser = get_comp_parser()
    
    for expr in expressions:
        print(f"\nParsing: {expr}")
        print("-" * 40)
        
        try:
            tree = parser.parse(expr)
            pretty_print_tree(tree)
        except Exception as e:
            print(f"Parse error: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Parse command line arguments
        expression = " ".join(sys.argv[1:])
        debug_parse(expression)
    else:
        # Test the problematic pipeline cases
        test_expressions = [
            # Working cases
            "{data|:blk}",
            "{data|?fallback}",
            "{data|<<debug}",
            
            # Failing cases  
            "{|:blk}",
            "{|?fallback}", 
            "{|<<debug}",
            
            # Simple cases for comparison
            "{data}",
            "data|:blk",
            "|:blk",
        ]
        
        print("Debugging pipeline expressions at Lark level:")
        debug_multiple(test_expressions)