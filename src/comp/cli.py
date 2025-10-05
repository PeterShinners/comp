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
        
        # Create runtime module
        module = comp.run.Module(filepath.stem)
        
        # Add builtins
        module.process_builtins()
        
        # Process the AST
        module.process_ast(ast_module)
        
        # Resolve all definitions
        module.resolve_all()
        
        # Look for a 'main' function
        if "main" not in module.funcs:
            print(f"Error: No 'main' function found in {filepath}", file=sys.stderr)
            print("\nDefine a main function like:", file=sys.stderr)
            print("  !func |main ~_ = {", file=sys.stderr)
            print("    ...", file=sys.stderr)
            print("  }", file=sys.stderr)
            sys.exit(1)
        
        # Invoke the main function
        main_func = module.funcs["main"]
        
        # Call main with empty arguments
        result = comp.run.invoke(
            main_func,
            module,
            comp.run.Value({}),  # $in
            comp.run.Value({}),  # $ctx
            comp.run.Value({}),  # $mod
            comp.run.Value({}),  # $arg
        )
        
        # If main returns a structure, print it
        if result.is_struct or result.is_num or result.is_str or result.is_tag:
            print(result)
        
        sys.exit(0)
        
    except comp.ParseError as e:
        print(f"Parse error in {filepath}:", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
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
