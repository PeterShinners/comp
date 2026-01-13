"""Internal modules that provide built-in functionality."""

__all__ = [
    "InternalModule",
    "InternalCallable",
    "SystemModule",
    "get_internal_module",
]

import inspect
import comp


class InternalCallable:
    """A Python function callable from Comp code.

    Wraps a Python function so it can be invoked like a Comp block.
    The Python function receives (input_val, args_val, frame) and returns a Value.
    The frame parameter is optional - functions that don't need it can ignore it.

    Args:
        name: (str) Name of the callable
        func: (callable) Python function to call

    Attributes:
        name: (str) Name for display
        func: (callable) The wrapped Python function
    """

    __slots__ = ("name", "func")

    def __init__(self, name, func):
        self.name = name
        self.func = func

    def __repr__(self):
        return f"<InternalCallable {self.name}>"


class InternalModule(comp.Module):
    """A module implemented in Python that provides internal functionality.

    Internal modules contain definitions for:
    - Tags (type constructors like `test`, `value.block`, etc.)
    - Shapes (type definitions)
    - Callables (functions implemented in Python)

    They can be imported using `!import` statements like regular modules.
    """

    def __init__(self, resource, doc):
        """Create an internal module.

        Args:
            resource: The import name for this module (e.g., "cop", "system")
        """
        # Create a minimal ModuleSource
        source = comp.ModuleSource(
            resource=resource,
            location=f"internal:{resource}",
            source_type="internal",
            etag=resource,
            anchor="",
            content=""  # Internal modules have no source text
        )
        super().__init__(source)

        docs = [{"content": doc}]
        scan = {
            "docs": comp.Value.from_python(docs)
        }
        self._scan = comp.Value.from_python(scan)
        self._imports = {}
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
            qualified_name: Qualified name like "fold" or "incr"
            python_function: Python function to call. Receives (input_val, args_val)
                and returns a Value.

        Returns:
            Definition: The created Definition object
        """
        callable_obj = InternalCallable(qualified_name, python_function)
        value = comp.Value(callable_obj)
        
        definition = comp.Definition(
            qualified=qualified_name,
            module_id=self.token,
            original_cop=None,
            shape=comp.shape_block
        )
        definition.value = value

        self._definitions[qualified_name] = definition
        return definition

    def finalize(self):
        self._finalized = True

    def definitions(self):
        return self._definitions



class SystemModule(comp.Module):
    """System module singleton with several builtin attributes"""

    def __init__(self):
        # Create a minimal ModuleSource for system module
        source = type('obj', (object,), {'resource': 'system', 'content': ''})()
        super().__init__(source)
        self.token = "system#0000"

        # Populate definitions dict with builtin tags and shapes as Definition objects
        # These are pre-folded since they're built-in objects
        self._imports = {}
        self._definitions = {}

        # Helper to create Definition with pre-folded value
        def _create_builtin_def(name, obj, shape_type):
            value = comp.Value.from_python(obj)
            defn = comp.Definition(name, self.token, value, shape_type)
            defn.resolved_cop = value  # Already resolved
            defn.value = value  # Already folded
            return defn

        # Builtin tags - use shape_struct for tag values
        self._definitions['nil'] = _create_builtin_def('nil', comp.tag_nil, comp.shape_struct)
        self._definitions['bool'] = _create_builtin_def('bool', comp.tag_bool, comp.shape_struct)
        self._definitions['bool.true'] = _create_builtin_def('bool.true', comp.tag_true, comp.shape_struct)
        self._definitions['bool.false'] = _create_builtin_def('bool.false', comp.tag_false, comp.shape_struct)
        # Note: 'true' and 'false' shortcuts are created via namespace permutations from 'bool.true' and 'bool.false'
        self._definitions['fail'] = _create_builtin_def('fail', comp.tag_fail, comp.shape_struct)

        # Builtin shapes
        self._definitions['num'] = _create_builtin_def('num', comp.shape_num, comp.shape_shape)
        self._definitions['text'] = _create_builtin_def('text', comp.shape_text, comp.shape_shape)
        self._definitions['struct'] = _create_builtin_def('struct', comp.shape_struct, comp.shape_shape)
        self._definitions['any'] = _create_builtin_def('any', comp.shape_any, comp.shape_shape)
        self._definitions['func'] = _create_builtin_def('func', comp.shape_block, comp.shape_shape)

        # Builtin callables
        def _incr(input_val, args_val, frame):
            """Increment a number by 1."""
            n = input_val.to_python()
            return comp.Value.from_python(n + 1)
        
        incr_callable = InternalCallable("incr", _incr)
        incr_value = comp.Value(incr_callable)
        incr_defn = comp.Definition("incr", self.token, incr_value, comp.shape_block)
        incr_defn.resolved_cop = incr_value
        incr_defn.value = incr_value
        self._definitions['incr'] = incr_defn

        def _wrap(input_val, args_val, frame):
            """Wrap a callable with outer wrappers.
            
            For now, just invokes the inner callable:
            wrapped.input | wrapped.callable(wrapped.args)
            
            Args:
                input_val: The wrap context ~(callable input args)
                args_val: Unused for now
                frame: The interpreter frame for invoking callables
                
            Returns:
                Result of invoking the inner callable
            """
            # Extract from wrap context struct
            # input_val is ~(callable input args)
            ctx = input_val.data
            callable_val = ctx.get(comp.Value.from_python("callable"))
            inner_input = ctx.get(comp.Value.from_python("input"))
            inner_args = ctx.get(comp.Value.from_python("args"))
            
            # Invoke: inner_input | callable(inner_args)
            if callable_val is None:
                return comp.Value.from_python(None)
            
            # callable_val is already a Value from struct.get()
            return frame.invoke_block(callable_val, inner_args, inner_input)
        
        wrap_callable = InternalCallable("wrap", _wrap)
        wrap_value = comp.Value(wrap_callable)
        wrap_defn = comp.Definition("wrap", self.token, wrap_value, comp.shape_block)
        wrap_defn.resolved_cop = wrap_value
        wrap_defn.value = wrap_value
        self._definitions['wrap'] = wrap_defn

        # Finalize to build namespace from definitions
        self.finalize()

    def namespace(self):
        # Simple implementation to avoid infinite recursion
        if self._namespace is None:
            self._namespace = {}
            for key, value in self._definitions.items():
                defset = comp._namespace.DefinitionSet()
                defset.definitions.add(value)
                self._namespace[key] = defset
        return self._namespace

    def finalize(self):
        self._finalized = True



# Registry of internal modules
_internal_registered = {}
_internal_modules = {}


def register_internal_module(resource):
    """Decorator for registering internal modules to a create function."""
    def fn(callback):
        _internal_registered[resource] = callback
        return callback
    return fn


def get_internal_module(resource):
    """Get an internal module by name.

    Args:
        resource: The import name (e.g., "cop", "system")

    Returns:
        InternalModule or None: The module if registered, None otherwise
    """
    module = _internal_modules.get(resource)
    if not module:
        if resource == "system":
            module = SystemModule()
        else:
            callback = _internal_registered.get(resource)
            if not callback:
                # Todo, this is begging for an exception?
                return None

            doc = inspect.getdoc(callback) or ""
            module = comp.InternalModule(resource, doc)
            callback(module)
            module.finalize()
        _internal_modules[resource] = module
    return module

