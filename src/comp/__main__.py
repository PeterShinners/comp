#!/usr/bin/env python3
"""Comp CLI - Command-line interface for the Comp language.
"""

import argparse
import pathlib
import os
import sys
import io
import comp
from lark import Token, Tree

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


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


def prettyscan(scan):
    """Scan a module and display metadata using the interpreter."""
    # Display package metadata
    pkg_val = scan.field('pkg')
    if pkg_val.data:
        print("Package metadata:")
        for item in pkg_val.data.values():
            name = item.field('name').data
            value = item.field('value').data
            print(f"  {name} = {value!r}")
        print()

    # Display imports
    try:
        imports_val = scan.field('imports')
        if imports_val.data:
            print("Imports:")
            for item in imports_val.data.values():
                name = item.field('name').data
                source = item.field('source').data
                try:
                    compiler = item.field('compiler').data
                    compiler_str = f" ({compiler})" if compiler != 'comp' else ""
                except (KeyError, AttributeError):
                    compiler_str = ""
                try:
                    pos = item.field('pos')
                    pos_vals = list(pos.data.values())
                    pos_str = f" @ {pos_vals[0].data}:{pos_vals[1].data}"
                except (KeyError, AttributeError, IndexError):
                    pos_str = ""
                print(f"  {name}: {source!r}{compiler_str}{pos_str}")
            print()
    except (KeyError, AttributeError):
        pass

    # Display docs
    try:
        docs_val = scan.field('docs')
        if docs_val.data:
            print("Documentation:")
            for item in docs_val.data.values():
                content = item.field('content').data
                try:
                    pos = item.field('pos')
                    pos_vals = list(pos.data.values())
                    pos_str = f" @ {pos_vals[0].data}:{pos_vals[1].data}"
                except (KeyError, AttributeError, IndexError):
                    pos_str = ""
                lines = content.split('\n')
                preview = lines[0][:60]
                if len(lines) > 1 or len(lines[0]) > 60:
                    preview += "..."
                print(f"  {preview!r}{pos_str}")
            print()
    except (KeyError, AttributeError):
        pass


def show_imports(module, interp, visited=None, prefix=""):
    """Print import tree for a module.

    Args:
        module: Module to analyze
        interp: Interpreter instance
        visited: Dict of location -> resource for cycle detection
        prefix: Tree drawing prefix for current line
    """
    visited = visited or {}

    # Check for cycles
    if module.source.location in visited:
        print(f"{prefix}└── {visited[module.source.location]} (CYCLIC)")
        return

    # Print this module
    scan = module.scan()
    docs = scan.to_python("docs") or []
    doc = docs[0].get("content", "").split("\n")[0][:50] if docs else ""
    print(f'{prefix}{module.source.resource} "{doc}"' if doc else f"{prefix}{module.source.resource}")

    visited[module.source.location] = module.source.resource

    # Process imports
    imports = scan.to_python("imports") or []
    for i, imp in enumerate(imports):
        name = imp.get("name")
        source = imp.get("source")
        if not (name and source):
            continue

        is_last = (i == len(imports) - 1)
        connector = "└── " if is_last else "├── "
        new_prefix = prefix + ("    " if is_last else "│   ")

        try:
            imported = interp.module(source, anchor=module.source.anchor)
            print(f"{prefix}{connector}{name}:")
            show_imports(imported, interp, visited, new_prefix)
        except Exception:
            print(f"{prefix}{connector}{name}: {source} (NOT FOUND)")


def show_namespace(filepath_or_source, is_text=False):
    """Show the finalized namespace for a module.

    Args:
        filepath_or_source: Path to the module file or source text
        is_text: If True, treat first arg as source text instead of filepath
    """
    interp = comp.Interp()
    module = interp.module_from_text(filepath_or_source) if is_text else interp.module(filepath_or_source)
    ns = module.namespace()
    for name, (priority, value) in sorted(ns.items()):
        if priority < 0:  # Skip system builtins
            continue
        if isinstance(value, comp.Ambiguous):
            print(f"  {name}: <Ambiguous {len(value.qualified_names)} values>")
        elif isinstance(value, comp.OverloadSet):
            print(f"  {name}: <Overload {len(value.callables)} callables>")
        else:
            print(f"  {name}: {value.format()}")


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
    parser.add_argument("source", help="Comp source to parse")
    parser.add_argument("--text", action="store_true", help="Treat source as direct expression to be parsed")
    parser.add_argument("--pos", action="store_true", help="Show line:column positions for nodes")
    parser.add_argument("--resolve", action="store_true", help="Resolve cop references")
    parser.add_argument("--fold", action="store_true", help="Fold cop constants")

    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--larkscan", action="store_true", help="Show scan Lark parse tree")
    modes.add_argument("--larkcomp", action="store_true", help="Show full Lark parse tree")

    modes.add_argument("--cop", action="store_true", help="Report parsed cop structure")
    modes.add_argument("--unparse", action="store_true", help="Convert cop nodes back to source")
    modes.add_argument("--code", action="store_true", help="Build and show instruction code")
    modes.add_argument("--eval", action="store_true", help="Evaluate the expression and show the result")
    modes.add_argument("--trace", action="store_true", help="Show each instruction as it executes with its result")
    modes.add_argument("--scan", action="store_true", help="Scan module metadata (pkg assignments, imports, docstrings). Use with --lark to show scan grammar tree.")
    modes.add_argument("--imports", action="store_true", help="Show import dependency tree with module documentation")
    modes.add_argument("--namespace", action="store_true", help="Show the module's finalized namespace with all definitions")
    modes.add_argument("--definitions", action="store_true", help="Show list of module definition")

    argv = None
    try:
        import debugpy
        if debugpy.is_client_connected():
            print("Debugger attached.")
            argv = ['~(one~num=1+1-1 ~num=2+2*1 three=3)', '--text', '--unparse', '--fold']
    except ImportError:
        pass

    args = parser.parse_args(argv)

    interp = comp.Interp()
    if args.text:
        mod = interp.module_from_text(args.source)
    else:
        mod = interp.module(args.source, anchor=os.getcwd())

    if args.larkscan or args.larkcomp:
        parser = comp._parse._lark_parser("scan" if args.larkscan else "comp")
        tree = parser.parse(mod.source.content)
        prettylark(tree, show_positions=args.pos)
        return

    if args.scan:
        print()
        scan = mod.scan()
        prettyscan(scan)
        return

    if args.cop or args.unparse:
        cop_tree = comp._parse.parse(mod.source.content)

        if args.resolve:
            namespace = {}
            cop_tree = comp._parse.cop_resolve(cop_tree, namespace)
        if args.fold:
            cop_tree = comp._parse.cop_fold(cop_tree)
        if args.cop:
            prettycop(cop_tree, show_pos=args.pos)
        elif args.unparse:
            source_text = comp.cop_unparse(cop_tree)
            print(source_text)
        return

    if args.definitions:
        defs = mod.definitions()
        for name in sorted(defs.keys()):
            value = defs[name]
            print(f"  {name}: {value.format()}")

    if args.imports:
        if any([args.cop, args.resolve, args.code, args.eval, args.trace, args.scan, args.namespace]):
            parser.error("--imports cannot be combined with other output modes")
        show_imports(mod, interp)
        return

    # Handle --namespace mode separately (it's its own output mode)
    if args.namespace:
        if any([args.cop, args.resolve, args.code, args.eval, args.trace, args.scan, args.imports]):
            parser.error("--namespace cannot be combined with other output modes")
        # Show namespace
        show_namespace(args.source if not args.text else source, is_text=args.text)
        return

    # Check if any output mode was specified
    if not any([args.larkcomp, args.larkscan, args.cop, args.resolve, args.code, args.eval, args.trace, args.definitions, args.scan]):
        parser.error("No output mode specified. Use --larkcomp, --larkscan, --cop, --resolve, --code, --eval, --trace, --scan, --imports, --definitions, or --namespace")


if __name__ == "__main__":
    main()
