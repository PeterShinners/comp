"""
Comp Module Scanner - Metadata extraction using Lark parser.

This scanner extracts module metadata:
- Package info (name, version, description, and nested fields)
- Import declarations  
- Module documentation

It's designed to be error-resilient: syntax errors in one part of
the file don't prevent extraction from other parts.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lark import Lark, Token, Tree


# Grammar file location
GRAMMAR_PATH = Path(__file__).parent / "scan.lark"


@dataclass
class ImportDef:
    """An import declaration."""
    name: str
    source: str
    import_type: str  # "comp", "stdlib", "python", etc.
    line: int = 0


@dataclass
class ModuleMetadata:
    """Extracted module metadata."""
    # Package info (flattened - nested structs become dotted paths)
    pkg: dict[str, str] = field(default_factory=dict)
    
    # Imports
    imports: list[ImportDef] = field(default_factory=list)
    
    # Documentation
    module_doc: Optional[str] = None
    doc_summary: Optional[str] = None  # First line of module_doc
    
    # Errors encountered (non-fatal)
    scan_errors: list[str] = field(default_factory=list)
    
    # Convenience properties for common pkg fields
    @property
    def pkg_name(self) -> Optional[str]:
        return self.pkg.get("pkg.name")
    
    @property
    def pkg_version(self) -> Optional[str]:
        return self.pkg.get("pkg.version")
    
    @property
    def pkg_description(self) -> Optional[str]:
        return self.pkg.get("pkg.description")


class ModuleScanner:
    """
    Lark-based scanner for Comp module metadata.
    
    Uses the scan.lark grammar for parsing with error recovery
    for files with syntax issues.
    """
    
    _parser: Optional[Lark] = None
    
    @classmethod
    def _get_parser(cls) -> Lark:
        """Lazy-load the parser."""
        if cls._parser is None:
            with open(GRAMMAR_PATH) as f:
                grammar = f.read()
            cls._parser = Lark(grammar, parser="lalr", propagate_positions=True)
        return cls._parser
    
    @classmethod
    def scan(cls, source: str) -> ModuleMetadata:
        """
        Scan source code and extract module metadata.
        
        This is resilient to errors - problems in one area won't
        prevent extraction from other areas.
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
    def scan_file(cls, path: Path) -> ModuleMetadata:
        """Scan a .comp file and extract metadata."""
        source = path.read_text(encoding='utf-8')
        return cls.scan(source)
    
    @classmethod
    def _try_partial_parse(cls, parser: Lark, source: str, meta: ModuleMetadata) -> Optional[Tree]:
        """Try to parse progressively smaller chunks from the start of the file."""
        for try_len in [4000, 2000, 1000, 600, 400, 200, 100]:
            if try_len >= len(source):
                continue
            try:
                truncated = cls._find_safe_truncation(source, try_len)
                tree = parser.parse(truncated)
                return tree
            except:
                continue
        return None
    
    @classmethod
    def _find_safe_truncation(cls, content: str, max_len: int) -> str:
        """Find a safe point to truncate content for parsing."""
        if len(content) <= max_len:
            return content
        
        truncated = content[:max_len]
        
        # Look for end of doc comment blocks before max_len
        last_doc_end = truncated.rfind('---')
        if last_doc_end > 0:
            before = truncated[:last_doc_end]
            doc_open = before.rfind('---')
            if doc_open >= 0:
                end_pos = last_doc_end + 3
                next_nl = truncated.find('\n', end_pos)
                if next_nl > 0:
                    return truncated[:next_nl]
                return truncated[:end_pos]
        
        # Find last line that ends cleanly
        lines = truncated.split('\n')
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if not line or line.endswith(')') or line.startswith('--'):
                return '\n'.join(lines[:i+1])
        
        last_nl = truncated.rfind('\n')
        if last_nl > 100:
            return truncated[:last_nl]
        return truncated
    
    @classmethod
    def _extract_from_tree(cls, tree: Tree, meta: ModuleMetadata):
        """Extract all metadata from the parse tree."""
        for item in tree.children:
            if isinstance(item, Tree):
                if item.data == "doc_comment":
                    cls._extract_doc_comment(item, meta)
                elif item.data == "assignment":
                    cls._extract_assignment(item, meta)
    
    @classmethod
    def _extract_doc_comment(cls, node: Tree, meta: ModuleMetadata):
        """Extract documentation from a doc_comment node."""
        if meta.module_doc is not None:
            return  # Only take the first doc comment
        
        for child in node.children:
            if isinstance(child, Token) and child.type == "DOC_CONTENT":
                meta.module_doc = child.value.strip()
                # Get first line as summary
                lines = meta.module_doc.split('\n')
                meta.doc_summary = lines[0].strip() if lines else None
                break
    
    @classmethod
    def _extract_assignment(cls, node: Tree, meta: ModuleMetadata):
        """Extract import or pkg assignment."""
        if len(node.children) < 3:
            return
        
        id_node = node.children[0]
        value_node = node.children[2]  # children[1] is ASSIGN token
        
        if not isinstance(id_node, Tree) or id_node.data != "identifier":
            return
        
        parts = cls._get_identifier_parts(id_node)
        if not parts:
            return
        
        if parts[0] == "import" and len(parts) >= 2:
            cls._extract_import(parts, value_node, meta, id_node)
        elif parts[0] == "pkg":
            cls._extract_pkg(parts, value_node, meta)
    
    @classmethod
    def _extract_import(cls, parts: list[str], value_node, meta: ModuleMetadata, id_node: Tree):
        """Extract an import declaration."""
        import_name = ".".join(parts[1:])
        
        if isinstance(value_node, Tree) and value_node.data == "struct":
            info = cls._extract_import_struct(value_node)
            line = getattr(id_node.children[0], 'line', 0) if id_node.children else 0
            meta.imports.append(ImportDef(
                name=import_name,
                source=info.get("source", ""),
                import_type=info.get("type", ""),
                line=line
            ))
    
    @classmethod
    def _extract_import_struct(cls, struct_node: Tree) -> dict:
        """Extract source and type from import struct like ("source" type)."""
        info = {"source": "", "type": ""}
        
        for child in struct_node.children:
            if isinstance(child, Tree):
                if child.data == "text":
                    info["source"] = cls._get_text_value(child) or ""
                elif child.data == "identifier":
                    parts = cls._get_identifier_parts(child)
                    if parts:
                        info["type"] = parts[0]
        
        return info
    
    @classmethod
    def _extract_pkg(cls, parts: list[str], value_node, meta: ModuleMetadata):
        """Extract package metadata, flattening nested structs."""
        prefix = ".".join(parts)
        
        # Check if value is a struct with nested assignments
        if isinstance(value_node, Tree) and value_node.data == "struct":
            has_assignments = any(
                isinstance(c, Tree) and c.data == "assignment"
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
    def _flatten_struct(cls, node: Tree, prefix: str, result: dict):
        """Recursively flatten struct assignments into dotted paths."""
        for child in node.children:
            if isinstance(child, Tree) and child.data == "assignment":
                if len(child.children) < 3:
                    continue
                
                id_node = child.children[0]
                value_node = child.children[2]
                
                if isinstance(id_node, Tree) and id_node.data == "identifier":
                    field_parts = cls._get_identifier_parts(id_node)
                    field_name = ".".join(field_parts)
                    full_key = f"{prefix}.{field_name}"
                    
                    # Check for nested struct with assignments
                    if isinstance(value_node, Tree) and value_node.data == "struct":
                        has_nested = any(
                            isinstance(c, Tree) and c.data == "assignment"
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
    def _get_identifier_parts(cls, node: Tree) -> list[str]:
        """Extract path parts from an identifier node."""
        parts = []
        for child in node.children:
            if isinstance(child, Token) and child.type == "TOKENFIELD":
                parts.append(child.value)
        return parts
    
    @classmethod
    def _get_text_value(cls, node: Tree) -> Optional[str]:
        """Extract string content from a text node."""
        for child in node.children:
            if isinstance(child, Token):
                if child.type in ("SHORT_TEXT_CONTENT", "LONG_TEXT_CONTENT"):
                    return child.value
        return None
    
    @classmethod
    def _get_simple_value(cls, node) -> Optional[str]:
        """Extract a simple value (text, number, identifier) from a node."""
        if isinstance(node, Token):
            if node.type == "BLOB":
                return node.value
            return None
        
        if isinstance(node, Tree):
            if node.data == "text":
                return cls._get_text_value(node)
            if node.data == "number":
                for child in node.children:
                    if isinstance(child, Token):
                        return child.value
            if node.data == "identifier":
                parts = cls._get_identifier_parts(node)
                return ".".join(parts) if parts else None
        
        return None


# Convenience function
def scan_module(source_or_path) -> ModuleMetadata:
    """
    Scan a module and return metadata.
    
    Args:
        source_or_path: Either source code string or Path to .comp file
        
    Returns:
        ModuleMetadata with extracted information
    """
    if isinstance(source_or_path, Path):
        return ModuleScanner.scan_file(source_or_path)
    elif isinstance(source_or_path, str) and not source_or_path.startswith(('import', 'pkg', '---', '--')):
        # Looks like a file path
        path = Path(source_or_path)
        if path.exists():
            return ModuleScanner.scan_file(path)
    return ModuleScanner.scan(source_or_path)


# === Quick test ===
if __name__ == '__main__':
    test_source = '''
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
'''
    
    meta = ModuleScanner.scan(test_source)
    
    print(f"Package: {meta.pkg_name} v{meta.pkg_version}")
    print(f"Doc summary: {meta.doc_summary}")
    print(f"Imports: {[(i.name, i.source, i.import_type) for i in meta.imports]}")
    print(f"All pkg fields: {meta.pkg}")
    if meta.scan_errors:
        print(f"Errors: {meta.scan_errors}")
