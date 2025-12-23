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
- Long pipelines split with `|` starting a new line

This said; the language is flexible and allows for whatever format feels most
readable and editable for your current project.

```comp
tight=:("oneline")  -- No spacing
spacey       = :arg ~num  -- Wild spacing
     ( prose and docs___
            !let first =
    1 !let second =arg
)
```

## Tokens

Tokens are used for naming variables, functions, tags, and nearly everything in
the language. Tokens have the following rules:

- Use kebab-case with hyphens as word separators
- No leading digits (digits allowed after first character)
- Leading and trailing underscores are allowed
- No leading or trailing hyphens allowed
- Characters are case sensitive
- Allows UAX #31 specification for valid unicode tokens

This unicode UAX #31 is the same character set used by languages like Rust and
Python. These are combined with a set of preferred patterns:

- Prefer lowercase tokens
- Prefer boolean functions and fields with a trailing `?`

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
- `_parity_bit`
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
records.#0."Owners".'$owner-name'.active?
```

## Struct literals

Structs are usually created from code surrounded by parenthesis `()`. These can
contain any mix of positional fields and named fields, which are separated by
any whitespace. All values have a positional order, even the named fields.

Struct literals can provide a decorator which modifies how the literal is
interepreted to define a new literal. These must be pure methods that use a
special `~literal` argument.

```comp
(|val color="red" 5)  -- 5
(|flat (1 2 3) (4) (5 6)) -- (1 2 3 4 5 6)
```

These decorators can be used interchangeably in many parts of the language

- Struct literals
- Function call arguments
- Function body definition
- Block body definition

More details about how scopes and created and referenced is in the
[Struct](struct.md) documentation.

## Comments and Documentation

Comp uses `--` to define line comments that include everything to the end of the
line. Block comments are nested between triple dash `---` symbols.

These comments actually become floating documentation that is associated with
the code around them in different ways.

Multiline comments will be unindented to positionally match the indentation of
the opening `---` symbol.

The documentation is generally freely positioned through the code, and can be
represented as literal information for documentation generators.

- The opening comment for a file is considered documentation for the module
  itself.
- Comments mid stream become general section information and apply to all
  following code.
- Line comments that follow code are applied to all the preceding code on that
  line.

```comp
---
The save functions will error if the given resources are not found
or do not have proper permissions.

### Markdown

It's possible that block documentation will be interpreted as markdown
in many contexts. What does this mean? Only time can tell.
---

-- Process different types of data appropriately

save = :~nil ()
save = ~(data) (implementation())

color = (1 0 0) -- red
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

**Pipeline and flow control:**

- `|` - Pipeline function chaining
- `|?` - Pipeline fallback operator
- `?` - Provide fallback value

**Assignment operators:**

- `=` - Normal assignment
- `=*` - Strong assignment (resists overwriting)  
- `=?` - Weak assignment (only if undefined)

**Special operators:**

- `~` - Shape definition
- `:` - Block or function definition

Comp's use of kebab case conflicts with use of the mathematic subtraction
operator between two tokens. For these cases an alternative syntax must be
chosen.

- `a - b` use spaces around the operator
- `a+-b` an add of the mathematic is the same as subtraction
- `(a)-(b)` one or both tokens must be wrapped in parenthesis

## Scopes

The language uses many predefined scopes. Some can be read and others can be
written to in specific contexts of the language.

- `mod` these constant values can only be set at the top level of the module.
  They can only be set to simple expressions or literal values, like the default
  for shape fields. They can be read from anywhere within the same file, but are
  not visible to code outside the module.
- `my` a simple scope that module assignments can be made to that are private to
  the current module. Values written to this scope can be referenced normally
  within the same module.
- `pkg` like `mod` these can be assigned to at the module top level. These
  contain package metadata for the module. These are intended to be accessed and
  read externally. There is a defined set of expected and optional field names
  that packages can define, although anything can be set here.
- `import` module level code can assign simple structures that define an import
  specification. The handling of imports is managed by the language before the
  module evaluates any code.
- `startup` a module level context that named functions or struct literals are
  assigned into. These are discoverable by runtime tools. The fields these
  defines become values defined in the `ctx` scope.
- `ctx` are values defined by the startup functions. This special context can
  only be accessed inside evaluating functions. It's fields are not normally
  accessible, but instead get merged into the function's argument definitions.
  It is possible to assign or overwrite new fields into this context, which will
  then be adopted by all function calls made from the current function.
- `var` is an internal private namespace for local variables. These can be used
  in functions and blocks, and is also accessible from regular struct literals
  to reuse data. Blocks defined in a function share the same `var` scope as the
  function that defined them.
- `tag` modules define tag hiearchy in this declarative namespace. They
  then become part of the module namespace after being processed.
- `out` when a function is running this can refer to fields that have already
  been defined. Nothing can be written to this scope directly.
- `<in>` each function can define a shape used for its input and choose whatever
  name it wants to represent this input. When data is given to a function
  through pipeline input it is only loosely matched, and can contain additional
  fields not part of the input shape.
- `<arg>` each function can also defin a shape used to define its argument. It
  can name this scope whatever it wants in the function definition. Argument
  values are strictly matched to their scope. The arguments will not contain any
  fields that are not in the function definition. This argument scope will be
  populated by the `ctx` and `mod` scopes with any named fields that satisfy the
  shape requirements for those arguments.

As code is executed, a variety of scopes are available to the running code.
These are always referenced through their fully qualified name, like
`mod.version` or `arg.verbose`. In some contexts different scopes can be written
to, like `ctx.server.port = 8000`. Remember that assignment doesn't modify
existing structures since they are immutable. Instead they construct a new data
with overlayed edits (and as much shared data as possible).

Functions optionally receive separate scopes for provded arguments and for data
passed through the pipeline. The block definition can define what name these two
structs will be assigned inside the body.

The pipeline data will always match the defined shape. It may also contain extra
data and fields..

The arguments struct is stricter and only contains explicitly defined fields.
The arguments can be contributed to by other scopes like `ctx` or `mod` if they
contain data that matches the defined shapes.

The special `var` context is used for storing temporaries inside the scope. This
scope is shared with any blocks defined inside the same function.

```comp
process-request = :in~(request) arg~(timeout ~num) (
    !let start = time()  -- Function-local variable
    !let user = in.user  -- Another local variable
    (
        response = in |validate() |process()  -- Struct field
        duration = now() - start  -- Field computed from local
    )

    ctx.server.timeout = arg.timeout  -- Copy argument value to context scope
    !let config = mod.settings  -- Module-level constants
)
```
