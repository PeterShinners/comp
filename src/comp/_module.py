"""Module represents a module's namespace at runtime"""

import os
from typing import Any

import comp


__all__ = ["Module"]


class Module:
    """A module in the Comp language.

    Namespaces are used to organize and scope identifiers in the language.
    They provide a way to group related definitions and prevent naming conflicts.

    Modules are immutable once finalized. The finalize() method must be called
    before any code from the module can be compiled or executed.

    Args:
        token: (str) Somewhat internal identifier for module
    
    """
    _token_counter = os.getpid() & 0xffff

    def __init__(self, token):
        # Module token is not attempting to be a secure id,
        # Just to help distinguish conflicting tokens with a non repeating id
        count = hash(token) & 0xffff ^ Module._token_counter
        Module._token_counter += 1
        self.token = f"{token}#{count:04x}"

        self.package = {}  # statically defined constants (pkg.name, etc)
        self.scope = {}  # module-level constants (mod.x assignments)
        self.contexts = {}  # defined context startups for this module
        self.imports = {}  # defined imports
        self.privatedefs = []  # The 'my' namespace
        self.publicdefs = []  # All defined/exported values
        
        # Populated by finalize()
        self.namespace = None  # Finally resolved namespace dict
        self._finalized = False
        
        # Slot mappings for compilation (populated during finalize)
        self._const_slots: dict[str, int] = {}  # name -> slot index
        self._const_values: list[Any] = []  # slot index -> Value

    def __repr__(self):
        return f"Module<{self.token}>"

    def __hash__(self):
        return id(self.token)

    @property
    def is_finalized(self) -> bool:
        return self._finalized

    def add_constant(self, name: str, value: Any) -> int:
        """Add a module constant and return its slot index.
        
        Must be called before finalize().
        """
        if self._finalized:
            raise RuntimeError("Cannot add constants to finalized module")
        if name in self._const_slots:
            raise ValueError(f"Constant '{name}' already defined")
        
        slot = len(self._const_values)
        self._const_slots[name] = slot
        self._const_values.append(value)
        return slot

    def get_const_slot(self, name: str) -> int | None:
        """Get the slot index for a module constant, or None if not found."""
        return self._const_slots.get(name)

    def get_const_value(self, slot: int) -> Any:
        """Get a constant value by slot index."""
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
        super().__init__("system")
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
            conflict.references += (full, )
            dictionary[ref] = conflict
        else:
            conflicts[ref] = NameConflict(full)
            dictionary[ref] = definition
