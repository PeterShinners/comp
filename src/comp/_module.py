"""Module represents a module's namespace at runtime"""

import os

import comp


__all__ = ["Module", "Definition"]


class Definition:
    """A module-level definition that can be referenced.

    Definitions are created during the extraction phase and progressively
    enhanced through the compilation pipeline:
    1. Extract: Create with original_cop and shape
    2. Resolve: Populate resolved_cop with identifier references resolved
    3. Fold: Populate value with constant-folded Shape/Block/etc
    4. Codegen: Populate instructions with bytecode

    Args:
        qualified: Fully qualified name (e.g., "cart", "add.i001")
        module_id: Module token string (not reference)
        original_cop: The original COP node
        shape: Shape constant (comp.shape_block, comp.shape_shape, etc.)
        private: Whether this definition is private to the module
        auto_suffix: Whether this definition has an auto-generated suffix
    Attributes:
        qualified: (str) Fully qualified name (e.g., "cart", "add.i001")
        module_id: (str) Module token that owns this definition (avoids circular refs)
        original_cop: (Value) The original COP node from parsing
        resolved_cop: (Value | None) The resolved+folded+optimized COP node
        shape: (Shape) Shape constant indicating definition type
        value: (Value | None) The constant-folded value (Shape/Block/etc) if applicable
        instructions: (list | None) Bytecode instructions for this definition
        private: (bool) Whether this definition is private to the module
        auto_suffix: (bool) Whether the qualified name has an auto-generated suffix

    """
    __slots__ = ("qualified", "module_id", "original_cop", "resolved_cop", "shape", "value", "instructions", "private", "auto_suffix")

    def __init__(self, qualified, module_id, original_cop, shape, private=False, auto_suffix=False):
        self.qualified = qualified
        self.module_id = module_id
        self.original_cop = original_cop
        self.shape = shape
        self.private = private  # Whether this definition is private to the module
        self.auto_suffix = auto_suffix  # Whether qualified name has auto-generated suffix
        self.resolved_cop = None  # Filled during identifier resolution
        self.value = None  # Filled during constant folding
        self.instructions = None  # Filled during code generation

    def __repr__(self):
        shape_name = self.shape.qualified
        return f"Definition<{self.qualified}:{shape_name}>"

    def is_resolved(self):
        """(bool) Whether identifiers have been resolved."""
        return self.resolved_cop is not None

    def is_folded(self):
        """(bool) Whether constant folding has been performed."""
        return self.value is not None

    def is_compiled(self):
        """(bool) Whether bytecode has been generated."""
        return self.instructions is not None


class Module:
    """A module in the Comp language.

    The module represents the data and code from source code. The module
    is not immediately parsed or loaded into this class. Methods like
    `scan` and `definitions` will incrementally build and prepare
    the module.

    Modules are created and managed by an Interp.
    
    Modules will import and reference other modules with import statements.
    Each import statement can use different compilers and resource locators
    but will always result in this same Module object.
        
    Modules are immutable once finalized. The finalize() method must be called
    before any code from the module can be compiled or executed.
    
    Args:
        source: ModuleSource containing the module's location and content

    """
    _token_counter = os.getpid() & 0xFFFF

    def __init__(self, source):
        if not hasattr(source, 'resource'):
            raise TypeError(f"Module requires a ModuleSource, got {type(source)}")

        self.source = source
        token = source.resource

        # Module token is not attempting to be a secure id,
        # Just to help distinguish conflicting tokens with a non repeating id
        count = hash(token) & 0xFFFF ^ Module._token_counter
        Module._token_counter += 1
        self.token = f"{token}#{count:04x}"

        # Intermediate cached parse passes
        self._scan = None
        self._imports = None
        self._definitions = None
        self._namespace = None
        self._finalized = False

    def __repr__(self):
        return f"Module<{self.token}>"

    def __hash__(self):
        return id(self.token)

    @property
    def is_finalized(self):
        """(bool) Whether the module has been finalized."""
        return self._finalized

    def scan(self):
        """Scan source for imports and metadata (fast, no full parse).

        This is a lightweight operation that extracts module metadata without
        doing a full parse. Useful for dependency resolution and tooling.

        This parse is fairly resilient to simple syntax errors, and 
        may be able to provide module information even when a full parse
        would fail.

        Results are cached.
        
        Returns:
            ScanResult: Object with .imports(), .package(), .docs() methods
        """

        if self._scan is None:
            self._scan = comp._scan.scan(self.source.content)
        return self._scan

    def imports(self):
        """Dictionary of imported modules with metadata.

        Each key is the name the module is imported as. The value is a dictionary
        containing the module object, possible import error, source location,
        documentation, and other known data.

        This requires the module belongs to an Interpreter that has already
        scanned and resolved its imports.

        Returns:
            dict: {name: {"module": Module|None, "error": Exception|None,
                          "source": str, "location": str, "docs": str, ...}}
        """
        if self._imports is None:
            raise comp.ModuleError("Module must belong to an interpreter.")

        imports = {}
        for name, (mod, err) in self._imports.items():
            import_info = {
                "module": mod,
                "error": err,
                "source": None,
                "location": None,
                "docs": None,
            }

            # Extract metadata from module if available
            if mod is not None:
                import_info["source"] = mod.source.resource
                import_info["location"] = mod.source.location
                try:
                    scan = mod.scan()
                    docs = scan.to_python("docs") or []
                    if docs:
                        import_info["docs"] = docs[0].get("content", "")
                except:
                    pass

            imports[name] = import_info
        return imports

    def _register_imports(self, imports, definitions, namespace):
        """Interpreter call to store registered imports and precached data.
        
        These modules are likely not parsed or finalized yet, but the
        interpreter must do this before the complete namespace can be generated.

        if the interpeter has precached information about the module definitions
        or namespace it can be passed now.

        """
        if self._imports is not None:
            raise comp.ModuleError("Module imports already registered.")
        self._definitions = definitions
        self._namespace = namespace
        self._imports = imports

    def definitions(self):
        """Parse source and extract definitions into module.definitions dict.

        This method lazily parses and extracts definitions on first call.
        Subsequent calls are no-ops if definitions already populated.

        Results are cached.

        Returns:
            dict: qualified names strings to Definition objects
        """
        if self._definitions is not None:
            return self._definitions

        parser = comp.lark_parser("comp")
        lark_tree = parser.parse(self.source.content)
        cop_tree = comp._parse.lark_to_cop(lark_tree)
        self._definitions = comp.extract_definitions(cop_tree, self.token)
        return self._definitions

    def namespace(self):
        """(dict) Resolved namespace dict for identifier lookups.

        Each value is a DefinitionSet which will contain at least one definition
        and methods to help validate the various types of lookups (shape,
        call, value)

        This requires the module belongs to an Interpreter that has already
        scanned and resolved its imports.

        """
        if self._namespace is not None:
            return self._namespace

        if self._imports is None:
            raise comp.ModuleError("Cannot build namespace until interpreter registers imports.")

        sys = comp.get_internal_module("system")
        self._namespace = dict(sys.namespace())
        for import_name, (import_module, import_err) in self._imports.items():
            if import_err:
                raise import_err
            import_definitions = import_module.definitions()
            import_namespace = comp._namespace.create_namespace(import_definitions, import_name)
            self._namespace = comp._namespace.merge_namespace(self._namespace, import_namespace, clobber=False)

        defs = self.definitions()
        namespace = comp._namespace.create_namespace(defs, None)
        self._namespace = comp._namespace.merge_namespace(self._namespace, namespace, clobber=True)

        return self._namespace

    def finalize(self):
        """Build namespace and resolve identifiers. Auto-calls definitions if needed.

        Args:
            imports: Dict {import_name: Module} of resolved imports
        """
        if self._namespace is None:
            raise comp.ModuleError("Cannot finalize module until interpreter generates namespace.")
        comp.resolve_identifiers(self._definitions, namespace)

        for definition in self._definitions.values():
            # Skip non-Definition objects (e.g., AST module Tags)
            if isinstance(definition, comp.Definition):
                fold_definition(definition)

        self._finalized = True


def fold_definition(definition):
    """Perform constant folding on a definition to create Shape/Block values.

    This function takes a Definition with resolved_cop and performs constant
    folding to create the final Value. For blocks, this creates Block objects.
    For shapes, this creates Shape objects.

    Args:
        definition: Definition with resolved_cop populated

    Side effects:
        Populates definition.value with the folded constant value
    """
    # Skip if already folded (e.g., SystemModule builtins)
    if definition.value is not None:
        return

    # Use resolved_cop if available, otherwise original_cop
    cop = definition.resolved_cop if definition.resolved_cop is not None else definition.original_cop

    if cop is None:
        return

    # Perform constant folding on the COP tree
    folded_cop = comp.cop_fold(cop)

    # For blocks, create Block objects
    if definition.shape is comp.shape_block:
        try:
            # Extract qualified name and create Block
            private = False  # TODO: Extract from definition or cop
            func_value = comp.create_blockdef(definition.qualified, private, folded_cop)
            definition.value = func_value
            # Keep the folded COP for the function body
            definition.resolved_cop = folded_cop
        except comp.CodeError as e:
            # If can't create func, just keep folded cop
            definition.resolved_cop = folded_cop

    # For shapes, create Shape objects
    elif definition.shape is comp.shape_shape:
        try:
            # Extract qualified name and create Shape
            private = False  # TODO: Extract from definition or cop
            shape_value = comp.create_shapedef(definition.qualified, private, folded_cop)
            definition.value = shape_value
            # Shapes should have no COP after folding (fully resolved)
            definition.resolved_cop = None
        except comp.CodeError as e:
            # If can't create shape, just keep folded cop
            definition.resolved_cop = folded_cop

    # For other values, just perform constant folding
    else:
        # Try to extract constant value from folded cop
        try:
            tag = comp.cop_tag(folded_cop)
            if tag == "value.constant":
                # Extract the constant value
                definition.value = folded_cop.field("value")
                definition.resolved_cop = folded_cop
            elif tag == "value.reference":
                # Keep as reference - will be resolved at build time
                definition.resolved_cop = folded_cop
            else:
                # Keep the folded cop
                definition.resolved_cop = folded_cop
        except (AttributeError, KeyError):
            definition.resolved_cop = folded_cop


