"""Internal modules that provide built-in functionality.

Internal modules are modules implemented in Python that provide tags, shapes,
and callable functions to Comp code. They can be imported like regular modules
using `!import` statements.

Example:
    !import cop ("cop" comp)
    x = cop.test
"""

__all__ = [
    "InternalModule",
    "register_internal_module",
    "get_internal_module",
    "get_cop_module",
]

import comp


class InternalModule(comp.Module):
    """A module implemented in Python that provides internal functionality.

    Internal modules contain definitions for:
    - Tags (type constructors like `test`, `value.block`, etc.)
    - Shapes (type definitions)
    - Callables (functions implemented in Python)

    They can be imported using `!import` statements like regular modules.
    """

    def __init__(self, resource_name):
        """Create an internal module.

        Args:
            resource_name: The import name for this module (e.g., "cop", "system")
        """
        # Create a minimal ModuleSource
        source = comp.ModuleSource(
            resource=resource_name,
            location=f"internal:{resource_name}",
            source_type="internal",
            etag=resource_name,
            anchor="",
            content=""  # Internal modules have no source text
        )
        super().__init__(source)
        self._definitions = {}
        self._finalized = False

    def add_tag(self, qualified_name, private=False):
        """Add a tag definition to this module.

        Args:
            qualified_name: Qualified name like "test" or "value.block"
            private: Whether this is a private tag

        Returns:
            Tag: The created Tag object
        """
        # Create the Tag object
        tag = comp.Tag(qualified_name, private)
        tag.module = self

        # Create a Definition for it
        definition = comp.Definition(
            qualified=qualified_name,
            module_id=self.token,
            original_cop=None,
            shape=comp.shape_struct  # Tags are struct-shaped values
        )
        definition.value = comp.Value.from_python(tag)

        self._definitions[qualified_name] = definition
        return tag

    def add_shape(self, qualified_name, shape_value):
        """Add a shape definition to this module.

        Args:
            qualified_name: Qualified name like "block" or "value"
            shape_value: The Shape object

        Returns:
            Definition: The created Definition object
        """
        definition = comp.Definition(
            qualified=qualified_name,
            module_id=self.token,
            original_cop=None,
            shape=comp.shape_shape
        )
        definition.value = comp.Value.from_python(shape_value)

        self._definitions[qualified_name] = definition
        return definition

    def add_callable(self, qualified_name, python_function):
        """Add a callable definition to this module.

        Args:
            qualified_name: Qualified name like "fold" or "unparse"
            python_function: Python function to call

        Returns:
            Definition: The created Definition object
        """
        # For now, wrap the Python function in a Value
        # TODO: Create proper InternalCallable type
        definition = comp.Definition(
            qualified=qualified_name,
            module_id=self.token,
            original_cop=None,
            shape=comp.shape_block
        )
        definition.value = None  # Will be set to InternalCallable later
        definition._python_function = python_function

        self._definitions[qualified_name] = definition
        return definition

    def finalize(self):
        """Mark this module as finalized.

        After finalization, no more definitions can be added.
        """
        self._finalized = True

    def definitions(self):
        """Return the definitions dict.

        Returns:
            dict: {qualified_name: Definition}
        """
        return self._definitions


# Registry of internal modules
_internal_modules = {}


def register_internal_module(resource_name, module):
    """Register an internal module so it can be imported.

    Args:
        resource_name: The import name (e.g., "cop", "system")
        module: The InternalModule instance
    """
    _internal_modules[resource_name] = module


def get_internal_module(resource_name):
    """Get an internal module by name.

    Args:
        resource_name: The import name (e.g., "cop", "system")

    Returns:
        InternalModule or None: The module if registered, None otherwise
    """
    return _internal_modules.get(resource_name)


def create_cop_module():
    """Create the 'cop' internal module with COP-related tags.

    Returns:
        InternalModule: The cop module
    """
    cop_module = InternalModule("cop")

    # Add a test tag
    cop_module.add_tag("test", private=False)

    # Add all COP tags
    from comp._parse import COP_TAGS
    for tag_name in COP_TAGS:
        cop_module.add_tag(tag_name, private=False)

    cop_module.finalize()
    register_internal_module("cop", cop_module)
    return cop_module


# Initialize the cop module on demand (lazy)
_cop_module = None

def get_cop_module():
    """Get or create the cop internal module.

    Returns:
        InternalModule: The cop module
    """
    global _cop_module
    if _cop_module is None:
        _cop_module = create_cop_module()
    return _cop_module
