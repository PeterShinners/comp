"""Command-line interface for Comp language.

🎉 Milestone Release 0.1.0 - A working Comp interpreter!

This CLI allows you to run .comp programs from the command line.
Every program needs a 'main' function that serves as the entry point.
"""

import sys
from pathlib import Path

import comp


def main():
    """Main entry point for the comp CLI.

    Usage:
        comp <file.comp>    - Run a Comp program
        comp repl           - Start interactive REPL
    """
    if len(sys.argv) < 2:
        print("Usage:", file=sys.stderr)
        print("  comp <file.comp>    - Run a Comp program", file=sys.stderr)
        print("  comp repl           - Start interactive REPL", file=sys.stderr)
        sys.exit(1)
    
    # Check for REPL command
    if sys.argv[1] == "repl":
        from . import repl
        repl.main()
        return

    # Get the file path
    filepath = Path(sys.argv[1])

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

        # Look for a 'main' function in the module
        try:
            main_funcs = module.lookup_function(["main"])
        except ValueError:
            # Not found
            print(f"Error: No 'main' function found in {filepath}", file=sys.stderr)
            print("\nDefine a main function like:", file=sys.stderr)
            print("  !func |main ~{} = {", file=sys.stderr)
            print("    ...", file=sys.stderr)
            print("  }", file=sys.stderr)
            sys.exit(1)

        result = engine.run_function(main_funcs[0])

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


if __name__ == "__main__":
    main()
