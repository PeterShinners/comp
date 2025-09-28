# Filesystem API Design

*Capability-based filesystem access for Comp*

## Design Principles

- **Capability-based security** - Directory handles are unforgeable tokens, not string paths
- **Relative operations** - All operations relative to directory handles, no ambient authority
- **Explicit boundaries** - Clear separation between filesystems via axis-shift notation
- **Platform abstraction** - Unified interface over OS-specific filesystem semantics
- **VFS-ready** - Archives, remote systems, and virtual filesystems use same interface

## Core Concepts

### Filesystem Objects
- `~filesystem` - Represents a filesystem mount (OS drive, archive, virtual)
- `~directory` - Handle to a directory within a filesystem
- No `~file` type - files are operations on directories

### Two-Tier Access
- **High-level** - `|fetch` for simple read operations from paths/URLs
- **Capability-based** - Directory handles for complex operations

## Basic Operations

```comp
; High-level fetch (90% use case)
content = ("/path/to/file" |fetch)
data = ("/archive.zip:zip/data.json/" |fetch)

; Directory-based operations (10% power use)
@dir = ("/home/user" |open-dir)
@entries = (@dir |list)
content = (@dir |read "file.txt")
@dir |write "output.txt" data
@subdir = (@dir |open-dir "subfolder")
```

## Trail Integration

Trails with axis-shift notation navigate filesystems and archives:
- `/path/to/dir/` - Regular filesystem navigation
- `/archive.zip:zip/contents/` - Enter archive filesystem
- `/data.tar:tar/2024/file/` - Navigate through tar archive

## Path Resolution

OS paths resolve to directory handles plus remaining segments:
```comp
@resolved = ("/home/user/new/file.txt" |resolve-path)
; Returns: {dir=<user-dir> trail=/home/user/ remaining=["new" "file.txt"]}
```

## Filesystem Types

Each filesystem type implements standard operations:
- Local filesystem (default)
- ZIP archives (`zip:`)
- TAR archives (`tar:`)
- Memory filesystem (testing)
- Future remote: (`ssh:`, `ftp:`), databases (`sqlite:`)

## Directory Entries

Directory listings return rich metadata without extra syscalls:
```comp
; Entry structure: {name type size modified permissions ...}
@entries = (@dir |list)
@files = (@entries |filter :{type == #file})
```

## Permission Model

Integrates with Comp's capability system:
- Directory handles require 'resource' permission to create
- Operations inherit handle's permissions
- No ambient filesystem access in pure functions

## Platform Differences

- **Linux/Unix** - Single root filesystem at `/`
- **Windows** - Multiple roots (`C:`, `D:`) as separate filesystems
- Platform-specific operations available through filesystem object

## Benefits Over Traditional APIs

- **No TOCTOU races** - Operations on handles, not paths
- **No path traversal attacks** - Can't escape directory scope
- **Natural sandboxing** - Only access through held capabilities
- **Efficient operations** - Cached handles, direntry-based listings
- **Uniform VFS** - Same interface for all filesystem types

## Future Considerations

- Recursive operations with trail patterns (`/**/*.txt`)
- File watching/monitoring through directory handles
- Transactional multi-operation support
- Extended attributes and platform-specific metadata