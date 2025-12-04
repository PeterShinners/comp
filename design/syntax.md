# Syntax and Style Guide

Description of the language syntax and requirements. This doesn't cover the
features in detail, but describes how they must be written.

## Whitespace

Whitespace is completely optional in most places of the language. Whitespace can
consist of any amount of spaces, tabs, extra lines or indentation.

The only place whitespace is required is between fields of a structure and
between the operations a function or structure.

The standard style uses:

- Tabs for indentation
- Lines under 100 characters when reasonable
- Space around binary operators
- Space between function name and container for arguments

This said; the language is flexible and allows for whatever format feels most
readable and editable for your current project.

```comp
tight=:{"oneline"}  # No spacing
spacey       = :arg ~num  # Wild spacing
     { prose and docs___
            var.first = 
    1 var.second =arg
}
```

## Tokens

Tokens are used for naming variables, functions, tags, and nearly everything in
the language. Tokens have the following rules:

- Use kebab-case with hyphens as word separators
  - No leading or trailing hyphens allowed
- No leading digits (digits allowed after first character)
- Leading underscores are allowed
- Final character may be a question mark `?`
- Characters are case sensitive
- Follow the UAX #31 specification for valid unicode tokens
  - With allowances for previously mentioned special characters

This unicode UAX #31 is the same character set used by languages like Rust and
Python. These are combined with a set of preferred patterns:

- Prefer lowercase tokens
- Prefer boolean functions and fields with a trailing `?`
- Operators at the start (`|`) when splitting long lines

The language convention is to use all lowercase characters when writing purely
Comp-specific identifiers. When interfacing with other languages or data
specifications, use capitalizations and underscores where preferred.

The style preference is to use hyphens as word separators instead of compacting
token names into abnormal compound words.

The style of using lowercase words with hyphen separators is referred to as
**kebab-case**.

Allowed tokens (although not always preferred)

- `html5`
- `Content-Accept`
- `_parity_bit?`
- `用户名`

## Identifier Fields

Most identifiers will use a chain of dotted field names, like `one.two.three`.

There are additional ways to reference field names that do not follow token
naming rules. Any expression and value type can be used as a field name. This is
done by wrapping the name in single quotes. This allows any type of value, like
numbers, booleans, tags and anything else. Like `'2+4'` or `'#status.ok'`.

Fields can also be referenced positionally. This is done using the `#` with a
number value. Like `#3` or `#0`. This can also use a mathemetic expression
wrapped in parenthesis to compute an index `#(2+2)`.

Any string can also be used as a field reference when wrapped in double quotes.
Although this does not work to reference the first level of a field name, only
nested fields can use this. Like `"Full Name"`.

These types of field names can be combined in a single identifier.

```comp
records.#0."Owners".'var.owner-name'.active?
```

## Struct literals

Structs are usually created from code surrounded by curly braces `{}`. These can
contain any mix of positional fields and named fields, which are separated by
any whitespace. All values have a positional order, even the named fields.

The language provides two alternative sets of braces for creating structs. These
result in regular structs, but the syntax used to define them is somewhat
changed.

- `[]` literals struct converts tokens and numbers into a struct of positional
  literals
- `()` statement struct takes whatever the final expression is and uses that as
  the struct value.

```comp
{1 2 z=3}
[one two 3]  # {"one" "two" 3}
(color="red" 5)  # 5
```

These types of containers can be used interchangeably in many parts of the
language

- Struct literals
- Function call arguments
- Function body definition
- Block body definition

More details about how scopes and created and referenced is in the
[Struct](struct.md) documentation.

## Comments and Documentation

Comp uses `#` hashes to create line comments. Everything following the `#` until
the end of the line is ignored by the parser. There is no support for block
comments.

The language does not do any interpretation of the comment contents. Everything
from the begin of the comment to the end of the line is strictly ignored.

Each struct and the module itself can define optional textual documentation for
that object. This is separated from the regular struct body with a `___` symbol.

This can be done inline for compact definition, but is often placed on its own
line. The documentation text is used as-is, even line comments it may contain
are treated as regular text, making it ideal for code examples and more.

The text will be unindented to match whatever indentation is used for the second
line.

```comp
The save functions will error if the given resources are not found
or do not have proper permissions.

### Markdown

It's possible that block documentation will be interpreted as markdown
in many contexts. What does this mean? Only time can tell.
___

save = ~{data} {
    Process different types of data appropriately
    ___
    # Function implementation
}

color = {red ___ 1 0 0}

```

## Operator Reference

**Mathematical operators:**

- `+`, `-`, `*`, `/` - Arithmetic operations  
- `==`, `!=` - Equality comparison
- `<`, `<=`, `>`, `>=` - Ordered comparison

**Logical operators:**

- `&&`, '||' - Logical AND and OR (short-circuiting)
- `!!` - Logical NOT (boolean negation)

All logical operators use double characters for consistency and clarity

**Pipeline and function operators:**

- `|` - Pipeline function chaining
- `|?` - Pipeline fallback operator

**Assignment operators:**

- `=` - Normal assignment
- `=*` - Strong assignment (resists overwriting)  
- `=?` - Weak assignment (only if undefined)

**Special operators:**

- `??` - Provide fallback value
- `~` - Shape definition
- `:` - Block or function definition

Comp's use of kebab case conflicts with use of the mathematic subtraction
operator between two tokens. For these cases an alternative syntax must be
chosen.

- `a - b` use spaces around the operator
- `a+-b` an add of the mathematic is the same as subtraction
- `(a)-(b)` one or both tokens must be wrapped in parenthesis

## Scope Reference

List of all named scopes, where they are defined, where they are accessible,
how they work, and when they can be modified.

- mod
- my
- pkg
- import
- context
- (pipeline input) gets arbitrary name per function
- (function args) gets arbitrary name per function
- var
