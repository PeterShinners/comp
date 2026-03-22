#!/usr/bin/env python3
"""Comp CLI - Command-line interface for the Comp language."""

import argparse
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


def prettymodule(module):
    """Scan a module and display metadata using the interpreter."""
    # Display package metadata if present
    package_meta = module.package()
    if package_meta:
        print("Package:")
        for key, value in package_meta.items():
            print(f"  {key:10s}: {value.format():20s} ({value.shape.qualified})")
        print()

    statements = module.statements()

    # Display statements with their bodies
    if statements:
        print("Module Statements:")
        for stmt in statements:
            operator = stmt.get('operator', '?')
            name = stmt.get('name', '?')
            body = stmt.get('body', '')
            pos = stmt.get('pos', ())
            content_hash = stmt.get('hash', '')

            # Format position - show full range (start and end)
            pos_str = ""
            if len(pos) >= 4:
                pos_str = f" @ {pos[0]}:{pos[1]}-{pos[2]}:{pos[3]}"
            elif len(pos) >= 2:
                pos_str = f" @ {pos[0]}:{pos[1]}"

            # Format body - show preview for long or multi-line bodies
            body_preview = body.strip()
            lines = body_preview.split('\n')

            # If multi-line, show first line with ellipsis
            if len(lines) > 1:
                first_line = lines[0].strip()
                if len(first_line) > 50:
                    body_preview = first_line[:47] + "..."
                else:
                    body_preview = first_line + " ..."
            # If single line but too long, truncate
            elif len(body_preview) > 50:
                body_preview = body_preview[:47] + "..."

            # Format hash - show abbreviated version
            hash_str = f" #{content_hash[:8]}" if content_hash else ""

            # Display the statement
            print(f"  !{operator} {name} {body_preview}{pos_str}{hash_str}")
        print()

    # Display comment summary
    scan = module.scan()
    try:
        docs_val = scan.field('docs')
        if docs_val.data:
            print("Comments:")
            for item in docs_val.data.values():
                content = item.field('content').data
                try:
                    comment_type = item.field('type').data
                except (KeyError, AttributeError):
                    comment_type = "unknown"
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
                print(f"  [{comment_type}] {preview!r}{pos_str}")
            print()
    except (KeyError, AttributeError) as e:
        print(f"Error reading docs: {e}")
        pass


def prettyimports(module, visited=None, prefix=""):
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

    # Print this module with its module-level comment
    doc = module.comment(None)
    # Show first line of comment, max 60 chars
    if doc:
        doc_preview = doc.split("\n")[0][:60]
        if len(doc) > 60 or "\n" in doc:
            doc_preview += "..."
        print(f'{prefix}{module.source.resource} "{doc_preview}"')
    else:
        print(f"{prefix}{module.source.resource}")

    visited[module.source.location] = module.source.resource

    # Process imports - now using the enriched imports dictionary
    module_imports = module.imports()
    for i, (name, import_info) in enumerate(module_imports.items()):
        imported_module = import_info["module"]
        import_error = import_info["error"]
        import_source = import_info["source"]

        is_last = (i == len(module_imports) - 1)
        connector = "└── " if is_last else "├── "
        new_prefix = prefix + ("    " if is_last else "│   ")

        if imported_module:
            print(f"{prefix}{connector}{name}:")
            prettyimports(imported_module, visited, new_prefix)
        elif import_error:
            print(f"{prefix}{connector}{name}: {import_source} (ERROR: {import_error})")
        else:
            print(f"{prefix}{connector}{name}: {import_source} (NOT FOUND)")


def prettynamespace(namespace):
    """Show the finalized namespace for a module."""
    for name, defset in sorted(namespace.items()):
        if all(d.module_id == "system#0000" for d in defset.entries):
            continue
        defs = [f"{d.module_id}:{d.qualified}" for d in defset.entries]
        if len(defset.entries) > 1:
            defs.insert(0, f"(x{len(defset.entries)})")
        defs = " ".join(defs)
        print(f"{name:18} {defs}")


def prettylark_statements(module, show_positions=False):
    """Parse each statement and show its Lark parse tree."""
    statements = module.statements()

    # Map operator to parser entry point
    entry_points = {
        "import": "start_import",
        "package": "start_package",
        "shape": "start_shape",
        "mod": "start_mod",
        "func": "start_func",
        "pure": "start_func",  # pure uses same entry point as func
        "startup": "start_startup",
        "tag": "start_tag",
    }

    for stmt in statements:
        operator = stmt.get("operator", "?")
        name = stmt.get("name", "?")
        body = stmt.get("body", "")
        pos = stmt.get("pos", ())

        # Format position
        pos_str = ""
        if len(pos) >= 4:
            pos_str = f" @ {pos[0]}:{pos[1]}-{pos[2]}:{pos[3]}"

        print(f"!{operator} {name}{pos_str}")

        # Check if we have a parser for this operator
        entry_point = entry_points.get(operator)
        if not entry_point:
            print(f"  (no parser entry point for !{operator})")
            print()
            continue

        # Try to parse the body
        line = pos[0] if pos else 0
        try:
            tree = comp.lark_parse(body, "comp", rule=entry_point, line_offset=line)
            prettylark(tree, indent=1, show_positions=show_positions)
        except Exception as e:
            print(f"  Parse error: {e}")
        print()


def format_instruction(idx, instr, indent=0):
    """Format a single instruction for display using SSA style."""
    ind = "    " * indent

    # Use the instruction's format method
    result = ind + instr.format(idx)

    # If this is a BuildBlock, show nested body instructions
    if hasattr(instr, 'body_instructions') and instr.body_instructions:
        for i, body_instr in enumerate(instr.body_instructions):
            result += "\n" + format_instruction(i, body_instr, indent + 1)

    # If this is a DispatchOn, show each branch's pattern and result instructions
    if hasattr(instr, 'branches') and instr.branches:
        for b, (pattern_instrs, result_instrs) in enumerate(instr.branches):
            branch_ind = "    " * (indent + 1)
            result += "\n" + branch_ind + f"branch {b}:"
            pat_ind = "    " * (indent + 2)
            result += "\n" + pat_ind + "pattern:"
            for i, pi in enumerate(pattern_instrs):
                result += "\n" + format_instruction(i, pi, indent + 3)
            result += "\n" + pat_ind + "result:"
            for i, ri in enumerate(result_instrs):
                result += "\n" + format_instruction(i, ri, indent + 3)

    return result


def _format_code_error(e, label="Build failure"):
    """Format a CodeError with source location context.

    Extracts position from the COP node attached to the error and shows
    the relevant source line with a caret underline, similar to how
    runtime failures are displayed.

    Args:
        e: (CodeError) The error to format
        label: (str) Prefix label (e.g. 'Build failure', 'Failure')

    Returns:
        (str) Formatted error string for stderr output
    """
    msg = e.message if hasattr(e, "message") else str(e)
    parts = [f"{label};"]

    # Try to extract position from cop_node or direct row/col attributes
    cop = getattr(e, "cop_node", None)
    row, col, end_col = None, None, None
    # Prefer direct position attributes (set by callout pipeline)
    row = getattr(e, "row", None)
    col = getattr(e, "col", None)
    end_col = getattr(e, "end_col", None)
    # Fall back to cop_node extraction
    if row is None and cop is not None:
        try:
            pos = cop.field("pos")
            if pos is not None:
                row = pos.to_python(0)
                col = pos.to_python(1)
                end_col = pos.to_python(3)
        except (KeyError, AttributeError, IndexError):
            pass

    # Try to get source file and content from attached module
    source_file = None
    source_lines = None
    mod = getattr(e, "module", None)
    defn_name = getattr(e, "definition_name", None)
    if mod is not None:
        try:
            source_file = mod.source.resource
            source_lines = mod.source.content.splitlines()
        except (AttributeError, TypeError):
            pass

    if msg:
        parts.append(msg)

    if row is not None and col is not None:
        loc_parts = []
        if defn_name:
            loc_parts.append(defn_name)
        if source_file:
            loc_parts.append(f"{source_file}:{row}:{col}")
        else:
            loc_parts.append(f"line {row}, col {col}")
        parts.append(f"  --> {', '.join(loc_parts)}")

        if source_lines and 1 <= row <= len(source_lines):
            src_line = source_lines[row - 1].rstrip("\n")
            parts.append(f"   | {src_line}")
            span = max(1, end_col - col) if end_col and end_col > col else 1
            caret = " " * (col - 1) + "^" * span
            parts.append(f"   | {caret}")
    elif source_file or defn_name:
        loc_parts = []
        if source_file:
            loc_parts.append(source_file)
        if defn_name:
            loc_parts.append(f"in {defn_name}")
        parts.append(f"  --> {', '.join(loc_parts)}")

    return "\n".join(parts)


def _format_failure_cli(fail_val, source_file=None, source_lines=None, depth=0):
    """Format a failure value for CLI error display.

    Args:
        fail_val: (comp.Value) Failure struct conforming to shape_failure
        source_file: (str | None) Source file path for context
        source_lines: (list[str] | None) Pre-read source lines (avoids re-reading)
        depth: (int) Recursion depth for cause chain indentation

    Returns:
        (str) Formatted error string for stderr output
    """
    if not isinstance(fail_val.data, dict):
        return f"Failure; {fail_val.format()}"

    indent = "  " * depth

    # Extract fields
    nil = comp.Value.from_python(comp.tag_nil)
    fail_key = comp.Value.from_python("fail")
    msg_key = comp.Value.from_python("message")
    cause_key = comp.Value.from_python("cause")
    cop_key = comp.Value.from_python("cop")
    frame_key = comp.Value.from_python("frame")

    tag_val = fail_val.data.get(fail_key, nil)
    msg_val = fail_val.data.get(msg_key, nil)
    cause_val = fail_val.data.get(cause_key, nil)
    cop_val = fail_val.data.get(cop_key, nil)
    frame_val = fail_val.data.get(frame_key, nil)

    # Tag string (without # prefix)
    if isinstance(tag_val.data, comp.Tag):
        tag_str = tag_val.data.qualified
    else:
        tag_str = tag_val.format()

    # Message string
    msg_str = msg_val.data if isinstance(msg_val.data, str) else ""

    # Build first line: "Failure; tag message"
    if msg_str:
        first_line = f"{indent}Failure; {tag_str} {msg_str}"
    else:
        first_line = f"{indent}Failure; {tag_str}"

    parts = [first_line]

    # Position from cop struct — extract row/col and show source line
    if isinstance(cop_val.data, dict):
        pos_key = comp.Value.from_python("pos")
        pos_val = cop_val.data.get(pos_key)
        if pos_val is not None and isinstance(pos_val.data, dict):
            try:
                row = pos_val.to_python(0)
                col = pos_val.to_python(1)
                end_col = pos_val.to_python(3)

                # Location line — frame context before file:line
                loc_parts = []
                if isinstance(frame_val.data, str):
                    loc_parts.append(frame_val.data)
                if source_file:
                    loc_parts.append(f"{source_file}:{row}:{col}")
                else:
                    loc_parts.append(f"line {row}, col {col}")
                parts.append(f"{indent}  --> {', '.join(loc_parts)}")

                # Source line + caret (lazy-read if needed)
                if source_lines is None and source_file:
                    try:
                        with open(source_file, encoding="utf-8") as f:
                            source_lines = f.readlines()
                    except OSError:
                        source_lines = []

                if source_lines and 1 <= row <= len(source_lines):
                    src_line = source_lines[row - 1].rstrip("\n")
                    parts.append(f"{indent}   | {src_line}")
                    # Caret: col is 1-based; underline the token span
                    span = max(1, end_col - col) if end_col > col else 1
                    caret = " " * (col - 1) + "^" * span
                    parts.append(f"{indent}   | {caret}")
            except Exception:
                pass

    # Cause chain
    if isinstance(cause_val.data, dict):
        parts.append(_format_failure_cli(
            cause_val,
            source_file=source_file,
            source_lines=source_lines,
            depth=depth + 1,
        ))

    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(
        prog="comp",
        description="Comp language command-line interface")
    parser.add_argument("source", help="Comp source to parse")
    parser.add_argument("--text", metavar="ENTRY",
                        help="Parse source as direct text using grammar entry point (shape, func, statement, expression, module)")
    parser.add_argument("--pos", action="store_true", help="Show line:column positions for nodes")
    parser.add_argument("--pure", action="store_true", help="Evaluate pure function invokes at compile time")
    parser.add_argument("--raw", action="store_true", help="Show unresolved/unfolded cop (skip resolve and fold passes)")

    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--scan", action="store_true", help="Show scan Lark parse tree")
    modes.add_argument("--lark", action="store_true", help="Show Lark parse tree for each parseable statement")
    modes.add_argument("--cop", action="store_true", help="Report parsed cop structure")
    modes.add_argument("--unparse", action="store_true", help="Convert cop nodes back to source")
    modes.add_argument("--code", action="store_true", help="Build and show instruction code")
    modes.add_argument("--eval", action="store_true", help="Evaluate the expression and show the result")
    modes.add_argument("--trace", action="store_true", help="Show each instruction as it executes with its result")
    modes.add_argument("--module", action="store_true", help="Show module metadata (definitions, comments)")
    modes.add_argument("--imports", action="store_true", help="Show import dependency tree with module documentation")
    modes.add_argument("--namespace", action="store_true", help="Show the module namespace with all definitions")
    modes.add_argument("--definitions", action="store_true", help="Show list of module definitions")
    modes.add_argument("--describe", metavar="NAME", help="Describe a named definition as a markdown report (supports overloads)")
    modes.add_argument("--callouts", action="store_true", help="Run module validation pipeline and print callouts")

    parser.add_argument("--startup", metavar="NAME", default="main",
                        help="Entry point to run (default: main)")

    argv = None
    try:
        import debugpy
        if debugpy.is_client_connected():
            print("Debugger attached.")
            argv = ['minimal.comp', '--callouts', '--pure']
    except ImportError:
        pass

    args = parser.parse_args(argv)

    # Map user-friendly entry point names to grammar start rules
    entry_point_map = {
        "shape": "start_shape",
        "func": "start_func",
        "startup": "start_startup",
        "statement": "statement_body",
        "expression": "expression",
        "module": None,  # Use module parsing (default)
    }

    interp = comp.Interp()

    # --text mode: parse source argument as direct text
    if args.text:
        if args.text not in entry_point_map:
            print(f"Error: Unknown entry point '{args.text}'")
            print(f"Valid entry points: {', '.join(entry_point_map.keys())}")
            return 1

        entry_point = entry_point_map[args.text]

        if args.lark:
            if entry_point is None:
                mod = interp.module_from_text(args.source)
                prettylark_statements(mod, show_positions=args.pos)
            else:
                try:
                    tree = comp._parse.lark_parse(args.source, "comp", rule=entry_point)
                    prettylark(tree, show_positions=args.pos)
                except comp.ParseError as e:
                    print(e.message, file=sys.stderr)
                    return 1
            return

        elif (args.cop or args.unparse) and entry_point is not None:
            try:
                tree = comp._parse.lark_parse(args.source, "comp", rule=entry_point)
                cop = comp._parse.lark_to_cop(tree)

                if not args.raw:
                    sys_ns = comp.get_internal_module("system").namespace()
                    cop = comp.cop_resolve_names(cop, sys_ns)
                    cop = comp.coptimize(cop, True, sys_ns)

                if args.cop:
                    prettycop(cop, show_pos=args.pos)
                elif args.unparse:
                    print(comp.cop_unparse(cop))
                return
            except (comp.ParseError, comp.CodeError) as e:
                if isinstance(e, comp.CodeError):
                    print(_format_code_error(e, "Failure"), file=sys.stderr)
                else:
                    print(e.message if hasattr(e, "message") else str(e), file=sys.stderr)
                return 1

        elif args.code and entry_point is not None:
            try:
                tree = comp._parse.lark_parse(args.source, "comp", rule=entry_point)
                cop = comp._parse.lark_to_cop(tree)

                sys_ns = comp.get_internal_module("system").namespace()
                cop = comp.cop_resolve_names(cop, sys_ns)
                cop = comp.coptimize(cop, True, sys_ns)

                instructions = comp.generate_code_for_definition(cop, namespace=sys_ns)
                print(f"Source: {comp.cop_unparse(cop)}")
                print("-" * 40)
                for i, instr in enumerate(instructions):
                    print(format_instruction(i, instr))
                return
            except (comp.ParseError, comp.CodeError) as e:
                if isinstance(e, comp.CodeError):
                    print(_format_code_error(e, "Failure"), file=sys.stderr)
                else:
                    print(e.message if hasattr(e, "message") else str(e), file=sys.stderr)
                return 1

        elif (args.eval or args.trace) and entry_point is not None:
            try:
                tree = comp._parse.lark_parse(args.source, "comp", rule=entry_point)
                cop = comp._parse.lark_to_cop(tree)

                sys_mod = comp.get_internal_module("system")
                sys_ns = sys_mod.namespace()
                cop = comp.cop_resolve_names(cop, sys_ns)
                cop = comp.coptimize(cop, True, sys_ns)

                instructions = comp.generate_code_for_definition(cop, namespace=sys_ns)
                env = {}

                if args.trace:
                    class TracingFrame(comp.ExecutionFrame):
                        def __init__(self, env=None, interp=None, module=None, depth=0, context=None):
                            super().__init__(env, interp, module, context=context)
                            self.depth = depth
                        def on_step(self, idx, instr, result):
                            indent = "  " * self.depth
                            result_str = result.format() if result else "(none)"
                            print(f"{indent}{instr.format(idx)}  ->  {result_str}")
                        def _make_child_frame(self, env, module=None):
                            return TracingFrame(env=env, interp=self.interp,
                                               module=module or self.module, depth=self.depth + 1,
                                               context=dict(self.context))
                    frame = TracingFrame(env, interp=interp, module=None, depth=0)
                else:
                    frame = comp.ExecutionFrame(env, interp=interp, module=None)

                result = frame.run(instructions)
                if frame.failure is not None:
                    print(_format_failure_cli(frame.failure), file=sys.stderr)
                    sys.exit(1)
                print(result.format())
                return
            except (comp.ParseError, comp.CodeError) as e:
                if isinstance(e, comp.CodeError):
                    print(_format_code_error(e, "Failure"), file=sys.stderr)
                else:
                    print(e.message if hasattr(e, "message") else str(e), file=sys.stderr)
                return 1

        else:
            mod = interp.module_from_text(args.source)
    else:
        mod = interp.module(args.source, anchor=os.getcwd())

    # --- Module-based modes ---

    if args.scan:
        tree = comp._parse.lark_parse(mod.source.content, "scan")
        prettylark(tree, show_positions=args.pos)
        return

    if args.lark:
        prettylark_statements(mod, show_positions=args.pos)
        return

    if args.module:
        prettymodule(mod)
        return

    if args.imports:
        prettyimports(mod)
        return

    if args.cop or args.unparse:
        if args.pure:
            # Full build pipeline needed so imported pure definitions
            # are compiled/executed and available for folding.
            interp.build_instructions()

        defs = mod.definitions()
        if not args.pure:
            interp.build_namespaces()
        namespace = mod.namespace()

        if not args.raw:
            # Resolve + fold all definitions
            for name, definition in defs.items():
                if not definition.resolved_cop:
                    definition.resolved_cop = comp.cop_resolve_names(definition.original_cop, namespace)
                    definition.resolved_cop = comp.coptimize(definition.resolved_cop, True, namespace)

        # Sort definitions by source position
        def get_position(item):
            name, definition = item
            cop = definition.original_cop
            try:
                pos = cop.field("pos").data
                if pos and len(pos) >= 2:
                    return (pos[0], pos[1])
            except (KeyError, AttributeError):
                pass
            return (999999, 0)

        sorted_defs = sorted(defs.items(), key=get_position)

        if args.cop:
            for name, definition in sorted_defs:
                print(f"\n{'='*60}")
                if definition.startup:
                    print(f"!startup {name.split('.', 1)[1]}")
                else:
                    print(f"Definition: {name} ({definition.shape.qualified})")
                print(f"{'='*60}")
                cop = definition.resolved_cop if (not args.raw and definition.resolved_cop) else definition.original_cop
                if cop is None:
                    continue
                prettycop(cop, show_pos=args.pos)

        elif args.unparse:
            for name, definition in sorted_defs:
                cop = definition.resolved_cop if (not args.raw and definition.resolved_cop) else definition.original_cop
                if cop is None:
                    continue
                source_text = comp.cop_unparse(cop)
                print(f"{name} = {source_text}")
        return

    if args.definitions:
        interp.build_namespaces()
        defs = mod.definitions()
        for name, definition in sorted(defs.items()):
            unparse = comp.cop_unparse(definition.original_cop)
            if len(unparse) > 40:
                unparse = unparse[:37] + "..."
            shape_name = definition.shape.qualified
            value = definition.value
            if value is None:
                value = ""
            else:
                value = f"{value.shape.qualified}"
                value = value.format()
            print(f"{name:16}  {f'({shape_name})':8s} {value} {unparse}")
        if mod._deferred_defs:
            if defs:
                print()
            for kind, def_name, def_ref, is_private in mod._deferred_defs:
                private_marker = " (private)" if is_private else ""
                print(f"!{kind} {def_name} -> {def_ref}{private_marker}")
        return

    if args.describe:
        description = comp._describe.describe_name(mod, args.describe)
        report = comp._describe.format_describe_markdown(description)
        print(report)
        return

    if args.namespace:
        interp.build_namespaces()
        ns = mod.namespace()
        prettynamespace(ns)
        return

    if args.callouts:
        callouts = interp.callouts(module=mod, min_severity=comp.WARNING)
        if not callouts:
            print("No callouts.")
            return 0

        has_error = False
        for c in callouts:
            sev = (c.severity or "info").upper()
            msg = c.message or ""
            print(f"{sev}; {msg}")

            if c.primary and c.primary.span:
                s = c.primary.span
                loc_parts = []
                defn_name = getattr(c, "definition_name", None)
                if defn_name:
                    loc_parts.append(f"`{defn_name}`")
                if s.file:
                    loc_parts.append(f"{s.file}:{s.line}:{s.col}")
                else:
                    loc_parts.append(f"line {s.line}, col {s.col}")
                print(f"  --> {', '.join(loc_parts)}")

                # Show source line with caret
                source_lines = None
                if s.file:
                    try:
                        with open(s.file, encoding="utf-8") as f:
                            source_lines = f.readlines()
                    except OSError:
                        pass
                if source_lines and 1 <= s.line <= len(source_lines):
                    src_line = source_lines[s.line - 1].rstrip("\n")
                    print(f"   | {src_line}")
                    span = s.length if s.length > 0 else 1
                    caret = " " * (s.col - 1) + "^" * span
                    print(f"   | {caret}")

            if c.severity == comp.ERROR:
                has_error = True
        return 1 if has_error else 0

    if args.code or args.eval or args.trace:
        # Full build pipeline
        try:
            errors = interp.build_instructions()
            if errors:
                err_mod, err_exc = errors[0]
                err_exc.module = err_mod
                raise err_exc
        except (comp.ParseError, comp.CodeError) as e:
            if isinstance(e, comp.CodeError):
                print(_format_code_error(e, "Build failure"), file=sys.stderr)
            else:
                msg = e.message if hasattr(e, "message") else str(e)
                err_mod = getattr(e, "module", None)
                if err_mod is not None:
                    try:
                        source_file = err_mod.source.resource
                        msg = msg.replace("  --> line ", f"  --> {source_file}:")
                        msg = msg.replace(", col ", ":")
                    except (AttributeError, TypeError):
                        pass
                print(msg, file=sys.stderr)
            return 1

        defs = mod.definitions()
        namespace = mod.namespace()

        if args.code:
            print("Instructions for each definition:")
            print("=" * 60)

            for name, definition in sorted(defs.items()):
                if definition.startup:
                    print(f"\n!startup {name.split('.', 1)[1]}")
                else:
                    print(f"\nDefinition: {name} ({definition.shape.qualified})")
                print(f"Source: {comp.cop_unparse(definition.original_cop)}")
                print("-" * 40)

                if definition.instructions:
                    for i, instr in enumerate(definition.instructions):
                        print(format_instruction(i, instr))
                else:
                    print("  (no instructions)")
            return

        if args.eval or args.trace:
            env = {}

            if args.trace:
                class TracingFrame(comp.ExecutionFrame):
                    def __init__(self, env=None, interp=None, module=None, depth=0, context=None):
                        super().__init__(env, interp, module, context=context)
                        self.depth = depth

                    def on_step(self, idx, instr, result):
                        indent = "  " * self.depth
                        result_str = result.format() if result else "(none)"
                        print(f"{indent}{instr.format(idx)}  ->  {result_str}")

                    def _make_child_frame(self, env, module=None):
                        return TracingFrame(env=env, interp=self.interp, module=module or self.module, depth=self.depth + 1, context=dict(self.context))

            # Definition values already populated by build()
            for name, definition in defs.items():
                if definition.value is not None:
                    env[name] = definition.value

            startup_name = args.startup
            startup_defn, context = mod.prepare_startup(startup_name) if mod is not None else (None, None)
            if startup_defn is not None and startup_defn.value is not None:
                startup_block = startup_defn.value
                if isinstance(startup_block.data, comp.Callable):
                    if args.trace:
                        print(f"\n-- startup {startup_name} --")
                        frame = TracingFrame(env, interp=interp, module=mod, depth=0)
                        try:
                            result = frame.invoke_block(startup_block, context, piped=None)
                        except comp.CompFail as e:
                            print(_format_failure_cli(e.value, source_file=args.source), file=sys.stderr)
                            sys.exit(1)
                        if result is not None:
                            print(result.format())
                    else:
                        startup_frame = comp.ExecutionFrame(env, interp=interp, module=mod)
                        try:
                            result = startup_frame.invoke_block(startup_block, context, piped=None)
                        except comp.CompFail as e:
                            print(_format_failure_cli(e.value, source_file=args.source), file=sys.stderr)
                            sys.exit(1)
                        if result is not None:
                            print(result.format())
            else:
                # No startup found - fall back to printing all definition values
                print("\nResults:")
                print("=" * 60)
                for name, definition in sorted(defs.items()):
                    if name in env:
                        value = env[name]
                        print(f"{name} = {value.format()}")
            return


if __name__ == "__main__":
    main()
