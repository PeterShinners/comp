#!/usr/bin/env python3
"""
Comp Parser Tool - Parse and display Comp language files.

Usage:
    python -m tools.parse_comp <file.comp>
    python -m tools.parse_comp <file.comp> --scan    # Use scanner grammar
    python -m tools.parse_comp <file.comp> --raw     # Show raw lark tree
"""

import argparse
import pathlib
import sys
from pathlib import Path
from typing import Optional
import comp
from lark import Lark, Token, Tree


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


def prettycop(cop, field=None, indent=0):
    """Pretty-print a cop structure."""
    ind = '  ' * indent
    if field:
        ind += f"{field}="
    if cop.shape is not comp.shape_struct:
        print(f"{ind}{cop.format()} <not a cop>")
        return

    items = list(cop.data.items())
    tokens = []
    kids = []
    for key, value in items:
        key = key.data if not isinstance(key, comp.Unnamed) else None
        if key == "pos":
            continue
        if key == "kids":
            kids = list(value.data.items())
            continue
        if key:
            tokens.append(f"{key}={value.format()}")
        else:
            tokens.append(value.format())
    line = " ".join(tokens)
    print(f"{ind}{line}")
    for field, child in kids:
        field = field.to_python() if not isinstance(field, comp.Unnamed) else None
        prettycop(child, field=field, indent=indent + 1)


def parse_source(source, use_scanner=False, show_positions=False):
    """Parse a file and display the results.
    
    Returns 0 on success, 1 on parse error.
    """
    grammar = "scan" if use_scanner else "comp"
    parser = comp._parse._lark_parser(grammar)
    tree = parser.parse(source)
    printer = TreePrinter(show_positions=show_positions)
    printer.print(tree)


def main():
    parser = argparse.ArgumentParser(
        description="Parse and display Comp language files.")
    parser.add_argument("source",
        help="Comp source to parse")
    parser.add_argument("--text", action="store_true",
        help="Treat source as direct expression to be parsed")
    parser.add_argument("--cop", action="store_true",
        help="Report parsed cop structure")
    parser.add_argument("--resolve", action="store_true",
        help="Report resolved cop structure")
    parser.add_argument("--scan", action="store_true",
        help="Use the scanner grammar (scan.lark) instead of full grammar")
    parser.add_argument( "--raw", action="store_true",
        help="Show raw Lark tree output (built-in pretty)")
    parser.add_argument("--pos", action="store_true",
        help="Show line:column positions for nodes")
    
    argv = None
    try:
        import debugpy
        if debugpy.is_client_connected():
            print("Debugger attached.")
            argv = ['11+ -2.34', '--text', '--resolve']
    except ImportError:
        pass

    args = parser.parse_args(argv)
    if args.scan and args.cop:
        raise SystemExit("Can't mix --scan and --cop flags")

    if args.text:
        source = args.source
    else:
        filepath = pathlib.Path(args.source)
        if not filepath.is_absolute():
            filepath = Path.cwd() / filepath
        source = filepath.read_text()

    if args.cop or args.resolve:
        cop = comp.parse(source)
        if args.resolve:
            namespace = None
            cop = comp.resolve(cop, namespace)
        prettycop(cop)
    else:
        parse_source(source, use_scanner=args.scan, show_positions=args.pos)


if __name__ == "__main__":
    main()
