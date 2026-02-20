"""COP (Compiler Operator) tree manipulation and transformation.

COP trees are the intermediate representation between parsing and code generation.
They are similar to AST structures but designed to be easy to manipulate, assemble,
and transform. COP objects are simple comp structures that are easy to serialize.

This module handles:
- COP node creation and inspection
- Identifier resolution (converting identifiers to references)
- Constant folding (compile-time evaluation)
- Definition folding with dependency tracking
- Unparsing (converting COP back to source text)
"""

__all__ = [
    "create_cop",
    "cop_tag",
    "cop_kids",
    "cop_fields",
    "cop_rebuild",
    "cop_unparse",
    "cop_resolve",
]

import decimal
import comp


def create_cop(tag_name, kids, **fields):
    """Create a COP node with the given tag and children.

    Args:
        tag_name: String tag like "value.block" or "mod.define"
        kids: List of child COP nodes
        **fields: Additional named fields

    Returns:
        Value: The constructed COP node
    """
    # Get the Tag object from the cop internal module
    cop_module = comp.get_internal_module("cop")

    tag_definition = cop_module.definitions().get(tag_name)
    if tag_definition is None:
        raise ValueError(f"Unknown COP tag: {tag_name}")

    tag = tag_definition.value.data  # Extract the Tag from the Definition

    data = {comp.Unnamed(): tag}
    for key, value in fields.items():
        data[key] = value
    data["kids"] = comp.Value.from_python(kids)
    value = comp.Value.from_python(data)
    return value


def cop_tag(cop_node):
    """Get the qualified tag name from a COP node.

    Args:
        cop_node: A COP Value node

    Returns:
        str: Qualified tag name like "mod.define", or None if invalid
    """
    try:
        tag = cop_node.positional(0)
        return tag.data.qualified
    except (AttributeError, KeyError, TypeError):
        return None


def cop_kids(cop_node):
    """Get the kids list from a COP node.

    Args:
        cop_node: A COP Value node

    Returns:
        list: List of child COP nodes (empty list if no kids)
    """
    try:
        kids = cop_node.field("kids")
        return list(kids.data.values())
    except (KeyError, AttributeError, TypeError):
        return []


def cop_fields(cop_node):
    """Extract named fields from a COP node (excluding tag and kids).

    Args:
        cop_node: A COP Value node

    Returns:
        dict: Field name -> value mapping
    """
    fields = {}
    for key, val in cop_node.data.items():
        if isinstance(key, comp.Unnamed):
            continue  # Skip the tag
        key_str = key.data if hasattr(key, "data") else key
        if key_str == "kids":
            continue  # Skip kids
        fields[key_str] = val
    return fields


def cop_rebuild(cop_node, kids):
    """Rebuild a COP node with new kids, preserving all other fields.

    Args:
        cop_node: Original COP node
        kids: New list of child nodes

    Returns:
        New COP node with same tag and fields but new kids
    """
    tag = cop_tag(cop_node)
    fields = cop_fields(cop_node)
    return create_cop(tag, kids, **fields)


def _resolve_to_references(cop, namespace, param_names=None):
    """Walk a COP tree and replace value.identifier with value.reference nodes.

    Args:
        cop: The COP node to walk
        namespace: Module namespace dict {name: DefinitionSet}
        param_names: Set of parameter names to skip (handled by codegen)

    Returns:
        Potentially modified COP node
    """
    if cop is None:
        return cop

    param_names = param_names or set()
    tag = cop_tag(cop)

    # Handle value.identifier - replace with value.reference
    if tag == "value.identifier":
        # Extract the qualified name from the identifier
        name = None
        parts = []
        for kid in cop_kids(cop):
            kid_tag = cop_tag(kid)
            if kid_tag in ("ident.token", "ident.text"):
                try:
                    value = kid.field("value").data
                    parts.append(value)
                except (KeyError, AttributeError):
                    break
            else:
                # Complex identifiers not supported yet
                break
        if parts:
            name = '.'.join(parts)

        # Skip if we couldn't extract a name
        if name is None:
            return cop

        # Skip parameter names (handled by codegen)
        if name in param_names:
            return cop

        # Try to resolve from namespace
        definition_set = namespace.get(name)
        if definition_set is not None:
            # Extract Definition from DefinitionSet
            definition = None
            import_namespace = None

            # Try to get a scalar (unambiguous) definition
            scalar_def = definition_set.scalar()
            if scalar_def is not None:
                # Single unambiguous definition
                definition = scalar_def
                # Check if this came from an import
                if hasattr(definition, '_import_namespace'):
                    import_namespace = definition._import_namespace
            else:
                # Multiple definitions - check if they're all invokables (overloaded functions)
                invokables = definition_set.invokables()
                if invokables is not None and len(invokables) > 0:
                    # Create reference with list of all overload qualified names
                    qualified_names = [d.qualified for d in invokables]
                    # Use first definition's module_id (they should all be same module for overloads)
                    module_id = invokables[0].module_id
                    fields = {
                        "qualified": qualified_names,  # List of qualified names for dispatch
                        "module_id": module_id
                    }
                    try:
                        pos = cop.field("pos")
                        if pos is not None:
                            fields["pos"] = pos
                    except (KeyError, AttributeError):
                        pass
                    return create_cop("value.reference", [], **fields)
                # Not all invokables - ambiguous, leave as identifier for error
                return cop

            # Create value.reference node
            if definition is not None:
                fields = {
                    "qualified": definition.qualified,
                    "module_id": definition.module_id
                }
                if import_namespace is not None:
                    fields["namespace"] = import_namespace
                try:
                    pos = cop.field("pos")
                    if pos is not None:
                        fields["pos"] = pos
                except (KeyError, AttributeError):
                    pass
                return create_cop("value.reference", [], **fields)

        # Unresolved - leave as-is (will error at build time)
        return cop

    # Handle value.block - extract parameter names from signature
    elif tag == "value.block":
        kids_list = cop_kids(cop)
        if len(kids_list) >= 2:
            # kid[0] = signature, kid[1] = body
            new_param_names = param_names.copy()
            new_param_names.add('input')
            new_param_names.add('args')
            new_body = _resolve_to_references(kids_list[1], namespace, new_param_names)
            if new_body is not kids_list[1]:
                return cop_rebuild(cop, [kids_list[0], new_body])
        return cop

    # Handle mod.namefield - resolve value child (kid[1]) but not name child (kid[0])
    elif tag == "mod.namefield":
        kids_list = cop_kids(cop)
        if len(kids_list) >= 2:
            new_value = _resolve_to_references(kids_list[1], namespace, param_names)
            if new_value is not kids_list[1]:
                return cop_rebuild(cop, [kids_list[0], new_value])
        return cop

    # For all other nodes, recursively walk kids
    else:
        kids_list = cop_kids(cop)
        new_kids = []
        changed = False
        for kid in kids_list:
            new_kid = _resolve_to_references(kid, namespace, param_names)
            new_kids.append(new_kid)
            if new_kid is not kid:
                changed = True
        if changed:
            return cop_rebuild(cop, new_kids)
        return cop


def cop_resolve(cop, namespace):
    """Resolve identifiers in a COP tree to references.

    This is a convenience wrapper around __resolve_to_references.

    Args:
        cop: COP node to resolve
        namespace: Namespace dict {name: DefinitionSet}

    Returns:
        Resolved COP node
    """
    return _resolve_to_references(cop, namespace)


def cop_unparse(cop):
    """Convert a COP tree back to source code text.

    Args:
        cop: COP node to unparse

    Returns:
        str: Source code representation
    """
    tag = cop_tag(cop)
    kids = cop_kids(cop)

    match tag:
        # Module structure
        case "mod.define":
            parts = []
            for kid in kids:
                parts.append(cop_unparse(kid))
            return "\n".join(parts)
        
        case "mod.namefield":
            if len(kids) >= 2:
                op = cop.to_python("op", "=")
                return f"{cop_unparse(kids[0])} {op} {cop_unparse(kids[1])}"
            return "<?mod.namefield?>"

        # Function structure
        case "function.define":
            parts = []
            if kids:
                parts.append(cop_unparse(kids[0]))       # signature
            if len(kids) >= 2:
                parts.append(cop_unparse(kids[1]))       # body
            return " ".join(parts) if parts else "<?func?>"
        
        case "function.signature":
            parts = []
            for kid in kids:
                parts.append(cop_unparse(kid))
            return " ".join(parts)
        
        case "signature.input":
            parts = []
            for kid in kids:
                parts.append(cop_unparse(kid))
            return " ".join(parts)
        
        case "signature.param":
            try:
                name = cop.to_python("name", "")
                parts = [":param"]
                if name:
                    parts.append(name)
                for kid in kids:
                    parts.append(cop_unparse(kid))
                return " ".join(parts)
            except (KeyError, AttributeError):
                return "<?param?>"
        
        case "signature.block":
            try:
                name = cop.to_python("name", "")
                parts = [":block"]
                if name:
                    parts.append(name)
                for kid in kids:
                    parts.append(cop_unparse(kid))
                return " ".join(parts)
            except (KeyError, AttributeError):
                return "<?block?>"
        
        # Statement structure
        case "statement.define":
            parts = []
            for kid in kids:
                kid_str = cop_unparse(kid)
                parts.append(kid_str)
            if not parts:
                return "()"
            # Check if we need parens
            if len(parts) == 1 and not parts[0].startswith("("):
                return f"({parts[0]})"
            return f"({' '.join(parts)})"
        
        case "statement.field":
            if kids:
                return cop_unparse(kids[0])
            return "<?statement.field?>"
        
        # Block structure
        case "block.signature":
            parts = []
            for kid in kids:
                parts.append(cop_unparse(kid))
            return " ".join(parts)
        
        case "value.block":
            if len(kids) >= 2:
                sig_str = cop_unparse(kids[0])
                body_str = cop_unparse(kids[1])
                return f":{sig_str}{body_str}" if sig_str else f":{body_str}"
            return "<?block?>"
        
        # Value expressions
        case "value.identifier":
            parts = []
            for kid in kids:
                kid_tag = cop_tag(kid)
                if kid_tag == "ident.token":
                    parts.append(kid.field("value").data)
                elif kid_tag == "ident.text":
                    text = kid.field("value").data
                    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
                    parts.append(f'"{escaped}"')
                elif kid_tag == "ident.index":
                    idx = kid.field("value").data
                    parts.append(f"[{idx}]")
                elif kid_tag == "ident.indexpr":
                    expr = cop_unparse(kid.positional(0))
                    parts.append(f"[{expr}]")
                elif kid_tag == "ident.expr":
                    expr = cop_unparse(kid.positional(0))
                    parts.append(f"({expr})")
            return ".".join(parts) if parts else "<?ident?>"
        
        case "ident.token":
            try:
                return cop.field("value").data
            except (KeyError, AttributeError):
                return "<?token?>"
        
        case "value.reference":
            try:
                qualified = cop.field("qualified").data
                try:
                    namespace = cop.field("namespace")
                    if namespace is not None:
                        return f"{namespace.data}.{qualified}"
                except (KeyError, AttributeError):
                    pass
                return qualified
            except (KeyError, AttributeError):
                return "<?ref?>"

        case "value.namespace":
            try:
                qualified = cop.field("qualified").data
                if isinstance(qualified, list):
                    return "|".join(qualified)
                return qualified
            except (KeyError, AttributeError):
                return "<?ns?>"

        case "value.local":
            try:
                name = cop.field("name").data
            except (KeyError, AttributeError):
                name = "<?local?>"
            field_kids = cop_kids(cop)
            if not field_kids:
                return name
            parts = [name]
            for kid in field_kids:
                kid_tag = cop_tag(kid)
                if kid_tag == "ident.token":
                    parts.append(kid.field("value").data)
                elif kid_tag == "ident.index":
                    idx = kid.field("value").data
                    parts.append(f"[{idx}]")
                else:
                    parts.append("<?field?>")
            return ".".join(parts)
        
        case "value.constant":
            try:
                value = cop.field("value")
                return str(value.data)
            except (KeyError, AttributeError):
                return "<?const?>"
        
        case "value.number":
            try:
                return cop.field("value").data
            except (KeyError, AttributeError):
                return "<?num?>"
        
        case "value.text":
            try:
                text = cop.field("value").data
                escaped = text.replace("\\", "\\\\").replace('"', '\\"')
                return f'"{escaped}"'
            except (KeyError, AttributeError):
                return "<?text?>"
        
        case "value.nil":
            return "nil"
        
        # Math and logic operations
        case "value.math.unary":
            if kids:
                op = cop.to_python("op")
                return f"{op}{cop_unparse(kids[0])}"
            return "<?unary?>"

        case "value.logic.unary":
            if kids:
                op = cop.to_python("op")
                return f"{op}{cop_unparse(kids[0])}"
            return "<?logic.unary?>"

        case "value.math.binary":
            if len(kids) >= 2:
                op = cop.to_python("op")
                return f"{cop_unparse(kids[0])}{op}{cop_unparse(kids[1])}"
            return "<?binary?>"

        case "value.compare":
            if len(kids) >= 2:
                op = cop.to_python("op")
                return f"{cop_unparse(kids[0])} {op} {cop_unparse(kids[1])}"
            return "<?compare?>"

        case "value.fallback":
            if len(kids) >= 2:
                op = cop.to_python("op", "??")
                return f"{cop_unparse(kids[0])} {op} {cop_unparse(kids[1])}"
            return "<?fallback?>"
        
        # Pipeline
        case "value.pipeline":
            parts = []
            for kid in kids:
                parts.append(cop_unparse(kid))
            return " | ".join(parts)
        
        # Binding (e.g., foo :bar, foo :x=1)
        case "value.binding":
            if len(kids) >= 2:
                callable_part = cop_unparse(kids[0])

                # Unparse binding arguments directly with : prefix
                # Get children of the struct.define
                binding_kids = cop_kids(kids[1])
                if not binding_kids:
                    # Empty bindings
                    return f"{callable_part} :"

                # Unparse each binding argument
                binding_parts = []
                for binding_kid in binding_kids:
                    binding_tag = cop_tag(binding_kid)
                    if binding_tag == "struct.posfield":
                        # Positional binding: :value
                        posfield_kids = cop_kids(binding_kid)
                        if posfield_kids:
                            binding_parts.append(f":{cop_unparse(posfield_kids[0])}")
                    elif binding_tag == "struct.namefield":
                        # Named binding: :name=value
                        namefield_kids = cop_kids(binding_kid)
                        if len(namefield_kids) >= 2:
                            op = binding_kid.to_python("op", "=")
                            binding_parts.append(f":{cop_unparse(namefield_kids[0])}{op}{cop_unparse(namefield_kids[1])}")
                    else:
                        # Unknown binding type
                        binding_parts.append(f":{cop_unparse(binding_kid)}")

                # Join with spaces
                return f"{callable_part} {' '.join(binding_parts)}"
            return "<?binding?>"
        
        # Field access
        case "value.field":
            if len(kids) >= 2:
                return f"{cop_unparse(kids[0])}.{cop_unparse(kids[1])}"
            return "<?field?>"
        
        # Invoke
        case "value.invoke":
            parts = []
            for kid in kids:
                parts.append(cop_unparse(kid))
            if len(parts) >= 2:
                return f"{parts[0]}({' '.join(parts[1:])})"
            elif len(parts) == 1:
                return f"{parts[0]}()"
            return "<?invoke?>"
        
        # Wrapper
        case "value.wrapper":
            if len(kids) >= 2:
                wrapper = cop_unparse(kids[0])
                value = cop_unparse(kids[1])
                return f"@{wrapper} {value}"
            return "<?wrapper?>"
        
        # Structure
        case "struct.define":
            parts = []
            for kid in kids:
                parts.append(cop_unparse(kid))
            return "{" + " ".join(parts) + "}"
        
        case "struct.namefield":
            if len(kids) >= 2:
                op = cop.to_python("op", "=")
                return f"{cop_unparse(kids[0])}{op}{cop_unparse(kids[1])}"
            return "<?namefield?>"
        
        case "struct.posfield":
            if kids:
                return cop_unparse(kids[0])
            return "<?posfield?>"
        
        # Let statement
        case "op.let":
            if len(kids) >= 2:
                name = cop_unparse(kids[0])
                value = cop_unparse(kids[1])
                return f"!let {name} {value}"
            return "<?let?>"
        
        case "op.on":
            # !on expression branch1 branch2 ...
            # First kid is the expression, rest are branches
            if not kids:
                return "!on"
            parts = ["!on", cop_unparse(kids[0])]
            for branch in kids[1:]:
                parts.append(cop_unparse(branch))
            return " ".join(parts)
        
        case "op.on.branch":
            # Branch is: ~shape expression
            if len(kids) >= 2:
                shape = cop_unparse(kids[0])
                expr = cop_unparse(kids[1])
                # Shape should already have ~ prefix from shape.define
                return f"{shape} {expr}"
            return "<?branch?>"
        
        # Shape
        case "shape.define":
            # Check if any children have name attributes (indicating struct fields)
            def _has_name(kid):
                try:
                    return bool(kid.to_python("name"))
                except (KeyError, TypeError):
                    return False

            has_named_fields = any(
                cop_tag(kid) == "shape.field" and _has_name(kid)
                for kid in kids
            )
            
            parts = []
            for kid in kids:
                parts.append(cop_unparse(kid))
            
            if len(parts) == 1 and not has_named_fields:
                return f"~{parts[0]}"
            elif has_named_fields:
                return "~{" + " ".join(parts) + "}"
            else:
                return "~(" + " ".join(parts) + ")"
        
        case "shape.field":
            # Try to get name attribute, but it may not exist for positional fields
            try:
                name = cop.to_python("name")
            except (KeyError, AttributeError, comp.CodeError):
                name = ""
            
            parts = []
            
            for i, kid in enumerate(kids):
                kid_tag = cop_tag(kid)
                unparsed = cop_unparse(kid)
                
                # Skip empty values and empty shape constants
                if not unparsed or unparsed in ("~()", ""):
                    continue
                
                # If this is a value.identifier as the first real child of a named field,
                # it's the shape type and needs a ~ prefix
                if name and i == 0 and kid_tag == "value.identifier":
                    unparsed = f"~{unparsed}"
                
                parts.append(unparsed)
            
            # Format based on whether field has a name
            if name:
                # Named field: "name ~type[suffix]<limit>*repeat"
                # Space between name and rest
                rest = "".join(parts)
                return f"{name} {rest}" if rest else name
            else:
                # Unnamed/positional field: "type[suffix]<limit>*repeat"
                # No spaces between components
                return "".join(parts) if parts else "<?shape.field?>"
        
        case "shape.union":
            parts = []
            for kid in kids:
                parts.append(cop_unparse(kid))
            return " | ".join(parts)
        
        case "shape.unit":
            if kids:
                return f"[{cop_unparse(kids[0])}]"
            return "<?unit?>"
        
        case "shape.limit":
            # shape.limit has 2 children: identifier and value
            # Format as <name=value>
            if len(kids) >= 2:
                name = cop_unparse(kids[0])
                value = cop_unparse(kids[1])
                return f"<{name}={value}>"
            elif len(kids) == 1:
                return f"<{cop_unparse(kids[0])}>"
            return "<>"
        
        case "shape.value":
            parts = []
            for kid in kids:
                parts.append(cop_unparse(kid))
            return " ".join(parts) if parts else "<?shape.value?>"
        
        case "shape.repeat":
            try:
                op = cop.to_python("op", "*")
                parts = []
                for kid in kids:
                    parts.append(cop_unparse(kid))
                
                # Always start with *, then use op to join numbers
                if len(parts) == 0:
                    return "*"
                elif len(parts) == 1:
                    if op == "+":
                        return f"*{parts[0]}+"
                    else:
                        # op == "=" or "*", both render as *N
                        return f"*{parts[0]}"
                elif len(parts) == 2:
                    # op == "-" for range
                    return f"*{parts[0]}-{parts[1]}"
                return "*" + op.join(parts)
            except (KeyError, AttributeError):
                return "<?repeat?>"
        
        case "shape.default":
            if kids:
                return f" = {cop_unparse(kids[0])}"
            return " ="
        
        # Catch-all
        case _:
            return f"<{tag}>"


