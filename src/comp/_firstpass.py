"""First-pass scanner for Comp source files.

Scans source to identify top-level declarations without full parsing.
This enables incremental parsing, resilient error handling, and
language server support.
"""

__all__ = ["SourceChunk", "first_pass", "CHUNK_KEYWORDS"]


# Keywords and the index of the token for the name
CHUNK_KEYWORDS = {
    "import": 1,
    "func": 1,
    "shape": 1,
    "tag": 1,
    "handle": 1,
    "mod": 1,
    "pure": 2,
    "entry": 2,
    "context": 1,
}


class SourceChunk:
    """A top-level declaration found in first pass.

    Attributes:
        keyword: (str) Declaration type: "import", "func", "shape", "tag", ...
        name: (str) Qualified name if detected from first token after keyword
        line_num: (int) First line of this chunk (0-indexed)
        lines: (list[str]) Source lines for this chunk
    """
    __slots__ = ("keyword", "name", "line_num", "lines")

    def __init__(self, keyword, name, line_num, first_line):
        self.keyword = keyword
        self.name = name
        self.line_num = line_num
        self.lines = [first_line] if first_line is not None else []

    def __repr__(self):
        return f"SourceChunk(!{self.keyword!r}, {self.name!r}, lines {len(self.lines)})"


def first_pass(source):
    """Scan source and return list of top-level chunks.

    Identifies all !keyword declarations at line start, tracking
    multiline strings and doc blocks to avoid false matches.

    Args:
        source: (str) Comp source code

    Returns:
        (list[SourceChunk]) Ordered list of chunks found
    """
    lines = source.splitlines(keepends=True)
    chunks = [SourceChunk("_prelude", None, 0, None)]
    chunklines = chunks[0].lines

    # Parser state
    in_multiline_string = False
    in_doc_block = False

    for line_num, line in enumerate(lines):
        # Strip comments for analysis (but keep original line in source)
        analysis_line = line.partition(";")[0]
        stripped = analysis_line.lstrip()

        # If inside multiline string, just accumulate (unless in doc block)
        if in_multiline_string and not in_doc_block:
            chunklines.append(line)
            # Check for closing """
            if analysis_line.count('"""') % 2 == 1:
                in_multiline_string = False
            continue

        # If inside doc block, just accumulate (unless closing)
        if in_doc_block:
            if stripped.startswith("---"):
                in_doc_block = False
            chunklines.append(line)
            continue

        # Check for doc block start
        if stripped.startswith("---"):
            in_doc_block = True
            chunks.append(SourceChunk("_doc", None, line_num, line))
            chunklines = chunks[-1].lines
            continue

        # Check for line doc
        if stripped.startswith("--"):
            chunks.append(SourceChunk("_doc", None, line_num, line))
            chunklines = chunks[-1].lines
            continue

        # Check for !keyword - do this BEFORE tracking """ so that
        # `!mod test = """` creates a new chunk first
        if stripped.startswith("!"):
            tokens = stripped[1:400].split(maxsplit=3)
            keyword = tokens[0]
            name_token = CHUNK_KEYWORDS.get(keyword)
            if name_token is not None and name_token < len(tokens):
                chunks.append(SourceChunk(keyword, tokens[name_token], line_num, line))
                chunklines = chunks[-1].lines
                # Track """ on this line for the NEW chunk
                if analysis_line.count('"""') % 2 == 1:
                    in_multiline_string = True
                continue

        # Track multiline string start on regular lines
        if analysis_line.count('"""') % 2 == 1:
            in_multiline_string = True

        # Regular line - add to current chunk
        chunklines.append(line)

    return chunks


def first_pass_outline(source):
    """Return a simple outline of declarations in source.

    Args:
        source: (str) Comp source code

    Returns:
        (list[tuple]) List of (keyword, name, line_number) tuples
    """
    chunks = first_pass(source)
    return [(c.keyword, c.name, c.line_num) for c in chunks]


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m comp._firstpass <file.comp> [...]", file=sys.stderr)
        sys.exit(1)

    for path in sys.argv[1:]:
        try:
            with open(path) as f:
                source = f.read()
        except FileNotFoundError:
            print(f"File not found: {path}", file=sys.stderr)
            continue

        print(f"=== {path} ===")
        chunks = first_pass(source)
        for chunk in chunks:
            if chunk.lines:
                line = "\n".join(l.strip() for l in chunk.lines)
                line = line.strip('---').strip()
                if len(line) > 60:
                    line = repr(line[:57]) + "..."
                else:
                    line = repr(line)
            else:
                line = None
            print(f"  {chunk.line_num+1:4d}: {chunk.keyword:8s} {chunk.name or '':14} {line}")
        print()
