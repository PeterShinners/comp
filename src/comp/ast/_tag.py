"""AST nodes for tag definitions and references."""

__all__ = ["Module", "ModuleOp", "TagDef", "TagChild", "TagValueRef", "ModuleAssign", "DocStatement"]


import comp

from . import _base, _ident, _literal


class Module(_base.AstNode):
    """Module node: collection of module-level definitions.

    Evaluates all module operations (tag definitions, function definitions, etc.)
    and builds a runtime Module object. The module operations are evaluated in
    order, allowing later definitions to reference earlier ones.

    Args:
        operations: List of module-level operations (TagDef, FuncDef, etc.)
    """

    def __init__(self, operations: list['ModuleOp']):
        if not isinstance(operations, list):
            raise TypeError("Module operations must be a list")
        if not all(isinstance(op, ModuleOp) for op in operations):
            raise TypeError("All operations must be ModuleOp instances")

        self.operations = operations

    def evaluate(self, frame):
        """Evaluate all module operations to build the runtime module.

        Uses existing prepared module from mod_* scopes if available,
        otherwise creates a new Module. This allows prepare() to pre-populate
        definitions that evaluation will then fill in with actual values.

        Returns:
            Module entity containing all registered definitions
        """
        # Try to get existing prepared module from scope
        # If prepare() was called and module was passed to engine.run(),
        # it will be available in the module scope
        module = frame.scope('module')
        
        # If no prepared module exists, create a new one
        if module is None:
            module = comp.Module()

        # IMPORTANT: Evaluate in phases to ensure dependencies are met:
        # Phase 1: Tags and handles (shapes and functions depend on these)
        # Phase 2: Shape definitions (functions reference shapes in their signatures)
        # Phase 3: Everything else (functions, module assigns, etc.)
        #
        # DocStatements are evaluated immediately before their target definition
        # to ensure pending_doc is set right when the definition consumes it.
        from . import _shape, _function, _handle

        # Phase 1: Evaluate TagDef, HandleDef operations and their preceding DocStatements
        # Tags and handles can't depend on shapes or functions, so evaluate them first
        for i, op in enumerate(self.operations):
            if isinstance(op, TagDef) or isinstance(op, _handle.HandleDef):
                # Check if there's a DocStatement right before this tag/handle
                if i > 0 and isinstance(self.operations[i-1], DocStatement):
                    # Evaluate the doc first
                    doc_result = yield comp.Compute(self.operations[i-1], module=module)
                    if frame.bypass_value(doc_result):
                        return doc_result
                # Now evaluate the tag/handle
                result = yield comp.Compute(op, module=module)
                if frame.bypass_value(result):
                    return result

        # Phase 2: Evaluate ShapeDef operations and their preceding DocStatements
        # Shapes can reference tags (from phase 1) but not functions
        for i, op in enumerate(self.operations):
            if isinstance(op, _shape.ShapeDef):
                # Check if there's a DocStatement right before this shape
                if i > 0 and isinstance(self.operations[i-1], DocStatement):
                    # Check if doc was already evaluated in phase 1 (if it preceded a tag/handle)
                    prev_op = self.operations[i-1]
                    if not (isinstance(prev_op, DocStatement)):
                        # This shouldn't happen, but skip if somehow already evaluated
                        pass
                    else:
                        # Evaluate the doc first
                        doc_result = yield comp.Compute(self.operations[i-1], module=module)
                        if frame.bypass_value(doc_result):
                            return doc_result
                # Now evaluate the shape
                result = yield comp.Compute(op, module=module)
                if frame.bypass_value(result):
                    return result

        # Phase 3: Evaluate all other operations (FuncDef, ImportDef, ModuleAssign, etc.)
        # Process in source order to preserve doc-before-definition pairing
        for i, op in enumerate(self.operations):
            # Skip tags/handles (phase 1) and shapes (phase 2)
            if isinstance(op, TagDef) or isinstance(op, _handle.HandleDef) or isinstance(op, _shape.ShapeDef):
                continue
            if isinstance(op, DocStatement):
                # Check if this doc precedes a tag/handle or shape (already evaluated)
                if i < len(self.operations) - 1:
                    next_op = self.operations[i+1]
                    if isinstance(next_op, (TagDef, _handle.HandleDef, _shape.ShapeDef)):
                        continue
            # Evaluate this operation
            result = yield comp.Compute(op, module=module)
            if frame.bypass_value(result):
                return result

        # Return the populated module
        return module

    def unparse(self) -> str:
        """Convert back to source code."""
        return "\n".join(op.unparse() for op in self.operations)

    def __repr__(self):
        return f"Module({len(self.operations)} ops)"


class ModuleOp(_base.AstNode):
    """Base class for module-level operations.

    Module operations register definitions in the module being built.
    They receive a 'module' scope containing the runtime Module with
    tags, shapes, and functions registries.

    Subclasses:
    - TagDef: Tag definitions
    - FuncDef: Function definitions
    - ShapeDef: Shape definitions
    - ImportDef: Import statements
    """
    pass


class TagDef(ModuleOp):
    """Tag definition: !tag #path.to.tag = value {...}

    Defines a tag in the module hierarchy. Tags can have:
    - A value (any expression that evaluates to a Value)
    - Children (nested tag definitions)
    - A generator function (for auto-generating values) - not implemented yet
    - An extends reference (tag from another module to extend)

    The path is stored in definition order (root to leaf), e.g.,
    ["status", "error", "timeout"] for !tag #timeout.error.status

    Multiple definitions of the same tag merge - later values override earlier ones.

    Args:
        path: Full path in definition order, e.g., ["status", "error", "timeout"]
        value: Optional expression that evaluates to tag's value
        children: List of nested TagChild definitions
        generator: Optional generator function (not implemented)
        extends_ref: Optional tag reference to extend (e.g., #fail/builtin)
    """

    def __init__(self, path: list[str], value: _base.ValueNode | None = None,
                 children: list['TagChild'] | None = None,
                 generator: _base.ValueNode | None = None,
                 extends_ref: 'TagRef | None' = None,
                 is_private: bool = False):
        if not path:
            raise ValueError("Tag path cannot be empty")
        if not all(isinstance(name, str) for name in path):
            raise TypeError("Tag path must be list of strings")
        if value is not None and not isinstance(value, _base.ValueNode):
            raise TypeError("Tag value must be ValueNode or None")
        if children is not None:
            if not isinstance(children, list):
                raise TypeError("Tag children must be list or None")
            if not all(isinstance(c, TagChild) for c in children):
                raise TypeError("All children must be TagChild instances")
        if generator is not None and not isinstance(generator, _base.ValueNode):
            raise TypeError("Tag generator must be ValueNode or None")
        # extends_ref validation skipped - it should be a TagRef but we can't import it here

        self.path = path
        self.value = value
        self.children = children or []
        self.generator = generator
        self.extends_ref = extends_ref
        self.is_private = is_private

    def evaluate(self, frame):
        """Register this tag and its children in the module.

        1. Get module from module scope
        2. Evaluate value expression if present (unless extends_ref is set)
        3. Resolve extends_ref if present
        4. Register tag in module with extends_def
        5. Recursively process children
        """
        # Get module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("TagDef requires module scope")

        # Resolve extends_ref if present
        extends_def = None
        if self.extends_ref is not None:
            # Evaluate the tag reference to get a Value containing a TagRef
            extends_value = yield comp.Compute(self.extends_ref)
            if frame.bypass_value(extends_value):
                return extends_value
            
            # Extract the scalar value (should be a TagRef)
            extends_value = extends_value.as_scalar()
            
            # Check if it's a tag
            if not extends_value.is_tag:
                return comp.fail(f"Tag extends must reference a tag, got {type(extends_value.data)}")
            
            # The data is a TagRef, which has a tag_def attribute
            tag_ref = extends_value.data
            if not hasattr(tag_ref, 'tag_def'):
                return comp.fail(f"Tag extends must reference a valid tag, got {type(tag_ref)}")
            
            extends_def = tag_ref.tag_def

        # Evaluate value if present (extends tags cannot have explicit values)
        # Tag values are evaluated in pure context to prevent side effects
        tag_value = None
        if self.value is not None:
            if extends_def is not None:
                return comp.fail("Tag with 'extends' cannot have an explicit value")
            tag_value = yield comp.Compute(self.value, pure_context=True)
            if frame.bypass_value(tag_value):
                return tag_value

        # Register this tag with extends_def
        tag_def = module.define_tag(self.path, tag_value, is_private=self.is_private)
        
        # Set extends_def if we have one
        if extends_def is not None:
            tag_def.extends_def = extends_def

        # Process children - they extend the path
        if self.children:
            for child in self.children:
                # Child paths are relative to this tag
                result = yield comp.Compute(child, module=module, parent_path=self.path)
                if frame.bypass_value(result):
                    return result

        return comp.Value(True)

    def unparse(self) -> str:
        """Convert back to source code."""
        parts = ["!tag", "#" + ".".join(reversed(self.path))]  # Reverse for reference notation

        if self.generator:
            parts.append(self.generator.unparse())

        if self.value or self.children:
            parts.append("=")

        if self.value:
            parts.append(self.value.unparse())

        if self.children:
            children_str = " ".join(c.unparse() for c in self.children)
            parts.append(f"{{{children_str}}}")

        return " ".join(parts)

    def __repr__(self):
        path_str = ".".join(self.path)
        return f"TagDef({path_str})"


class TagChild(ModuleOp):
    """Nested tag definition within a tag body.

    Similar to TagDef but used inside tag bodies. The path is relative
    to the parent tag's path.

    Example:
        !tag #status = {
            #active = 1      <- TagChild with path=["active"]
            #error = {       <- TagChild with path=["error"], has children
                #timeout     <- TagChild with path=["timeout"]
            }
        }

    Args:
        path: Relative path (single name or multiple for deep nesting)
        value: Optional expression for the tag's value
        children: Nested children (for hierarchies)
    """

    def __init__(self, path: list[str], value: _base.ValueNode | None = None,
                 children: list['TagChild'] | None = None,
                 is_private: bool = False):
        if not path:
            raise ValueError("TagChild path cannot be empty")
        if not all(isinstance(name, str) for name in path):
            raise TypeError("TagChild path must be list of strings")
        if value is not None and not isinstance(value, _base.ValueNode):
            raise TypeError("TagChild value must be ValueNode or None")
        if children is not None:
            if not isinstance(children, list):
                raise TypeError("TagChild children must be list or None")
            if not all(isinstance(c, TagChild) for c in children):
                raise TypeError("All children must be TagChild instances")

        self.path = path
        self.value = value
        self.children = children or []
        self.is_private = is_private

    def evaluate(self, frame):
        """Register this child tag in the module.

        Combines parent_path from scope with this child's relative path.
        """
        # Get module and parent path from scope
        module = frame.scope('module')
        parent_path = frame.scope('parent_path')

        if module is None:
            return comp.fail("TagChild requires module scope")
        if parent_path is None:
            return comp.fail("TagChild requires parent_path scope")

        # Build full path: parent + child
        full_path = parent_path + self.path

        # Evaluate value if present
        tag_value = None
        if self.value is not None:
            tag_value = yield comp.Compute(self.value)
            if frame.bypass_value(tag_value):
                return tag_value

        # Register tag
        module.define_tag(full_path, tag_value, is_private=self.is_private)

        # Process children
        if self.children:
            for child in self.children:
                result = yield comp.Compute(child, module=module, parent_path=full_path)
                if frame.bypass_value(result):
                    return result

        return comp.Value(True)

    def unparse(self) -> str:
        """Convert back to source code."""
        parts = ["#" + ".".join(reversed(self.path))]  # Reverse for reference notation

        if self.value or self.children:
            parts.append("=")

        if self.value:
            parts.append(self.value.unparse())

        if self.children:
            children_str = " ".join(c.unparse() for c in self.children)
            parts.append(f"{{{children_str}}}")

        return " ".join(parts)

    def __repr__(self):
        path_str = ".".join(self.path)
        return f"TagChild({path_str})"


class TagValueRef(_base.ValueNode):
    """Tag reference as a value: #status.error.timeout

    References are written in natural order and stored as a list for matching.
    The lookup uses partial suffix matching (last N elements of definition path).

    Examples:
        #active              -> ["active"]
        #error.timeout       -> ["error", "timeout"]
        #status.error.timeout -> ["status", "error", "timeout"]

    Args:
        path: Path in natural order, e.g., ["status", "error", "timeout"]
        namespace: Optional module namespace for cross-module refs (future)

    Attributes:
        _resolved: Pre-resolved TagDefinition (set by Module.prepare())
    """

    def __init__(self, path: list[str], namespace: str | _base.ValueNode | None = None):
        if not path:
            raise ValueError("Tag reference path cannot be empty")
        if not all(isinstance(name, str) for name in path):
            raise TypeError("Tag path must be list of strings")
        if namespace is not None and not isinstance(namespace, (str, _base.ValueNode)):
            raise TypeError("Tag namespace must be string, ValueNode, or None")

        self.path = path
        self.namespace = namespace
        self._resolved = None  # Pre-resolved definition (set by Module.prepare())

    def evaluate(self, frame):
        """Look up tag in module and return as a Value.

        Uses pre-resolved definition if available (from Module.prepare()),
        otherwise falls back to runtime lookup.

        Uses partial path matching to find the tag. If the reference is
        ambiguous (multiple matches), returns a failure.

        If namespace is provided (/namespace), searches only in that namespace.
        Otherwise, searches local module first, then all imported namespaces.
        """
        # Fast path: use pre-resolved definition if available
        if self._resolved is not None:
            tag_def = self._resolved
            # Return the TagRef itself wrapped in a Value
            return comp.Value(comp.TagRef(tag_def))
            yield  # Make this a generator (unreachable)

        # Slow path: runtime lookup (for modules not prepared)
        # Resolve namespace if it's a ValueNode (dynamic dispatch)
        resolved_namespace = None
        if self.namespace is not None:
            if isinstance(self.namespace, str):
                # Static namespace reference
                resolved_namespace = self.namespace
            else:
                # Dynamic namespace dispatch - evaluate the node to get a tag or handle
                namespace_value = yield comp.Compute(self.namespace)
                if frame.bypass_value(namespace_value):
                    return namespace_value
                
                # Extract the defining module from the tag or handle
                namespace_value = namespace_value.as_scalar()
                if namespace_value.is_tag:
                    # Get the tag's defining module
                    tag_ref = namespace_value.data
                    defining_module = tag_ref.tag_def.module
                    resolved_namespace = defining_module
                elif namespace_value.is_handle:
                    # Get the handle's defining module
                    handle_inst = namespace_value.data
                    defining_module = handle_inst.handle_def.module
                    resolved_namespace = defining_module
                else:
                    return comp.fail(f"Namespace dispatch requires tag or handle, got {type(namespace_value.data).__name__}")
        
        # Get module from frame
        module = frame.scope('module')
        if module is None:
            return comp.fail("Tag references require module scope")

        # Look up tag by partial path with namespace support
        # If resolved_namespace is a Module, need to look up directly in that module
        if isinstance(resolved_namespace, comp.Module):
            # Direct dispatch to a specific module
            try:
                tag_def = resolved_namespace.lookup_tag(self.path, namespace=None, local_only=False)
            except ValueError as e:
                # Not found or ambiguous reference
                return comp.fail(str(e))
        else:
            # String namespace or None - use normal lookup
            try:
                tag_def = module.lookup_tag(self.path, resolved_namespace)
            except ValueError as e:
                # Not found or ambiguous reference
                return comp.fail(str(e))

        # Return the TagRef itself wrapped in a Value
        return comp.Value(comp.TagRef(tag_def))
        yield  # Make this a generator (unreachable)

    def unparse(self) -> str:
        """Convert back to source code."""
        ref = "#" + ".".join(self.path)
        if self.namespace:
            if isinstance(self.namespace, str):
                ref += "/" + self.namespace
            else:
                ref += "/" + self.namespace.unparse()
        return ref

    def __repr__(self):
        path_str = ".".join(self.path)
        if self.namespace:
            if isinstance(self.namespace, str):
                return f"TagValueRef(#{path_str}/{self.namespace})"
            else:
                return f"TagValueRef(#{path_str}/{self.namespace!r})"
        return f"TagValueRef(#{path_str})"


class ModuleAssign(ModuleOp):
    """Module-level assignment: $mod.field.path = value

    Assigns a value to the module's $mod scope at module definition time.
    Only allows assignments to $mod (enforced at evaluation time).
    Values must be simple expressions (same as tag values - literals, references, arithmetic).

    Examples:
        $mod.server.port = 8000
        $mod.version = "1.0.0"
        $mod.config.debug = #false

    Args:
        path: List of field nodes representing the assignment path
        value: Expression that evaluates to the value (must be simple like tag values)

    Note:
        The grammar accepts any identifier, but evaluation will fail if it doesn't
        start with $mod. This allows better error messages.
    """

    def __init__(self, path: list, value: _base.ValueNode):
        if not isinstance(path, list) or not path:
            raise TypeError("ModuleAssign path must be a non-empty list")
        if not isinstance(value, _base.ValueNode):
            raise TypeError("ModuleAssign value must be a ValueNode")

        self.path = path
        self.value = value

    def evaluate(self, frame):
        """Assign value to $mod scope in the module.

        1. Validate that path starts with $mod scope
        2. Evaluate the value expression
        3. Navigate/create nested structs in $mod as needed
        4. Assign the value at the final path location
        """
        # Validate that first element is a ScopeField for 'mod'
        if not isinstance(self.path[0], _ident.ScopeField):
            return comp.fail("Module assignment must start with a scope (e.g., $mod)")

        scope_field = self.path[0]
        if scope_field.scope_name != 'mod':
            return comp.fail(f"Module assignment only allowed for $mod, not ${scope_field.scope_name}")

        if len(self.path) < 2:
            return comp.fail("Module assignment must specify a field path (e.g., $mod.field)")

        # Get the module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("ModuleAssign requires module scope")

        # Get or create $mod scope on the module
        # The module should have a mod_scope attribute that is a Value({})
        if not hasattr(module, 'mod_scope'):
            module.mod_scope = comp.Value({})

        # Evaluate the value with disarm_bypass=True to allow fail tags in module constants
        # Use pure_context=True to prevent side effects in module constants
        # Don't check bypass_value since we explicitly disarmed the evaluation
        value_result = yield comp.Compute(self.value, disarm_bypass=True, pure_context=True)

        # Navigate the path (skipping the $mod ScopeField)
        current_dict = module.mod_scope.struct
        field_path = self.path[1:]  # Skip $mod

        # Walk all but the last field, creating nested structs as needed
        for field_node in field_path[:-1]:
            # Get the key for this path segment
            key_value = yield from self._evaluate_path_field(frame, field_node, current_dict)
            if frame.bypass_value(key_value):
                return key_value

            # Navigate or create nested struct
            if key_value in current_dict:
                current_value = current_dict[key_value]
                if not current_value.is_struct:
                    # Replace non-struct with empty struct
                    current_value = comp.Value({})
                    current_dict[key_value] = current_value
                current_dict = current_value.struct
            else:
                # Create new nested struct
                new_struct = comp.Value({})
                current_dict[key_value] = new_struct
                current_dict = new_struct.struct

        # Handle the final field
        final_field = field_path[-1]
        final_key = yield from self._evaluate_path_field(frame, final_field, current_dict)
        if frame.bypass_value(final_key):
            return final_key

        # Assign the value at the final key
        current_dict[final_key] = value_result
        return comp.Value(True)

    def _evaluate_path_field(self, frame, field_node, current_dict):
        """Evaluate a field node to get its key value.

        Handles TokenField, IndexField, ComputeField, and String nodes.
        """
        if isinstance(field_node, _ident.TokenField):
            # TokenField: use the field name directly as a string key
            return comp.Value(field_node.name)
        elif isinstance(field_node, _ident.IndexField):
            # IndexField: get existing key at that position
            # Note: field_node.index can be either an int or a ValueNode (for computed indexes)
            if isinstance(field_node.index, int):
                # Static index
                keys_list = list(current_dict.keys())
                if not (0 <= field_node.index < len(keys_list)):
                    return comp.fail(
                        f"Index #{field_node.index} out of bounds "
                        f"(dict has {len(keys_list)} fields)"
                    )
                return keys_list[field_node.index]
            else:
                # Computed index - evaluate it first
                index_value = yield comp.Compute(field_node.index)
                if frame.bypass_value(index_value):
                    return index_value
                # Then get the key at that position
                if not index_value.is_num:
                    return comp.fail(f"Index must be a number, got {index_value}")
                idx = int(index_value.num)
                keys_list = list(current_dict.keys())
                if not (0 <= idx < len(keys_list)):
                    return comp.fail(
                        f"Index #{idx} out of bounds "
                        f"(dict has {len(keys_list)} fields)"
                    )
                return keys_list[idx]
        elif isinstance(field_node, _ident.ComputeField):
            # ComputeField: evaluate its expression to get the key
            key_value = yield comp.Compute(field_node.expr)
            return key_value
        elif isinstance(field_node, _literal.String):
            # String literal: use as key directly
            return comp.Value(field_node.value)
        else:
            # Other nodes: evaluate normally
            key_value = yield comp.Compute(field_node)
            return key_value

    def unparse(self) -> str:
        """Convert back to source code."""
        # Reconstruct the path
        path_parts = []
        for field in self.path:
            if isinstance(field, _ident.ScopeField):
                path_parts.append(f"${field.scope_name}")
            elif isinstance(field, _ident.TokenField):
                path_parts.append(field.name)
            else:
                path_parts.append(field.unparse())

        path_str = ".".join(path_parts)
        return f"{path_str} = {self.value.unparse()}"

    def __repr__(self):
        return f"ModuleAssign({len(self.path)} fields)"


class DocStatement(ModuleOp):
    """Documentation statement: !doc "text", !doc impl "text", or !doc module "text"

    Attaches documentation to the module or to the next definition (function, shape, tag, etc.).
    The documentation is stored temporarily and applied when the next definition is processed.

    Three forms:
    - Module: !doc module "description" (for the module itself)
    - General: !doc "description" (for next definition)
    - Implementation-specific: !doc impl "description" (for polymorphic functions)

    Examples:
        !doc module "Math utilities module"

        !doc "Calculate square root"
        !func |sqrt ~{~num} = {...}

        !doc impl "Optimized for integers"
        !func |sqrt ~{~int} = {...}

    Args:
        text: Documentation string
        is_impl: True if this is implementation-specific documentation
        is_module: True if this is module-level documentation
    """

    def __init__(self, text: str, is_impl: bool = False, is_module: bool = False):
        if not isinstance(text, str):
            raise TypeError("Documentation text must be a string")
        self.text = text
        self.is_impl = is_impl
        self.is_module = is_module

    def evaluate(self, frame):
        """Store documentation for the module or next definition.

        For module documentation, stores directly on the module.
        For definition documentation, stores in pending_doc for the next definition.
        """
        # Get module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("DocStatement requires module scope")

        # Handle module-level documentation
        if self.is_module:
            module.doc = self.text
        # Handle pending documentation for next definition
        elif self.is_impl:
            module.pending_impl_doc = self.text
        else:
            module.pending_doc = self.text

        return comp.Value(True)
        yield  # Make this a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        if self.is_module:
            return f'!doc module "{self.text}"'
        elif self.is_impl:
            return f'!doc impl "{self.text}"'
        return f'!doc "{self.text}"'

    def __repr__(self):
        if self.is_module:
            return "DocStatement(module)"
        elif self.is_impl:
            return "DocStatement(impl)"
        return "DocStatement(general)"

