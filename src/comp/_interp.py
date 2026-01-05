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

import hashlib
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

    # module methods should have compiler arg? probably.
    def module(self, resource, anchor=None):
        """Get new or existing Module for a given resource.

        Modules are cached and act as singletons within an interpreter.
        Module objects are lazily parsed and compiled. The Module may be
        invalid but still get a Module object.

        Args:
            resource: Module resource identifier to locate
            anchor: Directory of the module doing the import (for relative imports)
            compiler: Compiler to use for the module (default: "comp")

        Returns:
            (comp.Module) Module with location, content, and etag

        Raises:
            ModuleNotFoundError: Module not found in search paths
            NotImplementedError: For git://, http://, etc. URLs
        """
        anchored = comp._import.anchor_resource(resource, anchor)

        # Check for internal modules first
        # Ensure cop module is initialized (triggers lazy registration)
        comp.get_cop_module()

        internal_mod = comp.get_internal_module(anchored)
        if internal_mod is not None:
            # Cache and return the internal module
            self.module_cache[anchored] = internal_mod
            return internal_mod

        cached = self.module_cache.get(anchored)
        etag = cached.source.etag if cached else None
        src = comp._import.locate_resource(
            resource=anchored,
            etag=etag,
            search_paths=self.search_paths,
            search_fds=self.search_fds,
        )

        # If result is None, the etag matched - return cached version
        if src is None:
            return cached

        mod = comp.Module(src)
        self.module_cache[resource] = mod
        return mod

    def module_from_text(self, text):
        """Create a Module from existing text."""
        src = comp._import.ModuleSource(
            resource="text",
            location="text",
            source_type="text",
            etag=hashlib.sha256(text.encode('utf-8')).hexdigest(),
            content=text,
            anchor="",
        )
        mod = comp.Module(src)
        self.module_cache[mod.token] = mod
        return mod

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

    def invoke_block(self, block, args):
        """Call a function with the given arguments.

        Args:
            block: Value containing a Block
            args: Value containing the argument struct

        Returns:
            Value result of the function call
        """
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

