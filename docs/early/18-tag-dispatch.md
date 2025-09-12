## Dynamic Tag-Based Dispatch (Replacing `!super`)

The Comp language now uses field-based tag dispatch for polymorphic behavior across modules, replacing the earlier `!super` mechanism.

### Core Syntax

```comp
// Normal polymorphic dispatch - finds implementation based on tag's origin module
data -> :fieldname#:function

// Parent dispatch - explicitly calls parent tag's implementation  
data -> :fieldname#parent_tag:function
```

### How It Works

When a tag value is created (e.g., `#dog`), it carries metadata about which module defined it. The dispatch syntax uses this to find the correct implementation:

1. **`:fieldname#:function`** - Looks at the tag in `fieldname`, determines its origin module, then finds the most specific `:function` implementation for that shape
2. **`:fieldname#parent_tag:function`** - Temporarily masks the field's tag as `parent_tag` during shape matching, allowing explicit parent implementation calls

### Example

```comp
// base module
!tag #animal = {#mammal #reptile}
!tag #mammal = {#dog #cat}
!func :speak ~{#mammal ...} = "generic mammal sound"
!func :speak ~{#dog ...} = {
    $parent = .in -> :type#mammal:speak  // Explicit parent call
    "woof and ${parent}"
}

// extended module
!tag #mammal += {#wolf}
!func :speak ~{#wolf ...} = "howl"

// Usage - works across module boundaries
my_pet = {type#wolf name="Luna"}
my_pet -> :type#:speak         // "howl" - finds extended:speak
my_pet -> :type#mammal:speak   // "generic mammal sound" - forces parent
```

### Key Properties

- **Static module resolution** - The module is determined by the tag's origin, no dynamic searching
- **Dynamic shape matching** - Within the module, finds most specific implementation using the standard specificity tuple scoring
- **Parent-only constraint** - Can only dispatch through actual parents in the tag hierarchy (not siblings)
- **Consistent syntax** - Same mechanism works from inside implementations or external call sites

This replaces `!super` with a more general and composable mechanism that solves both inheritance and cross-module polymorphism.