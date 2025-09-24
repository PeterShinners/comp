# Trail System

*Structured navigation paths through Comp data and filesystems*

## Overview

Trails provide a way to represent navigation paths through hierarchical data as regular structures. The `/path/` syntax is syntactic sugar that creates structures representing navigation through various dimensional spaces. These paths can navigate filesystems, data structures, archives, and any hierarchical system through explicit axis-shift notation.

Trails are not special types in Comp - they're structures with conventional shapes that trail operations interpret. This design keeps the language core simple while enabling powerful navigation patterns through library functions. The axis-shift notation (using `:`) allows trails to explicitly mark transitions between different navigational contexts. For information about the underlying structure operations that trails build upon, see [Structures, Spreads, and Lazy Evaluation](structure.md).

The trail system embodies several key principles:

- **No special types**: Trails are just structures with conventional shapes
- **Syntactic convenience**: The `/path/` syntax generates these structures easily
- **Library interpretation**: Trail operations give meaning to trail structures  
- **Data as data**: Trails can be stored, passed, and manipulated like any value
- **Clear visual marker**: The `/` delimiters make navigation operations obvious
- **Explicit dimensional shifts**: The `:` operator marks transitions between contexts

This design maintains Comp's principle that everything is data while providing convenient syntax for navigation. The axis-shift capability makes trails universal for navigating any hierarchical system.

## Trail Fundamentals

A trail literal using `/path/` syntax creates a structure containing navigation segments. Each segment is either a field name, an expression in single quotes, or an axis-shift marker using `:`. This structure can be stored in variables, passed to functions, or manipulated like any other data.

```comp
; Simple trail literal
@path = /users/profile/theme/

; Trail with expression segments
@dynamic = /users/'user-id'/settings/

; Trail with axis shift
@archive = /backup.zip/zip:/data/config.json/

; Apply trails to navigate data
config |get /database/host/
data |set @path new-value
```

The trail syntax provides convenient shorthand for creating navigation structures. Trails are always relative to whatever object they're applied to - there's no concept of absolute trails.

## Axis-Shift Notation

The colon (`:`) operator marks dimensional transitions in trails, where the navigation context changes. This is essential for navigating through different types of hierarchical systems that require different interpretation rules.

```comp
; Filesystem to archive
/home/backup.tar/tar:/2024/data/

; Archive to nested archive  
/archives/data.zip/zip:/inner.tar/tar:/files/

; Future: filesystem to metadata
/var/log/system.log/stat:/mtime/

Common axis types for filesystem navigation (considered):
- `zip:` - Navigate into ZIP archive
- `tar:` - Navigate into TAR archive
- `gz:` - Decompress GZIP stream
- `stat:` - Access file metadata (future)

## Trail Syntax Elements

```comp
; Simple segments
/users/alice/profile/

; Expression segments (single quotes)
/users/'username'/profile/
/data/'key-name'/value/

; Axis shifts (colon notation)
/archive.zip/zip:/contents/
/data.tar.gz/gz:/tar:/files/

; Mixed syntax
/backups/'date'/tar:/users/'user-id'/

; Quoted segments for special characters
/documents/"law:"/record.pdf/
/folders/"my/folder"/file.txt/
```

## Trail Operations

Trail operations are functions that interpret trail structures and apply them to data. The primary operations for filesystem and data navigation:

```comp
; Basic trail operations
data |get /users/profile/
data |set /users/profile/ value
data |exists? /users/alice/

; Filesystem operations with trails
@dir |get /src/lib/utils/
@dir |set /config/settings.json/ content
@dir |exists? /build/output/

; Archive navigation
@archive = ("/data.zip" |open-as-filesystem)
@file = (@archive |get /documents/report.pdf/)
```

The standard library provides trail operations that interpret these structures. For information about the module system and standard library organization, see [Modules, Imports, and Namespaces](module.md).

```comp
!import /trail = std /core/trail/

; Trail manipulation functions
/users/profile/theme/ |segments/trail    ; [users profile theme]
/users/profile/ |parent/trail            ; /users/
{/base/ /extend/} |join/trail           ; Combine trails
```

## Trail Composition

Since trails are just structures, they compose using normal structure operations. Expression segments allow dynamic path construction:

```comp
; Dynamic segments with expressions
@user = "alice"
@data = data |get /users/'@user'/profile/

; Trail variables
@base = /api/v2/
@endpoint = /users/
@full = @base/'@endpoint'/    ; Expression joins paths

; Computed field names
@field = "email"
profile |get /user/'@field'/
```

## Filesystem Integration

Trails are the primary way to navigate filesystem hierarchies, with axis-shift notation for entering archives and other virtual filesystems:

```comp
; Directory operations with trails
@project = ("./myapp" |open-dir)
@config = (@project |get /config/settings.json/)
@source = (@project |list /src/*/)

; Archive navigation
/backups/2024.tar/tar:/january/data.json/
/downloads/package.zip/zip:/lib/core.comp/

; Windows drive letters work naturally
/C:/Windows/System32/
/D:/games/data.zip/zip:/assets/
```

## Import Statement Syntax

The import system uses trail notation for consistency with the rest of Comp's path-based operations:

```comp
; Standard library imports
!import /str = std /core/str/
!import /math = std /core/math/

; Git repository imports
!import /lib = comp /git@github.com:/user/repo.git/

; Local filesystem imports
!import /utils = comp /./lib/utils/

; Archive imports
!import /vendor = comp /vendor.tar/tar:/libs/

; URL-based imports
!import /remote = comp /https:/cdn.example.com/libs/v2/

; Fallback to string literals for complex cases
!import /special = custom "complex://provider?params=value"
```

## Navigation Patterns

Trail operations can include wildcards and recursive patterns:

```comp
; Wildcard selection
@dir |list /src/*/

; Recursive descent (with explicit axis)
/photos:dir/**.jpg/exif:/DateTaken/

; Pattern matching
@dir |match /tests/*_test.comp/

; Future: predicate filtering
/users:/array/[age > 18]/email/
```

## Store System Integration

The Store system uses trails for navigating mutable state:

```comp
; Store operations with trails
@store |get /users/alice/profile/
@store |set /cache/results/ data
@store |delete /temp/*/

; Axis shifts clarify navigation intent
@store |get /users:/key/alice/field:/email/
@store |set /cache:/ttl/3600/data:/results/ value
```

## Type Safety and Validation

While trails are runtime values (just structures), they can integrate with Comp's type system:

```comp
; Shape for trail structures (simplified)
!shape ~trail = {
    segments ~array
    axes ~array?
}

; Functions can require trail-shaped inputs
!func |navigate ^{data ~any path ~trail} = {
    ^data |apply/trail ^path
}

; Trail validation
!func |safe-navigate ~{data} ^{path} = {
    ^path |valid?/trail |if {
        data |get ^path
    } {
        {#invalid-trail.fail path=^path}
    }
}
```

## Performance Considerations

Trail operations can be optimized through caching and compilation:

- Parsed trail structures can be cached for repeated use
- Common navigation patterns can be compiled to efficient accessors
- Axis-shift handlers can be pre-resolved for known types

```comp
; First use parses and caches
@path = /users/profile/settings/
data |get @path     ; Cached trail structure reused

; Compiled accessors for hot paths
@hot-path = /api/v2/users/ |compile/trail
requests |map {$in |get @hot-path}
```