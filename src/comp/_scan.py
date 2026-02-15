"""Lightweight module scanner for imports and metadata"""

__all__ = [
]

import hashlib
import lark
import comp


def scan(source):
    """Scan source and extract module metadata as a Value.

    Returns a Value struct containing:
    - definitions: list of (operator, name, pos, body) for all module definitions
    - docs: list of (content, pos) for comments (found anywhere in the tree)

    Uses the scan.lark grammar which is error-resilient.
    """
    parser = comp._parse.lark_parser("scan")
    tree = parser.parse(source)

    definition_list = []
    doc_list = []

    # Walk tree recursively to find all definitions and comments
    def walk(node):
        # Skip tokens (like HASHBANG)
        if isinstance(node, lark.Token):
            return

        if not isinstance(node, lark.Tree):
            return

        if node.data == "mod_definition":
            # !operator name ...
            defn = _scan_mod_definition(node, source)
            if defn:
                definition_list.append(defn)
        elif node.data == "doc_comment":
            # /// doc comment
            doc = _scan_doc_comment(node)
            if doc:
                doc_list.append(doc)
        elif node.data == "line_comment":
            # // line comment
            doc = _scan_line_comment(node)
            if doc:
                doc_list.append(doc)
        elif node.data == "block_comment":
            # /* block comment */
            doc = _scan_block_comment(node)
            if doc:
                doc_list.append(doc)

        # Recursively walk children
        for child in node.children:
            walk(child)

    walk(tree)

    # Create Value struct with the results
    result = {
        "definitions": comp.Value.from_python(definition_list),
        "docs": comp.Value.from_python(doc_list),
    }
    return comp.Value.from_python(result)


def _scan_mod_definition(node, source):
    """Extract module definition info from mod_definition node.

    Returns dict or None: (operator~str name~str pos~(num num num num) body~str)
    """
    if len(node.children) < 2:
        return None

    # First child is the operator token (!import, !func, !shape, etc.)
    operator_token = node.children[0]
    if not isinstance(operator_token, lark.Token):
        return None

    # Extract operator name (remove the ! prefix)
    operator = operator_token.value[1:]  # Remove '!' prefix

    # Second child should be the name (usually an identifier or token)
    name_item = node.children[1]
    name = None
    name_end_line = None
    name_end_col = None

    if isinstance(name_item, lark.Token) and name_item.type == "TOKENFIELD":
        name = name_item.value
        name_end_line = name_item.end_line or name_item.line
        name_end_col = name_item.end_column or name_item.column
    elif isinstance(name_item, lark.Tree):
        if name_item.data == "identifier":
            # Extract first token from identifier
            for child in name_item.children:
                if isinstance(child, lark.Token) and child.type == "TOKENFIELD":
                    name = child.value
                    name_end_line = child.end_line or child.line
                    name_end_col = child.end_column or child.column
                    break
        elif name_item.data == "text":
            # For !package which might have text name
            for child in name_item.children:
                if isinstance(child, lark.Token) and "TEXT_CONTENT" in child.type:
                    name = child.value
                    name_end_line = child.end_line or child.line
                    name_end_col = child.end_column or child.column
                    break

    if not name:
        return None

    # Get position from the operator token through to the end of the node
    # But exclude trailing comments - find the last non-comment child
    last_non_comment = None
    for child in reversed(node.children):
        if isinstance(child, lark.Tree) and child.data in ("doc_comment", "line_comment", "block_comment"):
            continue
        last_non_comment = child
        break

    # Use the last non-comment child for the end position, or fall back to the full node
    if last_non_comment:
        end_pos = _pos_from_lark(last_non_comment)
        pos = (
            operator_token.line,
            operator_token.column,
            end_pos[2],  # end_line from last non-comment
            end_pos[3],  # end_col from last non-comment
        )
    else:
        pos = _pos_from_lark(node)

    # Extract body text directly from source (preserves whitespace)
    # Body starts right after the name and goes to the end of the definition
    body = ""
    if name_end_line and name_end_col:
        # Convert to 0-indexed
        source_lines = source.split('\n')
        body_start_line = name_end_line - 1
        body_start_col = name_end_col
        body_end_line = pos[2] - 1  # pos is (line, col, end_line, end_col)
        body_end_col = pos[3]

        if body_start_line == body_end_line:
            # Single line
            body = source_lines[body_start_line][body_start_col:body_end_col]
        else:
            # Multi-line
            lines = []
            lines.append(source_lines[body_start_line][body_start_col:])
            for i in range(body_start_line + 1, body_end_line):
                lines.append(source_lines[i])
            if body_end_line < len(source_lines):
                lines.append(source_lines[body_end_line][:body_end_col])
            body = '\n'.join(lines)

    # Compute content hash for change detection
    body_hash = hashlib.blake2s(body.encode('utf-8'), digest_size=8).hexdigest()

    return {
        "operator": operator,
        "name": name,
        "pos": pos,
        "body": body,
        "hash": body_hash,
    }


def _scan_doc_comment(node):
    """Extract doc comment from doc_comment node (/// line).

    Returns dict or None: (content~str pos~(num num num num))
    """
    for child in node.children:
        if isinstance(child, lark.Token) and child.type == "LINE_CONTENT":
            content = child.value.strip()
            pos = _pos_from_lark(node)
            return {
                "content": content,
                "pos": pos,
                "type": "doc",
            }
    return None


def _scan_line_comment(node):
    """Extract line comment from line_comment node (// line).

    Returns dict or None: (content~str pos~(num num num num))
    """
    for child in node.children:
        if isinstance(child, lark.Token) and child.type == "LINE_CONTENT":
            content = child.value.strip()
            pos = _pos_from_lark(node)
            return {
                "content": content,
                "pos": pos,
                "type": "line",
            }
    return None


def _scan_block_comment(node):
    """Extract block comment from block_comment node (/* block */).

    Returns dict or None: (content~str pos~(num num num num))
    """
    for child in node.children:
        if isinstance(child, lark.Token) and child.type == "BLOCK_COMMENT":
            # Remove /* and */ delimiters
            content = child.value[2:-2].strip()

            # For JavaDoc-style /** comments, remove leading * and whitespace
            if content.startswith('*'):
                content = content[1:].lstrip()

            pos = _pos_from_lark(node)
            return {
                "content": content,
                "pos": pos,
                "type": "block",
            }
    return None


def _extract_text_from_tree(tree):
    """Recursively extract all text content from a lark Tree."""
    if isinstance(tree, lark.Token):
        return tree.value
    elif isinstance(tree, lark.Tree):
        parts = []
        for child in tree.children:
            parts.append(_extract_text_from_tree(child))
        return "".join(parts)
    return ""


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

