"""Comp Module Scanner - Metadata extraction using Lark parser.

This scanner extracts module metadata:
- Package info (name, version, description, and nested fields)
- Import declarations
- Module documentation

It's designed to be error-resilient: syntax errors in one part of
the file don't prevent extraction from other parts.
"""

import pathlib
import lark

# Grammar file location
GRAMMAR_PATH = pathlib.Path(__file__).parent / "lark" / "scan.lark"

class ImportDef:
    """An import declaration.

    Attributes:
        name: (str) Import name
        source: (str) Source path or module
        import_type: (str) Type like "comp", "stdlib", "python"
        line: (int) Line number in source
    """
    __slots__ = ("name", "source", "import_type", "line")
    def __init__(self, name, source, import_type, line=0):
        self.name = name
        self.source = source
        self.import_type = import_type
        self.line = line

class DocComment:
    """A documentation or comment block.

    Attributes:
        content: (str) The comment content
        line: (int) Line number where comment starts
        column: (int) Column where comment starts
    """
    __slots__ = ("content", "line", "column")
    def __init__(self, content, line, column):
        self.content = content
        self.line = line
        self.column = column

class ModuleMetadata:
    """Extracted module metadata.

    Attributes:
        pkg: (dict) Package info (flattened - nested structs become dotted paths)
        imports: (list) Import declarations
        module_doc: (str | None) Full module documentation
        doc_summary: (str | None) First line of module_doc
        doc_comments: (list) All doc/comment blocks with location
        scan_errors: (list) Errors encountered (non-fatal)
    """
    __slots__ = ("pkg", "imports", "module_doc", "doc_summary", "doc_comments", "scan_errors")
    def __init__(self):
        self.pkg = {}
        self.imports = []
        self.module_doc = None
        self.doc_summary = None
        self.doc_comments = []
        self.scan_errors = []
    @property
    def pkg_name(self):
        """(str | None) Package name from pkg.name."""
        return self.pkg.get("pkg.name")
    @property
    def pkg_version(self):
        """(str | None) Package version from pkg.version."""
        return self.pkg.get("pkg.version")
    @property
    def pkg_description(self):
        """(str | None) Package description from pkg.description."""
        return self.pkg.get("pkg.description")

def get_parser():
    """Load the grammar using the parser function from _parse.py."""
    import comp._parse
    return comp._parse._lark_parser("scan")

class ModuleScanner:
    """Lark-based scanner for Comp module metadata.

    Uses the scan.lark grammar for parsing with error recovery
    for files with syntax issues.
    """
    _parser = None
    @classmethod
    def _get_parser(cls):
        """Lazy-load the parser using parser() from _parse.py."""
        if cls._parser is None:
            cls._parser = get_parser()
        return cls._parser
    @classmethod
    def scan(cls, source):
        """Scan source code and extract module metadata.

        This is resilient to errors - problems in one area won't
        prevent extraction from other areas.

        Args:
            source: (str) Source code to scan

        Returns:
            (ModuleMetadata) Extracted metadata
        """
        meta = ModuleMetadata()
        parser = cls._get_parser()
        tree = None
        try:
            tree = parser.parse(source)
        except Exception as e:
            meta.scan_errors.append(f"Full parse failed: {e}")
            tree = cls._try_partial_parse(parser, source, meta)
        if tree is None:
            return meta
        cls._extract_from_tree(tree, meta)
        return meta
    @classmethod
    def scan_file(cls, path):
        """Scan a .comp file and extract metadata.

        Args:
            path: (pathlib.Path) Path to file

        Returns:
            (ModuleMetadata) Extracted metadata
        """
        source = path.read_text(encoding="utf-8")
        return cls.scan(source)
    @classmethod
    def _try_partial_parse(cls, parser, source, meta):
        for try_len in [4000, 2000, 1000, 600, 400, 200, 100]:
            if try_len >= len(source):
                continue
            try:
                truncated = cls._find_safe_truncation(source, try_len)
                tree = parser.parse(truncated)
                return tree
            except Exception:
                continue
        return None
    @classmethod
    def _find_safe_truncation(cls, content, max_len):
        if len(content) <= max_len:
            return content
        truncated = content[:max_len]
        last_doc_end = truncated.rfind("---")
        if last_doc_end > 0:
            before = truncated[:last_doc_end]
            doc_open = before.rfind("---")
            if doc_open >= 0:
                end_pos = last_doc_end + 3
                next_nl = truncated.find("\n", end_pos)
                if next_nl > 0:
                    return truncated[:next_nl]
                return truncated[:end_pos]
        lines = truncated.split("\n")
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if not line or line.endswith(")") or line.startswith("--"):
                return "\n".join(lines[: i + 1])
        last_nl = truncated.rfind("\n")
        if last_nl > 100:
            return truncated[:last_nl]
        return truncated
    @classmethod
    def _extract_from_tree(cls, tree, meta):
        for item in tree.children:
            if isinstance(item, lark.Tree):
                if item.data == "doc_comment":
                    cls._extract_doc_comment(item, meta)
                elif item.data == "import_stmt":
                    cls._extract_import_stmt(item, meta)
                elif item.data == "assignment":
                    cls._extract_assignment(item, meta)
                elif item.data == "comment":
                    cls._extract_comment(item, meta)
    @classmethod
    def _extract_doc_comment(cls, node, meta):
        if meta.module_doc is not None:
            return
        for child in node.children:
            if isinstance(child, lark.Token) and child.type == "DOC_CONTENT":
                meta.module_doc = child.value.strip()
                lines = meta.module_doc.split("\n")
                meta.doc_summary = lines[0].strip() if lines else None
                meta.doc_comments.append(
                    DocComment(
                        content=child.value.strip(),
                        line=child.line if hasattr(child, "line") else 0,
                        column=child.column if hasattr(child, "column") else 0,
                    )
                )
                break
    @classmethod
    def _extract_comment(cls, node, meta):
        for child in node.children:
            if isinstance(child, lark.Token) and child.type == "COMMENT_CONTENT":
                meta.doc_comments.append(
                    DocComment(
                        content=child.value.strip(),
                        line=child.line if hasattr(child, "line") else 0,
                        column=child.column if hasattr(child, "column") else 0,
                    )
                )
    @classmethod
    def _extract_import_stmt(cls, node, meta):
        """Extract !import name (source type) statement."""
        if len(node.children) < 2:
            return
        # node.children[0] is IMPORT_KEY token
        # node.children[1] should be TOKENFIELD (the name)
        # node.children[2] should be struct (source type)
        name_token = None
        struct_node = None

        for child in node.children:
            if isinstance(child, lark.Token) and child.type == "TOKENFIELD":
                name_token = child
            elif isinstance(child, lark.Tree) and child.data == "struct":
                struct_node = child

        if name_token and struct_node:
            info = cls._extract_import_struct(struct_node)
            meta.imports.append(
                ImportDef(
                    name=name_token.value,
                    source=info.get("source", ""),
                    import_type=info.get("type", ""),
                    line=getattr(name_token, "line", 0),
                )
            )

    @classmethod
    def _extract_assignment(cls, node, meta):
        if len(node.children) < 3:
            return
        id_node = node.children[0]
        value_node = node.children[2]
        if not isinstance(id_node, lark.Tree) or id_node.data != "identifier":
            return
        parts = cls._get_identifier_parts(id_node)
        if not parts:
            return
        # No longer handle import.x assignments - they use !import now
        if parts[0] == "pkg":
            cls._extract_pkg(parts, value_node, meta)
    @classmethod
    def _extract_import(cls, parts, value_node, meta, id_node):
        import_name = ".".join(parts[1:])
        if isinstance(value_node, lark.Tree) and value_node.data == "struct":
            info = cls._extract_import_struct(value_node)
            line = getattr(id_node.children[0], "line", 0) if id_node.children else 0
            meta.imports.append(
                ImportDef(
                    name=import_name,
                    source=info.get("source", ""),
                    import_type=info.get("type", ""),
                    line=line,
                )
            )
    @classmethod
    def _extract_import_struct(cls, struct_node):
        info = {"source": "", "type": ""}
        # In scan.lark, the struct contains item nodes which can be text, identifier, etc.
        for child in struct_node.children:
            if isinstance(child, lark.Tree):
                if child.data == "text":
                    text_val = cls._get_text_value(child)
                    info["source"] = text_val or ""
                elif child.data == "identifier":
                    parts = cls._get_identifier_parts(child)
                    if parts:
                        info["type"] = parts[0]
            elif isinstance(child, lark.Token):
                # Handle direct text tokens and BLOBs
                if child.type in ("SHORT_TEXT_CONTENT", "LONG_TEXT_CONTENT"):
                    info["source"] = child.value
                elif child.type == "TOKENFIELD":
                    # This is likely the type field
                    if not info["type"]:
                        info["type"] = child.value
        return info
    @classmethod
    def _extract_pkg(cls, parts, value_node, meta):
        prefix = ".".join(parts)
        if isinstance(value_node, lark.Tree) and value_node.data == "struct":
            has_assignments = any(
                isinstance(c, lark.Tree) and c.data == "assignment"
                for c in value_node.children
            )
            if has_assignments:
                cls._flatten_struct(value_node, prefix, meta.pkg)
                return
        simple = cls._get_simple_value(value_node)
        if simple is not None:
            meta.pkg[prefix] = simple
    @classmethod
    def _flatten_struct(cls, node, prefix, result):
        for child in node.children:
            if isinstance(child, lark.Tree) and child.data == "assignment":
                if len(child.children) < 3:
                    continue
                id_node = child.children[0]
                value_node = child.children[2]
                if isinstance(id_node, lark.Tree) and id_node.data == "identifier":
                    field_parts = cls._get_identifier_parts(id_node)
                    field_name = ".".join(field_parts)
                    full_key = f"{prefix}.{field_name}"
                    if isinstance(value_node, lark.Tree) and value_node.data == "struct":
                        has_nested = any(
                            isinstance(c, lark.Tree) and c.data == "assignment"
                            for c in value_node.children
                        )
                        if has_nested:
                            cls._flatten_struct(value_node, full_key, result)
                            continue
                    simple = cls._get_simple_value(value_node)
                    if simple is not None:
                        result[full_key] = simple
    @classmethod
    def _get_identifier_parts(cls, node):
        parts = []
        for child in node.children:
            if isinstance(child, lark.Token) and child.type == "TOKENFIELD":
                parts.append(child.value)
        return parts
    @classmethod
    def _get_text_value(cls, node):
        for child in node.children:
            if isinstance(child, lark.Token):
                # Handle both namespaced and non-namespaced token types
                if "SHORT_TEXT_CONTENT" in child.type or "LONG_TEXT_CONTENT" in child.type:
                    return child.value
        return None
    @classmethod
    def _get_simple_value(cls, node):
        if isinstance(node, lark.Token):
            if node.type == "BLOB":
                return node.value
            return None
        if isinstance(node, lark.Tree):
            if node.data == "text":
                return cls._get_text_value(node)
            if node.data == "number":
                for child in node.children:
                    if isinstance(child, lark.Token):
                        return child.value
            if node.data == "identifier":
                parts = cls._get_identifier_parts(node)
                return ".".join(parts) if parts else None
        return None

def scan_module(source_or_path):
    """Scan a module and return metadata.

    Args:
        source_or_path: Either source code string or Path to .comp file

    Returns:
        (ModuleMetadata) Extracted information
    """
    if isinstance(source_or_path, pathlib.Path):
        return ModuleScanner.scan_file(source_or_path)
    elif isinstance(source_or_path, str) and not source_or_path.startswith(
        ("import", "pkg", "---", "--")
    ):
        path = pathlib.Path(source_or_path)
        if path.exists():
            return ModuleScanner.scan_file(path)
    return ModuleScanner.scan(source_or_path)

# === Quick test ===
if __name__ == "__main__":
    test_source = """
--- URL shortener service
A simple URL shortener using Redis for storage.
---

!import http ("http-server" stdlib)
!import redis ("redis" stdlib)

pkg.name = "shortly"
pkg.version = "1.0.0"
pkg.urls = (
    home = "https://shortly.io"
    docs = "https://docs.shortly.io"
)

mod.server.port = 8080
"""
    meta = ModuleScanner.scan(test_source)
    print(f"Package: {meta.pkg_name} v{meta.pkg_version}")
    print(f"Doc summary: {meta.doc_summary}")
    print(f"Imports: {[(i.name, i.source, i.import_type) for i in meta.imports]}")
    print(f"All pkg fields: {meta.pkg}")
    print(f"Doc/comments: {[(d.line, d.column, d.content[:40]) for d in meta.doc_comments]}")
    if meta.scan_errors:
        print(f"Errors: {meta.scan_errors}")
