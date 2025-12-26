#!/usr/bin/env python3
"""Comp CLI - Command-line interface for the Comp language.

Usage:
    comp <file.comp> --cop              # Show COP structure
    comp <file.comp> --code             # Show instruction code
    comp <file.comp> --eval             # Evaluate and show result
    comp <file.comp> --scan             # Scan module metadata
    comp <file.comp> --lark             # Show Lark parse tree
"""

import argparse
import pathlib
import sys
from pathlib import Path
import comp
from lark import Token, Tree


def prettylark(node, indent=0, show_positions=False):
    """Pretty-print a Lark parse tree.

    More readable than Lark's built-in pretty() for the Comp language.
    Shows tree structure with clear indentation and token values.
    """
    prefix = "  " * indent

    if isinstance(node, Token):
        # Token: show type and value
        pos = f" @{node.line}:{node.column}" if show_positions else ""
        value = repr(node.value) if len(node.value) < 60 else repr(node.value[:57] + "...")
        print(f"{prefix}{node.type}: {value}{pos}")

    elif isinstance(node, Tree):
        # Tree: show rule name and recurse into children
        pos = ""
        if show_positions and node.meta and node.meta.line:
            pos = f" @{node.meta.line}:{node.meta.column}"

        if len(node.children) == 0:
            print(f"{prefix}{node.data}(){pos}")
        elif len(node.children) == 1 and isinstance(node.children[0], Token):
            # Compact single-token nodes
            child = node.children[0]
            value = repr(child.value)
            print(f"{prefix}{node.data}: {value}{pos}")
        else:
            print(f"{prefix}{node.data}:{pos}")
            for child in node.children:
                prettylark(child, indent + 1, show_positions)

    else:
        # Unknown node type
        print(f"{prefix}??? {type(node).__name__}: {node!r}")


def prettycop(cop, field=None, indent=0, show_pos=False):
    """Pretty-print a cop structure."""
    ind = '  ' * indent
    if field:
        ind += f"{field}="
    if cop.shape is not comp.shape_struct or (
                cop.data and not isinstance(cop.positional(0).shape, comp.Tag)):
        valcop = cop.cop.format() if cop.cop else ""
        print(f"{ind}{cop.format()} <{cop.shape.qualified}> {valcop}")
        return

    items = list(cop.data.items())
    tokens = []
    kids = []
    pos = ""
    for key, value in items:
        key = key.data if not isinstance(key, comp.Unnamed) else None
        if key == "pos":
            if show_pos:
                nums = [n.data for n in value.data.values()]
                pos = f"  [{nums[0]},{nums[1]}-{nums[2]},{nums[3]}]"
            continue
        if key == "kids":
            kids = list(value.data.items())
            continue
        if key:
            tokens.append(f"{key}={value.format()}")
        else:
            tokens.append(value.format())
    line = " ".join(tokens)
    print(f"{ind}{line}{pos}")
    for field, child in kids:
        field = field.to_python() if not isinstance(field, comp.Unnamed) else None
        prettycop(child, field=field, indent=indent + 1, show_pos=show_pos)


def parse_source(source, use_scanner=False, show_positions=False):
    """Parse a file and display the results.

    Returns 0 on success, 1 on parse error.
    """
    grammar = "scan" if use_scanner else "comp"
    parser = comp._parse._lark_parser(grammar)
    tree = parser.parse(source)
    prettylark(tree, show_positions=show_positions)


def scan_module(source):
    """Scan a module and display metadata.

    Reports:
    - All pkg assignments in the module
    - All discovered imports
    """
    result = comp.scan(source)

    # Access via Value keys
    pkg_key = None
    imports_key = None
    docs_key = None
    for key in result.data.keys():
        if key.data == "pkg":
            pkg_key = key
        elif key.data == "imports":
            imports_key = key
        elif key.data == "docs":
            docs_key = key

    # Display package metadata
    if pkg_key:
        pkg_list = result.data[pkg_key]
        if pkg_list.data:
            print("Package metadata:")
            for pkg_item in pkg_list.data.values():
                # Find keys by matching string values
                name = None
                value = None
                pos = None
                for k, v in pkg_item.data.items():
                    if k.data == "name":
                        name = v
                    elif k.data == "value":
                        value = v
                    elif k.data == "pos":
                        pos = v

                if pos and pos.data:
                    pos_vals = list(pos.data.values())
                    pos_str = f" @ {pos_vals[0].data}:{pos_vals[1].data}"
                else:
                    pos_str = ""
                print(f"  {name.data} = {value.data!r}{pos_str}")
            print()

    # Display imports
    if imports_key:
        import_list = result.data[imports_key]
        if import_list.data:
            print("Imports:")
            for imp_item in import_list.data.values():
                # Find keys by matching string values
                name = None
                source = None
                compiler = None
                pos = None
                for k, v in imp_item.data.items():
                    if k.data == "name":
                        name = v
                    elif k.data == "source":
                        source = v
                    elif k.data == "compiler":
                        compiler = v
                    elif k.data == "pos":
                        pos = v

                compiler_str = f" ({compiler.data})" if compiler else ""
                if pos and pos.data:
                    pos_vals = list(pos.data.values())
                    pos_str = f" @ {pos_vals[0].data}:{pos_vals[1].data}"
                else:
                    pos_str = ""
                print(f"  {name.data}: {source.data!r}{compiler_str}{pos_str}")
            print()

    # Display docs
    if docs_key:
        doc_list = result.data[docs_key]
        if doc_list.data:
            print("Documentation:")
            for doc_item in doc_list.data.values():
                # Find keys by matching string values
                content = None
                pos = None
                for k, v in doc_item.data.items():
                    if k.data == "content":
                        content = v
                    elif k.data == "pos":
                        pos = v

                if pos and pos.data:
                    pos_vals = list(pos.data.values())
                    pos_str = f" @ {pos_vals[0].data}:{pos_vals[1].data}"
                else:
                    pos_str = ""

                # Show first line as preview
                if content and content.data:
                    lines = content.data.split('\n')
                    preview = lines[0][:60]
                    if len(lines) > 1 or len(lines[0]) > 60:
                        preview += "..."
                    print(f"  {preview!r}{pos_str}")
            print()


def format_instruction(idx, instr, indent=0):
    """Format a single instruction for display."""
    # Get instruction type name
    instr_type = instr.__class__.__name__

    # Indentation prefix
    ind = "  " * indent

    # Build a compact representation
    parts = [f"{instr_type}"]

    # Add key attributes based on instruction type
    if hasattr(instr, 'value') and instr.value is not None:
        # Const instruction
        parts.append(f"value={instr.value.format()}")
    if hasattr(instr, 'op') and instr.op is not None:
        # Binary/Unary op
        parts.append(f"op='{instr.op}'")
    if hasattr(instr, 'name') and instr.name is not None:
        # LoadVar/StoreVar
        parts.append(f"name='{instr.name}'")
    if hasattr(instr, 'left') and instr.left is not None:
        # BinOp
        left_str = instr.left.format() if hasattr(instr.left, 'format') else instr.left
        parts.append(f"left={left_str}")
    if hasattr(instr, 'right') and instr.right is not None:
        # BinOp
        right_str = instr.right.format() if hasattr(instr.right, 'format') else instr.right
        parts.append(f"right={right_str}")
    if hasattr(instr, 'operand') and instr.operand is not None:
        # UnOp
        operand_str = instr.operand.format() if hasattr(instr.operand, 'format') else instr.operand
        parts.append(f"operand={operand_str}")
    if hasattr(instr, 'source') and instr.source is not None:
        # StoreVar, Return
        source_str = instr.source.format() if hasattr(instr.source, 'format') else instr.source
        parts.append(f"source={source_str}")
    if hasattr(instr, 'callable') and instr.callable is not None:
        # Invoke
        callable_str = instr.callable.format() if hasattr(instr.callable, 'format') else instr.callable
        parts.append(f"callable={callable_str}")
    if hasattr(instr, 'args') and instr.args is not None:
        # Invoke
        args_str = instr.args.format() if hasattr(instr.args, 'format') else instr.args
        parts.append(f"args={args_str}")
    if hasattr(instr, 'fields') and instr.fields is not None:
        # BuildStruct - show the field values
        field_strs = []
        for key, val in instr.fields:
            if isinstance(key, comp.Unnamed):
                key_str = "#"
            else:
                key_str = repr(key) if isinstance(key, str) else key.format() if hasattr(key, 'format') else str(key)
            val_str = val.format() if hasattr(val, 'format') else val
            field_strs.append(f"{key_str}={val_str}")
        parts.append(f"[{', '.join(field_strs)}]")

    # Always show dest if present
    if hasattr(instr, 'dest') and instr.dest is not None:
        parts.append(f"-> {instr.dest}")

    result = f"{ind}  {idx:3d}  {' '.join(parts)}"

    # If this is a BuildBlock, show nested body instructions
    if hasattr(instr, 'body_instructions') and instr.body_instructions:
        result += f"\n{ind}       Body ({len(instr.body_instructions)} instructions):"
        for i, body_instr in enumerate(instr.body_instructions):
            result += "\n" + format_instruction(i, body_instr, indent + 2)

    return result


def main():
    parser = argparse.ArgumentParser(
        prog="comp",
        description="Comp language command-line interface")
    parser.add_argument("source",
        help="Comp source to parse")
    parser.add_argument("--text", action="store_true",
        help="Treat source as direct expression to be parsed")
    parser.add_argument("--lark", action="store_true",
        help="Show Lark parse tree")
    parser.add_argument("--cop", action="store_true",
        help="Report parsed cop structure")
    parser.add_argument("--resolve", action="store_true",
        help="Report resolved cop structure")
    parser.add_argument("--code", action="store_true",
        help="Build and show instruction code")
    parser.add_argument("--eval", action="store_true",
        help="Evaluate the expression and show the result")
    parser.add_argument("--trace", action="store_true",
        help="Show each instruction as it executes with its result")
    parser.add_argument("--no-fold", action="store_true",
        help="Disable constant folding during resolve (use with --code or --eval)")
    parser.add_argument("--scan", action="store_true",
        help="Scan module metadata (pkg assignments, imports, docstrings). Use with --lark to show scan grammar tree.")
    parser.add_argument( "--raw", action="store_true",
        help="Show raw Lark tree output (built-in pretty)")
    parser.add_argument("--pos", action="store_true",
        help="Show line:column positions for nodes")

    argv = None
    try:
        import debugpy
        if debugpy.is_client_connected():
            print("Debugger attached.")
            argv = ['examples/cart.comp', '--cop']
    except ImportError:
        pass

    args = parser.parse_args(argv)

    if args.text:
        source = args.source
    else:
        filepath = pathlib.Path(args.source)
        if not filepath.is_absolute():
            filepath = Path.cwd() / filepath
        source = filepath.read_text()

    # Handle --scan mode separately (it's its own output mode)
    if args.scan:
        if any([args.cop, args.resolve, args.code, args.eval, args.trace]):
            parser.error("--scan cannot be combined with other output modes")
        if args.lark:
            # Show lark tree with scan grammar
            parse_source(source, use_scanner=True, show_positions=args.pos)
        else:
            # Perform module scanning and display metadata
            scan_module(source)
        return

    # Check if any output mode was specified
    if not any([args.lark, args.cop, args.resolve, args.code, args.eval, args.trace]):
        parser.error("No output mode specified. Use --lark, --cop, --resolve, --code, --eval, --trace, or --scan")

    if args.lark:
        # Show Lark parse tree
        parse_source(source, use_scanner=args.scan, show_positions=args.pos)
    elif args.cop or args.resolve or args.code or args.eval or args.trace:
        cop = comp.parse(source)
        if args.resolve or args.code or args.eval or args.trace:
            namespace = None
            cop = comp.resolve(cop, namespace, no_fold=args.no_fold)
        if args.code:
            # Build instructions and display them
            instructions = comp.build(cop)
            print(f"Instructions ({len(instructions)}):")
            for i, instr in enumerate(instructions):
                print(format_instruction(i, instr))
        elif args.eval:
            # Build and execute instructions
            instructions = comp.build(cop)
            interp = comp.Interp()
            result = interp.execute(instructions)
            print(f"Result: {result.format()}")
        elif args.trace:
            # Build and execute with tracing
            instructions = comp.build(cop)
            interp = comp.Interp()
            frame = comp._interp.ExecutionFrame()

            print(f"Trace ({len(instructions)} instructions):")
            for i, instr in enumerate(instructions):
                result = instr.execute(frame)
                print(format_instruction(i, instr))
                print(f"       => {result.format()}")

            print(f"\nFinal result: {result.format()}")
        else:
            prettycop(cop, show_pos=args.pos)


if __name__ == "__main__":
    main()
