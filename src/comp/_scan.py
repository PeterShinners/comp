"""Lightweight module scanner for imports and metadata"""

__all__ = [
]

import lark
import comp


def scan(source):
    """Scan source and extract module metadata as a Value.

    Returns a Value struct containing:
    - pkg: list of (name, value, pos) cop nodes for pkg.* assignments
    - imports: list of (name, source, compiler, pos) cop nodes for !import statements
    - docs: list of (content, pos) cop nodes for --- blocks and -- line comments

    Uses the scan.lark grammar which is error-resilient.
    """
    parser = comp._parse.lark_parser("scan")
    tree = parser.parse(source)

    pkg_list = []
    import_list = []
    doc_list = []

    for item in tree.children:
        if not isinstance(item, lark.Tree):
            continue

        if item.data == "import_stmt":
            # !import name (source type)
            imp = _scan_import(item)
            if imp:
                import_list.append(imp)
        elif item.data == "assignment":
            # Check if it's a pkg.* assignment
            pkg = _scan_pkg_assignment(item)
            if pkg:
                pkg_list.append(pkg)
        elif item.data == "doc_comment":
            # --- doc block ---
            doc = _scan_doc_comment(item)
            if doc:
                doc_list.append(doc)
        elif item.data == "line_comment":
            # -- line comment
            doc = _scan_line_comment(item)
            if doc:
                doc_list.append(doc)

    # Create Value struct with the results
    result = {
        "pkg": comp.Value.from_python(pkg_list),
        "imports": comp.Value.from_python(import_list),
        "docs": comp.Value.from_python(doc_list),
    }
    return comp.Value.from_python(result)


def _scan_import(node):
    """Extract import info from import_stmt node.

    Returns cop node or None: (name~str source~str compiler~str pos~(num num num num))
    """
    name_token = None
    struct_node = None

    for child in node.children:
        if isinstance(child, lark.Token) and child.type == "TOKENFIELD":
            name_token = child
        elif isinstance(child, lark.Tree) and child.data == "struct":
            struct_node = child

    if not name_token or not struct_node:
        return None

    # Extract source and compiler from struct
    source_val = ""
    compiler_val = ""

    for child in struct_node.children:
        if isinstance(child, lark.Tree):
            if child.data == "text":
                for tok in child.children:
                    if isinstance(tok, lark.Token) and "TEXT_CONTENT" in tok.type:
                        source_val = tok.value
            elif child.data == "identifier":
                for tok in child.children:
                    if isinstance(tok, lark.Token) and tok.type == "TOKENFIELD":
                        compiler_val = tok.value
                        break
        elif isinstance(child, lark.Token) and child.type == "TOKENFIELD":
            if not compiler_val:
                compiler_val = child.value

    # Create cop node with position
    pos = _pos_from_lark(name_token)
    return {
        "name": name_token.value,
        "source": source_val,
        "compiler": compiler_val,
        "pos": pos,
    }


def _scan_pkg_assignment(node):
    """Extract pkg assignment from assignment node.

    Returns cop node or None: (name~str value~str pos~(num num num num))
    """
    if len(node.children) < 3:
        return None

    id_node = node.children[0]
    value_node = node.children[2]

    if not isinstance(id_node, lark.Tree) or id_node.data != "identifier":
        return None

    # Get identifier parts
    parts = []
    for child in id_node.children:
        if isinstance(child, lark.Token) and child.type == "TOKENFIELD":
            parts.append(child.value)

    if not parts or parts[0] != "pkg":
        return None

    name = ".".join(parts)

    # Extract simple value
    value = _scan_simple_value(value_node)
    if value is None:
        return None

    pos = _pos_from_lark(id_node)
    return {
        "name": name,
        "value": value,
        "pos": pos,
    }


def _scan_simple_value(node):
    """Extract simple value from node (text, number, or identifier)."""
    if isinstance(node, lark.Token):
        if node.type == "BLOB":
            return node.value
        return None

    if isinstance(node, lark.Tree):
        if node.data == "text":
            for child in node.children:
                if isinstance(child, lark.Token):
                    # Token types are namespaced when imported from common.lark
                    if "TEXT_CONTENT" in child.type:
                        return child.value
        elif node.data == "number":
            for child in node.children:
                if isinstance(child, lark.Token):
                    return child.value
        elif node.data == "identifier":
            parts = []
            for child in node.children:
                if isinstance(child, lark.Token) and child.type == "TOKENFIELD":
                    parts.append(child.value)
            return ".".join(parts) if parts else None

    return None


def _scan_doc_comment(node):
    """Extract doc comment from doc_comment node (--- block ---).

    Returns dict or None: (content~str pos~(num num num num))
    """
    for child in node.children:
        if isinstance(child, lark.Token) and child.type == "DOC_CONTENT":
            content = child.value.strip()
            pos = _pos_from_lark(child)
            return {
                "content": content,
                "pos": pos,
            }
    return None


def _scan_line_comment(node):
    """Extract line comment from line_comment node (-- line).

    Returns dict or None: (content~str pos~(num num num num))
    """
    for child in node.children:
        if isinstance(child, lark.Token) and child.type == "LINE_CONTENT":
            content = child.value.strip()
            pos = _pos_from_lark(child)
            return {
                "content": content,
                "pos": pos,
            }
    return None


def _pos_from_lark(treetoken):
    """Create the position tuple from a lark Tree or Token value."""
    if isinstance(treetoken, lark.Token):
        token = treetoken
        return (
            token.line,
            token.column,
            token.end_line or token.line,
            token.end_column or token.column,
        )
    elif isinstance(treetoken, lark.Tree):
        meta = treetoken.meta
        return (
            meta.line,
            meta.column,
            meta.end_line or meta.line,
            meta.end_column or meta.column,
        )

