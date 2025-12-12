#!/usr/bin/env python3
"""
Comp Module Info - Extract metadata from .comp files.

Uses the comp.scanner module to extract:
- Module docstring summary (first line)
- Import declarations
- Package metadata (flattened)
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from comp.scanner import ModuleScanner, ModuleMetadata


def print_module_info(meta: ModuleMetadata, filepath: Path, verbose: bool = False):
    """Print module info in a readable format."""
    print(f"=== {filepath.name} ===")
    
    # Doc summary
    if meta.doc_summary:
        print(f"\n  Summary: {meta.doc_summary}")
    else:
        print(f"\n  Summary: (none)")
    
    # Imports
    if meta.imports:
        print(f"\n  Imports:")
        for imp in sorted(meta.imports, key=lambda i: i.name):
            print(f"    {imp.name}: {imp.source!r} ({imp.import_type})")
    else:
        print(f"\n  Imports: (none)")
    
    # Package metadata
    if meta.pkg:
        print(f"\n  Package:")
        for key, value in sorted(meta.pkg.items()):
            # Remove 'pkg.' prefix for display
            display_key = key[4:] if key.startswith("pkg.") else key
            print(f"    {display_key}: {value!r}")
    else:
        print(f"\n  Package: (none)")
    
    # Errors (if verbose)
    if verbose and meta.scan_errors:
        print(f"\n  Errors:")
        for err in meta.scan_errors:
            print(f"    - {err[:80]}...")
    
    print()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Extract metadata from .comp module files."
    )
    parser.add_argument(
        "files", nargs="*", type=Path,
        help="Files to scan (default: examples/*.comp)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Show more details including errors"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON"
    )
    
    args = parser.parse_args()
    
    # Default to example files
    if not args.files:
        examples = Path(__file__).parent.parent / "examples"
        args.files = sorted(examples.glob("*.comp"))
    
    if not args.files:
        print("No files to scan.", file=sys.stderr)
        sys.exit(1)
    
    results = []
    for filepath in args.files:
        if not filepath.exists():
            print(f"File not found: {filepath}", file=sys.stderr)
            continue
        
        meta = ModuleScanner.scan_file(filepath)
        results.append((filepath, meta))
    
    if args.json:
        import json
        output = []
        for filepath, meta in results:
            output.append({
                "file": str(filepath),
                "summary": meta.doc_summary,
                "imports": {
                    imp.name: {"source": imp.source, "type": imp.import_type}
                    for imp in meta.imports
                },
                "pkg": meta.pkg,
                "errors": meta.scan_errors if args.verbose else [],
            })
        print(json.dumps(output, indent=2))
    else:
        for filepath, meta in results:
            print_module_info(meta, filepath, args.verbose)


if __name__ == "__main__":
    main()
