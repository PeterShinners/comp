"""Main interpreter and instruction types.

Instructions are a higher-level bytecode representation that sits between
COP nodes and execution. Each instruction:
- Has a reference to its source COP node for error reporting
- Contains pre-resolved references (no runtime lookups)
- Holds literal Values when known at build time
- Uses a register-based model (named slots, not stack)

The instruction stream is linear and easy to march through.
Performance optimizations can happen later - clarity first.
"""

import os
from pathlib import Path

import comp

__all__ = ["Interp"]

class Interp:
    """Interpreter and state for Comp.

    An interpreter must be created to do most anything with comp objects
    or the language.
    """

    def __init__(self):
        self.system = comp._module.SystemModule.get()
        # Import-related state (was ImportContext)
        comp_root = str(Path(__file__).parent)
        working_dir = str(Path.cwd())
        self.comp_root = comp_root
        self.working_dir = working_dir
        self.search_paths = [
            os.path.join(self.comp_root, "stdlib"),  # Built-in stdlib
            os.path.join(self.working_dir, "stdlib"),  # Project stdlib
            self.working_dir,  # Project root
        ]
        # Open directory file descriptors for efficient searching
        # On Windows, directory fds work differently, so we test if it's supported
        self.search_fds = []
        for path in self.search_paths:
            if not os.path.isdir(path):
                self.search_fds.append(-1)
                continue
            try:
                # Try to open directory - works on Unix, may fail on Windows
                fd = os.open(path, os.O_RDONLY)
                self.search_fds.append(fd)
            except (FileNotFoundError, OSError, PermissionError):
                # Directory exists but can't be opened as fd (Windows)
                # Use -1 to indicate fallback to path-based search
                self.search_fds.append(-1)

        # Module source cache: resource -> ModuleSource
        # Stores previously located module sources for etag validation and reuse
        self.module_cache = {}

        # Module cache: resource -> Module
        # Stores Module objects that have been created (may or may not be finalized)
        self.modules = {}

    def __del__(self):
        for fd in getattr(self, 'search_fds', []):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def __repr__(self):
        return "Interp<>"

    def __hash__(self):
        return id(self)

    def import_locate(self, resource, from_dir=None):
        """Locate a module using the interpreter's import search paths.

        Manages module caching: if the module has been located before, sends
        the cached etag to locate(). If locate() returns None (etag match),
        returns the cached ModuleSource. Otherwise caches and returns the new one.

        Args:
            resource: Module resource identifier to locate
            from_dir: Directory of the module doing the import (for relative imports)

        Returns:
            ModuleSource with location, content, and etag

        Raises:
            ModuleNotFoundError: Module not found in search paths
            NotImplementedError: For git://, http://, etc. URLs
        """
        # Check if we have a cached version and get its etag
        cached = self.module_cache.get(resource)
        etag = cached.etag if cached else None

        # Locate the module, passing the etag if we have one
        result = comp._import.locate(
            resource=resource,
            from_dir=from_dir,
            etag=etag,
            search_paths=self.search_paths,
            search_fds=self.search_fds,
        )

        # If result is None, the etag matched - return cached version
        if result is None:
            return cached

        # Otherwise, cache the new result and return it
        self.module_cache[resource] = result
        return result

    def import_discover(self, module_source):
        """Discover all dependencies recursively from a starting ModuleSource.

        This method:
        1. Scans the starting module to find its imports
        2. Recursively locates and scans each import
        3. Handles circular dependencies (stops recursion at cycles)
        4. Returns complete dependency graph as dict

        Args:
            module_source: Starting ModuleSource to discover dependencies from

        Returns:
            Dict mapping resource -> ModuleSource for entire dependency graph,
            including the starting module itself

        Raises:
            ModuleNotFoundError: If any imported module cannot be located
        """
        discovered = {}  # resource -> ModuleSource
        visited = set()  # resource names to detect cycles

        def discover_recursive(source):
            """Recursively discover dependencies from a ModuleSource."""
            resource = source.resource

            # Add to discovered dict
            discovered[resource] = source

            # Check for cycle
            if resource in visited:
                return
            visited.add(resource)

            # Scan to find imports
            try:
                metadata = comp.scan(source.content)
            except Exception:
                # If scan fails, can't discover dependencies
                return

            # Extract import list from metadata using .field() method
            # metadata is a Value struct with 'imports' field
            try:
                imports_val = metadata.field('imports')
            except (KeyError, AttributeError):
                # No imports field
                return

            # imports_val.data is a dict with Unnamed (_) keys for positional items
            if not hasattr(imports_val, 'data') or not isinstance(imports_val.data, dict):
                return

            # Process each import (iterate over dict values)
            for import_item in imports_val.data.values():
                # Each import has fields: name, source, compiler
                try:
                    # Extract 'source' field (not 'resource')
                    import_resource = import_item.field('source').data
                except (KeyError, AttributeError):
                    continue

                if not isinstance(import_resource, str):
                    continue

                # Skip if already discovered
                if import_resource in discovered:
                    continue

                # Locate the imported module
                try:
                    imported_source = self.import_locate(
                        import_resource,
                        from_dir=source.anchor
                    )
                    # Recursively discover from this module
                    discover_recursive(imported_source)
                except Exception:
                    # Module not found or other error - skip it
                    # The caller can decide how to handle missing modules
                    continue

        # Start recursive discovery from the initial module
        discover_recursive(module_source)

        return discovered

    def import_parse(self, module):
        """Parse a Module's source into COP tree.

        This is a convenience method that delegates to module.get_cop().
        You can call module.get_cop() directly instead.

        Args:
            module: Module object to parse (must have source attribute)

        Returns:
            The same Module object (for chaining)

        Raises:
            ValueError: If module has no source
            ParseError: If source cannot be parsed
        """
        module.get_cop()
        return module

    def import_module(self, resource, from_dir=None):
        """Get or create a Module for the given resource.

        This method manages the full module loading pipeline:
        1. Checks if Module already exists in cache → return it
        2. Otherwise:
           a. Calls import_locate() to get ModuleSource (with caching)
           b. Calls scan() on the source content to extract metadata
           c. Creates a new Module with the ModuleSource reference
           d. Populates Module with scan metadata (pkg, imports, etc)
           e. Caches the Module
           f. Returns the Module (NOT finalized - imports not yet resolved)

        Args:
            resource: Module resource identifier to load
            from_dir: Directory for relative imports (or None)

        Returns:
            Module object (may or may not be finalized)

        Raises:
            ModuleNotFoundError: Module source not found
            NotImplementedError: For git://, http://, etc. URLs
        """
        # Check if module already loaded
        if resource in self.modules:
            return self.modules[resource]

        # Locate the module source (uses cache)
        source = self.import_locate(resource, from_dir=from_dir)

        # Scan the source to extract metadata
        metadata = comp.scan(source.content)

        # Create a new Module with the source
        module = comp.Module(source)

        # Populate module with scan metadata
        # Note: metadata is a Value struct with fields: pkg, imports, docs
        # TODO: Process pkg assignments and imports into the module
        # For now, just store the raw metadata
        module._scan_metadata = metadata

        # Cache and return the module
        self.modules[resource] = module
        return module

    def execute(self, instructions, env=None):
        """Execute a sequence of instructions.

        Args:
            instructions: List of Instruction objects
            env: Initial environment (variable bindings)

        Returns:
            Final result Value (from last instruction)
        """
        frame = ExecutionFrame(env, interp=self)
        result = None

        for instr in instructions:
            result = instr.execute(frame)

        return result


class ExecutionFrame:
    """Runtime execution frame.

    Holds registers (temporaries) and environment (variables).
    This is the mutable state passed through instruction execution.

    Attributes:
        registers: Dict mapping register names to Values
        env: Dict mapping variable names to Values
        interp: The interpreter instance (for nested calls)
    """

    def __init__(self, env=None, interp=None):
        self.registers = {}
        self.env = env if env is not None else {}
        self.interp = interp

    def get_value(self, source):
        """Get a value from either a register or directly.

        Args:
            source: Either a register name (str) or a Value

        Returns:
            The Value
        """
        if isinstance(source, str):
            if source not in self.registers:
                raise ValueError(f"Undefined register: {source}")
            return self.registers[source]
        return source

    def call_function(self, func, args):
        """Call a function with the given arguments.

        Args:
            func: Value containing a Block
            args: Value containing the argument struct

        Returns:
            Value result of the function call
        """
        # Check if func contains a Block
        if not isinstance(func.data, Block):
            raise TypeError(f"Cannot call non-block value (got {type(func.data).__name__})")

        block = func.data

        # Create a new environment for the function
        # Start with the closure environment (captured at block definition)
        # TODO: Handle signature/parameters properly - bind args to param names
        new_env = dict(block.closure_env)

        # Execute the pre-compiled body instructions
        new_frame = ExecutionFrame(env=new_env, interp=self.interp)
        result = None

        for instr in block.body_instructions:
            result = instr.execute(new_frame)

        # Return the final result
        return result if result is not None else comp.Value.from_python(None)

