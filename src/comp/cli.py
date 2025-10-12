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
        comp <file.comp>
    """
    if len(sys.argv) < 2:
        print("Usage: comp <file.comp>", file=sys.stderr)
        print("\nRuns a Comp program by invoking its 'main' function.", file=sys.stderr)
        sys.exit(1)

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

        # Parse the module
        ast_module = comp.parse_module(code)

        # Create engine
        engine = comp.Engine()

        # Evaluate the module (processes all definitions)
        module_result = engine.run(ast_module)

        # Check if module evaluation returned a fail value
        if isinstance(module_result, comp.Value) and engine.is_fail(module_result):
            print(f"Error loading module {filepath}:", file=sys.stderr)
            print(f"  {module_result}", file=sys.stderr)
            sys.exit(1)

        # The result should be a Module entity
        if not isinstance(module_result, comp.Module):
            print(f"Error: Expected Module entity, got {type(module_result)}", file=sys.stderr)
            sys.exit(1)

        module = module_result

        # Look for a 'main' function in the module
        main_funcs = module.lookup_function(["main"])
        if main_funcs is None or len(main_funcs) == 0:
            print(f"Error: No 'main' function found in {filepath}", file=sys.stderr)
            print("\nDefine a main function like:", file=sys.stderr)
            print("  !func |main ~{} = {", file=sys.stderr)
            print("    ...", file=sys.stderr)
            print("  }", file=sys.stderr)
            sys.exit(1)

        # Get the main function definition (use first overload for now)
        main_func = main_funcs[0]

        # Invoke the main function
        # Main takes no input ($in will be nil) and no args ($arg will be empty)
        result = engine.run(
            main_func.body,
            in_=comp.Value(None),
            arg=comp.Value({}),
            ctx=comp.Value({}),
            mod=comp.Value({}),
            local=comp.Value({}),
            mod_funcs=module,
            mod_shapes=module,
            mod_tags=module,
        )

        # Check for failure
        if isinstance(result, comp.Value) and engine.is_fail(result):
            print("Error executing main:", file=sys.stderr)
            print(f"  {result}", file=sys.stderr)
            sys.exit(1)

        # Print the result if it's not None
        if isinstance(result, comp.Value) and result.data is not None:
            print(result.data)

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
