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


class ModuleMetadata:
    """Extracted module metadata.

    Attributes:
        pkg: (dict) Package info (flattened - nested structs become dotted paths)
        imports: (list) Import declarations
        module_doc: (str | None) Full module documentation
        doc_summary: (str | None) First line of module_doc
        scan_errors: (list) Errors encountered (non-fatal)
    """

    __slots__ = ("pkg", "imports", "module_doc", "doc_summary", "scan_errors")

    def __init__(self):
        self.pkg = {}
        self.imports = []
        self.module_doc = None
        self.doc_summary = None
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


class ModuleScanner:
    """Lark-based scanner for Comp module metadata.

    Uses the scan.lark grammar for parsing with error recovery
    for files with syntax issues.
    """

    _parser = None

    @classmethod
    def _get_parser(cls):
        """Lazy-load the parser.

        Returns:
            (lark.Lark) Parser instance
        """
        if cls._parser is None:
            with open(GRAMMAR_PATH) as f:
                grammar = f.read()
            cls._parser = lark.Lark(
                grammar,
                parser="lalr",
                propagate_positions=True,
                import_paths=[str(GRAMMAR_PATH.parent)],
            )
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

        # Try to parse the full source
        tree = None
        try:
            tree = parser.parse(source)
        except Exception as e:
            meta.scan_errors.append(f"Full parse failed: {e}")
            # Try partial parsing from the top of the file
            tree = cls._try_partial_parse(parser, source, meta)

        if tree is None:
            return meta

        # Extract metadata from parse tree
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
        """Try to parse progressively smaller chunks from the start of the file.

        Args:
            parser: (lark.Lark) Parser instance
            source: (str) Source code
            meta: (ModuleMetadata) Metadata to add errors to

        Returns:
            (lark.Tree | None) Parse tree or None
        """
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
        """Find a safe point to truncate content for parsing.

        Args:
            content: (str) Content to truncate
            max_len: (int) Maximum length

        Returns:
            (str) Truncated content
        """
        if len(content) <= max_len:
            return content

        truncated = content[:max_len]

        # Look for end of doc comment blocks before max_len
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

        # Find last line that ends cleanly
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
        """Extract all metadata from the parse tree.

        Args:
            tree: (lark.Tree) Parse tree
            meta: (ModuleMetadata) Metadata to populate
        """
        for item in tree.children:
            if isinstance(item, lark.Tree):
                if item.data == "doc_comment":
                    cls._extract_doc_comment(item, meta)
                elif item.data == "assignment":
                    cls._extract_assignment(item, meta)

    @classmethod
    def _extract_doc_comment(cls, node, meta):
        """Extract documentation from a doc_comment node.

        Args:
            node: (lark.Tree) Doc comment node
            meta: (ModuleMetadata) Metadata to populate
        """
        if meta.module_doc is not None:
            return  # Only take the first doc comment

        for child in node.children:
            if isinstance(child, lark.Token) and child.type == "DOC_CONTENT":
                meta.module_doc = child.value.strip()
                # Get first line as summary
                lines = meta.module_doc.split("\n")
                meta.doc_summary = lines[0].strip() if lines else None
                break

    @classmethod
    def _extract_assignment(cls, node, meta):
        """Extract import or pkg assignment.

        Args:
            node: (lark.Tree) Assignment node
            meta: (ModuleMetadata) Metadata to populate
        """
        if len(node.children) < 3:
            return

        id_node = node.children[0]
        value_node = node.children[2]  # children[1] is ASSIGN token

        if not isinstance(id_node, lark.Tree) or id_node.data != "identifier":
            return

        parts = cls._get_identifier_parts(id_node)
        if not parts:
            return

        if parts[0] == "import" and len(parts) >= 2:
            cls._extract_import(parts, value_node, meta, id_node)
        elif parts[0] == "pkg":
            cls._extract_pkg(parts, value_node, meta)

    @classmethod
    def _extract_import(cls, parts, value_node, meta, id_node):
        """Extract an import declaration.

        Args:
            parts: (list) Identifier parts
            value_node: (lark.Tree) Value node
            meta: (ModuleMetadata) Metadata to populate
            id_node: (lark.Tree) Identifier node
        """
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
        """Extract source and type from import struct like ("source" type).

        Args:
            struct_node: (lark.Tree) Struct node

        Returns:
            (dict) Dictionary with "source" and "type" keys
        """
        info = {"source": "", "type": ""}

        for child in struct_node.children:
            if isinstance(child, lark.Tree):
                if child.data == "text":
                    info["source"] = cls._get_text_value(child) or ""
                elif child.data == "identifier":
                    parts = cls._get_identifier_parts(child)
                    if parts:
                        info["type"] = parts[0]

        return info

    @classmethod
    def _extract_pkg(cls, parts, value_node, meta):
        """Extract package metadata, flattening nested structs.

        Args:
            parts: (list) Identifier parts
            value_node: (lark.Tree) Value node
            meta: (ModuleMetadata) Metadata to populate
        """
        prefix = ".".join(parts)

        # Check if value is a struct with nested assignments
        if isinstance(value_node, lark.Tree) and value_node.data == "struct":
            has_assignments = any(
                isinstance(c, lark.Tree) and c.data == "assignment"
                for c in value_node.children
            )
            if has_assignments:
                cls._flatten_struct(value_node, prefix, meta.pkg)
                return

        # Simple value
        simple = cls._get_simple_value(value_node)
        if simple is not None:
            meta.pkg[prefix] = simple

    @classmethod
    def _flatten_struct(cls, node, prefix, result):
        """Recursively flatten struct assignments into dotted paths.

        Args:
            node: (lark.Tree) Struct node
            prefix: (str) Current path prefix
            result: (dict) Dictionary to populate
        """
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

                    # Check for nested struct with assignments
                    if isinstance(value_node, lark.Tree) and value_node.data == "struct":
                        has_nested = any(
                            isinstance(c, lark.Tree) and c.data == "assignment"
                            for c in value_node.children
                        )
                        if has_nested:
                            cls._flatten_struct(value_node, full_key, result)
                            continue

                    # Simple value
                    simple = cls._get_simple_value(value_node)
                    if simple is not None:
                        result[full_key] = simple

    @classmethod
    def _get_identifier_parts(cls, node):
        """Extract path parts from an identifier node.

        Args:
            node: (lark.Tree) Identifier node

        Returns:
            (list) List of identifier parts
        """
        parts = []
        for child in node.children:
            if isinstance(child, lark.Token) and child.type == "TOKENFIELD":
                parts.append(child.value)
        return parts

    @classmethod
    def _get_text_value(cls, node):
        """Extract string content from a text node.

        Args:
            node: (lark.Tree) Text node

        Returns:
            (str | None) Text content or None
        """
        for child in node.children:
            if isinstance(child, lark.Token):
                if child.type in ("SHORT_TEXT_CONTENT", "LONG_TEXT_CONTENT"):
                    return child.value
        return None

    @classmethod
    def _get_simple_value(cls, node):
        """Extract a simple value (text, number, identifier) from a node.

        Args:
            node: (lark.Tree | lark.Token) Node to extract from

        Returns:
            (str | None) Simple value or None
        """
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
        # Looks like a file path
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

import.http = ("http-server" stdlib)
import.redis = ("redis" stdlib)

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
    if meta.scan_errors:
        print(f"Errors: {meta.scan_errors}")
