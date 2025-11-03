"""String library module for Comp."""

import comp

# String Transformation Functions

def upper(frame, input_value, args=None):
    """Convert string to uppercase: ["hello" |upper] → "HELLO" """
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|upper expects string, got {type(input_value.data).__name__}")
    return comp.Value(input_value.data.upper())


def lower(frame, input_value, args=None):
    """Convert string to lowercase: ["HELLO" |lower] → "hello" """
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|lower expects string, got {type(input_value.data).__name__}")
    return comp.Value(input_value.data.lower())


def capitalize(frame, input_value, args=None):
    """Capitalize first letter: ["hello world" |capitalize] → "Hello world" """
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|capitalize expects string, got {type(input_value.data).__name__}")
    return comp.Value(input_value.data.capitalize())


def title(frame, input_value, args=None):
    """Convert to title case: ["hello world" |title] → "Hello World" """
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|title expects string, got {type(input_value.data).__name__}")
    return comp.Value(input_value.data.title())


# String Trimming Functions

def strip(frame, input_value, args=None):
    """Remove leading/trailing whitespace: ["  hello  " |strip] → "hello" """
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|strip expects string, got {type(input_value.data).__name__}")

    # Optional chars argument
    chars = None
    if args and args.is_struct:
        chars_key = comp.Value("chars")
        if chars_key in args.struct:
            chars_value = args.struct[chars_key]
            if isinstance(chars_value.data, str):
                chars = chars_value.data

    return comp.Value(input_value.data.strip(chars))


def lstrip(frame, input_value, args=None):
    """Remove leading whitespace: ["  hello" |lstrip] → "hello" """
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|lstrip expects string, got {type(input_value.data).__name__}")

    chars = None
    if args and args.is_struct:
        chars_key = comp.Value("chars")
        if chars_key in args.struct:
            chars_value = args.struct[chars_key]
            if isinstance(chars_value.data, str):
                chars = chars_value.data

    return comp.Value(input_value.data.lstrip(chars))


def rstrip(frame, input_value, args=None):
    """Remove trailing whitespace: ["hello  " |rstrip] → "hello" """
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|rstrip expects string, got {type(input_value.data).__name__}")

    chars = None
    if args and args.is_struct:
        chars_key = comp.Value("chars")
        if chars_key in args.struct:
            chars_value = args.struct[chars_key]
            if isinstance(chars_value.data, str):
                chars = chars_value.data

    return comp.Value(input_value.data.rstrip(chars))


# String Splitting/Joining Functions

def split(frame, input_value, args=None):
    """Split string into list: ["a,b,c" |split ^{sep=","}] → ["a", "b", "c"]"""
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|split expects string, got {type(input_value.data).__name__}")

    # Optional separator argument (default: whitespace)
    sep = None
    maxsplit = -1

    if args and args.is_struct:
        sep_key = comp.Value("sep")
        if sep_key in args.struct:
            sep_value = args.struct[sep_key]
            if isinstance(sep_value.data, str):
                sep = sep_value.data

        max_key = comp.Value("max")
        if max_key in args.struct:
            max_value = args.struct[max_key]
            if hasattr(max_value.data, '__int__'):
                maxsplit = int(max_value.data)

    parts = input_value.data.split(sep, maxsplit)
    # Convert list of strings to list of Values
    return comp.Value([comp.Value(part) for part in parts])


def join(frame, input_value, args=None):
    """Join list into string: [["a", "b", "c"] |join ^{sep=","}] → "a,b,c" """
    # Input should be a struct (lists are represented as structs with Unnamed keys)
    if not input_value.is_struct:
        return comp.fail(f"|join expects list/struct, got {type(input_value.data).__name__}")

    # Optional separator argument (default: empty string)
    sep = ""
    if args and args.is_struct:
        sep_key = comp.Value("sep")
        if sep_key in args.struct:
            sep_value = args.struct[sep_key]
            if isinstance(sep_value.data, str):
                sep = sep_value.data

    # Extract string values from struct (treating it as a list)
    try:
        parts = []
        # Iterate over values in the struct
        for value in input_value.data.values():
            if isinstance(value, comp.Value):
                value = value.as_scalar()
                if isinstance(value.data, str):
                    parts.append(value.data)
                else:
                    parts.append(str(value.data))
            elif isinstance(value, str):
                parts.append(value)
            else:
                parts.append(str(value))

        return comp.Value(sep.join(parts))
    except Exception as e:
        return comp.fail(f"|join error: {e}")


def replace(frame, input_value, args=None):
    """Replace substring: ["hello" |replace ^{old="l" new="r"}] → "herro" """
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|replace expects string, got {type(input_value.data).__name__}")

    if not args or not args.is_struct:
        return comp.fail("|replace requires ^{old=... new=...}")

    old_key = comp.Value("old")
    new_key = comp.Value("new")

    if old_key not in args.struct or new_key not in args.struct:
        return comp.fail("|replace requires ^{old=... new=...}")

    old_value = args.struct[old_key]
    new_value = args.struct[new_key]

    if not isinstance(old_value.data, str) or not isinstance(new_value.data, str):
        return comp.fail("|replace old and new must be strings")

    # Optional count argument
    count = -1
    count_key = comp.Value("count")
    if count_key in args.struct:
        count_value = args.struct[count_key]
        if hasattr(count_value.data, '__int__'):
            count = int(count_value.data)

    result = input_value.data.replace(old_value.data, new_value.data, count)
    return comp.Value(result)


# String Testing Functions

def starts_with_(frame, input_value, args=None):
    """Check if starts with prefix: ["hello" |starts-with? ^{prefix="he"}] → #true"""
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|starts-with? expects string, got {type(input_value.data).__name__}")

    if not args or not args.is_struct:
        return comp.fail("|starts-with? requires ^{prefix=...}")

    prefix_key = comp.Value("prefix")
    if prefix_key not in args.struct:
        return comp.fail("|starts-with? requires ^{prefix=...}")

    prefix_value = args.struct[prefix_key]
    if not isinstance(prefix_value.data, str):
        return comp.fail("|starts-with? prefix must be string")

    result = input_value.data.startswith(prefix_value.data)
    return comp.Value(comp.builtin.TRUE if result else comp.builtin.FALSE)


def ends_with_(frame, input_value, args=None):
    """Check if ends with suffix: ["hello" |ends-with? ^{suffix="lo"}] → #true"""
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|ends-with? expects string, got {type(input_value.data).__name__}")

    if not args or not args.is_struct:
        return comp.fail("|ends-with? requires ^{suffix=...}")

    suffix_key = comp.Value("suffix")
    if suffix_key not in args.struct:
        return comp.fail("|ends-with? requires ^{suffix=...}")

    suffix_value = args.struct[suffix_key]
    if not isinstance(suffix_value.data, str):
        return comp.fail("|ends-with? suffix must be string")

    result = input_value.data.endswith(suffix_value.data)
    return comp.Value(comp.builtin.TRUE if result else comp.builtin.FALSE)


def contains_(frame, input_value, args=None):
    """Check if contains substring: ["hello" |contains? ^{substr="ll"}] → #true"""
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|contains? expects string, got {type(input_value.data).__name__}")

    if not args or not args.is_struct:
        return comp.fail("|contains? requires ^{substr=...}")

    substr_key = comp.Value("substr")
    if substr_key not in args.struct:
        return comp.fail("|contains? requires ^{substr=...}")

    substr_value = args.struct[substr_key]
    if not isinstance(substr_value.data, str):
        return comp.fail("|contains? substr must be string")

    result = substr_value.data in input_value.data
    return comp.Value(comp.builtin.TRUE if result else comp.builtin.FALSE)


# String Utility Functions

def length(frame, input_value, args=None):
    """Get string length: ["hello" |length] → 5"""
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|length expects string, got {type(input_value.data).__name__}")

    return comp.Value(len(input_value.data))


def slice(frame, input_value, args=None):
    """Extract substring: ["hello" |slice ^{start=1 end=4}] → "ell" """
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|slice expects string, got {type(input_value.data).__name__}")

    if not args or not args.is_struct:
        return comp.fail("|slice requires ^{start=... end=...}")

    start_key = comp.Value("start")
    end_key = comp.Value("end")

    start = 0
    end = len(input_value.data)

    if start_key in args.struct:
        start_value = args.struct[start_key]
        if hasattr(start_value.data, '__int__'):
            start = int(start_value.data)

    if end_key in args.struct:
        end_value = args.struct[end_key]
        if hasattr(end_value.data, '__int__'):
            end = int(end_value.data)

    return comp.Value(input_value.data[start:end])


def repeat(frame, input_value, args=None):
    """Repeat string: ["ab" |repeat ^{n=3}] → "ababab" """
    input_value = input_value.as_scalar()
    if not isinstance(input_value.data, str):
        return comp.fail(f"|repeat expects string, got {type(input_value.data).__name__}")

    if not args or not args.is_struct:
        return comp.fail("|repeat requires ^{n=...}")

    n_key = comp.Value("n")
    if n_key not in args.struct:
        return comp.fail("|repeat requires ^{n=...}")

    n_value = args.struct[n_key]
    if not hasattr(n_value.data, '__int__'):
        return comp.fail("|repeat n must be number")

    n = int(n_value.data)
    if n < 0:
        return comp.fail("|repeat n must be non-negative")

    return comp.Value(input_value.data * n)


# Module Creation

def create_module() -> comp.Module:
    """Create the string library module."""
    module = comp.Module()

    # Define all string functions
    functions = (
        # Transformation
        upper,
        lower,
        capitalize,
        title,
        # Trimming
        strip,
        lstrip,
        rstrip,
        # Splitting/Joining
        split,
        join,
        replace,
        # Testing
        starts_with_,
        ends_with_,
        contains_,
        # Utilities
        length,
        slice,
        repeat,
    )

    for py_func in functions:
        name = py_func.__name__
        # Convert trailing _ to ? and _ to -
        if name.endswith("_"):
            name = name[:-1].replace("_", "-") + "?"
        py_function = comp.PythonFunction(name, py_func)
        module.define_function(
            path=[name],
            body=py_function,
            is_pure=True,  # String functions are pure
            doc=py_func.__doc__,
        )

    return module
