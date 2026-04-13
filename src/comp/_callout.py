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

Callouts currently carry a single primary location plus core metadata.
"""

__all__ = [
    "Span",
    "Location",
    "Callout",
    "ERROR",
    "WARNING",
    "INFO",
    "HINT",
    "PHASE_PARSE",
    "PHASE_COP",
    "PHASE_CODEGEN",
]

import sys
import comp

# Severity level constants
ERROR = "error"
WARNING = "warning"
INFO = "info"
HINT = "hint"

# Pipeline phase constants
PHASE_PARSE = "parse"
PHASE_COP = "cop"
PHASE_CODEGEN = "codegen"


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

    Used for a callout's primary source location, where the label can provide
    extra context when needed.

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


class Callout:
    """A single validation result from any phase of the build pipeline.

    Attributes:
        severity: (str) ERROR | WARNING | INFO | HINT
        code:     (str) Stable identifier, e.g. "duplicate-definition"
        message:  (str) Human-readable description
        phase:    (str | None) Pipeline phase that produced this callout
        primary:  (Location | None) Primary source location
    """

    __slots__ = ("severity", "code", "message", "phase", "primary", "definition_name")

    def __init__(self, severity, code, message, phase=None, primary=None):
        self.severity = severity
        self.code = code
        self.message = message
        self.phase = phase
        self.primary = primary
        self.definition_name = None

    def __repr__(self):
        loc = f" {self.primary!r}" if self.primary else ""
        return f"Callout({self.severity} {self.code!r}{loc})"


# ---------------------------------------------------------------------------
# Callout generation functions
# ---------------------------------------------------------------------------
# Each function analyses a specific build artifact and returns callouts.
# The min_severity threshold lets callers skip validators that cannot produce
# callouts at the requested severity — e.g. normal execution passes ERROR
# so INFO/HINT validators are never invoked.
# ---------------------------------------------------------------------------

def _source_line_snippet(callout_mod, row, col, end_col):
    """Format a source-line snippet from callout.comp for error output."""
    try:
        csrc = callout_mod.source.content.splitlines()
        if 1 <= row <= len(csrc):
            src_line = csrc[row - 1].rstrip("\n")
            span = max(1, end_col - col) if end_col and end_col > col else 1
            caret = " " * (col - 1) + "^" * span
            return f"\n  --> callout.comp:{row}:{col}\n   | {src_line}\n   | {caret}"
    except (AttributeError, TypeError, IndexError):
        pass
    return f"\n  --> callout.comp:{row}:{col}"


def _extract_validator_location(fail_val, callout_mod):
    """Extract validator crash location from a comp.CompFail's structured value.

    The fail value may carry a 'cop' field pointing at the COP node where
    the failure originated (inside the validator), plus a 'frame' field
    naming the executing function.
    """
    info = ""
    if not isinstance(fail_val.data, dict):
        return info
    # Check for frame info (which validator function was running)
    frame_key = comp.Value.from_python("frame")
    frame_val = fail_val.data.get(frame_key)
    if frame_val is not None and isinstance(frame_val.data, str):
        info += f"\n  in validator: {frame_val.data}"
    # Check for cop node with position info
    cop_key = comp.Value.from_python("cop")
    cop_val = fail_val.data.get(cop_key)
    if cop_val is not None and not isinstance(cop_val.data, comp.Tag):
        try:
            pos = cop_val.field("pos")
            if pos is not None:
                vrow = pos.to_python(0)
                vcol = pos.to_python(1)
                vend_col = pos.to_python(3)
                info += _source_line_snippet(callout_mod, vrow, vcol, vend_col)
        except (KeyError, AttributeError, IndexError, TypeError):
            pass
    return info


def _extract_validator_location_from_exc(exc, callout_mod):
    """Extract validator crash location from an exception's cop_node."""
    info = ""
    cop_node = getattr(exc, "cop_node", None)
    if cop_node is not None:
        try:
            pos = cop_node.field("pos")
            if pos is not None:
                vrow = pos.to_python(0)
                vcol = pos.to_python(1)
                vend_col = pos.to_python(3)
                info += _source_line_snippet(callout_mod, vrow, vcol, vend_col)
        except (KeyError, AttributeError, IndexError, TypeError):
            pass
    return info


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
        raise ValueError("cop_callouts requires an initialized Interp")

    cop = definition.resolved_cop or definition.original_cop
    if cop is None:
        return []

    # Map severity string to the callout tag
    severity_tags = {
        ERROR: "callout.severity.error",
        WARNING: "callout.severity.warning",
        INFO: "callout.severity.info",
        HINT: "callout.severity.hint",
    }
    severity_tag_name = severity_tags.get(min_severity, "callout.severity.warning")

    callout_mod = interp._callout_mod
    if callout_mod is None:
        err = comp.CodeError("Validation runtime is not initialized (callout module missing)")
        err.callout_code = "validator-not-initialized"
        raise err

    # Resolve the severity tag from the callout module
    callout_defs = callout_mod.definitions()
    severity_def = callout_defs.get(severity_tag_name)
    if severity_def is None or severity_def.value is None:
        err = comp.CodeError("Validation runtime is corrupted: callout severity tag not found")
        err.callout_code = "validator-runtime-corrupt"
        raise err
    severity_val = severity_def.value

    validator_def = callout_defs.get("validate")
    if validator_def is None or validator_def.value is None:
        err = comp.CodeError("Validation runtime is corrupted: callout validate function not found")
        err.callout_code = "validator-runtime-corrupt"
        raise err

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
        # Run validators on resolved (post-fold) COP
        frame = comp.ExecutionFrame(env, interp=interp, module=callout_mod)
        result = frame.invoke_block(validator_def.value, args, piped=cop)
    except comp.CompFail as e:
        fail_val = e.value
        msg = "(unknown)"
        if isinstance(fail_val.data, dict):
            msg_key = comp.Value.from_python("message")
            msg_val = fail_val.data.get(msg_key)
            if msg_val is not None and isinstance(msg_val.data, str):
                msg = msg_val.data
        validator_info = _extract_validator_location(fail_val, callout_mod)
        defn_name = definition.qualified or getattr(definition, "token", None) or "?"
        err = comp.CodeError(
            f"Validation execution failed while checking `{defn_name}`: {msg}{validator_info}"
        )
        err.callout_code = "validator-failure"
        raise err from e
    except Exception as e:
        defn_name = definition.qualified or getattr(definition, "token", None) or "?"
        validator_info = _extract_validator_location_from_exc(e, callout_mod)
        err = comp.CodeError(
            f"Validation execution raised {type(e).__name__} while checking `{defn_name}`: {e}{validator_info}"
        )
        err.callout_code = "validator-exception"
        raise err from e
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

    Raises:
        comp.CodeError: If the result contains failure values instead of
            valid callout structs (indicates a bug in the validators)
    """
    if not isinstance(result.data, dict):
        return []

    found = []
    for val in result.data.values():
        if not isinstance(val.data, dict):
            # Detect failure strings or other non-struct junk — these indicate
            # the validator pipeline itself broke (e.g. complete-callouts
            # couldn't morph the result).
            if isinstance(val.data, str):
                #print(f"[EXTRACT-DEBUG] Found failure string: {val.data!r} in defn result", file=sys.stderr)
                raise comp.CodeError(
                    f"Validation pipeline produced a failure instead of callouts: {val.data}"
                )
            continue
        # Check for fail structs (have a "fail" key with a Tag value)
        fail_key = comp.Value.from_python("fail")
        fail_val = val.data.get(fail_key)
        if fail_val is not None and isinstance(fail_val.data, comp.Tag):
            msg_key = comp.Value.from_python("message")
            msg_val = val.data.get(msg_key)
            msg = msg_val.data if msg_val and isinstance(msg_val.data, str) else "(no message)"
            raise comp.CodeError(
                f"Validation pipeline failed: {fail_val.data.qualified}: {msg}"
            )
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
    except (AttributeError, TypeError, KeyError, ValueError):
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

