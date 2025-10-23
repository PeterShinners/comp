"""Command-line interface for Comp language.

🎉 Milestone Release 0.1.0 - A working Comp interpreter!

This CLI allows you to run .comp programs from the command line.
Every program needs a !main entry point that serves as the program start.
"""

import io
import sys
from pathlib import Path

import comp


def show_dependencies(filepath_str):
    """Display dependency tree for a Comp module.

    Args:
        filepath_str: Path to the .comp file
    """
    filepath = Path(filepath_str)

    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    try:
        # Read and parse the module
        code = filepath.read_text(encoding="utf-8")
        ast_module = comp.parse_module(code, filename=str(filepath))

        # Create engine and evaluate module
        engine = comp.Engine()
        module_result = engine.run(ast_module)

        # Check for errors
        if isinstance(module_result, comp.Value) and module_result.is_fail:
            print(f"Error loading module {filepath}:", file=sys.stderr)
            print(f"  {module_result}", file=sys.stderr)
            sys.exit(1)

        if not isinstance(module_result, comp.Module):
            print(f"Error: Expected Module entity, got {type(module_result)}", file=sys.stderr)
            sys.exit(1)

        module = module_result

        # Prepare the module
        try:
            module.prepare(ast_module, engine)
        except ValueError as e:
            print(f"Module preparation error in {filepath}:", file=sys.stderr)
            print(f"  {e}", file=sys.stderr)
            sys.exit(1)

        # Display dependency tree
        # Show root module with its doc
        if module.doc:
            print(f"{filepath.name} - {module.doc}")
        else:
            print(f"{filepath.name}")

        # Track visited modules to avoid infinite loops
        visited = set()

        def show_module_deps(mod, indent=0, prefix=""):
            """Recursively show module dependencies."""
            if not hasattr(mod, 'namespaces') or not mod.namespaces:
                return

            # Filter out builtin namespace and already visited
            namespaces = {
                name: ns for name, ns in mod.namespaces.items()
                if name != 'builtin' and id(ns) not in visited
            }

            if not namespaces:
                return

            namespace_items = list(namespaces.items())
            for i, (ns_name, ns_module) in enumerate(namespace_items):
                is_last = (i == len(namespace_items) - 1)

                # Tree characters
                if is_last:
                    branch = "└── "
                    extension = "    "
                else:
                    branch = "├── "
                    extension = "│   "

                # Print this namespace with its doc
                if hasattr(ns_module, 'doc') and ns_module.doc:
                    print(f"{prefix}{branch}/{ns_name} - {ns_module.doc}")
                else:
                    print(f"{prefix}{branch}/{ns_name}")

                # Mark as visited
                visited.add(id(ns_module))

                # Show its dependencies recursively
                show_module_deps(ns_module, indent + 1, prefix + extension)

        # Show dependencies starting from root module
        show_module_deps(module)

        # If no dependencies (except builtin), indicate that
        if not any(name != 'builtin' for name in module.namespaces.keys()):
            print("  (no dependencies)")

    except comp.ParseError as e:
        print(f"Parse error in {filepath}:", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading {filepath}:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point for the comp CLI.

    Usage:
        comp <file.comp>    - Run a Comp program
        comp repl           - Start interactive REPL
        comp doc <file>     - Show module documentation
        comp dep <file>     - Show module dependencies
    """
    if len(sys.argv) < 2:
        print("Usage:", file=sys.stderr)
        print("  comp <file.comp>    - Run a Comp program", file=sys.stderr)
        print("  comp repl           - Start interactive REPL", file=sys.stderr)
        print("  comp doc <file>     - Show module documentation", file=sys.stderr)
        print("  comp dep <file>     - Show module dependencies", file=sys.stderr)
        sys.exit(1)

    # Check for REPL command
    if sys.argv[1] == "repl":
        from . import repl
        repl.main()
        return

    # Check for doc command
    args = list(sys.argv[1:])
    if args[0] == "doc":
        if len(args) < 2:
            print("Error: 'doc' command requires a file path", file=sys.stderr)
            print("Usage: comp doc <file.comp>", file=sys.stderr)
            print("--rich   Use rich markdown formatting", file=sys.stderr)
            sys.exit(1)
        has_rich = (args.remove("--rich") and True) if "--rich" in args else False
        _show_documentation(args[1], rich=has_rich)
        return

    # Check for dep command
    if args[0] == "dep":
        if len(args) < 2:
            print("Error: 'dep' command requires a file path", file=sys.stderr)
            print("Usage: comp dep <file.comp>", file=sys.stderr)
            sys.exit(1)
        show_dependencies(args[1])
        return

    # Get the file path
    filepath = Path(args[0])

    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    if not filepath.suffix == ".comp":
        print(f"Warning: Expected .comp file, got {filepath.suffix}", file=sys.stderr)

    try:
        # Read the file
        code = filepath.read_text(encoding="utf-8")

        # Parse the module with filename for position tracking
        ast_module = comp.parse_module(code, filename=str(filepath))

        # Create engine
        engine = comp.Engine()

        # Evaluate the module (processes all definitions)
        module_result = engine.run(ast_module)

        # Check if module evaluation returned a fail value
        if isinstance(module_result, comp.Value) and module_result.is_fail:
            print(f"Error loading module {filepath}:", file=sys.stderr)
            print(f"  {module_result}", file=sys.stderr)
            sys.exit(1)

        # The result should be a Module entity
        if not isinstance(module_result, comp.Module):
            print(f"Error: Expected Module entity, got {type(module_result)}", file=sys.stderr)
            sys.exit(1)

        module = module_result

        # Prepare the module (pre-resolve all references)
        try:
            module.prepare(ast_module, engine)
        except ValueError as e:
            print(f"Module preparation error in {filepath}:", file=sys.stderr)
            print(f"  {e}", file=sys.stderr)
            sys.exit(1)

        # Look for a !main entry point in the module
        if module.main_func is None:
            print(f"Error: No !main entry point found in {filepath}", file=sys.stderr)
            print("\nDefine a main entry point like:", file=sys.stderr)
            print("  !main = {", file=sys.stderr)
            print("    \"Hello, world!\"", file=sys.stderr)
            print("  }", file=sys.stderr)
            sys.exit(1)

        # Execute the main function body
        result = engine.run(module.main_func, module=module)

        # Check for failure
        if result.is_fail:
            print("Error executing main:", file=sys.stderr)
            print(f"  {result}", file=sys.stderr)
            sys.exit(1)

        print(result.unparse())

        sys.exit(0)

    except comp.ParseError as e:
        print(f"Parse error in {filepath}:", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        print("\nNote: The parser is still under development.", file=sys.stderr)
        print("Some language features may not be fully implemented yet.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error running {filepath}:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        # Print traceback for debugging
        import traceback
        traceback.print_exc()
        sys.exit(1)


def _show_documentation(filepath_str, rich):
    """Display documentation for a Comp module.

    Args:
        filepath_str: Path to the .comp file
        rich: If True, use rich formatting (not implemented yet)
    """
    filepath = Path(filepath_str)

    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    try:
        # Read and parse the module
        code = filepath.read_text(encoding="utf-8")
        ast_module = comp.parse_module(code, filename=str(filepath))

        # Create engine and evaluate module
        engine = comp.Engine()
        module_result = engine.run(ast_module)

        # Check for errors
        if isinstance(module_result, comp.Value) and module_result.is_fail:
            print(f"Error loading module {filepath}:", file=sys.stderr)
            print(f"  {module_result}", file=sys.stderr)
            sys.exit(1)

        if not isinstance(module_result, comp.Module):
            print(f"Error: Expected Module entity, got {type(module_result)}", file=sys.stderr)
            sys.exit(1)

        module = module_result

        # Prepare the module
        try:
            module.prepare(ast_module, engine)
        except ValueError as e:
            print(f"Module preparation error in {filepath}:", file=sys.stderr)
            print(f"  {e}", file=sys.stderr)
            sys.exit(1)

        buffer = io.StringIO()
        output = lambda v="": (buffer.write(v), buffer.write("\n"))

        # Display documentation as markdown
        output(f"# Module: {filepath.name}")
        output()

        # Show module documentation
        if module.doc:
            output(_summarize(module.doc))
            output()

        # Show module metadata
        if hasattr(module, 'mod_scope') and module.mod_scope.struct:
            if module.mod_scope.struct:
                output("## Module Configuration")
                output()
                for key, value in module.mod_scope.struct.items():
                    # if isinstance(key, comp.Undefined):
                    #     continue
                    key = key.unparse().strip('"')
                    value = value.unparse()
                    output(f"- `{key}` = `{value}`")
                output()

        # Show shapes
        if module.shapes:
            output("## Shapes")
            output()
            for shape_name, shape_def in module.shapes.items():
                #shape_display = shape_name if shape_name.startswith('~') else f"~{shape_name}"
                output(f"- `{shape_name}` {_summarize(shape_def.doc)}")
                impl = shape_def.unparse().split("=", 1)[-1].strip()
                output(f"  - `{impl}`")
            output()

        # Show functions
        if module.functions:
            output("## Functions")
            output()
            for func_name, func_defs in module.functions.items():
                #func_display = func_name if func_name.startswith('|') else f"|{func_name}"
                doc = " ".join(_summarize(f.doc) for f in func_defs if f.doc)
                output(f"- `{func_name}` {doc}")

                # Functions can have multiple definitions (polymorphism)
                for func_def in func_defs:
                    shape = func_def.input_shape.unparse().split("=", 1)[-1].strip()
                    if func_def.arg_shape:
                        arg = func_def.arg_shape.unparse().split("=", 1)[-1].strip()
                        arg = f"  (arg `{arg}`)"
                    else:
                        arg = ""
                    output(f"  - `{shape}` {arg}")
            output()

        # Show tags
        if module.tags:
            output("## Tags")
            output()
            for tag_name, tag_def in module.tags.items():
                tag_display = tag_name if tag_name.startswith('#') else f"#{tag_name}"
                value_str = tag_def.value.unparse() if hasattr(tag_def, 'value') and tag_def.value else ""
                if value_str:
                    output(f"- `{tag_display}` = `{value_str}`")
                else:
                    output(f"- `{tag_display}`")
            output()

        if rich:
            import rich.markdown, rich.console
            console = rich.console.Console()
            markdown = rich.markdown.Markdown(buffer.getvalue())
            console.print(markdown)
        else:
            print(buffer.getvalue().replace("`", ""))

    except comp.ParseError as e:
        print(f"Parse error in {filepath}:", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading {filepath}:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def _summarize(doc):
    """Summarize documentation"""
    if not doc:
        return ""
    doc = doc.split("\n", 1)[0]
    doc = " ".join(doc.split())
    if len(doc) > 60:
        doc = doc[:57] + "..."
    return doc


if __name__ == "__main__":
    main()
