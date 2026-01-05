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

    Args:
        qualified: Fully qualified name (e.g., "cart", "add.i001")
        module_id: Module token string (not reference)
        original_cop: The original COP node
        shape: Shape constant (comp.shape_block, comp.shape_shape, etc.)
    Attributes:
        qualified: (str) Fully qualified name (e.g., "cart", "add.i001")
        module_id: (str) Module token that owns this definition (avoids circular refs)
        original_cop: (Value) The original COP node from parsing
        resolved_cop: (Value | None) The resolved+folded+optimized COP node
        shape: (Shape) Shape constant indicating definition type
        value: (Value | None) The constant-folded value (Shape/Block/etc) if applicable

    """
    __slots__ = ("qualified", "module_id", "original_cop", "resolved_cop", "shape", "value")

    def __init__(self, qualified, module_id, original_cop, shape):
        self.qualified = qualified
        self.module_id = module_id
        self.original_cop = original_cop
        self.shape = shape
        self.resolved_cop = None  # Filled during identifier resolution
        self.value = None  # Filled during constant folding

    def __repr__(self):
        shape_name = self.shape.qualified
        return f"Definition<{self.qualified}:{shape_name}>"

    def is_resolved(self):
        """(bool) Whether identifiers have been resolved."""
        return self.resolved_cop is not None

    def is_folded(self):
        """(bool) Whether constant folding has been performed."""
        return self.value is not None


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

    def namespace(self, imports=None):
        """(dict) Resolved namespace dict for identifier lookups.

        Each value is a DefinitionSet which will contain at least one definition
        and methods to help validate the various types of lookups (shape,
        call, value)
        """
        if imports is None:
            imports = {}
        if self._namespace is not None:
            return self._namespace

        # Don't try to get system module if we ARE the system module
        if isinstance(self, SystemModule):
            self._namespace = {}
        else:
            self._namespace = dict(SystemModule.get().namespace())
        for import_name, import_module in imports.items():
            import_definitions = import_module.definitions()
            import_namespace = comp._namespace.create_namespace(import_definitions, import_name)
            self._namespace = comp._namespace.merge_namespace(self._namespace, import_namespace, clobber=False)

        defs = self.definitions()
        namespace = comp._namespace.create_namespace(defs, None)
        self._namespace = comp._namespace.merge_namespace(self._namespace, namespace, clobber=True)

        return self._namespace

    def finalize(self, imports=None):
        """Build namespace and resolve identifiers. Auto-calls definitions if needed.

        Args:
            imports: Dict {import_name: Module} of resolved imports

        Returns:
            self (for chaining)
        """
        # Phase 3: Build namespace and resolve identifiers to references
        namespace = self.namespace(imports=imports)
        comp.resolve_identifiers(self._definitions, namespace)

        # Phase 4: Constant folding - create Block/Shape values
        for definition in self._definitions.values():
            # Skip non-Definition objects (e.g., AST module Tags)
            if isinstance(definition, comp.Definition):
                fold_definition(definition)

        self._finalized = True
        return self


class SystemModule(Module):
    """System module singleton with several builtin attributes"""

    _singleton = None

    def __init__(self):
        # Create a minimal ModuleSource for system module
        source = type('obj', (object,), {'resource': 'system', 'content': ''})()
        super().__init__(source)
        self.token = "system#0000"

        # Populate definitions dict with builtin tags and shapes as Definition objects
        # These are pre-folded since they're built-in objects

        self._definitions = {}

        # Helper to create Definition with pre-folded value
        def _create_builtin_def(name, obj, shape_type):
            value = comp.Value.from_python(obj)
            defn = comp.Definition(name, self.token, value, shape_type)
            defn.resolved_cop = value  # Already resolved
            defn.value = value  # Already folded
            return defn

        # Builtin tags - use shape_struct for tag values
        self._definitions['nil'] = _create_builtin_def('nil', comp.tag_nil, comp.shape_struct)
        self._definitions['bool'] = _create_builtin_def('bool', comp.tag_bool, comp.shape_struct)
        self._definitions['bool.true'] = _create_builtin_def('bool.true', comp.tag_true, comp.shape_struct)
        self._definitions['bool.false'] = _create_builtin_def('bool.false', comp.tag_false, comp.shape_struct)
        # Note: 'true' and 'false' shortcuts are created via namespace permutations from 'bool.true' and 'bool.false'
        self._definitions['fail'] = _create_builtin_def('fail', comp.tag_fail, comp.shape_struct)

        # Builtin shapes
        self._definitions['num'] = _create_builtin_def('num', comp.shape_num, comp.shape_shape)
        self._definitions['text'] = _create_builtin_def('text', comp.shape_text, comp.shape_shape)
        self._definitions['struct'] = _create_builtin_def('struct', comp.shape_struct, comp.shape_shape)
        self._definitions['any'] = _create_builtin_def('any', comp.shape_any, comp.shape_shape)
        self._definitions['func'] = _create_builtin_def('func', comp.shape_block, comp.shape_shape)

        # Set convenience attributes for direct access
        self.bool = comp.tag_bool
        self.true = comp.tag_true
        self.false = comp.tag_false
        self.fail = comp.tag_fail
        self.num = comp.shape_num
        self.text = comp.shape_text
        self.struct = comp.shape_struct
        self.any = comp.shape_any
        self.func = comp.shape_block

        # Finalize to build namespace from definitions
        self.finalize()

    @classmethod
    def get(cls):
        """Get system module singleton."""
        # Constructed lazy for first interpreter
        global _system_module
        if SystemModule._singleton is None:
            SystemModule._singleton = cls()
        return SystemModule._singleton

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
    folded_cop = comp._parse.cop_fold(cop)

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


