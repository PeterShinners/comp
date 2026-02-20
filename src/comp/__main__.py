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
        value = defset.scalar()
        if value and value.module_id == "system#0000":
            continue
        defs = [f"{d.module_id}:{d.qualified}" for d in defset.definitions]
        if len(defset.definitions) > 1:
            defs.insert(0, f"(x{len(defset.definitions)})")
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
        try:
            parser = comp._parse.lark_parser("comp", start=entry_point)
            tree = parser.parse(body)
            prettylark(tree, indent=1, show_positions=show_positions)
        except Exception as e:
            # Adjust line numbers in error messages to reflect source file positions
            error_line = getattr(e, 'line', None)
            if error_line is not None and len(pos) >= 1:
                # Body starts at pos[0], so error line needs offset
                # Error reports line 1 as first line of body, which is actually pos[0] in source
                actual_line = error_line + (pos[0] - 1)
                error_msg = str(e).replace(f"line {error_line}", f"line {actual_line}")
                print(f"  Parse error: {error_msg}")
            else:
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
    
    return result


def main():
    parser = argparse.ArgumentParser(
        prog="comp",
        description="Comp language command-line interface")
    parser.add_argument("source", help="Comp source to parse")
    parser.add_argument("--text", metavar="ENTRY",
                        help="Parse source as direct text using grammar entry point (shape, func, statement, expression, module)")
    parser.add_argument("--pos", action="store_true", help="Show line:column positions for nodes")
    parser.add_argument("--resolve", action="store_true", help="Resolve cop references")
    parser.add_argument("--fold", action="store_true", help="Fold cop constants")
    parser.add_argument("--pure", action="store_true", help="Evaluate pure function invokes at compile time")

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
    modes.add_argument("--namespace", action="store_true", help="Show the module's finalized namespace with all definitions")
    modes.add_argument("--definitions", action="store_true", help="Show list of module definition")

    argv = None
    try:
        import debugpy
        if debugpy.is_client_connected():
            print("Debugger attached.")
            argv = ['minimal.comp', '--definitions']
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
    if args.text:
        if args.text not in entry_point_map:
            print(f"Error: Unknown entry point '{args.text}'")
            print(f"Valid entry points: {', '.join(entry_point_map.keys())}")
            return 1

        entry_point = entry_point_map[args.text]
        
        # For --text mode with --lark, parse directly with the specified entry point
        if args.lark:
            if entry_point is None:
                # Module entry point - parse as module
                mod = interp.module_from_text(args.source)
                prettylark_statements(mod, show_positions=args.pos)
            else:
                # Direct grammar entry point
                lark_parser = comp._parse.lark_parser("comp", start=entry_point)
                try:
                    tree = lark_parser.parse(args.source)
                    prettylark(tree, show_positions=args.pos)
                except Exception as e:
                    print(f"Parse error: {e}")
                    return 1
            return
        
        # For --cop/--unparse modes with fragment entry points
        elif (args.cop or args.unparse) and entry_point is not None:
            # Parse fragment directly and convert to cop
            lark_parser = comp._parse.lark_parser("comp", start=entry_point)
            try:
                tree = lark_parser.parse(args.source)
                cop = comp._parse.lark_to_cop(tree)

                # Apply optimization/folding if requested
                if args.fold:
                    cop = comp.coptimize(cop, True, None)

                if args.cop:
                    prettycop(cop, show_pos=args.pos)
                elif args.unparse:
                    print(comp.cop_unparse(cop))
                return
            except Exception as e:
                print(f"Parse error: {e}")
                return 1

        # For --code mode with fragment entry points
        elif args.code and entry_point is not None:
            lark_parser = comp._parse.lark_parser("comp", start=entry_point)
            try:
                tree = lark_parser.parse(args.source)
                cop = comp._parse.lark_to_cop(tree)

                sys_ns = comp.get_internal_module("system").namespace()
                cop = comp.coptimize(cop, args.fold, sys_ns)

                instructions = comp.generate_code_for_definition(cop)
                print(f"Source: {comp.cop_unparse(cop)}")
                print("-" * 40)
                for i, instr in enumerate(instructions):
                    print(format_instruction(i, instr))
                return
            except Exception as e:
                print(f"Error: {e}")
                return 1

        # For --eval/--trace mode with fragment entry points
        elif (args.eval or args.trace) and entry_point is not None:
            lark_parser = comp._parse.lark_parser("comp", start=entry_point)
            try:
                tree = lark_parser.parse(args.source)
                cop = comp._parse.lark_to_cop(tree)

                sys_mod = comp.get_internal_module("system")
                sys_ns = sys_mod.namespace()
                cop = comp.coptimize(cop, args.fold, sys_ns)

                instructions = comp.generate_code_for_definition(cop)

                # System definitions are resolved via namespace lookup, not pre-loaded into env,
                # so that LoadVar auto-invoke semantics apply correctly.
                env = {}

                if args.trace:
                    class TracingFrame(comp.ExecutionFrame):
                        def __init__(self, env=None, interp=None, module=None, depth=0):
                            super().__init__(env, interp, module)
                            self.depth = depth
                        def on_step(self, idx, instr, result):
                            indent = "  " * self.depth
                            result_str = result.format() if result else "(none)"
                            print(f"{indent}{instr.format(idx)}  ->  {result_str}")
                        def _make_child_frame(self, env, module=None):
                            return TracingFrame(env=env, interp=self.interp,
                                               module=module or self.module, depth=self.depth + 1)
                    frame = TracingFrame(env, interp=interp, module=None, depth=0)
                    result = frame.run(instructions)
                else:
                    result = interp.execute(instructions, env)

                print(result.format())
                return
            except Exception as e:
                print(f"Error: {e}")
                return 1
        
        # For other modes or module entry point, use module parsing
        else:
            mod = interp.module_from_text(args.source)
    else:
        mod = interp.module(args.source, anchor=os.getcwd())

    if args.scan:
        parser = comp._parse.lark_parser("scan")
        tree = parser.parse(mod.source.content)
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
        # Display COP trees for each definition individually
        # This shows the scanner-based approach: each statement parsed separately
        defs = mod.definitions()

        # Optionally resolve and optimize
        namespace = None
        if args.resolve or args.fold or args.pure:
            namespace = mod.namespace()
            for name, definition in defs.items():
                if not definition.resolved_cop:
                    definition.resolved_cop = comp.coptimize(definition.original_cop, args.fold, namespace)

        if args.pure:
            comp.evaluate_pure_definitions(defs, interp)
            # Re-fold after pure evaluation
            if args.fold:
                for name, definition in defs.items():
                    definition.resolved_cop = comp.coptimize(definition.resolved_cop, True, namespace)

        # Sort definitions by source position (line number)
        def get_position(item):
            name, definition = item
            cop = definition.original_cop
            try:
                pos = cop.field("pos").data
                if pos and len(pos) >= 2:
                    return (pos[0], pos[1])  # (line, column)
            except (KeyError, AttributeError):
                pass
            return (999999, 0)  # Unknown positions go to end

        sorted_defs = sorted(defs.items(), key=get_position)

        if args.cop:
            # Display each definition's COP tree separately
            for name, definition in sorted_defs:
                print(f"\n{'='*60}")
                print(f"Definition: {name} ({definition.shape.qualified})")
                print(f"{'='*60}")
                # Show resolved or original COP
                cop = definition.resolved_cop if (args.resolve or args.fold or args.pure) else definition.original_cop
                prettycop(cop, show_pos=args.pos)

            # Also show !startup main if present
            startup_cop = mod.startup("main") if mod is not None else None
            if startup_cop is not None:
                if args.resolve or args.fold or args.pure:
                    startup_cop = comp.coptimize(startup_cop, args.fold, namespace)
                print(f"\n{'='*60}")
                print(f"!startup main")
                print(f"{'='*60}")
                prettycop(startup_cop, show_pos=args.pos)

        elif args.unparse:
            # Unparse each definition
            for name, definition in sorted_defs:
                cop = definition.resolved_cop if (args.resolve or args.fold or args.pure) else definition.original_cop
                source_text = comp.cop_unparse(cop)
                print(f"{name} = {source_text}")
        return

    if args.definitions:
        defs = mod.definitions()
        for name, definition in sorted(defs.items()):
            unparse = comp.cop_unparse(definition.original_cop)
            if len(unparse) > 40:
                unparse = unparse[:37] + "..."
            shape_name = definition.shape.qualified #if hasattr(definition.shape, "qualified") else str(definition.shape)
            value = definition.value
            if value is None:
                value = ""
            else:
                value = f"{value.shape.qualified}"
                value = value.format()
            print(f"{name:16}  {f'({shape_name})':8s} {value} {unparse}")
        return

    # Handle --namespace mode separately (it's its own output mode)
    if args.namespace:
        ns = mod.namespace()
        prettynamespace(ns)
        return

    if args.code or args.eval or args.trace:
        do_fold = args.fold or args.pure
        
        # Prepare ALL modules in the interp (imports and main module)
        # This is the "do everything up front" approach
        def prepare_module(module):
            """Prepare a single module: resolve COPs, generate instructions, populate values."""
            module_defs = module.definitions()
            module_ns = module.namespace()
            
            # Resolve and optionally fold all definitions
            for name, definition in module_defs.items():
                if not definition.resolved_cop:
                    definition.resolved_cop = comp.coptimize(definition.original_cop, do_fold, module_ns)
            
            # Generate code for all definitions
            for name, definition in module_defs.items():
                if not definition.instructions:
                    try:
                        definition.instructions = comp.generate_code_for_definition(definition.resolved_cop)
                    except Exception as e:
                        print(f"Code generation error for {module.token}:{name}: {e}")
                        raise
            
            # Populate definition values by executing their instructions
            # Process shapes first, then blocks (blocks may reference shapes)
            module_env = {}
            
            # First pass: shapes (shape definitions don't depend on blocks)
            for name, definition in module_defs.items():
                if definition.instructions and definition.value is None:
                    if definition.shape.qualified == "shape":
                        try:
                            result = interp.execute(definition.instructions, module_env, module=module)
                            definition.value = result
                            module_env[name] = result
                        except Exception as e:
                            print(f"Evaluation error for {module.token}:{name}: {e}")
                            raise
            
            # Second pass: everything else (blocks, etc.)
            for name, definition in module_defs.items():
                if definition.instructions and definition.value is None:
                    try:
                        result = interp.execute(definition.instructions, module_env, module=module)
                        definition.value = result
                        module_env[name] = result
                    except Exception as e:
                        print(f"Evaluation error for {module.token}:{name}: {e}")
                        raise
        
        # First prepare all imported modules (dependencies before dependents)
        for token, module in list(interp.module_cache.items()):
            if module is not mod:  # Skip main module for now
                prepare_module(module)
        
        # Now prepare the main module
        defs = mod.definitions()
        namespace = mod.namespace()
        
        # Resolve and optionally fold all definitions
        for name, definition in defs.items():
            if not definition.resolved_cop:
                definition.resolved_cop = comp.coptimize(definition.original_cop, do_fold, namespace)
        
        # Evaluate pure function invokes
        if args.pure:
            comp.evaluate_pure_definitions(defs, interp)
            # Post-fold after pure evaluation (only if --fold specified)
            if args.fold:
                for name, definition in defs.items():
                    definition.resolved_cop = comp.coptimize(definition.resolved_cop, True, namespace)
        
        # Pass 1: Generate code for all definitions
        for name, definition in defs.items():
            try:
                # Generate and store instructions
                definition.instructions = comp.generate_code_for_definition(definition.resolved_cop)
            except Exception as e:
                print(f"Code generation error for {name}: {e}")
                return
        
        if args.code:
            # Display instruction code for each definition
            print("Instructions for each definition:")
            print("=" * 60)

            for name, definition in sorted(defs.items()):
                print(f"\nDefinition: {name} ({definition.shape.qualified})")
                print(f"Source: {comp.cop_unparse(definition.original_cop)}")
                print("-" * 40)

                if definition.instructions:
                    for i, instr in enumerate(definition.instructions):
                        print(format_instruction(i, instr))
                else:
                    print("  (no instructions)")

            # Also show !startup main if present
            startup_cop = mod.startup("main") if mod is not None else None
            if startup_cop is not None:
                resolved_startup = comp.coptimize(startup_cop, do_fold, namespace)
                startup_instructions = comp.generate_code_for_definition(resolved_startup)
                print(f"\n!startup main")
                print(f"Source: {comp.cop_unparse(startup_cop)}")
                print("-" * 40)
                for i, instr in enumerate(startup_instructions):
                    print(format_instruction(i, instr))
            return
        
        if args.eval or args.trace:
            # Pass 2: Execute definitions in order
            # Build environment with all definition values
            env = {}

            if args.trace:
                # Create tracing frame subclass (used only for startup execution)
                class TracingFrame(comp.ExecutionFrame):
                    def __init__(self, env=None, interp=None, module=None, depth=0):
                        super().__init__(env, interp, module)
                        self.depth = depth

                    def on_step(self, idx, instr, result):
                        indent = "  " * self.depth
                        result_str = result.format() if result else "(none)"
                        print(f"{indent}{instr.format(idx)}  ->  {result_str}")

                    def _make_child_frame(self, env, module=None):
                        return TracingFrame(env=env, interp=self.interp, module=module or self.module, depth=self.depth + 1)

            # Execute definitions silently (definitions are setup, not the traced program)
            for name, definition in defs.items():
                if definition.instructions:
                    result = interp.execute(definition.instructions, env, module=mod)
                    definition.value = result
                    env[name] = result

            # Look for !startup main and run it if present
            startup_cop = mod.startup("main") if mod is not None else None
            if startup_cop is not None:
                resolved_startup = comp.coptimize(startup_cop, do_fold, namespace)
                startup_instructions = comp.generate_code_for_definition(resolved_startup)

                if args.trace:
                    print(f"\n-- startup main --")
                    frame = TracingFrame(env, interp=interp, module=mod, depth=0)
                    startup_block = frame.run(startup_instructions)
                    # function.define returns the Block; invoke it explicitly
                    if startup_block is not None and isinstance(startup_block.data, comp.Block):
                        frame.invoke_block(startup_block, comp.Value.from_python({}), piped=None)
                else:
                    startup_block = interp.execute(startup_instructions, env, module=mod)
                    # function.define returns the Block; invoke it explicitly
                    if startup_block is not None and isinstance(startup_block.data, comp.Block):
                        startup_frame = comp.ExecutionFrame(env, interp=interp, module=mod)
                        startup_frame.invoke_block(startup_block, comp.Value.from_python({}), piped=None)
            else:
                # No startup found - fall back to printing all definition values
                print("\nResults:")
                print("=" * 60)
                for name, definition in sorted(defs.items()):
                    if name in env:
                        value = env[name]
                        print(f"{name} = {value.format()}")
            return

    # Check if any output mode was specified
    if not any([args.parse, args.scan, args.cop, args.resolve, args.code, args.eval, args.trace, args.definitions, args.module]):
        parser.error("No output mode specified. Use --parse, --scan, --cop, --resolve, --code, --eval, --trace, --module, --imports, --definitions, or --namespace")


if __name__ == "__main__":
    main()
