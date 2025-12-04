"""Import system, compilation, and resource loading.

The import system coordinates between Compilers and Loaders to build
Modules from various sources (comp files, Python modules, schemas, etc).

Compilation phases:
1. Match loaders - Find loader(s) for resource string
2. Scan (extract_inventory) - Extract metadata, imports, contexts
   PARALLELIZABLE, CACHEABLE (tier 1)
3. Populate (compile) - Parse to TreeNode AST with docs
   CACHEABLE (tier 2)
4. Link - Bind references across module graph
   (runtime only, not cacheable)
5. Optimize - Constant folding, pure eval, DCE; TreeNode → FlatNode
   CACHEABLE (tier 3, composite key with dependencies)
6. Evaluate pure - Run pure functions for global data (runtime)
7. Context eval - Select context, find entry point (runtime)

AST representations:
- TreeNode: Phases 2-4. Parent/child pointers, rich metadata, easy modification
- FlatNode: Phase 5+. Flat instruction array, compact, optimized for execution

Cache tiers:
- Tier 0: Raw SourceData (optional, mostly redundant with loader caching)
- Tier 1: ModuleMetadata (inventory) - enables parallel dependency discovery
- Tier 2: Module with TreeNode AST - full compilation ready for linking
- Tier 3: Module with FlatNode AST - optimized code ready for execution
  Cache key: (module.id, module.cache_key, sorted((dep.id, dep.key)...))

Resilient caching:
- Continue walking all modules even if some fail compilation
- Cache whatever tier each module successfully reaches
- When fixing broken module, don't re-fetch/re-scan working dependencies

Key concepts:
- Loaders match resources and return identifiers for caching
- Volatility levels guide cache invalidation strategy
- Editable flag distinguishes dev/prod scenarios
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


__all__ = [
    "LoadMatch", "Volatility", "SourceData", "ModuleMetadata", "ImportSpec",
    "Loader", "Compiler", "ImportManager"
]


class Volatility(Enum):
    """Cache volatility levels for imported modules.

    STABLE - Never changes (pinned version, immutable)
    LOOSE - May change but rarely (local files in prod, stdlib)
    VOLATILE - Changes frequently (local files in dev, live APIs)
    """
    STABLE = "stable"
    LOOSE = "loose"
    VOLATILE = "volatile"


@dataclass
class LoadMatch:
    """Result of tentative loader match.

    Returned by can_load() to indicate confidence and provide
    a cache identifier without doing expensive I/O.

    Attributes:
        confidence: (float) 0-1, how confident this loader can handle it
        identifier: (str) Stable identifier for cache key (not URI)
        volatility: (Volatility) Expected stability of this resource
        editable: (bool) Whether this is editable (dev mode)
    """
    confidence: float
    identifier: str
    volatility: Volatility
    editable: bool = False


@dataclass
class SourceData:
    """Raw source data fetched from a loader.

    Attributes:
        source: (str | bytes) The actual source content
        uri: (str) Canonical URI for this source
        identifier: (str) Cache identifier (matches LoadMatch.identifier)
        cache_key: (str) Hash/etag/timestamp for cache validation
        volatility: (Volatility) Stability level
        editable: (bool) Whether source is editable
        metadata: (dict) Additional loader-specific metadata
    """
    source: str | bytes
    uri: str
    identifier: str
    cache_key: str
    volatility: Volatility
    editable: bool = False
    metadata: dict | None = None


@dataclass
class ImportSpec:
    """Specification for an import statement.

    From: !import namespace compiler "resource" ?? "fallback"

    Attributes:
        namespace: (str) Local namespace identifier
        compiler: (str) Compiler type (comp, python, openapi, etc)
        resource: (str) Resource string to resolve
        fallbacks: (list[tuple]) List of (compiler, resource) fallback pairs
        line_num: (int | None) Line number in source (for error messages)
    """
    namespace: str
    compiler: str
    resource: str
    fallbacks: list[tuple[str, str]] | None = None
    line_num: int | None = None


@dataclass
class ModuleMetadata:
    """Module inventory extracted from phase 2 (scan).

    Inventory provides enough info to resolve dependencies without
    full compilation. CACHEABLE - can be stored separately from Module.

    Used for:
    - Parallel dependency discovery
    - Fast determination of what can be imported
    - Tool queries about module structure

    Attributes:
        identifier: (str) Unique identifier for this module
        imports: (list[ImportSpec]) Import declarations in this module
        package: (dict) Package metadata from !mod package = ...
        contexts: (list[str]) Context names defined (!context foo ...)
        symbols: (dict | None) Symbol table by type (optional)
            {"func": ["foo", "bar"], "shape": ["~point"], ...}
            NOTE: Tags may be incomplete due to hierarchical definitions
        source_lines: (int) Number of lines in source (for error context)
    """
    identifier: str
    imports: list[ImportSpec]
    package: dict
    contexts: list[str]
    symbols: dict[str, list[str]] | None = None
    source_lines: int = 0


class Loader(Protocol):
    """Protocol for resource loaders.

    Loaders match resources and fetch source data. The matching phase
    (can_load) should be fast with minimal I/O - just pattern matching
    to determine if this loader *could* handle the resource.

    The load phase does the actual I/O and may return an error if
    the resource turns out not to exist after all.
    """

    def can_load(self, resource: str) -> LoadMatch | None:
        """Check if this loader might handle the given resource.

        Should be fast - just pattern matching, no I/O if possible.
        Returns match with confidence and identifier, or None.

        Args:
            resource: (str) Resource string from import
        Returns:
            (LoadMatch | None) Match info or None if clearly can't handle
        """
        ...

    def load(self, resource: str, prev_cache_key: str | None = None) -> SourceData:
        """Fetch source data for the given resource.

        Args:
            resource: (str) Resource string to fetch
            prev_cache_key: (str | None) Previous cache key for validation
        Returns:
            (SourceData) Fetched source with metadata
        Raises:
            LoadError: If resource cannot be fetched after all
        """
        ...


class FileLoader:
    """Loader for filesystem paths.

    Handles:
    - Relative paths: "./utils"
    - Absolute paths: "/usr/local/lib/comp/utils"
    - Home paths: "~/projects/mylib"
    """

    def __init__(self, base_path: str | None = None, editable: bool = True):
        """Initialize file loader.

        Args:
            base_path: (str | None) Base directory for relative paths
            editable: (bool) Whether files are editable (dev mode)
        """
        self.base_path = base_path
        self.editable = editable

    def can_load(self, resource: str) -> LoadMatch | None:
        """Check if resource looks like a file path.

        Fast check - just string pattern matching, no filesystem access.
        Returns identifier based on normalized path.
        """
        # Starts with ./ / ~/ or looks like path
        # Build identifier: "file://<normalized-path>"
        # Volatility: VOLATILE if editable, LOOSE otherwise
        # Confidence: 1.0 if clear path, 0.5 if ambiguous
        ...

    def load(self, resource: str, prev_cache_key: str | None = None) -> SourceData:
        """Read file from filesystem.

        Raises:
            LoadError: If file doesn't exist or can't be read
        """
        # Resolve path relative to base_path
        # Check for .comp file or .comd directory
        # Get mtime as cache_key
        # If prev_cache_key matches current mtime, could skip read
        # Return SourceData with uri, identifier, cache_key
        ...


class StdLibLoader:
    """Loader for standard library modules.

    Handles:
    - Standard library: "core/math", "core/str"

    Always STABLE volatility (stdlib is versioned with comp).
    """

    def __init__(self, stdlib_path: str):
        """Initialize stdlib loader.

        Args:
            stdlib_path: (str) Path to standard library directory
        """
        self.stdlib_path = stdlib_path

    def can_load(self, resource: str) -> LoadMatch | None:
        """Check if resource is stdlib path.

        Identifier: "stdlib:<module-name>"
        Volatility: STABLE (tied to comp version)
        """
        # Starts with "core/" or other stdlib prefix
        # High confidence if matches pattern
        ...

    def load(self, resource: str, prev_cache_key: str | None = None) -> SourceData:
        """Fetch module from stdlib.

        Cache key is comp version number (stdlib doesn't change within version).
        """
        # Map stdlib name to file path
        # Read from stdlib_path directory
        # Cache key is __version__ from comp module
        ...


class GitLoader:
    """Loader for git repositories.

    Handles:
    - Short form: "comp:pshinners/yolo@2.1.0"
    - Git URL: "git@github.com:user/repo.git#v1.0"

    Volatility depends on version specification:
    - Pinned version (tag/commit): STABLE
    - Branch name: LOOSE
    - No version: VOLATILE
    """

    def __init__(self, cache_dir: str):
        """Initialize git loader.

        Args:
            cache_dir: (str) Directory for caching cloned repos
        """
        self.cache_dir = cache_dir

    def can_load(self, resource: str) -> LoadMatch | None:
        """Check if resource is a git reference.

        Identifier: "git:<host>/<repo>@<version>"
        Parse version to determine volatility.
        """
        # Starts with comp:, git@, https://github, etc
        # Parse into repo and version
        # Identifier: normalized repo@version
        # Volatility: STABLE if tag, LOOSE if branch, VOLATILE if none
        ...

    def load(self, resource: str, prev_cache_key: str | None = None) -> SourceData:
        """Clone/fetch git repo and return source.

        Cache key is commit SHA.
        """
        # Parse repo and version/tag
        # Clone to cache_dir or update existing
        # Checkout version/tag
        # Get commit SHA as cache_key
        # Read module file
        ...


class HttpLoader:
    """Loader for HTTP/HTTPS resources.

    Handles:
    - Direct URLs: "https://example.com/module.comp"
    - API endpoints: "https://api.example.com/schemas/user.json"

    Volatility is VOLATILE unless response has strong caching headers.
    """

    def can_load(self, resource: str) -> LoadMatch | None:
        """Check if resource is HTTP URL.

        Identifier: "http:<url>"
        Default to VOLATILE unless URL hints at version.
        """
        # Parse URL
        # Check for version patterns in URL
        # Confidence based on URL structure
        ...

    def load(self, resource: str, prev_cache_key: str | None = None) -> SourceData:
        """Fetch resource via HTTP.

        If prev_cache_key provided, send If-None-Match or If-Modified-Since.
        Cache key from etag or last-modified header.
        """
        # HTTP GET request with conditional headers
        # Parse response headers for etag/last-modified
        # Handle 304 Not Modified by returning cached
        # Return SourceData with caching metadata
        ...


class Compiler:
    """Base compiler for converting sources to Modules.

    Each compiler type (comp, python, openapi, etc) subclasses this
    to handle its specific source format.
    """

    def __init__(self, loaders: list[Loader]):
        """Initialize compiler with loaders.

        Args:
            loaders: (list[Loader]) Ordered list of loaders to try
        """
        self.loaders = loaders

    def find_loader(self, resource: str) -> tuple[Loader, LoadMatch]:
        """Find best loader for this resource.

        Tries all loaders, picks highest confidence match.

        Args:
            resource: (str) Resource string to resolve
        Returns:
            (tuple) (loader, match)
        Raises:
            ValueError: If no loader can handle resource
        """
        # Try all loaders
        # Collect matches with confidence > 0
        # Pick highest confidence
        # If tie, use loader order
        ...

    def fetch(self, resource: str, prev_cache_key: str | None = None) -> SourceData:
        """Fetch source data using best loader.

        Args:
            resource: (str) Resource to fetch
            prev_cache_key: (str | None) Previous cache key for validation
        Returns:
            (SourceData) Fetched source data
        """
        loader, match = self.find_loader(resource)
        return loader.load(resource, prev_cache_key)

    def extract_inventory(self, source: SourceData) -> ModuleMetadata:
        """Phase 2: Extract module inventory without full compilation.

        CACHEABLE - results can be stored and reused.
        PARALLELIZABLE - can scan multiple modules concurrently.

        Fast first pass to get imports and symbols for dependency resolution.
        Should be resilient to syntax errors where possible.

        Args:
            source: (SourceData) Source to analyze
        Returns:
            (ModuleMetadata) Extracted inventory
        Raises:
            CompileError: If inventory cannot be extracted (with line number)
        """
        raise NotImplementedError

    def compile(self, source: SourceData, dependencies: dict[str, "Module"]) -> "Module":
        """Phase 3: Fully compile source into a Module.

        CACHEABLE - compiled Module can be stored and reused.
        Requires dependencies already compiled.

        Args:
            source: (SourceData) Source to compile
            dependencies: (dict) Imported modules keyed by namespace
        Returns:
            (Module) Compiled module with ASTs and documentation
        Raises:
            CompileError: If compilation fails (with line number and position)
        """
        raise NotImplementedError


class CompCompiler(Compiler):
    """Compiler for .comp source files."""

    def extract_inventory(self, source: SourceData) -> ModuleMetadata:
        """Extract inventory using first-pass scanner.

        Uses _firstpass.first_pass() to get chunks.
        Extracts:
        - !import declarations → ImportSpec with line numbers
        - !mod package = ... data
        - !context definitions
        - Function/shape/tag/handle names from chunks

        NOTE: Tags may have hierarchical definitions not in chunks,
        so tag list may be incomplete. Full parse needed for complete list.
        """
        # Use comp.first_pass() to get chunks
        # Find all chunks with keyword="import", parse into ImportSpec
        # Find chunks with keyword="mod" where name="package"
        # Find chunks with keyword="context"
        # Collect symbol names from chunks (func, shape, handle names)
        # Note: tag list may be incomplete due to hierarchy
        ...

    def compile(self, source: SourceData, dependencies: dict[str, "Module"]) -> "Module":
        """Compile .comp file to Module.

        Full parse and compilation with all dependencies available.
        """
        # Parse AST from source
        # Create Module object
        # Process imports (already resolved in dependencies)
        # Compile functions, shapes, tags (including hierarchy), handles
        # Finalize module
        ...


class PythonCompiler(Compiler):
    """Compiler for Python modules.

    Wraps Python modules as Comp modules, exposing functions
    and type hints as Comp shapes.
    """

    def extract_inventory(self, source: SourceData) -> ModuleMetadata:
        """Extract inventory from Python module.

        Python modules have no !import in Comp sense.
        Extract from docstring, __version__, etc.
        """
        # No imports (Python handles its own)
        # Parse with ast.parse for safety (don't exec yet)
        # Extract module docstring, __version__ as package metadata
        # No contexts
        # Collect function/class names from AST
        ...

    def compile(self, source: SourceData, dependencies: dict[str, "Module"]) -> "Module":
        """Import Python module and wrap as Comp Module."""
        # Import Python module (now safe to exec)
        # Inspect functions, classes
        # Create Comp wrapper functions
        # Convert type hints to shapes
        ...


class JsonSchemaCompiler(Compiler):
    """Compiler for JSON Schema definitions.

    Converts JSON Schema into Comp shapes.
    Foreign imports have same interface - provide inventory, then compile.
    """

    def extract_inventory(self, source: SourceData) -> ModuleMetadata:
        """Extract inventory from JSON Schema.

        Schema file is foreign import - no comp imports,
        but provides same inventory interface.
        """
        # Parse JSON
        # No imports or contexts
        # Extract title, description, version as package metadata
        # Collect schema definition names as shape symbols
        ...

    def compile(self, source: SourceData, dependencies: dict[str, "Module"]) -> "Module":
        """Convert JSON Schema to Module with shapes."""
        # Parse JSON Schema
        # Create ShapeDef objects from schema
        # Build Module with generated shapes
        ...


class ImportManager:
    """Orchestrates the import resolution and compilation process.

    Manages two-tier caching:
    1. Inventory cache (ModuleMetadata) - fast dependency resolution
    2. Module cache (compiled Module) - full compilation

    The caching backend (likely sqlite) stores both tiers separately.
    """

    def __init__(self, compilers: dict[str, Compiler], inventory_cache=None, module_cache=None):
        """Initialize import manager.

        Args:
            compilers: (dict) Map of compiler type to Compiler instance
            inventory_cache: (object | None) Cache for ModuleMetadata (fast tier)
            module_cache: (object | None) Cache for compiled Modules (full tier)
        """
        self.compilers = compilers
        self.inventory_cache = inventory_cache
        self.module_cache = module_cache

    def get_compiler(self, compiler_type: str) -> Compiler:
        """Get compiler for the given type.

        Args:
            compiler_type: (str) Compiler type (comp, python, etc)
        Returns:
            (Compiler) Compiler instance
        Raises:
            ValueError: If compiler type not registered
        """
        if compiler_type not in self.compilers:
            raise ValueError(f"Unknown compiler type: {compiler_type}")
        return self.compilers[compiler_type]

    def get_inventory(self, import_spec: ImportSpec) -> tuple[ModuleMetadata, SourceData]:
        """Get module inventory, checking cache first.

        Args:
            import_spec: (ImportSpec) Import to resolve
        Returns:
            (tuple) (metadata, source_data) for later compilation
        """
        # Get compiler
        # Find loader and match
        # Check inventory_cache with identifier
        # If cached and volatility allows, check prev_cache_key
        # If cache valid, return cached inventory
        # Otherwise fetch source
        # Extract inventory
        # Cache inventory with identifier and cache_key
        ...

    def resolve_import(self, import_spec: ImportSpec, module_cache_only: bool = False) -> "Module":
        """Resolve a single import specification.

        Args:
            import_spec: (ImportSpec) Import to resolve
            module_cache_only: (bool) Only check module cache, don't compile
        Returns:
            (Module) Resolved and compiled module
        """
        # Check module_cache first
        # If module_cache_only and not found, raise
        # Get inventory (may use inventory_cache)
        # Recursively resolve dependencies from inventory.imports
        # Compile with dependencies
        # Cache full module
        # Return module
        ...

    def build_module_tree(self, compiler_type: str, resource: str) -> "Module":
        """Build complete module tree from entry point.

        Recursively resolves all imports, building the full dependency graph.
        Uses inventory cache for fast dependency resolution, then compiles.

        Args:
            compiler_type: (str) Compiler for entry module
            resource: (str) Resource for entry module
        Returns:
            (Module) Entry module with all dependencies loaded
        """
        # Create ImportSpec for entry point
        # Get inventory for entry
        # Build dependency graph from inventories (fast - uses inventory cache)
        # Detect circular dependencies
        # Compile in dependency order (leaves first)
        # Return root module
        ...

    def invalidate_cache(self, identifier: str):
        """Invalidate cached data for given identifier.

        Clears both inventory and module caches.

        Args:
            identifier: (str) Module identifier to invalidate
        """
        # Remove from inventory_cache
        # Remove from module_cache
        ...
