"""Module represents a module's namespace at runtime"""

import os

import comp


__all__ = ["Module"]


class Module:
    """A module in the Comp language.

    Namespaces are used to organize and scope identifiers in the language.
    They provide a way to group related definitions and prevent naming conflicts.

    Modules are immutable once finalized. The finalize() method must be called
    before any code from the module can be compiled or executed.

    Args:
        source: ModuleSource containing the module's location and content
                If None, creates a module without a source (e.g., system module)

    """

    _token_counter = os.getpid() & 0xFFFF

    def __init__(self, source=None):
        # Module token is not attempting to be a secure id,
        # Just to help distinguish conflicting tokens with a non repeating id

        # Handle backward compatibility: source can be a string (legacy) or ModuleSource
        if isinstance(source, str):
            # Legacy API: source is just a token string
            token = source
            self.source = None
        elif source is None:
            token = "anonymous"
            self.source = None
        else:
            # New API: source is a ModuleSource
            token = source.resource
            self.source = source

        count = hash(token) & 0xFFFF ^ Module._token_counter
        Module._token_counter += 1
        self.token = f"{token}#{count:04x}"

        self.package = {}  # statically defined constants (pkg.name, etc)
        self.scope = {}  # module-level constants (mod.x assignments)
        self.startups = {}  # defined context startups for this module
        self.imports = {}  # defined imports
        self.privatedefs = []  # The 'my' namespace
        self.publicdefs = []  # All defined/exported values

        # COP tree and transformation tracking
        self.cop_tree = None  # Current COP nodes (gets progressively transformed)
        self._cop_parsed = False  # Has initial parse been done?
        self._cop_resolved = False  # Have references been resolved?
        self._cop_optimized = False  # Have optimizations been applied?

        # Populated by finalize()
        self.namespace = None  # Finally resolved namespace dict
        self._finalized = False

        # Slot mappings for compilation (populated during finalize)
        self._const_slots = {}  # name -> slot index
        self._const_values = []  # slot index -> Value

    def __repr__(self):
        return f"Module<{self.token}>"

    def __hash__(self):
        return id(self.token)

    @property
    def is_finalized(self):
        """(bool) Whether the module has been finalized."""
        return self._finalized

    @property
    def is_parsed(self):
        """(bool) Whether the module has been parsed (cop_tree populated)."""
        return self._cop_parsed

    @property
    def is_resolved(self):
        """(bool) Whether references have been resolved."""
        return self._cop_resolved

    @property
    def is_optimized(self):
        """(bool) Whether optimizations have been applied."""
        return self._cop_optimized

    def get_cop(self):
        """Get the module's COP tree, parsing from source if needed.

        This method lazily parses the module's source into COP nodes on first call.
        Subsequent calls return the cached cop_tree.

        Returns:
            Value containing COP nodes for this module

        Raises:
            ValueError: If module has no source to parse
            ParseError: If source cannot be parsed
        """
        if self._cop_parsed:
            return self.cop_tree

        if self.source is None:
            raise ValueError("Cannot parse module without source")

        # Parse the source content into COP nodes
        # Directly call comp.parse() - no interpreter needed
        self.cop_tree = comp.parse(self.source.content)
        self._cop_parsed = True

        return self.cop_tree

    def get_imports(self):
        """Get list of immediate import dependencies from scan metadata.

        Returns:
            List of (name, resource) tuples, where:
                name: The import binding name (e.g., 'cart')
                resource: The module resource string (e.g., './examples/cart')

        Returns empty list if no scan metadata or no imports.
        """
        if not hasattr(self, '_scan_metadata') or self._scan_metadata is None:
            return []

        try:
            imports_val = self._scan_metadata.field('imports')
        except (KeyError, AttributeError):
            return []

        if not hasattr(imports_val, 'data') or not isinstance(imports_val.data, dict):
            return []

        result = []
        for import_item in imports_val.data.values():
            try:
                name = import_item.field('name').data
                resource = import_item.field('source').data
                result.append((name, resource))
            except (KeyError, AttributeError):
                continue

        return result

    def add_constant(self, name, value):
        """Add a module constant and return its slot index.

        Must be called before finalize().

        Args:
            name: (str) Name of the constant
            value: Value to store

        Returns:
            (int) Slot index for the constant
        """
        if self._finalized:
            raise RuntimeError("Cannot add constants to finalized module")
        if name in self._const_slots:
            raise ValueError(f"Constant '{name}' already defined")

        slot = len(self._const_values)
        self._const_slots[name] = slot
        self._const_values.append(value)
        return slot

    def get_const_slot(self, name):
        """Get the slot index for a module constant, or None if not found.

        Args:
            name: (str) Name of the constant

        Returns:
            (int | None) Slot index or None if not found
        """
        return self._const_slots.get(name)

    def get_const_value(self, slot):
        """Get a constant value by slot index.

        Args:
            slot: (int) Slot index

        Returns:
            Value at the given slot
        """
        return self._const_values[slot]

    def finalize(self):
        """Finalize module after all imports and definitions are added.

        This populates the namespace dictionaries for fast lookup.
        All imports must be complete at this point.
        """
        pass


class SystemModule(Module):
    """System module singleton with several builtin attributes"""

    _singleton = None

    def __init__(self):
        super().__init__(source=None)  # System module has no source file
        self.token = "system#0000"

        # Builtin tags
        self.bool = comp.tag_bool
        self.true = comp.tag_true
        self.false = comp.tag_false
        self.fail = comp.tag_fail

        # Builtin shapes
        self.num = comp.shape_num
        self.text = comp.shape_text
        self.struct = comp.shape_struct
        self.any = comp.shape_any
        self.func = comp.shape_func

    @classmethod
    def get(cls):
        """Get system module singleton."""
        # Constructed lazy for first interpreter
        global _system_module
        if SystemModule._singleton is None:
            SystemModule._singleton = cls()
        return SystemModule._singleton


class NameConflict:
    """Used in namespaces where conflicts exist"""

    # This is used to help error messages later on
    def __init__(self, *references):
        self.references = references

    def __repr__(self):
        return f"NameConflict{self.references}"


def add_name_permutations(dictionary, ns, qualified, definition):
    """Generate possible qualified names for a given namespace and qualified name.

    Args:
        dictionary: (dict) Dictionary to add names to
        ns: (str) Namespace prefix
        qualified: (str) Qualified name
    Returns:
        (list[str]) valid reference names
    """
    variations = []
    # Generate all forms of named variations
    while True:
        if not qualified:
            break
        if ns:
            variations.extend((f"{qualified}/{ns}", qualified))
        else:
            variations.append(qualified)
        qualified = qualified.partition(".")[2]

    full = variations[0]
    conflicts = {}  # track conflicts so we can reference full names

    # Add to dictionary, potentially with conflicts
    for ref in variations:
        conflict = conflicts.get(ref)
        if conflict:
            conflict.references += (full,)
            dictionary[ref] = conflict
        else:
            conflicts[ref] = NameConflict(full)
            dictionary[ref] = definition
