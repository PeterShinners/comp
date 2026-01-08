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


def prettyscan(module):
    """Scan a module and display metadata using the interpreter."""
    scan = module.scan()
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

    # Print this module
    scan = module.scan()
    docs = scan.to_python("docs") or []
    doc = docs[0].get("content", "").split("\n")[0][:50] if docs else ""
    print(f'{prefix}{module.source.resource} "{doc}"' if doc else f"{prefix}{module.source.resource}")

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
            argv = ['examples/tree.comp', '--imports']
    except ImportError:
        pass

    args = parser.parse_args(argv)

    interp = comp.Interp()
    if args.text:
        mod = interp.module_from_text(args.source)
    else:
        mod = interp.module(args.source, anchor=os.getcwd())

    if args.larkscan or args.larkcomp:
        parser = comp._parse.lark_parser("scan" if args.larkscan else "comp")
        tree = parser.parse(mod.source.content)
        prettylark(tree, show_positions=args.pos)
        return

    if args.scan:
        prettyscan(mod)
        return

    if args.imports:
        prettyimports(mod)
        return

    if args.cop or args.unparse:
        # The parse tree is normally not exposed directly like this, instead
        # it gets divvied up into a series of Definitions for the module.
        parser = comp.lark_parser("comp")
        lark_tree = parser.parse(mod.source.content)
        cop_tree = comp._parse.lark_to_cop(lark_tree)
        namespace = None
        if args.resolve:
            # Build namespace and resolve identifiers
            defs = mod.definitions()
            namespace = mod.namespace()
            # Resolve identifiers in the COP tree
            cop_tree = comp.cop_resolve(cop_tree, namespace)

            # If we're also folding, fold definitions with dependency tracking
            if args.fold:
                comp.fold_definitions(defs, namespace)
        if args.fold:
            # Pass namespace for reference folding if available
            cop_tree = comp.cop_fold(cop_tree, namespace)
        if args.cop:
            prettycop(cop_tree, show_pos=args.pos)
        elif args.unparse:
            source_text = comp.cop_unparse(cop_tree)
            print(source_text)
        return

    if args.definitions:
        defs = mod.definitions()
        for name, definition in sorted(defs.items()):
            value = comp.cop_unparse(definition.original_cop)
            if len(value) > 40:
                value = value[:37] + "..."
            shape_name = definition.shape.qualified #if hasattr(definition.shape, "qualified") else str(definition.shape)
            print(f"{name:16}  ({shape_name}) {value}")
        return

    # Handle --namespace mode separately (it's its own output mode)
    if args.namespace:
        ns = mod.namespace()
        prettynamespace(ns)
        return

    if args.code or args.eval or args.trace:
        # Build instruction code for each definition
        defs = mod.definitions()
        namespace = mod.namespace()
        
        # Optional: fold constants before code generation
        if args.fold:
            comp.fold_definitions(defs, namespace)
        
        # Pass 1: Generate code for all definitions
        for name, definition in defs.items():
            try:
                # Ensure the definition is resolved
                if not definition.resolved_cop:
                    definition.resolved_cop = comp.cop_resolve(definition.original_cop, namespace)
                
                # Apply constant folding if requested
                if args.fold:
                    definition.resolved_cop = comp.cop_fold(definition.resolved_cop, namespace)
                
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
            return
        
        if args.eval or args.trace:
            # Pass 2: Execute definitions in order
            # Build environment with all definition values
            env = {}
            
            if args.trace:
                # Create tracing frame subclass
                class TracingFrame(comp.ExecutionFrame):
                    def __init__(self, env=None, interp=None, depth=0):
                        super().__init__(env, interp)
                        self.depth = depth
                    
                    def on_step(self, idx, instr, result):
                        indent = "  " * self.depth
                        result_str = result.format() if result else "(none)"
                        print(f"{indent}{instr.format(idx)}  ->  {result_str}")
                    
                    def _make_child_frame(self, env):
                        return TracingFrame(env=env, interp=self.interp, depth=self.depth + 1)
                
                # Execute with tracing
                for name, definition in defs.items():
                    if definition.instructions:
                        print(f"\n-- {name} --")
                        frame = TracingFrame(env, interp=interp, depth=0)
                        result = frame.run(definition.instructions)
                        env[name] = result
            else:
                # Normal execution
                for name, definition in defs.items():
                    if definition.instructions:
                        result = interp.execute(definition.instructions, env)
                        env[name] = result
            
            # Print final values
            print("\nResults:")
            print("=" * 60)
            for name, definition in sorted(defs.items()):
                if name in env:
                    value = env[name]
                    print(f"{name} = {value.format()}")
            return

    # Check if any output mode was specified
    if not any([args.larkcomp, args.larkscan, args.cop, args.resolve, args.code, args.eval, args.trace, args.definitions, args.scan]):
        parser.error("No output mode specified. Use --larkcomp, --larkscan, --cop, --resolve, --code, --eval, --trace, --scan, --imports, --definitions, or --namespace")


if __name__ == "__main__":
    main()
