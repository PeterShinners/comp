"""Module represents a module's module at runtime"""

import os

import comp


__all__ = ["Module"]


class Module:
    """A module in the Comp language.

    Namespaces are used to organize and scope identifiers in the language.
    They provide a way to group related definitions and prevent naming conflicts.

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
        
        self.mod_data = None  # eventually a Value
        self.imports = []
        self.local_tags = []
        self.local_funcs = []
        self.local_shapes = []
        self.local_handles = []

        # completed full namespace
        self.ns_tags = {}
        self.ns_funcs = {}
        self.ns_shapes = {}
        self.ns_handles = {}

    def __repr__(self):
        return f"Module<{self.token}>"

    def __hash__(self):
        return id(self.token)

    def finalize(self):
        """Finalize module after all imports and definitions are added.

        This populates the namespace dictionaries for fast lookup.
        """

        local_tags = {}
        found_locals = set()
        for tag in self.local_tags:
            if tag.module is None:
                tag.module = self
            elif tag.module is not self:
                raise comp.ModuleError(f"Tag defined in wrong module: {tag.qualified}")
            if tag.qualified in found_locals:
                raise comp.ModuleError(f"Duplicate local tag definition: {tag.qualified}")
            found_locals.add(tag.qualified)
            add_name_permutations(local_tags, "", tag.qualified, tag)
        for imp in self.imports:
            for tag in imp.module.local_tags:
                if not tag.private:
                    add_name_permutations(self.ns_tags, imp.namespace, tag.qualified, tag)
        self.ns_tags.update(local_tags)

        # Tags are special because any deep definitions should automatically
        # define all intermediate parents. Or should that be the job of the
        # compiler?
        # I don't think functions or shapes or handles work that way

        for tag in self.local_tags:
            self.ns_tags[tag.qualified] = tag

        # Functions can have sparse hierarchy
        local_funcs = {}
        found_local_funcs = set()
        for func in self.local_funcs:
            if func.module is None:
                func.module = self
            elif func.module is not self:
                raise comp.ModuleError(f"Func defined in wrong module: {func.qualified}")
            if func.qualified in found_local_funcs:
                raise comp.ModuleError(f"Duplicate local func definition: {func.qualified}")
            found_local_funcs.add(func.qualified)
            add_name_permutations(local_funcs, "", func.qualified, func)
        for imp in self.imports:
            for func in imp.module.local_funcs:
                if not func.private:
                    add_name_permutations(self.ns_funcs, imp.namespace, func.qualified, func)
        self.ns_funcs.update(local_funcs)

        for func in self.local_funcs:
            self.ns_funcs[func.qualified] = func

        # Shapes can have sparse hierarchy (e.g., "geom.point" without "geom")
        local_shapes = {}
        found_local_shapes = set()
        for shape in self.local_shapes:
            if shape.module is None:
                shape.module = self
            elif shape.module is not self:
                raise comp.ModuleError(f"Shape defined in wrong module: {shape.qualified}")
            if shape.qualified in found_local_shapes:
                raise comp.ModuleError(f"Duplicate local shape definition: {shape.qualified}")
            found_local_shapes.add(shape.qualified)
            add_name_permutations(local_shapes, "", shape.qualified, shape)
        for imp in self.imports:
            for shape in imp.module.local_shapes:
                if not shape.private:
                    add_name_permutations(self.ns_shapes, imp.namespace, shape.qualified, shape)
        self.ns_shapes.update(local_shapes)

        for shape in self.local_shapes:
            self.ns_shapes[shape.qualified] = shape

        # Handles can have sparse hierarchy
        local_handles = {}
        found_local_handles = set()
        for handle in self.local_handles:
            if handle.module is None:
                handle.module = self
            elif handle.module is not self:
                raise comp.ModuleError(f"Handle defined in wrong module: {handle.qualified}")
            if handle.qualified in found_local_handles:
                raise comp.ModuleError(f"Duplicate local handle definition: {handle.qualified}")
            found_local_handles.add(handle.qualified)
            add_name_permutations(local_handles, "", handle.qualified, handle)
        for imp in self.imports:
            for handle in imp.module.local_handles:
                if not handle.private:
                    add_name_permutations(self.ns_handles, imp.namespace, handle.qualified, handle)
        self.ns_handles.update(local_handles)

        for handle in self.local_handles:
            self.ns_handles[handle.qualified] = handle


class Import:
    """Definition of an module import statement.

    Args:
        namespace: (str) Namespace to use for imported module
    
    Defined when a module imports another.
    """
    def __init__(self, namespace, compiler):
        self.namespace = namespace
        self.compiler = compiler
        self.provider = None  # populated by import process
        self.module = None  # populated by import process


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
