# Filesystem API Design

*Entry-based filesystem access for Comp*

## Design Principles

- **Entries, not paths** — The central object is a filesystem entry: a handle to a named location that may be a file, directory, link, or nothing yet. All operations go through entries.
- **Paths are URLs** — File paths are parsed like URLs (with implied `file:` scheme). This makes the path → entry bridge uniform and extends naturally to VFS schemes.
- **Roots are just entries** — A root is a regular directory entry that happens to be the top of its filesystem. It is not a special type. Every entry has a reference to its root. `|parent` on a root returns itself.
- **Roots never overlap** — Two roots cannot cover the same filesystem territory. Entries from different roots are different entities, even if they happen to correspond to the same absolute disk path. This is a hard rule.
- **Missing is a kind** — An entry for a name that doesn't exist yet is still an entry. You can write to it, mkdir it, query it. This eliminates the gap between "I have a path" and "I have a handle."
- **Pure roots exist** — Path manipulation, remapping, and testing don't require syscalls. Pure roots and memory roots provide the full entry interface without touching disk.
- **Platform encapsulation** — Native APIs underneath (Win32, Linux syscalls), never libc. The Comp surface is identical everywhere.

## Overview

The filesystem API has two layers:

1. **Paths** — Strings parsed like URLs. They are data. They can be relative or absolute. They name a location but don't hold a reference to anything.
2. **Entries** — Handles obtained by resolving a path against a root (or another entry). An entry is a snapshot of a location in a filesystem at lookup time. It knows its name, its kind, its parent, and its root.

The API is: **parse path → resolve against root/entry → get entry → operate on entry.**

There is no separate "high-level" or "convenience" API. The entry system *is* the API, and it is designed to be convenient. Getting an entry from a path is one call. Reading an entry is one call. The two together are two calls. That's the right amount.

```comp
; The whole flow: path → entry → contents
$var.cwd = [|cwd-entry]
$var.config = [$var.cwd |resolve "./config.json" |read]

; Or from an absolute path
$var.entry = ["/etc/hosts" |resolve-path]
$var.content = [$var.entry |read]
```

## Paths

File paths in Comp are treated as URL-like structured strings. An absolute path has an implied `file:` scheme. This isn't a gimmick — it's the natural way to unify local paths, archive paths, and future remote paths under one parsing model.

```comp
; Absolute paths (implied file: scheme)
"/home/user/config.json"        ; Linux absolute
"C:/Users/pete/code"            ; Windows absolute

; Relative paths (no scheme, no root)
"./src/lib"                     ; Relative to context
"../data/input.csv"             ; Relative with parent traversal

; Future: explicit schemes for VFS
"zip:///path/to/archive.zip"    ; ZIP filesystem
"memory://test-fixtures"        ; In-memory filesystem
```

Path parsing extracts structured data — scheme, root, segments — without touching the filesystem. This is pure data manipulation. You can parse, decompose, join, and remap paths without any syscalls.

```comp
; Parse a path into its components (pure operation, no syscalls)
$var.p = ["/home/user/docs/file.txt" |parse-path]
; => {scheme=#file root="/" segments=["home" "user" "docs" "file.txt"]}

; Manipulate path data
$var.p2 = [$var.p |with-name "other.txt"]
; => {scheme=#file root="/" segments=["home" "user" "docs" "other.txt"]}

$var.p3 = [$var.p |with-ext ".md"]
; => segments=["home" "user" "docs" "file.md"]

; Relative path between two parsed paths (pure)
$var.rel = [$var.base-path |relative-to $var.target-path]
```

## Roots

A root is just a regular directory entry that sits at the top of its filesystem. There is no special `~fs-root` type — a root is a `~entry` with `kind=#dir` that happens to be its own root. `|parent` on a root returns itself. `|root?` returns `#true`.

A program starts with a set of roots. On Windows, the defaults are the mounted drive letters. On Linux, it's `/`. Each root carries a permission level (`#read` or `#read-write`). But these are entry properties, not special root properties.

```comp
; Get the platform's default roots
$var.roots = [|fs-roots]
; Linux:   [~entry for "/"]
; Windows: [~entry for "C:", ~entry for "D:", ...]

; Get the working directory as an entry
$var.cwd = [|cwd-entry]
; => ~entry {kind=#dir name="comp" ...}

; Look up a root by name
$var.c = [|fs-root "C:"]
; => ~entry (a regular directory entry that is its own root)
```

### The no-overlap rule

Two roots cannot cover the same filesystem territory. Entries from different roots are always different entities, even if they correspond to the same location on disk.

Consider: you have the `C:` root and you promote `C:/Users/pete/code` into its own root. These are now two separate filesystem namespaces. `C:/Users/pete/code/foo.txt` resolved through the `C:` root and `foo.txt` resolved through the `code` root are **different entries**. They may point at the same bytes on disk, but they belong to different root scopes and cannot be compared with `|same?`.

This is intentional. Overlapping roots would make entry identity ambiguous, break `|parent` traversal guarantees, and create aliasing problems. The rule is simple: roots partition the filesystem space. If you want a narrower scope, promote a subdirectory to its own root — don't access it through two roots.

### Mounting and promoting

Roots come from **mount** operations. Each backend type has its own mount call that accepts whatever arguments that backend needs.

```comp
; Platform filesystem mounts (provided at startup)
; These are the default roots — mounted by the runtime

; Mount a zip file as a new root
$var.zip = [$var.archive-entry |mount #zip]
; => a new root entry whose children are the zip's contents

; Mount a tar
$var.tar = [$var.backup-entry |mount #tar]

; Create a memory root (a writable in-memory filesystem)
$var.mem = [|mount #memory]

; Create a pure root (path manipulation only, no I/O)
$var.pure = [|mount #pure "virtual"]
```

**Promoting** an existing directory entry into its own root:

```comp
; Take a directory entry and make it a root
$var.code-dir = [$var.cwd |resolve "src/comp"]
$var.code-root = [$var.code-dir |promote-root]
; => a new root entry for the same directory
;
; The new root gets an entry:// URI with a short unique identifier:
;   original entry: file:///home/user/projects/comp/src/comp
;   promoted root:  entry://comp-a3cc/
;
; The identifier is the cleaned base name + a short unique suffix,
; similar to how module tokens work. It's only valid in-process.
;
; Children get URIs under this root:
;   entry://comp-a3cc/runtime/func.py
;
; Children of $var.code-root have $var.code-root as their root.
; They cannot |parent above it. They are in a different root scope
; from entries obtained through the original file:// root.

; Get the backing filesystem path (for interop with external tools)
[$var.code-root |backing-path]
; => "file:///home/user/projects/comp/src/comp"
; This is the only way to get back to the underlying location.
```

The `entry://` scheme is important: it cannot be confused with a `file://` path, even though it maps to the same disk location. The short identifier keeps URIs readable without embedding the potentially deep, multiply-nested backing path. The full backing path is available via `|backing-path` for interop.

For serialization/recreation, promoted roots also have a **descriptor** — the full resolved URI stack showing how the mount was created. This can be used to recreate the root in a compatible environment:

```comp
[$var.code-root |mount-descriptor]
; => {scheme=#local backing="file:///home/user/projects/comp/src/comp"}

; Nested mounts get a chain:
[$var.zip-inside-promoted |mount-descriptor]
; => {scheme=#zip
;     backing="entry://comp-a3cc/data/archive.zip"
;     parent={scheme=#local backing="file:///home/user/projects/comp/src/comp"}}
```

VFS boundaries are always explicit. You never silently traverse into an archive or a promoted directory — you mount/promote it, getting a new root, and navigate within that root.

### Overlay roots

A root can also be a stack of other entries — an overlay. This is similar to overlayfs on Linux: reads search the stack top-down, writes go to the top layer.

```comp
; Stack a writable memory layer on top of a read-only disk layer
$var.base = [|cwd-entry |resolve "templates" |promote-root |restrict #read]
$var.overlay = [|mount #memory]
$var.combined = [|mount #overlay [$var.overlay $var.base]]

; Reading: checks overlay first, falls through to base
$var.content = [$var.combined |entry "page.html" |read]

; Writing: always goes to the top (overlay) layer
[$var.combined |entry "page.html" |write modified-content]
; The base layer template is untouched
```

Overlay roots enable powerful patterns:
- **Copy-on-write sandboxes** — writable overlay on read-only base
- **Configuration layering** — defaults → system → user → local
- **Build systems** — source tree + generated files as unified view
- **Testing** — memory overlay on real files, discarded after test

This is a future feature but the entry model supports it naturally because entries are snapshots with backend-agnostic operations.

### HTTP as a backend

An HTTP endpoint can be mounted as a read (or read-write) root. The entry operations map naturally to HTTP methods:

```comp
; Mount an API endpoint
$var.api = [|mount #http {url="https://api.example.com/v1" auth=bearer-token}]

; GET — reading entries
$var.spec = [$var.api |entry "openapi.json" |read]
$var.users = [$var.api |entry "users" |list]  ; GET + parse directory-like listing

; PUT — writing entries
[$var.api |entry "config/settings.json" |write new-config]
```

Not everything maps to filesystem concepts — POST requests, custom headers, multipart uploads, WebSocket upgrades — and the entry API doesn't try to absorb all of HTTP. Instead, HTTP-specific operations are extended calls in an HTTP module that build on top of the same entry:

```comp
!import http

; POST, form data, custom headers — these aren't filesystem operations
$var.response = [$var.api |entry "users" |http.post {name="alice" role="admin"}]
$var.response = [$var.api |entry "upload" |http.post-multipart file-data]

; HTTP-specific metadata
$var.headers = [$var.api |entry "users/123" |http.headers]
$var.etag = [$var.api |entry "users/123" |http.etag]
```

The principle: the entry system provides the **navigation and basic I/O** (read, write, list, stat). Protocol-specific operations are extensions in their own modules that accept entries and add specialized behavior. The entry is the common substrate; the protocol module adds the verbs that are unique to that protocol.

This means you don't need a separate `requests`-style library for the common case of "read a JSON endpoint." You mount it, navigate it, read from it. When you need POST, streaming, or protocol-specific features, you import the HTTP module and use its extended operations on the same entries.

### The entry as I/O foundation

This pattern extends beyond HTTP. The entry system is not trying to be a universal API for everything — but it provides a **universal starting point** for I/O. Every I/O operation starts with "where" (an entry) and the basic operations (read, write, list, stat) cover a surprisingly large surface. Domain-specific operations extend from there:

```comp
; Database — mount, navigate tables as directories, read rows
$var.db = [$var.db-file |mount #sqlite]
$var.users = [$var.db |entry "users" |list]     ; SELECT *
$var.user = [$var.db |entry "users/123" |read]   ; SELECT ... WHERE id=123
[$var.db |entry "users" |sqlite.query "SELECT * WHERE role='admin'"]

; SSH — mount remote, navigate like local
$var.remote = [|mount #ssh {host="server.com" key=ssh-key}]
[copy-tree ($var.remote |entry "backups/latest") $var.local-dir]
```

The door stays open for anything. But the filesystem entry concept is the common handle that all I/O hands you first, and specialized modules build on top of it without replacing it.

### Backend types

| Type | Tag | Writable | Backed by | Mount via |
|------|-----|----------|-----------|----------|
| Local OS | `#local` | yes | Platform filesystem | Runtime default |
| ZIP | `#zip` | read-only (initially) | A file entry | `entry \|mount #zip` |
| TAR | `#tar` | read-only | A file entry | `entry \|mount #tar` |
| Memory | `#memory` | yes | RAM (mutable store) | `\|mount #memory` |
| Pure | `#pure` | structural only | Nothing (path math) | `\|mount #pure name` |
| Overlay | `#overlay` | top layer | Stack of roots | `\|mount #overlay [layers]` |
| HTTP | `#http` | read (GET), write (PUT) | Remote server | `\|mount #http {url=... auth=...}` |
| (Future) SSH | `#ssh` | yes | Remote connection | backend-specific |
| (Future) SQLite | `#sqlite` | yes | Database file | backend-specific |

## Entries

An entry (`~entry`) is a handle to a named location in a filesystem. It is the one type you work with for all filesystem operations.

Every entry knows:
- Its **name** — the leaf name in its parent
- Its **kind** — `#dir`, `#file`, `#link`, or `#missing`
- Its **parent** — the directory entry it lives in (at the root, parent is self)
- Its **root** — the root entry of its filesystem (which is itself just an entry)
- Its **permissions** — inherited from the root (or narrowed)
- Its **uri** — a URL-like identifier unique to its root scope

The root reference is what makes entry identity unambiguous. Two entries with the same name and path segments but different roots are different entries. The root is the namespace.

### Entry kinds

```comp
$var.e = [$var.dir |entry "config.json"]
[$var.e |kind]  ; => #file, #dir, #link, or #missing
```

**`#dir`** — A directory. Can be listed, can have children, can be navigated into.

**`#file`** — A file. Can be read, written, appended to. Has size, modification time, etc.

**`#link`** — A symbolic link. It is its own thing — not silently dereferenced. You can read where it points (`|link-target` returns the raw path string), or explicitly follow it to get the target entry. Symlink resolution is scoped to the root:
- The link's target path is resolved relative to the link's parent directory
- If the resolved path escapes the root boundary → the link is `#unresolved`
- An outer root that covers more filesystem territory may be able to resolve what an inner root cannot
- This is intentional: a promoted/mounted root is a sandbox, and links cannot tunnel out of it

A good library of relative-path remapping between entries makes it possible for code with the right root entries to untangle cross-root links when needed.

**`#missing`** — The name doesn't exist in the filesystem (yet). This is the key concept: a missing entry is still a fully functional entry handle. You can:
- `|write` to it (creates a file)
- `|mkdir` it (creates a directory)
- `|kind` it (returns `#missing`)
- hold onto it and check later (it might appear)

A missing entry does **not** mean the entry is invalid. It means "this is a real location in a real filesystem that happens to be empty right now." This is exactly Comp's general posture toward resource handles — they refer to locations that may change at any time.

### Getting entries

```comp
; From a directory entry, get a child entry
$var.child = [$var.dir |entry "README.md"]
; => ~entry — might be #file, #dir, #link, or #missing

; From any entry, get its parent
$var.parent = [$var.entry |parent]
; At the root, |parent returns the root itself (no escape)

; Detect hitting the root
[$var.entry |root?]  ; => #true if this entry IS the root

; Resolve a multi-segment relative path (handles . and ..)
$var.deep = [$var.dir |resolve "./src/../lib/utils.comp"]
; => ~entry for utils.comp (might be #file or #missing)
; Parent traversal (..) is clamped at the root
```

### Resolving absolute paths

Absolute path strings resolve against the available roots:

```comp
; Resolve an absolute path to an entry
$var.entry = ["/home/user/projects/comp" |resolve-path]
; Finds the "/" root, walks down, returns entry
; Final entry might be #dir, #file, #link, or #missing

; On Windows
$var.entry = ["C:/Users/pete/code" |resolve-path]
; Finds the "C:" root, walks segments

; Relative paths need an anchor
$var.entry = [$var.cwd |resolve "../sibling/file.txt"]
```

`|resolve-path` takes a search path of roots (defaulting to the platform roots). `|resolve` on an entry takes a relative path anchored to that entry.

### Entry operations

Operations on entries depend on kind. Calling `|read` on a `#dir` or `|list` on a `#file` is an error. Calling `|read` on a `#missing` entry is an error. Calling `|write` on a `#missing` entry creates the file.

```comp
; --- Reading ---
$var.text = [$var.entry |read]              ; text by default
$var.bytes = [$var.entry |read #bytes]      ; raw bytes

; --- Writing ---
[$var.entry |write "hello world"]           ; write text (create or overwrite)
[$var.entry |write data #bytes]             ; write bytes
[$var.entry |append "new line\n"]           ; append to file

; --- Directories ---
$var.children = [$var.entry |list]          ; list child entries
; => [~entry ~entry ~entry ...]
; Each child is a full entry with kind, name, metadata

$var.child = [$var.entry |entry "sub"]      ; get a specific child

; --- Creating ---
$var.new-dir = [$var.entry |mkdir]          ; create directory (entry was #missing)
$var.new-dir = [$var.parent |mkdir "name"]  ; shorthand: create named child dir

; --- Removing ---
[$var.entry |remove]                        ; remove file or empty dir
[$var.entry |remove-tree]                   ; remove directory tree

; --- Renaming ---
[$var.entry |rename "new-name"]             ; rename within same parent
[$var.entry |move $var.other-dir]           ; move to another directory
[$var.entry |move $var.other-dir "new-name"] ; move and rename

; --- Metadata ---
$var.info = [$var.entry |stat]
; => {kind=#file size=1234 modified=... created=... permissions=... atomicity=...}
; |stat on a #missing entry returns {kind=#missing}
; atomicity: #none, #rename, or #full — describes the entry's atomic write support

; --- Refresh ---
$var.fresh = [$var.entry |refresh]          ; new entry, same URI, fresh metadata
[$var.entry == $var.fresh]                  ; #false if anything changed on disk

; --- Streaming ---
$var.stream = [$var.entry |open #read]      ; open for streaming read
$var.stream = [$var.entry |open #write]     ; open for streaming write
$var.stream = [$var.entry |open #read-write] ; open for both
; Stream operations: |stream-read, |stream-write, |seek, |tell, |close
; Streams DO hold an open OS handle — they must be closed

; --- Identity ---
[$var.a |same? $var.b]                      ; same filesystem location?

; --- Permissions ---
$var.ro = [$var.entry |restrict #read]      ; narrow to read-only

; --- Atomic writes ---
[$var.entry |write-atomic data]             ; best-effort atomic overwrite
; Uses the best available mechanism for the backend:
;   #full     — true atomic write (platform primitive)
;   #rename   — write to temp + atomic rename
;   #none     — falls back to regular |write (e.g. some VFS backends)
; Check what's available: ($var.entry |stat).atomicity
```

### Entry handles and OS resources

Directory entries hold an open OS handle. This is a key design choice that makes relative operations fast and correct.

**On Linux**, a directory entry holds an `fd` opened with `O_RDONLY | O_DIRECTORY`. This fd:
- Does **not** lock anything — other processes freely create, delete, rename files inside
- Enables all `*at` operations: `openat`, `fstatat`, `mkdirat`, `renameat`, `unlinkat`
- Prevents the directory inode from being freed (same as any open fd), but the directory can be renamed or unlinked from its parent
- Is cheap to hold indefinitely

**On Windows**, a directory entry holds a `HANDLE` opened with `CreateFileW`:
```
CreateFileW(path,
    FILE_LIST_DIRECTORY,                                    // minimal access
    FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, // full sharing
    NULL, OPEN_EXISTING,
    FILE_FLAG_BACKUP_SEMANTICS,                             // required for directories
    NULL)
```

With full sharing flags, this handle does **not** cause locking problems:
- Other processes can freely read, write, create, delete files inside the directory
- The only restriction: the directory itself can't be fully deleted until the last handle closes (delete is deferred). This matches Linux behavior.
- Windows 10+ `FILE_DISPOSITION_POSIX_SEMANTICS` makes even this behave like Unix

For `openat`-style relative operations on Windows, the NT native API (`NtCreateFile`) supports a `RootDirectory` parameter — which is literally `openat`. For listing by handle, `NtQueryDirectoryFile` operates on the directory handle directly (not `FindFirstFile`/`FindNextFile`, which are enumeration cursors meant to be short-lived).

Note: `FindFirstFile`/`FindNextFile` are **not** used for directory handles. Those are search-state cursors that DO cause locking. The right primitive is `CreateFileW` on the directory with full sharing, which is a lightweight non-locking reference.

**File, link, and missing entries** do not hold their own OS handle. They hold a reference to their parent directory entry (which has the handle) plus their leaf name. Operations on these entries use the parent's handle:
- `|read` on a file entry → `openat(parent.fd, name, O_RDONLY)` on Linux, `NtCreateFile` with parent's `RootDirectory` on Windows → reads → closes
- `|write` on a missing entry → `openat(parent.fd, name, O_WRONLY|O_CREAT)` → writes → closes
- `|stat` on any entry → `fstatat(parent.fd, name)` / `GetFileInformationByHandleEx`

This means:
- Directory entries are slightly heavier (they hold a handle) but enable fast relative operations for their children
- File/link/missing entries are lightweight — just a parent reference + name
- No entry ever locks a file or prevents other programs from working
- The handle tree mirrors the directory tree: root holds a handle, child dirs hold handles, leaves reference their parent

### Entry metadata is a snapshot

Although directory entries hold a live handle, the **metadata** on any entry (kind, size, mtime, etc.) is a snapshot captured at lookup time. The handle is live; the metadata is frozen.

```comp
$var.e = [$var.dir |entry "output.txt"]
; Snapshot at lookup: kind=#missing, parent=$var.dir (which has live handle)

$var.e = [$var.e |write "hello"]
; |write uses parent's handle to create the file
; Returns a fresh entry with kind=#file

; Old snapshot vs fresh:
$var.old = [$var.dir |entry "output.txt"]  ; snapshot
; ... time passes, file changes externally ...
$var.fresh = [$var.old |refresh]
[$var.old == $var.fresh]  ; #false if anything changed
```

`|refresh` returns a new entry with the same path and parent handle, but re-statted metadata. `==` compares snapshot metadata for change detection.

Entries returned from mutating operations (`|write`, `|mkdir`, etc.) are already fresh. Entries from `|list` are fresh at list time. Explicit `|refresh` is for the case where you're holding an entry and want to check if the world changed.

Importantly, `|list` on a directory entry uses the directory's live handle to enumerate children, returning child entries that reference that handle. This is one `getdents`/`NtQueryDirectoryFile` call — no path resolution overhead.

## Pure Roots and Memory Roots

This is where things get interesting.

### Pure roots (`#pure`)

A pure root provides the full entry structure — names, parents, children, paths — but with no backing filesystem. No syscalls. No I/O. Entries in a pure root have kind `#missing` for everything (there's nothing on disk), but you can still navigate, resolve paths, compute relative paths, change extensions, etc.

Pure roots are for **path manipulation**. They let you work with filesystem-shaped namespaces without touching the real filesystem. Pure functions *can* use pure roots because there are no side effects.

```comp
; Create a pure root
$var.vfs = [|mount #pure "site"]

; Build a path structure
$var.page = [$var.vfs |resolve "blog/2024/post.html"]
; => ~entry in the pure root (kind=#missing, but structurally valid)

; Path manipulation
[$var.page |name]           ; => "post.html"
[$var.page |parent |name]   ; => "2024"
[$var.page |with-ext ".md"] ; => entry for "post.md" in same parent
[$var.page |with-name "index.html"] ; => entry for "index.html" in same parent

; Compute relative path between entries
$var.rel = [$var.page |relative-to $var.vfs]
; => "blog/2024/post.html"
```

### Memory roots (`#memory`)

A memory root is a writable in-memory filesystem. It has the full entry interface — read, write, list, mkdir — backed by RAM instead of disk. Entries in a memory root have real kinds (#file, #dir, #missing) that change as you operate on them.

This is essentially the **mutable store** concept from other design docs, wearing a filesystem interface. The two ideas converge: a store is a memory root, a memory root is a store.

```comp
; Create a memory root
$var.mem = [|mount #memory]

; Use it exactly like a real filesystem
[$var.mem |mkdir "config"]
$var.cfg = [$var.mem |entry "config"]
[$var.cfg |entry "app.json" |write "{\"port\": 8080}"]

; Read it back
$var.data = [$var.cfg |entry "app.json" |read |parse-json]

; List it
[$var.mem |list]
; => [~entry{name="config" kind=#dir}]
```

Memory roots are perfect for:
- **Testing** — pass a memory root to code that expects a filesystem, verify what it wrote
- **Staging** — build up a directory structure in memory, then copy to disk
- **Templates** — populate a memory root from a template, customize, write out

## Usage Sketches

### Read a JSON config file

```comp
$var.cwd = [|cwd-entry]
$var.config-entry = [$var.cwd |entry "config.json"]

!on [$var.config-entry |kind]
~file [$var.config-entry |read |parse-json]
~missing !error "config.json not found"

; Or with a fallback chain — |entry always succeeds (might be #missing)
$var.home = [|home-entry]

$var.config-entry = [$var.cwd |entry "config.json"]
$var.config = !on [$var.config-entry |kind]
    ~file [$var.config-entry |read |parse-json]
    ~missing (
        $var.fallback = [$var.home |resolve ".myapp/config.json"]
        !on [$var.fallback |kind]
        ~file [$var.fallback |read |parse-json]
        ~missing default-config
    )
```

No special "try-read," no exceptions for missing files. The entry exists, you check its kind, you branch. The missing entry *is* the "file not found" signal.

### Walk up looking for a .git directory

```comp
!define find-project-root (
    :param dir ~entry

    $var.git = [$dir |entry ".git"]
    !on [$var.git |kind]
    ~dir $dir
    ~else (
        !on [$dir |root?]
        ~true !error "not in a git repository"
        ~false [find-project-root ($dir |parent)]
    )
)

$var.project = [find-project-root (|cwd-entry)]
$var.git-config = [$var.project |entry ".git" |entry "config" |read]
```

`|entry` then `|kind` replaces `|dir?` with something more general. `|root?` replaces the `|same?` dance — it directly answers "am I at the ceiling?" And chaining `|entry` reads naturally: "in the project, in .git, the file called config."

### Static file server: map a URI to a file

This is the sketch that benefits most from pure roots. The idea: compute the path mapping in pure-entry space, then apply it to the real filesystem.

```comp
; The real static files on disk
$var.static-dir = [|cwd-entry |resolve "public" |restrict #read]

; Handle a request
!define serve-static (
    :param root ~entry
    :param uri-path ~text

    ; Resolve the URI path against the root entry
    ; |resolve handles ".." but clamps at root — path traversal is contained
    $var.target = [$root |resolve uri-path]

    !on [$var.target |kind]
    ~file [$var.target |read #bytes]
    ~dir (
        ; Try index.html
        $var.index = [$var.target |entry "index.html"]
        !on [$var.index |kind]
        ~file [$var.index |read #bytes]
        ~else !error #not-found
    )
    ~missing !error #not-found
    ~link !error #not-found  ; don't follow symlinks in web roots
)

[serve-static $var.static-dir request.path]
```

The security story: `$var.static-dir` is restricted to `#read` and `|resolve` can't escape the root. Even if `uri-path` is `"../../../../etc/passwd"`, the `..` traversal stops at the root entry. The directory entry *is* the sandbox — no path validation needed beyond what the entry system provides.

The more ambitious version with pure roots for URL remapping:

```comp
; Map between two namespaces without touching disk
$var.url-space = [|mount #pure "site"]
$var.url-entry = [$var.url-space |resolve uri-path]

; Compute relative path in URL space
$var.rel = [$var.url-entry |relative-to $var.url-space]

; Apply that same relative path to the real static directory
$var.real-entry = [$var.static-dir |resolve $var.rel]

!on [$var.real-entry |kind]
~file [$var.real-entry |read #bytes]
~else !error #not-found
```

This is the pattern: compute a path relationship in one namespace (pure, fast, no I/O), then project it onto another namespace (real, backed by disk). The pure root makes the "URL path" into a first-class navigable structure instead of just a string you're splitting on slashes.

### Rotating log handler

```comp
$var.log-dir = [$var.app-dir |entry "logs"]
!on [$var.log-dir |kind]
~missing [$var.log-dir |mkdir]

!define rotate-if-needed (
    :param log-entry ~entry

    !on [$log-entry |kind]
    ~file (
        !on [($log-entry |stat).size > 10_000_000]
        ~true (
            $var.ts = [|now |format "YYYYMMDD-HHmmss"]
            $var.backup-name = [$log-entry |name |replace ".log" ("-" + $var.ts + ".log")]
            [$log-entry |rename $var.backup-name]
        )
    )
)

!define write-log (
    :param dir ~entry
    :param message ~text

    $var.log = [$dir |entry "app.log"]
    [rotate-if-needed $var.log]

    ; |append on a #missing entry creates the file
    [$var.log |append (message + "\n")]
)

[write-log $var.log-dir "server started"]
```

Notice: `$var.log` is fetched as an entry snapshot. After `|rename`, we get `$var.log` fresh again via `|entry` — the new snapshot reflects the rename (the old name is now `#missing`). `|append` on a `#missing` entry creates the file — this is the missing-entry concept earning its keep. No "create-if-not-exists" flag needed.

The log handler receives an entry (which happens to be a directory). It could be a memory root in tests. Same code either way.

### Copy a directory tree between filesystem types

```comp
!define copy-tree (
    :param src ~entry
    :param dest ~entry

    [$src |list |each :(
        !on [$item |kind]
        ~file [$dest |entry ($item |name) |write ($item |read #bytes) #bytes]
        ~dir (
            $var.sub = [$dest |entry ($item |name) |mkdir]
            [copy-tree $item $var.sub]
        )
        ~link #skip  ; TODO: decide on link copying
    )]
)

; Local to local
[copy-tree (|cwd-entry |entry "project") (|cwd-entry |entry "backup" |mkdir)]

; Zip contents to disk
$var.zip = [|cwd-entry |entry "archive.zip" |mount #zip]
[copy-tree $var.zip (|cwd-entry |entry "extracted" |mkdir)]

; Disk to memory (for testing)
$var.mem = [|mount #memory]
[copy-tree (|cwd-entry |entry "fixtures") $var.mem]
```

The `|list` on a directory entry returns child entries (not metadata structs). These child entries have kinds, names, and can be operated on directly. This is cleaner than the old `{name kind}` struct approach — entries all the way down.

### Process a user-provided path argument

```comp
$var.cwd = [|cwd-entry]
$var.input-path = args.1  ; "../data/input.csv"

; Resolve relative path to an entry (handles .., clamps at root)
$var.entry = [$var.cwd |resolve input-path]

!on [$var.entry |kind]
~file [process-csv ($var.entry |read)]
~missing !error ("file not found: " + input-path)
~dir !error ("expected a file, got a directory: " + input-path)
```

`|resolve` is the bridge from user-string to entry. One call. Then you're in entry-world and can branch on kind.

## Platform Backend

The filesystem runtime uses native platform APIs, not libc:

- **Linux** — `open(O_DIRECTORY)` for directory handles, `openat`/`fstatat`/`mkdirat`/`renameat`/`unlinkat` for relative operations, `getdents64` for listing. Optional libuv for async.
- **Windows** — `CreateFileW` with `FILE_FLAG_BACKUP_SEMANTICS` + full sharing for directory handles. `NtCreateFile` with `RootDirectory` for `openat`-style relative operations. `NtQueryDirectoryFile` for listing by handle. No `FindFirstFile`/`FindNextFile` for entry handles (those are enumeration cursors). No POSIX emulation.
- **macOS** — Same fd-based approach as Linux, plus native APIs where advantageous (`getattrlistbulk` for fast directory listing with metadata).

This is fully encapsulated behind the entry interface.

### Why not libc

- Hides platform capabilities behind a lowest-common-denominator interface
- No `openat`-style relative operations in portable C
- No useful directory entry metadata without extra `stat` calls
- Global error state (`errno`), no async, wrong string encoding assumptions (Windows is UTF-16)

## Pure Integration

Real filesystem roots (local, zip, tar) are resources. Pure functions cannot hold them.

- `!pure` functions cannot operate on live filesystem entries
- `!pure` functions *can* use pure roots (no I/O, no side effects)
- `!pure` functions can work with parsed path data (it's just structures)
- Impure code resolves paths and reads files, then passes data to pure functions

## Security Properties

- **Bounded traversal** — `|parent` and `|resolve ".."` stop at the filesystem root. You cannot escape the root you entered through.
- **No ambient access** — No operation implicitly uses a "current directory." `|cwd-entry` must be called explicitly.
- **Permission narrowing** — `|restrict` can narrow but never widen. A read-only entry cannot produce a writable child.
- **Unforgeable entries** — Entries cannot be constructed from strings. Only obtained from roots or parent entries.
- **Missing ≠ accessible** — A `#missing` entry lets you check and create, but read operations still fail. The handle doesn't grant access to content that doesn't exist.

## Resolved Design Decisions

- **Directory entries hold OS handles (best-effort)** — On Linux, an `fd` opened with `O_DIRECTORY`. On Windows, a `HANDLE` from `CreateFileW` with full sharing flags. These are non-locking and enable `openat`-style relative operations. File/link/missing entries reference their parent's handle + leaf name. Handle preservation is a **backend capability, not a guarantee**. Local filesystem backends on Linux and Windows support it. An HTTP backend won't. A ZIP backend might hold a file handle but not per-directory handles. The API works identically either way — backends that can't hold handles re-resolve paths internally. Anything on the filesystem can change at any time regardless; the handle just makes operations faster and more correct when available.
- **Metadata is snapshot, handle is live** — Entry metadata (kind, size, mtime) is frozen at lookup time. `|refresh` returns a new entry with fresh metadata. `==` compares snapshots. But the underlying OS handle on directory entries is live and used for operations.
- **Symlinks scope to root** — Link resolution cannot escape the root boundary. Cross-root links are `#unresolved`. Outer roots can resolve what inner roots cannot.
- **Mounted root URIs** — `entry://name-suffix/path` scheme. Short unique in-process identifier (cleaned base name + random suffix). Full backing URI available via `|backing-path`. Serializable descriptor via `|mount-descriptor` for recreation.
- **Atomic writes are best-effort** — `|write-atomic` uses the best mechanism available. Entry metadata reports atomicity level (`#none`, `#rename`, `#full`).
- **Streaming via `|open`** — Returns a `~stream` with read/write/seek/tell/close. Streams hold an additional open OS handle for the file itself and must be closed.

## Open Questions

- **Handle lifecycle** — Directory entries hold OS handles. When are these closed? Reference counting? Explicit close? Scope-based? A deeply nested directory walk could open many handles — is there a limit or LRU cache? On Linux `ulimit -n` is typically 1024; we may need handle pooling.
- **File watching** — OS-level change notifications on entries. Important, but doesn't change the core API.
- **Glob patterns** — Recursive listing with patterns (`**/*.txt`). Likely a library function that walks entries.
- **Promote vs. restrict** — `|promote-root` creates a new root scope with its own namespace. `|restrict` narrows permissions but stays in the same root. These are different operations with different implications. Is the distinction clear enough in the API?
- **Cross-root operations** — `|move` between entries in different roots is conceptually a copy+delete. Should it be disallowed, explicit, or transparent?
- **Root discovery** — When resolving an absolute path, the runtime searches roots. What order? Longest-prefix match? Explicit search path? What if a promoted root shadows part of a platform root?
- **Overlay conflict semantics** — When the same name exists in multiple overlay layers, reads take the topmost. But what about `|list`? Union of all layers? What about conflicting kinds (file in one layer, dir in another)?
- **Entry equality granularity** — `==` compares snapshot data. How deep? Just kind+size+mtime? Or full stat? Platform differences in available metadata make this tricky.
- **Relative path remapping library** — Core API for remapping relative paths between entries/roots. Essential for untangling cross-root symlinks and namespace projection patterns. What operations does this need?