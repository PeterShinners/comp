"""Namespace building and lookup for Comp modules."""

import comp


__all__ = ["NamespaceBuilder", "OverloadSet", "Ambiguous"]


class OverloadSet:
    """Collection of overloaded callables sharing the same name.

    Used when a name has multiple definitions (function overloads,
    or a shape + factory functions, etc.). Separates shape definitions
    from callable definitions to handle both ~Shape and Shape() contexts.
    """

    def __init__(self):
        self.shape = None       # Shape Value if one exists
        self.callables = []     # List of callable Values (Func, may include shape)

    def add_shape(self, shape_value):
        """Add a shape definition. Also adds to callables (shapes are callable)."""
        self.shape = shape_value
        if shape_value not in self.callables:
            self.callables.append(shape_value)

    def add_callable(self, func_value):
        """Add a callable (function) definition."""
        self.callables.append(func_value)

    def get_for_shape_context(self):
        """Get the value for ~name lookup."""
        if self.shape is None:
            raise TypeError("Name is not a shape")
        return self.shape

    def get_for_call_context(self):
        """Get candidates for name() call dispatch."""
        return self.callables

    def get_single(self):
        """Get single value if unambiguous, else return self for dispatch."""
        if len(self.callables) == 1:
            return self.callables[0]
        return self

    def __repr__(self):
        parts = []
        if self.shape:
            parts.append(f"shape={self.shape.data.qualified if hasattr(self.shape.data, 'qualified') else 'shape'}")
        parts.append(f"{len(self.callables)} callable(s)")
        return f"OverloadSet({', '.join(parts)})"


class Ambiguous:
    """Represents a name conflict in the namespace.

    Created when multiple non-overloadable definitions share the same
    unqualified name. This is an error condition that gets caught at
    build time when the name is referenced.
    """

    def __init__(self, qualified_names):
        self.qualified_names = list(qualified_names)

    def add_conflict(self, qualified_name):
        """Add another conflicting name."""
        if qualified_name not in self.qualified_names:
            self.qualified_names.append(qualified_name)

    def __repr__(self):
        return f"Ambiguous({', '.join(self.qualified_names)})"


class NamespaceBuilder:
    """Build and manage namespace for module definition lookups.

    Handles name permutations, overload sets, import shadowing, and conflicts.

    The namespace maps lookup names to (priority, value) tuples where:
    - priority: -1=system builtins, 0=imports, 1=local definitions
    - value: Value, OverloadSet, or Ambiguous

    ## Examples

    Basic usage:
        >>> from comp.tooling import NamespaceBuilder
        >>> nb = NamespaceBuilder()
        >>> nb.add_definition("server.host", host_value)
        >>> result = nb.lookup("host")
        >>> result is not None
        True
        >>> result = nb.lookup("server.host")
        >>> result is not None
        True

    Adding with import prefix:
        >>> nb.add_definition("status", status_value, import_prefix="http")
        >>> nb.lookup("http.status")  # Prefixed lookup
        >>> nb.lookup("status")        # Also works

    Adding module definitions:
        >>> nb.add_module_definitions(module.definitions, is_local=True)

    Detecting conflicts:
        >>> conflicts = nb.conflicts()
        >>> for name, ambig in conflicts.items():
        ...     print(f"Conflict: {name}")
        ...     for qname in ambig.qualified_names:
        ...         print(f"  - {qname}")

    Finding overload sets:
        >>> overloads = nb.overloads()
        >>> for name, overload_set in overloads.items():
        ...     print(f"{name}: {len(overload_set.callables)} overloads")

    Priority system (shadowing):
        >>> # System builtins (priority -1)
        >>> nb.add_system_builtins(system_namespace)
        >>> # Imports (priority 0) shadow system
        >>> nb.add_module_definitions(import.definitions, is_local=False)
        >>> # Local (priority 1) shadows imports
        >>> nb.add_module_definitions(module.definitions, is_local=True)
    """

    def __init__(self):
        # Internal namespace: lookup_name -> (priority, value/OverloadSet/Ambiguous)
        self._namespace = {}

    def add_definition(self, qualified_name, value, import_prefix=None, is_local=True):
        """Add a definition to namespace with all permutations.

        Args:
            qualified_name: Full name like 'display.set_mode.i001'
            value: Value to insert
            import_prefix: Import prefix like 'pg' for imported definitions
            is_local: True for local definitions (priority 1), False for imports (priority 0)
        """
        priority = 1 if is_local else 0

        # Generate all lookup permutations
        permutations = self._generate_permutations(qualified_name, import_prefix)

        for lookup_name in permutations:
            self._insert(lookup_name, qualified_name, value, priority)

    def add_module_definitions(self, definitions_dict, import_prefix=None, is_local=True):
        """Add all definitions from a module.

        Args:
            definitions_dict: Dict of qualified_name -> Value
            import_prefix: Optional import prefix for imported modules
            is_local: Whether these are local (True) or imported (False) definitions
        """
        for qualified_name, value in definitions_dict.items():
            # Skip pkg.* definitions - not part of namespace
            if qualified_name.startswith('pkg.'):
                continue
            # Skip tag union definitions (tag.*) - individual tags are added separately
            if qualified_name.startswith('tag.'):
                continue

            self.add_definition(qualified_name, value, import_prefix, is_local)

    def add_system_builtins(self, system_namespace):
        """Add system module builtins with priority -1.

        Args:
            system_namespace: Dict from SystemModule.get().namespace
        """
        for lookup_name, (_, value) in system_namespace.items():
            # Add with priority -1 (lower than imports which are 0)
            if lookup_name not in self._namespace:
                self._namespace[lookup_name] = (-1, value)

    def lookup(self, name):
        """Look up a name in the namespace.

        Args:
            name: Name to look up (can be short or qualified)

        Returns:
            Value, OverloadSet, or Ambiguous, or None if not found
        """
        entry = self._namespace.get(name)
        if entry is None:
            return None
        priority, value = entry
        return value

    def conflicts(self):
        """Get all ambiguous names.

        Returns:
            Dict[str, Ambiguous]: Mapping of name -> Ambiguous object
        """
        result = {}
        for name, (priority, value) in self._namespace.items():
            if isinstance(value, Ambiguous):
                result[name] = value
        return result

    def overloads(self):
        """Get all overloaded names.

        Returns:
            Dict[str, OverloadSet]: Mapping of name -> OverloadSet
        """
        result = {}
        for name, (priority, value) in self._namespace.items():
            if isinstance(value, OverloadSet):
                result[name] = value
        return result

    def to_dict(self):
        """Export namespace as simple dict (for Module.namespace).

        Returns:
            Dict[str, (int, Value|OverloadSet|Ambiguous)]
        """
        return dict(self._namespace)

    def update_entry(self, lookup_name, new_value):
        """Update an existing namespace entry's value (preserving priority).

        Args:
            lookup_name: The name to update
            new_value: The new value to set

        Returns:
            bool: True if updated, False if name not found
        """
        if lookup_name not in self._namespace:
            return False
        priority, _ = self._namespace[lookup_name]
        self._namespace[lookup_name] = (priority, new_value)
        return True

    # Private helper methods

    def _generate_permutations(self, qualified_name, import_prefix=None):
        """Generate lookup name permutations.

        Args:
            qualified_name: e.g., 'display.set_mode.i001'
            import_prefix: e.g., 'pg' if imported, None if local

        Returns:
            List of lookup names

        Examples:
            _generate_permutations('display.set_mode.i001')
            → ['display.set_mode', 'set_mode']

            _generate_permutations('display.set_mode', 'pg')
            → ['pg.display.set_mode', 'display.set_mode', 'set_mode']
        """
        # Strip .iXXX suffix
        base_name = self._strip_overload_suffix(qualified_name)

        permutations = []
        parts = base_name.split('.')

        # Add import-prefixed version
        if import_prefix:
            permutations.append(f"{import_prefix}.{base_name}")

        # Add all partial suffixes
        for i in range(len(parts)):
            permutations.append('.'.join(parts[i:]))

        return permutations

    def _strip_overload_suffix(self, qualified_name):
        """Strip .iXXX overload suffix from name.

        Args:
            qualified_name: e.g., 'add.i001' or 'display.set_mode.i123'

        Returns:
            Base name without overload suffix, e.g., 'add' or 'display.set_mode'
        """
        if '.' not in qualified_name:
            return qualified_name

        parts = qualified_name.split('.')
        last_part = parts[-1]

        # Check if last part is .iXXX format
        if last_part.startswith('i') and len(last_part) > 1 and last_part[1:].isdigit():
            return '.'.join(parts[:-1])

        return qualified_name

    def _insert(self, lookup_name, qualified_name, value, priority):
        """Insert into namespace with conflict/overload handling.

        Args:
            lookup_name: The exact name to insert at (e.g., 'set_mode', 'pg.display.set_mode')
            qualified_name: Full qualified name for error messages
            value: The Value to insert
            priority: -1=system, 0=imported, 1=local (for shadowing)
        """
        existing = self._namespace.get(lookup_name)

        # Case 1: No existing entry - insert directly
        if existing is None:
            self._namespace[lookup_name] = (priority, value)
            return

        existing_priority, existing_value = existing

        # Case 2: Lower priority - don't insert (shadowed by higher priority)
        if priority < existing_priority:
            return

        # Case 3: Higher priority - replace (local shadows import)
        if priority > existing_priority:
            self._namespace[lookup_name] = (priority, value)
            return

        # Case 4: Same priority - need to merge or create Ambiguous
        # Helper to get qualified name from various value types
        def get_qualified_name(val):
            if isinstance(val, Ambiguous):
                return None  # Already ambiguous
            if isinstance(val, OverloadSet):
                # Get qualified name from first callable
                if val.callables:
                    return val.callables[0].data.qualified if hasattr(val.callables[0].data, 'qualified') else None
            if hasattr(val, 'data') and hasattr(val.data, 'qualified'):
                return val.data.qualified
            return None

        # Handle Ambiguous existing value
        if isinstance(existing_value, Ambiguous):
            existing_value.add_conflict(qualified_name)
            return

        # Handle OverloadSet existing value
        if isinstance(existing_value, OverloadSet):
            if isinstance(value.data, comp.Shape):
                if existing_value.shape is not None:
                    # Two shapes with same name = ambiguous
                    self._namespace[lookup_name] = (priority, Ambiguous([
                        existing_value.shape.data.qualified,
                        qualified_name
                    ]))
                else:
                    existing_value.add_shape(value)
            elif isinstance(value.data, comp.Func):
                existing_value.add_callable(value)
            else:
                # Non-callable conflicts with OverloadSet
                existing_qualified = get_qualified_name(existing_value)
                if existing_qualified:
                    self._namespace[lookup_name] = (priority, Ambiguous([existing_qualified, qualified_name]))
            return

        # Both are single Values - determine if we can create OverloadSet
        existing_is_callable = isinstance(existing_value.data, (comp.Func, comp.Shape))
        new_is_callable = isinstance(value.data, (comp.Func, comp.Shape))

        if existing_is_callable and new_is_callable:
            # Both callable - create OverloadSet
            overloads = OverloadSet()

            # Add existing
            if isinstance(existing_value.data, comp.Shape):
                overloads.add_shape(existing_value)
            else:
                overloads.add_callable(existing_value)

            # Add new
            if isinstance(value.data, comp.Shape):
                overloads.add_shape(value)
            else:
                overloads.add_callable(value)

            self._namespace[lookup_name] = (priority, overloads)
        else:
            # Incompatible types - create Ambiguous
            existing_qualified = get_qualified_name(existing_value) or lookup_name
            self._namespace[lookup_name] = (priority, Ambiguous([existing_qualified, qualified_name]))
