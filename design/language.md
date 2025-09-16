# General Syntax

* Listing of general purpose features in the Comp syntax. *

## Overview

Comp has many general purpose features, aside from the major topics like
modules, functions, shapes, and tags. Many of those topics share common
functionality that is better described in this document.


## Privacy

Private and unexported data uses the `&` in different ways to prevent other
modules from accessing values and definitions. Remember this by tilting your
head and imagining the symbol represents a padlock.

Each module has a private namespace `!mod` that allows storing and updating data
that no code outside the current module can reference or modify.

### Private Definitions

Shape, function, and tag definitions that are internal for the module use only.
These definitions place an `&` ampersand as a suffix on the name. This also
applies to namespace aliases which are exported by default.

```comp
!func :secret_hash& ~str = {...}
!tag @attachment& = {precall postcall}
!shape bunker& = {width~num length~num depth~num}
```

The & suffix is not used when referencing private definitions. The privacy is an
access control mechanism, not part of the interface itself.

This also applies when using the `!alias` operator. Aliases default to being
exposed definitions for the module itself. Adding the `&` ampersand suffix
allows them to be used privately.

```comp
!alias :leftpad = :str/ljust    ; global definition
!alias #logsev& = #log#severity ; private definition
```

### Private Data Attachment

Each module can attach private data to any structure using `&` syntax. Other
modules cannot access private data attached by different modules:

This private data exists outside the value itself, which means the shape is not
modified by hidden or internal fields.

Referencing and assigning private data can be done either individual fields or
the entire private structure.

```comp
; Create structure with private data inline
$user = {login="pete" email="pete@example.com"}&{session="abc123" id=789}

; Access private data (only in same module)
$user.login          ; "pete" - public field
$user&.session       ; "abc123" - private field (same module only)
$user&.id           ; 789 - private field (same module only)

; Manual private data assignment
$user& = {session="abc123", internal_id=789}
```

This private data is natually transferred to every value passed through a
pipeline's chain of statement. This includes full spread operators.

```comp
$user& = {session="abc", token="xyz"}

; Automatic preservation in pipelines
$result = $user -> :transform -> :validate
; $result& = {session="abc", token="xyz"}

; Automatic preservation in full spread
$copy = {...$user extra="field"}
; $copy& = {session="abc", token="xyz"}

; Manual copying when needed
$selective = {name=$user.name}
$selective& = $user&  ; Manual private data transfer
```

When the result of a structure comes from the combination of mutliple existing
structure then the private data will be merged, using "first reference wins"
collision rules. There is no way to override this merging behavior using strong
or weak operations.

When strict handling of private data is needed through complex merging
operations, the private data can always be saved and modified from earlier steps
in the operation, then applied back to the resulting object directly.

```comp
$source1& = {token="abc", shared="first"}
$source2& = {cache="xyz", shared="second"}

$merged = {field1=$source1.name, field2=$source2.email}
; $merged& = {token="abc", shared="first", cache="xyz"}
; First reference wins: $source1& merged before $source2&
```


## Docstrings

The language supports docstrings which are extended user information attached to
any shape, function, tag, or field. These are more powerful than comments
because they are recognized by the language and can be accessed at runtime.

A docstring is a string literal that follow the `!doc` operator. These can use
single or triple string quotes for single and multiline use cases. There are two
forms of these documentation strings.
* **Inline** is the simplest, it uses `!doc "Information"` to immediately apply
the docstring to whatever function, shape, tag, or field definition follows.
* **Detached** adds a reference to the object being documented, like `!doc
#severity = "Logging level strengths."

Docstrings for the module must use the detached form of `!doc module "Top level
info."`.

Multiple docstrings attached to the same definition are appended together in
file order, with a blank line inserted between each docstring. Docstring tools
will expect docstrings to use Markdown formatting to style the information.

Use inline `!doc` for:
* *Brief single-line descriptions
* *Simple field documentation

Use detached `!doc target` for:
* *Extended multi-paragraph documentation  
* *Documentation in separate files
* *Avoiding clutter in complex definitions
* *Module-level documentation (required)

More documentation guidelines:
* Single line summaries whould be written like a sentence with capitalization
  and punctuation.
* Multiple definitions of detached documentation will be joined with an empty
  line.
* When a definition only has a multiline detached docstring it should still
  include a summary line that is separated by a single blank line from the
  remaining documentation.

```comp
!tag #status = {
    pending={review approved rejected}
    !doc "Actively being developed."
    active
    !doc "All work completed and ready to deliver."
    complete
}

!doc #status "Workflow status indicators."
!doc #status#pending "Awaiting decision."
!doc #status#pending#review "Under active review."
!doc #status#pending#approved "Approved but not yet active."
```

Documentation strings are regular string literals and can include formatting
instructions `${}`. Documentation strings expanded in a special context that has
access to
* `field` lookup fields in the static module namespace
* `doc.toc` table of contents for the active object (module, shape, or tag)
* `describe` structure created using the `!describe` operator for the attached
  object

Documentation tools should attempt to auto-recognize references to functions
shapes and tags and generate properly linked references where possible.

It should not be necessary to document information clearly defined in the
language, like field shapes or default values. Tools displaying documentation
should also consider grouping multiple implementations of a function with the
same name, when defined with different shape signatures.
