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
    PHASE_COP      — cop node resolution and folding
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

    __slots__ = ("severity", "code", "message", "phase", "primary", "related", "notes", "definition_name")

    def __init__(self, severity, code, message, phase=None, primary=None,
                 related=(), notes=()):
        self.severity = severity
        self.code = code
        self.message = message
        self.phase = phase
        self.primary = primary
        self.related = list(related)
        self.notes = list(notes)
        self.definition_name = None

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
# Each function analyses a specific build artifact and returns callouts.
# The min_severity threshold lets callers skip validators that cannot produce
# callouts at the requested severity — e.g. normal execution passes ERROR
# so INFO/HINT validators are never invoked.
# ---------------------------------------------------------------------------

def cop_callouts(definition, min_severity=ERROR, interp=None, namespace=None):
    """Run comp-side validators on a Definition's COP tree.

    Loads the callout stdlib module (if not already cached on the interpreter)
    and calls the unified ``validate`` function which runs all enabled
    validators on the resolved-and-folded COP.

    A context struct is built from the Definition's metadata and passed
    to the comp validators alongside the COP.  Currently carries:

    - ``pure``: whether the definition was declared !pure
    - (future: input_shape, etc.)

    This is an internal function.  External callers should use
    ``Interp.callouts()`` instead.

    Args:
        definition:   (Definition) Definition whose cop nodes to validate
        min_severity: (str) Minimum severity to report
        interp:       (Interp | None) Interpreter instance for calling comp code
        namespace:    (dict | None) Module namespace for callee lookups

    Returns:
        (list) List of Callout objects found, or empty list
    """
    if interp is None:
        return []

    cop = definition.resolved_cop or definition.original_cop
    if cop is None:
        return []

    import comp

    # Map severity string to the callout tag
    severity_tags = {
        ERROR: "callout.error",
        WARNING: "callout.warning",
        INFO: "callout.info",
        HINT: "callout.hint",
    }
    severity_tag_name = severity_tags.get(min_severity, "callout.warning")

    callout_mod = getattr(interp, "_callout_mod", None)
    if callout_mod is None:
        interp._disable_build_validations = getattr(interp, "_disable_build_validations", 0) + 1
        try:
            callout_mod = interp.module("callout")
            interp.build_instructions()
            interp._callout_mod = callout_mod
        except Exception:
            return []
        finally:
            interp._disable_build_validations = max(getattr(interp, "_disable_build_validations", 1) - 1, 0)

    # Resolve the severity tag from the callout module
    callout_defs = callout_mod.definitions()
    severity_def = callout_defs.get(severity_tag_name)
    if severity_def is None or severity_def.value is None:
        return []
    severity_val = severity_def.value

    validator_def = callout_defs.get("validate")
    if validator_def is None or validator_def.value is None:
        return []

    # Build context struct from Definition metadata
    context_val = comp.Value.from_python({"pure": definition.pure})

    # Wrap the namespace as an opaque Value — comp code passes it to is-pure
    # but does not inspect it directly.
    ns_val = comp.Value.from_python(namespace) if namespace else comp.Value.from_python(comp.tag_nil)

    original_cop = definition.original_cop
    original_val = comp.Value.from_python(original_cop) if original_cop else comp.Value.from_python(comp.tag_nil)

    args = comp.Value.from_python({
        "min-severity": severity_val,
        "context": context_val,
        "namespace": ns_val,
        "original": original_val,
    })
    env = {k: d.value for k, d in callout_defs.items() if d.value is not None}
    all_callouts = []
    interp._disable_build_validations = getattr(interp, "_disable_build_validations", 0) + 1
    try:
        from comp._interp import ExecutionFrame, CompFail

        # Run validators on resolved (post-fold) COP
        frame = ExecutionFrame(env, interp=interp, module=callout_mod)
        result = frame.invoke_block(validator_def.value, args, piped=cop)
    except CompFail as e:
        import sys
        fail_val = e.value
        msg = "(unknown)"
        if isinstance(fail_val.data, dict):
            import comp as _comp
            msg_key = _comp.Value.from_python("message")
            msg_val = fail_val.data.get(msg_key)
            if msg_val is not None and isinstance(msg_val.data, str):
                msg = msg_val.data
        defn_name = getattr(definition, "token", None) or "?"
        print(
            f"Callout validator failure in `{defn_name}`: {msg}",
            file=sys.stderr,
        )
        return []
    except Exception as e:
        import sys
        defn_name = getattr(definition, "token", None) or "?"
        print(
            f"Callout validator error in `{defn_name}`: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return []
    finally:
        interp._disable_build_validations = max(getattr(interp, "_disable_build_validations", 1) - 1, 0)

    all_callouts.extend(_extract_callouts(result))
    return all_callouts


def _extract_callouts(result):
    """Recursively extract Callout objects from a comp Value result.

    The validate function returns a nested struct: top-level values may be
    individual callout structs (with severity/code/message) or sub-structs
    grouping callouts from different validators.  This flattens them all.

    Args:
        result: (Value) Struct of callout values (possibly nested)

    Returns:
        (list) Flat list of Callout objects
    """
    if not isinstance(result.data, dict):
        return []

    found = []
    for val in result.data.values():
        if not isinstance(val.data, dict):
            continue
        callout = _value_to_callout(val)
        if callout is not None:
            found.append(callout)
        else:
            # Sub-struct from a validator group — recurse
            found.extend(_extract_callouts(val))
    return found


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
        pos_key = comp.Value.from_python("pos")

        severity_val = val.data.get(severity_key)
        code_val = val.data.get(code_key)
        message_val = val.data.get(message_key)
        phase_val = val.data.get(phase_key)
        pos_val = val.data.get(pos_key)

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

        # Extract primary location from pos struct {row col end_row end_col}
        primary = None
        if pos_val is not None and isinstance(pos_val.data, dict):
            try:
                row = pos_val.to_python(0)
                col = pos_val.to_python(1)
                end_col = pos_val.to_python(3)
                length = max(1, end_col - col) if end_col and end_col > col else 1
                primary = Location(Span(None, row, col, length))
            except (AttributeError, IndexError, TypeError):
                pass

        return Callout(
            severity=severity,
            code=code,
            message=message,
            phase=phase,
            primary=primary,
        )
    except Exception:
        return None


def exception_to_callout(exc, stmt=None, source_file=None):
    """Convert a Python exception from statement processing into an error Callout.

    Args:
        exc: The exception that was raised
        stmt: (dict | None) Statement dict with pos info
        source_file: (str | None) Source file path for location

    Returns:
        (Callout) An error-severity callout
    """
    import comp
    message = getattr(exc, "message", None) or str(exc)
    if isinstance(exc, comp.ParseError):
        code = "parse-error"
        phase = PHASE_PARSE
    else:
        code = "definition-error"
        phase = PHASE_COP

    primary = None
    if stmt and source_file:
        pos = stmt.get("pos")
        if pos and len(pos) >= 2:
            primary = Location(Span(source_file, pos[0], pos[1]))

    return Callout(
        severity=ERROR, code=code, message=message,
        phase=phase, primary=primary,
    )


def callout_to_exception(callout):
    """Promote an error Callout to the appropriate Python exception.

    Args:
        callout: (Callout) The callout to convert

    Returns:
        (Exception) ParseError or CodeError
    """
    import comp
    if callout.phase == PHASE_PARSE:
        return comp.ParseError(callout.message)
    return comp.CodeError(callout.message)
