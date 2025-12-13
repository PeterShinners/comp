#!/usr/bin/env python3
"""
Comp Parser Tool - Parse and display Comp language files.

Usage:
    python -m tools.parse_comp <file.comp>
    python -m tools.parse_comp <file.comp> --scan    # Use scanner grammar
    python -m tools.parse_comp <file.comp> --raw     # Show raw lark tree
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from lark import Lark, Token, Tree


# Grammar file locations
GRAMMAR_DIR = Path(__file__).parent.parent / "src" / "comp" / "lark"
COMP_GRAMMAR = GRAMMAR_DIR / "comp.lark"
SCAN_GRAMMAR = GRAMMAR_DIR / "scan.lark"


class TreePrinter:
    """
    Pretty printer for Lark parse trees.
    
    More readable than Lark's built-in pretty() for the Comp language.
    Shows tree structure with clear indentation and token values.
    """
    
    def __init__(self, indent: str = "  ", show_positions: bool = False):
        self.indent = indent
        self.show_positions = show_positions
    
    def print(self, tree: Tree, file=None) -> None:
        """Print the tree to stdout or a file."""
        output = self.format(tree)
        print(output, file=file or sys.stdout)
    
    def format(self, tree: Tree) -> str:
        """Format the tree as a string."""
        lines = []
        self._format_node(tree, lines, 0)
        return "\n".join(lines)
    
    def _format_node(self, node, lines: list, depth: int) -> None:
        """Recursively format a node and its children."""
        prefix = self.indent * depth
        
        if isinstance(node, Token):
            # Token: show type and value
            pos = f" @{node.line}:{node.column}" if self.show_positions else ""
            value = repr(node.value) if len(node.value) < 60 else repr(node.value[:57] + "...")
            lines.append(f"{prefix}{node.type}: {value}{pos}")
        
        elif isinstance(node, Tree):
            # Tree: show rule name and recurse into children
            pos = ""
            if self.show_positions and node.meta and node.meta.line:
                pos = f" @{node.meta.line}:{node.meta.column}"
            
            if len(node.children) == 0:
                lines.append(f"{prefix}{node.data}(){pos}")
            elif len(node.children) == 1 and isinstance(node.children[0], Token):
                # Compact single-token nodes
                child = node.children[0]
                value = repr(child.value)
                lines.append(f"{prefix}{node.data}: {value}{pos}")
            else:
                lines.append(f"{prefix}{node.data}:{pos}")
                for child in node.children:
                    self._format_node(child, lines, depth + 1)
        
        else:
            # Unknown node type
            lines.append(f"{prefix}??? {type(node).__name__}: {node!r}")


def load_parser(grammar_path: Path) -> Lark:
    """Load a Lark parser from a grammar file."""
    with open(grammar_path) as f:
        grammar = f.read()
    
    return Lark(
        grammar,
        parser="lalr",
        propagate_positions=True,
        import_paths=[str(GRAMMAR_DIR)],
    )


def parse_file(
    filepath: Path,
    use_scanner: bool = False,
    raw_output: bool = False,
    show_positions: bool = False,
) -> int:
    """
    Parse a file and display the results.
    
    Returns 0 on success, 1 on parse error.
    """
    # Select grammar
    grammar_path = SCAN_GRAMMAR if use_scanner else COMP_GRAMMAR
    grammar_name = "scan" if use_scanner else "comp"
    
    # Load source
    try:
        source = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1
    
    # Load parser
    try:
        parser = load_parser(grammar_path)
    except Exception as e:
        print(f"Error loading {grammar_name}.lark grammar: {e}", file=sys.stderr)
        return 1
    
    # Parse
    try:
        tree = parser.parse(source)
    except Exception as e:
        print(f"Parse error in {filepath.name}:", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        return 1
    
    # Display results
    print(f"# Parsed: {filepath.name} (using {grammar_name}.lark)")
    print()
    
    if raw_output:
        # Use Lark's built-in pretty printer
        print(tree.pretty())
    else:
        # Use our custom printer
        printer = TreePrinter(show_positions=show_positions)
        printer.print(tree)
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Parse and display Comp language files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m tools.parse_comp examples/cart.comp
    python -m tools.parse_comp examples/cart.comp --scan
    python -m tools.parse_comp examples/cart.comp --pos
    python -m tools.parse_comp examples/cart.comp --raw
        """,
    )
    
    parser.add_argument(
        "file",
        type=Path,
        help="Comp source file to parse",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Use the scanner grammar (scan.lark) instead of full grammar",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Show raw Lark tree output (built-in pretty)",
    )
    parser.add_argument(
        "--pos",
        action="store_true",
        help="Show line:column positions for nodes",
    )
    
    args = parser.parse_args()
    
    # Resolve file path
    filepath = args.file
    if not filepath.is_absolute():
        filepath = Path.cwd() / filepath
    
    sys.exit(parse_file(
        filepath,
        use_scanner=args.scan,
        raw_output=args.raw,
        show_positions=args.pos,
    ))


if __name__ == "__main__":
    main()
