"""Interactive REPL for Comp language.

Provides a read-eval-print loop for interactive development and experimentation.
"""

import sys

import comp


class ReplContext:
    """Context for REPL session.
    
    Maintains state across multiple evaluations:
    - @local scope for user-defined variables
    - Module for definitions (!tag, !shape, !func, !import)
    - Last result (_)
    - Engine instance
    """
    
    def __init__(self):
        self.engine = comp.Engine()
        self.module = comp.Module()
        self.local_scope = comp.Value({})
        self.last_result = comp.Value(None)
        
    def eval_line(self, line: str) -> comp.Value:
        """Evaluate a single line of input.
        
        Supports:
        - Expressions: 5 + 3, {x = 10}
        - Definitions: !tag #status, !func |foo, !shape ~point
        - References to _ (last result) and @local variables
        
        Returns the result Value.
        """
        line = line.strip()
        if not line:
            return comp.Value(None)
        
        # Try to parse as a module statement first (for definitions)
        # If it starts with !, it's probably a definition
        if line.startswith('!'):
            try:
                # Parse as a module with this single statement
                module_code = line
                ast_module = comp.parse_module(module_code, filename="<repl>")
                
                # Prepare the module (pre-resolve references)
                try:
                    self.module.prepare(ast_module, self.engine)
                except ValueError as e:
                    return comp.fail(f"Module preparation error: {e}")
                
                # Run the module statements to register definitions
                result = self.engine.run(ast_module)
                
                # Check if result is a fail
                if isinstance(result, comp.Value) and self.engine.is_fail(result):
                    return result
                
                # Update our module reference - definitions return Module entity
                if isinstance(result, comp.Module):
                    self.module = result
                    return comp.Value(True)  # Success indicator
                
                # Wrap result in Value if needed
                if not isinstance(result, comp.Value):
                    return comp.Value(result)
                
                return result
                
            except comp.ParseError as e:
                return comp.fail(f"Parse error: {e}")
            except Exception as e:
                return comp.fail(f"Error: {e}")
        
        # Otherwise, try to parse as an expression
        try:
            ast_expr = comp.parse_expr(line, filename="<repl>")
            
            # Store last result as _ in local scope
            if self.last_result is not None and self.last_result.data is not None:
                self.local_scope.struct[comp.Value('_')] = self.last_result
            
            # Evaluate with our context
            result = self.engine.run(
                ast_expr,
                local=self.local_scope,
                ctx=comp.Value({}),
                mod=comp.Value({}),
                module=self.module,
            )
            
            return result
            
        except comp.ParseError as e:
            return comp.fail(f"Parse error: {e}")
        except Exception as e:
            return comp.fail(f"Error: {e}")


def format_value(value: comp.Value) -> str:
    """Format a Value for display in the REPL.
    
    Uses unparse() if available, otherwise falls back to repr.
    """
    if value is None or value.data is None:
        return ""
    
    # Check for fail
    if value.is_struct and comp.Value('_') in value.struct:
        fail_marker = value.struct[comp.Value('_')]
        if fail_marker.is_tag:
            # It's a failure (tagged with #fail)
            if comp.Value('message') in value.struct:
                return f"✗ {value.struct[comp.Value('message')].data}"
            return f"✗ Fail: {value}"
    
    # Try to unparse if possible
    if hasattr(value, 'unparse'):
        try:
            return value.unparse()
        except Exception:
            pass
    
    # For True, show a simple checkmark
    if value.data is True:
        return "✓"
    
    # For structs, try to show nicely
    if value.is_struct:
        if not value.struct:
            return "{}"
        
        # Simple struct display
        items = []
        for k, v in value.struct.items():
            if isinstance(k, comp.Value):
                key_str = k.unparse() if hasattr(k, 'unparse') else str(k.data)
            else:
                key_str = str(k)
            
            if isinstance(v, comp.Value):
                val_str = format_value(v)
            else:
                val_str = str(v)
            
            items.append(f"{key_str}: {val_str}")
        
        return "{" + ", ".join(items) + "}"
    
    # Fallback to data representation
    return str(value.data)


def repl():
    """Run the interactive REPL."""
    print("Comp REPL v0.1.0")
    print("Type expressions to evaluate them, or use !tag, !shape, !func for definitions.")
    print("Use @varname to store in local scope, access with @varname later.")
    print("Last result is available as @_")
    print("Type 'exit' or Ctrl-C to quit.\n")
    
    context = ReplContext()
    
    while True:
        try:
            # Read input
            try:
                line = input("comp> ")
            except EOFError:
                print("\nGoodbye!")
                break
            
            # Check for exit commands
            if line.strip().lower() in ('exit', 'quit', ':q'):
                print("Goodbye!")
                break
            
            # Skip empty lines
            if not line.strip():
                continue
            
            # Evaluate
            result = context.eval_line(line)
            
            # Store as last result
            context.last_result = result
            
            # Display result
            output = format_value(result)
            if output:
                print(output)
            
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt")
            print("Type 'exit' to quit.")
            continue
        except Exception as e:
            print(f"Internal error: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main entry point for REPL."""
    try:
        repl()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
