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


def scan_module(filepath):
    """Scan a module and display metadata using the interpreter.

    Uses the interpreter's import system to:
    1. Locate the module (creating ModuleSource)
    2. Run scan() on the source content
    3. Display the scan results

    Reports:
    - Module location and metadata
    - All pkg assignments in the module
    - All discovered imports
    - All documentation strings

    Args:
        filepath: Path to the module file to scan
    """
    # Create interpreter to use the import system
    interp = comp.Interp()

    # Convert filepath to absolute path
    filepath = pathlib.Path(filepath)
    if not filepath.is_absolute():
        filepath = pathlib.Path.cwd() / filepath

    # Determine resource identifier and from_dir
    # For simplicity, use relative import from the file's parent directory
    from_dir = filepath.parent
    resource = f"./{filepath.stem}"  # e.g., "./cart" for "cart.comp"

    try:
        # Locate the module source using the interpreter
        module_source = interp.import_locate(resource, from_dir=from_dir)

        # Display source metadata
        print(f"Module: {module_source.resource}")
        print(f"Location: {module_source.location}")
        print(f"Type: {module_source.source_type}")
        print()

        # Scan the source content
        result = comp.scan(module_source.content)
    except comp._import.ModuleNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

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


def build_dependency_tree(filepath, interp, visited=None, depth=0):
    """Recursively build import dependency tree for a module.

    Args:
        filepath: Path to the module file
        interp: Interpreter instance (for caching)
        visited: Set of resource identifiers already visited (for cycle detection)
        depth: Current recursion depth

    Returns:
        dict with keys:
            'resource': Module resource identifier
            'location': Full file path
            'doc_summary': First line of module documentation (or None)
            'imports': List of (name, import_dict or error_str)
            'cyclic': True if this module was already visited
    """
    if visited is None:
        visited = set()

    # Convert filepath to absolute path and determine resource
    filepath = pathlib.Path(filepath)
    if not filepath.is_absolute():
        filepath = pathlib.Path.cwd() / filepath

    from_dir = filepath.parent
    resource = f"./{filepath.stem}"

    # Check for cycles
    if resource in visited:
        return {
            'resource': resource,
            'location': str(filepath),
            'doc_summary': None,
            'imports': [],
            'cyclic': True
        }

    # Try to locate and scan the module
    try:
        module_source = interp.import_locate(resource, from_dir=from_dir)
        scan_result = comp.scan(module_source.content)
    except comp._import.ModuleNotFoundError as e:
        return {
            'resource': resource,
            'location': 'NOT FOUND',
            'doc_summary': None,
            'imports': [],
            'error': str(e).split('\n')[0]
        }

    # Mark as visited
    visited.add(resource)

    # Extract doc summary (first doc comment first line)
    doc_summary = None
    docs_key = None
    for k in scan_result.data.keys():
        if k.data == "docs":
            docs_key = k
            break

    if docs_key:
        doc_list = scan_result.data[docs_key]
        if doc_list.data:
            # Get first doc item
            first_doc = next(iter(doc_list.data.values()), None)
            if first_doc:
                for k, v in first_doc.data.items():
                    if k.data == "content":
                        content = v.data
                        # Get first line
                        lines = content.split('\n')
                        doc_summary = lines[0].strip()[:70]
                        if len(lines) > 1 or len(lines[0]) > 70:
                            doc_summary += "..."
                        break

    # Process imports
    imports_list = []
    imports_key = None
    for k in scan_result.data.keys():
        if k.data == "imports":
            imports_key = k
            break

    if imports_key:
        import_data = scan_result.data[imports_key]
        if import_data.data:
            for imp_item in import_data.data.values():
                # Extract import fields
                import_name = None
                import_source = None
                import_compiler = None

                for k, v in imp_item.data.items():
                    if k.data == "name":
                        import_name = v.data
                    elif k.data == "source":
                        import_source = v.data
                    elif k.data == "compiler":
                        import_compiler = v.data

                if import_name and import_source:
                    # Recursively build tree for imported module
                    # Use module_source.anchor as from_dir for the import
                    try:
                        # Try to locate the imported module
                        imported_source = interp.import_locate(import_source, from_dir=module_source.anchor)

                        # Build subtree
                        import_tree = build_dependency_tree(
                            imported_source.location,
                            interp,
                            visited,
                            depth + 1
                        )
                        imports_list.append((import_name, import_tree))
                    except comp._import.ModuleNotFoundError as e:
                        # Import not found
                        imports_list.append((import_name, {
                            'resource': import_source,
                            'location': 'NOT FOUND',
                            'doc_summary': None,
                            'imports': [],
                            'error': f"Module '{import_source}' not found"
                        }))

    return {
        'resource': resource,
        'location': module_source.location,
        'doc_summary': doc_summary,
        'imports': imports_list,
        'cyclic': False
    }


def display_dependency_tree(tree, indent=0, is_last=True, prefix=""):
    """Display a dependency tree in a nice format.

    Args:
        tree: Tree dict from build_dependency_tree
        indent: Current indentation level
        is_last: Whether this is the last item in parent's children
        prefix: Prefix for the current line (tree drawing characters)
    """
    # Prepare the tree characters (ASCII-safe for Windows)
    if indent == 0:
        connector = ""
        new_prefix = ""
    else:
        connector = "`-- " if is_last else "|-- "
        new_prefix = prefix + ("    " if is_last else "|   ")

    # Build the main line
    parts = []

    # Resource/location
    if tree.get('error'):
        parts.append(f"{tree['resource']} (NOT FOUND)")
    elif tree.get('cyclic'):
        parts.append(f"{tree['resource']} (CYCLIC)")
    else:
        parts.append(tree['resource'])

    # Location (if different from resource)
    if tree.get('location') and tree['location'] != 'NOT FOUND':
        # Show relative path for brevity
        location = pathlib.Path(tree['location'])
        try:
            rel_loc = location.relative_to(pathlib.Path.cwd())
            parts.append(f"[{rel_loc}]")
        except ValueError:
            parts.append(f"[{location}]")

    # Doc summary
    if tree.get('doc_summary'):
        parts.append(f'"{tree["doc_summary"]}"')

    # Print the line
    print(f"{prefix}{connector}{' '.join(parts)}")

    # Display error if present
    if tree.get('error') and indent > 0:
        error_prefix = new_prefix + "    "
        print(f"{error_prefix}Error: {tree['error']}")

    # Don't recurse if cyclic or error
    if tree.get('cyclic') or tree.get('error'):
        return

    # Display imports
    imports = tree.get('imports', [])
    for i, (import_name, import_tree) in enumerate(imports):
        is_last_import = (i == len(imports) - 1)

        # Print import name (ASCII-safe)
        import_connector = "`-- " if is_last_import else "|-- "
        print(f"{new_prefix}{import_connector}{import_name}:")

        # Display imported module tree
        import_prefix = new_prefix + ("    " if is_last_import else "|   ")
        display_dependency_tree(import_tree, indent + 2, True, import_prefix)


def show_dependency_tree(filepath):
    """Show import dependency tree for a module.

    Args:
        filepath: Path to the module file to analyze
    """
    # Create interpreter for caching
    interp = comp.Interp()

    # Build the tree
    tree = build_dependency_tree(filepath, interp)

    # Display the tree
    print("Module Dependency Tree:")
    print()
    display_dependency_tree(tree)


def show_namespace(filepath_or_source, is_text=False):
    """Show the finalized namespace for a module.

    Args:
        filepath_or_source: Path to the module file or source text
        is_text: If True, treat first arg as source text instead of filepath
    """
    try:
        if is_text:
            # Create module directly from source text
            module = comp.Module.from_source(filepath_or_source)
            module.load_definitions()
            module.finalize()
            print(f"Namespace for: <text>")
            print()
        else:
            # Create interpreter to use the import system
            interp = comp.Interp()

            # Convert filepath to absolute path
            filepath = pathlib.Path(filepath_or_source)
            if not filepath.is_absolute():
                filepath = pathlib.Path.cwd() / filepath

            # Determine resource identifier and from_dir
            from_dir = filepath.parent
            resource = f"./{filepath.stem}"

            # Locate the module source
            module_source = interp.import_locate(resource, from_dir=from_dir)

            # Create module and load definitions
            module = comp.Module(module_source)
            module.load_definitions()

            # Finalize to build namespace (for now without imports)
            # TODO: In future, load and finalize with imports
            module.finalize()

            print(f"Namespace for: {module_source.location}")
            print()

        # Collect all namespace entries grouped by lookup name
        entries = []
        for lookup_name, (priority, value) in module.namespace.items():
            entries.append((lookup_name, priority, value))

        # Sort by lookup name
        entries.sort(key=lambda x: x[0])

        # Display each entry
        for lookup_name, priority, value in entries:
            # Determine the qualified name and module info
            qualified_name = lookup_name
            module_info = ""
            value_preview = ""

            # Handle different value types
            if isinstance(value, comp.Ambiguous):
                # Multiple conflicting definitions
                modules = set()
                for qname in value.qualified_names:
                    # Extract module info from definitions if available
                    if qname in module.definitions:
                        # It's from this module
                        pass
                    else:
                        modules.add("imported")

                module_str = f" from modules {', '.join(modules)}" if modules else ""
                value_preview = f"{len(value.qualified_names)} values{module_str} ({', '.join(value.qualified_names[:3])}{'...' if len(value.qualified_names) > 3 else ''})"

            elif isinstance(value, comp.OverloadSet):
                # Multiple overloaded callables
                count = len(value.callables)
                names = []
                for callable_val in value.callables[:3]:
                    if hasattr(callable_val.data, 'qualified'):
                        names.append(callable_val.data.qualified)
                names_str = ', '.join(names)
                if count > 3:
                    names_str += '...'
                value_preview = f"{count} overloads ({names_str})"

            else:
                # Single value
                # Determine qualified name from the value
                if hasattr(value.data, 'qualified'):
                    qualified_name = value.data.qualified

                    # Check if it's from a different module (has import prefix in lookup_name)
                    parts = lookup_name.split('.')
                    if len(parts) > 1:
                        # Could be an import prefix
                        # Check if the first part matches any qualified name parts
                        qname_parts = qualified_name.split('.')
                        if parts[0] not in qname_parts:
                            # First part is likely an import prefix
                            module_info = f" (from {parts[0]})"

                # Get value preview (first 40 chars)
                try:
                    # Use format() for all values
                    full_format = value.format()
                    if len(full_format) > 40:
                        value_preview = full_format[:40] + "..."
                    else:
                        value_preview = full_format
                except Exception:
                    value_preview = str(value.data)[:40]

            # Format the output line
            # Determine if we should show qualified name in brackets
            show_qualified = (qualified_name != lookup_name and
                            hasattr(value, 'data') and
                            hasattr(value.data, 'qualified'))

            if module_info:
                # Imported value
                qname_part = f"[{qualified_name}]" if show_qualified else ""
                print(f"{lookup_name:30s} {qname_part:20s} {value_preview}")
            elif show_qualified:
                # Local value with different qualified name
                print(f"{lookup_name:30s} [{qualified_name}]{' ' * max(0, 20 - len(qualified_name) - 2)} {value_preview}")
            else:
                # Simple local value
                print(f"{lookup_name:30s} {' ' * 20} {value_preview}")

    except comp._import.ModuleNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading module: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


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
    parser.add_argument("--tree", action="store_true",
        help="Show import dependency tree with module documentation")
    parser.add_argument("--namespace", action="store_true",
        help="Show the module's finalized namespace with all definitions")
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
        if any([args.cop, args.resolve, args.code, args.eval, args.trace, args.tree]):
            parser.error("--scan cannot be combined with other output modes")
        if args.text:
            parser.error("--scan requires a file path, not --text")
        if args.lark:
            # Show lark tree with scan grammar (still needs source text)
            parse_source(source, use_scanner=True, show_positions=args.pos)
        else:
            # Perform module scanning using ModuleSource
            # Pass the original args.source (file path) not the loaded source text
            scan_module(args.source)
        return

    # Handle --tree mode separately (it's its own output mode)
    if args.tree:
        if any([args.cop, args.resolve, args.code, args.eval, args.trace, args.scan, args.namespace]):
            parser.error("--tree cannot be combined with other output modes")
        if args.text:
            parser.error("--tree requires a file path, not --text")
        # Show dependency tree
        show_dependency_tree(args.source)
        return

    # Handle --namespace mode separately (it's its own output mode)
    if args.namespace:
        if any([args.cop, args.resolve, args.code, args.eval, args.trace, args.scan, args.tree]):
            parser.error("--namespace cannot be combined with other output modes")
        # Show namespace
        show_namespace(args.source if not args.text else source, is_text=args.text)
        return

    # Check if any output mode was specified
    if not any([args.lark, args.cop, args.resolve, args.code, args.eval, args.trace]):
        parser.error("No output mode specified. Use --lark, --cop, --resolve, --code, --eval, --trace, --scan, --tree, or --namespace")

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
