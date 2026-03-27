"""In-memory filesystem runtime for Comp ramfs backend.

Low-level operations callable via py.call from ramfs.comp.
All filesystem state lives in Python-side RamNode objects that are
stashed in entries and round-tripped through py.call — exactly like
DirHandle in the native backend.

A RamHandle wraps a RamNode (the actual storage) plus a virtual path
string, mirroring DirHandle's (node, path) shape so that ramfs.comp
can be structured identically to nativefs.comp.

Multiple opens of the same virtual path share the same RamNode, so
mutations are visible across all entries backed by that mount.
"""

import time


# ---------------------------------------------------------------------------
# Storage nodes
# ---------------------------------------------------------------------------

class RamNode:
    """A single node in an in-memory filesystem tree.

    Nodes are mutable and shared by object identity — all RamHandle
    objects wrapping the same RamNode see each other's writes instantly.
    """

    __slots__ = ("kind", "children", "content", "modified")

    def __init__(self, kind: str) -> None:
        self.kind = kind          # "dir" or "file"
        self.children: dict[str, "RamNode"] = {}  # name -> RamNode (dirs only)
        self.content: bytes = b""  # UTF-8 payload (files only)
        self.modified: float = time.time()

    def __repr__(self) -> str:
        return f"<RamNode kind={self.kind!r} children={list(self.children)!r}>"


class RamHandle:
    """Opaque wrapper around a RamNode with its virtual path.

    Analogous to DirHandle in the native backend.  Comp code stashes
    this and passes it back to runtime functions via py.call; it never
    inspects the internal structure.
    """

    __slots__ = ("node", "path")

    def __init__(self, node: RamNode, path: str) -> None:
        self.node = node
        self.path = path

    def __repr__(self) -> str:
        return f"<RamHandle path={self.path!r} kind={self.node.kind!r}>"


# ---------------------------------------------------------------------------
# Global mount registry
# ---------------------------------------------------------------------------

# Virtual path -> root RamNode.  Persists for the lifetime of the process.
_roots: dict[str, RamNode] = {}


# ---------------------------------------------------------------------------
# Public API — called via py.call from ramfs.comp
# ---------------------------------------------------------------------------

def new_root(path: str) -> RamHandle:
    """Open (or create) the ramfs mounted at *path*.

    If *path* has been opened before the same in-memory tree is
    returned, making the ramfs a true shared in-process store.
    """
    path = path.rstrip("/") or "/"
    if path not in _roots:
        _roots[path] = RamNode("dir")
    return RamHandle(_roots[path], path)


def open_child(parent_handle: RamHandle, name: str) -> RamHandle:
    """Open a named child directory relative to *parent_handle*.

    Supports multi-segment names: "a/b/c" navigates each segment in
    turn, identical to the native backend's open_child.  Raises
    OSError if any segment is missing or not a directory.
    """
    segments = [s for s in name.replace("\\", "/").split("/") if s]
    current = parent_handle
    for seg in segments:
        child = current.node.children.get(seg)
        if child is None:
            raise OSError(f"no such directory: {seg!r} in {current.path!r}")
        if child.kind != "dir":
            raise OSError(f"not a directory: {seg!r}")
        child_path = current.path.rstrip("/") + "/" + seg
        current = RamHandle(child, child_path)
    return current


def stat_entry(parent_handle: RamHandle, name: str) -> dict | None:
    """Stat a named child of *parent_handle*.

    Returns a dict with name, entry-type, size, modified — the same
    schema as the native stat_entry — or None if not found.
    """
    child = parent_handle.node.children.get(name)
    if child is None:
        return None
    return {
        "name": name,
        "entry-type": child.kind,
        "size": len(child.content),
        "modified": child.modified,
    }


def list_dir(handle: RamHandle) -> list[dict]:
    """List all children of *handle*.  Returns a list of stat dicts."""
    return [
        {
            "name": name,
            "entry-type": child.kind,
            "size": len(child.content),
            "modified": child.modified,
        }
        for name, child in handle.node.children.items()
    ]


def read_file(parent_handle: RamHandle, name: str) -> str:
    """Read a file as UTF-8 text.  Raises OSError if missing or is a dir."""
    child = parent_handle.node.children.get(name)
    if child is None:
        raise OSError(f"no such file: {name!r}")
    if child.kind != "file":
        raise OSError(f"is a directory: {name!r}")
    return child.content.decode("utf-8")


def write_file(parent_handle: RamHandle, name: str, content: str) -> None:
    """Write *content* to a file.  Creates the file node if missing."""
    child = parent_handle.node.children.get(name)
    if child is None:
        child = RamNode("file")
        parent_handle.node.children[name] = child
    elif child.kind != "file":
        raise OSError(f"is a directory: {name!r}")
    child.content = content.encode("utf-8")
    child.modified = time.time()


def mkdir(parent_handle: RamHandle, name: str) -> None:
    """Create a single directory child.  Raises if the name already exists."""
    if name in parent_handle.node.children:
        raise OSError(f"already exists: {name!r}")
    node = RamNode("dir")
    parent_handle.node.children[name] = node


def mkdir_all(parent_handle: RamHandle, name: str) -> RamHandle:
    """Create directories for every segment in *name*, makedirs-style.

    Existing directories are opened rather than recreated.
    Returns a RamHandle to the deepest (final) directory.
    Raises OSError if any segment already exists as a file.
    """
    segments = [s for s in name.replace("\\", "/").split("/") if s]
    current = parent_handle
    for seg in segments:
        child = current.node.children.get(seg)
        if child is None:
            child = RamNode("dir")
            current.node.children[seg] = child
        elif child.kind != "dir":
            raise OSError(f"exists but is not a directory: {seg!r}")
        child_path = current.path.rstrip("/") + "/" + seg
        current = RamHandle(child, child_path)
    return current


def remove(parent_handle: RamHandle, name: str) -> None:
    """Remove a file or empty directory.

    Raises OSError if the entry is missing or a non-empty directory.
    """
    child = parent_handle.node.children.get(name)
    if child is None:
        raise OSError(f"no such file or directory: {name!r}")
    if child.kind == "dir" and child.children:
        raise OSError(f"directory not empty: {name!r}")
    del parent_handle.node.children[name]


def handle_path(handle: RamHandle) -> str:
    """Return the virtual path stored in *handle*."""
    return handle.path


def clear_root(path: str) -> None:
    """Discard the ramfs mounted at *path*.

    Useful in tests to get a clean slate between runs.
    """
    path = path.rstrip("/") or "/"
    _roots.pop(path, None)
