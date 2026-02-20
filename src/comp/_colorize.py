"""Text colorization and styling for terminal output.

Provides lightweight formatting using \\-X- escape-like codes in strings.
Codes are processed by the output builtin when writing to TTY.

Syntax:
    \\-r-  red        \\-g-  green      \\-b-  blue       \\-y-  yellow
    \\-c-  cyan       \\-m-  magenta    \\-w-  white      \\-k-  black
    \\-s-  strong (bold/bright)         \\-d-  dim
    \\-n-  normal (reset all)

Examples:
    "Server \\-s-started\\-n- successfully"
    "Error: \\-r-file not found\\-n-"
    "\\-rs-ALERT\\-n- please check \\-d-the logs\\-n-"

Public API
----------
apply_ansi(text)         → str with ANSI codes applied
strip_codes(text)        → str with color codes removed
should_use_color(stream) → bool (TTY detection + NO_COLOR)
"""

import re
import os


# ANSI escape codes for colors and styles
CODES = {
    "r": "\033[31m",  # red
    "g": "\033[32m",  # green
    "b": "\033[34m",  # blue
    "y": "\033[33m",  # yellow
    "c": "\033[36m",  # cyan
    "m": "\033[35m",  # magenta
    "w": "\033[37m",  # white
    "k": "\033[30m",  # black
    "s": "\033[1m",   # strong (bold/bright)
    "d": "\033[2m",   # dim
    "n": "\033[0m",   # normal (reset)
}


# Pattern to match color codes like \-r-, \-rs-, \-gsd-, etc.
COLOR_CODE_PATTERN = re.compile(r"\\-([rgbycmwksdn]+)-")


def apply_ansi(text):
    """Replace color codes with ANSI escape sequences.
    
    Automatically appends a reset code at the end if any color codes were applied.

    Args:
        text: (str) Text potentially containing \\-X- color codes

    Returns:
        (str) Text with color codes replaced by ANSI sequences, with trailing reset
    """
    replacement_count = [0]  # Use list to allow modification in nested function
    
    def replace_code(match):
        chars = match.group(1)
        # Accumulate ANSI codes for each character
        ansi_codes = "".join(CODES.get(c, "") for c in chars)
        replacement_count[0] += 1
        return ansi_codes

    result = COLOR_CODE_PATTERN.sub(replace_code, text)
    
    # Append reset code if any replacements were made
    if replacement_count[0] > 0:
        result += "\033[0m"
    
    return result


def strip_codes(text):
    """Remove all color codes from text.

    Args:
        text: (str) Text potentially containing \\-X- color codes

    Returns:
        (str) Text with color codes removed
    """
    return COLOR_CODE_PATTERN.sub("", text)


def should_use_color(stream):
    """Determine if color output should be used.

    Checks:
    - Stream is a TTY
    - NO_COLOR environment variable is not set

    Args:
        stream: Output stream (like sys.stdout)

    Returns:
        (bool) True if colors should be applied
    """
    # Check if NO_COLOR env var is set (standard: https://no-color.org/)
    if os.environ.get("NO_COLOR") is not None:
        return False

    # Check if stream is a TTY
    try:
        return stream.isatty()
    except AttributeError:
        # Stream doesn't support isatty() - assume not a TTY
        return False
