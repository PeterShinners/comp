## Import System Design Summary

### Core Syntax
```comp
!import name = source "specifier"
```
- **source** is an unquoted token: `std`, `pkg`, `comp`, `git`, `python`, `openapi`, `main`
- **specifier** is always a quoted string allowing interpolation

### Key Innovation: Automatic Main Override
Libraries write simple imports that are automatically overridable:
```comp
// Library writes:
!import json = std "json"

// Automatically behaves as:
!import json = main "json" | std "json"  // Try main first, fallback to std
```

### Assignment Operators for Control
```comp
!import json = std "json"      // Normal: main can override
!import json *= std "json"     // Strong: always use this version
!import json ?= std "json"     // Weak: only if not already provided
!import json = main "json"     // Explicit: must be provided by main
```

### Fallback Syntax
```comp
!import json = main "json" | std "json" | file "./minimal-json"
```
Uses existing `|` operator - consistent with field fallback behavior

### Import Sources
- `std` - Standard library modules
- `pkg` - Package manager (exact versions: `pkg "json@2.5.1"`)
- `comp` - Comp modules from files/URLs
- `git` - Git repositories with tags/commits
- `python`/`openapi` - Foreign language/spec imports
- `main` - Inherit from main module's imports

### Design Principles

1. **Modules are namespaces, not values**
   - Can't assign module to variable
   - Used as `:json:stringify` not `json.stringify`

2. **Single source of truth**
   - Main module controls all dependency versions
   - No hidden middle-layer dependency sharing
   - Clear dependency tree visible to tooling

3. **Explicit versions**
   - No version ranges or fuzzy matching (for now)
   - No lock files needed
   - Tools can analyze and update versions in source

4. **Library simplicity**
   - Default behavior is the common case
   - Libraries work standalone with defaults
   - Applications override what they need

### What Changed from Earlier Designs

- **Removed**: `.app` namespace for shared dependencies
- **Removed**: Modules as assignable values  
- **Added**: `main` as import source for dependency injection
- **Added**: Automatic main-override behavior as default
- **Simplified**: No complex inheritance chains, everything goes through main

This design achieves the goal: libraries are both standalone AND composable, with minimal syntax burden.