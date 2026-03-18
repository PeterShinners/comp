"""Callout: validation results emitted during comp analysis.

Callouts are the output of the validation pipeline — everything from parse
errors to idiomatic style hints. They are modelled after cop nodes: plain
Python objects with __slots__, lightweight to create, convertible to Value
structs for comp-side analysis.

Severity levels (low ordinal = high severity):
    ERROR   — code cannot run correctly; stops deeper analysis of current scope
    WARNING — legal but probably wrong
    INFO    — notable but intentional (e.g. shadowed definition)
    HINT    — style / idiomatic, low signal

Phases (in pipeline order):
    PHASE_PARSE    — lark grammar / token errors
    PHASE_COP      — cop node construction, resolution, and folding
    PHASE_CODEGEN  — instruction generation

Notes are leaf attachments on a Callout — a message with an optional source
location. They have no severity or code of their own; they enrich the parent
(e.g. "did you mean X?", "first defined here").
"""

__all__ = [
    "Span",
    "Location",
    "Note",
    "Callout",
    "Collector",
    "ERROR",
    "WARNING",
    "INFO",
    "HINT",
    "PHASE_PARSE",
    "PHASE_COP",
    "PHASE_CODEGEN",
    "parse_callouts",
    "cop_callouts",
    "code_callouts",
]

# Severity level constants
ERROR = "error"
WARNING = "warning"
INFO = "info"
HINT = "hint"

_SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2, HINT: 3}

# Pipeline phase constants
PHASE_PARSE = "parse"
PHASE_COP = "cop"
PHASE_CODEGEN = "codegen"

_PHASE_ORDER = {PHASE_PARSE: 0, PHASE_COP: 1, PHASE_CODEGEN: 2}


def _severity_passes(severity, min_severity):
    """True if severity is at least as severe as min_severity."""
    return _SEVERITY_ORDER.get(severity, 99) <= _SEVERITY_ORDER.get(min_severity, 99)


class Span:
    """Source location: file path, line, column, and character length.

    line and col are 1-based. length=0 indicates a point location (no span).

    Attributes:
        file:   (str) Source file path
        line:   (int) 1-based line number
        col:    (int) 1-based column number
        length: (int) Character count; 0 for a point location
    """

    __slots__ = ("file", "line", "col", "length")

    def __init__(self, file, line, col, length=0):
        self.file = file
        self.line = line
        self.col = col
        self.length = length

    def __repr__(self):
        return f"Span({self.file}:{self.line}:{self.col}+{self.length})"


class Location:
    """A span with an optional descriptive label.

    Used for the primary location and each entry in a callout's related list,
    where the label contextualises the location (e.g. "first defined here").

    Attributes:
        span:  (Span) Source location
        label: (str | None) Optional human-readable label for this location
    """

    __slots__ = ("span", "label")

    def __init__(self, span, label=None):
        self.span = span
        self.label = label

    def __repr__(self):
        label_part = f" {self.label!r}" if self.label else ""
        return f"Location({self.span!r}{label_part})"


class Note:
    """An attached enrichment on a Callout — no severity or code of its own.

    Notes are leaves: they cannot contain further notes. Used for suggestions
    and secondary context like "did you mean X?" or "declared here".

    Attributes:
        message:  (str) Human-readable note text
        location: (Location | None) Optional source location for this note
    """

    __slots__ = ("message", "location")

    def __init__(self, message, location=None):
        self.message = message
        self.location = location

    def __repr__(self):
        loc = f" {self.location!r}" if self.location else ""
        return f"Note({self.message!r}{loc})"


class Callout:
    """A single validation result from any phase of the build pipeline.

    Attributes:
        severity: (str) ERROR | WARNING | INFO | HINT
        code:     (str) Stable identifier, e.g. "duplicate-definition"
        message:  (str) Human-readable description
        phase:    (str | None) Pipeline phase that produced this callout
        primary:  (Location | None) Primary source location
        related:  (list[Location]) Secondary labeled locations
        notes:    (list[Note]) Attached notes/suggestions (leaves, no severity)
    """

    __slots__ = ("severity", "code", "message", "phase", "primary", "related", "notes")

    def __init__(self, severity, code, message, phase=None, primary=None,
                 related=(), notes=()):
        self.severity = severity
        self.code = code
        self.message = message
        self.phase = phase
        self.primary = primary
        self.related = list(related)
        self.notes = list(notes)

    def __repr__(self):
        loc = f" {self.primary!r}" if self.primary else ""
        return f"Callout({self.severity} {self.code!r}{loc})"


class Collector:
    """Accumulates callouts across analysis phases and definition scopes.

    Scopes map to definition boundaries — push one per definition being
    analysed so that errors can be scoped. scope_has_errors() lets callers
    bail out of deeper analysis without stopping work on sibling definitions.

    The phase gate enforces pipeline ordering: once a phase has produced
    errors, higher-ordinal phases are suppressed to prevent phantom cascades.

    Usage:
        col = Collector()
        col.push_scope("my-func")
        col.report(Callout(ERROR, "bad-syntax", "...", phase=PHASE_PARSE))
        if col.scope_has_errors():
            col.pop_scope()
            # skip further analysis of this definition
        col.pop_scope()
    """

    def __init__(self):
        self._callouts = []
        self._scope_stack = []    # list[str] — current scope path
        self._scope_errors = {}   # scope_name -> bool
        self._max_phase = None    # ordinal of earliest phase that has errors

    def report(self, callout):
        """Add a callout to the collection.

        Suppresses callouts from phases later than the earliest phase with
        errors — prevents phantom cascades like C++'s missing-include floods.

        Args:
            callout: (Callout) The callout to record
        """
        if callout.phase is not None and self._max_phase is not None:
            incoming = _PHASE_ORDER.get(callout.phase, 99)
            if incoming > self._max_phase:
                return  # suppress — earlier phase already has errors

        self._callouts.append(callout)

        if callout.severity == ERROR:
            if callout.phase is not None:
                phase_ord = _PHASE_ORDER.get(callout.phase, 99)
                if self._max_phase is None or phase_ord < self._max_phase:
                    self._max_phase = phase_ord
            if self._scope_stack:
                self._scope_errors[self._scope_stack[-1]] = True

    def push_scope(self, name):
        """Enter a new definition scope.

        Args:
            name: (str) Scope identifier, typically the definition name
        """
        self._scope_stack.append(name)
        self._scope_errors.setdefault(name, False)

    def pop_scope(self):
        """Leave the current definition scope."""
        if self._scope_stack:
            self._scope_stack.pop()

    def scope_has_errors(self):
        """True if the current scope has any ERROR-severity callouts.

        Returns:
            (bool) Whether to bail out of deeper analysis for this scope
        """
        if not self._scope_stack:
            return False
        return self._scope_errors.get(self._scope_stack[-1], False)

    def has_errors(self):
        """True if any collected callout has ERROR severity.

        Returns:
            (bool)
        """
        return any(c.severity == ERROR for c in self._callouts)

    @property
    def callouts(self):
        """(list[Callout]) All collected callouts in order."""
        return list(self._callouts)

    def by_severity(self, severity):
        """Return callouts matching the given severity.

        Args:
            severity: (str) ERROR | WARNING | INFO | HINT

        Returns:
            (list[Callout])
        """
        return [c for c in self._callouts if c.severity == severity]

    def by_phase(self, phase):
        """Return callouts from the given phase.

        Args:
            phase: (str) PHASE_PARSE | PHASE_COP | PHASE_CODEGEN

        Returns:
            (list[Callout])
        """
        return [c for c in self._callouts if c.phase == phase]


# ---------------------------------------------------------------------------
# Callout generation functions
# ---------------------------------------------------------------------------
# Each function analyses a specific build artifact and appends callouts to
# the module or definition. The min_severity threshold lets callers skip
# validators that cannot produce callouts at the requested severity — e.g.
# normal execution passes ERROR so INFO/HINT validators are never invoked.
# ---------------------------------------------------------------------------

def parse_callouts(tree, source, file, module, min_severity=ERROR):
    """Validate a lark grammar tree, appending callouts to module.callouts.

    Called after lark_parse succeeds. Parse errors that prevent lark from
    producing a tree at all are caught by the caller and turned into
    module-level ERROR callouts directly.

    Args:
        tree:         (lark.Tree) Parsed grammar tree
        source:       (str) Original source text
        file:         (str) Source file path (for Span construction)
        module:       (Module) Module to append callouts to
        min_severity: (str) Minimum severity to report; skip cheaper checks
    """
    # Validators to be added here
    pass


def cop_callouts(definition, min_severity=ERROR, interp=None):
    """Validate cop nodes on a Definition, appending to definition.callouts.

    Works on whichever cop stage the definition has reached: original_cop
    (raw), resolved_cop (names resolved and folded). Callers should prefer
    resolved_cop when available.

    Loads the callout stdlib module and calls validate-cop from comp code.
    The comp-side function walks the COP tree and returns callout structs.

    Args:
        definition:   (Definition) Definition whose cop nodes to validate
        min_severity: (str) Minimum severity to report
        interp:       (Interp | None) Interpreter instance for calling comp code
    """
    if interp is None:
        return

    cop = definition.resolved_cop or definition.original_cop
    if cop is None:
        return

    import comp

    # Map severity string to the callout tag
    severity_tags = {
        ERROR: "callout.error",
        WARNING: "callout.warning",
        INFO: "callout.info",
        HINT: "callout.hint",
    }
    severity_tag_name = severity_tags.get(min_severity, "callout.warning")

    try:
        callout_mod = interp.module("callout")
        interp.build(callout_mod)
    except Exception:
        return

    # Resolve the severity tag from the callout module
    callout_defs = callout_mod.definitions()
    severity_def = callout_defs.get(severity_tag_name)
    if severity_def is None or severity_def.value is None:
        return
    severity_val = severity_def.value

    try:
        args = comp.Value.from_python({"min-severity": severity_val})
        result = interp.call_function(callout_mod, "validate-cop", piped=cop, args=args)
    except Exception:
        return

    # Convert result struct of callout values into Python Callout objects
    if not isinstance(result.data, dict):
        return

    for val in result.data.values():
        if not isinstance(val.data, dict):
            continue
        callout = _value_to_callout(val)
        if callout is not None:
            if definition.callouts is None:
                definition.callouts = []
            definition.callouts.append(callout)


def _value_to_callout(val):
    """Convert a comp Value (callout struct) to a Python Callout object.

    Args:
        val: (Value) A comp struct matching the callout shape

    Returns:
        (Callout | None) The converted callout, or None on failure
    """
    import comp

    try:
        severity_key = comp.Value.from_python("severity")
        code_key = comp.Value.from_python("code")
        message_key = comp.Value.from_python("message")
        phase_key = comp.Value.from_python("phase")

        severity_val = val.data.get(severity_key)
        code_val = val.data.get(code_key)
        message_val = val.data.get(message_key)
        phase_val = val.data.get(phase_key)

        if severity_val is None or code_val is None or message_val is None:
            return None

        # Extract severity tag name
        if isinstance(severity_val.data, comp.Tag):
            severity = severity_val.data.qualified.split(".")[-1]
        else:
            severity = str(severity_val.data)

        code = str(code_val.data) if code_val else ""
        message = str(message_val.data) if message_val else ""

        phase = None
        if phase_val is not None and isinstance(phase_val.data, comp.Tag):
            phase = phase_val.data.qualified.split(".")[-1]

        return Callout(
            severity=severity,
            code=code,
            message=message,
            phase=phase,
        )
    except Exception:
        return None


def code_callouts(definition, min_severity=ERROR):
    """Validate generated instructions on a Definition, appending to definition.callouts.

    Args:
        definition:   (Definition) Definition with instructions populated
        min_severity: (str) Minimum severity to report
    """
    # Validators to be added here
    pass
