"""Runtime module with definitions and namespace mappings."""

__all__ = ["Module"]

import comp
from . import _func, _shape, _tag


class Module:
    """Runtime module containing tag, function, and shape definitions.

    A module represents a compiled Comp source file with all its definitions
    resolved and ready for execution. Modules track their own definitions
    and imported modules with local namespace aliases.

    Examples:
        >>> import comp
        >>> mod = comp.run.Module("myapp")
        >>> ast = comp.parse_module("!tag #status.active")
        >>> mod.process_ast(ast)
        >>> mod.dump_contents()
        Module: myapp
        Tags:
          #status
          #status.active
    """
    def __init__(self, identifier):
        self.identifier = identifier
        self.tags = {}
        self.funcs = {}
        self.shapes = {}
        self.mods = {}
        # Module scope storage for $mod namespace
        # This is a Value with a struct containing module-level state
        from . import _value
        self.scope = _value.Value(None)  # Empty struct initially
        if self.scope.struct is None:
            self.scope.struct = {}

    def process_ast(self, module_ast):
        """Process a module AST and extract all definitions."""

        # Process tag definitions
        for stmt in module_ast.statements:
            if isinstance(stmt, comp.ast.TagDef):
                self._process_taginition(stmt)
            elif isinstance(stmt, comp.ast.FuncDef):
                self._process_func_definition(stmt)
            elif isinstance(stmt, comp.ast.ShapeDef):
                self._process_shape_definition(stmt)

    def resolve_all(self):
        """Resolve all definitions (evaluate tag expressions, resolve shapes, etc.)."""
        # Resolve tag values
        for tag in self.tags.values():
            tag.resolve(self)

        # Resolve shapes
        for shape in self.shapes.values():
            shape.resolve(self)

        # Resolve function implementations
        for func in self.funcs.values():
            for impl in func.implementations:
                impl.resolve(self)

    def process_builtins(self):
        """Add builtin module namespace to this module.

        Instead of copying builtin functions and tags into this module,
        we add a reference to the shared builtin module in self.mods.
        This ensures singleton tag behavior and proper namespace resolution.

        References without a namespace (e.g., |print, #true) will search:
        1. Current module first
        2. Then all modules in self.mods (including builtin)

        References with a namespace (e.g., |print/builtin) will only search
        that specific namespace.
        """
        # Add reference to the shared builtin module
        from . import builtin
        self.mods["builtin"] = builtin.get_builtin_module()

    def resolve_tag(self, tokens, namespace=None):
        """Resolve a tag reference with namespace support.

        Args:
            tokens: Tag identifier path in child-first order (e.g., ["error", "status"] for #error.status)
            namespace: Optional namespace (e.g., "builtin" for #tag/builtin)

        Returns:
            TagDef if found, None otherwise

        Resolution rules:
            - If namespace is specified: only search that namespace module
            - If no namespace: search current module first, then all mods
            - Partial names match if unambiguous (e.g., #cat matches #animal.pet.cat)

        Note: Tag references use child-first notation (#error.status) but are stored
        parent-first ("status.error"), so we need to reverse the tokens.
        """
        # Reverse tokens from child-first to parent-first for storage lookup
        reversed_tokens = tuple(reversed(tokens))
        tag_name = ".".join(reversed_tokens)

        if namespace:
            # Only search the specified namespace
            if namespace in self.mods:
                return self._match_tag_in_dict(tag_name, self.mods[namespace].tags)
            return None

        # No namespace: search current module first
        match = self._match_tag_in_dict(tag_name, self.tags)
        if match:
            return match

        # Then search all referenced modules
        for mod in self.mods.values():
            match = self._match_tag_in_dict(tag_name, mod.tags)
            if match:
                return match

        return None

    def _match_tag_in_dict(self, partial_name, tags_dict):
        """Match a partial tag name against a dictionary of tags.

        Args:
            partial_name: Partial tag path (e.g., "cat" or "pet.cat")
            tags_dict: Dictionary of tag definitions keyed by full path

        Returns:
            TagDef if exactly one match found, None otherwise

        Matching rules:
            - Exact match always wins
            - Partial match from the end (suffix match)
            - Must be unambiguous (only one match)
        """
        # Try exact match first
        if partial_name in tags_dict:
            return tags_dict[partial_name]

        # Try suffix matching: partial_name must match the end of the full path
        # For example, "cat" matches "animal.pet.cat", "pet.cat" matches "animal.pet.cat"
        matches = []
        for full_name, tag_def in tags_dict.items():
            if full_name == partial_name:
                return tag_def  # Exact match
            # Check if full_name ends with ".partial_name"
            if full_name.endswith("." + partial_name):
                matches.append(tag_def)

        # Return match only if unambiguous
        if len(matches) == 1:
            return matches[0]

        # Ambiguous or no match
        return None

    def resolve_func(self, tokens, namespace=None):
        """Resolve a function reference with namespace support.

        Args:
            tokens: Function identifier path (e.g., ["http", "get"])
            namespace: Optional namespace (e.g., "builtin" for |func/builtin)

        Returns:
            FuncDef if found, None otherwise

        Resolution rules:
            - If namespace is specified: only search that namespace module
            - If no namespace: search current module first, then all mods
        """
        func_name = ".".join(tokens)

        if namespace:
            # Only search the specified namespace
            if namespace in self.mods:
                return self.mods[namespace].funcs.get(func_name)
            return None

        # No namespace: search current module first
        if func_name in self.funcs:
            return self.funcs[func_name]

        # Then search all referenced modules
        for mod in self.mods.values():
            if func_name in mod.funcs:
                return mod.funcs[func_name]

        return None

    def resolve_shape(self, tokens, namespace=None):
        """Resolve a shape reference with namespace support.

        Args:
            tokens: Shape identifier path (e.g., ["user", "profile"])
            namespace: Optional namespace (e.g., "models" for ~shape/models)

        Returns:
            ShapeDef if found, None otherwise

        Resolution rules:
            - If namespace is specified: only search that namespace module
            - If no namespace: search current module first, then all mods
        """
        shape_name = ".".join(tokens)

        if namespace:
            # Only search the specified namespace
            if namespace in self.mods:
                return self.mods[namespace].shapes.get(shape_name)
            return None

        # No namespace: search current module first
        if shape_name in self.shapes:
            return self.shapes[shape_name]

        # Then search all referenced modules
        for mod in self.mods.values():
            if shape_name in mod.shapes:
                return mod.shapes[shape_name]

        return None

    def _process_taginition(self, tag):
        """Extract tag definitions from AST node."""
        parent_path = tag.tokens
        parent_key = ".".join(parent_path)
        self._ensure_tag_hierarchy(parent_path)
        # Store the value expression for later resolution
        if tag.value:
            self.tags[parent_key]._value_expr = tag.value
        body = tag.body
        if body:
            for child in body.kids:
                if isinstance(child, comp.ast.TagChild):
                    self._process_tag_child(child, parent_path)

    def _process_tag_child(self, tag_child, parent_path):
        """Extract tag from child node relative to parent."""
        child_tokens = tag_child.tokens
        full_path = parent_path + child_tokens
        full_key = ".".join(full_path)
        self._ensure_tag_hierarchy(full_path)
        # Store the value expression for later resolution
        if tag_child.value:
            self.tags[full_key]._value_expr = tag_child.value
        body = tag_child.body
        if body:
            for nested_child in body.kids:
                if isinstance(nested_child, comp.ast.TagChild):
                    self._process_tag_child(nested_child, full_path)

    def _ensure_tag_hierarchy(self, identifier):
        """Ensure tag and all parent tags exist in this module."""
        for i in range(1, len(identifier) + 1):
            path = identifier[:i]
            key = ".".join(path)
            if key not in self.tags:
                self.tags[key] = _tag.TagDef(identifier=path, namespace=self.identifier)

    def _process_func_definition(self, func_def: comp.ast.FuncDef):
        """Extract function definition from AST node."""

        key = ".".join(func_def.tokens)
        func = self.funcs.get(key)
        if not func:
            func = self.funcs[key] = _func.FuncDef(identifier=func_def.tokens)
        impl = _func.FuncImpl(ast_node=func_def)
        func.implementations.append(impl)

    def _process_shape_definition(self, shape_def: comp.ast.ShapeDef):
        """Extract shape definition from AST node."""
        key = ".".join(shape_def.tokens)
        runtime_shape = _shape.ShapeDef(identifier=shape_def.tokens)
        self.shapes[key] = runtime_shape

        # Populate fields from the AST node
        _shape.populate_shape_def_fields(runtime_shape, shape_def, self)

    def dump_contents(self):
        """Print formatted contents of this module."""
        print(f"Module: {self.identifier}")
        if self.tags:
            print()
            print(f"Tags {len(self.tags)}:")
            for name, tag in sorted(self.tags.items()):
                print(f"  #{name} = {tag.value}") if tag.value is not None else print(f"  #{name}")
        if self.funcs:
            print()
            print(f"Functions {len(self.funcs)}:")
            for name, func in sorted(self.funcs.items()):
                print(f"  |{name}")
        if self.shapes:
            print()
            print(f"Shapes {len(self.shapes)}:")
            for name, shape in sorted(self.shapes.items()):
                print(f"  ~{name}")
        if self.mods:
            print()
            print(f"Namespaces {len(self.mods)}:")
            for name, module in sorted(self.mods.items()):
                print(f"  {name} -> {module.identifier}")
        if not (self.tags or self.funcs or self.shapes or self.mods):
            print("  (empty)")

    def __repr__(self):
        counts = []
        if self.tags:
            counts.append(f"{len(self.tags)} tags")
        if self.funcs:
            counts.append(f"{len(self.funcs)} funcs")
        if self.shapes:
            counts.append(f"{len(self.shapes)} shapes")

        contents = ", ".join(counts) if counts else "empty"
        return f"Module({self.identifier!r}, {contents})"
