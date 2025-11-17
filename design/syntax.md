# Syntax and Style Guide

Description of the language syntax and requirements. This doesn't cover
the features in detail, but describes how they must be written.

## Whitespace

Whitespace is completely optional in most places of the language. Whitespace
can consist of any amount of spaces, tabs, extra lines or indentation.

The only place whitespace is required is between fields of a structure
and between the operations a function or structure.

The standard style uses:

- Tabs for indentation
- Lines under 100 characters when reasonable
- Space around binary operators
- Space between function name and container for arguments

This said; the language is flexible and allows for whatever format feels most readable and editable for your current project.

```comp
mod.primes = {1 3
 5      7}

func tight ~nil {"oneline"}
func       ~nil 
 |spacey
{
                var.first = 
    1 var.second =2
}
```

## Tokens

Tokens are used for naming variables, functions, tags, and nearly
everything in the language. Tokens have the following rules:

- Use kebab-case with hyphens as word separators
  - **No leading or trailing hyphens allowed**
- **No leading digits** (digits allowed after first character)
- Leading underscores are allowed
- Final character may be a question mark `?`
- Characters are case sensitive
- Follow the UAX #31 specification for valid unicode tokens
  - With allowances for previously mentioned special characters

This unicode UAX #31 is the same character set used by languages
like Rust and Python. These are combined with a set of preferred patterns:

- Prefer lowercase tokens
- Prefer boolean functions and fields with a trailing `?`
- Operators at the start (`|`) when splitting long lines

The language convention is to use all lowercase characters when writing purely
Comp-specific identifiers. When interfacing with other languages or data
specifications, use capitalizations and underscores where preferred.

The style preference is to use hyphens as word separators instead of
compacting token names into abnormal compound words.

The style of using lowercase words with hyphen separators is referred to as
**kebab-case**.

Allowed tokens (although not always preferred)
- `html5`
- `Content-Accept`
- `_parity_bit?`
- `用户名`

Several builtin types are prefixed with special characters. These are
needed when referencing these values from the module namespace, 
although they can be assigned to local and context variables used
without the decorators.

- `~` shape definitions and references
- `#` tag definitions and references
- `^` handle definitions and references


## Identifier Fields

Most identifiers will use a chain of dotted field names, like `"one.two.three"`.

There are three ways to reference field names that do not follow token naming rules. Any expression and value type can be used as a field name. This is done by wrapping the name in single quotes. This allows any type of value, like numbers, booleans, tags and anything else. Like `'2+4'` or `'#status.ok'`.

Fields can also be referenced positionally. This is done using the `#` with a number value. Like `#3` or `#0`. This can also use a mathemetic expression wrapped in parenthesis to compute an index `#(2+2)`.

Any string can also be used as a field reference when wrapped in double quotes. Although this does not work to reference the first level of a field name, only nested fields can use this. Like `"Full Name"`.

These types of field names can be combined in a single identifier.

```comp
records.#0."Owners".'var.owner-name'.active?
```

## Struct literals

Structs are usually created from code surrounded by curly braces `{}`.
These can contain any mix of positional fields and named fields,
which are separated by any whitespace.

The language provides two alternative sets of braces for creating structs.
These result in regular structs, but the syntax used to define them is
somewhat changed.

- `[]` literals struct converts tokens and numbers into a struct of positional literals
- `()` statement struct takes whatever the final expression is and uses that as the struct value.

```
{1 2 z=3}
[one two 3]  ; {"one" "two" 3}
(color="red" 5)  ; 5
```

These types of containers can be used interchangeably in many parts of the language

- Struct literals
- Function call arguments
- Function body definition
- Block body definition

More details about how scopes and created and referenced is in the
[Struct](struct.md) documentation.


## Comments and Documentation

Comp uses `;` semicolons to create line comments. Everything following
the `;` until the end of the line is ignored by the parser.
There is no support for block style comments.

The language does not do any interpretation of the comment contents.
Everything from the begin of the comment to the end of the line is strictly
ignored.

Comp can define documentation. This gets attached to objects and
and can be referenced by developer tools to describe those objects
and how they are used.

There are two styles of documentation. 

- Line documentation uses a `--` symbol and uses everything until the end of the current line as documentation.
  - If the `--` is the first (and only) statement on the current line then the   documentation is attached to whatever object follows this line.
  - Otherwise the `--` line document is attached to whatever object or field precedes the documentation.
- Block documentation uses a `---` symbol as the only statement on a line to begin and end a block of documentation.
  - The block documentation is positionally attached to the module. This can be used for grouping functions into described sections.


```comp

---
The save functions will error if the given resources are not found
or do not have proper permissions.

### Markdown

It's likely that block documentation will be interpreted as markdown
in many contexts. What does this mean? Only time can tell.
---

-- "Process different types of data appropriately"
func save ~{data} {
    ; Function implementation
}
```

## Operator Reference

**Mathematical operators:**
- `+`, `-`, `*`, `/` - Arithmetic operations  
- `==`, `!=` - Equality comparison
- `<`, `<=`, `>`, `>=` - Ordered comparison

**Logical operators (symmetric double-character design):**
- `&&` - Logical AND (short-circuiting)
- `||` - Logical OR (short-circuiting)  
- `!!` - Logical NOT (boolean negation)
- Note: All logical operators use double characters for consistency and clarity

**Pipeline and function operators:**
- `|` - Pipeline attachment
- `|?` - Fallback atttachment

**Assignment operators:**
- `=` - Normal assignment
- `=*` - Strong assignment (resists overwriting)  
- `=?` - Weak assignment (only if undefined)

**Special operators:**
- `??` - Provide fallback value
- `~` - Shape morphing
- `..` - Struct update
- `???` - Placeholder for unimplemented code
- `:` - Create block for deferred execution

Comp's use of kebab case conflicts with use of the mathematic subtraction
operator between two tokens. For these cases an alternative syntax must be
chosen.
- `a - b` use spaces around the operator
- `a+-b` an add of the mathematic is the same as subtraction
- `(a)-(b)` one or both tokens must be wrapped in parenthesis


### Struct morph and update

Two important operators are used to modify structs. Remember that
values are immutable, these create new structs based on the originals.

- The `~` morph operator takes a struct and a shape and alters the
data in the struct to match the given shape. 
- The `..` update operator takes two structs and applies data in the
second struct the first.

```comp
loaded-data ~account-shape
{} ~shape-with-all-defaults

default-setting .. loaded-settings
server .. {port=8080 host="0.0.0.0"}
```

The [Struct](struct.md) documentation has details on defining shapes
and applying updates and morphs to them.

