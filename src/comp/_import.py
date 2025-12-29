"""Module import system for Comp.

This module handles:
- Locating modules by name
- Scanning and caching module metadata
- Building dependency graphs
- Resolving imports and namespaces
- Loading complete modules with dependencies
"""

__all__ = []


import os
from dataclasses import dataclass
from pathlib import Path

import comp


class ModuleNotFoundError(Exception):
    """Raised when a module cannot be located."""
    pass


@dataclass
class ModuleSource:
    """Result of locating a module.

    Attributes:
        resource: Original module resource identifier requested
        location: Where it came from (file path, URL, etc.)
        source_type: Type of source - "file", "git", "http", "builtin"
        etag: Version identifier for cache validation (mtime_ns for files)
        content: Source text
        anchor: Directory path for relative imports from this module
    """

    resource: str
    location: str
    source_type: str
    etag: str
    content: str
    anchor: str


def locate(
    resource: str,
    from_dir: str | Path | None = None,
    etag: str | None = None,
    search_paths: list[str] | None = None,
    search_fds: list[int] | None = None,
) -> ModuleSource | None:
    """Locate a module and return its source and information.

    Module resource formats supported:
    - Relative path: "./utils", "../shared/helpers"
    - Stdlib module: "stdlib/loop", "http"
    - Absolute path: "/full/path/to/module.comp"

    Future formats (not yet implemented):
    - Git URL: "git+https://github.com/user/repo"
    - HTTP URL: "https://example.com/module.comp"

    Args:
        resource: Module resource identifier to locate
        from_dir: Directory of the module doing the import (for relative imports)
                  Can be Path, string path, or None
        etag: Optional etag for cache validation. If provided and matches,
              returns None (caller already has all the data)
        search_paths: List of search directory paths (for error messages and fallback)
        search_fds: List of open directory file descriptors (for efficient search)
                    Must be same length as search_paths. Use -1 for invalid paths.

    Returns:
        ModuleSource with location, content, and etag, or None if etag matches

    Raises:
        ModuleNotFoundError: Module not found in search paths
        NotImplementedError: For git://, http://, etc. URLs

    Implementation:
        Uses file descriptors for efficiency:
        - Uses openat() on directory fds to locate candidate files
        - Uses fstat on fd to get mtime
        - Generates etag from abspath + mtime
        - Returns None if etag matches (cache hit)
        - Only reads file contents on cache miss
        - Validates file size before reading
    """
    if search_paths is None:
        raise ValueError("search_paths must be provided")
    if search_fds is None:
        raise ValueError("search_fds must be provided")
    if len(search_paths) != len(search_fds):
        raise ValueError("search_paths and search_fds must have the same length")

    # Check for unsupported URL schemes
    if resource.startswith(("http://", "https://", "git+", "ssh://")):
        raise NotImplementedError(
            f"Remote modules not yet supported: {resource}\n"
            f"Git and HTTP packages will be supported in a future release."
        )

    # Find and load the module using fd-based approach
    return _locate_file(resource, from_dir, etag, search_paths, search_fds)


def _locate_file(
    resource: str,
    from_dir: str | Path | None,
    etag: str | None,
    search_paths: list[str],
    search_fds: list[int],
) -> ModuleSource | None:
    """Locate and load a file-based module using file descriptors.

    Efficiently locates modules by:
    1. Using openat() on directory fds for each candidate (cheap syscall on Unix)
    2. Using fstat on fd to get mtime
    3. Generating etag from abspath + mtime
    4. Returning None if etag matches (cache hit)
    5. Only reading file contents if etag differs or not provided

    Platform notes:
    - On Unix systems: Uses openat() with directory fds for efficient search
    - On Windows: Falls back to regular path-based open (dir_fd not supported)
    - search_fds values of -1 indicate fallback to path-based search

    Args:
        resource: Module resource identifier to locate
        from_dir: Directory for relative imports (or None)
        etag: Optional etag for cache validation
        search_paths: List of search directory paths (for error messages and fallback)
        search_fds: List of open directory file descriptors (for efficient search on Unix)
                    Use -1 for paths without valid fds (Windows, non-existent dirs)

    Returns:
        ModuleSource with location, content, and etag, or None if etag matches

    Raises:
        ModuleNotFoundError: Module not found
    """
    # Maximum file size (10MB - sanity check)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # Normalize from_dir to string
    if isinstance(from_dir, Path):
        from_dir = str(from_dir)

    # Build list of candidates: (full_path, dir_fd, relative_path)
    # dir_fd is used with openat(), relative_path is relative to that fd
    candidates = []

    # Handle relative imports (./foo or ../bar)
    if resource.startswith("."):
        if from_dir is None:
            raise ModuleNotFoundError(
                f"Relative import '{resource}' requires from_dir to be specified"
            )
        # Resolve relative path
        base_path = os.path.abspath(from_dir)
        rel_path = os.path.normpath(os.path.join(base_path, resource))

        # Try with .comp extension (use absolute path, no dir_fd)
        if not rel_path.endswith(".comp"):
            candidates.append((rel_path + ".comp", None, None))
        candidates.append((rel_path, None, None))

    # Handle absolute paths
    elif os.path.isabs(resource):
        if not resource.endswith(".comp"):
            candidates.append((resource + ".comp", None, None))
        candidates.append((resource, None, None))

    # Search in configured search paths using directory fds
    else:
        for search_path, dir_fd in zip(search_paths, search_fds):
            # Try as direct file (e.g., "stdlib/loop" -> "stdlib/loop.comp")
            rel_name = resource if resource.endswith(".comp") else resource + ".comp"
            full_path = os.path.join(search_path, rel_name)
            # Include dir_fd even if -1 (will fall back to path-based open)
            candidates.append((full_path, dir_fd, rel_name))

            # Try as directory with __init__.comp
            init_rel = os.path.join(resource, "__init__.comp")
            init_full = os.path.join(search_path, init_rel)
            candidates.append((init_full, dir_fd, init_rel))

    # Try each candidate
    for candidate_path, dir_fd, rel_path in candidates:
        try:
            # Try to open the file using openat() if we have a valid dir_fd
            if dir_fd is not None and dir_fd >= 0 and rel_path is not None:
                # Use openat() - open relative to directory fd (Unix-like systems)
                try:
                    fd = os.open(rel_path, os.O_RDONLY, dir_fd=dir_fd)
                except (TypeError, NotImplementedError):
                    # dir_fd not supported on this platform (Windows), fall back
                    fd = os.open(candidate_path, os.O_RDONLY)
            else:
                # No dir_fd available or absolute path - use regular open
                fd = os.open(candidate_path, os.O_RDONLY)
        except (FileNotFoundError, OSError):
            # File doesn't exist, try next candidate
            continue

        try:
            # Get file stats using the fd
            stat_result = os.fstat(fd)

            # Check file size
            if stat_result.st_size > MAX_FILE_SIZE:
                raise ModuleNotFoundError(
                    f"Module file too large: {candidate_path} "
                    f"({stat_result.st_size} bytes, max {MAX_FILE_SIZE})"
                )

            # Generate etag from abspath + mtime and check
            abs_path = os.path.abspath(candidate_path)
            computed_etag = f"{abs_path}:{stat_result.st_mtime_ns}"
            if etag is not None and etag == computed_etag:
                os.close(fd)
                return None

            # Read file contents using fd with universal newlines
            stream = os.fdopen(fd, "r", encoding="utf-8")
            content = stream.read()
            # Note: fdopen takes ownership of fd, so stream.close() will close it

            anchor = os.path.dirname(abs_path)

            return ModuleSource(
                resource=resource,
                location=abs_path,
                source_type="file",
                etag=computed_etag,
                content=content,
                anchor=anchor,
            )
        except Exception:
            # Make sure fd is closed on any error
            try:
                os.close(fd)
            except OSError:
                pass
            raise

    # Not found anywhere
    raise ModuleNotFoundError(
        f"Module '{resource}' not found\n"
        f"Searched:\n" + "\n".join(f"  - {p[0]}" for p in candidates)
    )
